"""Find AI tools that are not in the catalog.

A curated list can never keep up — new agents and clients appear weekly, and
in-house tools will never be on any public list. Discovery closes that gap by
looking for the *shapes* AI tooling takes on disk rather than for known names:

* a config directory whose name reads as AI tooling;
* a file that declares MCP servers, whatever the surrounding tool is;
* an agent instruction file (``AGENTS.md``, ``CLAUDE.md``, ``.cursorrules``);
* a settings file naming an LLM provider or model.

Each hit is scored, and anything above the threshold is offered as a synthetic
:class:`Target` so the rest of the pipeline treats it exactly like a catalogued
tool. Discovery never guesses at reinstall commands — it only preserves what it
found and records where it came from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .model import Install, Item, McpSource, Target
from .paths import expand, portable
from .util import load_structured
from .walk import walk_files

#: Roots whose immediate children are worth inspecting.
SEARCH_ROOTS = ("~", "%APPDATA%", "%LOCALAPPDATA%")

#: Directory-name signals. Distinctive substrings score on their own.
STRONG_NAME_HINTS = (
    "claude", "anthropic", "openai", "chatgpt", "gpt", "gemini", "copilot", "cursor",
    "codex", "cline", "roo", "aider", "ollama", "lmstudio", "llm", "langchain",
    "langgraph", "llama", "mistral", "deepseek", "qwen", "perplexity", "windsurf",
    "antigravity", "opencode", "goose", "continue", "tabnine", "codeium", "supermaven",
    "augment", "sourcegraph", "cody", "kilocode", "qodo", "devin", "kimi", "grok",
    "mcp", "agent", "autogen", "crewai", "letta", "memgpt", "mem0", "anythingllm",
    "openwebui", "sillytavern", "koboldcpp", "gpt4all", "localai", "jan", "msty",
    "flowise", "langflow", "dify", "promptfoo", "langfuse", "langsmith", "huggingface",
)

#: Weaker signals — only count when paired with structural evidence.
WEAK_NAME_HINTS = ("ai", "bot", "chat", "prompt", "assistant", "copilot", "inference")

_STRONG = re.compile("|".join(re.escape(h) for h in STRONG_NAME_HINTS), re.IGNORECASE)
_WEAK = re.compile(r"(?:^|[^a-z0-9])(" + "|".join(WEAK_NAME_HINTS) + r")(?:[^a-z0-9]|$)", re.IGNORECASE)

#: Files that mark a directory as agent tooling regardless of its name.
INSTRUCTION_FILES = (
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "AGENT.md", "COPILOT.md",
    ".cursorrules", ".windsurfrules", ".clinerules", ".goosehints", "SKILL.md",
)

MCP_FILENAMES = re.compile(
    r"(?i)^(mcp|mcp[_-]config|mcp[_-]settings|mcp[_-]servers|.*[_.-]mcp)\.(json|toml|ya?ml)$"
)

CONFIG_SUFFIXES = {".json", ".toml", ".yaml", ".yml"}

#: Keys inside a settings file that betray an LLM client.
TELLTALE_KEYS = (
    "mcpservers", "mcp_servers", "servers", "model", "models", "provider", "providers",
    "apikey", "api_key", "systemprompt", "system_prompt", "temperature", "anthropic",
    "openai", "llm", "embedding",
)

#: Directories under the search roots that are never AI tooling.
IGNORE_NAMES = frozenset({
    "microsoft", "windows", "temp", "tmp", "packages", "programs", "package cache",
    "nuget", "npm", "npm-cache", "pnpm", "yarn", "node_modules", "history", "cache",
    "crashdumps", "connecteddevicesplatform", "d3dscache", "iconcache.db", "comms",
    "publishers", "virtualstore", "deployment", "assembly", "squirreltemp",
    "temporary internet files", "placeholdertilelogofolder", "application data",
    "desktop", "documents", "downloads", "music", "pictures", "videos", "favorites",
    "links", "contacts", "searches", "saved games", "onedrive", "appdata",
    ".git", ".vs", ".gradle", ".m2", ".nuget", ".docker", ".kube", ".azure", ".aws",
    "google", "mozilla", "adobe", "zoom", "discord", "steam", "epic games",
    # Editor extension stores: the catalog already records extensions by id, and
    # their payloads are re-downloaded, so sweeping them would be pure bloat.
    ".vscode", ".vscode-insiders", ".cursor", ".windsurf", ".antigravity",
    ".antigravity-ide", ".devin", ".trae", ".pearai", ".kiro", ".void-editor",
    # Cloud sync roots hold other people's files, not this machine's AI settings.
    "dropbox", "google drive", "googledrive", "box", "icloud", "iclouddrive",
    "nextcloud", "syncthing", "megasync", "pcloud",
})

MIN_SCORE = 3
MAX_DEPTH_FILES = 400


@dataclass(frozen=True)
class Discovery:
    """One directory that looks like an uncatalogued AI tool."""

    name: str
    path: str
    score: int
    signals: tuple[str, ...]
    mcp_files: tuple[str, ...]
    instruction_files: tuple[str, ...]
    config_files: tuple[str, ...]

    @property
    def tool_id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return f"discovered-{slug}" or "discovered-unknown"


def _looks_structural(path: Path) -> tuple[bool, bool]:
    """Return ``(declares_mcp, names_a_provider)`` for one config file."""
    data = load_structured(path)
    if not isinstance(data, dict):
        return False, False
    lowered = {str(k).lower() for k in data.keys()}
    declares_mcp = bool(lowered & {"mcpservers", "mcp_servers"}) or (
        "servers" in lowered and path.name.lower().startswith("mcp")
    )
    names_provider = bool(lowered & set(TELLTALE_KEYS))
    return declares_mcp, names_provider


def _is_code_project(directory: Path) -> bool:
    """A repo or package is the user's own project, not an AI tool's config."""
    markers = (".git", "package.json", "pyproject.toml", "go.mod", "Cargo.toml", ".sln")
    return any((directory / marker).exists() for marker in markers)


def _inspect(directory: Path) -> Discovery | None:
    """Score a single candidate directory."""
    score = 0
    signals: list[str] = []
    mcp_files: list[str] = []
    instruction_files: list[str] = []
    config_files: list[str] = []

    name = directory.name
    if _STRONG.search(name):
        score += 3
        signals.append("name matches a known AI vendor or tool")
    elif _WEAK.search(name):
        score += 1
        signals.append("name hints at AI tooling")

    seen = 0
    # walk_files prunes node_modules, .git and friends *before* descending, which
    # is the difference between seconds and minutes across a whole home directory.
    for entry in walk_files(directory, max_depth=5, max_entries=MAX_DEPTH_FILES):
        seen += 1
        if seen > MAX_DEPTH_FILES:
            break

        filename = entry.name
        try:
            relative = entry.relative_to(directory).as_posix()
        except ValueError:
            continue

        if filename in INSTRUCTION_FILES:
            score += 3
            instruction_files.append(relative)
            signals.append(f"agent instruction file: {filename}")
            continue

        if MCP_FILENAMES.match(filename):
            declares, _ = _looks_structural(entry)
            score += 4 if declares else 2
            mcp_files.append(relative)
            signals.append(f"MCP config: {filename}")
            continue

        if entry.suffix.lower() not in CONFIG_SUFFIXES:
            continue
        try:
            small = entry.stat().st_size < 2_000_000
        except OSError:
            continue
        if small:
            declares_mcp, names_provider = _looks_structural(entry)
            if declares_mcp:
                score += 4
                mcp_files.append(relative)
                signals.append(f"declares MCP servers: {relative}")
            elif names_provider:
                score += 1
                config_files.append(relative)
            elif len(config_files) < 40:
                config_files.append(relative)

    if score < MIN_SCORE:
        return None

    return Discovery(
        name=name,
        path=portable(directory),
        score=score,
        signals=tuple(dict.fromkeys(signals))[:8],
        mcp_files=tuple(mcp_files[:20]),
        instruction_files=tuple(instruction_files[:40]),
        config_files=tuple(config_files[:40]),
    )


def _candidates() -> Iterable[Path]:
    for spec in SEARCH_ROOTS:
        root = expand(spec)
        if not root.is_dir():
            continue
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.lower() in IGNORE_NAMES:
                continue
            yield entry


def scan(known_paths: set[str] | None = None, limit: int = 400) -> list[Discovery]:
    """Find likely AI tool directories the catalog does not already cover."""
    known = {p.lower() for p in (known_paths or set())}
    found: list[Discovery] = []

    for directory in _candidates():
        if len(found) >= limit:
            break
        token = portable(directory).lower()
        if token in known or any(token.startswith(k + chr(92)) for k in known):
            continue
        if _is_code_project(directory):
            continue
        result = _inspect(directory)
        if result is not None:
            found.append(result)

    found.sort(key=lambda d: (-d.score, d.name.lower()))
    return found


def known_roots(targets: Iterable[Target]) -> set[str]:
    """Portable paths already claimed by catalog entries."""
    claimed: set[str] = set()
    for target in targets:
        for spec in target.detect:
            path = expand(spec)
            if path.exists():
                claimed.add(portable(path))
    return claimed


def to_target(found: Discovery) -> Target:
    """Wrap a discovery as a Target so the normal pipeline can capture it.

    Only the files that actually earned the score are captured, plus settings at
    the top two levels. A recursive sweep of an unknown directory would drag in
    extension payloads and caches — exactly what this tool exists to avoid.
    """
    items: list[Item] = [
        Item(f"{found.path}/{rel}", "prompt", "Discovered instruction file")
        for rel in found.instruction_files
    ]
    items += [Item(f"{found.path}/{rel}", "config", "Discovered MCP config") for rel in found.mcp_files]
    items.append(
        Item(
            found.path,
            "tree",
            "Discovered settings (top levels only)",
            include=("*.json", "*.toml", "*.yaml", "*.yml", "*.md", "*.mdc",
                     "*/*.json", "*/*.toml", "*/*.yaml", "*/*.yml", "*/*.md"),
            exclude=("**/node_modules/**", "**/.git/**", "**/cache/**", "**/logs/**",
                     "**/extensions/**", "**/History/**", "**/globalStorage/**"),
            max_file_mb=2.0,
            max_total_mb=5.0,
        )
    )

    sources = tuple(
        McpSource(f"{found.path}/{rel}", "mcp_servers", f"{found.name} (discovered)")
        for rel in found.mcp_files
        if rel.lower().endswith(".json")
    )

    return Target(
        id=found.tool_id,
        name=f"{found.name} (discovered)",
        category="Discovered",
        detect=(found.path,),
        items=tuple(items),
        mcp_sources=sources,
        install=Install(note="Discovered heuristically — reinstall source unknown"),
        notes="; ".join(found.signals),
    )
