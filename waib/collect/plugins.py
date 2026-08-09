"""Record plugins, marketplaces, skills, agents, and slash commands by *source*.

Payloads under plugin caches are re-cloneable, so the backup keeps the marketplace
coordinates plus the enabled-plugin list rather than hundreds of megabytes.
Hand-authored skills/agents/commands are copied elsewhere by the file collector;
here they are indexed so the inventory can list them by name.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..paths import expand, portable
from ..util import load_structured

SKILL_DIRS: tuple[tuple[str, str], ...] = (
    ("~/.claude/skills", "Claude Code"),
    ("~/.agents/skills", "Portable (.agents)"),
    ("~/.agent/skills", "Portable (.agent)"),
    ("~/.openclaw/skills", "OpenClaw"),
    ("~/.gemini/skills", "Gemini CLI"),
    ("~/.codex/skills", "Codex CLI"),
    ("~/.cursor/skills-cursor", "Cursor"),
)

AGENT_DIRS: tuple[tuple[str, str], ...] = (
    ("~/.claude/agents", "Claude Code"),
    ("~/.cursor/agents", "Cursor"),
)

COMMAND_DIRS: tuple[tuple[str, str], ...] = (
    ("~/.claude/commands", "Claude Code"),
    ("~/.gemini/commands", "Gemini CLI"),
)

RULE_DIRS: tuple[tuple[str, str], ...] = (
    ("~/.claude/rules", "Claude Code"),
    ("~/.cursor/rules", "Cursor"),
    ("~/.antigravity/rules", "Antigravity"),
    ("~/.agent/rules", "Portable (.agent)"),
    ("~/.continue/rules", "Continue"),
)


def _first_line_summary(path: Path) -> str:
    """Pull the description out of front matter, or fall back to the first heading."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in lines[:20]:
        stripped = line.strip()
        if stripped.lower().startswith("description:"):
            return stripped.split(":", 1)[1].strip()[:180]
    for line in lines[:20]:
        if line.startswith("# "):
            return line[2:].strip()[:180]
    return ""


def _index_dir(spec: str, owner: str, kind: str) -> list[dict[str, Any]]:
    root = expand(spec)
    if not root.is_dir():
        return []

    out: list[dict[str, Any]] = []
    if kind == "skill":
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            manifest = entry / "SKILL.md"
            out.append({
                "name": entry.name,
                "owner": owner,
                "path": portable(entry),
                "has_manifest": manifest.is_file(),
                "description": _first_line_summary(manifest) if manifest.is_file() else "",
            })
    else:
        for entry in sorted(root.rglob("*.md")):
            out.append({
                "name": entry.stem,
                "owner": owner,
                "path": portable(entry),
                "description": _first_line_summary(entry),
            })
        for entry in sorted(root.rglob("*.mdc")):
            out.append({"name": entry.stem, "owner": owner, "path": portable(entry), "description": ""})
    return out


def _claude_plugins() -> dict[str, Any]:
    settings = load_structured(expand("~/.claude/settings.json")) or {}
    installed = load_structured(expand("~/.claude/plugins/installed_plugins.json")) or {}
    known = load_structured(expand("~/.claude/plugins/known_marketplaces.json")) or {}

    enabled = settings.get("enabledPlugins") if isinstance(settings, dict) else {}
    marketplaces = settings.get("extraKnownMarketplaces") if isinstance(settings, dict) else {}

    entries: list[dict[str, Any]] = []
    for plugin_ref, is_enabled in (enabled or {}).items():
        name, _, marketplace = str(plugin_ref).partition("@")
        source = ((marketplaces or {}).get(marketplace) or {}).get("source") or {}
        entries.append({
            "plugin": name,
            "marketplace": marketplace,
            "enabled": bool(is_enabled),
            "source": source,
            "restore": _plugin_restore(name, marketplace, source),
        })

    return {
        "plugins": entries,
        "marketplaces": marketplaces or {},
        "known_marketplaces_file": known if isinstance(known, dict) else {},
        "installed_plugins_file": installed if isinstance(installed, dict) else {},
    }


def _plugin_restore(name: str, marketplace: str, source: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    kind = source.get("source")
    if kind == "github" and source.get("repo"):
        steps.append(f"claude plugin marketplace add {source['repo']}")
    elif kind == "git" and source.get("url"):
        steps.append(f"claude plugin marketplace add {source['url']}")
    elif kind == "directory" and source.get("path"):
        steps.append(f"# local marketplace — restore folder: {source['path']}")
    steps.append(f"claude plugin install {name}@{marketplace}")
    return steps


def collect() -> dict[str, Any]:
    return {
        "claude_code": _claude_plugins(),
        "skills": [s for spec, owner in SKILL_DIRS for s in _index_dir(spec, owner, "skill")],
        "agents": [a for spec, owner in AGENT_DIRS for a in _index_dir(spec, owner, "agent")],
        "commands": [c for spec, owner in COMMAND_DIRS for c in _index_dir(spec, owner, "command")],
        "rules": [r for spec, owner in RULE_DIRS for r in _index_dir(spec, owner, "rule")],
    }
