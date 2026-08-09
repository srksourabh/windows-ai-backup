"""Copy catalog items into the backup tree, redacting secrets along the way."""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

from ..copyio import CopyError, safe_copy, safe_read_text, safe_write_text
from ..model import CapturedFile, Item, ItemKind, Target, TargetResult
from ..paths import archive_relpath, expand, portable
from ..scrub import is_secret_filename, scrub_file
from ..util import extract_secrets, load_structured, redact, sha256_file
from ..walk import tree_size, walk_files

STRUCTURED_SUFFIXES = {".json", ".toml", ".yaml", ".yml"}
TEXT_SUFFIXES = {".md", ".mdc", ".txt", ".js", ".ps1", ".sh", ".py", ".prompt", ".xml", ".env", ""}


def _matches(rel: str, patterns: tuple[str, ...]) -> bool:
    """Glob match where a leading ``**/`` also matches files at the tree root.

    ``fnmatch`` requires a literal separator for ``**/``, so ``**/*.json`` would
    otherwise miss ``opencode.json`` sitting directly in the directory.
    """
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(rel, pattern[3:]):
            return True
    return False


def _iter_tree(root: Path, item: Item) -> list[Path]:
    picked: list[Path] = []
    for path in walk_files(root):
        rel = path.relative_to(root).as_posix()
        if item.exclude and _matches(rel, item.exclude):
            continue
        if item.include and not _matches(rel, item.include):
            continue
        picked.append(path)
    return picked


class FileCollector:
    """Copies files, keeps a secret vault payload, and reports what it did."""

    def __init__(self, out_dir: Path, capture_secrets: bool) -> None:
        self.files_root = out_dir / "files"
        self.prompts_root = out_dir / "prompts"
        self.capture_secrets = capture_secrets
        self.vault: dict[str, dict[str, str]] = {}

    # ---------------------------------------------------------------- helpers

    def _store_secret_file(self, source: Path) -> None:
        try:
            self.vault.setdefault("files", {})[portable(source)] = safe_read_text(source)
        except (OSError, CopyError) as exc:
            self.vault.setdefault("errors", {})[portable(source)] = str(exc)

    def _write_copy(self, source: Path, item: Item) -> CapturedFile:
        rel = archive_relpath(source)
        dest = self.files_root / rel
        # No mkdir here: safe_copy/safe_write_text create the parent through the
        # extended-length API. A plain Path.mkdir raises WinError 206 once the
        # destination exceeds MAX_PATH, which used to abort the whole tree.
        size = source.stat().st_size
        redactions: list[str] = []

        if source.suffix.lower() in STRUCTURED_SUFFIXES:
            parsed = load_structured(source)
            if parsed is not None:
                clean, found = redact(parsed)
                # default=str: TOML and YAML carry native dates and times that
                # json.dumps cannot serialise on its own.
                safe_write_text(dest, json.dumps(clean, indent=2, ensure_ascii=False, default=str))
                redactions.extend(found)
                if found and self.capture_secrets:
                    secrets = extract_secrets(parsed)
                    if secrets:
                        self.vault.setdefault(portable(source), {}).update(secrets)
                if source.suffix.lower() != ".json":
                    # Keep the original alongside the normalised JSON so restore can
                    # write the exact dialect the tool expects.
                    original = dest.with_suffix(dest.suffix + ".original")
                    safe_copy(source, original)
                    scrub_file(original)
            else:
                safe_copy(source, dest)
        else:
            safe_copy(source, dest)

        # Structured redaction cannot see a key hardcoded in source, or one buried
        # inside a longer string, so every written file gets a text-level pass.
        scrubbed = scrub_file(dest)
        if scrubbed:
            redactions.append(f"<{scrubbed} inline credential(s) scrubbed>")

        if item.kind == "prompt":
            mirror = self.prompts_root / rel
            safe_copy(dest, mirror)

        return CapturedFile(
            source=portable(source),
            archive=f"files/{rel}",
            kind=item.kind,
            size=size,
            sha256=sha256_file(source),
            redactions=tuple(redactions),
        )

    # ------------------------------------------------------------------- main

    def _vault_only(self, source: Path, kind: ItemKind) -> CapturedFile:
        """Send credentials to the vault; never write them into ``files/``.

        Handles directories too — several tools keep a ``credentials/`` folder
        rather than a single file.
        """
        members = [source] if source.is_file() else [p for p in walk_files(source) if p.is_file()]
        size = sum(p.stat().st_size for p in members)

        if self.capture_secrets and members:
            for member in members:
                self._store_secret_file(member)
            reason = f"stored in encrypted vault ({len(members)} file(s))"
        elif members:
            reason = "excluded (run with --secrets to include, encrypted)"
        else:
            reason = "no readable credential files"
        return CapturedFile(portable(source), None, kind, size, None, skipped_reason=reason)

    def collect_item(self, item: Item) -> list[CapturedFile]:
        source = expand(item.path)
        if not source.exists():
            return []

        # A file named like a credential store is one, whatever the catalog says.
        if source.is_file() and item.kind != "record" and is_secret_filename(source.name):
            return [self._vault_only(source, "secret")]

        if item.kind == "record":
            total = tree_size(source) if source.is_dir() else source.stat().st_size
            return [
                CapturedFile(
                    source=portable(source),
                    archive=None,
                    kind="record",
                    size=total,
                    sha256=None,
                    skipped_reason=item.note or "recorded only; re-downloadable",
                )
            ]

        if item.kind == "secret":
            return [self._vault_only(source, "secret")]

        if source.is_file():
            if source.stat().st_size > item.max_file_mb * 1024 * 1024:
                return [
                    CapturedFile(
                        source=portable(source),
                        archive=None,
                        kind=item.kind,
                        size=source.stat().st_size,
                        sha256=None,
                        skipped_reason=f"larger than {item.max_file_mb} MB cap",
                    )
                ]
            try:
                return [self._write_copy(source, item)]
            except (CopyError, OSError) as exc:
                return [
                    CapturedFile(portable(source), None, item.kind, source.stat().st_size,
                                 None, skipped_reason=str(exc))
                ]

        out: list[CapturedFile] = []
        budget = int(item.max_total_mb * 1024 * 1024)
        used = 0
        for path in _iter_tree(source, item):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > item.max_file_mb * 1024 * 1024:
                out.append(
                    CapturedFile(portable(path), None, item.kind, size, None,
                                 skipped_reason=f"larger than {item.max_file_mb} MB cap")
                )
                continue
            if used + size > budget:
                out.append(
                    CapturedFile(portable(path), None, item.kind, size, None,
                                 skipped_reason=f"tree budget {item.max_total_mb} MB exhausted")
                )
                continue
            if is_secret_filename(path.name):
                out.append(self._vault_only(path, "secret"))
                continue
            try:
                out.append(self._write_copy(path, item))
                used += size
            except (CopyError, OSError) as exc:
                out.append(CapturedFile(portable(path), None, item.kind, size, None,
                                        skipped_reason=str(exc)))
        return out

    def collect_target(self, target: Target) -> TargetResult:
        root = next((expand(d) for d in target.detect if expand(d).exists()), None)
        if root is None:
            return TargetResult(target.id, target.name, target.category, False, None,
                                install=target.install.as_dict(), notes=target.notes)

        files: list[CapturedFile] = []
        errors: list[str] = []
        for item in target.items:
            try:
                files.extend(self.collect_item(item))
            except (OSError, ValueError) as exc:
                errors.append(f"{item.path}: {exc}")

        return TargetResult(
            target_id=target.id,
            name=target.name,
            category=target.category,
            present=True,
            root=portable(root),
            files=tuple(files),
            install=target.install.as_dict(),
            notes=target.notes,
            errors=tuple(errors),
        )
