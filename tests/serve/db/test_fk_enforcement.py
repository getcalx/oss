"""Tests for foreign key enforcement (PRAGMA foreign_keys=ON)."""
from __future__ import annotations

import sqlite3

import pytest

from calx.serve.db.engine import HandoffRow


class TestForeignKeyEnforcement:

    @pytest.mark.asyncio
    async def test_handoff_with_invalid_session_id_raises(self, db):
        """Inserting a handoff with non-existent session_id should raise."""
        h = HandoffRow(
            session_id="nonexistent_session",
            what_changed="Test",
            created_at="2026-03-31T17:00:00Z",
        )
        with pytest.raises(Exception):
            await db.insert_handoff(h)
