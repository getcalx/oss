"""Tests for calx.hooks.installer."""

from __future__ import annotations

import json
import os
from pathlib import Path

from calx.hooks.installer import (
    _extract_commands,
    _merge_hooks,
    install_hooks,
)


def test_install_creates_settings_json(tmp_path: Path):
    """install_hooks creates .claude/settings.json when it doesn't exist."""
    result = install_hooks(tmp_path)
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    assert result.settings_created is True


def test_hooks_structure(tmp_path: Path):
    """Hooks are correctly structured in the output."""
    install_hooks(tmp_path)
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]

    # SessionStart
    assert "SessionStart" in hooks
    assert len(hooks["SessionStart"]) == 1
    start_cmd = hooks["SessionStart"][0]["hooks"][0]["command"]
    assert start_cmd.endswith("/session-start.sh")
    assert "/" in start_cmd and not start_cmd.startswith(".")  # absolute path

    # PreToolUse
    assert "PreToolUse" in hooks
    assert len(hooks["PreToolUse"]) == 1
    assert hooks["PreToolUse"][0]["matcher"] == "Edit|Write"
    commands = [h["command"] for h in hooks["PreToolUse"][0]["hooks"]]
    assert any(c.endswith("/orientation-gate.sh") for c in commands)
    assert any(c.endswith("/collapse-guard.sh") for c in commands)

    # Stop
    assert "Stop" in hooks
    assert len(hooks["Stop"]) == 1
    stop_cmd = hooks["Stop"][0]["hooks"][0]["command"]
    assert stop_cmd.endswith("/session-end.sh")
    assert not stop_cmd.startswith(".")


def test_idempotent_install(tmp_path: Path):
    """Re-running install_hooks doesn't duplicate hooks."""
    result1 = install_hooks(tmp_path)
    result2 = install_hooks(tmp_path)

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]

    # Should have exactly the same number of entries
    assert len(hooks["SessionStart"]) == 1
    assert len(hooks["PreToolUse"]) == 1
    assert len(hooks["Stop"]) == 1

    # Second run should skip all hooks
    assert len(result1.hooks_installed) == 3
    assert len(result2.hooks_skipped) == 3
    assert result2.settings_created is False


def test_existing_hooks_preserved(tmp_path: Path):
    """Existing hooks in settings.json are preserved."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    existing = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "my-custom-hook.sh"}],
                }
            ]
        },
        "other_setting": True,
    }
    (claude_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")

    install_hooks(tmp_path)

    settings = json.loads((claude_dir / "settings.json").read_text())

    # Original setting preserved
    assert settings["other_setting"] is True

    # Original PreToolUse hook preserved
    pre_tool = settings["hooks"]["PreToolUse"]
    commands = set()
    for entry in pre_tool:
        for hook in entry.get("hooks", []):
            commands.add(hook["command"])

    assert "my-custom-hook.sh" in commands
    assert any(c.endswith("/orientation-gate.sh") for c in commands)
    assert any(c.endswith("/collapse-guard.sh") for c in commands)


def test_templates_copied(tmp_path: Path):
    """Hook templates are copied to .calx/hooks/ with correct names."""
    install_hooks(tmp_path)

    hooks_dir = tmp_path / ".calx" / "hooks"
    expected = ["session-start.sh", "session-end.sh", "orientation-gate.sh", "collapse-guard.sh"]
    for name in expected:
        assert (hooks_dir / name).exists(), f"{name} not found in .calx/hooks/"


def test_templates_executable(tmp_path: Path):
    """Hook templates are executable."""
    install_hooks(tmp_path)

    hooks_dir = tmp_path / ".calx" / "hooks"
    for name in ["session-start.sh", "session-end.sh", "orientation-gate.sh", "collapse-guard.sh"]:
        path = hooks_dir / name
        assert os.access(path, os.X_OK), f"{name} is not executable"


def test_merge_hooks_preserves_existing():
    """_merge_hooks preserves existing entries."""
    existing = {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": "other-start.sh"}]}
        ],
    }
    calx_hooks = {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": ".calx/hooks/session-start.sh"}]}
        ],
        "Stop": [
            {"hooks": [{"type": "command", "command": ".calx/hooks/session-end.sh"}]}
        ],
    }

    merged = _merge_hooks(existing, calx_hooks)

    # Original entry preserved
    commands = _extract_commands(merged["SessionStart"])
    assert "other-start.sh" in commands
    assert ".calx/hooks/session-start.sh" in commands

    # New event added
    assert "Stop" in merged


def test_extract_commands():
    """_extract_commands works correctly."""
    entries = [
        {
            "matcher": "Edit|Write",
            "hooks": [
                {"type": "command", "command": "hook-a.sh"},
                {"type": "command", "command": "hook-b.sh"},
            ],
        },
        {
            "hooks": [{"type": "command", "command": "hook-c.sh"}],
        },
    ]
    result = _extract_commands(entries)
    assert result == {"hook-a.sh", "hook-b.sh", "hook-c.sh"}


def test_extract_commands_empty():
    """_extract_commands handles empty and malformed input."""
    assert _extract_commands([]) == set()
    assert _extract_commands([{"no_hooks_key": True}]) == set()
    assert _extract_commands([{"hooks": [{"no_command": True}]}]) == set()
