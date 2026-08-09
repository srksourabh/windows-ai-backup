"""Last line of defence: strip credentials from any text leaving the machine.

Structured redaction only reaches values it can see as JSON/TOML/YAML nodes. It
misses three real cases found in practice:

* an API key hardcoded in a ``.js`` or ``.py`` source file;
* a token embedded *inside* a longer string (``"npx x --key sk-live-..."``);
* a config whose extension or dialect the parser could not handle.

Every text file written into a backup, and every generated report, passes through
:func:`scrub_text` — so a credential has to survive both layers to escape.
"""
from __future__ import annotations

import re
from pathlib import Path

REDACTED = "<<WAIB:REDACTED>>"

#: Unanchored, prefix-anchored patterns. Each has a vendor-specific prefix so a
#: match is a credential rather than an unlucky identifier.
TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    # `sk-` is used by OpenAI, Anthropic, and every compatible vendor
    # (sk-ant-…, sk-proj-…, sk-gamma-…), so match the prefix broadly.
    re.compile(r"sk-[A-Za-z0-9_-]{24,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),                 # GitHub
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{16,}"),                   # GitLab
    re.compile(r"AIza[A-Za-z0-9_-]{30,}"),                     # Google
    re.compile(r"ya29\.[A-Za-z0-9_-]{30,}"),                   # Google OAuth
    re.compile(r"xox[baprse]-[A-Za-z0-9-]{15,}"),              # Slack
    re.compile(r"hf_[A-Za-z0-9]{30,}"),                        # Hugging Face
    re.compile(r"AKIA[0-9A-Z]{16}"),                           # AWS access key id
    re.compile(r"sbp_[A-Za-z0-9]{30,}"),                       # Supabase
    re.compile(r"gsk_[A-Za-z0-9]{30,}"),                       # Groq
    re.compile(r"pplx-[A-Za-z0-9]{20,}"),                      # Perplexity
    re.compile(r"tvly-[A-Za-z0-9_-]{16,}"),                    # Tavily
    # Anchored on a word boundary and exactly 32 hex, so a UUID segment such as
    # `...befc-4ac1-9536-10203c2efe6e` is not mistaken for a Firecrawl key.
    re.compile(r"\bfc-[a-f0-9]{32}\b"),                        # Firecrawl
    re.compile(r"nvapi-[A-Za-z0-9_-]{30,}"),                   # NVIDIA
    re.compile(r"r8_[A-Za-z0-9]{30,}"),                        # Replicate
    re.compile(r"dop_v1_[a-f0-9]{32,}"),                       # DigitalOcean
    re.compile(r"dckr_pat_[A-Za-z0-9_-]{20,}"),                # Docker Hub
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]{0,4000}?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{24,}={0,2}"),
)

#: ``KEY = "value"`` / ``"token": "value"`` in any language, including source code.
ASSIGNMENT_PATTERN = re.compile(
    r"""(?ix)
    (                                        # group 1: the name and separator
      (?:[A-Za-z0-9_.\[\]"']*)
      (?:api[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|
         client[_-]?secret|secret[_-]?key|private[_-]?key|password|passwd|
         bearer[_-]?token|[_.\b]token|[_.\b]secret|apikey)
      \s* [:=] \s* ["']?
    )
    ( [A-Za-z0-9_\-./+=]{16,} )              # group 2: the value
    """,
)

#: Placeholders and obvious non-secrets that must not be mangled.
SAFE_VALUES = re.compile(
    r"(?i)^(your[_-]?|example|placeholder|changeme|xxx+|<|\$\{|%[A-Z_]+%|"
    r"process\.env|os\.environ|null|none|true|false|undefined|redacted)",
)


def _is_placeholder(value: str) -> bool:
    return bool(SAFE_VALUES.match(value.strip())) or REDACTED in value


def scrub_text(text: str) -> tuple[str, int]:
    """Return ``(clean_text, replacements)``.

    Idempotent: text already containing the marker is left alone.
    """
    count = 0

    def replace_token(match: re.Match[str]) -> str:
        nonlocal count
        if _is_placeholder(match.group(0)):
            return match.group(0)
        count += 1
        return REDACTED

    clean = text
    for pattern in TOKEN_PATTERNS:
        clean = pattern.sub(replace_token, clean)

    def replace_assignment(match: re.Match[str]) -> str:
        nonlocal count
        value = match.group(2)
        if _is_placeholder(value) or value == REDACTED:
            return match.group(0)
        count += 1
        return match.group(1) + REDACTED

    clean = ASSIGNMENT_PATTERN.sub(replace_assignment, clean)
    return clean, count


def scrub_file(path: Path) -> int:
    """Scrub a file that was already written into the backup.

    Returns the number of credentials removed. Binary content is left untouched —
    a file that does not decode as UTF-8 is not a config or a source file.
    """
    from .copyio import long_path

    try:
        with open(long_path(path), "r", encoding="utf-8") as handle:
            original = handle.read()
    except (OSError, UnicodeDecodeError, ValueError):
        return 0
    clean, count = scrub_text(original)
    if count:
        try:
            with open(long_path(path), "w", encoding="utf-8", newline="") as handle:
                handle.write(clean)
        except OSError:
            return 0
    return count


#: File names that are credential stores no matter which tool owns them.
SECRET_FILENAMES = re.compile(
    r"(?i)^(\.?credentials?(\.json|\.yaml|\.yml)?|auth\.json|secrets?\.json|"
    r"oauth[_-]?creds?\.json|token(s)?\.json|\.env(\..*)?|.*\.pem|.*\.key|"
    r"id_(rsa|ed25519|ecdsa)|stored_tokens|\.netrc|\.npmrc|\.pgpass)$",
)


def is_secret_filename(name: str) -> bool:
    """True when a file should be vaulted rather than copied, on its name alone."""
    return bool(SECRET_FILENAMES.match(name))
