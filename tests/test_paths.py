"""Path portability is the hinge the whole restore depends on."""
from __future__ import annotations

import os

import pytest

from waib import paths


def test_portable_uses_userprofile_placeholder():
    target = paths.expand("~/.claude/settings.json")
    assert paths.portable(target).startswith("%USERPROFILE%")


def test_portable_prefers_most_specific_root():
    """LOCALAPPDATA lives under USERPROFILE; the deeper root must win."""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        pytest.skip("LOCALAPPDATA not set")
    assert paths.portable(local + r"\Programs").startswith("%LOCALAPPDATA%")


def test_archive_relpath_strips_placeholder_syntax():
    target = paths.expand("~/.claude/settings.json")
    assert paths.archive_relpath(target) == "USERPROFILE/.claude/settings.json"


def test_restore_target_round_trips():
    original = paths.expand("~/.claude/settings.json")
    rel = paths.archive_relpath(original)
    assert paths.restore_target(rel) == original


def test_restore_target_handles_absolute_drive_paths():
    rel = paths.archive_relpath(r"D:\tools\thing.json")
    restored = paths.restore_target(rel)
    assert restored is not None
    assert str(restored).lower().startswith("d:")


def test_restore_target_returns_none_for_unknown_root():
    assert paths.restore_target("NOT_A_REAL_ENV_VAR/x/y.json") is None


def test_expand_handles_env_placeholders():
    assert paths.expand("%APPDATA%/Claude").is_absolute()
