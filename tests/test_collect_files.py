"""End-to-end behaviour of the file collector against a synthetic home tree."""
from __future__ import annotations

import json

import pytest

from waib.collect.files import FileCollector, _matches
from waib.model import Item


@pytest.fixture()
def collector(tmp_path):
    return FileCollector(tmp_path / "out", capture_secrets=True)


def test_matches_handles_root_level_files():
    """'**/*.json' must also match a file sitting directly in the directory."""
    assert _matches("opencode.json", ("**/*.json",))
    assert _matches("nested/deep/opencode.json", ("**/*.json",))
    assert not _matches("opencode.toml", ("**/*.json",))


def test_config_is_copied_with_secrets_redacted(tmp_path, collector):
    source = tmp_path / "settings.json"
    source.write_text(json.dumps({"model": "opus", "apiKey": "abcdef123456"}), encoding="utf-8")

    captured = collector.collect_item(Item(str(source), "config"))
    assert len(captured) == 1
    stored = json.loads((collector.files_root / captured[0].archive[len("files/"):]).read_text())
    assert stored["model"] == "opus"
    assert stored["apiKey"] == "<<WAIB:REDACTED>>"
    assert captured[0].redactions == ("apiKey",)


def test_real_secret_goes_to_the_vault(tmp_path, collector):
    source = tmp_path / "settings.json"
    source.write_text(json.dumps({"apiKey": "abcdef123456"}), encoding="utf-8")
    collector.collect_item(Item(str(source), "config"))
    assert any("abcdef123456" in v for group in collector.vault.values() for v in group.values())


def test_prompt_files_are_mirrored_into_prompts_dir(tmp_path, collector):
    source = tmp_path / "CLAUDE.md"
    source.write_text("# master prompt", encoding="utf-8")
    captured = collector.collect_item(Item(str(source), "prompt"))
    rel = captured[0].archive[len("files/"):]
    assert (collector.prompts_root / rel).read_text(encoding="utf-8") == "# master prompt"


def test_secret_kind_is_never_written_in_the_clear(tmp_path, collector):
    source = tmp_path / ".credentials.json"
    source.write_text('{"token": "sk-ant-xyz"}', encoding="utf-8")
    captured = collector.collect_item(Item(str(source), "secret"))
    assert captured[0].archive is None
    assert "vault" in captured[0].skipped_reason
    assert not list(collector.files_root.rglob("*.json"))


def test_secret_excluded_entirely_without_capture_flag(tmp_path):
    plain = FileCollector(tmp_path / "out2", capture_secrets=False)
    source = tmp_path / ".credentials.json"
    source.write_text('{"token": "sk-ant-xyz"}', encoding="utf-8")
    captured = plain.collect_item(Item(str(source), "secret"))
    assert plain.vault == {}
    assert "--secrets" in captured[0].skipped_reason


def test_record_kind_notes_size_without_copying(tmp_path, collector):
    heavy = tmp_path / "cache_dir"
    heavy.mkdir()
    (heavy / "blob.dat").write_bytes(b"x" * 2048)
    captured = collector.collect_item(Item(str(heavy), "record"))
    assert captured[0].archive is None
    assert captured[0].size == 2048


def test_oversized_file_is_skipped_with_a_reason(tmp_path, collector):
    source = tmp_path / "big.json"
    source.write_bytes(b"{}" + b" " * 4096)
    captured = collector.collect_item(Item(str(source), "config", max_file_mb=0.001))
    assert captured[0].archive is None
    assert "cap" in captured[0].skipped_reason


def test_tree_respects_include_and_exclude(tmp_path, collector):
    root = tmp_path / "skills"
    (root / "keep").mkdir(parents=True)
    (root / "keep" / "SKILL.md").write_text("keep me", encoding="utf-8")
    (root / "keep" / "notes.txt").write_text("drop me", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "SKILL.md").write_text("junk", encoding="utf-8")

    captured = collector.collect_item(Item(str(root), "tree", include=("**/*.md",)))
    stored = [c.source for c in captured if c.archive]
    assert len(stored) == 1
    assert stored[0].endswith("SKILL.md")
    assert "node_modules" not in stored[0]


def test_missing_path_yields_nothing(collector):
    assert collector.collect_item(Item("Z:/does/not/exist", "config")) == []


def test_deep_destination_path_does_not_abort_the_tree(tmp_path):
    """The archive path is far longer than the source; MAX_PATH must not lose files.

    This is the real shape of the bug: a short source tree under the home
    directory, written into a backup folder nested deep enough that the mirrored
    path crosses 260 characters.
    """
    deep = tmp_path / ("d" * 70) / ("e" * 70) / ("f" * 70)
    collector = FileCollector(deep, capture_secrets=False)

    root = tmp_path / "skills"
    nested = root / "clerk-react-router-patterns" / "templates" / "basic-auth" / "app"
    nested.mkdir(parents=True)
    for index in range(5):
        (nested / f"route{index}.md").write_text(f"# route {index}", encoding="utf-8")

    captured = collector.collect_item(Item(str(root), "tree", include=("**/*.md",)))
    copied = [c for c in captured if c.archive]
    assert len(copied) == 5, [c.skipped_reason for c in captured if not c.archive]
