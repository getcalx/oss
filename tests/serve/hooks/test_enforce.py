"""Tests for the enforcement hook (merged orientation + collapse guard)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from calx.serve.hooks.enforce import (
    run_enforce,
    EnforceResult,
)


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".calx" / "state"
    d.mkdir(parents=True)
    return d


def _write_state(state_dir: Path, session_id: str, **overrides):
    data = {
        "session_id": session_id,
        "surface": "claude-code",
        "oriented": True,
        "token_estimate": 0,
        "tool_call_count": 0,
        "soft_cap": 200000,
        "ceiling": 250000,
        "server_fail_mode": "open",
        "collapse_fail_mode": "closed",
        "started_at": "2026-03-31T17:00:00Z",
        "rules": [],
    }
    data.update(overrides)
    (state_dir / f"session-{session_id}.json").write_text(json.dumps(data))
    (state_dir / "active-session").write_text(session_id)


class TestEnforceOrientation:

    def test_blocks_when_not_oriented(self, state_dir):
        _write_state(state_dir, "sess1", oriented=False)
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 2
        assert "rules" in result.message.lower() or "calx" in result.message.lower()

    def test_allows_when_oriented(self, state_dir):
        _write_state(state_dir, "sess1", oriented=True)
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 0


class TestEnforceCollapse:

    def test_allows_under_soft_cap(self, state_dir):
        _write_state(state_dir, "sess1", oriented=True,
                     token_estimate=100000, tool_call_count=100)
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 0
        assert result.warning is None

    def test_warns_at_soft_cap(self, state_dir):
        _write_state(state_dir, "sess1", oriented=True,
                     token_estimate=200000, tool_call_count=200)
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 0
        assert result.warning is not None
        assert "approaching" in result.warning.lower() or "tool calls" in result.warning.lower()

    def test_blocks_at_ceiling_closed(self, state_dir):
        _write_state(state_dir, "sess1", oriented=True,
                     token_estimate=250000, tool_call_count=250,
                     collapse_fail_mode="closed")
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 2
        assert "ceiling" in result.message.lower()

    def test_warns_at_ceiling_open(self, state_dir):
        _write_state(state_dir, "sess1", oriented=True,
                     token_estimate=250000, tool_call_count=250,
                     collapse_fail_mode="open")
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 0
        assert result.warning is not None


class TestEnforceNoState:

    def test_no_active_session_file(self, state_dir):
        """No active-session file means no enforcement."""
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 0

    def test_missing_state_file(self, state_dir):
        """Active session but no state file."""
        (state_dir / "active-session").write_text("sess1")
        result = run_enforce(state_dir, server_url=None)
        # Should fall through (fail open by default)
        assert result.exit_code == 0


class TestEnforceIncrementToolCall:

    @patch("calx.serve.hooks.enforce._call_increment_tool_call")
    def test_calls_increment_when_oriented_and_server_available(self, mock_incr, state_dir):
        """When oriented and server_url is set, must call increment-tool-call."""
        _write_state(state_dir, "sess1", oriented=True)
        mock_incr.return_value = {"status": "ok", "tool_call_count": 1, "token_estimate": 1000, "action": "allow"}
        result = run_enforce(state_dir, server_url="http://127.0.0.1:4195")
        mock_incr.assert_called_once_with("http://127.0.0.1:4195", "sess1")
        assert result.exit_code == 0

    @patch("calx.serve.hooks.enforce._call_increment_tool_call")
    def test_increment_warn_action(self, mock_incr, state_dir):
        """Increment returns warn: exit 0 with warning."""
        _write_state(state_dir, "sess1", oriented=True)
        mock_incr.return_value = {"status": "ok", "tool_call_count": 200, "token_estimate": 200000, "action": "warn"}
        result = run_enforce(state_dir, server_url="http://127.0.0.1:4195")
        assert result.exit_code == 0
        assert result.warning is not None

    @patch("calx.serve.hooks.enforce._call_increment_tool_call")
    def test_increment_block_action_closed(self, mock_incr, state_dir):
        """Increment returns block + collapse_fail_mode=closed: exit 2."""
        _write_state(state_dir, "sess1", oriented=True, collapse_fail_mode="closed")
        mock_incr.return_value = {"status": "ok", "tool_call_count": 250, "token_estimate": 250000, "action": "block"}
        result = run_enforce(state_dir, server_url="http://127.0.0.1:4195")
        assert result.exit_code == 2
        assert "ceiling" in result.message.lower()

    @patch("calx.serve.hooks.enforce._call_increment_tool_call")
    def test_increment_block_action_open(self, mock_incr, state_dir):
        """Increment returns block + collapse_fail_mode=open: exit 0 with warning."""
        _write_state(state_dir, "sess1", oriented=True, collapse_fail_mode="open")
        mock_incr.return_value = {"status": "ok", "tool_call_count": 250, "token_estimate": 250000, "action": "block"}
        result = run_enforce(state_dir, server_url="http://127.0.0.1:4195")
        assert result.exit_code == 0
        assert result.warning is not None

    def test_no_increment_without_server_url(self, state_dir):
        """Without server_url, no increment call. Falls back to state file values."""
        _write_state(state_dir, "sess1", oriented=True)
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 0

    @patch("calx.serve.hooks.enforce._call_increment_tool_call")
    def test_increment_failure_falls_back_to_state(self, mock_incr, state_dir):
        """If increment call fails, fall back to state file values."""
        _write_state(state_dir, "sess1", oriented=True, token_estimate=0)
        mock_incr.return_value = None  # Connection failure
        result = run_enforce(state_dir, server_url="http://127.0.0.1:4195")
        assert result.exit_code == 0


class TestEnforceServerFailMode:

    def test_fail_open_when_no_server(self, state_dir):
        _write_state(state_dir, "sess1", oriented=True, server_fail_mode="open")
        # No server URL, should pass through
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 0

    def test_first_session_message(self, state_dir):
        """Zero rules, zero corrections: show calx correct message."""
        _write_state(state_dir, "sess1", oriented=False, rules=[])
        result = run_enforce(state_dir, server_url=None)
        assert result.exit_code == 2
        assert "calx correct" in result.message.lower() or "no rules" in result.message.lower()

    @patch("calx.serve.hooks.enforce._http_fallback")
    def test_http_fallback_respects_closed_mode(self, mock_fb, state_dir):
        """When state file missing + server unreachable + mode=closed: exit 2."""
        (state_dir / "active-session").write_text("sess1")
        # No state file exists, so it falls through to _http_fallback
        mock_fb.return_value = EnforceResult(exit_code=2, message="Server unreachable, fail closed.")
        result = run_enforce(state_dir, server_url="http://127.0.0.1:4195", server_fail_mode="closed")
        mock_fb.assert_called_once()
        assert result.exit_code == 2

    @patch("calx.serve.hooks.enforce._http_fallback")
    def test_http_fallback_fail_open_by_default(self, mock_fb, state_dir):
        """Default server_fail_mode=open: exit 0 on unreachable server."""
        (state_dir / "active-session").write_text("sess1")
        mock_fb.return_value = EnforceResult(exit_code=0)
        result = run_enforce(state_dir, server_url="http://127.0.0.1:4195")
        assert result.exit_code == 0
