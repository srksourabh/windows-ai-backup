"""Generate the bundled catalog data files under ``waib/data/catalog.d``.

Kept as a script rather than inline JSON so the hundreds of entries stay
readable and consistent. Run it after editing, then commit the generated JSON —
the JSON is what ships, this file is only how it is maintained.

    python tools/build_catalog.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "waib" / "data" / "catalog.d"

JUNK = ["**/node_modules/**", "**/.git/**", "**/__pycache__/**", "**/*.log", "**/cache/**"]
MD = ["**/*.md"]
JSONY = ["**/*.json", "**/*.yaml", "**/*.yml", "**/*.toml"]
PROMPTY = ["**/*.md", "**/*.txt", "**/*.mdc", "**/*.prompt"]


def tool(
    tool_id: str,
    name: str,
    category: str,
    detect: list[str],
    items: list[dict],
    *,
    mcp: list[dict] | None = None,
    install: dict | None = None,
    extensions_dir: str | None = None,
    notes: str = "",
) -> dict:
    entry = {"id": tool_id, "name": name, "category": category, "detect": detect, "items": items}
    if mcp:
        entry["mcp_sources"] = mcp
    if install:
        entry["install"] = install
    if extensions_dir:
        entry["extensions_dir"] = extensions_dir
    if notes:
        entry["notes"] = notes
    return entry


def cfg(path: str, note: str = "") -> dict:
    return {"path": path, "kind": "config", **({"note": note} if note else {})}


def prompt(path: str, note: str = "", include: list[str] | None = None) -> dict:
    entry = {"path": path, "kind": "prompt"}
    if note:
        entry["note"] = note
    if include:
        entry["include"] = include
    return entry


def tree(path: str, note: str = "", include: list[str] | None = None, mb: float = 60) -> dict:
    entry = {"path": path, "kind": "tree", "exclude": JUNK, "max_total_mb": mb}
    if note:
        entry["note"] = note
    if include:
        entry["include"] = include
    return entry


def secret(path: str, note: str = "") -> dict:
    return {"path": path, "kind": "secret", **({"note": note} if note else {})}


def record(path: str, note: str = "") -> dict:
    return {"path": path, "kind": "record", **({"note": note} if note else {})}


def mcp_src(path: str, fmt: str, client: str) -> dict:
    return {"path": path, "fmt": fmt, "client": client}


# --------------------------------------------------------------- Agent CLIs

AGENT_CLIS = [
    tool("aider", "Aider", "Agent CLI", ["~/.aider.conf.yml", "~/.aider.model.settings.yml"], [
        cfg("~/.aider.conf.yml", "Default model and flags"),
        cfg("~/.aider.model.settings.yml", "Per-model settings"),
        cfg("~/.aider.model.metadata.json"),
    ], install={"pipx": "aider-chat", "uv": "aider-chat", "docs": "https://aider.chat/docs"}),

    tool("amazon-q", "Amazon Q Developer", "Agent CLI", ["~/.aws/amazonq"], [
        cfg("~/.aws/amazonq/mcp.json", "MCP servers"),
        cfg("~/.aws/amazonq/global_context.json"),
        tree("~/.aws/amazonq/profiles", include=["**/*.json", "**/*.md"]),
        tree("~/.aws/amazonq/cli-agents", "Custom agents", include=["**/*.json"]),
    ], mcp=[mcp_src("~/.aws/amazonq/mcp.json", "mcp_servers", "Amazon Q")],
        install={"docs": "https://docs.aws.amazon.com/amazonq/"}),

    tool("claude-code", "Claude Code", "Agent CLI", ["~/.claude", "~/.claude.json"], [
        cfg("~/.claude.json", "Global config: MCP servers, account, per-project settings"),
        cfg("~/.claude/settings.json", "Permissions, plugins, statusline, effort level"),
        cfg("~/.claude/settings.local.json", "Machine-local overrides"),
        prompt("~/.claude/CLAUDE.md", "Global master prompt"),
        prompt("~/CLAUDE.md", "Home-scope master prompt"),
        prompt("~/.claude/rules", "Rule set loaded into every session", MD),
        tree("~/.claude/agents", "Custom subagent definitions", MD),
        tree("~/.claude/commands", "Custom slash commands", MD),
        tree("~/.claude/skills", "Custom and installed skills", mb=200),
        tree("~/.claude/local-plugins", "Locally authored plugins"),
        tree("~/.claude/scripts", "Helper scripts referenced by hooks and statusline"),
        cfg("~/.claude/statusline-command.js"),
        cfg("~/.claude/statusline-command.ps1"),
        cfg("~/.claude/statusline-command.sh"),
        cfg("~/.claude/keybindings.json"),
        cfg("~/.claude/mcp_config.json", "Standalone MCP config"),
        cfg("~/.claude/claude_desktop_config.json", "Desktop MCP config staged by the CLI"),
        cfg("~/.claude/plugins/installed_plugins.json", "Enabled plugins, restored by name"),
        cfg("~/.claude/plugins/known_marketplaces.json", "Plugin marketplace sources"),
        cfg("~/.claude/plugins/config.json"),
        cfg("~/.claude/skills-lock.json", "Pinned skill versions"),
        prompt("~/.claude/projects", "Per-project auto-memory", ["**/memory/**/*.md"]),
        secret("~/.claude/.credentials.json", "OAuth tokens and API key"),
        record("~/.claude/plugins/cache", "Plugin payloads — re-cloned from marketplaces"),
        record("~/.claude/projects", "Session transcripts — not needed for a fresh setup"),
    ], mcp=[mcp_src("~/.claude.json", "claude_json", "Claude Code"),
            mcp_src("~/.claude/mcp_config.json", "mcp_servers", "Claude Code")],
        install={"npm": "@anthropic-ai/claude-code", "docs": "https://docs.claude.com/en/docs/claude-code",
                 "note": "Native installer: irm https://claude.ai/install.ps1 | iex"}),

    tool("cline-cli", "Cline CLI", "Agent CLI", ["~/.cline"], [
        tree("~/.cline/data", "Settings, rules, MCP config", JSONY + MD, mb=40),
    ], mcp=[mcp_src("~/.cline/data/mcp_settings.json", "mcp_servers", "Cline CLI")],
        install={"npm": "cline", "docs": "https://docs.cline.bot"}),

    tool("codex", "OpenAI Codex CLI", "Agent CLI", ["~/.codex"], [
        cfg("~/.codex/config.toml", "Models, providers, sandbox policy, MCP servers"),
        prompt("~/.codex/AGENTS.md", "Global master prompt"),
        prompt("~/.codex/prompts", "Saved prompts", MD),
        tree("~/.codex/skills", "Skills"),
        secret("~/.codex/auth.json", "API key or ChatGPT session"),
        record("~/.codex/sessions", "Session transcripts"),
    ], mcp=[mcp_src("~/.codex/config.toml", "toml_mcp", "Codex CLI")],
        install={"npm": "@openai/codex", "docs": "https://developers.openai.com/codex/cli"}),

    tool("copilot-cli", "GitHub Copilot CLI", "Agent CLI", ["~/.copilot"], [
        cfg("~/.copilot/config.json", "Model and client settings"),
        cfg("~/.copilot/mcp-config.json", "MCP servers"),
    ], mcp=[mcp_src("~/.copilot/mcp-config.json", "mcp_servers", "Copilot CLI")],
        install={"npm": "@github/copilot"}),

    tool("crush", "Charm Crush", "Agent CLI", ["~/.config/crush", "%LOCALAPPDATA%/crush"], [
        cfg("~/.config/crush/crush.json", "Providers, models, MCP servers"),
        cfg("%LOCALAPPDATA%/crush/crush.json"),
        prompt("~/.config/crush/CRUSH.md"),
    ], mcp=[mcp_src("~/.config/crush/crush.json", "mcp_servers", "Crush")],
        install={"npm": "@charmland/crush", "docs": "https://github.com/charmbracelet/crush"}),

    tool("gemini-cli", "Google Gemini CLI", "Agent CLI", ["~/.gemini"], [
        cfg("~/.gemini/settings.json", "MCP servers, hooks, IDE and security settings"),
        prompt("~/.gemini/GEMINI.md", "Global master prompt"),
        tree("~/.gemini/commands", "Custom commands", ["**/*.toml", "**/*.md"]),
        tree("~/.gemini/skills", "Skills"),
        cfg("~/.gemini/trustedFolders.json"),
        cfg("~/.gemini/google_accounts.json", "Signed-in Google account identity"),
        cfg("~/.gemini/installation_id", "Install identity"),
        secret("~/.gemini/oauth_creds.json", "Google OAuth credentials"),
    ], mcp=[mcp_src("~/.gemini/settings.json", "mcp_servers", "Gemini CLI")],
        install={"npm": "@google/gemini-cli"}),

    tool("goose", "Block Goose", "Agent CLI", ["~/.config/goose", "%APPDATA%/Goose"], [
        cfg("~/.config/goose/config.yaml", "Providers and extensions (MCP)"),
        cfg("~/.config/goose/profiles.yaml"),
        prompt("~/.config/goose/.goosehints"),
        cfg("%APPDATA%/Goose/config.yaml"),
    ], mcp=[mcp_src("~/.config/goose/config.yaml", "yaml_mcp", "Goose")],
        install={"docs": "https://block.github.io/goose"}),

    tool("gptme", "gptme", "Agent CLI", ["~/.config/gptme"], [
        cfg("~/.config/gptme/config.toml", "Providers, models, tools"),
        prompt("~/.config/gptme/prompts", include=PROMPTY),
    ], install={"pipx": "gptme"}),

    tool("kilocode-cli", "Kilo Code CLI", "Agent CLI", ["~/.kilocode"], [
        tree("~/.kilocode", "Settings and rules", JSONY + MD, mb=20),
    ], install={"npm": "@kilocode/cli"}),

    tool("llm-datasette", "llm (Datasette)", "Agent CLI",
         ["%APPDATA%/io.datasette.llm", "~/.config/io.datasette.llm"], [
        cfg("%APPDATA%/io.datasette.llm/default_model.txt"),
        cfg("%APPDATA%/io.datasette.llm/extra-openai-models.yaml", "Custom model endpoints"),
        prompt("%APPDATA%/io.datasette.llm/templates", include=["**/*.yaml", "**/*.yml"]),
        secret("%APPDATA%/io.datasette.llm/keys.json", "Provider API keys"),
        record("%APPDATA%/io.datasette.llm/logs.db", "Prompt log database"),
    ], install={"pipx": "llm", "docs": "https://llm.datasette.io"}),

    tool("mods", "Charm Mods", "Agent CLI", ["%APPDATA%/mods", "~/.config/mods"], [
        cfg("%APPDATA%/mods/mods.yml", "Providers, models, roles"),
        cfg("~/.config/mods/mods.yml"),
    ], install={"choco": "mods", "docs": "https://github.com/charmbracelet/mods"}),

    tool("open-interpreter", "Open Interpreter", "Agent CLI",
         ["%APPDATA%/Open Interpreter", "~/.config/open-interpreter"], [
        tree("%APPDATA%/Open Interpreter/profiles", "Profiles", ["**/*.yaml", "**/*.py"]),
        cfg("~/.config/open-interpreter/config.yaml"),
    ], install={"pipx": "open-interpreter"}),

    tool("opencode", "OpenCode", "Agent CLI",
         ["~/.config/opencode", "%APPDATA%/ai.opencode.desktop"], [
        cfg("~/.config/opencode/opencode.json", "Providers, models, MCP servers"),
        prompt("~/.config/opencode/AGENTS.md"),
        tree("~/.config/opencode/agent", "Custom agents", MD),
        tree("~/.config/opencode/command", "Custom commands", MD),
        secret("~/.local/share/opencode/auth.json", "Provider credentials"),
    ], mcp=[mcp_src("~/.config/opencode/opencode.json", "mcp_servers", "OpenCode")],
        install={"npm": "opencode-ai", "docs": "https://opencode.ai/docs"}),

    tool("openhands", "OpenHands", "Agent CLI", ["~/.openhands"], [
        cfg("~/.openhands/settings.json", "LLM provider and agent settings"),
        cfg("~/.openhands/config.toml"),
        record("~/.openhands/sessions", "Session state"),
    ], install={"docs": "https://docs.all-hands.dev"}),

    tool("plandex", "Plandex", "Agent CLI", ["~/.plandex-home-v2", "~/.plandex-home"], [
        cfg("~/.plandex-home-v2/settings.json"),
        secret("~/.plandex-home-v2/auth.json"),
    ], install={"docs": "https://plandex.ai"}),

    tool("qodo", "Qodo Command", "Agent CLI", ["~/.qodo"], [
        tree("~/.qodo", "Agents, settings, MCP", JSONY + MD, mb=20),
    ], mcp=[mcp_src("~/.qodo/mcp.json", "mcp_servers", "Qodo")],
        install={"npm": "@qodo/command"}),

    tool("shell-gpt", "ShellGPT", "Agent CLI", ["~/.config/shell_gpt"], [
        cfg("~/.config/shell_gpt/.sgptrc", "Model and behaviour settings"),
        prompt("~/.config/shell_gpt/roles", "Custom roles", ["**/*.json"]),
    ], install={"pipx": "shell-gpt"}),

    tool("aichat", "aichat", "Agent CLI", ["%APPDATA%/aichat", "~/.config/aichat"], [
        cfg("%APPDATA%/aichat/config.yaml", "Clients, models, RAG settings"),
        cfg("~/.config/aichat/config.yaml"),
        prompt("%APPDATA%/aichat/roles", include=MD),
        tree("%APPDATA%/aichat/functions", "Function tools"),
    ], install={"choco": "aichat", "docs": "https://github.com/sigoden/aichat"}),

    tool("fabric", "Fabric", "Agent CLI", ["~/.config/fabric"], [
        cfg("~/.config/fabric/.env", "Provider endpoints"),
        prompt("~/.config/fabric/patterns", "Prompt patterns", MD),
    ], install={"docs": "https://github.com/danielmiessler/fabric"}),

    tool("codebuff", "Codebuff", "Agent CLI", ["~/.config/manicode", "~/.codebuff"], [
        cfg("~/.config/manicode/credentials.json"),
        tree("~/.codebuff", include=JSONY + MD, mb=20),
    ], install={"npm": "codebuff"}),

    tool("droid-factory", "Factory Droid", "Agent CLI", ["~/.factory"], [
        cfg("~/.factory/config.json", "Model and provider settings"),
        cfg("~/.factory/mcp.json", "MCP servers"),
        prompt("~/.factory/AGENTS.md"),
        tree("~/.factory/droids", "Custom droids", MD),
    ], mcp=[mcp_src("~/.factory/mcp.json", "mcp_servers", "Factory Droid")],
        install={"docs": "https://docs.factory.ai"}),

    tool("amp-code", "Amp (Sourcegraph)", "Agent CLI", ["~/.config/amp", "%APPDATA%/amp"], [
        cfg("~/.config/amp/settings.json"),
        cfg("%APPDATA%/amp/settings.json"),
        prompt("~/.config/amp/AGENT.md"),
    ], install={"npm": "@sourcegraph/amp"}),
]

# ------------------------------------------------------------------ AI IDEs

AI_IDES = [
    tool("antigravity", "Google Antigravity", "AI IDE", ["~/.antigravity", "%APPDATA%/Antigravity"], [
        prompt("~/.antigravity/rules", "Global rules", ["**/*.md", "**/*.mdc"]),
        cfg("~/.antigravity/argv.json"),
        cfg("%APPDATA%/Antigravity/User/settings.json"),
        cfg("%APPDATA%/Antigravity/User/keybindings.json"),
        tree("%APPDATA%/Antigravity/User/snippets"),
        cfg("%APPDATA%/Antigravity IDE/User/settings.json"),
        cfg("~/.gemini/antigravity/mcp_config.json", "Antigravity MCP servers"),
        tree("~/.gemini/antigravity-cli", "Antigravity CLI config", JSONY + MD),
    ], mcp=[mcp_src("~/.gemini/antigravity/mcp_config.json", "mcp_servers", "Antigravity")],
        extensions_dir="~/.antigravity/extensions",
        install={"url": "https://antigravity.google/download"}),

    tool("cursor", "Cursor", "AI IDE", ["~/.cursor", "%APPDATA%/Cursor"], [
        cfg("~/.cursor/mcp.json", "MCP servers"),
        cfg("~/.cursor/cli-config.json"),
        prompt("~/.cursor/rules", "Global rules", ["**/*.md", "**/*.mdc"]),
        tree("~/.cursor/agents", "Custom agents", ["**/*.md", "**/*.json"]),
        tree("~/.cursor/skills-cursor", "Skills"),
        {"path": "~/.cursor/plugins", "kind": "tree", "note": "Plugin settings",
         "include": ["*.json", "*/*.json"], "exclude": JUNK, "max_total_mb": 10},
        record("~/.cursor/plugins/marketplaces", "Plugin payloads — re-cloned"),
        cfg("%APPDATA%/Cursor/User/settings.json", "Editor and AI settings"),
        cfg("%APPDATA%/Cursor/User/keybindings.json"),
        tree("%APPDATA%/Cursor/User/snippets"),
        record("~/.cursor/extensions", "Extensions — reinstalled by id"),
        record("~/.cursor/chats", "Chat history"),
    ], mcp=[mcp_src("~/.cursor/mcp.json", "mcp_servers", "Cursor")],
        extensions_dir="~/.cursor/extensions",
        install={"winget": "Anysphere.Cursor", "url": "https://cursor.com/download"}),

    tool("kiro", "AWS Kiro", "AI IDE", ["~/.kiro", "%APPDATA%/Kiro"], [
        cfg("~/.kiro/settings/mcp.json", "MCP servers"),
        prompt("~/.kiro/steering", "Steering documents", MD),
        cfg("%APPDATA%/Kiro/User/settings.json"),
        tree("%APPDATA%/Kiro/User/snippets"),
    ], mcp=[mcp_src("~/.kiro/settings/mcp.json", "mcp_servers", "Kiro")],
        extensions_dir="~/.kiro/extensions",
        install={"url": "https://kiro.dev/downloads"}),

    tool("pearai", "PearAI", "AI IDE", ["%APPDATA%/PearAI", "~/.pearai"], [
        cfg("%APPDATA%/PearAI/User/settings.json"),
        tree("~/.pearai", include=JSONY + MD, mb=20),
    ], extensions_dir="~/.pearai/extensions", install={"url": "https://trypear.ai"}),

    tool("trae", "Trae", "AI IDE", ["%APPDATA%/Trae", "~/.trae"], [
        cfg("%APPDATA%/Trae/User/settings.json"),
        cfg("%APPDATA%/Trae/User/mcp.json", "MCP servers"),
        prompt("~/.trae/rules", include=["**/*.md", "**/*.mdc"]),
    ], mcp=[mcp_src("%APPDATA%/Trae/User/mcp.json", "vscode_mcp", "Trae")],
        extensions_dir="~/.trae/extensions", install={"url": "https://trae.ai"}),

    tool("void-editor", "Void", "AI IDE", ["%APPDATA%/Void", "~/.void-editor"], [
        cfg("%APPDATA%/Void/User/settings.json"),
        tree("%APPDATA%/Void/User/snippets"),
    ], extensions_dir="~/.void-editor/extensions", install={"url": "https://voideditor.com"}),

    tool("vscode", "Visual Studio Code", "AI IDE", ["%APPDATA%/Code"], [
        cfg("%APPDATA%/Code/User/settings.json", "Editor plus Copilot and Chat settings"),
        cfg("%APPDATA%/Code/User/mcp.json", "MCP servers"),
        cfg("%APPDATA%/Code/User/chatLanguageModels.json", "Registered chat models"),
        cfg("%APPDATA%/Code/User/keybindings.json"),
        tree("%APPDATA%/Code/User/snippets"),
        prompt("%APPDATA%/Code/User/prompts", "Copilot prompt and instruction files", MD),
        tree("%APPDATA%/Code/User/profiles", "Profiles", ["**/*.json"], mb=20),
        {"path": "%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings",
         "kind": "config", "note": "Cline settings and MCP servers", "include": ["**/*.json"]},
        {"path": "%APPDATA%/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings",
         "kind": "config", "note": "Roo Code settings and MCP servers", "include": ["**/*.json"]},
        {"path": "%APPDATA%/Code/User/globalStorage/kilocode.kilo-code/settings",
         "kind": "config", "note": "Kilo Code settings", "include": ["**/*.json"]},
        {"path": "%APPDATA%/Code/User/globalStorage/continue.continue",
         "kind": "config", "note": "Continue settings", "include": ["*.json", "*.yaml"]},
        record("%APPDATA%/Code/User/globalStorage", "Extension state — rebuilt on reinstall"),
    ], mcp=[
        mcp_src("%APPDATA%/Code/User/mcp.json", "vscode_mcp", "VS Code"),
        mcp_src("%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
                "mcp_servers", "Cline (VS Code)"),
        mcp_src("%APPDATA%/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json",
                "mcp_servers", "Roo Code (VS Code)"),
        mcp_src("%APPDATA%/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json",
                "mcp_servers", "Kilo Code (VS Code)"),
    ], extensions_dir="~/.vscode/extensions", install={"winget": "Microsoft.VisualStudioCode"}),

    tool("vscode-insiders", "VS Code Insiders", "AI IDE", ["%APPDATA%/Code - Insiders"], [
        cfg("%APPDATA%/Code - Insiders/User/settings.json"),
        cfg("%APPDATA%/Code - Insiders/User/mcp.json"),
        cfg("%APPDATA%/Code - Insiders/User/chatLanguageModels.json"),
        prompt("%APPDATA%/Code - Insiders/User/prompts", include=MD),
        tree("%APPDATA%/Code - Insiders/User/snippets"),
    ], mcp=[mcp_src("%APPDATA%/Code - Insiders/User/mcp.json", "vscode_mcp", "VS Code Insiders")],
        extensions_dir="~/.vscode-insiders/extensions",
        install={"winget": "Microsoft.VisualStudioCode.Insiders"}),

    tool("windsurf", "Windsurf", "AI IDE", ["~/.codeium/windsurf", "%APPDATA%/Windsurf"], [
        cfg("~/.codeium/windsurf/mcp_config.json", "MCP servers"),
        prompt("~/.codeium/windsurf/memories", "Cascade memories and global rules", MD),
        prompt("~/.codeium/windsurf/global_rules.md", "Global rules"),
        cfg("~/.codeium/windsurf-next/mcp_config.json"),
        cfg("%APPDATA%/Windsurf/User/settings.json"),
        cfg("%APPDATA%/Windsurf/User/keybindings.json"),
        prompt("%APPDATA%/Windsurf/User/prompts", include=MD),
        cfg("%APPDATA%/Windsurf/User/chatLanguageModels.json"),
        tree("%APPDATA%/Windsurf/User/snippets"),
    ], mcp=[mcp_src("~/.codeium/windsurf/mcp_config.json", "mcp_servers", "Windsurf"),
            mcp_src("~/.codeium/windsurf-next/mcp_config.json", "mcp_servers", "Windsurf Next")],
        extensions_dir="~/.windsurf/extensions",
        install={"winget": "Codeium.Windsurf", "url": "https://windsurf.com/download"}),

    tool("zed", "Zed", "AI IDE", ["%APPDATA%/Zed", "~/.config/zed"], [
        cfg("%APPDATA%/Zed/settings.json", "Assistant and model settings"),
        cfg("%APPDATA%/Zed/keymap.json"),
        cfg("~/.config/zed/settings.json"),
        prompt("%APPDATA%/Zed/prompts", include=MD),
    ], install={"winget": "ZedIndustries.Zed"}),

    tool("jetbrains-ai", "JetBrains AI Assistant", "AI IDE", ["%APPDATA%/JetBrains"], [
        {"path": "%APPDATA%/JetBrains", "kind": "config", "note": "AI Assistant and MCP options",
         "include": ["**/options/*ai*.xml", "**/options/mcp*.xml", "**/options/llm*.xml"],
         "max_total_mb": 20},
    ], install={"docs": "https://www.jetbrains.com/ai/"}),

    tool("junie", "JetBrains Junie", "AI IDE", ["~/.junie"], [
        cfg("~/.junie/mcp", "MCP servers", ),
        prompt("~/.junie/guidelines.md"),
    ], mcp=[mcp_src("~/.junie/mcp/mcp.json", "mcp_servers", "Junie")],
        install={"docs": "https://www.jetbrains.com/junie/"}),

    tool("devin-ide", "Devin", "AI IDE", ["~/.devin", "%APPDATA%/Devin - Next"], [
        cfg("~/.devin/argv.json"),
        cfg("%APPDATA%/Devin - Next/User/settings.json"),
        cfg("%APPDATA%/Devin - Next/User/chatLanguageModels.json"),
    ], extensions_dir="~/.devin/extensions", install={"url": "https://devin.ai"}),
]

# -------------------------------------------------------- IDE AI extensions

EXTENSIONS = [
    tool("continue", "Continue", "AI IDE Extension", ["~/.continue"], [
        cfg("~/.continue/config.json", "Models and context providers"),
        cfg("~/.continue/config.yaml"),
        tree("~/.continue/assistants", include=["**/*.yaml", "**/*.yml", "**/*.json"]),
        prompt("~/.continue/rules", include=MD),
        prompt("~/.continue/prompts", include=["**/*.prompt", "**/*.md"]),
        {"path": "~/.continue/mcpServers", "kind": "config", "include": ["**/*.yaml", "**/*.json"]},
    ], mcp=[mcp_src("~/.continue/config.json", "mcp_servers", "Continue")],
        install={"docs": "https://docs.continue.dev"}),

    tool("tabnine", "Tabnine", "AI IDE Extension", ["%LOCALAPPDATA%/TabNine"], [
        cfg("%LOCALAPPDATA%/TabNine/tabnine_config.json"),
        record("%LOCALAPPDATA%/TabNine", "Local model payloads"),
    ], install={"docs": "https://www.tabnine.com"}),

    tool("supermaven", "Supermaven", "AI IDE Extension", ["%LOCALAPPDATA%/supermaven", "~/.supermaven"], [
        cfg("%LOCALAPPDATA%/supermaven/config.json"),
        cfg("~/.supermaven/config.json"),
    ], install={"docs": "https://supermaven.com"}),

    tool("augment", "Augment Code", "AI IDE Extension", ["~/.augment", "%APPDATA%/Augment"], [
        tree("~/.augment", include=JSONY + MD, mb=20),
        prompt("~/.augment/guidelines.md"),
    ], install={"docs": "https://www.augmentcode.com"}),

    tool("sourcegraph-cody", "Sourcegraph Cody", "AI IDE Extension",
         ["~/.sourcegraph", "%APPDATA%/Code/User/globalStorage/sourcegraph.cody-ai"], [
        cfg("~/.sourcegraph/cody.json"),
        {"path": "%APPDATA%/Code/User/globalStorage/sourcegraph.cody-ai", "kind": "config",
         "include": ["*.json"]},
    ], install={"docs": "https://sourcegraph.com/cody"}),

    tool("codeium-extension", "Codeium", "AI IDE Extension", ["~/.codeium"], [
        {"path": "~/.codeium", "kind": "config", "include": ["*.json", "config.json"]},
    ], install={"docs": "https://codeium.com"}),
]

# ------------------------------------------------------------ Local inference

LOCAL_INFERENCE = [
    tool("ollama", "Ollama", "Local Inference", ["~/.ollama"], [
        cfg("~/.ollama/server.json"),
        secret("~/.ollama/id_ed25519", "Ollama identity key"),
        record("~/.ollama/models/manifests", "Installed models — re-pulled by name"),
        record("~/.ollama/models/blobs", "Model weights"),
    ], install={"winget": "Ollama.Ollama", "url": "https://ollama.com/download/windows"}),

    tool("lmstudio", "LM Studio", "Local Inference", ["~/.lmstudio"], [
        cfg("~/.lmstudio/mcp.json", "MCP servers"),
        {"path": "~/.lmstudio/config-presets", "kind": "config", "note": "Inference presets",
         "include": ["**/*.json"]},
        {"path": "~/.lmstudio/.internal", "kind": "config", "note": "App settings", "include": ["*.json"]},
        record("~/.lmstudio/models", "Model weights — re-download from the Hub"),
        record("~/.lmstudio/conversations"),
    ], mcp=[mcp_src("~/.lmstudio/mcp.json", "mcp_servers", "LM Studio")],
        install={"winget": "ElementLabs.LMStudio", "url": "https://lmstudio.ai/download"}),

    tool("jan", "Jan", "Local Inference", ["~/jan", "%APPDATA%/Jan"], [
        cfg("~/jan/settings/settings.json"),
        tree("~/jan/assistants", "Assistants", ["**/*.json"]),
        tree("~/jan/engines", "Engine settings", ["**/*.json", "**/*.yaml"]),
        record("~/jan/models", "Model weights"),
        record("~/jan/threads", "Conversation history"),
    ], install={"url": "https://jan.ai/download"}),

    tool("gpt4all", "GPT4All", "Local Inference",
         ["%LOCALAPPDATA%/nomic.ai/GPT4All", "~/AppData/Roaming/nomic.ai"], [
        cfg("%LOCALAPPDATA%/nomic.ai/GPT4All/settings.json"),
        record("%LOCALAPPDATA%/nomic.ai/GPT4All", "Model weights"),
    ], install={"url": "https://gpt4all.io"}),

    tool("msty", "Msty", "Local Inference", ["%APPDATA%/Msty", "~/.msty"], [
        {"path": "%APPDATA%/Msty", "kind": "config", "include": ["*.json"]},
        record("~/.msty/models", "Model weights"),
    ], install={"url": "https://msty.app"}),

    tool("anythingllm", "AnythingLLM", "Local Inference", ["%APPDATA%/anythingllm-desktop"], [
        {"path": "%APPDATA%/anythingllm-desktop/storage", "kind": "config",
         "note": "Workspace and provider settings", "include": ["*.json", "**/*.json"],
         "max_total_mb": 20},
        record("%APPDATA%/anythingllm-desktop/storage/models", "Model weights"),
        record("%APPDATA%/anythingllm-desktop/storage/vector-cache", "Vector index"),
    ], install={"url": "https://anythingllm.com/download"}),

    tool("open-webui", "Open WebUI", "Local Inference", ["~/.open-webui", "%APPDATA%/open-webui"], [
        cfg("~/.open-webui/config.json"),
        record("~/.open-webui/webui.db", "Application database"),
    ], install={"docs": "https://docs.openwebui.com"}),

    tool("koboldcpp", "KoboldCpp", "Local Inference", ["~/.koboldcpp", "%APPDATA%/KoboldCpp"], [
        {"path": "~/.koboldcpp", "kind": "config", "include": ["*.kcpps", "*.json"]},
    ], install={"url": "https://github.com/LostRuins/koboldcpp"}),

    tool("sillytavern", "SillyTavern", "Local Inference", ["~/SillyTavern/data", "~/.sillytavern"], [
        tree("~/SillyTavern/data/default-user/settings.json", "UI and API settings"),
        prompt("~/SillyTavern/data/default-user/context", include=["**/*.json"]),
        prompt("~/SillyTavern/data/default-user/instruct", include=["**/*.json"]),
        record("~/SillyTavern/data/default-user/characters", "Character cards"),
    ], install={"docs": "https://docs.sillytavern.app"}),

    tool("text-generation-webui", "text-generation-webui", "Local Inference",
         ["~/text-generation-webui/user_data", "~/text-generation-webui/settings.yaml"], [
        cfg("~/text-generation-webui/settings.yaml"),
        cfg("~/text-generation-webui/user_data/settings.yaml"),
        record("~/text-generation-webui/models", "Model weights"),
    ], install={"docs": "https://github.com/oobabooga/text-generation-webui"}),

    tool("localai", "LocalAI", "Local Inference", ["~/.localai", "%APPDATA%/LocalAI"], [
        tree("~/.localai/models", "Model definition YAMLs", ["**/*.yaml", "**/*.yml"]),
        record("~/.localai/models", "Model weights"),
    ], install={"docs": "https://localai.io"}),

    tool("ramalama", "RamaLama", "Local Inference", ["~/.config/ramalama"], [
        cfg("~/.config/ramalama/ramalama.conf"),
        record("~/.local/share/ramalama", "Model weights"),
    ], install={"pipx": "ramalama"}),
]

# ------------------------------------------------------------- Desktop apps

DESKTOP_APPS = [
    tool("claude-desktop", "Claude Desktop", "Desktop App",
         ["%APPDATA%/Claude", "~/.claude/claude_desktop_config.json"], [
        cfg("%APPDATA%/Claude/claude_desktop_config.json", "MCP servers for the desktop app"),
        cfg("%APPDATA%/Claude/config.json"),
        record("%APPDATA%/Claude/window-state.json"),
    ], mcp=[mcp_src("%APPDATA%/Claude/claude_desktop_config.json", "mcp_servers", "Claude Desktop"),
            mcp_src("~/.claude/claude_desktop_config.json", "mcp_servers", "Claude Desktop")],
        install={"winget": "Anthropic.Claude", "url": "https://claude.ai/download"}),

    tool("chatgpt-desktop", "ChatGPT Desktop", "Desktop App", ["%LOCALAPPDATA%/OpenAI"], [
        {"path": "%LOCALAPPDATA%/OpenAI", "kind": "config", "include": ["**/*.json"],
         "max_total_mb": 10},
        record("%LOCALAPPDATA%/OpenAI", "Cached app payloads"),
    ], install={"url": "https://openai.com/chatgpt/download"}),

    tool("perplexity-desktop", "Perplexity", "Desktop App",
         ["%LOCALAPPDATA%/Perplexity", "%APPDATA%/Perplexity"], [
        {"path": "%APPDATA%/Perplexity", "kind": "config", "include": ["*.json"]},
    ], install={"url": "https://www.perplexity.ai/download"}),

    tool("chatbox", "Chatbox", "Desktop App", ["%APPDATA%/xyz.chatboxapp.app"], [
        {"path": "%APPDATA%/xyz.chatboxapp.app", "kind": "config", "include": ["config.json", "settings*.json"]},
    ], install={"url": "https://chatboxai.app"}),

    tool("cherry-studio", "Cherry Studio", "Desktop App", ["%APPDATA%/CherryStudio"], [
        {"path": "%APPDATA%/CherryStudio/Data", "kind": "config",
         "note": "Providers, assistants, MCP servers", "include": ["**/*.json"], "max_total_mb": 20},
        record("%APPDATA%/CherryStudio/Data/KnowledgeBase", "Vector index"),
    ], mcp=[mcp_src("%APPDATA%/CherryStudio/Data/mcp.json", "mcp_servers", "Cherry Studio")],
        install={"url": "https://cherry-ai.com"}),

    tool("lobe-chat", "LobeChat", "Desktop App", ["%APPDATA%/LobeHub", "%APPDATA%/lobehub"], [
        {"path": "%APPDATA%/LobeHub", "kind": "config", "include": ["**/*.json"], "max_total_mb": 20},
    ], install={"docs": "https://lobehub.com"}),

    tool("librechat", "LibreChat", "Desktop App", ["~/LibreChat/librechat.yaml"], [
        cfg("~/LibreChat/librechat.yaml", "Endpoints, models, MCP servers"),
    ], mcp=[mcp_src("~/LibreChat/librechat.yaml", "yaml_mcp", "LibreChat")],
        install={"docs": "https://www.librechat.ai"}),

    tool("typingmind", "TypingMind", "Desktop App", ["%APPDATA%/TypingMind"], [
        {"path": "%APPDATA%/TypingMind", "kind": "config", "include": ["*.json"]},
    ], install={"url": "https://www.typingmind.com"}),

    tool("wispr-flow", "Wispr Flow", "Desktop App",
         ["%APPDATA%/Wispr Flow", "%LOCALAPPDATA%/WisprFlow"], [
        {"path": "%APPDATA%/Wispr Flow", "kind": "config", "include": ["*.json"]},
        prompt("%APPDATA%/Wispr Flow/dictionary", "Custom vocabulary", ["**/*.json", "**/*.txt"]),
    ], install={"url": "https://wisprflow.ai"}),

    tool("superwhisper", "Superwhisper", "Desktop App", ["~/Documents/superwhisper"], [
        tree("~/Documents/superwhisper/modes", "Custom modes", ["**/*.json"]),
        record("~/Documents/superwhisper/models", "Speech model weights"),
    ], install={"url": "https://superwhisper.com"}),
]

# --------------------------------------------------------- Agent platforms

PLATFORMS = [
    tool("openclaw", "OpenClaw", "Agent Platform", ["~/.openclaw"], [
        cfg("~/.openclaw/openclaw.json", "Gateway, channels, model routing"),
        tree("~/.openclaw/skills", "Skills"),
        tree("~/.openclaw/agents", include=["**/*.md", "**/*.json"]),
    ], install={"docs": "https://docs.openclaw.ai"}),

    tool("n8n", "n8n", "Agent Platform", ["~/.n8n"], [
        cfg("~/.n8n/config", "Instance settings"),
        record("~/.n8n/database.sqlite", "Workflow database — export workflows instead"),
        record("~/.n8n/nodes", "Community nodes — reinstalled by name"),
    ], install={"npm": "n8n", "docs": "https://docs.n8n.io"}),

    tool("flowise", "Flowise", "Agent Platform", ["~/.flowise"], [
        cfg("~/.flowise/.env"),
        record("~/.flowise/database.sqlite", "Chatflow database — export chatflows instead"),
    ], install={"npm": "flowise"}),

    tool("langflow", "Langflow", "Agent Platform", ["~/.langflow"], [
        cfg("~/.langflow/settings.yaml"),
        record("~/.langflow/langflow.db", "Flow database"),
    ], install={"pipx": "langflow"}),

    tool("dify", "Dify", "Agent Platform", ["~/.dify"], [
        {"path": "~/.dify", "kind": "config", "include": ["*.yaml", "*.env", "*.json"]},
    ], install={"docs": "https://docs.dify.ai"}),

    tool("crewai", "CrewAI", "Agent Platform", ["~/.crewai", "~/.config/crewai"], [
        {"path": "~/.crewai", "kind": "config", "include": ["*.json", "*.yaml"]},
        {"path": "~/.config/crewai", "kind": "config", "include": ["*.json", "*.yaml"]},
    ], install={"pipx": "crewai"}),

    tool("letta", "Letta (MemGPT)", "Agent Platform", ["~/.letta", "~/.memgpt"], [
        cfg("~/.letta/config"),
        cfg("~/.memgpt/config"),
        record("~/.letta/sqlite.db", "Agent memory database"),
    ], install={"pipx": "letta"}),

    tool("mem0", "mem0", "Agent Platform", ["~/.mem0"], [
        cfg("~/.mem0/config.json", "Memory layer configuration"),
    ], install={"pipx": "mem0ai"}),

    tool("claude-mem", "claude-mem", "Agent Platform", ["~/.claude-mem"], [
        cfg("~/.claude-mem/settings.json"),
        record("~/.claude-mem/claude-mem.db", "Memory database — rebuilt from transcripts"),
        record("~/.claude-mem/chroma", "Vector index"),
    ], install={"npm": "claude-mem"}),

    tool("agent-dirs", "Portable agent directories", "Cross-tool Standard",
         ["~/.agent", "~/.agents", "~/AGENTS.md"], [
        prompt("~/.agent/rules", include=MD),
        tree("~/.agent/skills", "Skills"),
        tree("~/.agents/skills", "Skills"),
        cfg("~/.agents/.skill-lock.json"),
        prompt("~/AGENTS.md", "Cross-tool master prompt"),
    ], install={"docs": "https://agents.md"}),
]

# ------------------------------------------------------------------ MCP

MCP_TOOLS = [
    tool("custom-mcp-workspace", "Custom MCP server workspace", "MCP Server",
         ["~/mcp-servers", "~/mcp", "~/.mcp-servers", "~/Documents/mcp-servers"], [
        {"path": "~/mcp-servers", "kind": "tree",
         "note": "Every custom server in the workspace, including ones not currently wired up",
         "include": ["**/*.js", "**/*.mjs", "**/*.cjs", "**/*.ts", "**/*.py", "**/*.json",
                     "**/*.toml", "**/*.md", "**/*.yaml", "**/*.yml", "**/*.ps1", "**/*.sh",
                     "**/*.txt", "**/*.env.example", "**/*.lock"],
         "exclude": JUNK + ["**/*-venv/**", "**/*.venv/**"], "max_total_mb": 80},
        {"path": "~/.mcp-servers", "kind": "tree", "exclude": JUNK, "max_total_mb": 80},
        {"path": "~/mcp", "kind": "tree", "exclude": JUNK, "max_total_mb": 80},
    ], notes="Source of hand-written MCP servers. Dependencies are rebuilt, never copied."),

    tool("serena", "Serena", "MCP Server", ["~/.serena", "~/.claude/.serena"], [
        cfg("~/.serena/serena_config.yml"),
        tree("~/.serena/contexts", include=["**/*.yml", "**/*.yaml"]),
        tree("~/.serena/modes", include=["**/*.yml", "**/*.yaml"]),
        tree("~/.claude/.serena", "Project memories", ["**/*.md", "**/*.yml"], mb=20),
    ], install={"uv": "serena-agent", "docs": "https://github.com/oraios/serena"}),

    tool("mcpm", "mcpm", "MCP Server", ["~/.config/mcpm"], [
        cfg("~/.config/mcpm/config.json", "Managed MCP server registry"),
        cfg("~/.config/mcpm/profiles.json"),
    ], mcp=[mcp_src("~/.config/mcpm/config.json", "mcp_servers", "mcpm")],
        install={"pipx": "mcpm"}),

    tool("fastmcp", "FastMCP", "MCP Server", ["~/.fastmcp", "%LOCALAPPDATA%/fastmcp"], [
        {"path": "~/.fastmcp", "kind": "config", "include": ["*.json", "*.yaml"]},
    ], install={"pipx": "fastmcp"}),

    tool("mcp-hub", "MCP Hub", "MCP Server", ["~/.mcp-hub", "~/.config/mcphub"], [
        cfg("~/.mcp-hub/config.json"),
        cfg("~/.config/mcphub/servers.json"),
    ], mcp=[mcp_src("~/.mcp-hub/config.json", "mcp_servers", "MCP Hub")]),
]

# ------------------------------------------------------------------ LLMOps

LLMOPS = [
    tool("langsmith", "LangSmith / LangChain", "LLM Ops", ["~/.langchain", "~/.langsmith"], [
        {"path": "~/.langchain", "kind": "config", "include": ["*.json", "*.yaml"]},
        secret("~/.langsmith/credentials"),
    ], install={"docs": "https://docs.smith.langchain.com"}),

    tool("langfuse", "Langfuse", "LLM Ops", ["~/.langfuse"], [
        {"path": "~/.langfuse", "kind": "config", "include": ["*.json", "*.yaml"]},
    ], install={"docs": "https://langfuse.com/docs"}),

    tool("wandb", "Weights & Biases", "LLM Ops", ["~/.config/wandb", "~/.netrc"], [
        cfg("~/.config/wandb/settings", "Default entity and project"),
        secret("~/.netrc", "Contains the W&B API key"),
    ], install={"pipx": "wandb"}),

    tool("mlflow", "MLflow", "LLM Ops", ["~/.mlflow"], [
        cfg("~/.mlflow/credentials"),
    ], install={"pipx": "mlflow"}),

    tool("promptfoo", "promptfoo", "LLM Ops", ["~/.promptfoo"], [
        cfg("~/.promptfoo/promptfoo.yaml"),
        prompt("~/.promptfoo/prompts", include=PROMPTY),
    ], install={"npm": "promptfoo"}),

    tool("huggingface-cli", "Hugging Face CLI", "LLM Ops",
         ["~/.cache/huggingface", "~/.huggingface", "~/.hf-cli"], [
        cfg("~/.cache/huggingface/accelerate/default_config.yaml"),
        secret("~/.cache/huggingface/token", "Hugging Face access token"),
        secret("~/.cache/huggingface/stored_tokens"),
        tree("~/.hf-cli", include=JSONY),
        record("~/.cache/huggingface/hub", "Downloaded model weights"),
    ], install={"pipx": "huggingface_hub[cli]"}),
]

FILES = {
    "agent-clis.json": AGENT_CLIS,
    "ai-ides.json": AI_IDES,
    "ide-extensions.json": EXTENSIONS,
    "local-inference.json": LOCAL_INFERENCE,
    "desktop-apps.json": DESKTOP_APPS,
    "agent-platforms.json": PLATFORMS,
    "mcp.json": MCP_TOOLS,
    "llmops.json": LLMOPS,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    seen: set[str] = set()
    for filename, tools in FILES.items():
        for entry in tools:
            if entry["id"] in seen:
                raise SystemExit(f"duplicate tool id: {entry['id']}")
            seen.add(entry["id"])
        payload = {"catalog_version": 1, "tools": tools}
        (OUT / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"  {filename:26} {len(tools):3} tools")
        total += len(tools)
    print(f"\n{total} tools written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
