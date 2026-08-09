# Changelog

## 2.0.0 — 2026-08-09

The catalog stopped being a list and became a platform.

### The tool list is no longer fixed

* **Catalog is data, not code.** 87 tools ship as JSON under
  `waib/data/catalog.d/`. Adding one is a JSON object — no code change, no rebuild.
* **Four merge layers.** Bundled files, downloadable updates
  (`%APPDATA%\WindowsAIBackup\catalog\`), and your own in-house tools
  (`%APPDATA%\WindowsAIBackup\catalog.local\`). Later ids override earlier ones, so
  a user can correct a shipped entry without touching the install.
* **Heuristic discovery.** For everything nobody catalogued, `discover` scores
  directories on real evidence — a file declaring MCP servers, an `AGENTS.md`, a
  vendor name, settings that name a model. On the development machine it found 38
  AI tools beyond the 87 in the catalog.
* **New commands:** `catalog`, `catalog --where`, `catalog --validate`, `discover`.

Catalog grew from 25 to 87: 24 agent CLIs, 13 AI IDEs, 12 local inference
runtimes, 10 desktop apps, 9 agent platforms, 6 IDE extensions, 6 LLM Ops tools,
5 MCP tools.

### Editions

* **Demo now captures any 5 tools you choose**, not a fixed five:
  `backup --tools claude-code,cursor,ollama,vscode,windsurf`. Without `--tools` it
  picks the five most broadly useful tools that are actually installed.
* **Premium is unlimited**, and adds `--discover` for uncatalogued tools.
* `scan`, `catalog`, `mcp`, `discover` and `restore` remain ungated in both
  editions — you see everything before paying, and your own backup is never held
  hostage.

### Fixes

* **Long destination paths no longer abort a whole tree.** A backup folder nested
  deep enough pushed mirrored paths past `MAX_PATH`; `Path.mkdir` threw and the
  entire item was lost. On one run that silently dropped 589 skill files.
* **`Path.is_file()` lies past `MAX_PATH`.** Restore reported 6,547 files "missing
  from backup" that were present all along. Every filesystem touch in the restore
  engine now goes through the extended-length API.
* **YAML and TOML dates no longer break a copy.** A config with a native date
  value raised `TypeError` from `json.dumps` and the file was skipped.
* **Discovery no longer sweeps extension stores or cloud sync roots.** It captures
  the files that earned the score plus top-level settings, capped at 5 MB per tool
  — 124 MB down to 34 MB on the development machine.

### Tests

121 tests, including new suites for catalog loading, merge precedence, malformed
user files, discovery scoring and its exclusions.

---

## 1.0.0 — 2026-08-09

First release.

* 25 AI tools in a hand-written catalog
* Unified MCP server registry across six config dialects, with reinstall hints
* Custom MCP server source captured; dependencies recorded as rebuild commands
* Three-layer credential safety: structured redaction, text scrubbing, filename
  rules; AES-256-GCM vault with a scrypt-derived key
* Portable `%ENVVAR%` paths so a backup restores under a different user name
* Generated phase-based `restore.ps1` with `-WhatIf` and per-phase selection
* Demo and Premium editions, Ed25519-signed offline license keys
