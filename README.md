<div align="center">

# Windows AI Backup

**Reinstall Windows without losing your AI setup.**

One executable that finds every AI tool on a Windows PC, records what it is and where it lives,
backs up the parts that cannot be re-downloaded, and generates a script that rebuilds
the whole setup on a fresh machine.

[![Download](https://img.shields.io/badge/Download-WindowsAIBackup.exe-2ea44f?style=for-the-badge&logo=windows)](https://github.com/srksourabh/windows-ai-backup/releases/latest/download/WindowsAIBackup.exe)
[![Premium](https://img.shields.io/badge/Premium-%241%20once-8250df?style=for-the-badge)](PRICING.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Catalog](https://img.shields.io/badge/catalog-87%2B%20AI%20tools-0969da?style=for-the-badge)](waib/data/catalog.d)
[![Tests](https://img.shields.io/badge/tests-121%20passing-brightgreen?style=for-the-badge)](tests)

*Built by [Sourabh Bhaumik](https://github.com/srksourabh)*

</div>

---

## The problem

Your AI setup is scattered across two dozen directories. Master prompts in `~/.claude/CLAUDE.md`,
MCP servers in six different config dialects, skills you wrote by hand, agent definitions,
rules, memories, API keys, model choices, IDE extensions. A Windows reinstall erases all of it.

Copying `C:\Users\you` wholesale doesn't work either — it's gigabytes of plugin caches,
`node_modules`, session transcripts and model weights that all re-download in minutes anyway.

## The answer

Know the difference between **what exists nowhere else** and **what the internet still has**.

```mermaid
flowchart LR
    A["🔍 Scan<br/>87 known AI tools<br/>+ heuristic discovery"] --> B{Can this be<br/>re-downloaded?}
    B -->|No| C["📄 Copy it<br/>prompts · skills · agents<br/>settings · custom servers"]
    B -->|Yes| D["📝 Record it<br/>plugin sources · extension ids<br/>model names · package names"]
    B -->|It's a secret| E["🔐 Encrypt it<br/>AES-256-GCM vault"]
    C --> F["📦 Backup<br/>~17 MB"]
    D --> F
    E --> F
    F --> G["⚡ restore.ps1<br/>rebuilds everything"]

    style C fill:#1a7f37,color:#fff
    style D fill:#0969da,color:#fff
    style E fill:#8250df,color:#fff
    style F fill:#bf8700,color:#fff
    style G fill:#cf222e,color:#fff
```

**~2 GB of config directories become a 5 MB zip.** Nothing that matters is lost.

---

## Quick start

```powershell
# Download WindowsAIBackup.exe from Releases, then:

.\WindowsAIBackup.exe                    # interactive menu
.\WindowsAIBackup.exe scan               # what's on this PC
.\WindowsAIBackup.exe backup --secrets   # full backup, credentials encrypted
```

After the reinstall:

```powershell
Expand-Archive .\WindowsAIBackup_*.zip -DestinationPath .\restore
cd .\restore
.\restore.ps1 -WhatIf     # preview every action
.\restore.ps1             # rebuild the machine
```

No Python, no dependencies, no installer. One 12 MB file.

---

## Demo and Premium

The same executable runs in **Demo** until you activate a key. Full details in [PRICING.md](PRICING.md).

| | Demo (free) | Premium — **$1 once** |
|---|:---:|:---:|
| Scan, catalog, MCP registry, discovery report | ✅ full | ✅ full |
| **Tools captured in a backup** | **any 5 you pick** | **unlimited** |
| Restore a backup | ✅ **always** | ✅ |
| Encrypted credential vault | — | ✅ |
| Capture uncatalogued tools | — | ✅ |
| Custom MCP server source | listed only | ✅ copied |
| Future tools | — | ✅ |

Demo does not choose for you — pick any five:

```powershell
WindowsAIBackup.exe catalog                                    # every tool id
WindowsAIBackup.exe backup --tools claude-code,cursor,ollama,vscode,windsurf
WindowsAIBackup.exe license                                    # what Premium adds
WindowsAIBackup.exe activate <key>                             # unlock
```

**Scanning, discovery and restore are never gated.** You see everything the tool
finds before deciding to pay, and a backup you already made stays restorable
forever, in any edition.

---

## What it captures

| Category | Handling |
|---|---|
| **Master prompts** — `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, global rules, memories | Copied, and mirrored into `prompts/` for quick access |
| **Skills, agents, slash commands** | Copied — hand-authored, on no registry |
| **MCP servers** | Merged into one registry across every client, with the command that reinstalls each |
| **Custom MCP servers you wrote** | Source copied, dependencies recorded as a rebuild command |
| **Settings** — every client's JSON / TOML / YAML | Copied with credentials stripped |
| **Plugins & marketplaces** | Recorded by source repo, re-cloned on restore |
| **IDE extensions** | Recorded by id, reinstalled via each IDE's CLI |
| **CLI packages** — npm, uv, pipx, bun, winget, go | Recorded, reinstalled from the network |
| **Models** | Cloud model selections copied; local weights recorded and re-pulled |
| **Accounts & IDs** | Emails, user / org / install ids, machine ids |
| **Environment variables** | AI-related names and non-secret values |
| **Credentials** | Encrypted vault only, never in the clear |

---

## Tools it knows about

**87 in the shipped catalog, and it is not a closed list.**

```mermaid
mindmap
  root((87 tools<br/>+ discovery))
    Agent CLIs · 24
      Claude Code
      OpenAI Codex
      Gemini CLI
      Copilot CLI
      Cline · Aider
      OpenCode · Goose
      Amazon Q · Qodo
      Crush · Plandex
      Factory Droid · Amp
      OpenHands · fabric
      aichat · mods · llm
    AI IDEs · 13
      Cursor
      VS Code + Insiders
      Windsurf
      Antigravity
      Zed · Kiro · Trae
      Void · PearAI
      JetBrains AI · Junie
    Local Inference · 12
      Ollama · LM Studio
      Jan · GPT4All · Msty
      AnythingLLM
      Open WebUI
      SillyTavern
      KoboldCpp · LocalAI
    Desktop Apps · 10
      Claude Desktop
      ChatGPT · Perplexity
      Cherry Studio
      LobeChat · Chatbox
      Wispr Flow
    Platforms · 9
      OpenClaw · n8n
      Flowise · Langflow
      Dify · CrewAI
      Letta · mem0
    Extensions · 6
      Continue · Tabnine
      Supermaven · Augment
      Cody · Codeium
    MCP · 5
      Custom workspace
      Serena · mcpm
    LLM Ops · 6
      LangSmith · Langfuse
      W&B · MLflow
      promptfoo · HF CLI
```

### Three ways the list grows

| | How | Needs a new build? |
|---|---|:---:|
| **Shipped catalog** | JSON in [`waib/data/catalog.d/`](waib/data/catalog.d) — one object per tool | no |
| **Your own tools** | Drop JSON into `%APPDATA%\WindowsAIBackup\catalog.local\` | no |
| **Everything else** | Heuristic discovery finds tools nobody catalogued | no |

```powershell
WindowsAIBackup.exe catalog            # browse all 87, '*' marks what's installed
WindowsAIBackup.exe catalog --where    # which files the catalog loads from
WindowsAIBackup.exe catalog --validate # check your own additions parse
WindowsAIBackup.exe discover           # what's here that the catalog misses
```

### Discovery — for the tools nobody has catalogued

A curated list can never keep up; new agents ship weekly, and your company's
internal tool will never be on any public list. Discovery looks for the *shapes*
AI tooling takes on disk rather than for known names.

```mermaid
flowchart TD
    S["Every directory under<br/>~ · %APPDATA% · %LOCALAPPDATA%"] --> F{Already in<br/>the catalog?}
    F -->|Yes| SKIP1["skip"]
    F -->|No| G{A git repo or<br/>npm package?}
    G -->|Yes| SKIP2["skip — that's your project,<br/>not a tool"]
    G -->|No| SCORE["Score the evidence"]

    SCORE --> E1["declares MCP servers · +4"]
    SCORE --> E2["AGENTS.md / CLAUDE.md · +3"]
    SCORE --> E3["name matches an AI vendor · +3"]
    SCORE --> E4["settings name a model or provider · +1"]

    E1 --> T{score ≥ 3?}
    E2 --> T
    E3 --> T
    E4 --> T
    T -->|Yes| KEEP["Captured — the evidence files<br/>plus top-level settings"]
    T -->|No| SKIP3["skip"]

    style KEEP fill:#1a7f37,color:#fff
    style SKIP2 fill:#6e7781,color:#fff
```

On the machine this was built on, discovery found **38 AI tools** beyond the 87 in
the catalog. It captures only the files that earned the score plus top-level
settings — never a recursive sweep of an unknown directory.

---

## How a backup runs

```mermaid
sequenceDiagram
    autonumber
    participant U as You
    participant W as WindowsAIBackup
    participant FS as Your PC
    participant O as Backup folder

    U->>W: backup --secrets
    W->>FS: Walk 87 catalog targets
    FS-->>W: Config roots that exist
    W->>W: Redact secrets by key, value shape, arg position
    W->>W: Scrub keys hardcoded in source
    W->>O: files/ + prompts/
    W->>FS: Read every MCP config dialect
    W->>O: registry/mcp.json (unified)
    W->>FS: Trace custom server entrypoints
    W->>O: Server source, minus node_modules
    W->>FS: npm · uv · pipx · winget · extensions · models
    W->>O: registry/*.json
    W->>O: INVENTORY.md · restore.ps1
    W->>O: secrets.vault (AES-256-GCM)
    O-->>U: 5 MB zip
```

---

## What the backup looks like

```
WindowsAIBackup_2026-08-09_043330/
├── INVENTORY.md          every setting found, and exactly where it lives
├── INVENTORY.json        the same data, machine-readable
├── RESTORE.md            step-by-step rebuild instructions
├── restore.ps1           generated, phase-by-phase restore script
├── secrets.vault         AES-256-GCM, scrypt-derived key (only with --secrets)
├── registry/
│   ├── mcp.json            unified MCP server registry
│   ├── local_servers.json  custom servers + rebuild commands
│   ├── plugins.json        skills, agents, commands, rules, marketplaces
│   ├── models.json         cloud selections + local models
│   ├── packages.json       npm / uv / pipx / winget / go + AI apps
│   ├── extensions.json     IDE extensions by id
│   ├── identity.json       accounts, user ids, install ids
│   └── env.json            AI environment variables
├── files/                verbatim copies, keyed by %ENVVAR% root
└── prompts/              every master prompt and rule file in one place
```

Paths are stored as `%USERPROFILE%\...` and `%APPDATA%\...` rather than absolute,
so a backup restores onto a machine with a **different user name**.

---

## Restoring

`restore.ps1` is generated per-backup and runs in phases. Run all of them, or just one.

```mermaid
flowchart TD
    P1["1 · prereqs<br/><i>Node · Python · Git · uv</i>"] --> P2["2 · apps<br/><i>winget installs</i>"]
    P2 --> P3["3 · packages<br/><i>npm · uv · pipx · bun globals</i>"]
    P3 --> LAUNCH{{"Launch each AI tool once<br/>so it creates its config dir"}}
    LAUNCH --> P4["4 · files<br/><i>settings · prompts · rules<br/>skills · agents</i>"]
    P4 --> P5["5 · mcp<br/><i>prefetch server packages</i>"]
    P5 --> P5b["5b · localservers<br/><i>clone or restore source, rebuild deps</i>"]
    P5b --> P6["6 · plugins<br/><i>marketplaces + plugins</i>"]
    P6 --> P7["7 · extensions<br/><i>per-IDE CLI installs</i>"]
    P7 --> P8["8 · models<br/><i>ollama pull · lms get</i>"]
    P8 --> P9["9 · env<br/><i>user environment variables</i>"]
    P9 --> DONE["🔓 unlock the vault<br/>sign in · done"]

    style LAUNCH fill:#bf8700,color:#fff
    style DONE fill:#1a7f37,color:#fff
```

```powershell
.\restore.ps1 -WhatIf              # preview, changes nothing
.\restore.ps1                      # everything
.\restore.ps1 -Only files,mcp      # just settings and MCP
.\restore.ps1 -Only packages,apps  # just the tooling
```

Every file the script overwrites is backed up beside the original as
`<name>.waib-<timestamp>.bak`. Nothing is destroyed silently.

---

## Security

Credentials never reach the plain-text side of a backup. Three independent layers,
because in testing each one caught leaks the others missed:

```mermaid
flowchart TD
    IN["A file on your PC"] --> L0{Named like a<br/>credential store?}
    L0 -->|"auth.json · .env · *.pem<br/>.credentials.json · id_ed25519"| VAULT
    L0 -->|No| L1{Parses as<br/>JSON / TOML / YAML?}

    L1 -->|Yes| R1["Layer 1 — structured redaction<br/>by key name · by value shape<br/>by argument position"]
    L1 -->|No| R2
    R1 --> R2["Layer 2 — text scrubbing<br/>keys hardcoded in source<br/>tokens buried inside strings"]
    R2 --> OUT["files/ — safe to share"]

    VAULT["Layer 3 — encrypted vault<br/>AES-256-GCM · scrypt N=2¹⁵"] --> SEALED["secrets.vault"]

    style VAULT fill:#8250df,color:#fff
    style SEALED fill:#8250df,color:#fff
    style OUT fill:#1a7f37,color:#fff
```

**Why not DPAPI?** Windows DPAPI keys are bound to the machine and user profile.
A DPAPI-sealed vault becomes unreadable after exactly the reinstall this tool exists
to survive. The vault uses a passphrase you choose, so it travels.

**Without `--secrets`, credentials are neither copied nor stored anywhere.**

Real leaks found and fixed during development, each now covered by a regression test:

- secrets passed as positional CLI args — `["--access-token", "sbp_…"]`
- API keys hardcoded in custom MCP server `.js` source
- local-server copies bypassing the scrubber entirely

A full scan of a production backup — 1950 files, 12 credential patterns — comes back clean.

---

## Commands

| Command | What it does |
|---|---|
| `WindowsAIBackup.exe` | Interactive menu (double-click friendly) |
| `scan` | List every AI tool and MCP server found, write nothing |
| `backup` | Create a backup folder and zip |
| `backup --secrets` | Same, plus an encrypted credential vault |
| `backup --no-zip` / `--zip-only` | Control the output format |
| `mcp` / `mcp --json` | Print the unified MCP server registry |
| `restore -b <folder>` | Dry run — show what would be written |
| `restore -b <folder> --apply` | Write the files back |
| `unlock -b <folder> -o <dir>` | Decrypt the credential vault |
| `unlock -b <folder> --apply` | Put credential files back at their original paths |
| `license` | Show the current edition and what Premium adds |
| `license --remove` | Remove the installed license |
| `activate <key>` | Activate a Premium key |
| `catalog` | Browse every tool the catalog knows |
| `catalog --where` | Show which files the catalog loads from |
| `catalog --validate` | Check every catalog file parses |
| `discover` | Find AI tools that are not in the catalog |
| `backup --tools a,b,c` | Capture only these tools (Demo picks its 5 this way) |
| `backup --discover` | Also capture uncatalogued tools (Premium) |

---

## Building from source

```powershell
git clone https://github.com/srksourabh/windows-ai-backup.git
cd windows-ai-backup
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Runs the test suite, then produces `dist\WindowsAIBackup.exe`.

Development:

```powershell
python -m pip install -r requirements.txt pytest
python -m pytest tests -q
python -m waib scan
```

Requires Python 3.11+ (uses `tomllib`). Windows only — the whole point is Windows paths.

---

## Extending the catalog

One JSON object adds a tool. Drop this in `%APPDATA%\WindowsAIBackup\catalog.localcme.json`:

```json
{
  "tools": [{
    "id": "acme-agent",
    "name": "Acme Internal Agent",
    "category": "Agent CLI",
    "detect": ["~/.acme"],
    "install": { "npm": "@acme/agent" },
    "items": [
      { "path": "~/.acme/config.json", "kind": "config", "note": "Providers and models" },
      { "path": "~/.acme/AGENTS.md",   "kind": "prompt", "note": "Master prompt" },
      { "path": "~/.acme/skills",      "kind": "tree",   "include": ["**/*.md"] },
      { "path": "~/.acme/auth.json",   "kind": "secret" },
      { "path": "~/.acme/cache",       "kind": "record", "note": "Re-downloadable" }
    ],
    "mcp_sources": [
      { "path": "~/.acme/config.json", "fmt": "mcp_servers", "client": "Acme Agent" }
    ]
  }]
}
```

Item kinds: `config` (copy, redact secrets) · `prompt` (copy + mirror into `prompts/`) ·
`tree` (copy with globs and size caps) · `secret` (vault only, never in the clear) ·
`record` (note it, don't copy — it's re-downloadable).

MCP dialects: `mcp_servers` · `claude_json` · `vscode_mcp` · `toml_mcp` · `yaml_mcp`.

Later files win, so you can also *correct* a shipped entry without editing the install.
`catalog --validate` checks your work; a broken file is reported, never fatal.

---

## Architecture

```mermaid
flowchart TB
    subgraph CLI[" "]
        direction LR
        C1["cli.py"] --- C2["interactive.py"]
    end

    CLI --> BK["backup.py<br/><i>orchestration</i>"]
    CLI --> RS["restore.py<br/><i>put it back</i>"]

    BK --> CAT["catalog.py<br/><b>25 Targets — the only file<br/>you edit to add a tool</b>"]

    BK --> COL
    subgraph COL["collect/"]
        direction TB
        F["files.py"]
        M["mcp.py"]
        L["localservers.py"]
        P["plugins.py"]
        MO["models.py"]
        PK["packages.py"]
        E["extensions.py"]
        I["identity.py"]
        V["envvars.py"]
    end

    COL --> SAFE
    subgraph SAFE["safety"]
        direction LR
        U["util.py<br/><i>redaction</i>"]
        S["scrub.py<br/><i>text scrubbing</i>"]
        SV["secrets_vault.py<br/><i>AES-GCM</i>"]
    end

    SAFE --> OUT
    subgraph OUT["output"]
        direction LR
        MAN["manifest.py<br/><i>INVENTORY</i>"]
        RSC["restore_script.py<br/><i>restore.ps1</i>"]
    end

    PATHS["paths.py<br/><i>%ENVVAR% portability</i>"] -.-> COL
    PATHS -.-> RS
    WALK["walk.py · copyio.py<br/><i>pruned walks · long paths · locked files</i>"] -.-> COL

    style CAT fill:#0969da,color:#fff
    style SAFE fill:#8250df,color:#fff
```

Every module is small and single-purpose. Catalog entries are frozen dataclasses;
collectors return new objects rather than mutating shared state, so a scan is
reproducible and side-effect free.

---

## Design notes

**Pruned directory walks.** `Path.rglob` visits every entry under a root, so a 1 GB
`node_modules` costs minutes even when every file in it is filtered out afterwards.
`walk.py` cuts the branch at the directory level instead — the difference between
a 103-second scan and a 24-second one.

**Long paths and locked files.** Plugin and extension trees routinely exceed
`MAX_PATH`, and running AI tools hold their configs open. `copyio.py` handles both:
extended-length `\\?\` prefixes, and a read-and-write fallback when `CopyFile2` refuses.

**Portable paths.** A backup taken as `soura` restores as `alex`. Everything is
stored relative to `%USERPROFILE%`, `%APPDATA%`, `%LOCALAPPDATA%`.

**Custom MCP servers.** An entry like `node C:/Users/me/mcp-servers/foo/index.js`
points at code that exists on no registry — losing it loses the server. Those project
roots get traced from the MCP registry and their source copied, while `node_modules`
is replaced by the command that rebuilds it.

---

## License

The **source code** is MIT — see [LICENSE](LICENSE). Fork it, learn from it, ship your own.

The **Premium key** is a convenience, not a legal restriction: it saves you building
and signing your own binary. If you would rather build from source than pay a dollar,
that is exactly what MIT allows.

Copyright © 2026 **Sourabh Bhaumik**

- Pricing and licensing: [PRICING.md](PRICING.md)
- Full feature reference: [FEATURES.md](FEATURES.md)
