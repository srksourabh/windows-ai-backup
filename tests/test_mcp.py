"""MCP normalisation decides whether servers come back after a rebuild."""
from __future__ import annotations

import json

import pytest

from waib.collect import mcp
from waib.model import McpSource


def test_normalise_stdio_server():
    entry = mcp._normalise(
        "serena",
        {"command": "uvx", "args": ["--from", "serena-agent", "serena"], "env": {"KEY": "abcdef123456"}},
        "Claude Code",
        "origin.json",
    )
    assert entry["transport"] == "stdio"
    assert entry["command"] == "uvx"
    assert entry["env"]["KEY"] == "<<WAIB:REDACTED>>"
    assert entry["env_keys"] == ["KEY"]


def test_normalise_remote_server():
    entry = mcp._normalise("hf", {"url": "https://huggingface.co/mcp"}, "Claude Code", "o.json")
    assert entry["transport"] == "http"
    assert entry["url"] == "https://huggingface.co/mcp"
    assert "no install needed" in entry["install_hint"]


@pytest.mark.parametrize(
    ("command", "args", "expected"),
    [
        ("npx", ["-y", "firecrawl-mcp"], "npx -y firecrawl-mcp"),
        ("uvx", ["serena-agent"], "uvx serena-agent"),
        ("docker", ["run", "-i", "ghcr.io/github/github-mcp-server"], "docker pull ghcr.io/github/github-mcp-server"),
        ("python.exe", ["-m", "mcp_india_stack"], "pip install mcp-india-stack"),
    ],
)
def test_install_hint_reconstructs_the_provisioning_command(command, args, expected):
    entry = mcp._normalise("x", {"command": command, "args": args}, "c", "o")
    assert entry["install_hint"] == expected


def test_claude_json_dialect_includes_project_scoped_servers(tmp_path, monkeypatch):
    config = tmp_path / ".claude.json"
    config.write_text(
        json.dumps({
            "mcpServers": {"global-one": {"command": "npx", "args": ["-y", "a"]}},
            "projects": {r"C:\work\repo": {"mcpServers": {"scoped": {"command": "node", "args": ["s.js"]}}}},
        }),
        encoding="utf-8",
    )
    names = [name for name, _ in mcp._extract(McpSource(str(config), "claude_json", "Claude Code"))]
    assert "global-one" in names
    assert any(n.startswith("scoped (project:") for n in names)


def test_vscode_dialect_reads_servers_key(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"servers": {"a": {"command": "npx", "args": []}}}), encoding="utf-8")
    assert [n for n, _ in mcp._extract(McpSource(str(config), "vscode_mcp", "VS Code"))] == ["a"]


def test_missing_file_yields_nothing():
    assert list(mcp._extract(McpSource("Z:/nope/mcp.json", "mcp_servers", "X"))) == []


@pytest.mark.parametrize(
    ("command", "args", "expected"),
    [
        (r"C:\Users\me\.local\bin\uvx.exe", ["serena-agent"], "uvx serena-agent"),
        (r"C:\Program Files\nodejs\npx.cmd", ["-y", "firecrawl-mcp"], "npx -y firecrawl-mcp"),
        ("uvx", ["--from", "git+https://github.com/a/b", "entry"],
         "uvx --from git+https://github.com/a/b entry"),
    ],
)
def test_install_hint_handles_full_paths_and_from_sources(command, args, expected):
    """A launcher referenced by absolute path must resolve like the bare name."""
    entry = mcp._normalise("x", {"command": command, "args": args}, "c", "o")
    assert entry["install_hint"] == expected


def test_local_script_hint_points_at_the_rebuild_path():
    entry = mcp._normalise("x", {"command": "node", "args": [r"C:\srv\index.js"]}, "c", "o")
    assert "source backed up" in entry["install_hint"]
