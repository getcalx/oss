"""Tests for end_session MCP tool."""
from __future__ import annotations

from pathlib import Path

import pytest

from calx.serve.db.engine import SessionRow
from calx.serve.engine.state_writer import write_session_state, write_active_session


class TestEndSession:

    @pytest.mark.asyncio
    async def test_end_session(self, db):
        from calx.serve.tools.end_session import handle_end_session

        await db.insert_session(SessionRow(
            id="sess1", surface="claude-code", surface_type="claude-code",
            soft_cap=200000, ceiling=250000, started_at="2026-03-31T17:00:00Z",
        ))
        result = await handle_end_session(db, session_id="sess1")
        assert result["status"] == "ok"

        session = await db.get_session("sess1")
        assert session.ended_at is not None

    @pytest.mark.asyncio
    async def test_end_session_not_found(self, db):
        from calx.serve.tools.end_session import handle_end_session

        result = await handle_end_session(db, session_id="nope")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_end_session_writes_handoff(self, db):
        from calx.serve.tools.end_session import handle_end_session

        await db.insert_session(SessionRow(
            id="sess1", surface="claude-code", surface_type="claude-code",
            soft_cap=200000, ceiling=250000, started_at="2026-03-31T17:00:00Z",
        ))
        result = await handle_end_session(
            db, session_id="sess1",
            what_changed="Added auth module",
            next_priorities="Build login flow",
        )
        assert result["status"] == "ok"

        handoff = await db.get_latest_handoff(session_id="sess1")
        assert handoff is not None
        assert handoff.what_changed == "Added auth module"

    @pytest.mark.asyncio
    async def test_end_session_removes_state_files(self, db, tmp_path):
        from calx.serve.tools.end_session import handle_end_session

        state_dir = tmp_path / ".calx" / "state"
        state_dir.mkdir(parents=True)

        await db.insert_session(SessionRow(
            id="sess1", surface="claude-code", surface_type="claude-code",
            soft_cap=200000, ceiling=250000, started_at="2026-03-31T17:00:00Z",
        ))
        # Create state files that should be cleaned up
        write_session_state(
            state_dir=state_dir, session_id="sess1", surface="claude-code",
            oriented=True, token_estimate=0, tool_call_count=0,
            soft_cap=200000, ceiling=250000, server_fail_mode="open",
            collapse_fail_mode="closed", started_at="2026-03-31T17:00:00Z",
            rules=[],
        )
        write_active_session(state_dir, "sess1")

        result = await handle_end_session(db, session_id="sess1", state_dir=state_dir)
        assert result["status"] == "ok"
        assert not (state_dir / "session-sess1.json").exists()
        assert not (state_dir / "active-session").exists()

    @pytest.mark.asyncio
    async def test_end_session_writes_clean_exit_marker(self, db, tmp_path):
        from calx.serve.tools.end_session import handle_end_session

        state_dir = tmp_path / ".calx" / "state"
        state_dir.mkdir(parents=True)

        await db.insert_session(SessionRow(
            id="sess1", surface="claude-code", surface_type="claude-code",
            soft_cap=200000, ceiling=250000, started_at="2026-03-31T17:00:00Z",
        ))
        result = await handle_end_session(db, session_id="sess1", state_dir=state_dir)
        assert (state_dir / "clean-exit-sess1").exists()

    @pytest.mark.asyncio
    async def test_end_session_returns_corrections_count(self, db):
        from calx.serve.tools.end_session import handle_end_session
        from calx.serve.db.engine import CorrectionRow

        await db.insert_session(SessionRow(
            id="sess1", surface="claude-code", surface_type="claude-code",
            soft_cap=200000, ceiling=250000, started_at="2026-03-31T17:00:00Z",
        ))
        # Log a correction during the session
        await db.insert_correction(CorrectionRow(
            id="C100", uuid="es-u1", correction="Test",
            domain="general", category="structural",
            created_at="2026-03-31T17:30:00Z",
        ))
        result = await handle_end_session(db, session_id="sess1")
        assert result["corrections_logged"] >= 1

    @pytest.mark.asyncio
    async def test_end_session_includes_health_summary(self, db):
        from calx.serve.tools.end_session import handle_end_session

        await db.insert_session(SessionRow(
            id="health-sess", surface="reid", surface_type="reid",
            soft_cap=200000, ceiling=250000, started_at="2026-03-31T17:00:00Z",
        ))
        result = await handle_end_session(db, session_id="health-sess")
        assert "health_summary" in result
        assert "rules_scored" in result["health_summary"]
