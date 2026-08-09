"""Resilient file copying for a live Windows machine.

Two realities this has to survive:

* **Locked files** — databases, logs and configs of running AI tools are often
  held open. A failed copy must never abort the backup.
* **MAX_PATH** — plugin and extension trees routinely exceed 260 characters.
  Prefixing with ``\\\\?\\`` lifts the limit for the Win32 API calls beneath
  ``shutil``.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

BACKSLASH = chr(92)
LONG_PREFIX = BACKSLASH * 2 + "?" + BACKSLASH
UNC_PREFIX = BACKSLASH * 2
LONG_PATH_THRESHOLD = 240


class CopyError(RuntimeError):
    """Raised when a file could not be copied for a reportable reason."""


def long_path(path: Path) -> str:
    """Return a string safe to hand to the Win32 API for deep paths."""
    text = str(path.absolute())
    if len(text) < LONG_PATH_THRESHOLD or text.startswith(LONG_PREFIX):
        return text
    if text.startswith(UNC_PREFIX):
        return LONG_PREFIX + "UNC" + text[1:]
    return LONG_PREFIX + text


def _ensure_parent(destination: Path) -> None:
    """Create the destination directory, tolerating paths past MAX_PATH.

    ``Path.mkdir`` goes through the short-path API and raises WinError 206 on deep
    trees, so the extended-length form is used instead.
    """
    parent = destination.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        os.makedirs(long_path(parent), exist_ok=True)


def safe_copy(source: Path, destination: Path) -> int:
    """Copy ``source`` to ``destination``; return bytes written.

    Raises :class:`CopyError` with a short explanation instead of letting an
    OS-level failure unwind the whole scan.
    """
    _ensure_parent(destination)
    try:
        shutil.copy2(long_path(source), long_path(destination))
        return os.stat(long_path(destination)).st_size
    except PermissionError:
        pass
    except (OSError, shutil.Error) as exc:
        raise CopyError(f"{type(exc).__name__}: {exc}") from exc

    # Locked file: a plain read-and-write still succeeds for most shared-read handles.
    try:
        with open(long_path(source), "rb") as reader, open(long_path(destination), "wb") as writer:
            shutil.copyfileobj(reader, writer, length=1 << 20)
        return os.stat(long_path(destination)).st_size
    except (OSError, shutil.Error) as exc:
        raise CopyError(f"locked by another process ({type(exc).__name__})") from exc


def safe_write_text(destination: Path, text: str) -> int:
    _ensure_parent(destination)
    try:
        with open(long_path(destination), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return os.stat(long_path(destination)).st_size
    except OSError as exc:
        raise CopyError(f"{type(exc).__name__}: {exc}") from exc


def safe_read_text(source: Path) -> str:
    try:
        with open(long_path(source), "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as exc:
        raise CopyError(f"{type(exc).__name__}: {exc}") from exc
