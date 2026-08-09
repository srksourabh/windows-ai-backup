"""The vault has to survive a machine wipe, so it must be passphrase-only."""
from __future__ import annotations

import pytest

from waib.secrets_vault import VaultError, open_vault, seal

PAYLOAD = {
    "files": {r"%USERPROFILE%\.claude\.credentials.json": '{"token": "sk-ant-secret"}'},
    "environment": {"OPENAI_API_KEY": "sk-live-value"},
}


def test_round_trip(tmp_path):
    path = seal(PAYLOAD, "a strong passphrase", tmp_path / "secrets.vault")
    assert open_vault(path, "a strong passphrase") == PAYLOAD


def test_wrong_passphrase_is_rejected(tmp_path):
    path = seal(PAYLOAD, "right", tmp_path / "secrets.vault")
    with pytest.raises(VaultError):
        open_vault(path, "wrong")


def test_ciphertext_contains_no_plaintext(tmp_path):
    path = seal(PAYLOAD, "pass", tmp_path / "secrets.vault")
    raw = path.read_bytes()
    assert b"sk-ant-secret" not in raw
    assert b"OPENAI_API_KEY" not in raw


def test_empty_passphrase_refused(tmp_path):
    with pytest.raises(VaultError):
        seal(PAYLOAD, "", tmp_path / "secrets.vault")


def test_non_vault_file_is_detected(tmp_path):
    stray = tmp_path / "secrets.vault"
    stray.write_bytes(b"not a vault at all")
    with pytest.raises(VaultError):
        open_vault(stray, "pass")


def test_each_seal_uses_a_fresh_nonce(tmp_path):
    first = seal(PAYLOAD, "pass", tmp_path / "one.vault").read_bytes()
    second = seal(PAYLOAD, "pass", tmp_path / "two.vault").read_bytes()
    assert first != second
