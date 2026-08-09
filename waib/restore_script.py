"""Generate the standalone PowerShell restore script and its companion README.

The generated script is self-contained: it only needs the backup folder next to
it, so a fresh Windows install can run it without Python or this tool present.
"""
from __future__ import annotations

from typing import Any

BACKTICK = chr(96)
DOLLAR = "$"


def _ps_string(value: Any) -> str:
    text = str(value or "")
    return "'" + text.replace("'", "''") + "'"


def _phase(title: str) -> list[str]:
    return ["", f"Write-Step {_ps_string(title)}", ""]


def build(inventory: dict[str, Any]) -> str:
    registries = inventory["registries"]
    lines: list[str] = [
        "<#",
        "    Windows AI Backup - restore script",
        f"    Generated: {inventory.get('created_at')}",
        f"    Source machine: {inventory.get('hostname')} / {inventory.get('username')}",
        "",
        "    Usage:",
        "        powershell -ExecutionPolicy Bypass -File .\\restore.ps1            # full restore",
        "        powershell -ExecutionPolicy Bypass -File .\\restore.ps1 -WhatIf    # preview only",
        "        powershell -ExecutionPolicy Bypass -File .\\restore.ps1 -Only files,mcp",
        "",
        "    Phases: prereqs, packages, apps, files, mcp, plugins, extensions, models, env",
        "#>",
        "[CmdletBinding(SupportsShouldProcess)]",
        "param(",
        "    [string[]] $Only = @(),",
        "    [switch] $SkipConfirm",
        ")",
        "",
        "$ErrorActionPreference = 'Continue'",
        "$script:Root = Split-Path -Parent $MyInvocation.MyCommand.Path",
        "$script:FilesRoot = Join-Path $script:Root 'files'",
        "$script:Failures = @()",
        "",
        "function Write-Step($Text) {",
        "    Write-Host ''",
        "    Write-Host ('=' * 70) -ForegroundColor DarkCyan",
        "    Write-Host $Text -ForegroundColor Cyan",
        "    Write-Host ('=' * 70) -ForegroundColor DarkCyan",
        "}",
        "",
        "function Test-Phase($Name) {",
        "    if ($Only.Count -eq 0) { return $true }",
        "    return $Only -contains $Name",
        "}",
        "",
        "function Invoke-Step($Label, $ScriptBlock) {",
        "    if (-not $PSCmdlet.ShouldProcess($Label)) { return }",
        "    try {",
        "        & $ScriptBlock",
        "        Write-Host ('  [ok] ' + $Label) -ForegroundColor Green",
        "    } catch {",
        "        Write-Host ('  [!!] ' + $Label + ' -> ' + $_.Exception.Message) -ForegroundColor Yellow",
        "        $script:Failures += $Label",
        "    }",
        "}",
        "",
        "function Restore-File($Relative, $Target) {",
        "    $source = Join-Path $script:FilesRoot $Relative",
        "    if (-not (Test-Path -LiteralPath $source)) { throw \"missing in backup: $Relative\" }",
        "    $expanded = [Environment]::ExpandEnvironmentVariables($Target)",
        "    $parent = Split-Path -Parent $expanded",
        "    if ($parent -and -not (Test-Path -LiteralPath $parent)) {",
        "        New-Item -ItemType Directory -Path $parent -Force | Out-Null",
        "    }",
        "    if (Test-Path -LiteralPath $expanded) {",
        "        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'",
        "        Copy-Item -LiteralPath $expanded -Destination \"$expanded.waib-$stamp.bak\" -Force",
        "    }",
        "    Copy-Item -LiteralPath $source -Destination $expanded -Force",
        "}",
        "",
        "Write-Host 'Windows AI Backup - restore' -ForegroundColor Magenta",
        f"Write-Host {_ps_string('Backup taken: ' + str(inventory.get('created_at')))} -ForegroundColor DarkGray",
        "if (-not $SkipConfirm -and -not $WhatIfPreference) {",
        "    $reply = Read-Host 'This will overwrite AI settings on this machine. Continue? (y/N)'",
        "    if ($reply -notmatch '^[Yy]') { Write-Host 'Aborted.'; exit 1 }",
        "}",
    ]

    lines += _phase("PHASE 1/9  Prerequisites")
    lines += ["if (Test-Phase 'prereqs') {"]
    runtimes = registries.get("packages", {}).get("runtimes", {})
    prereqs = [
        ("node", "OpenJS.NodeJS.LTS", "Node.js"),
        ("python", "Python.Python.3.12", "Python 3.12"),
        ("git", "Git.Git", "Git"),
        ("uv", "astral-sh.uv", "uv"),
    ]
    for key, winget_id, label in prereqs:
        if runtimes.get(key):
            lines += [
                f"    if (-not (Get-Command {key} -ErrorAction SilentlyContinue)) {{",
                f"        Invoke-Step {_ps_string('install ' + label)} {{ winget install --id {winget_id} -e --accept-package-agreements --accept-source-agreements }}",
                "    } else {",
                f"        Write-Host {_ps_string('  [skip] ' + label + ' already present')} -ForegroundColor DarkGray",
                "    }",
            ]
    lines += ["}"]

    lines += _phase("PHASE 2/9  AI applications (winget)")
    lines += ["if (Test-Phase 'apps') {"]
    app_ids = {
        target["install"].get("winget"): target["name"]
        for target in inventory["targets"]
        if target["present"] and target["install"].get("winget")
    }
    for winget_id, name in sorted(app_ids.items()):
        lines.append(
            f"    Invoke-Step {_ps_string(name)} {{ winget install --id {winget_id} -e "
            "--accept-package-agreements --accept-source-agreements }"
        )
    for target in inventory["targets"]:
        if target["present"] and not target["install"].get("winget") and target["install"].get("url"):
            lines.append(
                f"    Write-Host {_ps_string('  [manual] ' + target['name'] + ' -> ' + target['install']['url'])} -ForegroundColor Yellow"
            )
    lines += ["}"]

    lines += _phase("PHASE 3/9  CLI packages")
    lines += ["if (Test-Phase 'packages') {"]
    package_registry = registries.get("packages", {})
    # Every hand-installed global is restored: guessing which npm CLI is "AI enough"
    # loses tools, and reinstalling a package that was already wanted costs nothing.
    seen_commands: set[str] = set()
    for pkg in package_registry.get("restore_all") or package_registry.get("ai_packages", []):
        command = pkg.get("restore") or ""
        if command.startswith("#") or not command or command in seen_commands:
            continue
        seen_commands.add(command)
        lines.append(f"    Invoke-Step {_ps_string(pkg['name'])} {{ {command} }}")
    lines += ["}"]

    lines += _phase("PHASE 4/9  Settings, prompts, rules, skills, agents")
    lines += ["if (Test-Phase 'files') {"]
    for target in inventory["targets"]:
        if not target["present"]:
            continue
        copied = [f for f in target["files"] if f["archive"]]
        if not copied:
            continue
        lines.append(f"    Write-Host {_ps_string('  -- ' + target['name'])} -ForegroundColor White")
        for entry in copied:
            rel = entry["archive"][len("files/"):]
            lines.append(
                f"    Invoke-Step {_ps_string(entry['source'])} "
                f"{{ Restore-File {_ps_string(rel)} {_ps_string(entry['source'])} }}"
            )
    lines += ["}"]

    lines += _phase("PHASE 5/9  MCP servers")
    lines += [
        "if (Test-Phase 'mcp') {",
        "    # MCP definitions live in the config files restored in phase 4.",
        "    # These commands pre-fetch the server packages so first launch is instant,",
        "    # and re-register stdio servers with the Claude Code CLI.",
    ]
    seen_fetch: set[str] = set()
    for server in registries.get("mcp", {}).get("servers", []):
        hint = server.get("install_hint") or ""
        if hint.startswith("npx -y "):
            pkg = hint[len("npx -y "):].strip()
            if pkg and pkg not in seen_fetch:
                seen_fetch.add(pkg)
                lines.append(f"    Invoke-Step {_ps_string('prefetch ' + pkg)} {{ npm view {pkg} version | Out-Null }}")
        elif hint.startswith("docker pull "):
            image = hint[len("docker pull "):].strip()
            if image and image not in seen_fetch:
                seen_fetch.add(image)
                lines.append(f"    Invoke-Step {_ps_string(hint)} {{ docker pull {image} }}")
        elif hint.startswith("uvx ") or hint.startswith("pip install "):
            if hint not in seen_fetch:
                seen_fetch.add(hint)
                lines.append(f"    Invoke-Step {_ps_string(hint)} {{ {hint} }}")
    lines += [
        "    Write-Host '  Review registry\\mcp.json for servers needing credentials or a remote login.' -ForegroundColor DarkGray",
        "}",
    ]

    lines += _phase("PHASE 5b/9  Locally-authored MCP servers")
    lines += ["if ((Test-Phase 'mcp') -or (Test-Phase 'localservers')) {"]
    for project in registries.get("local_servers", {}).get("projects", []):
        lines.append(f"    Write-Host {_ps_string('  -- ' + project['name'] + ' (' + project['strategy'] + ')')} -ForegroundColor White")
        target_dir = project["path"]
        if project.get("git_remote"):
            lines += [
                f"    Invoke-Step {_ps_string('clone ' + project['name'])} {{",
                f"        $dir = [Environment]::ExpandEnvironmentVariables({_ps_string(target_dir)})",
                "        if (-not (Test-Path -LiteralPath $dir)) {",
                f"            git clone {project['git_remote']} $dir",
                "        }",
                "    }",
            ]
        rebuild = project.get("rebuild", "")
        if rebuild and not rebuild.startswith("#"):
            lines += [
                f"    Invoke-Step {_ps_string('rebuild ' + project['name'])} {{",
                f"        $dir = [Environment]::ExpandEnvironmentVariables({_ps_string(target_dir)})",
                "        if (Test-Path -LiteralPath $dir) {",
                "            Push-Location $dir",
                f"            {rebuild}",
                "            Pop-Location",
                "        }",
                "    }",
            ]
    lines += ["}"]

    lines += _phase("PHASE 6/9  Claude Code plugins & marketplaces")
    lines += ["if (Test-Phase 'plugins') {"]
    for plugin in registries.get("plugins", {}).get("claude_code", {}).get("plugins", []):
        for step in plugin.get("restore", []):
            if step.startswith("#"):
                lines.append(f"    Write-Host {_ps_string('  [manual] ' + step)} -ForegroundColor Yellow")
            else:
                lines.append(f"    Invoke-Step {_ps_string(step)} {{ {step} }}")
    lines += ["}"]

    lines += _phase("PHASE 7/9  IDE extensions")
    lines += ["if (Test-Phase 'extensions') {"]
    for ide in registries.get("extensions", {}).get("ides", []):
        cli = ide["cli"]
        lines += [
            f"    if (Get-Command {cli} -ErrorAction SilentlyContinue) {{",
            f"        Write-Host {_ps_string('  -- ' + ide['ide'] + ' (' + str(ide['count']) + ' extensions)')} -ForegroundColor White",
        ]
        for ext in ide["extensions"]:
            lines.append(
                f"        Invoke-Step {_ps_string(ide['ide'] + ': ' + ext['id'])} "
                f"{{ {cli} --install-extension {ext['id']} --force }}"
            )
        lines += [
            "    } else {",
            f"        Write-Host {_ps_string('  [skip] ' + ide['ide'] + ' CLI not on PATH')} -ForegroundColor DarkGray",
            "    }",
        ]
    lines += ["}"]

    lines += _phase("PHASE 8/9  Local models")
    lines += ["if (Test-Phase 'models') {"]
    local = registries.get("models", {}).get("local", {})
    for model in local.get("ollama", {}).get("models", []):
        lines.append(f"    Invoke-Step {_ps_string(model['restore'])} {{ {model['restore']} }}")
    lm_repos = sorted({m["repo"] for m in local.get("lmstudio", {}).get("models", [])})
    for repo in lm_repos:
        lines.append(f"    Invoke-Step {_ps_string('lms get ' + repo)} {{ lms get {repo} }}")
    lines += ["}"]

    lines += _phase("PHASE 9/9  Environment variables")
    lines += ["if (Test-Phase 'env') {"]
    for var in registries.get("env", {}).get("variables", []):
        if var["scope"] != "user (persistent)":
            continue
        if var["is_secret"]:
            lines.append(
                f"    Write-Host {_ps_string('  [secret] ' + var['name'] + ' -> restore from the vault (waib unlock)')} -ForegroundColor Yellow"
            )
        else:
            lines.append(
                f"    Invoke-Step {_ps_string('setx ' + var['name'])} "
                f"{{ [Environment]::SetEnvironmentVariable({_ps_string(var['name'])}, {_ps_string(var['value'])}, 'User') }}"
            )
    lines += ["}"]

    lines += [
        "",
        "Write-Step 'Done'",
        "if ($script:Failures.Count -gt 0) {",
        "    Write-Host 'Steps that need attention:' -ForegroundColor Yellow",
        "    $script:Failures | ForEach-Object { Write-Host ('  - ' + $_) -ForegroundColor Yellow }",
        "} else {",
        "    Write-Host 'All steps completed.' -ForegroundColor Green",
        "}",
        "Write-Host ''",
        "Write-Host 'Next: sign in to each tool, then unseal credentials with:' -ForegroundColor Cyan",
        "Write-Host '    WindowsAIBackup.exe unlock --backup . --out restored-secrets' -ForegroundColor Cyan",
        "",
    ]
    return "\n".join(lines) + "\n"


def readme(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    return f"""# Restoring this backup

Taken {inventory.get('created_at')} on `{inventory.get('hostname')}` (user `{inventory.get('username')}`).

Contains **{summary['tools_detected']} AI tools**, **{summary['mcp_servers']} MCP servers**,
**{summary['skills']} skills**, **{summary['agents']} agents**, **{summary['ide_extensions']} IDE extensions**,
**{summary['local_models']} local models**.

## Quick restore

```powershell
Expand-Archive .\\WindowsAIBackup_*.zip -DestinationPath .\\restore
cd .\\restore
powershell -ExecutionPolicy Bypass -File .\\restore.ps1 -WhatIf   # preview
powershell -ExecutionPolicy Bypass -File .\\restore.ps1           # apply
```

Run a single phase with `-Only`:

```powershell
.\\restore.ps1 -Only files          # settings, prompts, rules, skills, agents only
.\\restore.ps1 -Only packages,apps  # reinstall tooling only
.\\restore.ps1 -Only mcp,plugins
```

Phases: `prereqs`, `apps`, `packages`, `files`, `mcp`, `plugins`, `extensions`, `models`, `env`.

Every file the script overwrites is backed up next to the original as
`<name>.waib-<timestamp>.bak`.

## Credentials

Secrets are never stored in the clear. If the backup was taken with `--secrets`,
`secrets.vault` holds them under AES-256-GCM with a scrypt-derived key.

```powershell
WindowsAIBackup.exe unlock --backup . --out .\\restored-secrets
```

You will be prompted for the passphrase. Files are written back to their original
names inside `restored-secrets\\` — copy them into place, or let
`WindowsAIBackup.exe unlock --apply` put them back at their recorded paths.

Without a vault, sign in to each tool normally; everything else restores unattended.

## What is in the folder

| Path | Contents |
|---|---|
| `INVENTORY.md` | Human-readable report: every setting found and where it lives |
| `INVENTORY.json` | The same data, machine-readable |
| `registry/mcp.json` | Unified MCP server registry across all clients |
| `registry/plugins.json` | Skills, agents, commands, rules, plugins, marketplaces |
| `registry/models.json` | Cloud model selections + local model list |
| `registry/packages.json` | npm/uv/pipx/winget packages and AI apps |
| `registry/extensions.json` | IDE extensions by id |
| `registry/identity.json` | Account emails, user/org ids, install ids |
| `registry/env.json` | AI environment variables |
| `files/` | Verbatim copies, mirrored by `%ENVVAR%` root |
| `prompts/` | Master prompts, rules, and memories in one place |
| `restore.ps1` | The generated restore script |

## Order of operations after a Windows reinstall

1. Install Windows, sign in, connect to the network.
2. Install a package manager base: winget is built in; `restore.ps1 -Only prereqs`
   adds Node, Python, Git, uv.
3. `restore.ps1 -Only apps,packages` — installs the AI tools themselves.
4. Launch each tool **once** so it creates its config directory, then close it.
5. `restore.ps1 -Only files,mcp,plugins,extensions` — puts your settings back.
6. `restore.ps1 -Only models,env`.
7. Sign in to each tool (or unseal the vault).
"""
