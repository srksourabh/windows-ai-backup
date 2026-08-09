"""Edition gating: Demo (free) and Premium ($1, one-time).

A license key is a signed payload, not a shared secret. The private signing key
lives only with the publisher; the executable embeds the matching **public** key
and can therefore verify a key offline, with no activation server and no phone
home.

Honest limits: at a $1 price point the cryptography stops casual copying, not a
determined person with a debugger. That is a deliberate trade — the tool stays
fully offline and never contacts a licence server, which matters more for
software that reads your AI configuration than unbreakable enforcement does.

Restore is never gated. A backup you already made must always be restorable,
whatever the edition — holding someone's own data hostage would be indefensible.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .paths import expand

#: Ed25519 public key of the publisher, base64. Replace when you mint your own
#: keypair with ``python tools/keygen.py init``.
PUBLISHER_PUBLIC_KEY = "p/kEGjqRG0XD6hwImIGCrPoNUkMHaoQodJvVWQ7pmzQ="

LICENSE_PATH = "%APPDATA%/WindowsAIBackup/license.key"
PURCHASE_URL = "https://github.com/srksourabh/windows-ai-backup/blob/main/PRICING.md"


class Edition(str, Enum):
    DEMO = "demo"
    PREMIUM = "premium"


@dataclass(frozen=True)
class License:
    """A verified license, or the implicit demo license when none is present."""

    edition: Edition
    name: str = ""
    email: str = ""
    issued: str = ""
    order: str = ""
    invalid_reason: str = ""

    @property
    def is_premium(self) -> bool:
        return self.edition is Edition.PREMIUM

    @property
    def label(self) -> str:
        if self.is_premium:
            who = self.name or self.email or "licensed"
            return f"Premium — {who}"
        return "Demo"


DEMO = License(Edition.DEMO)


# --------------------------------------------------------------------- limits

#: How many tools a Demo backup may capture. Which five is the user's choice.
DEMO_TOOL_LIMIT = 5

#: Used only when the user does not pick, so the Demo still lands on something
#: useful. Anything present but not in this list can still be chosen explicitly.
DEMO_PREFERRED_ORDER = (
    "claude-code", "cursor", "codex", "gemini-cli", "claude-desktop",
    "vscode", "windsurf", "copilot-cli", "antigravity", "cline-cli",
    "opencode", "aider", "ollama", "lmstudio", "continue",
)

DEMO_LIMITS = (
    f"Backs up any {DEMO_TOOL_LIMIT} tools you choose (--tools), out of every tool found",
    "No encrypted credential vault (--secrets is Premium)",
    "No discovery of uncatalogued tools (--discover is Premium)",
    "Custom MCP server source is listed but not copied",
    "INVENTORY.md carries a demo notice",
)

PREMIUM_FEATURES = (
    "Unlimited tools — every one found on the machine, and every tool added later",
    "Discovery of AI tools that are not in the catalog yet",
    "Encrypted credential vault (AES-256-GCM, scrypt-derived key)",
    "Custom MCP server source captured and rebuilt on restore",
    "Clean, unwatermarked reports",
    "One-time $1 — no subscription, no account, works offline forever",
)


def demo_selection(present_ids: list[str], requested: list[str] | None = None) -> list[str]:
    """Choose which tools a Demo backup captures.

    An explicit ``--tools`` selection wins, truncated to the limit. Otherwise the
    preferred order picks the most broadly useful tools that are actually present,
    topped up with whatever else was found.
    """
    if requested:
        return [t for t in requested if t in present_ids][:DEMO_TOOL_LIMIT]

    ranked = [t for t in DEMO_PREFERRED_ORDER if t in present_ids]
    ranked += [t for t in present_ids if t not in ranked]
    return ranked[:DEMO_TOOL_LIMIT]


# ---------------------------------------------------------------- verification

def _verify(payload: bytes, signature: bytes) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return False

    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLISHER_PUBLIC_KEY))
    except (ValueError, TypeError, base64.binascii.Error):
        return False

    try:
        public.verify(signature, payload)
        return True
    except InvalidSignature:
        return False


def parse_key(text: str) -> License:
    """Verify a license key string. Returns the demo license on any failure."""
    compact = "".join(text.split())
    if not compact:
        return License(Edition.DEMO, invalid_reason="empty key")

    try:
        blob = base64.urlsafe_b64decode(compact + "=" * (-len(compact) % 4))
        envelope = json.loads(blob.decode("utf-8"))
        payload_b64 = envelope["payload"]
        signature = base64.b64decode(envelope["signature"])
        payload_bytes = base64.b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return License(Edition.DEMO, invalid_reason="malformed key")

    if not _verify(payload_bytes, signature):
        return License(Edition.DEMO, invalid_reason="signature does not match")

    if payload.get("edition") != Edition.PREMIUM.value:
        return License(Edition.DEMO, invalid_reason="key is not a Premium key")

    return License(
        edition=Edition.PREMIUM,
        name=str(payload.get("name", "")),
        email=str(payload.get("email", "")),
        issued=str(payload.get("issued", "")),
        order=str(payload.get("order", "")),
    )


def license_file() -> Path:
    return expand(LICENSE_PATH)


def load() -> License:
    """Read the installed license, if any."""
    path = license_file()
    if not path.is_file():
        return DEMO
    try:
        return parse_key(path.read_text(encoding="utf-8"))
    except OSError:
        return DEMO


def install(key: str) -> License:
    """Verify a key and, if valid, store it for future runs."""
    verified = parse_key(key)
    if not verified.is_premium:
        return verified

    path = license_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.strip() + "\n", encoding="utf-8")
    return verified


def remove() -> bool:
    path = license_file()
    if path.is_file():
        path.unlink()
        return True
    return False


def stamp() -> str:
    return datetime.now(timezone.utc).date().isoformat()
