"""Collect the account identifiers needed to sign back in after a rebuild.

Only non-secret identity is captured here: emails, account/org/user ids, machine
ids, install ids, subscription tier. Tokens live in the encrypted vault.
"""
from __future__ import annotations

from typing import Any

from ..paths import expand, portable
from ..util import load_structured, run

#: (label, settings file, keys to lift — dotted paths supported)
ID_SOURCES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Claude Code", "~/.claude.json", (
        "oauthAccount", "userID", "anonymousId", "machineID", "installMethod",
        "hasAvailableSubscription", "firstStartTime", "claudeCodeFirstTokenDate",
    )),
    ("Gemini CLI", "~/.gemini/google_accounts.json", ("active", "accounts")),
    ("Gemini CLI", "~/.gemini/installation_id", ()),
    ("Codex CLI", "~/.codex/.codex-global-state.json", ("accountId", "email", "plan", "userId")),
    ("Copilot CLI", "~/.copilot/config.json", ("user", "account", "login", "device_id")),
    ("Kimi CLI", "~/.kimi-code/device_id", ()),
    ("Cursor", "~/.cursor/cli-config.json", ("userId", "email", "teamId")),
    ("LM Studio", "~/.lmstudio/.internal/user.json", ("userId", "email")),
    ("Hugging Face", "~/.cache/huggingface/stored_tokens", ()),
)

#: Keys that must never leave the machine unencrypted, even from an ID source.
DROP = ("accesstoken", "refreshtoken", "idtoken", "apikey", "secret", "password")


def _prune(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if k.lower().replace("_", "") not in DROP}
    if isinstance(value, list):
        return [_prune(v) for v in value]
    return value


def _dig(data: Any, dotted: str) -> Any:
    node = data
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def _git_identity() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("user.name", "user.email"):
        code, value = run(["git", "config", "--global", key], timeout=20)
        if code == 0 and value.strip():
            out[key] = value.strip()
    code, value = run(["gh", "auth", "status"], timeout=30)
    if code == 0:
        accounts = [line.strip() for line in value.splitlines() if "account" in line.lower()]
        if accounts:
            out["github_cli"] = accounts
    return out


def collect() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for label, spec, keys in ID_SOURCES:
        path = expand(spec)
        if not path.exists():
            continue

        if not keys:
            try:
                raw = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            entries.append({"client": label, "source": portable(path), "values": {path.name: raw[:400]}})
            continue

        data = load_structured(path)
        if not isinstance(data, dict):
            continue
        values = {k: _prune(_dig(data, k)) for k in keys}
        values = {k: v for k, v in values.items() if v not in (None, {}, [])}
        if values:
            entries.append({"client": label, "source": portable(path), "values": values})

    return {"accounts": entries, "git": _git_identity()}
