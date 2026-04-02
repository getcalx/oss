"""Tests for record_foil_review MCP tool."""
from __future__ import annotations

import pytest

from calx.serve.db.engine import SessionRow


@pytest.mark.asyncio
async def test_record_review(db):
    from calx.serve.tools.record_foil_review import handle_record_foil_review

    result = await handle_record_foil_review(
        db, spec_reference="src/server.py", reviewer_domain="backend",
        verdict="revise", findings="Missing FK pragma", round=1,
    )
    assert result["status"] == "ok"
    assert "review_id" in result
    reviews = await db.get_foil_reviews()
    assert len(reviews) == 1
    assert reviews[0].verdict == "revise"


@pytest.mark.asyncio
async def test_record_review_links_session(db):
    from calx.serve.tools.record_foil_review import handle_record_foil_review

    await db.insert_session(SessionRow(
        id="active-sess", surface="reid", surface_type="reid",
        started_at="2026-03-31T10:00:00Z",
    ))
    result = await handle_record_foil_review(
        db, spec_reference="spec.md", reviewer_domain="spec",
        verdict="approve",
    )
    assert result["status"] == "ok"
    reviews = await db.get_foil_reviews()
    assert reviews[0].session_id == "active-sess"


@pytest.mark.asyncio
async def test_review_gaps(db):
    from calx.serve.tools.record_foil_review import get_review_gaps
    from calx.serve.db.engine import CorrectionRow

    # Insert 6 corrections in "general" domain (> 5 threshold)
    for i in range(6):
        await db.insert_correction(CorrectionRow(
            id=f"C{i:03d}", uuid=f"gap-{i}",
            correction=f"Correction {i}", domain="general",
            category="procedural", created_at="2026-03-01T10:00:00Z",
        ))
    gaps = await get_review_gaps(db)
    assert len(gaps) > 0
    assert gaps[0]["correction_count"] >= 6
