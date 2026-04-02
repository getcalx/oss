"""Tests for the session bootstrap engine."""
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from calx.serve.db.engine import HandoffRow, SessionRow
from calx.serve.engine.bootstrap import bootstrap_session


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hours_ago(hours: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_with_handoff(db):
    """DB with a recent handoff (within 24 hours)."""
    session_id = str(_uuid.uuid4())
    session = SessionRow(
        id=session_id,
        surface="thane",
        surface_type="cli",
        oriented=1,
        started_at=_hours_ago(2),
        ended_at=_hours_ago(1),
    )
    await db.insert_session(session)
    handoff = HandoffRow(
        session_id=session_id,
        what_changed="Built the bootstrap engine",
        what_others_need="Review the new tests",
        decisions_deferred=None,
        next_priorities="Chunk 1E",
        created_at=_hours_ago(1),
    )
    await db.insert_handoff(handoff)
    return db


@pytest_asyncio.fixture
async def db_with_dirty_session(db):
    """DB with an active session (ended_at=None) -- simulates dirty exit."""
    session_id = str(_uuid.uuid4())
    session = SessionRow(
        id=session_id,
        surface="thane",
        surface_type="cli",
        oriented=1,
        started_at=_hours_ago(3),
        ended_at=None,
    )
    await db.insert_session(session)
    return db


@pytest_asyncio.fixture
async def db_with_ended_session(db):
    """DB with a properly ended session."""
    session_id = str(_uuid.uuid4())
    session = SessionRow(
        id=session_id,
        surface="thane",
        surface_type="cli",
        oriented=1,
        started_at=_hours_ago(3),
        ended_at=_hours_ago(1),
    )
    await db.insert_session(session)
    return db


@pytest_asyncio.fixture
async def db_with_stale_handoff(db):
    """DB with a handoff created 48 hours ago."""
    session_id = str(_uuid.uuid4())
    session = SessionRow(
        id=session_id,
        surface="thane",
        surface_type="cli",
        oriented=1,
        started_at=_hours_ago(50),
        ended_at=_hours_ago(48),
    )
    await db.insert_session(session)
    handoff = HandoffRow(
        session_id=session_id,
        what_changed="Old work from 48 hours ago",
        what_others_need=None,
        decisions_deferred=None,
        next_priorities=None,
        created_at=_hours_ago(48),
    )
    await db.insert_handoff(handoff)
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_prior_session(db):
    """Fresh DB: no handoff, no dirty exit, no staleness."""
    result = await bootstrap_session(db)
    assert result.last_handoff is None
    assert result.dirty_exit is False
    assert result.staleness_warning is None


@pytest.mark.asyncio
async def test_with_handoff(db_with_handoff):
    """DB with recent handoff: handoff returned, no staleness."""
    result = await bootstrap_session(db_with_handoff)
    assert result.last_handoff is not None
    assert result.last_handoff.what_changed != ""
    assert result.staleness_warning is None


@pytest.mark.asyncio
async def test_dirty_exit_detected(db_with_dirty_session, tmp_path):
    """Session with no ended_at and no clean-exit marker -> dirty."""
    result = await bootstrap_session(db_with_dirty_session, state_dir=tmp_path)
    assert result.dirty_exit is True
    assert result.dirty_session_id is not None


@pytest.mark.asyncio
async def test_clean_exit_not_dirty(db_with_ended_session, tmp_path):
    """Session with ended_at -> not dirty even without marker."""
    result = await bootstrap_session(db_with_ended_session, state_dir=tmp_path)
    assert result.dirty_exit is False


@pytest.mark.asyncio
async def test_stale_handoff_warning(db_with_stale_handoff):
    """Handoff older than threshold -> staleness warning."""
    result = await bootstrap_session(db_with_stale_handoff, staleness_hours=24)
    assert result.staleness_warning is not None
