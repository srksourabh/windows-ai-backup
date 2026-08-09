"""Declarative catalog of AI tools, their settings, and how to reinstall them.

Adding support for a new tool means appending one :class:`Target` here — no
changes to the scanner, collectors, or restore engine are required.

Capture policy
--------------
* Hand-authored content (prompts, rules, skills, agents, memories) is copied.
* Anything re-downloadable (plugin caches, model weights, extension payloads,
  node_modules) is *recorded* by name/source so restore can fetch it fresh.
* Credentials are never written in the clear — they go to the encrypted vault.
"""
from __future__ import annotations

from .model import Install, Item, McpSource, Target

# Directories that are always worthless in a settings backup.
JUNK = (
    "**/node_modules/**",
    "**/.git/**",
    "**/__pycache__/**",
    "**/*.log",
    "**/*.tmp",
    "**/*.lock",
    "**/Cache/**",
    "**/cache/**",
    "**/logs/**",
)

CLAUDE_CODE = Target(
    id="claude-code",
    name="Claude Code (CLI)",
    category="Agent CLI",
    detect=("~/.claude", "~/.claude.json"),
    install=Install(
        npm="@anthropic-ai/claude-code",
        docs="https://docs.claude.com/en/docs/claude-code",
        note="Native installer: irm https://claude.ai/install.ps1 | iex",
    ),
    items=(
        Item("~/.claude.json", "config", "Global config: MCP servers, account, per-project settings"),
        Item("~/.claude/settings.json", "config", "Permissions, plugins, statusline, effort level"),
        Item("~/.claude/settings.local.json", "config", "Machine-local overrides"),
        Item("~/.claude/CLAUDE.md", "prompt", "Global master prompt"),
        Item("~/CLAUDE.md", "prompt", "Home-scope master prompt"),
        Item("~/.claude/rules", "prompt", "Rule set loaded into every session", include=("**/*.md",)),
        Item("~/.claude/agents", "tree", "Custom subagent definitions", include=("**/*.md",)),
        Item("~/.claude/commands", "tree", "Custom slash commands", include=("**/*.md",)),
        Item("~/.claude/skills", "tree", "Custom + installed skills", exclude=JUNK, max_total_mb=200),
        Item("~/.claude/local-plugins", "tree", "Locally authored plugins", exclude=JUNK),
        Item("~/.claude/scripts", "tree", "Helper scripts referenced by hooks/statusline"),
        Item("~/.claude/statusline-command.js", "config", "Status line implementation"),
        Item("~/.claude/statusline-command.ps1", "config"),
        Item("~/.claude/statusline-command.sh", "config"),
        Item("~/.claude/keybindings.json", "config"),
        Item("~/.claude/mcp_config.json", "config", "Standalone MCP config"),
        Item("~/.claude/claude_desktop_config.json", "config", "Desktop MCP config staged by CLI"),
        Item("~/.claude/plugins/installed_plugins.json", "config", "Enabled plugins (restored by name)"),
        Item("~/.claude/plugins/known_marketplaces.json", "config", "Plugin marketplace sources"),
        Item("~/.claude/plugins/config.json", "config"),
        Item("~/.claude/skills-lock.json", "config", "Pinned skill versions"),
        Item("~/.claude/projects", "prompt", "Per-project auto-memory", include=("**/memory/**/*.md",), max_total_mb=40),
        Item("~/.claude/.credentials.json", "secret", "OAuth tokens / API key"),
        Item("~/.claude/plugins/cache", "record", "Plugin payloads — re-cloned from marketplaces"),
        Item("~/.claude/projects", "record", "Session transcripts — not needed for a fresh setup"),
    ),
    mcp_sources=(
        McpSource("~/.claude.json", "claude_json", "Claude Code"),
        McpSource("~/.claude/mcp_config.json", "mcp_servers", "Claude Code"),
    ),
)

CLAUDE_DESKTOP = Target(
    id="claude-desktop",
    name="Claude Desktop",
    category="Desktop App",
    detect=("%APPDATA%/Claude", "~/.claude/claude_desktop_config.json"),
    install=Install(winget="Anthropic.Claude", url="https://claude.ai/download"),
    items=(
        Item("%APPDATA%/Claude/claude_desktop_config.json", "config", "MCP servers for the desktop app"),
        Item("%APPDATA%/Claude/config.json", "config"),
        Item("%APPDATA%/Claude/window-state.json", "record"),
    ),
    mcp_sources=(
        McpSource("%APPDATA%/Claude/claude_desktop_config.json", "mcp_servers", "Claude Desktop"),
        McpSource("~/.claude/claude_desktop_config.json", "mcp_servers", "Claude Desktop"),
    ),
)

CODEX = Target(
    id="codex",
    name="OpenAI Codex CLI",
    category="Agent CLI",
    detect=("~/.codex",),
    install=Install(npm="@openai/codex", docs="https://developers.openai.com/codex/cli"),
    items=(
        Item("~/.codex/config.toml", "config", "Models, providers, sandbox policy, MCP servers"),
        Item("~/.codex/AGENTS.md", "prompt", "Global master prompt"),
        Item("~/.codex/prompts", "prompt", "Saved prompts", include=("**/*.md",)),
        Item("~/.codex/skills", "tree", "Skills", exclude=JUNK),
        Item("~/.codex/auth.json", "secret", "API key / ChatGPT session"),
        Item("~/.codex/.credentials.json", "secret"),
        Item("~/.codex/sessions", "record", "Session transcripts"),
    ),
    mcp_sources=(McpSource("~/.codex/config.toml", "toml_mcp", "Codex CLI"),),
)

GEMINI_CLI = Target(
    id="gemini-cli",
    name="Google Gemini CLI",
    category="Agent CLI",
    detect=("~/.gemini",),
    install=Install(npm="@google/gemini-cli", docs="https://github.com/google-gemini/gemini-cli"),
    items=(
        Item("~/.gemini/settings.json", "config", "MCP servers, hooks, IDE + security settings"),
        Item("~/.gemini/GEMINI.md", "prompt", "Global master prompt"),
        Item("~/.gemini/commands", "tree", "Custom commands", include=("**/*.toml", "**/*.md")),
        Item("~/.gemini/skills", "tree", "Skills", exclude=JUNK),
        Item("~/.gemini/trustedFolders.json", "config"),
        Item("~/.gemini/google_accounts.json", "config", "Signed-in Google account identity"),
        Item("~/.gemini/installation_id", "config", "Install identity"),
        Item("~/.gemini/oauth_creds.json", "secret", "Google OAuth credentials"),
    ),
    mcp_sources=(McpSource("~/.gemini/settings.json", "mcp_servers", "Gemini CLI"),),
)

COPILOT_CLI = Target(
    id="copilot-cli",
    name="GitHub Copilot CLI",
    category="Agent CLI",
    detect=("~/.copilot",),
    install=Install(npm="@github/copilot", docs="https://docs.github.com/copilot/how-tos/use-copilot-agents/use-copilot-cli"),
    items=(
        Item("~/.copilot/config.json", "config", "Model + client settings"),
        Item("~/.copilot/mcp-config.json", "config", "MCP servers"),
        Item("~/.copilot/ide", "record"),
    ),
    mcp_sources=(McpSource("~/.copilot/mcp-config.json", "mcp_servers", "Copilot CLI"),),
)

CURSOR = Target(
    id="cursor",
    name="Cursor",
    category="AI IDE",
    detect=("~/.cursor", "%APPDATA%/Cursor"),
    install=Install(winget="Anysphere.Cursor", url="https://cursor.com/download"),
    extensions_dir="~/.cursor/extensions",
    items=(
        Item("~/.cursor/mcp.json", "config", "MCP servers"),
        Item("~/.cursor/cli-config.json", "config"),
        Item("~/.cursor/rules", "prompt", "Global rules", include=("**/*.md", "**/*.mdc")),
        Item("~/.cursor/agents", "tree", "Custom agents", include=("**/*.md", "**/*.json")),
        Item("~/.cursor/skills-cursor", "tree", "Skills", exclude=JUNK),
        Item("~/.cursor/plugins", "tree", "Plugin settings",
             include=("*.json", "*/*.json"), exclude=JUNK, max_total_mb=10),
        Item("~/.cursor/plugins/marketplaces", "record", "Plugin payloads — re-cloned from marketplaces"),
        Item("%APPDATA%/Cursor/User/settings.json", "config", "Editor + AI settings"),
        Item("%APPDATA%/Cursor/User/keybindings.json", "config"),
        Item("%APPDATA%/Cursor/User/snippets", "tree"),
        Item("~/.cursor/extensions", "record", "Extensions — reinstalled by id"),
        Item("~/.cursor/chats", "record", "Chat history"),
    ),
    mcp_sources=(McpSource("~/.cursor/mcp.json", "mcp_servers", "Cursor"),),
)

VSCODE = Target(
    id="vscode",
    name="Visual Studio Code",
    category="AI IDE",
    detect=("%APPDATA%/Code",),
    install=Install(winget="Microsoft.VisualStudioCode"),
    extensions_dir="~/.vscode/extensions",
    items=(
        Item("%APPDATA%/Code/User/settings.json", "config", "Editor + Copilot/Chat settings"),
        Item("%APPDATA%/Code/User/mcp.json", "config", "MCP servers"),
        Item("%APPDATA%/Code/User/chatLanguageModels.json", "config", "Registered chat models"),
        Item("%APPDATA%/Code/User/keybindings.json", "config"),
        Item("%APPDATA%/Code/User/snippets", "tree"),
        Item("%APPDATA%/Code/User/prompts", "prompt", "Copilot prompt + instruction files", include=("**/*.md",)),
        Item("%APPDATA%/Code/User/profiles", "tree", "Profiles", include=("**/*.json",), max_total_mb=20),
        Item(
            "%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings",
            "config",
            "Cline settings + MCP servers",
            include=("**/*.json",),
        ),
        Item(
            "%APPDATA%/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings",
            "config",
            "Roo Code settings + MCP servers",
            include=("**/*.json",),
        ),
        Item("%APPDATA%/Code/User/globalStorage", "record", "Extension state — rebuilt on reinstall"),
    ),
    mcp_sources=(
        McpSource("%APPDATA%/Code/User/mcp.json", "vscode_mcp", "VS Code"),
        McpSource(
            "%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            "mcp_servers",
            "Cline (VS Code)",
        ),
        McpSource(
            "%APPDATA%/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json",
            "mcp_servers",
            "Roo Code (VS Code)",
        ),
    ),
)

VSCODE_INSIDERS = Target(
    id="vscode-insiders",
    name="VS Code Insiders",
    category="AI IDE",
    detect=("%APPDATA%/Code - Insiders",),
    install=Install(winget="Microsoft.VisualStudioCode.Insiders"),
    extensions_dir="~/.vscode-insiders/extensions",
    items=(
        Item("%APPDATA%/Code - Insiders/User/settings.json", "config"),
        Item("%APPDATA%/Code - Insiders/User/mcp.json", "config"),
        Item("%APPDATA%/Code - Insiders/User/chatLanguageModels.json", "config"),
        Item("%APPDATA%/Code - Insiders/User/prompts", "prompt", include=("**/*.md",)),
        Item("%APPDATA%/Code - Insiders/User/snippets", "tree"),
    ),
    mcp_sources=(McpSource("%APPDATA%/Code - Insiders/User/mcp.json", "vscode_mcp", "VS Code Insiders"),),
)

WINDSURF = Target(
    id="windsurf",
    name="Windsurf (Codeium)",
    category="AI IDE",
    detect=("~/.codeium/windsurf", "%APPDATA%/Windsurf"),
    install=Install(winget="Codeium.Windsurf", url="https://windsurf.com/download"),
    extensions_dir="~/.windsurf/extensions",
    items=(
        Item("~/.codeium/windsurf/mcp_config.json", "config", "MCP servers"),
        Item("~/.codeium/windsurf/memories", "prompt", "Cascade memories + global rules", include=("**/*.md",)),
        Item("~/.codeium/windsurf/global_rules.md", "prompt", "Global rules"),
        Item("~/.codeium/windsurf-next/mcp_config.json", "config"),
        Item("%APPDATA%/Windsurf/User/settings.json", "config"),
        Item("%APPDATA%/Windsurf/User/keybindings.json", "config"),
        Item("%APPDATA%/Windsurf/User/prompts", "prompt", include=("**/*.md",)),
        Item("%APPDATA%/Windsurf/User/chatLanguageModels.json", "config"),
        Item("%APPDATA%/Windsurf/User/snippets", "tree"),
    ),
    mcp_sources=(
        McpSource("~/.codeium/windsurf/mcp_config.json", "mcp_servers", "Windsurf"),
        McpSource("~/.codeium/windsurf-next/mcp_config.json", "mcp_servers", "Windsurf Next"),
    ),
)

ANTIGRAVITY = Target(
    id="antigravity",
    name="Google Antigravity",
    category="AI IDE",
    detect=("~/.antigravity", "%APPDATA%/Antigravity"),
    install=Install(url="https://antigravity.google/download"),
    extensions_dir="~/.antigravity/extensions",
    items=(
        Item("~/.antigravity/rules", "prompt", "Global rules", include=("**/*.md", "**/*.mdc")),
        Item("~/.antigravity/argv.json", "config"),
        Item("%APPDATA%/Antigravity/User/settings.json", "config"),
        Item("%APPDATA%/Antigravity/User/keybindings.json", "config"),
        Item("%APPDATA%/Antigravity/User/snippets", "tree"),
        Item("%APPDATA%/Antigravity IDE/User/settings.json", "config"),
        Item("~/.gemini/antigravity/mcp_config.json", "config", "Antigravity MCP servers"),
        Item("~/.gemini/antigravity-cli", "tree", "Antigravity CLI config", include=("**/*.json", "**/*.md")),
    ),
    mcp_sources=(McpSource("~/.gemini/antigravity/mcp_config.json", "mcp_servers", "Antigravity"),),
)

CLINE_CLI = Target(
    id="cline",
    name="Cline CLI",
    category="Agent CLI",
    detect=("~/.cline",),
    install=Install(npm="cline", docs="https://docs.cline.bot"),
    items=(
        Item("~/.cline/data", "tree", "Settings, rules, MCP config", include=("**/*.json", "**/*.md"), max_total_mb=40),
    ),
    mcp_sources=(McpSource("~/.cline/data/mcp_settings.json", "mcp_servers", "Cline CLI"),),
)

CONTINUE = Target(
    id="continue",
    name="Continue",
    category="AI IDE Extension",
    detect=("~/.continue",),
    install=Install(docs="https://docs.continue.dev"),
    items=(
        Item("~/.continue/config.json", "config", "Models + context providers"),
        Item("~/.continue/config.yaml", "config"),
        Item("~/.continue/assistants", "tree", include=("**/*.yaml", "**/*.yml", "**/*.json")),
        Item("~/.continue/rules", "prompt", include=("**/*.md",)),
        Item("~/.continue/prompts", "prompt", include=("**/*.prompt", "**/*.md")),
        Item("~/.continue/mcpServers", "config", include=("**/*.yaml", "**/*.json")),
    ),
    mcp_sources=(McpSource("~/.continue/config.json", "mcp_servers", "Continue"),),
)

AIDER = Target(
    id="aider",
    name="Aider",
    category="Agent CLI",
    detect=("~/.aider.conf.yml", "~/.aider.model.settings.yml"),
    install=Install(pipx="aider-chat", uv="aider-chat", docs="https://aider.chat/docs"),
    items=(
        Item("~/.aider.conf.yml", "config", "Default model, flags"),
        Item("~/.aider.model.settings.yml", "config", "Per-model settings"),
        Item("~/.aider.model.metadata.json", "config"),
    ),
)

OPENCODE = Target(
    id="opencode",
    name="OpenCode",
    category="Agent CLI",
    detect=("~/.config/opencode", "%APPDATA%/ai.opencode.desktop"),
    install=Install(npm="opencode-ai", docs="https://opencode.ai/docs"),
    items=(
        Item("~/.config/opencode", "tree", "Config, agents, commands, MCP", include=("**/*.json", "**/*.md", "**/*.toml"), max_total_mb=40),
        Item("~/.local/share/opencode/auth.json", "secret", "Provider credentials"),
    ),
    mcp_sources=(McpSource("~/.config/opencode/opencode.json", "mcp_servers", "OpenCode"),),
)

GOOSE = Target(
    id="goose",
    name="Block Goose",
    category="Agent CLI",
    detect=("~/.config/goose", "%APPDATA%/Goose"),
    install=Install(docs="https://block.github.io/goose"),
    items=(
        Item("~/.config/goose/config.yaml", "config", "Providers + extensions (MCP)"),
        Item("~/.config/goose/profiles.yaml", "config"),
        Item("~/.config/goose/.goosehints", "prompt"),
        Item("%APPDATA%/Goose/config.yaml", "config"),
    ),
    mcp_sources=(McpSource("~/.config/goose/config.yaml", "yaml_mcp", "Goose"),),
)

LM_STUDIO = Target(
    id="lmstudio",
    name="LM Studio",
    category="Local Inference",
    detect=("~/.lmstudio",),
    install=Install(winget="ElementLabs.LMStudio", url="https://lmstudio.ai/download"),
    items=(
        Item("~/.lmstudio/mcp.json", "config", "MCP servers"),
        Item("~/.lmstudio/config-presets", "config", "Inference presets", include=("**/*.json", "**/*.preset.json")),
        Item("~/.lmstudio/.internal", "config", "App settings", include=("*.json",)),
        Item("~/.lmstudio/models", "record", "Model weights — re-download from the Hub"),
        Item("~/.lmstudio/conversations", "record"),
    ),
    mcp_sources=(McpSource("~/.lmstudio/mcp.json", "mcp_servers", "LM Studio"),),
)

OLLAMA = Target(
    id="ollama",
    name="Ollama",
    category="Local Inference",
    detect=("~/.ollama",),
    install=Install(winget="Ollama.Ollama", url="https://ollama.com/download/windows"),
    items=(
        Item("~/.ollama/server.json", "config"),
        Item("~/.ollama/id_ed25519", "secret", "Ollama identity key"),
        Item("~/.ollama/models/manifests", "record", "Installed models — re-pulled by name"),
        Item("~/.ollama/models/blobs", "record", "Model weights"),
    ),
)

AMAZON_Q = Target(
    id="amazon-q",
    name="Amazon Q Developer",
    category="Agent CLI",
    detect=("~/.aws/amazonq",),
    install=Install(docs="https://docs.aws.amazon.com/amazonq/"),
    items=(
        Item("~/.aws/amazonq/mcp.json", "config", "MCP servers"),
        Item("~/.aws/amazonq/global_context.json", "config"),
        Item("~/.aws/amazonq/profiles", "tree", include=("**/*.json", "**/*.md")),
        Item("~/.aws/amazonq/cli-agents", "tree", include=("**/*.json",)),
        Item("~/.aws/aws-api-mcp", "config", include=("**/*.json",)),
    ),
    mcp_sources=(McpSource("~/.aws/amazonq/mcp.json", "mcp_servers", "Amazon Q"),),
)

JUNIE = Target(
    id="junie",
    name="JetBrains Junie",
    category="AI IDE Extension",
    detect=("~/.junie",),
    install=Install(docs="https://www.jetbrains.com/junie/"),
    items=(
        Item("~/.junie/mcp", "config", "MCP servers", include=("**/*.json",)),
        Item("~/.junie/guidelines.md", "prompt"),
    ),
    mcp_sources=(McpSource("~/.junie/mcp/mcp.json", "mcp_servers", "Junie"),),
)

ZED = Target(
    id="zed",
    name="Zed",
    category="AI IDE",
    detect=("%APPDATA%/Zed", "~/.config/zed"),
    install=Install(winget="ZedIndustries.Zed"),
    items=(
        Item("%APPDATA%/Zed/settings.json", "config", "Assistant + model settings"),
        Item("%APPDATA%/Zed/keymap.json", "config"),
        Item("~/.config/zed/settings.json", "config"),
    ),
)

SERENA = Target(
    id="serena",
    name="Serena (semantic code MCP)",
    category="MCP Server",
    detect=("~/.serena", "~/.claude/.serena"),
    install=Install(uv="serena-agent", docs="https://github.com/oraios/serena"),
    items=(
        Item("~/.serena/serena_config.yml", "config"),
        Item("~/.serena/contexts", "tree", include=("**/*.yml", "**/*.yaml")),
        Item("~/.serena/modes", "tree", include=("**/*.yml", "**/*.yaml")),
        Item("~/.claude/.serena", "tree", "Project memories", include=("**/*.md", "**/*.yml"), max_total_mb=20),
    ),
)

OPENCLAW = Target(
    id="openclaw",
    name="OpenClaw",
    category="Agent Platform",
    detect=("~/.openclaw",),
    install=Install(docs="https://docs.openclaw.ai"),
    items=(
        Item("~/.openclaw/openclaw.json", "config", "Gateway, channels, model routing"),
        Item("~/.openclaw/skills", "tree", "Skills", exclude=JUNK, max_total_mb=60),
        Item("~/.openclaw/agents", "tree", include=("**/*.md", "**/*.json")),
    ),
)

CLAUDE_MEM = Target(
    id="claude-mem",
    name="claude-mem",
    category="Agent Add-on",
    detect=("~/.claude-mem",),
    install=Install(npm="claude-mem"),
    items=(
        Item("~/.claude-mem/settings.json", "config"),
        Item("~/.claude-mem/claude-mem.db", "record", "Memory database — large, rebuilt from transcripts"),
        Item("~/.claude-mem/chroma", "record", "Vector index"),
    ),
)

GENERIC_AGENT_DIRS = Target(
    id="agent-dirs",
    name="Portable agent directories (.agent / .agents / AGENTS.md)",
    category="Cross-tool Standard",
    detect=("~/.agent", "~/.agents", "~/AGENTS.md"),
    install=Install(docs="https://agents.md"),
    items=(
        Item("~/.agent/rules", "prompt", include=("**/*.md",)),
        Item("~/.agent/skills", "tree", exclude=JUNK, max_total_mb=60),
        Item("~/.agents/skills", "tree", exclude=JUNK, max_total_mb=60),
        Item("~/.agents/.skill-lock.json", "config"),
        Item("~/AGENTS.md", "prompt", "Cross-tool master prompt"),
    ),
)

MISC_TOOLS = Target(
    id="misc-ai-tools",
    name="Other AI tools",
    category="Assorted",
    detect=("~/.mem0", "~/.n8n-mcp", "~/.kimi-code", "~/.devin", "~/.gsd", "~/.omniroute", "~/.cagent", "~/.qodo", "~/.kilocode", "~/.clawhub", "~/.council-of-mine", "~/.aitk", "~/.hf-cli"),
    items=(
        Item("~/.mem0/config.json", "config", "mem0 memory layer"),
        Item("~/.n8n-mcp/telemetry.json", "record"),
        Item("~/.kimi-code/migrations-effort.json", "config"),
        Item("~/.kimi-code/credentials", "secret"),
        Item("~/.devin/argv.json", "config"),
        Item("~/.gsd/agent", "tree", "get-shit-done agent config", include=("**/*.json", "**/*.md")),
        Item("~/.omniroute/.env", "secret", "OmniRoute provider keys"),
        Item("~/.omniroute/server", "tree", "Router config", include=("**/*.json", "**/*.yaml"), max_total_mb=20),
        Item("~/.cagent/models_dev.json", "config"),
        Item("~/.qodo", "tree", include=("**/*.json", "**/*.yaml", "**/*.md"), max_total_mb=20),
        Item("~/.kilocode", "tree", include=("**/*.json", "**/*.md"), max_total_mb=20),
        Item("~/.clawhub/lock.json", "config"),
        Item("~/.aitk", "tree", "AI Toolkit for VS Code", include=("**/*.json",), max_total_mb=20),
        Item("~/.hf-cli", "tree", "Hugging Face CLI", include=("**/*.json", "**/*.yaml")),
        Item("~/.cache/huggingface/token", "secret", "Hugging Face token"),
        Item("~/.copilot/config.json", "config"),
    ),
)

CUSTOM_MCP_WORKSPACE = Target(
    id="custom-mcp-workspace",
    name="Custom MCP server workspace",
    category="MCP Server",
    detect=("~/mcp-servers", "~/mcp", "~/.mcp-servers", "~/Documents/mcp-servers"),
    notes="Source of hand-written MCP servers. Dependencies are rebuilt, never copied.",
    items=(
        Item(
            "~/mcp-servers",
            "tree",
            "Every custom server in the workspace, including ones not currently wired up",
            include=(
                "**/*.js", "**/*.mjs", "**/*.cjs", "**/*.ts", "**/*.py", "**/*.json",
                "**/*.toml", "**/*.md", "**/*.yaml", "**/*.yml", "**/*.ps1", "**/*.sh",
                "**/*.txt", "**/*.env.example", "**/*.lock",
            ),
            exclude=JUNK + ("**/*-venv/**", "**/*.venv/**"),
            max_total_mb=80,
        ),
        Item("~/.mcp-servers", "tree", include=("**/*",), exclude=JUNK, max_total_mb=80),
        Item("~/mcp", "tree", include=("**/*",), exclude=JUNK, max_total_mb=80),
    ),
)

TARGETS: tuple[Target, ...] = (
    CUSTOM_MCP_WORKSPACE,
    CLAUDE_CODE,
    CLAUDE_DESKTOP,
    CODEX,
    GEMINI_CLI,
    COPILOT_CLI,
    CURSOR,
    VSCODE,
    VSCODE_INSIDERS,
    WINDSURF,
    ANTIGRAVITY,
    CLINE_CLI,
    CONTINUE,
    AIDER,
    OPENCODE,
    GOOSE,
    LM_STUDIO,
    OLLAMA,
    AMAZON_Q,
    JUNIE,
    ZED,
    SERENA,
    OPENCLAW,
    CLAUDE_MEM,
    GENERIC_AGENT_DIRS,
    MISC_TOOLS,
)


def by_id(target_id: str) -> Target | None:
    return next((t for t in TARGETS if t.id == target_id), None)
