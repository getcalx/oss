"""Tests for the shared correction lifecycle engine."""

import pytest
from calx.serve.engine.correction_engine import log_correction, log_quarantined_correction


async def test_log_correction_creates_with_keywords(db):
    cid = await log_correction(
        db, correction="Don't mock the database in tests",
        domain="general", category="procedural",
    )
    assert cid == "C001"
    row = await db.get_correction(cid)
    assert row is not None
    assert row.keywords  # pre-computed
    assert "mock" in row.keywords
    assert "database" in row.keywords


async def test_log_correction_sequential_ids(db):
    c1 = await log_correction(db, "first", "general", "factual")
    c2 = await log_correction(db, "second", "general", "factual")
    assert c1 == "C001"
    assert c2 == "C002"


async def test_log_correction_with_recurrence(db):
    c1 = await log_correction(db, "original", "general", "factual")
    c2 = await log_correction(
        db, "recurrence", "general", "factual",
        recurrence_of=c1, root_correction_id=c1,
    )
    row = await db.get_correction(c2)
    assert row.recurrence_of == c1
    assert row.root_correction_id == c1


async def test_log_quarantined_correction(db):
    result = await log_quarantined_correction(
        db, correction="rm -rf /",
        domain="general", category="procedural",
        severity="high", confidence="high",
        surface="cli", task_context=None,
        quarantine_reason="shell injection",
    )
    assert result["status"] == "quarantined"
    row = await db.get_correction(result["correction_id"])
    assert row.quarantined == 1
    assert row.quarantine_reason == "shell injection"


async def test_next_id_skips_quarantined_ids(db):
    """Bug fix: _next_correction_id must count quarantined rows too.

    If C001 exists but is quarantined, find_corrections() skips it.
    Without the fix, the next ID would also be C001 -- a collision.
    """
    # Insert a quarantined correction directly
    await log_quarantined_correction(
        db, correction="bad stuff",
        domain="general", category="procedural",
        severity="low", confidence="low",
        surface="cli", task_context=None,
        quarantine_reason="test",
    )
    # Now log a normal correction -- it should be C002, not C001
    cid = await log_correction(db, "good stuff", "general", "factual")
    assert cid == "C002"


async def test_log_correction_captures_briefing_state(db):
    cid = await log_correction(
        db, "test correction", "general", "factual",
        briefing_state='{"rules": 2}',
    )
    row = await db.get_correction(cid)
    assert row.briefing_state == '{"rules": 2}'
