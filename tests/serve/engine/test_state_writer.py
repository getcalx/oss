"""Tests for state file writer (atomic writes to .calx/state/)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from calx.serve.engine.state_writer import (
    write_session_state,
    write_active_session,
    remove_session_state,
    read_session_state,
)


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """Temporary .calx/state/ directory."""
    d = tmp_path / ".calx" / "state"
    d.mkdir(parents=True)
    return d


class TestWriteSessionState:

    def test_writes_state_file(self, state_dir):
        write_session_state(
            state_dir=state_dir,
            session_id="sess1",
            surface="claude-code",
            oriented=False,
            token_estimate=0,
            tool_call_count=0,
            soft_cap=200000,
            ceiling=250000,
            server_fail_mode="open",
            collapse_fail_mode="closed",
            started_at="2026-03-31T17:00:00Z",
            rules=[{"id": "general-R001", "text": "Use real DB"}],
        )
        state_file = state_dir / "session-sess1.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["session_id"] == "sess1"
        assert data["surface"] == "claude-code"
        assert data["oriented"] is False
        assert data["tool_call_count"] == 0
        assert data["soft_cap"] == 200000
        assert data["collapse_fail_mode"] == "closed"
        assert len(data["rules"]) == 1

    def test_overwrites_existing(self, state_dir):
        for oriented in [False, True]:
            write_session_state(
                state_dir=state_dir,
                session_id="sess1",
                surface="claude-code",
                oriented=oriented,
                token_estimate=0,
                tool_call_count=0,
                soft_cap=200000,
                ceiling=250000,
                server_fail_mode="open",
                collapse_fail_mode="closed",
                started_at="2026-03-31T17:00:00Z",
                rules=[],
            )
        data = json.loads((state_dir / "session-sess1.json").read_text())
        assert data["oriented"] is True

    def test_atomic_write(self, state_dir):
        """State file should not have temp files left behind."""
        write_session_state(
            state_dir=state_dir,
            session_id="sess1",
            surface="claude-code",
            oriented=False,
            token_estimate=0,
            tool_call_count=0,
            soft_cap=200000,
            ceiling=250000,
            server_fail_mode="open",
            collapse_fail_mode="closed",
            started_at="2026-03-31T17:00:00Z",
            rules=[],
        )
        # No temp files should remain
        files = list(state_dir.iterdir())
        assert all(not f.name.startswith(".tmp") for f in files)


class TestWriteActiveSession:

    def test_writes_active_session_file(self, state_dir):
        write_active_session(state_dir, "sess1")
        active_file = state_dir / "active-session"
        assert active_file.exists()
        assert active_file.read_text().strip() == "sess1"


class TestRemoveSessionState:

    def test_removes_state_and_active(self, state_dir):
        write_session_state(
            state_dir=state_dir,
            session_id="sess1",
            surface="claude-code",
            oriented=True,
            token_estimate=0,
            tool_call_count=0,
            soft_cap=200000,
            ceiling=250000,
            server_fail_mode="open",
            collapse_fail_mode="closed",
            started_at="2026-03-31T17:00:00Z",
            rules=[],
        )
        write_active_session(state_dir, "sess1")

        remove_session_state(state_dir, "sess1")
        assert not (state_dir / "session-sess1.json").exists()
        assert not (state_dir / "active-session").exists()

    def test_remove_nonexistent_is_noop(self, state_dir):
        remove_session_state(state_dir, "nonexistent")  # Should not raise


class TestReadSessionState:

    def test_reads_state_file(self, state_dir):
        write_session_state(
            state_dir=state_dir,
            session_id="sess1",
            surface="claude-code",
            oriented=True,
            token_estimate=5000,
            tool_call_count=5,
            soft_cap=200000,
            ceiling=250000,
            server_fail_mode="open",
            collapse_fail_mode="closed",
            started_at="2026-03-31T17:00:00Z",
            rules=[],
        )
        data = read_session_state(state_dir, "sess1")
        assert data is not None
        assert data["oriented"] is True
        assert data["tool_call_count"] == 5

    def test_returns_none_for_missing(self, state_dir):
        data = read_session_state(state_dir, "nonexistent")
        assert data is None
