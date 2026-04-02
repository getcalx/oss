"""Auto-init logic for calx serve.

On first run (no .calx/ directory), creates .calx/, detects Claude Code,
registers hooks, generates bearer token. Zero interactive prompts.
"""
from __future__ import annotations

import json
import secrets
import sys
import uuid
from pathlib import Path


def auto_init(project_dir: Path) -> dict:
    """Auto-initialize .calx/ directory if it doesn't exist.

    Returns dict with initialization results. Silent: no interactive prompts.
    """
    calx_dir = project_dir / ".calx"

    # Skip if already initialized
    if calx_dir.exists() and (calx_dir / "calx.json").exists():
        return {"initialized": False}

    calx_dir.mkdir(exist_ok=True)

    # Create state directory
    state_dir = calx_dir / "state"
    state_dir.mkdir(exist_ok=True)

    # Create rules directory
    rules_dir = calx_dir / "rules"
    rules_dir.mkdir(exist_ok=True)

    # Generate auth token
    auth_token = secrets.token_urlsafe(32)

    # Write server.json
    server_json = {
        "host": "127.0.0.1",
        "port": 4195,
        "auth_token": auth_token,
    }
    (calx_dir / "server.json").write_text(json.dumps(server_json, indent=2))

    # Write calx.json with defaults
    calx_json = {
        "schema_version": "2.0",
        "enforcement": {
            "server_fail_mode": "open",
            "collapse_fail_mode": "closed",
            "tokens_per_call": 1000,
        },
        "token_discipline": {
            "soft_cap": 200000,
            "ceiling": 250000,
        },
        "telemetry": {
            "enabled": True,
            "install_id": str(uuid.uuid4()),
        },
    }
    (calx_dir / "calx.json").write_text(json.dumps(calx_json, indent=2))

    # Telemetry notice (non-interactive, safe for subprocess/CI)
    print(
        "Calx: Anonymous usage telemetry is enabled by default.\n"
        "We collect: session duration, feature usage flags, aggregate counts.\n"
        "We do NOT collect: correction text, rule text, file paths, project names, or any content.\n"
        "Run `calx telemetry --show` to see exactly what gets sent.\n"
        "Run `calx telemetry --off` to disable permanently.",
        file=sys.stderr,
    )

    # Install ping (one-time, fire-and-forget)
    if calx_json["telemetry"]["enabled"]:
        _send_install_ping(calx_json["telemetry"]["install_id"])

    # Install default foil profiles
    _install_foil_profiles(calx_dir)

    result = {"initialized": True, "calx_dir": str(calx_dir)}

    # Detect Claude Code
    claude_dir = project_dir / ".claude"
    if claude_dir.exists():
        result["claude_code_detected"] = True
        _register_claude_code_hooks(project_dir, calx_dir)
        print(
            "Calx: initialized. Claude Code hooks registered.",
            file=sys.stderr,
        )
    else:
        print("Calx: initialized. No Claude Code detected.", file=sys.stderr)

    return result


def _register_claude_code_hooks(project_dir: Path, calx_dir: Path) -> None:
    """Register hooks in .claude/settings.json."""
    settings_file = project_dir / ".claude" / "settings.json"

    # Load existing settings or start fresh
    settings: dict = {}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
        except (json.JSONDecodeError, OSError):
            settings = {}

    # Define hook config
    hooks = settings.get("hooks", {})

    hooks["SessionStart"] = [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": ".calx/hooks/session-start.sh",
                }
            ]
        }
    ]

    hooks["PreToolUse"] = [
        {
            "matcher": "Edit|Write",
            "hooks": [
                {
                    "type": "command",
                    "command": ".calx/hooks/enforce.sh",
                }
            ],
        }
    ]

    hooks["Stop"] = [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": ".calx/hooks/session-end.sh",
                }
            ]
        }
    ]

    settings["hooks"] = hooks
    settings_file.write_text(json.dumps(settings, indent=2))

    # Install hook shell scripts
    _install_hook_scripts(calx_dir)


def _install_hook_scripts(calx_dir: Path) -> None:
    """Copy hook shell scripts into .calx/hooks/."""
    hooks_dir = calx_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    templates_dir = Path(__file__).parent / "hooks" / "templates"

    script_map = {
        "session_start.sh": "session-start.sh",
        "enforce.sh": "enforce.sh",
        "session_end.sh": "session-end.sh",
    }

    for src_name, dst_name in script_map.items():
        src = templates_dir / src_name
        dst = hooks_dir / dst_name
        if src.exists():
            dst.write_text(src.read_text())
            dst.chmod(0o755)


def _install_foil_profiles(calx_dir: Path) -> None:
    """Copy bundled default foil profiles into .calx/foils/."""
    foils_dir = calx_dir / "foils"
    foils_dir.mkdir(exist_ok=True)

    profiles_dir = Path(__file__).parent / "foil_profiles"
    if not profiles_dir.exists():
        return

    for src in profiles_dir.glob("*.md"):
        dst = foils_dir / src.name
        if not dst.exists():
            dst.write_text(src.read_text())


def _send_install_ping(install_id: str) -> None:
    """Send a one-time install event. Fire-and-forget, never raises."""
    import platform
    try:
        from calx.serve.engine.telemetry_sender import send_telemetry
        payload = {
            "v": 1,
            "event_type": "install",
            "install_id": install_id,
            "payload_id": str(uuid.uuid4()),
            "calx_version": _get_calx_version(),
            "os": platform.system().lower(),
            "arch": platform.machine(),
            "python_version": platform.python_version(),
        }
        send_telemetry(payload)
    except Exception:
        pass


def _get_calx_version() -> str:
    try:
        from calx.serve import __version__
        return __version__
    except Exception:
        return "unknown"


def detect_old_hooks(project_dir: Path) -> list[str]:
    """Check .claude/settings.json for old-style hook commands.

    Returns list of hook entries that use old-style commands (not .calx/hooks/).
    """
    settings_file = project_dir / ".claude" / "settings.json"
    if not settings_file.exists():
        return []

    try:
        settings = json.loads(settings_file.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    hooks = settings.get("hooks", {})
    old_entries = []
    for event_name, entries in hooks.items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd and ".calx/hooks/" not in cmd and "calx" in cmd.lower():
                    old_entries.append(f"{event_name}: {cmd}")
    return old_entries


def upgrade_init(project_dir: Path) -> dict:
    """Upgrade an existing .calx/ installation.

    Re-registers hooks preserving existing config. Used by `calx init --upgrade`.
    """
    calx_dir = project_dir / ".calx"
    if not calx_dir.exists():
        print("No .calx/ directory found. Run `calx serve` first.", file=sys.stderr)
        return {"upgraded": False}

    old_hooks = detect_old_hooks(project_dir)
    if old_hooks:
        print(f"Detected {len(old_hooks)} old-style hook(s):", file=sys.stderr)
        for h in old_hooks:
            print(f"  {h}", file=sys.stderr)

    # Re-register hooks
    claude_dir = project_dir / ".claude"
    if claude_dir.exists():
        _register_claude_code_hooks(project_dir, calx_dir)
        print("Hooks re-registered.", file=sys.stderr)
    else:
        print("No .claude/ directory found. Hooks not updated.", file=sys.stderr)

    # Re-install hook scripts and foil profiles
    _install_hook_scripts(calx_dir)
    _install_foil_profiles(calx_dir)

    return {"upgraded": True, "old_hooks_found": len(old_hooks)}
