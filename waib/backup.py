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

from . import catalog_loader, discovery, licensing, manifest, restore_script
from .collect import envvars, extensions, identity, localservers, mcp, models, packages, plugins
from .collect.files import FileCollector
from .discovery import Discovery
from .licensing import License
from .paths import expand
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
    tools: list[str] | None = None,
    discover: bool = False,
) -> dict[str, Any]:
    """Produce a backup folder (and optionally a .zip) at ``destination``.

    ``tools`` restricts the run to specific catalog ids. ``discover`` adds AI
    tools found heuristically that the catalog does not list yet.
    """
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

    catalogue = catalog_loader.targets()
    progress(f"Scanning {len(catalogue)} known AI tools...  [{entitlement.label}]")

    present = [t for t in catalogue if any(expand(d).exists() for d in t.detect)]
    discovered: list[Discovery] = []

    if discover and entitlement.is_premium:
        progress("Looking for AI tools not in the catalog...")
        discovered = discovery.scan(discovery.known_roots(catalogue))
        for found in discovered:
            present.append(discovery.to_target(found))
        progress(f"  [+] {len(discovered)} uncatalogued tool(s) found")

    present_ids = [t.id for t in present]
    if entitlement.is_premium:
        selected_ids = [t for t in present_ids if not tools or t in tools]
    else:
        selected_ids = licensing.demo_selection(present_ids, tools)

    skipped_targets = [t.name for t in present if t.id not in selected_ids]

    results: list[TargetResult] = []
    for target in present:
        if target.id not in selected_ids:
            continue
        result = collector.collect_target(target)
        results.append(result)
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
        "discovered": {
            "count": len(discovered),
            "note": "AI tools found heuristically that the catalog does not list yet.",
            "tools": [
                {"name": d.name, "path": d.path, "score": d.score,
                 "signals": list(d.signals), "mcp_files": list(d.mcp_files),
                 "instruction_files": list(d.instruction_files)}
                for d in discovered
            ],
        },
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
    meta["catalog_size"] = len(catalogue)
    meta["tools_present"] = len(present)
    meta["tools_captured"] = len(selected_ids)
    meta["discovered_tools"] = [
        {"name": d.name, "path": d.path, "score": d.score, "signals": list(d.signals)}
        for d in discovered
    ]
    meta["licensed_to"] = entitlement.name or entitlement.email
    if skipped_targets:
        meta["demo_skipped_tools"] = sorted(skipped_targets)
        meta["demo_notice"] = (
            f"Demo edition captures {licensing.DEMO_TOOL_LIMIT} tools; "
            f"{len(skipped_targets)} more were found on this machine and left out, "
            f"along with the credential vault and custom MCP server source. "
            f"Unlock unlimited tools for a one-time $1 — {licensing.PURCHASE_URL}"
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
