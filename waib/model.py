"""Immutable data model for catalog entries and scan results.

Every structure here is a frozen dataclass: collectors build new objects rather
than mutating shared state, which keeps the scan reproducible and side-effect
free.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

ItemKind = Literal["config", "prompt", "tree", "secret", "record"]

#: ``config``  small JSON/TOML/YAML settings file, copied verbatim (secrets redacted)
#: ``prompt``  instruction / rules / memory file, copied and mirrored into ``prompts/``
#: ``tree``    directory copied with include/exclude globs and size caps
#: ``secret``  credential file: never copied in the clear, vault only
#: ``record``  existence + metadata noted in the inventory, contents not copied


@dataclass(frozen=True)
class Item:
    """One capturable artifact belonging to a target."""

    path: str
    kind: ItemKind = "config"
    note: str = ""
    include: tuple[str, ...] = ("**/*",)
    exclude: tuple[str, ...] = ()
    max_file_mb: float = 8.0
    max_total_mb: float = 120.0
    optional: bool = True


@dataclass(frozen=True)
class McpSource:
    """A file that declares MCP servers, plus the schema dialect it uses."""

    path: str
    fmt: Literal["mcp_servers", "claude_json", "vscode_mcp", "toml_mcp", "yaml_mcp"]
    client: str


@dataclass(frozen=True)
class Install:
    """How to obtain the tool again on a fresh machine."""

    npm: str | None = None
    pipx: str | None = None
    uv: str | None = None
    winget: str | None = None
    choco: str | None = None
    url: str | None = None
    docs: str | None = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass(frozen=True)
class Target:
    """A single AI tool/product and everything worth preserving about it."""

    id: str
    name: str
    category: str
    detect: tuple[str, ...]
    items: tuple[Item, ...] = ()
    mcp_sources: tuple[McpSource, ...] = ()
    install: Install = field(default_factory=Install)
    extensions_dir: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class CapturedFile:
    """Record of one file placed into the backup (or deliberately skipped)."""

    source: str            # portable path, e.g. %USERPROFILE%\.claude\settings.json
    archive: str | None    # path inside the backup, or None when recorded only
    kind: ItemKind
    size: int
    sha256: str | None
    redactions: tuple[str, ...] = ()
    skipped_reason: str | None = None


@dataclass(frozen=True)
class TargetResult:
    """Outcome of scanning one target."""

    target_id: str
    name: str
    category: str
    present: bool
    root: str | None
    files: tuple[CapturedFile, ...] = ()
    install: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    errors: tuple[str, ...] = ()

    def with_files(self, files: tuple[CapturedFile, ...]) -> "TargetResult":
        return replace(self, files=files)

    @property
    def bytes_copied(self) -> int:
        return sum(f.size for f in self.files if f.archive)
