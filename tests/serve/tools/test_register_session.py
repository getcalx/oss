"""Tests for register_session MCP tool."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestRegisterSession:

    @pytest.mark.asyncio
    async def test_register_session(self, db):
        from calx.serve.tools.register_session import handle_register_session

        result = await handle_register_session(db, surface="claude-code")
        assert result["status"] == "ok"
        assert "session_id" in result
        assert "briefing" in result

    @pytest.mark.asyncio
    async def test_register_session_with_id(self, db):
        from calx.serve.tools.register_session import handle_register_session

        result = await handle_register_session(
            db, surface="claude-code", session_id="my-sess",
        )
        assert result["session_id"] == "my-sess"

    @pytest.mark.asyncio
    async def test_register_session_ends_previous(self, db):
        from calx.serve.tools.register_session import handle_register_session

        r1 = await handle_register_session(db, surface="claude-code", session_id="s1")
        r2 = await handle_register_session(db, surface="claude-code", session_id="s2")

        s1 = await db.get_session("s1")
        assert s1.ended_at is not None
        s2 = await db.get_session("s2")
        assert s2.ended_at is None

    @pytest.mark.asyncio
    async def test_register_session_writes_state_file(self, db, tmp_path):
        from calx.serve.tools.register_session import handle_register_session

        state_dir = tmp_path / ".calx" / "state"
        state_dir.mkdir(parents=True)

        result = await handle_register_session(
            db, surface="claude-code", session_id="sf-sess",
            state_dir=state_dir,
        )
        assert result["status"] == "ok"
        assert result.get("state_file") is not None

        # State file should exist
        state_file = state_dir / "session-sf-sess.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["session_id"] == "sf-sess"
        assert data["oriented"] is False

    @pytest.mark.asyncio
    async def test_register_session_writes_active_session(self, db, tmp_path):
        from calx.serve.tools.register_session import handle_register_session

        state_dir = tmp_path / ".calx" / "state"
        state_dir.mkdir(parents=True)

        await handle_register_session(
            db, surface="claude-code", session_id="as-sess",
            state_dir=state_dir,
        )
        active_file = state_dir / "active-session"
        assert active_file.exists()
        assert active_file.read_text().strip() == "as-sess"

    @pytest.mark.asyncio
    async def test_register_session_includes_bootstrap(self, db):
        from calx.serve.tools.register_session import handle_register_session

        result = await handle_register_session(db, surface="reid")
        assert "bootstrap" in result
        assert result["bootstrap"]["dirty_exit"] is False

    @pytest.mark.asyncio
    async def test_register_session_with_prior_handoff(self, db):
        from calx.serve.tools.register_session import handle_register_session
        from calx.serve.db.engine import SessionRow, HandoffRow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        await db.insert_session(SessionRow(
            id="old-sess", surface="reid", surface_type="reid",
            started_at=now, ended_at=now,
        ))
        await db.insert_handoff(HandoffRow(
            session_id="old-sess", what_changed="Built engines",
            created_at=now,
        ))
        result = await handle_register_session(db, surface="reid")
        assert result["bootstrap"]["handoff"] is not None
        assert result["bootstrap"]["handoff"]["what_changed"] == "Built engines"
