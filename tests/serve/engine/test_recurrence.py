"""Tests for recurrence detection."""

import pytest
from tests.serve.conftest import make_correction


@pytest.mark.asyncio
async def test_matching_correction_returns_match(db):
    from calx.serve.engine.recurrence import check_recurrence

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", domain="general",
        correction="Don't mock the database in integration tests",
        keywords='["database", "integration", "mock", "tests"]',
    ))

    result = await check_recurrence(
        db, "Don't mock the database in integration tests", "general"
    )
    assert result.is_match is True
    assert result.original_id == "C001"
    assert result.new_count == 2


@pytest.mark.asyncio
async def test_non_matching_correction_returns_no_match(db):
    from calx.serve.engine.recurrence import check_recurrence

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", domain="general",
        correction="Don't mock the database in integration tests",
        keywords='["database", "integration", "mock", "tests"]',
    ))

    result = await check_recurrence(
        db, "Use Crimson Pro for headlines", "general"
    )
    assert result.is_match is False


@pytest.mark.asyncio
async def test_uses_precomputed_keywords(db):
    from calx.serve.engine.recurrence import check_recurrence

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", domain="general",
        correction="some text that would normally not match",
        keywords='["database", "integration", "mock", "tests"]',
    ))

    result = await check_recurrence(
        db, "Don't mock the database in integration tests", "general"
    )
    # Should match against pre-computed keywords, not the correction text
    assert result.is_match is True


@pytest.mark.asyncio
async def test_returns_root_correction_id(db):
    from calx.serve.engine.recurrence import check_recurrence

    # Root correction
    await db.insert_correction(make_correction(
        id="C001", uuid="u1", domain="general",
        correction="Don't mock the database",
        keywords='["database", "mock"]',
        recurrence_count=2,
    ))
    # Child correction pointing to root (shares enough keywords to match)
    await db.insert_correction(make_correction(
        id="C002", uuid="u2", domain="general",
        correction="Don't mock the database in tests",
        keywords='["database", "mock", "tests"]',
        recurrence_of="C001",
        root_correction_id="C001",
    ))

    result = await check_recurrence(
        db, "Don't mock the database in integration tests", "general"
    )
    assert result.is_match is True
    assert result.original_id == "C001"  # Returns root, not C002


@pytest.mark.asyncio
async def test_different_domain_no_match(db):
    from calx.serve.engine.recurrence import check_recurrence

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", domain="api",
        correction="Don't mock the database in integration tests",
        keywords='["database", "integration", "mock", "tests"]',
    ))

    result = await check_recurrence(
        db, "Don't mock the database in integration tests", "frontend"
    )
    assert result.is_match is False
