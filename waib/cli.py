"""Command-line interface for Windows AI Backup."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from . import licensing
from . import restore as restore_engine
from . import catalog_loader, discovery
from .backup import run_backup
from .collect import mcp
from .paths import expand
from .secrets_vault import VaultError
from .util import human_bytes

VERSION = "2.0.0"
BANNER = r"""
 __      __ _         _                   _    ___   ___             _
 \ \    / /(_) _ _  __| | ___ __ __ ___   /_\  |_ _| | _ ) __ _  __ | |__ _  _  _ __
  \ \/\/ / | || ' \/ _` |/ _ \\ V  V /(_) / _ \  | |  | _ \/ _` |/ _|| / /| || || '_ \
   \_/\_/  |_||_||_\__,_|\___/ \_/\_/    /_/ \_\|___| |___/\__,_|\__||_\_\ \_,_|| .__/
                                                                               |_|
"""


def _default_destination() -> Path:
    return expand("~/Documents/WindowsAIBackup")


def _passphrase(confirm: bool) -> str:
    first = getpass.getpass("Vault passphrase: ")
    if not first:
        raise SystemExit("A passphrase is required when capturing secrets.")
    if confirm:
        again = getpass.getpass("Confirm passphrase: ")
        if first != again:
            raise SystemExit("Passphrases did not match.")
    return first


def cmd_backup(args: argparse.Namespace) -> int:
    destination = Path(args.out) if args.out else _default_destination()
    entitlement = licensing.load()

    if args.secrets and not entitlement.is_premium:
        print("The encrypted credential vault is a Premium feature.")
        print(f"Unlock everything for a one-time $1: {licensing.PURCHASE_URL}")
        print("Already bought it?  WindowsAIBackup.exe activate <key>")
        return 3

    if args.discover and not entitlement.is_premium:
        print("Discovering uncatalogued tools is a Premium feature.")
        print(f"Unlock everything for a one-time $1: {licensing.PURCHASE_URL}")
        return 3

    selected: list[str] | None = None
    if args.tools:
        requested = [name for chunk in args.tools for name in chunk.split(",")]
        selected, unknown = catalog_loader.resolve_ids(requested)
        if unknown:
            print(f"Unknown tool(s): {', '.join(unknown)}")
            print("Run  WindowsAIBackup.exe catalog  to see valid ids.")
            return 2
        if not entitlement.is_premium and len(selected) > licensing.DEMO_TOOL_LIMIT:
            print(f"Demo backs up {licensing.DEMO_TOOL_LIMIT} tools; you asked for {len(selected)}.")
            print(f"The first {licensing.DEMO_TOOL_LIMIT} will be used. Premium removes the limit:")
            print(f"  {licensing.PURCHASE_URL}")

    passphrase = _passphrase(confirm=True) if args.secrets else None

    result = run_backup(
        destination=destination,
        capture_secrets=args.secrets,
        passphrase=passphrase,
        make_zip=not args.no_zip,
        keep_folder=not args.zip_only,
        progress=lambda msg: print(msg, flush=True),
        license=entitlement,
        tools=selected,
        discover=args.discover,
    )

    summary = result["inventory"]["summary"]
    print("")
    print("Backup complete.")
    if result["folder"]:
        print(f"  Folder : {result['folder']}")
    if result["zip"]:
        print(f"  Zip    : {result['zip']}  ({human_bytes(result['zip'].stat().st_size)})")
    if result["vault"]:
        print(f"  Vault  : {result['vault']}  (encrypted)")
    print("")
    print(f"  {summary['tools_detected']} AI tools, {summary['files_copied']} files "
          f"({human_bytes(summary['bytes_copied'])})")
    print(f"  {summary['mcp_servers']} MCP servers | {summary['skills']} skills | "
          f"{summary['agents']} agents | {summary['commands']} commands")
    print(f"  {summary['ai_packages']} packages | {summary['ide_extensions']} extensions | "
          f"{summary['local_models']} local models | {summary['env_vars']} env vars")
    print("")
    print("  Read INVENTORY.md for the full what-and-where report.")
    if not args.secrets and entitlement.is_premium:
        print("  Note: credentials were NOT captured. Re-run with --secrets to include them (encrypted).")
    inventory = result["inventory"]
    print(f"  Catalog: {inventory.get('catalog_size')} tools known | "
          f"{inventory.get('tools_present')} present here | "
          f"{inventory.get('tools_captured')} captured")
    if not entitlement.is_premium:
        skipped = inventory.get("demo_skipped_tools") or []
        print("")
        print(f"  DEMO EDITION — capped at {licensing.DEMO_TOOL_LIMIT} tools; "
              f"{len(skipped)} more were found and left out.")
        print("  Choose which five with:  --tools claude-code,cursor,codex,vscode,ollama")
        for limit in licensing.DEMO_LIMITS[1:]:
            print(f"    - {limit}")
        print(f"  Unlimited tools, one-time $1: {licensing.PURCHASE_URL}")
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    key = args.key or _ask_multiline_key()
    result = licensing.install(key)
    if not result.is_premium:
        print(f"Activation failed: {result.invalid_reason}")
        print(f"Keys are issued at {licensing.PURCHASE_URL}")
        return 2
    print(f"Activated — {result.label}")
    print(f"  Issued : {result.issued}")
    print(f"  Stored : {licensing.license_file()}")
    print("\nPremium unlocked:")
    for feature in licensing.PREMIUM_FEATURES:
        print(f"  - {feature}")
    return 0


def cmd_license(args: argparse.Namespace) -> int:
    if args.remove:
        print("License removed." if licensing.remove() else "No license was installed.")
        return 0

    current = licensing.load()
    print(f"Edition : {current.label}")
    if current.is_premium:
        print(f"Issued  : {current.issued}")
        print(f"File    : {licensing.license_file()}")
        return 0

    print("\nDemo limits:")
    for limit in licensing.DEMO_LIMITS:
        print(f"  - {limit}")
    print("\nPremium — one-time $1:")
    for feature in licensing.PREMIUM_FEATURES:
        print(f"  - {feature}")
    print(f"\n  {licensing.PURCHASE_URL}")
    return 0


def _ask_multiline_key() -> str:
    print("Paste your Premium key, then press Enter twice:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line.strip())
    return "".join(lines)


def cmd_scan(args: argparse.Namespace) -> int:
    entitlement = licensing.load()
    print(BANNER)
    print(f"  Edition: {entitlement.label}")
    catalogue = catalog_loader.targets()
    print(f"\nCatalog: {len(catalogue)} AI tools known\n")

    present = []
    for target in catalogue:
        root = next((expand(d) for d in target.detect if expand(d).exists()), None)
        if root is None:
            if args.all:
                print(f"  [ ] {target.name}")
            continue
        present.append(target)
        # Scanning is never limited — you see the whole picture before deciding to buy.
        print(f"  [x] {target.name:<38} {root}")

    print(f"\n{len(present)} of {len(catalogue)} catalogued tools present on this machine.")

    if args.discover:
        print("\nSearching for AI tools that are not in the catalog...")
        for found in discovery.scan(discovery.known_roots(catalogue)):
            print(f"  [?] {found.name:<38} {found.path}")
            print(f"      score {found.score}: {'; '.join(found.signals[:2])}")

    if not entitlement.is_premium and len(present) > licensing.DEMO_TOOL_LIMIT:
        extra = len(present) - licensing.DEMO_TOOL_LIMIT
        print(f"\nDemo captures {licensing.DEMO_TOOL_LIMIT} of these; {extra} would be left out.")
        print(f"Premium removes the limit: {licensing.PURCHASE_URL}")

    registry = mcp.build_registry()
    print(f"\nMCP servers: {registry['server_count']}")
    for server in registry["servers"]:
        where = server.get("url") or f"{server.get('command')} {' '.join(map(str, server.get('args') or []))}".strip()
        print(f"  - {server['name']:<28} {where[:70]}")
        print(f"    used by: {', '.join(server['clients'])}")
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    """List, validate, or extend the tool catalog."""
    if args.where:
        print("Catalog files, in load order (later files override earlier ids):")
        print("")
        for path in catalog_loader.catalog_files():
            print(f"  {path}")
        print("")
        print("Drop your own JSON into:")
        print(f"  {expand(catalog_loader.USER_LOCAL_CATALOG_DIR)}")
        return 0

    if args.validate:
        try:
            loaded, issues = catalog_loader.load_targets(strict=False)
        except catalog_loader.CatalogError as exc:
            print(f"invalid: {exc}")
            return 2
        print(f"{len(loaded)} tools loaded from {len(catalog_loader.catalog_files())} file(s).")
        if issues:
            print("")
            print(f"{len(issues)} problem(s):")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        print("No problems found.")
        return 0

    catalogue = catalog_loader.targets()
    if args.json:
        print(json.dumps([{"id": t.id, "name": t.name, "category": t.category,
                           "detect": list(t.detect), "items": len(t.items)}
                          for t in catalogue], indent=2))
        return 0

    grouped = catalog_loader.categories()
    for category in sorted(grouped):
        entries = grouped[category]
        print("")
        print(f"{category}  ({len(entries)})")
        for target in entries:
            here = any(expand(d).exists() for d in target.detect)
            print(f"  {'*' if here else ' '} {target.id:<26} {target.name}")
    print("")
    print(f"{len(catalogue)} tools in the catalog. '*' marks tools present on this machine.")
    print("Use ids with:  backup --tools <id>,<id>")
    for warning in catalog_loader.warnings():
        print(f"  [warn] {warning}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """Report AI tools the catalog does not know about yet."""
    catalogue = catalog_loader.targets()
    found = discovery.scan(discovery.known_roots(catalogue))
    if args.json:
        print(json.dumps([{"name": d.name, "path": d.path, "score": d.score,
                           "signals": list(d.signals), "mcp_files": list(d.mcp_files),
                           "instruction_files": list(d.instruction_files)} for d in found], indent=2))
        return 0

    print(f"{len(found)} AI tool(s) found that are not in the catalog of {len(catalogue)}:")
    print("")
    for d in found:
        print(f"  {d.name}")
        print(f"    path   : {d.path}")
        print(f"    score  : {d.score}")
        print(f"    signals: {'; '.join(d.signals[:3])}")
        print("")
    if found:
        print("Include these in a backup with:  backup --discover   (Premium)")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    registry = mcp.build_registry()
    if args.json:
        print(json.dumps(registry, indent=2, ensure_ascii=False))
        return 0
    for server in registry["servers"]:
        print(f"{server['name']}")
        print(f"  transport : {server.get('transport')}")
        if server.get("url"):
            print(f"  url       : {server['url']}")
        else:
            print(f"  command   : {server.get('command')} {' '.join(map(str, server.get('args') or []))}")
        if server.get("env_keys"):
            print(f"  env keys  : {', '.join(server['env_keys'])}")
        print(f"  clients   : {', '.join(server['clients'])}")
        print(f"  reinstall : {server.get('install_hint')}")
        print("")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    backup = Path(args.backup)
    result = restore_engine.restore_files(
        backup=backup,
        dry_run=not args.apply,
        progress=lambda msg: print(msg, flush=True),
    )
    if result["dry_run"]:
        print(f"\nDry run — {len(result['applied'])} file(s) would be restored:")
        for line in result["applied"][:200]:
            print(f"  {line}")
        if len(result["applied"]) > 200:
            print(f"  ... and {len(result['applied']) - 200} more")
        print("\nRe-run with --apply to write them.")
    else:
        print(f"\nRestored {len(result['applied'])} file(s).")
    for path, reason in result["skipped"]:
        print(f"  [skip] {path}: {reason}")
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    backup = Path(args.backup)
    passphrase = _passphrase(confirm=False)
    try:
        result = restore_engine.unlock(
            backup=backup,
            passphrase=passphrase,
            out_dir=Path(args.out) if args.out else None,
            apply_in_place=args.apply,
            progress=lambda msg: print(msg, flush=True),
        )
    except VaultError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"\nWrote {len(result['written'])} file(s).")
    if result["config_entries"]:
        print("\nSecrets embedded in config files (paste back into the restored configs):")
        for source, keys in result["config_entries"].items():
            print(f"  {source}")
            for key in keys:
                print(f"    - {key}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="WindowsAIBackup",
        description="Back up and restore every AI tool setting on a Windows machine.",
    )
    parser.add_argument("--version", action="version", version=f"Windows AI Backup {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    backup_cmd = sub.add_parser("backup", help="Create a backup folder and zip")
    backup_cmd.add_argument("-o", "--out", help="Destination directory (default: ~/Documents/WindowsAIBackup)")
    backup_cmd.add_argument("--secrets", action="store_true",
                            help="Include credentials in an encrypted vault (prompts for a passphrase)")
    backup_cmd.add_argument("--no-zip", action="store_true", help="Leave the folder uncompressed")
    backup_cmd.add_argument("--zip-only", action="store_true", help="Delete the folder after zipping")
    backup_cmd.add_argument("--tools", action="append", metavar="IDS",
                            help="Only these tools (comma-separated ids; repeatable). "
                                 "Demo uses this to choose which 5 to capture.")
    backup_cmd.add_argument("--discover", action="store_true",
                            help="Also capture AI tools not yet in the catalog (Premium)")
    backup_cmd.set_defaults(func=cmd_backup)

    scan_cmd = sub.add_parser("scan", help="Show what would be backed up, without writing anything")
    scan_cmd.add_argument("--all", action="store_true", help="Also list tools that are not installed")
    scan_cmd.add_argument("--discover", action="store_true",
                          help="Also search for tools missing from the catalog")
    scan_cmd.set_defaults(func=cmd_scan)

    catalog_cmd = sub.add_parser("catalog", help="List the tool catalog, or validate and extend it")
    catalog_cmd.add_argument("--json", action="store_true", help="Emit JSON")
    catalog_cmd.add_argument("--validate", action="store_true", help="Check every catalog file parses")
    catalog_cmd.add_argument("--where", action="store_true", help="Show which files the catalog loads from")
    catalog_cmd.set_defaults(func=cmd_catalog)

    discover_cmd = sub.add_parser("discover", help="Find AI tools that are not in the catalog")
    discover_cmd.add_argument("--json", action="store_true", help="Emit JSON")
    discover_cmd.set_defaults(func=cmd_discover)

    mcp_cmd = sub.add_parser("mcp", help="Print the unified MCP server registry")
    mcp_cmd.add_argument("--json", action="store_true", help="Emit JSON")
    mcp_cmd.set_defaults(func=cmd_mcp)

    restore_cmd = sub.add_parser("restore", help="Copy settings from a backup back into place")
    restore_cmd.add_argument("-b", "--backup", required=True, help="Path to an extracted backup folder")
    restore_cmd.add_argument("--apply", action="store_true", help="Actually write files (default is a dry run)")
    restore_cmd.set_defaults(func=cmd_restore)

    unlock_cmd = sub.add_parser("unlock", help="Decrypt the credential vault from a backup")
    unlock_cmd.add_argument("-b", "--backup", required=True, help="Path to an extracted backup folder")
    unlock_cmd.add_argument("-o", "--out", help="Write decrypted files into this directory")
    unlock_cmd.add_argument("--apply", action="store_true", help="Write credential files back to their original paths")
    unlock_cmd.set_defaults(func=cmd_unlock)

    activate_cmd = sub.add_parser("activate", help="Activate a Premium license key")
    activate_cmd.add_argument("key", nargs="?", help="The key; omit to paste it interactively")
    activate_cmd.set_defaults(func=cmd_activate)

    license_cmd = sub.add_parser("license", help="Show the current edition and what each one includes")
    license_cmd.add_argument("--remove", action="store_true", help="Delete the installed license")
    license_cmd.set_defaults(func=cmd_license)

    return parser


def _dispatch(argv: list[str]) -> int:
    """Run one command; used by both the CLI and the interactive menu."""
    args = build_parser().parse_args(argv)
    return args.func(args)


def main(argv: list[str] | None = None) -> int:
    from . import interactive

    raw = list(sys.argv[1:] if argv is None else argv)
    if interactive.should_run(raw):
        return interactive.run(_dispatch)

    parser = build_parser()
    args = parser.parse_args(raw)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except (OSError, ValueError, VaultError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
