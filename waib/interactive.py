"""Menu shown when the executable is launched with no arguments (double-click)."""
from __future__ import annotations

import sys
from pathlib import Path

from .paths import expand

MENU = """
  1  Scan          See every AI tool and setting found on this PC
  2  Back up       Settings only (no credentials)        [recommended]
  3  Back up + secrets   Includes an encrypted credential vault
  4  MCP servers   List every MCP server across all clients
  5  Restore       Apply a backup to this PC
  6  Unlock        Decrypt a backup's credential vault
  7  Edition       Compare Demo vs Premium
  8  Activate      Enter a Premium license key
  0  Exit
"""


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return answer or default


def _pause() -> None:
    try:
        input("\nPress Enter to return to the menu...")
    except EOFError:
        pass


def run(dispatch) -> int:
    """Loop the menu, delegating each choice to ``dispatch(argv)``."""
    from .cli import BANNER, VERSION

    print(BANNER)
    print(f"  Windows AI Backup {VERSION}")
    print("  Backs up every AI tool setting on this PC so a fresh Windows can be rebuilt.\n")

    default_out = str(expand("~/Documents/WindowsAIBackup"))

    while True:
        print(MENU)
        choice = _ask("Choose", "2")

        if choice in {"0", "q", "exit", "quit"}:
            return 0

        try:
            if choice == "1":
                dispatch(["scan"])
            elif choice in {"2", "3"}:
                out = _ask("Save to", default_out)
                argv = ["backup", "--out", out]
                if choice == "3":
                    argv.append("--secrets")
                dispatch(argv)
            elif choice == "4":
                dispatch(["mcp"])
            elif choice == "5":
                backup = _ask("Backup folder")
                if not backup:
                    print("  No folder given.")
                    _pause()
                    continue
                if not (Path(backup) / "INVENTORY.json").is_file():
                    print(f"  {backup} is not a Windows AI Backup folder.")
                    _pause()
                    continue
                dispatch(["restore", "--backup", backup])
                if _ask("Apply for real? (y/N)", "n").lower().startswith("y"):
                    dispatch(["restore", "--backup", backup, "--apply"])
            elif choice == "6":
                backup = _ask("Backup folder")
                out = _ask("Write decrypted files to", str(Path(backup or ".") / "restored-secrets"))
                dispatch(["unlock", "--backup", backup, "--out", out])
            elif choice == "7":
                dispatch(["license"])
            elif choice == "8":
                dispatch(["activate"])
            else:
                print("  Unrecognised choice.")
        except SystemExit as exc:
            print(f"  (exit code {exc.code})")
        except KeyboardInterrupt:
            print("\n  Cancelled.")
        except Exception as exc:  # keep the menu alive whatever a command does
            print(f"  error: {exc}")

        _pause()


def should_run(argv: list[str]) -> bool:
    """Interactive only when launched bare from a console the user can type into."""
    return not argv and sys.stdin is not None and sys.stdin.isatty()
