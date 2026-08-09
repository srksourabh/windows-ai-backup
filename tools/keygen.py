"""Publisher-side tool: mint Premium license keys.

Never ship this, and never commit ``publisher_private.key``. The executable only
ever carries the public half.

    python tools/keygen.py init                       # one time — create a keypair
    python tools/keygen.py issue --name "Jane Doe" --email jane@example.com
    python tools/keygen.py verify <key>

After ``init``, paste the printed public key into
``waib/licensing.py`` as ``PUBLISHER_PUBLIC_KEY`` and rebuild.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRIVATE_KEY_PATH = Path(__file__).resolve().parent / "publisher_private.key"


def cmd_init(args: argparse.Namespace) -> int:
    if PRIVATE_KEY_PATH.exists() and not args.force:
        print(f"{PRIVATE_KEY_PATH} already exists. Pass --force to replace it.")
        print("Replacing it invalidates every key you have already issued.")
        return 1

    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIVATE_KEY_PATH.write_text(base64.b64encode(raw).decode(), encoding="utf-8")

    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_b64 = base64.b64encode(public_raw).decode()

    print(f"Private key written to {PRIVATE_KEY_PATH}")
    print("  Keep it secret. Keep it backed up. It is gitignored.\n")
    print("Paste this into waib/licensing.py as PUBLISHER_PUBLIC_KEY:\n")
    print(f'PUBLISHER_PUBLIC_KEY = "{public_b64}"')
    return 0


def _load_private() -> Ed25519PrivateKey:
    if not PRIVATE_KEY_PATH.is_file():
        raise SystemExit(f"No keypair yet — run: python {Path(__file__).name} init")
    raw = base64.b64decode(PRIVATE_KEY_PATH.read_text(encoding="utf-8").strip())
    return Ed25519PrivateKey.from_private_bytes(raw)


def cmd_issue(args: argparse.Namespace) -> int:
    private = _load_private()
    payload = {
        "edition": "premium",
        "name": args.name,
        "email": args.email,
        "order": args.order,
        "issued": datetime.now(timezone.utc).date().isoformat(),
        "product": "windows-ai-backup",
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = private.sign(payload_bytes)

    envelope = {
        "payload": base64.b64encode(payload_bytes).decode(),
        "signature": base64.b64encode(signature).decode(),
    }
    key = base64.urlsafe_b64encode(
        json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    ).decode().rstrip("=")

    print(f"Premium key for {args.name or args.email or 'customer'}:\n")
    for start in range(0, len(key), 76):
        print("  " + key[start:start + 76])
    print("\nActivate with:\n  WindowsAIBackup.exe activate <key>")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from waib import licensing

    result = licensing.parse_key(args.key)
    if result.is_premium:
        print(f"VALID — {result.label}  (issued {result.issued}, order {result.order or 'n/a'})")
        return 0
    print(f"INVALID — {result.invalid_reason}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint Windows AI Backup Premium keys.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create the publisher keypair (run once)")
    init.add_argument("--force", action="store_true", help="Replace an existing keypair")
    init.set_defaults(func=cmd_init)

    issue = sub.add_parser("issue", help="Issue a Premium key")
    issue.add_argument("--name", default="", help="Customer name")
    issue.add_argument("--email", default="", help="Customer email")
    issue.add_argument("--order", default="", help="Order or payment reference")
    issue.set_defaults(func=cmd_issue)

    verify = sub.add_parser("verify", help="Check a key against the embedded public key")
    verify.add_argument("key")
    verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
