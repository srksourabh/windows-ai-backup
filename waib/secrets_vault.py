"""Passphrase-encrypted vault for credentials.

Windows DPAPI is deliberately *not* used: DPAPI keys are bound to the user
profile and machine, so a DPAPI-sealed vault becomes unreadable after the very
reinstall this tool exists to survive. A scrypt-derived AES-256-GCM key travels.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

MAGIC = b"WAIB1"
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LEN = 32
SALT_LEN = 16
NONCE_LEN = 12


class VaultError(RuntimeError):
    pass


def _aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover
        raise VaultError(
            "The 'cryptography' package is required for secret capture.\n"
            "Install it with:  python -m pip install cryptography"
        ) from exc
    return AESGCM


def _derive(passphrase: str, salt: bytes) -> bytes:
    import hashlib

    return hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_LEN,
        maxmem=SCRYPT_N * SCRYPT_R * 256,
    )


def seal(payload: dict[str, Any], passphrase: str, destination: Path) -> Path:
    """Encrypt ``payload`` to ``destination``. Returns the written path."""
    if not passphrase:
        raise VaultError("A passphrase is required to seal the vault.")

    aesgcm_cls = _aesgcm()
    salt = secrets.token_bytes(SALT_LEN)
    nonce = secrets.token_bytes(NONCE_LEN)
    key = _derive(passphrase, salt)
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = aesgcm_cls(key).encrypt(nonce, blob, MAGIC)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(MAGIC + salt + nonce + ciphertext)
    try:
        os.chmod(destination, 0o600)
    except OSError:
        pass
    return destination


def open_vault(source: Path, passphrase: str) -> dict[str, Any]:
    """Decrypt a vault file. Raises :class:`VaultError` on a wrong passphrase."""
    aesgcm_cls = _aesgcm()
    raw = source.read_bytes()
    if not raw.startswith(MAGIC):
        raise VaultError(f"{source} is not a Windows AI Backup vault.")

    offset = len(MAGIC)
    salt = raw[offset:offset + SALT_LEN]
    nonce = raw[offset + SALT_LEN:offset + SALT_LEN + NONCE_LEN]
    ciphertext = raw[offset + SALT_LEN + NONCE_LEN:]

    key = _derive(passphrase, salt)
    try:
        plaintext = aesgcm_cls(key).decrypt(nonce, ciphertext, MAGIC)
    except Exception as exc:
        raise VaultError("Wrong passphrase, or the vault file is corrupt.") from exc
    return json.loads(plaintext.decode("utf-8"))
