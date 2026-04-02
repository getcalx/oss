"""Enforcement gate: orientation + tool-call counting + collapse guard.

Merged PreToolUse hook that fires on every Edit/Write. Reads state file
for fast hot-path decisions. Falls back to HTTP when state file is missing.

Exit codes:
  0 = allow (optionally with stderr warning)
  2 = block (with stdout message for agent context)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from calx.serve.hooks._common import find_calx_dir, log_hook_error


@dataclass
class EnforceResult:
    exit_code: int  # 0 = allow, 2 = block
    message: str = ""  # stdout message (for agent context on block)
    warning: str | None = None  # stderr warning (advisory)


def run_enforce(
    state_dir: Path,
    server_url: str | None = None,
    server_fail_mode: str = "open",
) -> EnforceResult:
    """Run the enforcement gate logic. Returns result with exit code and messages."""
    # Read active session ID
    active_file = state_dir / "active-session"
    if not active_file.exists():
        return EnforceResult(exit_code=0)

    session_id = active_file.read_text().strip()
    if not session_id:
        return EnforceResult(exit_code=0)

    # Read state file
    state_file = state_dir / f"session-{session_id}.json"
    if not state_file.exists():
        # No state file: fall back to server or respect fail mode
        if server_url:
            return _http_fallback(server_url, session_id, server_fail_mode)
        if server_fail_mode == "closed":
            return EnforceResult(exit_code=2, message="Calx: No state file and server_fail_mode=closed.")
        return EnforceResult(exit_code=0)

    try:
        data = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return EnforceResult(exit_code=0)

    # Step 1: Orientation check
    if not data.get("oriented", False):
        rules = data.get("rules", [])
        if not rules:
            return EnforceResult(
                exit_code=2,
                message="Calx: No rules yet. Make corrections with `calx correct` and they'll compound into rules.",
            )
        rule_count = len(rules)
        return EnforceResult(
            exit_code=2,
            message=f"Calx: {rule_count} rules loaded. Read rules before editing files.",
        )

    # Step 2: Increment tool call count (if server available)
    collapse_fail_mode = data.get("collapse_fail_mode", "closed")

    if server_url:
        incr_result = _call_increment_tool_call(server_url, session_id)
        if incr_result:
            action = incr_result.get("action", "allow")
            tool_call_count = incr_result.get("tool_call_count", 0)
            token_estimate = incr_result.get("token_estimate", 0)
            return _apply_action(action, tool_call_count, token_estimate, collapse_fail_mode)

    # Fallback: use state file values (stale but better than nothing)
    token_estimate = data.get("token_estimate", 0)
    tool_call_count = data.get("tool_call_count", 0)
    soft_cap = data.get("soft_cap", 200000)
    ceiling = data.get("ceiling", 250000)

    if token_estimate >= ceiling:
        return _apply_action("block", tool_call_count, token_estimate, collapse_fail_mode)
    if token_estimate >= soft_cap:
        return _apply_action("warn", tool_call_count, token_estimate, collapse_fail_mode)

    return EnforceResult(exit_code=0)


def _apply_action(
    action: str, tool_call_count: int, token_estimate: int, collapse_fail_mode: str,
) -> EnforceResult:
    """Convert an action string to an EnforceResult."""
    if action == "block":
        if collapse_fail_mode == "closed":
            return EnforceResult(
                exit_code=2,
                message="CEILING REACHED. Commit everything. Write handoff. End session.",
            )
        return EnforceResult(
            exit_code=0,
            warning=f"Calx: {tool_call_count} tool calls, ~{token_estimate} tokens. CEILING REACHED but collapse_fail_mode=open.",
        )
    if action == "warn":
        return EnforceResult(
            exit_code=0,
            warning=f"Calx: {tool_call_count} tool calls, ~{token_estimate} tokens. Approaching session ceiling.",
        )
    return EnforceResult(exit_code=0)


def _call_increment_tool_call(server_url: str, session_id: str) -> dict | None:
    """POST /enforce/increment-tool-call. Returns response dict or None on failure."""
    try:
        import urllib.request
        body = json.dumps({"session_id": session_id}).encode()
        req = urllib.request.Request(
            f"{server_url}/enforce/increment-tool-call",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=2)
        return json.loads(resp.read())
    except Exception:
        return None


def _http_fallback(
    server_url: str, session_id: str, server_fail_mode: str = "open",
) -> EnforceResult:
    """Fall back to server HTTP for orientation check."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{server_url}/enforce/orientation?session_id={session_id}",
            method="GET",
        )
        resp = urllib.request.urlopen(req, timeout=2)
        data = json.loads(resp.read())
        if not data.get("oriented", False):
            return EnforceResult(
                exit_code=2,
                message="Calx: Loading rules before first edit. This runs once per session.",
            )
        return EnforceResult(exit_code=0)
    except Exception:
        if server_fail_mode == "closed":
            return EnforceResult(
                exit_code=2,
                message="Calx: Server unreachable and server_fail_mode=closed.",
            )
        return EnforceResult(exit_code=0)


def main() -> None:
    """Enforcement hook entry point."""
    try:
        calx_dir = find_calx_dir()
        if not calx_dir:
            sys.exit(0)

        state_dir = calx_dir / "state"

        # Try to get server URL for HTTP fallback
        from calx.serve.hooks._common import get_server_url
        server_url = get_server_url(calx_dir)

        # Read server_fail_mode from calx.json
        sfm = "open"
        config_file = calx_dir / "calx.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    cfg = json.load(f)
                sfm = cfg.get("enforcement", {}).get("server_fail_mode", "open")
            except (json.JSONDecodeError, OSError):
                pass

        result = run_enforce(state_dir, server_url, server_fail_mode=sfm)

        if result.warning:
            print(result.warning, file=sys.stderr)

        if result.exit_code == 2:
            print(result.message)

        sys.exit(result.exit_code)

    except Exception as e:
        log_hook_error(f"enforce: {e}")
        sys.exit(0)  # fail open on errors


if __name__ == "__main__":
    main()
