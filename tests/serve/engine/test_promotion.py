"""Tests for progressive promotion with confidence tiers."""

import pytest

from tests.serve.conftest import make_correction


@pytest.mark.asyncio
async def test_high_confidence_auto_promotes(db):
    from calx.serve.engine.promotion import check_auto_promotion

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", confidence="high", recurrence_count=3,
    ))

    result = await check_auto_promotion(db, "C001")
    assert result.action == "auto_promoted"
    assert result.rule_id is not None

    # Verify rule was created
    rule = await db.get_rule(result.rule_id)
    assert rule is not None


@pytest.mark.asyncio
async def test_medium_confidence_queues_for_review(db):
    from calx.serve.engine.promotion import check_auto_promotion

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", confidence="medium", recurrence_count=3,
    ))

    result = await check_auto_promotion(db, "C001")
    assert result.action == "queued_for_review"


@pytest.mark.asyncio
async def test_low_confidence_never_auto_promotes(db):
    from calx.serve.engine.promotion import check_auto_promotion

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", confidence="low", recurrence_count=100,
    ))

    result = await check_auto_promotion(db, "C001")
    assert result.action == "never_auto_promote"


@pytest.mark.asyncio
async def test_uses_original_confidence_not_new(db):
    """The original correction's confidence determines promotion behavior,
    not the confidence of the new recurrence that triggered the check."""
    from calx.serve.engine.promotion import check_auto_promotion

    # Original correction has medium confidence
    await db.insert_correction(make_correction(
        id="C001", uuid="u1", confidence="medium", recurrence_count=3,
    ))

    # check_auto_promotion only takes correction_id, reads confidence from DB
    result = await check_auto_promotion(db, "C001")
    assert result.action == "queued_for_review"  # medium, not auto-promoted


@pytest.mark.asyncio
async def test_already_promoted_returns_none(db):
    from calx.serve.engine.promotion import check_auto_promotion

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", confidence="high", recurrence_count=5,
        promoted=1,
    ))

    result = await check_auto_promotion(db, "C001")
    assert result.action == "none"


@pytest.mark.asyncio
async def test_below_threshold_returns_none(db):
    from calx.serve.engine.promotion import check_auto_promotion

    await db.insert_correction(make_correction(
        id="C001", uuid="u1", confidence="high", recurrence_count=1,
    ))

    result = await check_auto_promotion(db, "C001")
    assert result.action == "none"
