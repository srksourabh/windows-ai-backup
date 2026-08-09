"""Text-level scrubbing is the layer that catches keys structured parsing misses."""
from __future__ import annotations

import pytest

from waib.scrub import REDACTED, is_secret_filename, scrub_file, scrub_text


def test_hardcoded_key_in_source_is_removed():
    source = 'const API_KEY = "AIza' + "S" * 35 + '";'
    clean, count = scrub_text(source)
    assert count >= 1
    assert "AIza" not in clean


def test_token_embedded_in_a_longer_string_is_removed():
    text = '"command": "npx server --token sk-' + "a" * 30 + ' --port 3000"'
    clean, count = scrub_text(text)
    assert count >= 1
    assert "sk-" not in clean
    assert "--port 3000" in clean


def test_placeholders_are_preserved():
    for placeholder in ('api_key = "your-api-key-here"', 'token = "${GITHUB_TOKEN}"',
                        'apiKey = "process.env.OPENAI_KEY"'):
        clean, count = scrub_text(placeholder)
        assert count == 0, placeholder
        assert clean == placeholder


def test_scrubbing_is_idempotent():
    once, first = scrub_text("key: sk-" + "z" * 30)
    twice, second = scrub_text(once)
    assert second == 0
    assert once == twice


def test_private_key_block_is_removed():
    pem = "-----BEGIN RSA PRIVATE KEY-----\n" + "MIIE" * 20 + "\n-----END RSA PRIVATE KEY-----"
    clean, count = scrub_text(pem)
    assert count == 1
    assert clean.strip() == REDACTED


def test_scrub_file_rewrites_only_when_needed(tmp_path):
    clean_file = tmp_path / "ok.json"
    clean_file.write_text('{"model": "opus"}', encoding="utf-8")
    before = clean_file.stat().st_mtime_ns
    assert scrub_file(clean_file) == 0
    assert clean_file.stat().st_mtime_ns == before


def test_scrub_file_leaves_binary_alone(tmp_path):
    blob = tmp_path / "weights.bin"
    blob.write_bytes(bytes(range(256)))
    assert scrub_file(blob) == 0
    assert blob.read_bytes() == bytes(range(256))


@pytest.mark.parametrize("name", [
    ".credentials.json", "auth.json", "secrets.json", "oauth_creds.json",
    ".env", ".env.local", "id_ed25519", "server.pem", "private.key", ".netrc",
])
def test_credential_filenames_are_recognised(name):
    assert is_secret_filename(name)


@pytest.mark.parametrize("name", ["settings.json", "CLAUDE.md", "mcp.json", "package.json"])
def test_ordinary_filenames_are_not(name):
    assert not is_secret_filename(name)
