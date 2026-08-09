"""Inventory the AI tooling installed through package managers.

Payloads are never copied — only the identity of each package, so restore can
reinstall from the network.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ..paths import expand
from ..util import run

#: Distinctive enough to match anywhere inside a package name.
STRONG_HINTS = (
    "claude", "anthropic", "openai", "codex", "copilot", "gemini", "cursor",
    "cline", "aider", "ollama", "lmstudio", "lm-studio", "windsurf", "perplexity",
    "huggingface", "langchain", "llama", "mistral", "qodo", "kilocode", "opencode",
    "antigravity", "devin", "deepseek", "flowise", "chatgpt", "gpt-", "-gpt",
    "openrouter", "together-ai", "groq", "cohere", "replicate", "whisper",
    "stable-diffusion", "comfyui", "autogen", "crewai", "litellm", "vllm",
)

#: Short and ambiguous — only count them as whole words ("ai", not "Mail").
WEAK_HINTS = ("ai", "llm", "gpt", "mcp", "agent", "agents", "goose", "roo", "kimi", "grok", "n8n")

_WEAK_PATTERN = re.compile(r"(?:^|[^a-z0-9])(" + "|".join(WEAK_HINTS) + r")(?:[^a-z0-9]|$)")


def _is_ai(name: str) -> bool:
    """True when a package name plausibly identifies an AI tool.

    Word-boundary matching for short tokens keeps 'Windows Mail' and
    'Mozilla Maintenance Service' out of the AI inventory.
    """
    lowered = name.lower()
    if any(hint in lowered for hint in STRONG_HINTS):
        return True
    return bool(_WEAK_PATTERN.search(lowered))


def _npm_globals() -> list[dict[str, Any]]:
    code, out = run(["npm", "ls", "-g", "--depth=0", "--json"], timeout=120)
    if code not in (0, 1) or not out.strip().startswith("{"):
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return [
        {
            "name": name,
            "version": (info or {}).get("version"),
            "manager": "npm",
            "restore": f"npm install -g {name}@latest",
            "ai_related": _is_ai(name),
        }
        for name, info in (data.get("dependencies") or {}).items()
        if name != "npm"
    ]


def _uv_tools() -> list[dict[str, Any]]:
    root = expand("%APPDATA%/uv/tools")
    if not root.is_dir():
        return []
    return [
        {
            "name": entry.name,
            "manager": "uv",
            "restore": f"uv tool install {entry.name}",
            "ai_related": _is_ai(entry.name),
        }
        for entry in sorted(root.iterdir())
        if entry.is_dir()
    ]


def _pipx_tools() -> list[dict[str, Any]]:
    root = expand("~/pipx/venvs")
    if not root.is_dir():
        return []
    return [
        {
            "name": entry.name,
            "manager": "pipx",
            "restore": f"pipx install {entry.name}",
            "ai_related": _is_ai(entry.name),
        }
        for entry in sorted(root.iterdir())
        if entry.is_dir()
    ]


def _bun_globals() -> list[dict[str, Any]]:
    root = expand("~/.bun/install/global/node_modules")
    if not root.is_dir():
        return []
    names: list[str] = []
    for entry in sorted(root.iterdir()):
        if entry.name.startswith("@") and entry.is_dir():
            names.extend(f"{entry.name}/{sub.name}" for sub in sorted(entry.iterdir()) if sub.is_dir())
        elif entry.is_dir():
            names.append(entry.name)
    return [
        {"name": n, "manager": "bun", "restore": f"bun add -g {n}", "ai_related": _is_ai(n)}
        for n in names
    ]


def _winget_apps() -> list[dict[str, Any]]:
    code, out = run(["winget", "list", "--disable-interactivity"], timeout=180)
    if code != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 2:
            continue
        name, package_id = parts[0], parts[1]
        if not re.match(r"^[\w.+-]+\.[\w.+-]+$", package_id):
            continue
        if not (_is_ai(name) or _is_ai(package_id)):
            continue
        rows.append({
            "name": name,
            "id": package_id,
            "version": parts[2] if len(parts) > 2 else None,
            "manager": "winget",
            "restore": f"winget install --id {package_id} -e --accept-package-agreements --accept-source-agreements",
            "ai_related": True,
        })
    return rows


def _go_bins() -> list[dict[str, Any]]:
    root = expand("~/go/bin")
    if not root.is_dir():
        return []
    return [
        {"name": f.stem, "manager": "go", "restore": f"# go install <module>  ({f.name})", "ai_related": _is_ai(f.stem)}
        for f in sorted(root.glob("*.exe"))
    ]


def _programs() -> list[dict[str, Any]]:
    """Detect AI desktop apps by their install directories."""
    roots = [
        expand("%LOCALAPPDATA%/Programs"),
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
    ]
    seen: dict[str, dict[str, Any]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir() and _is_ai(entry.name) and entry.name.lower() not in seen:
                seen[entry.name.lower()] = {
                    "name": entry.name,
                    "path": str(entry),
                    "manager": "installer",
                    "restore": f"# reinstall {entry.name} from its vendor site",
                    "ai_related": True,
                }
    return sorted(seen.values(), key=lambda p: p["name"].lower())


#: Globals the user installed by hand — restored wholesale, since classifying
#: every package as AI-or-not is guesswork and reinstalling a CLI is cheap.
USER_INSTALLED_MANAGERS = {"npm", "uv", "pipx", "bun", "go"}


def collect() -> dict[str, Any]:
    everything = (
        _npm_globals() + _uv_tools() + _pipx_tools() + _bun_globals() + _winget_apps() + _go_bins()
    )
    return {
        "ai_packages": [p for p in everything if p.get("ai_related")],
        "other_global_packages": [p for p in everything if not p.get("ai_related")],
        "restore_all": [p for p in everything if p["manager"] in USER_INSTALLED_MANAGERS],
        "ai_applications": _programs(),
        "runtimes": _runtimes(),
    }


def _runtimes() -> dict[str, str | None]:
    """Prerequisites the restore script must install before anything else."""
    checks = {
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "python": ["python", "--version"],
        "uv": ["uv", "--version"],
        "git": ["git", "--version"],
        "docker": ["docker", "--version"],
        "pwsh": ["pwsh", "--version"],
    }
    out: dict[str, str | None] = {}
    for name, cmd in checks.items():
        code, text = run(cmd, timeout=30)
        out[name] = text.strip().splitlines()[0] if code == 0 and text.strip() else None
    return out
