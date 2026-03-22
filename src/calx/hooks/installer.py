"""Hook installer for Calx — wires into .claude/settings.json."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InstallResult:
    hooks_installed: list[str] = field(default_factory=list)
    hooks_skipped: list[str] = field(default_factory=list)
    settings_created: bool = False


def _calx_hooks(project_dir: Path) -> dict:
    """Build hook config with absolute paths to prevent resolution failures."""
    hooks_dir = str((project_dir / ".calx" / "hooks").resolve())
    return {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": f"{hooks_dir}/session-start.sh"}]}
        ],
        "PreToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {"type": "command", "command": f"{hooks_dir}/orientation-gate.sh"},
                    {"type": "command", "command": f"{hooks_dir}/collapse-guard.sh"},
                ],
            }
        ],
        "Stop": [
            {"hooks": [{"type": "command", "command": f"{hooks_dir}/session-end.sh"}]}
        ],
    }

# Template source name -> installed name mapping
_TEMPLATE_MAP = {
    "session_start.sh": "session-start.sh",
    "session_end.sh": "session-end.sh",
    "orientation_gate.sh": "orientation-gate.sh",
    "collapse_guard.sh": "collapse-guard.sh",
}


def install_hooks(project_dir: Path) -> InstallResult:
    """Install Calx hooks into .claude/settings.json and copy hook scripts.

    1. Copy shell templates from package data to .calx/hooks/
    2. Merge hook config into .claude/settings.json
    """
    result = InstallResult()

    # Copy hook templates
    _copy_templates(project_dir)

    # Merge into settings.json
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"

    if settings_path.exists():
        settings = _read_claude_settings(project_dir)
    else:
        settings = {}
        result.settings_created = True

    calx_hooks = _calx_hooks(project_dir)
    existing_hooks = settings.get("hooks", {})
    merged = _merge_hooks(existing_hooks, calx_hooks)

    # Track what was installed vs skipped
    for event_name in calx_hooks:
        if event_name not in existing_hooks:
            result.hooks_installed.append(event_name)
        else:
            # Check if our hooks were already present
            existing_commands = _extract_commands(existing_hooks.get(event_name, []))
            new_commands = _extract_commands(calx_hooks[event_name])
            added = [c for c in new_commands if c not in existing_commands]
            if added:
                result.hooks_installed.append(event_name)
            else:
                result.hooks_skipped.append(event_name)

    settings["hooks"] = merged
    _write_claude_settings(project_dir, settings)

    return result


def _copy_templates(project_dir: Path) -> None:
    """Copy hook templates from package data to .calx/hooks/."""
    hooks_dir = project_dir / ".calx" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    templates_dir = Path(__file__).parent / "templates"

    for source_name, installed_name in _TEMPLATE_MAP.items():
        source = templates_dir / source_name
        dest = hooks_dir / installed_name
        if source.exists():
            shutil.copy2(source, dest)
            dest.chmod(0o755)  # Set executable


def _read_claude_settings(project_dir: Path) -> dict:
    """Read .claude/settings.json."""
    path = project_dir / ".claude" / "settings.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _merge_hooks(existing: dict, calx_hooks: dict) -> dict:
    """Merge Calx hooks into existing hooks without clobbering."""
    merged = dict(existing)

    for event_name, calx_entries in calx_hooks.items():
        if event_name not in merged:
            merged[event_name] = calx_entries
        else:
            # Append Calx entries that aren't already present
            existing_commands = _extract_commands(merged[event_name])
            for entry in calx_entries:
                entry_commands = _extract_commands([entry])
                if not all(c in existing_commands for c in entry_commands):
                    merged[event_name].append(entry)

    return merged


def _extract_commands(entries: list) -> set[str]:
    """Extract all command strings from hook entries."""
    commands: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict):
            for hook in entry.get("hooks", []):
                if isinstance(hook, dict) and "command" in hook:
                    commands.add(hook["command"])
    return commands


def _write_claude_settings(project_dir: Path, settings: dict) -> None:
    """Write .claude/settings.json."""
    path = project_dir / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
