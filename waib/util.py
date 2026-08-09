"""Shared helpers: hashing, config parsing, and secret redaction."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

#: Keys whose values are treated as credentials wherever they appear in a config.
SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|credential|authorization|"
    r"private[_-]?key|client[_-]?secret|access[_-]?key|refresh[_-]?token|"
    r"session[_-]?key|bearer|cookie|dsn|connection[_-]?string|"
    # A name that *is* KEY, or ends in _KEY, is a credential; KEYBOARD and monkey are not.
    r"(?:^|[_-])key$)",
    re.IGNORECASE,
)

#: Case-sensitive so camelCase ``apiKey``/``authKey`` match but ``monkey`` does not.
CAMEL_KEY_PATTERN = re.compile(r"[a-z0-9]Key$")

#: Values that look like credentials even under an innocuous key name.
SECRET_VALUE_PATTERNS = (
    re.compile(r"^sk-[A-Za-z0-9_-]{16,}$"),          # OpenAI / Anthropic style
    re.compile(r"^sk-ant-[A-Za-z0-9_-]{16,}$"),
    re.compile(r"^gh[pousr]_[A-Za-z0-9]{16,}$"),      # GitHub
    re.compile(r"^github_pat_[A-Za-z0-9_]{20,}$"),
    re.compile(r"^AIza[A-Za-z0-9_-]{20,}$"),          # Google
    re.compile(r"^xox[baprs]-[A-Za-z0-9-]{10,}$"),    # Slack
    re.compile(r"^hf_[A-Za-z0-9]{20,}$"),             # Hugging Face
    re.compile(r"^AKIA[0-9A-Z]{16}$"),                # AWS
    re.compile(r"^ya29\.[A-Za-z0-9_-]{20,}$"),        # Google OAuth
    re.compile(r"^ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),  # JWT
    re.compile(r"^sbp_[A-Za-z0-9]{20,}$"),            # Supabase
    re.compile(r"^gsk_[A-Za-z0-9]{20,}$"),            # Groq
    re.compile(r"^pplx-[A-Za-z0-9]{20,}$"),           # Perplexity
    re.compile(r"^tvly-[A-Za-z0-9_-]{16,}$"),         # Tavily
    re.compile(r"^fc-[a-f0-9]{32}$"),                 # Firecrawl (fc- + 32 hex)
    re.compile(r"^nvapi-[A-Za-z0-9_-]{20,}$"),        # NVIDIA
    re.compile(r"^r8_[A-Za-z0-9]{20,}$"),             # Replicate
    re.compile(r"^glpat-[A-Za-z0-9_-]{16,}$"),        # GitLab
    re.compile(r"^dop_v1_[a-f0-9]{32,}$"),            # DigitalOcean
    re.compile(r"^dckr_pat_[A-Za-z0-9_-]{16,}$"),     # Docker Hub
)
# A bare 40-char alphanumeric run is deliberately *not* treated as a secret:
# git commit SHAs, content hashes and machine ids all take that shape.

#: Command-line flags whose *following* argument is a credential.
SECRET_FLAG_PATTERN = re.compile(
    r"^--?(api[_-]?key|key|token|access[_-]?token|auth[_-]?token|secret|"
    r"client[_-]?secret|password|passwd|pat|bearer|credential)s?$",
    re.IGNORECASE,
)

REDACTED = "<<WAIB:REDACTED>>"


def sha256_file(path: Path, chunk: int = 1 << 20) -> str | None:
    """Digest a file, or return None when it cannot be read (locked, vanished)."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while block := handle.read(chunk):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def looks_secret(key: str, value: Any) -> bool:
    if isinstance(value, str):
        if any(p.match(value.strip()) for p in SECRET_VALUE_PATTERNS):
            return True
        if not value.strip() or len(value) < 8:
            return False
        if SECRET_KEY_PATTERN.search(key) or CAMEL_KEY_PATTERN.search(key):
            return True
    return False


def redact(data: Any, trail: str = "") -> tuple[Any, list[str]]:
    """Return ``(clean_copy, redacted_paths)`` without mutating ``data``."""
    found: list[str] = []

    if isinstance(data, dict):
        clean: dict[str, Any] = {}
        for key, value in data.items():
            where = f"{trail}.{key}" if trail else str(key)
            if looks_secret(str(key), value):
                clean[key] = REDACTED
                found.append(where)
            else:
                sub, sub_found = redact(value, where)
                clean[key] = sub
                found.extend(sub_found)
        return clean, found

    if isinstance(data, list):
        cleaned: list[Any] = []
        redact_next = False
        for index, value in enumerate(data):
            where = f"{trail}[{index}]"
            # `["--access-token", "sbp_live..."]` hides a credential in a position,
            # not under a key — the flag before it is the only signal.
            if redact_next and isinstance(value, str) and value.strip():
                cleaned.append(REDACTED)
                found.append(where)
                redact_next = False
                continue
            redact_next = isinstance(value, str) and bool(SECRET_FLAG_PATTERN.match(value.strip()))

            if isinstance(value, str) and "=" in value and value.startswith("-"):
                flag, _, inline = value.partition("=")
                if SECRET_FLAG_PATTERN.match(flag) and inline:
                    cleaned.append(f"{flag}={REDACTED}")
                    found.append(where)
                    continue

            sub, sub_found = redact(value, where)
            cleaned.append(sub)
            found.extend(sub_found)
        return cleaned, found

    if isinstance(data, str) and any(p.match(data.strip()) for p in SECRET_VALUE_PATTERNS):
        return REDACTED, [trail or "<value>"]

    return data, found


def extract_secrets(data: Any, trail: str = "") -> dict[str, str]:
    """Collect the real secret values keyed by their dotted location."""
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            where = f"{trail}.{key}" if trail else str(key)
            if looks_secret(str(key), value):
                out[where] = value
            else:
                out.update(extract_secrets(value, where))
    elif isinstance(data, list):
        capture_next = False
        for index, value in enumerate(data):
            where = f"{trail}[{index}]"
            if capture_next and isinstance(value, str) and value.strip():
                out[where] = value
                capture_next = False
                continue
            capture_next = isinstance(value, str) and bool(SECRET_FLAG_PATTERN.match(value.strip()))
            if isinstance(value, str) and value.startswith("-") and "=" in value:
                flag, _, inline = value.partition("=")
                if SECRET_FLAG_PATTERN.match(flag) and inline:
                    out[where] = inline
                    continue
            out.update(extract_secrets(value, where))
    elif isinstance(data, str) and any(p.match(data.strip()) for p in SECRET_VALUE_PATTERNS):
        out[trail or "<value>"] = data
    return out


def load_structured(path: Path) -> Any | None:
    """Parse JSON / JSONC / TOML / YAML. Returns None when unparsable."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None

    suffix = path.suffix.lower()
    if suffix == ".toml":
        if tomllib is None:
            return None
        try:
            return tomllib.loads(text)
        except Exception:
            return None

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore

            return yaml.safe_load(text)
        except Exception:
            return _naive_yaml(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _json_with_comments(text)


def _json_with_comments(text: str) -> Any | None:
    """Best-effort JSONC: strip // and /* */ comments plus trailing commas."""
    without_block = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    without_line = re.sub(r"(^|\s)//[^\n]*", r"\1", without_block)
    without_trailing = re.sub(r",(\s*[}\]])", r"\1", without_line)
    try:
        return json.loads(without_trailing)
    except json.JSONDecodeError:
        return None


def _naive_yaml(text: str) -> dict[str, Any] | None:
    """Minimal top-level ``key: value`` reader for when PyYAML is unavailable."""
    out: dict[str, Any] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or line[0].isspace() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip() or {}
    return out or None


def resolve_executable(name: str) -> str | None:
    """Find an executable on PATH, including Windows ``.cmd``/``.bat`` shims.

    ``subprocess`` with ``shell=False`` will not find ``npm``, because the real
    file is ``npm.cmd``; ``shutil.which`` consults PATHEXT and does.
    """
    import shutil

    direct = shutil.which(name)
    if direct:
        return direct
    for extension in (".cmd", ".bat", ".exe", ".ps1"):
        found = shutil.which(name + extension)
        if found:
            return found
    return None


def run(args: list[str], timeout: int = 90) -> tuple[int, str]:
    """Run a command, returning ``(returncode, stdout+stderr)``. Never raises."""
    if args:
        resolved = resolve_executable(args[0])
        if resolved is None:
            return 127, "not installed"
        args = [resolved, *args[1:]]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return 127, "not installed"
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except OSError as exc:
        return 1, str(exc)


def human_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
