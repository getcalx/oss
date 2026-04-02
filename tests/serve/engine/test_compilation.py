"""Tests for compilation verification engine (Chunk 1C)."""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from calx.serve.db.engine import CompilationEventRow, RuleRow
from calx.serve.engine.compilation import (
    VERIFICATION_PERIOD_DAYS,
    check_post_compilation_recurrence,
    check_verification_status,
    get_compilation_candidates,
    get_compilation_stats,
)
from tests.serve.conftest import make_correction, make_rule


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_ago_str(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_with_compiled_rule(db):
    """DB with a compiled (inactive) rule and a compilation event."""
    corr = make_correction(
        id="C001",
        uuid="comp-uuid-1",
        domain="general",
        correction="Don't use em dashes in documentation",
        recurrence_count=3,
    )
    await db.insert_correction(corr)

    rule = make_rule(
        id="general-R001",
        domain="general",
        rule_text="Don't use em dashes in documentation",
        active=0,
        health_status="compiled",
        source_correction_id="C001",
        learning_mode="process",
    )
    await db.insert_rule(rule)

    event = CompilationEventRow(
        rule_id="general-R001",
        source_correction_id="C001",
        rule_text="Don't use em dashes in documentation",
        learning_mode_before="process",
        mechanism_type="config_change",
        mechanism_description="Added linter rule for em dashes",
        recurrence_count_at_compilation=3,
        rule_age_days=10,
        correction_chain_length=1,
        post_compilation_recurrence=0,
        verified_at=None,
        created_at=_now_str(),
    )
    await db.insert_compilation_event(event)
    return db


@pytest_asyncio.fixture
async def db_with_old_compilation(db):
    """DB with a compiled rule whose verification period has elapsed, zero recurrence."""
    corr = make_correction(
        id="C001",
        uuid="comp-uuid-2",
        domain="general",
        correction="Don't use em dashes in documentation",
        recurrence_count=3,
    )
    await db.insert_correction(corr)

    rule = make_rule(
        id="general-R001",
        domain="general",
        rule_text="Don't use em dashes in documentation",
        active=0,
        health_status="compiled",
        source_correction_id="C001",
        learning_mode="process",
    )
    await db.insert_rule(rule)

    event = CompilationEventRow(
        rule_id="general-R001",
        source_correction_id="C001",
        rule_text="Don't use em dashes in documentation",
        learning_mode_before="process",
        mechanism_type="config_change",
        mechanism_description="Added linter rule for em dashes",
        recurrence_count_at_compilation=3,
        rule_age_days=10,
        correction_chain_length=1,
        post_compilation_recurrence=0,
        verified_at=None,
        created_at=_days_ago_str(VERIFICATION_PERIOD_DAYS + 1),
    )
    await db.insert_compilation_event(event)
    return db


@pytest_asyncio.fixture
async def db_with_failed_compilation(db):
    """DB with a compiled rule past verification period with recurrence > 0."""
    corr = make_correction(
        id="C001",
        uuid="comp-uuid-3",
        domain="general",
        correction="Don't use em dashes in documentation",
        recurrence_count=3,
    )
    await db.insert_correction(corr)

    rule = make_rule(
        id="general-R001",
        domain="general",
        rule_text="Don't use em dashes in documentation",
        active=0,
        health_status="compiled",
        source_correction_id="C001",
        learning_mode="process",
    )
    await db.insert_rule(rule)

    event = CompilationEventRow(
        rule_id="general-R001",
        source_correction_id="C001",
        rule_text="Don't use em dashes in documentation",
        learning_mode_before="process",
        mechanism_type="config_change",
        mechanism_description="Added linter rule for em dashes",
        recurrence_count_at_compilation=3,
        rule_age_days=10,
        correction_chain_length=1,
        post_compilation_recurrence=2,
        verified_at=None,
        created_at=_days_ago_str(VERIFICATION_PERIOD_DAYS + 1),
    )
    await db.insert_compilation_event(event)
    return db


# ---------------------------------------------------------------------------
# Tests: check_post_compilation_recurrence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_match_returns_empty(db):
    """Correction in different domain shouldn't match compiled rules."""
    result = await check_post_compilation_recurrence(db, "unrelated text", "other_domain")
    assert result == []


@pytest.mark.asyncio
async def test_match_increments_recurrence(db_with_compiled_rule):
    """Correction matching compiled rule's error class increments counter."""
    db = db_with_compiled_rule
    result = await check_post_compilation_recurrence(
        db, "don't use em dashes", "general",
    )
    assert len(result) == 1
    events = await db.get_compilation_events(rule_id=result[0].rule_id)
    assert events[0].post_compilation_recurrence == 1


# ---------------------------------------------------------------------------
# Tests: check_verification_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verification_confirmed(db_with_old_compilation):
    """Zero recurrence after verification period -> verified."""
    db = db_with_old_compilation
    now = datetime.now(timezone.utc)
    results = await check_verification_status(db, now=now)
    verified = [r for r in results if r.status == "verified"]
    assert len(verified) == 1
    assert verified[0].recurrence_count == 0
    events = await db.get_compilation_events(rule_id=verified[0].rule_id)
    assert events[0].verified_at is not None


@pytest.mark.asyncio
async def test_verification_failed_reactivates(db_with_failed_compilation):
    """Recurrence during verification -> rule reactivated."""
    db = db_with_failed_compilation
    results = await check_verification_status(db)
    failed = [r for r in results if r.status == "failed"]
    assert len(failed) == 1
    rule = await db.get_rule(failed[0].rule_id)
    assert rule.active == 1
    assert rule.health_status == "warning"


# ---------------------------------------------------------------------------
# Tests: get_compilation_candidates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compilation_candidates_returns_process_rules(db):
    """Active process rules with recurrent corrections are candidates."""
    corr = make_correction(
        id="C010", uuid="cand-uuid-1", domain="general",
        correction="Always run tests before committing",
        recurrence_count=4,
    )
    await db.insert_correction(corr)

    rule = make_rule(
        id="general-R010", domain="general",
        rule_text="Always run tests before committing",
        active=1, learning_mode="process",
        source_correction_id="C010",
    )
    await db.insert_rule(rule)

    candidates = await get_compilation_candidates(db)
    assert len(candidates) >= 1
    assert candidates[0].id == "general-R010"


@pytest.mark.asyncio
async def test_compilation_candidates_excludes_architectural(db):
    """Architectural rules should not appear as compilation candidates."""
    corr = make_correction(
        id="C011", uuid="cand-uuid-2", domain="general",
        correction="Use /v2/users endpoint",
        recurrence_count=5,
    )
    await db.insert_correction(corr)

    rule = make_rule(
        id="general-R011", domain="general",
        rule_text="Use /v2/users endpoint",
        active=1, learning_mode="architectural",
        source_correction_id="C011",
    )
    await db.insert_rule(rule)

    candidates = await get_compilation_candidates(db)
    arch_ids = [c.id for c in candidates]
    assert "general-R011" not in arch_ids


# ---------------------------------------------------------------------------
# Tests: get_compilation_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compilation_stats_empty_db(db):
    """Empty DB should return zeroed stats."""
    stats = await get_compilation_stats(db)
    assert stats["total_compilations"] == 0
    assert stats["verified"] == 0
    assert stats["in_verification"] == 0
    assert stats["failed"] == 0
    assert stats["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_compilation_stats_with_data(db_with_old_compilation):
    """Stats should reflect a single verified compilation after check runs."""
    db = db_with_old_compilation
    # Run verification first so verified_at gets set
    await check_verification_status(db)
    stats = await get_compilation_stats(db)
    assert stats["total_compilations"] == 1
    assert stats["verified"] == 1
    assert stats["success_rate"] == 1.0
