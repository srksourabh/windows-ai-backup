"""Load the tool catalog from data files rather than Python source.

The catalog is JSON so it can grow to hundreds of tools without touching code,
ship updates without rebuilding the executable, and accept user-authored entries
for in-house tools that will never be in the public list.

Sources are merged in increasing order of precedence:

1. ``waib/data/catalog.json``          — bundled with the build
2. ``waib/data/catalog.d/*.json``      — bundled, split by category
3. ``%APPDATA%/WindowsAIBackup/catalog/*.json``  — downloaded updates
4. ``%APPDATA%/WindowsAIBackup/catalog.local/*.json`` — the user's own entries

Later definitions of the same ``id`` replace earlier ones, so a user can correct
a bundled entry without editing the install.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .model import Install, Item, McpSource, Target
from .paths import expand

USER_CATALOG_DIR = "%APPDATA%/WindowsAIBackup/catalog"
USER_LOCAL_CATALOG_DIR = "%APPDATA%/WindowsAIBackup/catalog.local"

VALID_KINDS = {"config", "prompt", "tree", "secret", "record"}
VALID_FORMATS = {"mcp_servers", "claude_json", "vscode_mcp", "toml_mcp", "yaml_mcp"}


class CatalogError(ValueError):
    """A catalog file is malformed in a way worth telling the user about."""


def data_dir() -> Path:
    """The bundled data directory, inside the PyInstaller bundle when frozen."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "waib" / "data"
    return Path(__file__).resolve().parent / "data"


def _read(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{path.name}: {exc}") from exc

    if isinstance(payload, list):
        return payload
    tools = payload.get("tools")
    if not isinstance(tools, list):
        raise CatalogError(f"{path.name}: expected a 'tools' array")
    return tools


def catalog_files() -> list[Path]:
    """Every catalog file that will be loaded, in precedence order."""
    found: list[Path] = []
    bundled = data_dir()
    primary = bundled / "catalog.json"
    if primary.is_file():
        found.append(primary)
    found.extend(sorted((bundled / "catalog.d").glob("*.json")))
    for spec in (USER_CATALOG_DIR, USER_LOCAL_CATALOG_DIR):
        directory = expand(spec)
        if directory.is_dir():
            found.extend(sorted(directory.glob("*.json")))
    return found


def _build_item(raw: dict[str, Any], tool_id: str) -> Item:
    kind = raw.get("kind", "config")
    if kind not in VALID_KINDS:
        raise CatalogError(f"{tool_id}: unknown item kind {kind!r}")
    if not raw.get("path"):
        raise CatalogError(f"{tool_id}: an item is missing 'path'")
    return Item(
        path=raw["path"],
        kind=kind,
        note=raw.get("note", ""),
        include=tuple(raw.get("include") or ("**/*",)),
        exclude=tuple(raw.get("exclude") or ()),
        max_file_mb=float(raw.get("max_file_mb", 8.0)),
        max_total_mb=float(raw.get("max_total_mb", 120.0)),
    )


def _build_target(raw: dict[str, Any]) -> Target:
    tool_id = raw.get("id")
    if not tool_id:
        raise CatalogError("a tool entry is missing 'id'")
    if not raw.get("detect"):
        raise CatalogError(f"{tool_id}: 'detect' must list at least one path")

    sources = []
    for source in raw.get("mcp_sources") or []:
        fmt = source.get("fmt")
        if fmt not in VALID_FORMATS:
            raise CatalogError(f"{tool_id}: unknown mcp format {fmt!r}")
        sources.append(McpSource(source["path"], fmt, source.get("client", raw.get("name", tool_id))))

    install = raw.get("install") or {}
    return Target(
        id=tool_id,
        name=raw.get("name", tool_id),
        category=raw.get("category", "Other"),
        detect=tuple(raw["detect"]),
        items=tuple(_build_item(i, tool_id) for i in raw.get("items") or ()),
        mcp_sources=tuple(sources),
        install=Install(**{k: v for k, v in install.items() if k in Install.__dataclass_fields__}),
        extensions_dir=raw.get("extensions_dir"),
        notes=raw.get("notes", ""),
    )


def load_targets(strict: bool = False) -> tuple[tuple[Target, ...], list[str]]:
    """Return ``(targets, warnings)``. A bad entry is skipped, not fatal."""
    merged: dict[str, Target] = {}
    warnings: list[str] = []

    for path in catalog_files():
        try:
            entries = _read(path)
        except CatalogError as exc:
            if strict:
                raise
            warnings.append(str(exc))
            continue

        for raw in entries:
            try:
                target = _build_target(raw)
            except (CatalogError, TypeError, ValueError) as exc:
                if strict:
                    raise CatalogError(f"{path.name}: {exc}") from exc
                warnings.append(f"{path.name}: {exc}")
                continue
            merged[target.id] = target

    ordered = tuple(sorted(merged.values(), key=lambda t: (t.category.lower(), t.name.lower())))
    return ordered, warnings


@lru_cache(maxsize=1)
def targets() -> tuple[Target, ...]:
    loaded, _ = load_targets()
    return loaded


@lru_cache(maxsize=1)
def warnings() -> tuple[str, ...]:
    _, issues = load_targets()
    return tuple(issues)


def by_id(tool_id: str) -> Target | None:
    return next((t for t in targets() if t.id == tool_id), None)


def categories() -> dict[str, list[Target]]:
    grouped: dict[str, list[Target]] = {}
    for target in targets():
        grouped.setdefault(target.category, []).append(target)
    return grouped


def reset_cache() -> None:
    """Forget the loaded catalog — used after an update or in tests."""
    targets.cache_clear()
    warnings.cache_clear()


def resolve_ids(names: Iterable[str]) -> tuple[list[str], list[str]]:
    """Map user-supplied names or ids onto catalog ids. Returns (ids, unknown)."""
    lookup: dict[str, str] = {}
    for target in targets():
        lookup[target.id.lower()] = target.id
        lookup[target.name.lower()] = target.id

    resolved: list[str] = []
    unknown: list[str] = []
    for name in names:
        key = name.strip().lower()
        if not key:
            continue
        if key in lookup:
            if lookup[key] not in resolved:
                resolved.append(lookup[key])
        else:
            unknown.append(name)
    return resolved, unknown
