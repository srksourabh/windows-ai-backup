"""Secrets must never reach the plain-text side of a backup."""
from __future__ import annotations

from waib.util import REDACTED, extract_secrets, looks_secret, redact


def test_redacts_by_key_name():
    clean, found = redact({"mcpServers": {"x": {"env": {"API_KEY": "abcdef123456"}}}})
    assert clean["mcpServers"]["x"]["env"]["API_KEY"] == REDACTED
    assert found == ["mcpServers.x.env.API_KEY"]


def test_redacts_by_value_shape_under_innocent_key():
    clean, found = redact({"note": "sk-ant-api03-AAAABBBBCCCCDDDDEEEE"})
    assert clean["note"] == REDACTED
    assert found == ["note"]


def test_leaves_ordinary_values_alone():
    original = {"model": "claude-opus-5", "args": ["-y", "some-package"], "port": 8080}
    clean, found = redact(original)
    assert clean == original
    assert found == []


def test_redact_does_not_mutate_input():
    original = {"token": "abcdef123456"}
    redact(original)
    assert original["token"] == "abcdef123456"


def test_short_values_are_not_treated_as_secrets():
    assert not looks_secret("api_key", "")
    assert not looks_secret("api_key", "true")


def test_extract_secrets_finds_the_real_values():
    data = {"servers": {"a": {"headers": {"Authorization": "Bearer abcdefghijkl"}}}}
    assert extract_secrets(data) == {"servers.a.headers.Authorization": "Bearer abcdefghijkl"}


def test_nested_lists_are_walked():
    clean, found = redact({"items": [{"password": "hunter2hunter2"}]})
    assert clean["items"][0]["password"] == REDACTED
    assert found == ["items[0].password"]


def test_secret_after_a_flag_is_redacted():
    """`["--access-token", "sbp_live..."]` hides a credential in a position."""
    clean, found = redact({"args": ["-y", "@supabase/mcp", "--access-token", "sbp_" + "a" * 24]})
    assert clean["args"] == ["-y", "@supabase/mcp", "--access-token", REDACTED]
    assert found == ["args[3]"]


def test_inline_flag_value_is_redacted_but_flag_survives():
    clean, found = redact({"args": ["--api-key=abcdef1234567890"]})
    assert clean["args"] == ["--api-key=" + REDACTED]
    assert found == ["args[0]"]


def test_ordinary_flags_and_values_are_untouched():
    original = {"args": ["-y", "firecrawl-mcp", "--port", "8080"]}
    clean, found = redact(original)
    assert clean == original
    assert found == []


def test_extract_recovers_positional_secrets():
    token = "sbp_" + "a" * 24
    assert extract_secrets({"args": ["--access-token", token]}) == {"args[1]": token}


def test_vendor_token_shapes_are_caught_by_value():
    for token in ("gsk_" + "a" * 24, "pplx-" + "b" * 24, "r8_" + "c" * 24, "nvapi-" + "d" * 24):
        clean, found = redact({"note": token})
        assert clean["note"] == REDACTED, token
        assert found == ["note"]


def test_git_sha_is_not_mistaken_for_a_secret():
    """40-char hex runs are commit SHAs and content hashes, not credentials."""
    original = {"originalHeadCommit": "a" * 40, "contentHash": "b" * 64}
    clean, found = redact(original)
    assert clean == original
    assert found == []


def test_uuid_segment_is_not_mistaken_for_a_firecrawl_key():
    from waib.scrub import scrub_text

    text = '"sessionId": "64dc2422-befc-4ac1-9536-10203c2efe6e"'
    clean, count = scrub_text(text)
    assert clean == text
    assert count == 0
