"""Render INVENTORY.json (machine-readable) and INVENTORY.md (human-readable)."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .model import TargetResult
from .util import human_bytes

KIND_LABEL = {
    "config": "settings",
    "prompt": "prompt/rules",
    "tree": "files",
    "secret": "credential",
    "record": "noted only",
}


def build(results: list[TargetResult], registries: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    present = [r for r in results if r.present]
    return {
        "tool": "Windows AI Backup",
        "format_version": 1,
        **meta,
        "summary": {
            "tools_detected": len(present),
            "tools_scanned": len(results),
            "files_copied": sum(len([f for f in r.files if f.archive]) for r in present),
            "bytes_copied": sum(r.bytes_copied for r in present),
            "mcp_servers": registries.get("mcp", {}).get("server_count", 0),
            "skills": len(registries.get("plugins", {}).get("skills", [])),
            "agents": len(registries.get("plugins", {}).get("agents", [])),
            "commands": len(registries.get("plugins", {}).get("commands", [])),
            "ai_packages": len(registries.get("packages", {}).get("ai_packages", [])),
            "ide_extensions": sum(
                ide["count"] for ide in registries.get("extensions", {}).get("ides", [])
            ),
            "local_models": (
                registries.get("models", {}).get("local", {}).get("ollama", {}).get("count", 0)
                + registries.get("models", {}).get("local", {}).get("lmstudio", {}).get("count", 0)
            ),
            "env_vars": registries.get("env", {}).get("count", 0),
            "local_mcp_projects": registries.get("local_servers", {}).get("project_count", 0),
        },
        "targets": [asdict(r) for r in results],
        "registries": registries,
    }


def _table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> list[str]:
    if not rows:
        return ["_None found._", ""]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", r"\|") for c in row) + " |" for row in rows]
    out.append("")
    return out


def to_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    registries = data["registries"]
    lines: list[str] = [
        "# Windows AI Backup — Inventory",
        "",
        f"- **Created:** {data.get('created_at')}",
        f"- **Machine:** {data.get('hostname')}  |  **User:** {data.get('username')}",
        f"- **Secrets included:** {'yes (encrypted vault)' if data.get('secrets_included') else 'no'}",
        f"- **Edition:** {data.get('edition', 'demo').title()}"
        + (f" — licensed to {data['licensed_to']}" if data.get("licensed_to") else ""),
        "",
    ]

    if data.get("demo_notice"):
        skipped = data.get("demo_skipped_tools") or []
        lines += [
            "> [!IMPORTANT]",
            f"> **This is a Demo backup — it is not complete.** {data['demo_notice']}",
            ">",
            "> Tools present on the machine but *not* captured: "
            + ", ".join(skipped[:12]) + ("…" if len(skipped) > 12 else ""),
            "",
        ]

    lines += ["## At a glance", ""]
    lines += _table(
        [
            ("AI tools detected", summary["tools_detected"]),
            ("Files copied", f"{summary['files_copied']} ({human_bytes(summary['bytes_copied'])})"),
            ("MCP servers", summary["mcp_servers"]),
            ("Skills / agents / commands", f"{summary['skills']} / {summary['agents']} / {summary['commands']}"),
            ("AI packages + apps", summary["ai_packages"]),
            ("IDE extensions", summary["ide_extensions"]),
            ("Local models", summary["local_models"]),
            ("AI environment variables", summary["env_vars"]),
        ],
        ("Item", "Count"),
    )

    lines += ["## Master prompts & instruction files", "",
              "Copied verbatim and mirrored under `prompts/` for quick access.", ""]
    prompt_rows = [
        (f["source"], target["name"], human_bytes(f["size"]), f["archive"])
        for target in data["targets"] if target["present"]
        for f in target["files"] if f["kind"] == "prompt" and f["archive"]
    ]
    lines += _table(prompt_rows, ("Original location", "Tool", "Size", "In backup"))

    lines += ["## MCP servers", "",
              "One row per unique server; the same server used by several clients is merged.", ""]
    mcp_rows = [
        (
            s["name"],
            s.get("transport", ""),
            s.get("url") or f"{s.get('command', '')} {' '.join(map(str, s.get('args') or []))}".strip(),
            ", ".join(s.get("clients", [])),
            s.get("install_hint", ""),
        )
        for s in registries.get("mcp", {}).get("servers", [])
    ]
    lines += _table(mcp_rows, ("Server", "Transport", "Command / URL", "Used by", "Reinstall"))

    lines += ["### MCP config files found", ""]
    lines += _table(
        [
            (s["client"], s["path"], "yes" if s["exists"] else "no", s["server_count"])
            for s in registries.get("mcp", {}).get("sources_scanned", [])
            if s["exists"]
        ],
        ("Client", "Path", "Exists", "Servers"),
    )

    lines += [
        "## Locally-authored MCP servers",
        "",
        "Custom servers that exist on no registry. Source is copied; dependencies are rebuilt.",
        "",
    ]
    lines += _table(
        [
            (
                p["name"],
                p["path"],
                ", ".join(p["used_by_servers"]),
                p["strategy"],
                p.get("git_remote") or "—",
                p["rebuild"],
            )
            for p in registries.get("local_servers", {}).get("projects", [])
        ],
        ("Project", "Original path", "Serves", "Strategy", "Git remote", "Rebuild"),
    )

    lines += ["## AI tools detected", ""]
    lines += _table(
        [
            (
                t["name"],
                t["category"],
                t["root"] or "",
                len([f for f in t["files"] if f["archive"]]),
                human_bytes(sum(f["size"] for f in t["files"] if f["archive"])),
                ", ".join(f"{k}: {v}" for k, v in (t["install"] or {}).items() if k != "note") or "—",
            )
            for t in data["targets"] if t["present"]
        ],
        ("Tool", "Category", "Config root", "Files", "Size", "Reinstall via"),
    )

    lines += ["## Skills", ""]
    lines += _table(
        [(s["name"], s["owner"], s.get("description", "")[:90]) for s in registries.get("plugins", {}).get("skills", [])],
        ("Skill", "Owner", "Description"),
    )

    lines += ["## Agents", ""]
    lines += _table(
        [(a["name"], a["owner"]) for a in registries.get("plugins", {}).get("agents", [])],
        ("Agent", "Owner"),
    )

    lines += ["## Slash commands", ""]
    lines += _table(
        [(c["name"], c["owner"]) for c in registries.get("plugins", {}).get("commands", [])],
        ("Command", "Owner"),
    )

    lines += ["## Claude Code plugins & marketplaces", ""]
    lines += _table(
        [
            (p["plugin"], p["marketplace"], "on" if p["enabled"] else "off",
             (p.get("source") or {}).get("repo") or (p.get("source") or {}).get("url")
             or (p.get("source") or {}).get("path") or "")
            for p in registries.get("plugins", {}).get("claude_code", {}).get("plugins", [])
        ],
        ("Plugin", "Marketplace", "Enabled", "Source"),
    )

    lines += ["## Models", "", "### Cloud model selections", ""]
    lines += _table(
        [(m["client"], ", ".join(f"{k}={v}" for k, v in m["settings"].items())[:160], m["source"])
         for m in registries.get("models", {}).get("cloud_selections", [])],
        ("Client", "Settings", "Source"),
    )

    local = registries.get("models", {}).get("local", {})
    lines += ["### Local models (re-downloaded, never copied)", ""]
    lines += _table(
        [(m["reference"], "Ollama", human_bytes(m["approx_bytes"]), m["restore"])
         for m in local.get("ollama", {}).get("models", [])]
        + [(m["repo"], "LM Studio", human_bytes(m["bytes"]), m["restore"])
           for m in local.get("lmstudio", {}).get("models", [])],
        ("Model", "Runtime", "Size", "Restore"),
    )

    lines += ["## Packages & applications", ""]
    lines += _table(
        [(p["name"], p["manager"], p.get("version") or "", p["restore"])
         for p in registries.get("packages", {}).get("ai_packages", [])],
        ("Package", "Manager", "Version", "Restore command"),
    )

    lines += ["### AI desktop applications", ""]
    lines += _table(
        [(a["name"], a["path"]) for a in registries.get("packages", {}).get("ai_applications", [])],
        ("Application", "Install path"),
    )

    lines += ["## IDE extensions", ""]
    for ide in registries.get("extensions", {}).get("ides", []):
        lines += [f"### {ide['ide']} ({ide['count']})", "",
                  f"Reinstall: `{ide['restore_command']}`", ""]
        lines += _table([(e["id"], e.get("version") or "") for e in ide["extensions"]], ("Extension id", "Version"))

    lines += ["## Accounts & identifiers", ""]
    for account in registries.get("identity", {}).get("accounts", []):
        lines += [f"### {account['client']}", "", f"Source: `{account['source']}`", "", "```json"]
        import json as _json

        lines += [_json.dumps(account["values"], indent=2)[:2500], "```", ""]

    lines += ["## Environment variables", ""]
    lines += _table(
        [(v["name"], v["scope"], "secret" if v["is_secret"] else str(v["value"])[:60])
         for v in registries.get("env", {}).get("variables", [])],
        ("Variable", "Scope", "Value"),
    )

    lines += ["## Recorded but not copied", "",
              "These are re-downloadable or transient; the inventory keeps their location and size.", ""]
    lines += _table(
        [
            (f["source"], target["name"], human_bytes(f["size"]), f["skipped_reason"] or "")
            for target in data["targets"] if target["present"]
            for f in target["files"] if not f["archive"]
        ],
        ("Location", "Tool", "Size", "Reason"),
    )

    errors = [(t["name"], e) for t in data["targets"] for e in t.get("errors", [])]
    if errors:
        lines += ["## Warnings", ""]
        lines += _table(errors, ("Tool", "Problem"))

    return "\n".join(lines) + "\n"
