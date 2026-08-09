"""A backup is only worth taking if it restores. This proves the loop closes."""
from __future__ import annotations

import json

import pytest

from waib import restore as restore_engine
from waib.backup import run_backup
from waib.collect import packages


@pytest.fixture(scope="module")
def backup(tmp_path_factory):
    """One real backup of this machine, shared by every test in the module.

    A full scan is the most expensive thing in the suite; running it per-test
    would make the build take minutes for no extra coverage.
    """
    return run_backup(
        destination=tmp_path_factory.mktemp("roundtrip"),
        capture_secrets=False,
        make_zip=False,
        progress=lambda _msg: None,
    )


def test_backup_produces_the_expected_artifacts(backup):
    folder = backup["folder"]
    for name in ("INVENTORY.json", "INVENTORY.md", "RESTORE.md", "restore.ps1"):
        assert (folder / name).is_file(), name
    for registry in ("mcp", "plugins", "models", "packages", "extensions", "identity", "env", "local_servers"):
        assert (folder / "registry" / f"{registry}.json").is_file(), registry


def test_inventory_is_self_consistent(backup):
    data = json.loads((backup["folder"] / "INVENTORY.json").read_text(encoding="utf-8"))
    copied = [f for t in data["targets"] for f in t["files"] if f["archive"]]
    assert data["summary"]["files_copied"] == len(copied)
    assert data["summary"]["mcp_servers"] == len(data["registries"]["mcp"]["servers"])


def test_every_archived_file_actually_exists(backup):
    """Path.is_file() lies past MAX_PATH, so check through the long-path API."""
    import os

    from waib.copyio import long_path

    folder = backup["folder"]
    data = json.loads((folder / "INVENTORY.json").read_text(encoding="utf-8"))
    missing = [
        f["archive"]
        for t in data["targets"]
        for f in t["files"]
        if f["archive"] and not os.path.isfile(long_path(folder / f["archive"]))
    ]
    assert missing == []


def test_no_credential_file_was_copied_in_the_clear(backup):
    folder = backup["folder"]
    data = json.loads((folder / "INVENTORY.json").read_text(encoding="utf-8"))
    secrets = [f for t in data["targets"] for f in t["files"] if f["kind"] == "secret"]
    assert all(f["archive"] is None for f in secrets)
    assert not list((folder / "files").rglob(".credentials.json"))


def test_dry_run_restore_resolves_every_stored_file(backup):
    result = restore_engine.restore_files(backup["folder"], dry_run=True, progress=lambda _m: None)
    assert result["dry_run"] is True
    assert result["skipped"] == []
    assert len(result["applied"]) > 0


def test_restore_writes_files_back(tmp_path, monkeypatch, backup):
    """Redirect USERPROFILE so a real write lands in a sandbox, not the live home."""
    sandbox = tmp_path / "fresh-machine"
    sandbox.mkdir()
    monkeypatch.setenv("USERPROFILE", str(sandbox))

    result = restore_engine.restore_files(backup["folder"], dry_run=False, progress=lambda _m: None)
    written = [p for p in result["applied"] if str(sandbox) in p]
    assert written, "expected at least one file restored into the sandboxed profile"


def test_package_classifier_ignores_lookalike_names():
    assert not packages._is_ai("Windows Mail")
    assert not packages._is_ai("Mozilla Maintenance Service")
    assert not packages._is_ai("Portrait Displays")
    assert packages._is_ai("@openai/codex")
    assert packages._is_ai("firecrawl-mcp")
    assert packages._is_ai("open-ai-tools")
