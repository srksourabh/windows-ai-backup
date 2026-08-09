"""Capture AI-related environment variables.

Names are always recorded (restore needs to know *which* variables to set again).
Values are recorded only when they are not credentials; credential values go to
the encrypted vault when ``--secrets`` is used.
"""
from __future__ import annotations

import os
import re
from typing import Any

from ..util import looks_secret, run

NAME_PATTERN = re.compile(
    r"(ANTHROPIC|CLAUDE|OPENAI|AZURE_OPENAI|GEMINI|GOOGLE_API|GOOGLE_GENAI|VERTEX|"
    r"COPILOT|GITHUB_TOKEN|HUGGING|HF_|GROQ|MISTRAL|COHERE|DEEPSEEK|TOGETHER|"
    r"FIREWORKS|OPENROUTER|PERPLEXITY|XAI|GROK|NVIDIA|REPLICATE|OLLAMA|LMSTUDIO|"
    r"LM_STUDIO|MCP_|AIDER|CURSOR|WINDSURF|CODEX|LANGCHAIN|LANGSMITH|LLAMA|"
    r"AI_|_AI$|LLM|EMBEDDING|PINECONE|WEAVIATE|QDRANT|CHROMA|SERPAPI|TAVILY|"
    r"EXA_|FIRECRAWL|BRAVE_|E2B_|DAYTONA)",
    re.IGNORECASE,
)

#: Session-scoped noise that must not be restored.
EPHEMERAL = re.compile(
    r"^(CLAUDE_CODE_(SESSION_ID|CHILD_SESSION|ENTRYPOINT|EXECPATH)|CLAUDE_PID|CLAUDECODE|"
    r"CLAUDE_EFFORT|AI_AGENT|MCP_TIMEOUT)$",
    re.IGNORECASE,
)


def _persistent_user_vars() -> dict[str, str]:
    """Read HKCU\\Environment so we capture what survives a reboot, not the session."""
    script = (
        "[Environment]::GetEnvironmentVariables('User').GetEnumerator() | "
        "ForEach-Object { $_.Key + '=' + $_.Value }"
    )
    code, out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=60)
    if code != 0:
        return {}
    result: dict[str, str] = {}
    for line in out.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip():
            result[key.strip()] = value
    return result


def collect(capture_secrets: bool) -> tuple[dict[str, Any], dict[str, str]]:
    """Return ``(inventory, vault_payload)``."""
    persistent = _persistent_user_vars()
    session = dict(os.environ)

    entries: list[dict[str, Any]] = []
    vault: dict[str, str] = {}
    # Windows env vars are case-insensitive; persistent spellings win over session ones.
    ordered = sorted(set(persistent) | set(session), key=lambda n: (n not in persistent, n))
    unique: dict[str, str] = {}
    for name in ordered:
        unique.setdefault(name.upper(), name)

    for name in sorted(unique.values()):
        if not NAME_PATTERN.search(name) or EPHEMERAL.match(name):
            continue
        value = persistent.get(name, session.get(name, ""))
        scope = "user (persistent)" if name in persistent else "session only"
        secret = looks_secret(name, value)
        entry: dict[str, Any] = {
            "name": name,
            "scope": scope,
            "is_secret": secret,
            "restore": f'setx {name} "<value>"' if secret else f'setx {name} "{value}"',
        }
        if secret:
            entry["value"] = "<<WAIB:REDACTED>>"
            entry["value_length"] = len(value)
            if capture_secrets and value:
                vault[name] = value
        else:
            entry["value"] = value
        entries.append(entry)

    return (
        {
            "count": len(entries),
            "note": "Only 'user (persistent)' variables should be recreated; session vars are transient.",
            "variables": entries,
        },
        vault,
    )
