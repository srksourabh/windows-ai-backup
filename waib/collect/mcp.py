"""Build one unified MCP server registry across every AI client on the machine.

Each client stores MCP servers in its own dialect. This module normalises them
into a single schema so restore can rewrite every client's config from one
source of truth, and so duplicate servers are recognised across clients.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..catalog import TARGETS
from ..model import McpSource
from ..paths import expand, portable
from ..util import load_structured, redact

TRANSPORT_KEYS = ("url", "httpUrl", "serverUrl", "endpoint")


def _normalise(name: str, raw: Any, client: str, origin: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    clean, redactions = redact(raw)
    entry: dict[str, Any] = {
        "name": name,
        "clients": [client],
        "origins": [origin],
        "redacted_fields": redactions,
    }

    # Everything published here comes from `clean`: an access token can hide in a
    # positional argument or a query string, not just under an obvious key.
    url = next((clean[k] for k in TRANSPORT_KEYS if isinstance(clean.get(k), str)), None)
    if url:
        entry["transport"] = raw.get("type") or ("sse" if "sse" in url else "http")
        entry["url"] = url
        if isinstance(clean.get("headers"), dict):
            entry["headers"] = clean["headers"]
    else:
        entry["transport"] = raw.get("type") or "stdio"
        entry["command"] = clean.get("command")
        entry["args"] = list(clean.get("args") or [])
        env = clean.get("env")
        if isinstance(env, dict):
            entry["env"] = env
            entry["env_keys"] = sorted(env.keys())

    for optional in ("disabled", "trust", "autoApprove", "alwaysAllow", "tools", "timeout", "cwd"):
        if optional in raw:
            entry[optional] = clean.get(optional)

    entry["install_hint"] = _install_hint(entry)
    return entry


def _install_hint(entry: dict[str, Any]) -> str:
    """Reconstruct the one-liner that would provision this server again."""
    if entry.get("url"):
        return f"remote endpoint — no install needed ({entry['url']})"

    raw = (entry.get("command") or "").lower()
    # Configs reference launchers either bare (`uvx`) or by full path
    # (`C:\...\uvx.exe`); both must resolve to the same install command.
    command = raw.removesuffix(".exe").removesuffix(".cmd").removesuffix(".bat")
    args = [str(a) for a in entry.get("args") or []]

    if command.endswith("npx"):
        pkg = next((a for a in args if not a.startswith("-")), "")
        return f"npx -y {pkg}" if pkg else "npx"
    if command.endswith("uvx"):
        # `uvx --from <source> <entrypoint>` needs the source, not the entrypoint.
        if "--from" in args:
            source = args[args.index("--from") + 1] if args.index("--from") + 1 < len(args) else ""
            return f"uvx --from {source} {args[-1]}" if source else "uvx"
        pkg = next((a for a in args if not a.startswith("-")), "")
        return f"uvx {pkg}" if pkg else "uvx"
    if command.endswith("docker"):
        image = next((a for a in args if "/" in a or ":" in a), "")
        return f"docker pull {image}" if image else "docker"
    if command.endswith("python") or command.endswith("python3"):
        module = args[1] if len(args) > 1 and args[0] == "-m" else ""
        return f"pip install {module.replace('_', '-')}" if module else "python script — path recorded"
    if command.endswith(("node", "bun", "deno", "tsx")):
        return "local script — source backed up, run its rebuild command"
    return raw or "unknown"


def _extract(source: McpSource) -> Iterable[tuple[str, Any]]:
    path = expand(source.path)
    if not path.exists() or not path.is_file():
        return []
    data = load_structured(path)
    if not isinstance(data, dict):
        return []

    if source.fmt in {"mcp_servers", "toml_mcp"}:
        block = data.get("mcpServers") or data.get("mcp_servers") or {}
    elif source.fmt == "vscode_mcp":
        block = data.get("servers") or data.get("mcpServers") or {}
    elif source.fmt == "claude_json":
        block = dict(data.get("mcpServers") or {})
        for project_path, project in (data.get("projects") or {}).items():
            for name, cfg in (project.get("mcpServers") or {}).items():
                block[f"{name} (project: {Path(project_path).name})"] = cfg
    elif source.fmt == "yaml_mcp":
        block = data.get("extensions") or data.get("mcpServers") or {}
    else:
        block = {}

    return list(block.items()) if isinstance(block, dict) else []


def build_registry() -> dict[str, Any]:
    """Merge every discovered MCP declaration into a deduplicated registry."""
    servers: dict[str, dict[str, Any]] = {}
    scanned: list[dict[str, Any]] = []

    sources = [src for target in TARGETS for src in target.mcp_sources]
    for source in sources:
        path = expand(source.path)
        entries = list(_extract(source))
        scanned.append({
            "client": source.client,
            "path": portable(path),
            "exists": path.exists(),
            "server_count": len(entries),
        })
        for name, raw in entries:
            entry = _normalise(name, raw, source.client, portable(path))
            if entry is None:
                continue
            key = name.lower()
            if key in servers:
                merged = servers[key]
                merged["clients"] = sorted(set(merged["clients"]) | set(entry["clients"]))
                merged["origins"] = sorted(set(merged["origins"]) | set(entry["origins"]))
            else:
                servers[key] = entry

    ordered = sorted(servers.values(), key=lambda s: s["name"].lower())
    return {
        "server_count": len(ordered),
        "sources_scanned": scanned,
        "servers": ordered,
    }
