"""Record installed IDE extensions by identifier so restore can reinstall them."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..paths import expand, portable

#: extensions dir -> (label, CLI executable used to reinstall)
IDE_EXTENSION_DIRS: tuple[tuple[str, str, str], ...] = (
    ("~/.vscode/extensions", "VS Code", "code"),
    ("~/.vscode-insiders/extensions", "VS Code Insiders", "code-insiders"),
    ("~/.cursor/extensions", "Cursor", "cursor"),
    ("~/.windsurf/extensions", "Windsurf", "windsurf"),
    ("~/.antigravity/extensions", "Antigravity", "antigravity"),
    ("~/.devin/extensions", "Devin", "devin"),
)


def _from_index(root: Path) -> list[dict[str, Any]]:
    """Prefer the extensions.json index the IDE maintains — it is authoritative."""
    index = root / "extensions.json"
    if not index.is_file():
        return []
    try:
        data = json.loads(index.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for entry in data:
        identifier = (entry or {}).get("identifier") or {}
        ext_id = identifier.get("id")
        if not ext_id:
            continue
        out.append({
            "id": ext_id,
            "version": (entry.get("version") if isinstance(entry.get("version"), str) else None),
            "publisher": ext_id.split(".")[0],
        })
    return out


def _from_folders(root: Path) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        manifest = entry / "package.json"
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8-sig", errors="replace"))
                publisher, name = data.get("publisher"), data.get("name")
                if publisher and name:
                    out[f"{publisher}.{name}".lower()] = {
                        "id": f"{publisher}.{name}",
                        "version": data.get("version"),
                        "publisher": publisher,
                    }
                    continue
            except (OSError, json.JSONDecodeError):
                pass
        # Fall back to the folder naming convention: publisher.name-1.2.3
        stem = entry.name.rsplit("-", 1)[0]
        if "." in stem:
            out[stem.lower()] = {"id": stem, "version": None, "publisher": stem.split(".")[0]}
    return list(out.values())


def collect() -> dict[str, Any]:
    ides: list[dict[str, Any]] = []
    for spec, label, cli in IDE_EXTENSION_DIRS:
        root = expand(spec)
        if not root.is_dir():
            continue
        extensions = _from_index(root) or _from_folders(root)
        extensions.sort(key=lambda e: e["id"].lower())
        ides.append({
            "ide": label,
            "cli": cli,
            "path": portable(root),
            "count": len(extensions),
            "restore_command": f"{cli} --install-extension <id>",
            "extensions": extensions,
        })
    return {"ide_count": len(ides), "ides": ides}
