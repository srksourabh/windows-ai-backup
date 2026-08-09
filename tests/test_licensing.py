"""Edition gating must be honest: real keys work, fakes don't, restore never locks."""
from __future__ import annotations

import base64
import json

import pytest

from waib import licensing
from waib.licensing import Edition


def _sign(payload: dict, private) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    envelope = {
        "payload": base64.b64encode(payload_bytes).decode(),
        "signature": base64.b64encode(private.sign(payload_bytes)).decode(),
    }
    return base64.urlsafe_b64encode(json.dumps(envelope, separators=(",", ":")).encode()).decode().rstrip("=")


@pytest.fixture()
def publisher(monkeypatch):
    """A throwaway keypair standing in for the real publisher key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    monkeypatch.setattr(licensing, "PUBLISHER_PUBLIC_KEY", base64.b64encode(public).decode())
    return private


def test_valid_key_grants_premium(publisher):
    key = _sign({"edition": "premium", "name": "Jane Doe", "issued": "2026-08-09"}, publisher)
    result = licensing.parse_key(key)
    assert result.edition is Edition.PREMIUM
    assert result.is_premium
    assert result.name == "Jane Doe"


def test_key_signed_by_someone_else_is_rejected(publisher):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    forged = _sign({"edition": "premium", "name": "Attacker"}, Ed25519PrivateKey.generate())
    result = licensing.parse_key(forged)
    assert not result.is_premium
    assert "signature" in result.invalid_reason


def test_tampering_with_the_payload_breaks_the_signature(publisher):
    key = _sign({"edition": "premium", "name": "Jane"}, publisher)
    blob = json.loads(base64.urlsafe_b64decode(key + "=" * (-len(key) % 4)))
    payload = json.loads(base64.b64decode(blob["payload"]))
    payload["name"] = "Someone Else"
    blob["payload"] = base64.b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).decode()
    tampered = base64.urlsafe_b64encode(json.dumps(blob).encode()).decode().rstrip("=")
    assert not licensing.parse_key(tampered).is_premium


@pytest.mark.parametrize("junk", ["", "not-a-key", "!!!!", base64.urlsafe_b64encode(b"{}").decode()])
def test_garbage_never_grants_premium(publisher, junk):
    assert not licensing.parse_key(junk).is_premium


def test_a_non_premium_edition_claim_is_refused(publisher):
    key = _sign({"edition": "enterprise", "name": "Jane"}, publisher)
    result = licensing.parse_key(key)
    assert not result.is_premium
    assert "not a Premium key" in result.invalid_reason


def test_install_and_remove_round_trip(publisher, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    key = _sign({"edition": "premium", "email": "a@b.c"}, publisher)

    assert licensing.load().edition is Edition.DEMO
    assert licensing.install(key).is_premium
    assert licensing.load().is_premium
    assert licensing.remove() is True
    assert licensing.load().edition is Edition.DEMO


def test_bad_key_is_not_written_to_disk(publisher, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert not licensing.install("garbage").is_premium
    assert not licensing.license_file().exists()


def test_demo_preference_list_references_real_catalog_ids():
    from waib import catalog_loader

    known = {t.id for t in catalog_loader.targets()}
    unknown = [t for t in licensing.DEMO_PREFERRED_ORDER if t not in known]
    assert unknown == [], f"preferred demo tools missing from the catalog: {unknown}"


def test_demo_selection_honours_an_explicit_choice():
    present = ["ollama", "vscode", "aider", "claude-code", "zed", "goose", "jan"]
    chosen = licensing.demo_selection(present, ["zed", "jan", "aider"])
    assert chosen == ["zed", "jan", "aider"]


def test_demo_selection_caps_at_the_limit():
    present = [f"tool-{i}" for i in range(20)]
    chosen = licensing.demo_selection(present, present)
    assert len(chosen) == licensing.DEMO_TOOL_LIMIT


def test_demo_selection_ignores_tools_that_are_not_installed():
    chosen = licensing.demo_selection(["ollama"], ["zed", "ollama"])
    assert chosen == ["ollama"]


def test_demo_selection_falls_back_to_the_preferred_order():
    present = ["zzz-unknown", "cursor", "claude-code"]
    chosen = licensing.demo_selection(present)
    assert chosen[:2] == ["claude-code", "cursor"]
    assert len(chosen) == 3


def test_secrets_are_refused_without_premium(tmp_path, monkeypatch):
    from waib.backup import run_backup

    monkeypatch.setenv("APPDATA", str(tmp_path))
    with pytest.raises(ValueError, match="Premium"):
        run_backup(tmp_path / "out", capture_secrets=True, passphrase="x",
                   make_zip=False, progress=lambda _m: None, license=licensing.DEMO)


@pytest.fixture(scope="module")
def demo_backup(tmp_path_factory):
    """One demo backup shared across the edition tests - a full scan is costly."""
    from waib.backup import run_backup

    return run_backup(tmp_path_factory.mktemp("demo"), make_zip=False,
                      progress=lambda _m: None, license=licensing.DEMO,
                      tools=["gemini-cli", "copilot-cli", "claude-desktop"])


def test_restore_is_never_gated(demo_backup):
    """A backup you already made must stay restorable in any edition."""
    from waib import restore as restore_engine

    result = restore_engine.restore_files(demo_backup["folder"], dry_run=True,
                                          progress=lambda _m: None)
    assert result["skipped"] == []
    assert len(result["applied"]) > 0


def test_demo_backup_is_labelled_and_lists_what_it_skipped(demo_backup):
    inventory = demo_backup["inventory"]
    assert inventory["edition"] == "demo"
    assert inventory["demo_skipped_tools"]
    assert "Demo backup" in (demo_backup["folder"] / "INVENTORY.md").read_text(encoding="utf-8")
