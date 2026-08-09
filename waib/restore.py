"""Restore engine: put backed-up files back, and unseal the credential vault."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .copyio import CopyError, long_path, safe_copy, safe_write_text
from .paths import restore_target
from .secrets_vault import open_vault

Progress = Callable[[str], None]


def load_inventory(backup: Path) -> dict[str, Any]:
    path = backup / "INVENTORY.json"
    if not path.is_file():
        raise FileNotFoundError(f"No INVENTORY.json in {backup} — is this a Windows AI Backup folder?")
    return json.loads(path.read_text(encoding="utf-8"))


def restore_files(
    backup: Path,
    dry_run: bool = True,
    only_kinds: tuple[str, ...] = ("config", "prompt", "tree"),
    progress: Progress = print,
) -> dict[str, Any]:
    """Copy every stored file back to its original location."""
    inventory = load_inventory(backup)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    applied: list[str] = []
    skipped: list[tuple[str, str]] = []

    for target in inventory["targets"]:
        if not target["present"]:
            continue
        for entry in target["files"]:
            if not entry["archive"] or entry["kind"] not in only_kinds:
                continue
            source = backup / entry["archive"]
            if not os.path.isfile(long_path(source)):
                skipped.append((entry["source"], "missing from backup"))
                continue

            rel = entry["archive"][len("files/"):]
            destination = restore_target(rel)
            if destination is None:
                skipped.append((entry["source"], "unresolvable root variable"))
                continue

            if dry_run:
                applied.append(f"{entry['source']}  <-  {entry['archive']}")
                continue

            try:
                if os.path.exists(long_path(destination)):
                    safe_copy(destination, destination.with_name(f"{destination.name}.waib-{stamp}.bak"))
                safe_copy(source, destination)
            except CopyError as exc:
                skipped.append((entry["source"], str(exc)))
                continue
            applied.append(str(destination))
            progress(f"  [ok] {destination}")

    return {"applied": applied, "skipped": skipped, "dry_run": dry_run}


def unlock(
    backup: Path,
    passphrase: str,
    out_dir: Path | None = None,
    apply_in_place: bool = False,
    progress: Progress = print,
) -> dict[str, Any]:
    """Decrypt ``secrets.vault``; write files out, or restore them in place."""
    vault_path = backup / "secrets.vault"
    if not vault_path.is_file():
        raise FileNotFoundError(f"No secrets.vault in {backup}.")

    payload = open_vault(vault_path, passphrase)
    written: list[str] = []

    files = payload.get("files", {})
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for portable_path, content in files.items():
            safe = portable_path.replace("%", "").replace(":", "").replace("\\", "__").replace("/", "__")
            destination = out_dir / safe
            destination.write_text(content, encoding="utf-8")
            written.append(str(destination))
            progress(f"  [ok] {destination}")

        env_vars = payload.get("environment", {})
        if env_vars:
            script = out_dir / "restore-secret-env.ps1"
            body = "\n".join(
                f"[Environment]::SetEnvironmentVariable('{name}', '{value.replace(chr(39), chr(39) * 2)}', 'User')"
                for name, value in env_vars.items()
            )
            script.write_text(
                "# Recreates AI environment variables that hold credentials.\n" + body + "\n",
                encoding="utf-8",
            )
            written.append(str(script))
            progress(f"  [ok] {script}")

    if apply_in_place:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for portable_path, content in files.items():
            head, _, tail = portable_path.partition("%")[2].partition("%")
            root = os.environ.get(head)
            if not root:
                progress(f"  [skip] {portable_path} (unknown root {head})")
                continue
            destination = Path(root) / tail.lstrip("\\/")
            if os.path.exists(long_path(destination)):
                safe_copy(destination, destination.with_name(f"{destination.name}.waib-{stamp}.bak"))
            safe_write_text(destination, content)
            written.append(str(destination))
            progress(f"  [ok] {destination}")

    other_keys = [k for k in payload if k not in {"files", "environment", "errors"}]
    return {
        "written": written,
        "config_entries": {k: sorted(payload[k].keys()) for k in other_keys},
        "note": "Config-embedded secrets are listed by location; paste them back into the restored config files.",
        "values": {k: payload[k] for k in other_keys} if apply_in_place else {},
    }
