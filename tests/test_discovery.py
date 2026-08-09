"""Discovery is what lets the tool cover more than the catalog lists."""
from __future__ import annotations

import json

import pytest

from waib import discovery


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    """Point every search root at a sandbox so tests never read the real home."""
    monkeypatch.setattr(discovery, "SEARCH_ROOTS", (str(tmp_path),))
    return tmp_path


def _make(root, name, files: dict[str, str]):
    directory = root / name
    for rel, content in files.items():
        target = directory / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def test_finds_a_tool_by_its_mcp_config(fake_home):
    _make(fake_home, "totally-unknown-tool",
          {"mcp.json": json.dumps({"mcpServers": {"x": {"command": "npx"}}})})
    found = discovery.scan()
    assert [d.name for d in found] == ["totally-unknown-tool"]
    assert found[0].mcp_files == ("mcp.json",)


def test_finds_a_tool_by_its_agent_instruction_file(fake_home):
    _make(fake_home, "some-editor", {"AGENTS.md": "# how to behave"})
    found = discovery.scan()
    assert [d.name for d in found] == ["some-editor"]
    assert "AGENTS.md" in found[0].instruction_files


def test_name_alone_is_enough_for_a_known_vendor(fake_home):
    _make(fake_home, "acme-claude-helper", {"readme.txt": "hello"})
    assert [d.name for d in discovery.scan()] == ["acme-claude-helper"]


def test_ordinary_directories_are_ignored(fake_home):
    _make(fake_home, "holiday-photos", {"notes.txt": "beach"})
    _make(fake_home, "invoices", {"q1.json": json.dumps({"total": 10})})
    assert discovery.scan() == []


def test_a_code_project_is_not_a_tool(fake_home):
    """An AGENTS.md in a repo is project context, not a tool to restore."""
    project = _make(fake_home, "my-app", {"AGENTS.md": "# project rules"})
    (project / "package.json").write_text("{}", encoding="utf-8")
    assert discovery.scan() == []


def test_extension_stores_are_skipped(fake_home):
    _make(fake_home, ".vscode", {"extensions/foo/mcp.json": json.dumps({"mcpServers": {}})})
    assert discovery.scan() == []


def test_cloud_sync_roots_are_skipped(fake_home):
    _make(fake_home, "Dropbox", {"work/mcp.json": json.dumps({"mcpServers": {"a": {}}})})
    assert discovery.scan() == []


def test_catalogued_paths_are_not_reported_again(fake_home):
    directory = _make(fake_home, "claude-thing", {"AGENTS.md": "x"})
    from waib.paths import portable

    assert discovery.scan(known_paths={portable(directory)}) == []


def test_weak_evidence_alone_is_below_the_threshold(fake_home):
    """One vague signal is not enough — that is how false positives are kept out."""
    _make(fake_home, "weak-ai-thing", {"settings.json": json.dumps({"model": "x"})})
    assert discovery.scan() == []


def test_score_ranks_stronger_evidence_first(fake_home):
    _make(fake_home, "gpt-notes", {"config.json": json.dumps({"model": "x"})})
    _make(fake_home, "strong-claude-thing",
          {"AGENTS.md": "x", "mcp.json": json.dumps({"mcpServers": {"a": {"command": "npx"}}})})
    found = discovery.scan()
    assert [d.name for d in found][0] == "strong-claude-thing"
    assert found[0].score > found[-1].score


def test_to_target_captures_the_evidence_not_the_whole_tree(fake_home):
    _make(fake_home, "mystery-agent", {
        "AGENTS.md": "# rules",
        "mcp.json": json.dumps({"mcpServers": {"a": {"command": "npx"}}}),
        "extensions/big/payload.json": "{}",
    })
    target = discovery.to_target(discovery.scan()[0])
    paths = [item.path for item in target.items]
    assert any(p.endswith("AGENTS.md") for p in paths)
    assert any(p.endswith("mcp.json") for p in paths)

    sweep = [i for i in target.items if i.kind == "tree"][0]
    assert sweep.max_total_mb <= 5, "an unknown directory must not be swept wholesale"
    assert any("extensions" in pattern for pattern in sweep.exclude)


def test_discovered_target_is_marked_as_such(fake_home):
    _make(fake_home, "mystery-agent", {"AGENTS.md": "# rules"})
    target = discovery.to_target(discovery.scan()[0])
    assert target.category == "Discovered"
    assert target.id.startswith("discovered-")
    assert "discovered" in target.name.lower()
