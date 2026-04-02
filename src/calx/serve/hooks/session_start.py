"""Session start hook -- fires once at the beginning of each Claude Code session.

1. Register session with server (POST /enforce/register-session)
2. Mark session as oriented (POST /enforce/mark-oriented)
3. Output briefing to stdout (injected into agent context)
4. Fall back to file-based injection if server unreachable
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from calx.serve.hooks._common import (
    find_calx_dir,
    get_server_url,
    log_hook_error,
    server_is_running,
)


def _register_and_brief(server_url: str, surface: str = "claude-code") -> str | None:
    """Register session with server and get briefing."""
    try:
        import urllib.request
        body = json.dumps({"surface": surface}).encode()
        req = urllib.request.Request(
            f"{server_url}/enforce/register-session",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        session_id = data.get("session_id", "")

        # Mark oriented immediately
        if session_id:
            mark_body = json.dumps({"session_id": session_id}).encode()
            mark_req = urllib.request.Request(
                f"{server_url}/enforce/mark-oriented",
                data=mark_body,
                method="POST",
            )
            mark_req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(mark_req, timeout=2)

        return data.get("briefing")
    except Exception:
        return None


def _inject_rules_from_files(calx_dir: Path) -> None:
    """Fallback: inject rules from .calx/rules/*.md to stdout."""
    rules_dir = calx_dir / "rules"
    if not rules_dir.exists():
        return
    for rule_file in sorted(rules_dir.glob("*.md")):
        content = rule_file.read_text().strip()
        if content:
            print(content)


def _get_fail_mode(calx_dir: Path) -> str:
    """Read server_fail_mode from calx.json. Default: open."""
    config_file = calx_dir / "calx.json"
    if not config_file.exists():
        return "open"
    try:
        with open(config_file) as f:
            data = json.load(f)
        return data.get("enforcement", {}).get("server_fail_mode", "open")
    except (json.JSONDecodeError, OSError):
        return "open"


def main() -> None:
    """Session start hook entry point."""
    try:
        calx_dir = find_calx_dir()
        if not calx_dir:
            return

        server_url = get_server_url(calx_dir)
        if server_url and server_is_running(server_url):
            briefing = _register_and_brief(server_url)
            if briefing:
                print(briefing)
            else:
                _inject_rules_from_files(calx_dir)
        else:
            fail_mode = _get_fail_mode(calx_dir)
            if fail_mode == "open":
                _inject_rules_from_files(calx_dir)
                # Surface last handoff if available
                handoff_file = calx_dir / "state" / "last-handoff.json"
                if handoff_file.exists():
                    try:
                        data = json.loads(handoff_file.read_text())
                        what_changed = data.get("what_changed", "")
                        if what_changed:
                            print(f"\n## Last Session Handoff\n\n{what_changed}")
                    except (json.JSONDecodeError, OSError):
                        pass
                print("Calx: Server unreachable. Rules loaded from files.", file=sys.stderr)
            else:
                print("Calx: Server unreachable and server_fail_mode=closed.", file=sys.stderr)

    except Exception as e:
        log_hook_error(f"session_start: {e}")


if __name__ == "__main__":
    main()
