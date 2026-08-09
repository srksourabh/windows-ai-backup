"""Backup orchestration: scan every catalog target, build registries, write output."""
from __future__ import annotations

import json
import os
import platform
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import licensing, manifest, restore_script
from .catalog import TARGETS
from .collect import envvars, extensions, identity, localservers, mcp, models, packages, plugins
from .collect.files import FileCollector
from .licensing import License
from .model import TargetResult
from .scrub import scrub_text
from .secrets_vault import seal

Progress = Callable[[str], None]


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _meta(capture_secrets: bool) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "hostname": socket.gethostname(),
        "username": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
        "windows": platform.platform(),
        "python": platform.python_version(),
        "secrets_included": capture_secrets,
    }


def _local_server_target(local_registry: dict[str, Any]) -> TargetResult:
    """Wrap copied local-MCP-server source as a synthetic target."""
    from .model import CapturedFile

    files = tuple(
        CapturedFile(
            source=entry["source"],
            archive=entry["archive"],
            kind="tree",
            size=entry["size"],
            sha256=None,
        )
        for project in local_registry["projects"]
        for entry in project.get("captured", [])
    )
    projects = local_registry["projects"]
    return TargetResult(
        target_id="local-mcp-servers",
        name="Locally-authored MCP servers",
        category="MCP Server",
        present=bool(projects),
        root=projects[0]["path"] if projects else None,
        files=files,
        install={"note": "Rebuild dependencies with each project's recorded command"},
        notes=local_registry["note"],
    )


def run_backup(
    destination: Path,
    capture_secrets: bool = False,
    passphrase: str | None = None,
    make_zip: bool = True,
    keep_folder: bool = True,
    progress: Progress = print,
    license: License | None = None,
) -> dict[str, Any]:
    """Produce a backup folder (and optionally a .zip) at ``destination``."""
    entitlement = license or licensing.load()

    if capture_secrets and not entitlement.is_premium:
        raise ValueError(
            "The encrypted credential vault is a Premium feature.\n"
            f"Unlock it for a one-time $1: {licensing.PURCHASE_URL}"
        )
    if capture_secrets and not passphrase:
        raise ValueError("Secret capture requires a passphrase.")

    out_dir = destination / f"WindowsAIBackup_{_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "registry").mkdir(exist_ok=True)

    collector = FileCollector(out_dir, capture_secrets)

    progress(f"Scanning AI tools...  [{entitlement.label}]")
    results: list[TargetResult] = []
    skipped_targets: list[str] = []
    for target in TARGETS:
        if not entitlement.is_premium and target.id not in licensing.DEMO_TARGET_IDS:
            skipped_targets.append(target.name)
            continue
        result = collector.collect_target(target)
        results.append(result)
        if result.present:
            copied = len([f for f in result.files if f.archive])
            progress(f"  [+] {result.name}: {copied} file(s)")

    progress("Building MCP server registry...")
    mcp_registry = mcp.build_registry()

    if entitlement.is_premium:
        progress("Backing up locally-authored MCP servers...")
        local_registry = localservers.collect(mcp_registry, out_dir)
        for project in local_registry["projects"]:
            progress(f"  [+] {project['name']}: {project['strategy']}")
    else:
        # Demo lists the projects so the report is honest about what exists,
        # but copies no source.
        local_registry = localservers.discover(mcp_registry)
    # Surface the copied source through the normal target/file machinery so both
    # restore.ps1 and `waib restore` put it back with no special-casing.
    results.append(_local_server_target(local_registry))

    progress("Indexing skills, agents, commands, plugins...")
    plugin_registry = plugins.collect()

    progress("Inventorying models...")
    model_registry = models.collect()

    progress("Inventorying packages and applications...")
    package_registry = packages.collect()

    progress("Listing IDE extensions...")
    extension_registry = extensions.collect()

    progress("Reading account identifiers...")
    identity_registry = identity.collect()

    progress("Reading AI environment variables...")
    env_registry, env_secrets = envvars.collect(capture_secrets)
    if env_secrets:
        collector.vault.setdefault("environment", {}).update(env_secrets)

    registries: dict[str, Any] = {
        "mcp": mcp_registry,
        "local_servers": local_registry,
        "plugins": plugin_registry,
        "models": model_registry,
        "packages": package_registry,
        "extensions": extension_registry,
        "identity": identity_registry,
        "env": env_registry,
    }

    # Registries are assembled from many parsers; a credential that slipped past
    # any one of them must not reach disk in a generated report either.
    def write_scrubbed(path: Path, text: str) -> None:
        clean, _ = scrub_text(text)
        path.write_text(clean, encoding="utf-8")

    for name, payload in registries.items():
        write_scrubbed(
            out_dir / "registry" / f"{name}.json",
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        )

    meta = _meta(capture_secrets)
    meta["edition"] = entitlement.edition.value
    meta["licensed_to"] = entitlement.name or entitlement.email
    if skipped_targets:
        meta["demo_skipped_tools"] = sorted(skipped_targets)
        meta["demo_notice"] = (
            f"Demo edition: {len(skipped_targets)} tools were not captured, and no "
            f"credential vault or custom MCP server source was included. "
            f"Unlock everything for a one-time $1 — {licensing.PURCHASE_URL}"
        )

    inventory = manifest.build(results, registries, meta)
    write_scrubbed(
        out_dir / "INVENTORY.json",
        json.dumps(inventory, indent=2, ensure_ascii=False, default=str),
    )
    write_scrubbed(out_dir / "INVENTORY.md", manifest.to_markdown(inventory))

    progress("Writing restore plan...")
    write_scrubbed(out_dir / "restore.ps1", restore_script.build(inventory))
    write_scrubbed(out_dir / "RESTORE.md", restore_script.readme(inventory))

    vault_path: Path | None = None
    if capture_secrets and collector.vault:
        progress("Sealing encrypted secret vault...")
        vault_path = seal(collector.vault, passphrase or "", out_dir / "secrets.vault")

    zip_path: Path | None = None
    if make_zip:
        progress("Creating zip archive...")
        zip_path = Path(shutil.make_archive(str(out_dir), "zip", root_dir=out_dir))
        if not keep_folder:
            shutil.rmtree(out_dir, ignore_errors=True)

    return {
        "folder": None if (make_zip and not keep_folder) else out_dir,
        "zip": zip_path,
        "vault": vault_path,
        "inventory": inventory,
    }
