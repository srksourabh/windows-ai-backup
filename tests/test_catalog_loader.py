"""The catalog is data now, so its integrity is a test concern, not a review one."""
from __future__ import annotations

import json

import pytest

from waib import catalog_loader
from waib.catalog_loader import CatalogError


@pytest.fixture(autouse=True)
def clean_cache():
    catalog_loader.reset_cache()
    yield
    catalog_loader.reset_cache()


def test_bundled_catalog_loads_without_warnings():
    loaded, issues = catalog_loader.load_targets()
    assert issues == [], issues
    assert len(loaded) >= 80, "the shipped catalog should cover a large tool set"


def test_every_tool_has_an_id_name_and_detect_path():
    for target in catalog_loader.load_targets()[0]:
        assert target.id and target.name and target.detect, target.id


def test_tool_ids_are_unique_across_files():
    seen: dict[str, str] = {}
    for path in catalog_loader.catalog_files():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for entry in payload.get("tools", []):
            tool_id = entry["id"]
            assert tool_id not in seen, f"{tool_id} defined in both {seen[tool_id]} and {path.name}"
            seen[tool_id] = path.name


def test_every_item_kind_is_valid():
    for path in catalog_loader.catalog_files():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for entry in payload.get("tools", []):
            for item in entry.get("items", []):
                assert item.get("kind", "config") in catalog_loader.VALID_KINDS, item


def test_every_mcp_source_uses_a_known_dialect():
    for path in catalog_loader.catalog_files():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for entry in payload.get("tools", []):
            for source in entry.get("mcp_sources", []):
                assert source["fmt"] in catalog_loader.VALID_FORMATS, source


def test_user_entries_override_bundled_ones(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    local = tmp_path / "WindowsAIBackup" / "catalog.local"
    local.mkdir(parents=True)
    (local / "override.json").write_text(json.dumps({"tools": [{
        "id": "claude-code", "name": "My Claude Code", "category": "Custom",
        "detect": ["~/.claude"], "items": [{"path": "~/.claude/settings.json", "kind": "config"}],
    }]}), encoding="utf-8")

    catalog_loader.reset_cache()
    override = catalog_loader.by_id("claude-code")
    assert override is not None
    assert override.name == "My Claude Code"


def test_a_user_can_add_an_entirely_new_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    local = tmp_path / "WindowsAIBackup" / "catalog.local"
    local.mkdir(parents=True)
    (local / "inhouse.json").write_text(json.dumps({"tools": [{
        "id": "acme-internal-agent", "name": "Acme Internal Agent", "category": "Agent CLI",
        "detect": ["~/.acme"], "items": [{"path": "~/.acme/config.json", "kind": "config"}],
    }]}), encoding="utf-8")

    catalog_loader.reset_cache()
    assert catalog_loader.by_id("acme-internal-agent") is not None


def test_a_broken_file_is_reported_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    local = tmp_path / "WindowsAIBackup" / "catalog.local"
    local.mkdir(parents=True)
    (local / "broken.json").write_text("{ not json", encoding="utf-8")

    catalog_loader.reset_cache()
    loaded, issues = catalog_loader.load_targets()
    assert loaded, "a broken user file must not wipe the bundled catalog"
    assert any("broken.json" in issue for issue in issues)


def test_strict_mode_raises_on_a_bad_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    local = tmp_path / "WindowsAIBackup" / "catalog.local"
    local.mkdir(parents=True)
    (local / "bad.json").write_text(json.dumps({"tools": [{"id": "x", "name": "X"}]}), encoding="utf-8")

    catalog_loader.reset_cache()
    with pytest.raises(CatalogError):
        catalog_loader.load_targets(strict=True)


def test_resolve_ids_accepts_ids_and_display_names():
    resolved, unknown = catalog_loader.resolve_ids(["claude-code", "Cursor", "nope-not-real"])
    assert "claude-code" in resolved
    assert "cursor" in resolved
    assert unknown == ["nope-not-real"]


def test_categories_partition_the_catalog():
    grouped = catalog_loader.categories()
    total = sum(len(v) for v in grouped.values())
    assert total == len(catalog_loader.targets())
