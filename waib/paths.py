"""Path resolution and portability helpers.

Captured paths are stored with environment placeholders (``%APPDATA%`` etc.) so a
backup taken on one machine restores correctly on another after a Windows
reinstall, even if the user name or drive layout changed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

# Order matters: the most specific root must win when several roots share a prefix.
_ROOT_KEYS = (
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES(X86)",
    "PROGRAMFILES",
    "USERPROFILE",
)

SEPARATORS = "/" + chr(92)
BACKSLASH = chr(92)


def _roots() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for key in _ROOT_KEYS:
        raw = os.environ.get(key)
        if not raw:
            continue
        try:
            out.append((key, Path(raw).resolve()))
        except OSError:
            continue
    out.sort(key=lambda kv: len(str(kv[1])), reverse=True)
    return out


ROOTS = _roots()


def expand(spec: str) -> Path:
    """Expand a catalog path spec (``~/...`` or ``%APPDATA%/...``) into a real path."""
    text = os.path.expandvars(spec)
    if text.startswith("~"):
        text = os.path.expanduser(text)
    return Path(text)


def portable(path: Path | str) -> str:
    """Render an absolute path using ``%ENVVAR%`` placeholders where possible."""
    try:
        resolved = Path(path).resolve()
    except OSError:
        resolved = Path(path)
    text = str(resolved)
    for key, root in ROOTS:
        root_text = str(root)
        if text.lower().startswith(root_text.lower()):
            tail = text[len(root_text):].lstrip(SEPARATORS)
            return f"%{key}%{BACKSLASH}{tail}" if tail else f"%{key}%"
    return text


def archive_relpath(path: Path | str) -> str:
    """Map an absolute path to its location inside the backup's ``files/`` tree."""
    token = portable(path)
    if token.startswith("%"):
        key, _, tail = token[1:].partition("%")
        tail = tail.lstrip(SEPARATORS)
        return f"{key}/{tail}".replace(BACKSLASH, "/").rstrip("/")
    drive, _, tail = token.replace(BACKSLASH, "/").partition("/")
    return f"_DRIVE_{drive.rstrip(':')}/{tail}"


def restore_target(archive_rel: str) -> Path | None:
    """Inverse of :func:`archive_relpath` — where a stored file belongs on restore."""
    head, _, tail = archive_rel.replace(BACKSLASH, "/").partition("/")
    prefix = "_DRIVE_"
    if head.startswith(prefix):
        return Path(f"{head[len(prefix):]}:/{tail}")
    root = os.environ.get(head)
    if not root:
        return None
    return Path(root) / tail


def first_existing(specs: Iterable[str]) -> Path | None:
    for spec in specs:
        candidate = expand(spec)
        if candidate.exists():
            return candidate
    return None
