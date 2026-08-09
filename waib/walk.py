"""Directory walking that prunes heavy subtrees *before* descending into them.

``Path.rglob`` visits every entry under a root, so a 1 GB ``node_modules`` costs
minutes even when every file in it is filtered out afterwards. These helpers cut
the branch at the directory level instead.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

#: Directory names that never belong in a settings backup.
PRUNE_DIRS = frozenset({
    "node_modules", ".venv", "venv", "env", "__pycache__", ".git", "dist", "build",
    ".next", ".turbo", ".cache", "cache", "target", ".pytest_cache", ".mypy_cache",
    "site-packages", ".tox", ".ruff_cache", "coverage", ".nyc_output", ".gradle",
    ".idea", ".vs", "Debug", "Release", "obj", "logs", "log", "tmp", "temp",
    ".svelte-kit", ".parcel-cache", ".vite", "vendor", "Pods", ".terraform",
})

#: Extensions that are payload, not configuration.
PRUNE_SUFFIXES = frozenset({
    ".gguf", ".safetensors", ".bin", ".onnx", ".pt", ".pth", ".ckpt", ".h5",
    ".dll", ".exe", ".so", ".dylib", ".pyd", ".lib", ".obj", ".pdb", ".msi",
    ".zip", ".7z", ".tar", ".gz", ".xz", ".rar", ".iso", ".wasm", ".node",
    ".mp4", ".mov", ".avi", ".mkv", ".wav", ".mp3", ".pack", ".idx",
})


def walk_files(
    root: Path,
    prune_dirs: frozenset[str] = PRUNE_DIRS,
    prune_suffixes: frozenset[str] = PRUNE_SUFFIXES,
    max_depth: int = 12,
    max_entries: int = 200_000,
) -> Iterator[Path]:
    """Yield files under ``root``, skipping pruned directories and payload files."""
    root = Path(root)
    base_depth = len(root.parts)
    seen = 0

    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        if len(current_path.parts) - base_depth >= max_depth:
            dirnames[:] = []
            continue

        # Mutating dirnames in place is what stops os.walk descending.
        dirnames[:] = sorted(d for d in dirnames if d not in prune_dirs and not d.startswith("$"))

        for name in sorted(filenames):
            if Path(name).suffix.lower() in prune_suffixes:
                continue
            seen += 1
            if seen > max_entries:
                return
            yield current_path / name


def tree_size(root: Path, prune: bool = False) -> int:
    """Total bytes under ``root``; ``prune=True`` ignores heavy subtrees."""
    total = 0
    if prune:
        for path in walk_files(root):
            try:
                total += path.stat().st_size
            except OSError:
                continue
        return total

    for current, dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            try:
                total += (Path(current) / name).stat().st_size
            except OSError:
                continue
    return total
