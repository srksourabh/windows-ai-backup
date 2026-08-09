"""Inventory every LLM the machine is configured to use.

Two classes:

* **Local weights** (Ollama, LM Studio, GPT4All) — recorded by name and digest so
  restore re-pulls them instead of moving gigabytes.
* **Cloud models** — the model ids selected inside each client's settings, plus
  the providers/endpoints configured for them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..paths import expand, portable
from ..util import load_structured


def _ollama() -> dict[str, Any]:
    root = expand("~/.ollama/models/manifests")
    if not root.is_dir():
        return {"present": False, "models": []}

    models: list[dict[str, Any]] = []
    for manifest in sorted(root.rglob("*")):
        if not manifest.is_file():
            continue
        rel = manifest.relative_to(root).as_posix().split("/")
        if len(rel) < 3:
            continue
        registry, namespace, name, tag = rel[0], rel[1], "/".join(rel[2:-1]), rel[-1]
        reference = f"{namespace}/{name}:{tag}" if namespace != "library" else f"{name}:{tag}"
        size = 0
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
            size = sum(layer.get("size", 0) for layer in data.get("layers", []))
        except (OSError, json.JSONDecodeError):
            pass
        models.append({
            "reference": reference,
            "registry": registry,
            "approx_bytes": size,
            "restore": f"ollama pull {reference}",
        })

    return {
        "present": True,
        "path": portable(root),
        "count": len(models),
        "models": sorted(models, key=lambda m: m["reference"]),
    }


def _lmstudio() -> dict[str, Any]:
    root = expand("~/.lmstudio/models")
    if not root.is_dir():
        return {"present": False, "models": []}

    models: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".gguf", ".safetensors"}:
            rel = path.relative_to(root).as_posix()
            repo = "/".join(rel.split("/")[:2])
            models.append({
                "file": rel,
                "repo": repo,
                "bytes": path.stat().st_size,
                "restore": f"lms get {repo}",
            })
    return {
        "present": True,
        "path": portable(root),
        "count": len(models),
        "models": models,
    }


#: (label, settings file, dotted-ish keys that name a model)
CLOUD_MODEL_SOURCES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Claude Code", "~/.claude.json", ("model",)),
    ("Claude Code (settings)", "~/.claude/settings.json", ("model", "env.ANTHROPIC_MODEL")),
    ("Codex CLI", "~/.codex/config.toml", ("model", "model_provider", "model_reasoning_effort")),
    ("Gemini CLI", "~/.gemini/settings.json", ("model", "selectedAuthType")),
    ("Copilot CLI", "~/.copilot/config.json", ("model",)),
    ("Cursor", "%APPDATA%/Cursor/User/settings.json", ("cursor.chat.model",)),
    ("VS Code", "%APPDATA%/Code/User/settings.json", ("github.copilot.chat.model", "chat.defaultModel")),
    ("Continue", "~/.continue/config.json", ("models",)),
    ("Aider", "~/.aider.conf.yml", ("model", "weak-model", "editor-model")),
    ("Goose", "~/.config/goose/config.yaml", ("GOOSE_PROVIDER", "GOOSE_MODEL")),
    ("OpenCode", "~/.config/opencode/opencode.json", ("model", "provider")),
)


def _dig(data: Any, dotted: str) -> Any:
    node = data
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def _cloud() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, spec, keys in CLOUD_MODEL_SOURCES:
        path = expand(spec)
        if not path.is_file():
            continue
        data = load_structured(path)
        if not isinstance(data, dict):
            continue
        found = {k: _dig(data, k) for k in keys}
        found = {k: v for k, v in found.items() if v not in (None, {}, [])}
        providers = data.get("model_providers") or data.get("providers")
        if isinstance(providers, dict):
            found["providers"] = sorted(providers.keys())
        if found:
            out.append({"client": label, "source": portable(path), "settings": found})
    return out


def _chat_language_models() -> list[dict[str, Any]]:
    """VS Code-family editors cache the model list they were configured with."""
    out: list[dict[str, Any]] = []
    for spec, label in (
        ("%APPDATA%/Code/User/chatLanguageModels.json", "VS Code"),
        ("%APPDATA%/Code - Insiders/User/chatLanguageModels.json", "VS Code Insiders"),
        ("%APPDATA%/Windsurf/User/chatLanguageModels.json", "Windsurf"),
        ("%APPDATA%/Devin - Next/User/chatLanguageModels.json", "Devin"),
    ):
        path = expand(spec)
        data = load_structured(path) if path.is_file() else None
        if data:
            out.append({"client": label, "source": portable(path), "models": data})
    return out


def collect() -> dict[str, Any]:
    return {
        "local": {"ollama": _ollama(), "lmstudio": _lmstudio()},
        "cloud_selections": _cloud(),
        "registered_chat_models": _chat_language_models(),
    }
