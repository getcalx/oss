"""Tests for health-based rule auto-deactivation."""

import pytest

from tests.serve.conftest import make_rule


@pytest.mark.asyncio
async def test_critical_health_deactivates_rule(db):
    """Rules with health_score below 0.3 are auto-deactivated."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(
        id="general-R001", health_score=0.1,
    ))

    results = await auto_deactivate_unhealthy_rules(db)

    assert len(results) == 1
    assert results[0]["action"] == "deactivated"
    assert results[0]["rule_id"] == "general-R001"
    assert results[0]["health_score"] == 0.1

    # Verify the rule was actually deactivated in DB
    rule = await db.get_rule("general-R001")
    assert rule.active == 0


@pytest.mark.asyncio
async def test_warning_health_flags_but_keeps_active(db):
    """Rules with health_score between 0.3 and 0.5 get warned but stay active."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(
        id="general-R001", health_score=0.4,
    ))

    results = await auto_deactivate_unhealthy_rules(db)

    assert len(results) == 1
    assert results[0]["action"] == "warning"
    assert results[0]["rule_id"] == "general-R001"

    # Verify rule is still active
    rule = await db.get_rule("general-R001")
    assert rule.active == 1


@pytest.mark.asyncio
async def test_healthy_rule_untouched(db):
    """Rules with health_score >= 0.5 are not flagged or deactivated."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(
        id="general-R001", health_score=0.8,
    ))

    results = await auto_deactivate_unhealthy_rules(db)

    assert len(results) == 0

    # Rule stays active
    rule = await db.get_rule("general-R001")
    assert rule.active == 1


@pytest.mark.asyncio
async def test_default_health_score_untouched(db):
    """Rules with default health_score (1.0) are not flagged."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(
        id="general-R001",
    ))

    results = await auto_deactivate_unhealthy_rules(db)

    assert len(results) == 0

    rule = await db.get_rule("general-R001")
    assert rule.active == 1


@pytest.mark.asyncio
async def test_mixed_health_scores(db):
    """Multiple rules with different health scores are handled correctly."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(id="general-R001", health_score=0.1))
    await db.insert_rule(make_rule(id="general-R002", rule_text="r2", health_score=0.4))
    await db.insert_rule(make_rule(id="general-R003", rule_text="r3", health_score=0.9))
    await db.insert_rule(make_rule(id="general-R004", rule_text="r4", health_score=1.0))

    results = await auto_deactivate_unhealthy_rules(db)

    # Deactivated first, then warnings
    assert len(results) == 2
    assert results[0]["action"] == "deactivated"
    assert results[0]["rule_id"] == "general-R001"
    assert results[1]["action"] == "warning"
    assert results[1]["rule_id"] == "general-R002"

    # Verify DB state
    r1 = await db.get_rule("general-R001")
    assert r1.active == 0
    r2 = await db.get_rule("general-R002")
    assert r2.active == 1
    r3 = await db.get_rule("general-R003")
    assert r3.active == 1
    r4 = await db.get_rule("general-R004")
    assert r4.active == 1


@pytest.mark.asyncio
async def test_already_inactive_rules_not_processed(db):
    """Inactive rules are not fetched (active_only=True), so they don't get double-processed."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(
        id="general-R001", health_score=0.1, active=0,
    ))

    results = await auto_deactivate_unhealthy_rules(db)

    # Rule was already inactive, find_rules(active_only=True) won't return it
    assert len(results) == 0


@pytest.mark.asyncio
async def test_boundary_at_critical_threshold(db):
    """Rule exactly at 0.3 is NOT deactivated (< not <=)."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(
        id="general-R001", health_score=0.3,
    ))

    results = await auto_deactivate_unhealthy_rules(db)

    assert len(results) == 1
    assert results[0]["action"] == "warning"

    rule = await db.get_rule("general-R001")
    assert rule.active == 1


@pytest.mark.asyncio
async def test_boundary_at_warning_threshold(db):
    """Rule exactly at 0.5 is NOT warned (< not <=)."""
    from calx.serve.engine.health import auto_deactivate_unhealthy_rules

    await db.insert_rule(make_rule(
        id="general-R001", health_score=0.5,
    ))

    results = await auto_deactivate_unhealthy_rules(db)

    assert len(results) == 0
