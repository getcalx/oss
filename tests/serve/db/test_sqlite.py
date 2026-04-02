"""Tests for SQLite database engine CRUD operations."""

from unittest.mock import patch

import pytest

from tests.serve.conftest import make_correction, make_rule

# ---------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_get_correction(db):
    c = make_correction(id="C001", uuid="round-trip-1")
    await db.insert_correction(c)
    result = await db.get_correction("C001")
    assert result is not None
    assert result.id == "C001"
    assert result.uuid == "round-trip-1"
    assert result.correction == c.correction
    assert result.domain == "general"


@pytest.mark.asyncio
async def test_correction_exists_by_uuid(db):
    c = make_correction(id="C001", uuid="exists-check")
    await db.insert_correction(c)
    assert await db.correction_exists("exists-check") is True
    assert await db.correction_exists("nonexistent") is False


@pytest.mark.asyncio
async def test_find_corrections_by_domain(db):
    await db.insert_correction(make_correction(id="C001", uuid="u1", domain="api"))
    await db.insert_correction(make_correction(id="C002", uuid="u2", domain="api"))
    await db.insert_correction(make_correction(id="C003", uuid="u3", domain="general"))

    api_corrections = await db.find_corrections(domain="api")
    assert len(api_corrections) == 2
    assert all(c.domain == "api" for c in api_corrections)


@pytest.mark.asyncio
async def test_find_corrections_excludes_quarantined(db):
    await db.insert_correction(make_correction(id="C001", uuid="u1"))
    await db.insert_correction(make_correction(
        id="C002", uuid="u2", quarantined=1, quarantine_reason="test"))

    results = await db.find_corrections()
    assert len(results) == 1
    assert results[0].id == "C001"


@pytest.mark.asyncio
async def test_update_correction_recurrence_count(db):
    await db.insert_correction(make_correction(id="C001", uuid="u1"))
    await db.update_correction("C001", recurrence_count=4)
    result = await db.get_correction("C001")
    assert result.recurrence_count == 4


@pytest.mark.asyncio
async def test_find_corrections_respects_limit(db):
    for i in range(10):
        await db.insert_correction(make_correction(id=f"C{i:03d}", uuid=f"u{i}"))
    results = await db.find_corrections(limit=3)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_get_rule(db):
    r = make_rule(id="api-R001", domain="api", surface="reid")
    await db.insert_rule(r)
    result = await db.get_rule("api-R001")
    assert result is not None
    assert result.id == "api-R001"
    assert result.surface == "reid"
    assert result.domain == "api"


@pytest.mark.asyncio
async def test_rule_exists(db):
    await db.insert_rule(make_rule(id="test-R001"))
    assert await db.rule_exists("test-R001") is True
    assert await db.rule_exists("test-R999") is False


@pytest.mark.asyncio
async def test_find_rules_by_domain(db):
    await db.insert_rule(make_rule(id="api-R001", domain="api"))
    await db.insert_rule(make_rule(id="api-R002", domain="api"))
    await db.insert_rule(make_rule(id="gen-R001", domain="general"))

    api_rules = await db.find_rules(domain="api")
    assert len(api_rules) == 2


@pytest.mark.asyncio
async def test_find_rules_active_only(db):
    await db.insert_rule(make_rule(id="test-R001", active=1))
    await db.insert_rule(make_rule(id="test-R002", domain="general", active=0))

    active = await db.find_rules(active_only=True)
    assert len(active) == 1
    assert active[0].id == "test-R001"


@pytest.mark.asyncio
async def test_next_rule_id(db):
    await db.insert_rule(make_rule(id="api-R001", domain="api"))
    await db.insert_rule(make_rule(id="api-R002", domain="api"))

    next_id = await db.next_rule_id("api")
    assert next_id == "api-R003"


@pytest.mark.asyncio
async def test_next_rule_id_fresh_domain(db):
    next_id = await db.next_rule_id("brand_new")
    assert next_id == "brand_new-R001"


@pytest.mark.asyncio
async def test_update_rule(db):
    await db.insert_rule(make_rule(id="test-R001"))
    await db.update_rule("test-R001", active=0)
    result = await db.get_rule("test-R001")
    assert result.active == 0


# ---------------------------------------------------------------------------
# Metrics (founder-specific)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_get_metric(db):
    metric_id = await db.insert_metric("pypi_downloads", 627.0, source="pypistats")
    assert metric_id > 0

    metrics = await db.get_latest_metrics(name="pypi_downloads")
    assert len(metrics) == 1
    assert metrics[0].value == 627.0


@pytest.mark.asyncio
async def test_get_latest_metrics_returns_most_recent(db):
    await db.insert_metric("pypi_downloads", 500.0)
    await db.insert_metric("pypi_downloads", 627.0)

    metrics = await db.get_latest_metrics(name="pypi_downloads")
    assert len(metrics) == 1
    assert metrics[0].value == 627.0


# ---------------------------------------------------------------------------
# Pipeline (founder-specific)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_pipeline_create(db):
    await db.upsert_pipeline("Precursor", status="strong yes", gate="Wire SAFE")
    results = await db.get_pipeline(investor="Precursor")
    assert len(results) == 1
    assert results[0].status == "strong yes"


@pytest.mark.asyncio
async def test_upsert_pipeline_update(db):
    await db.upsert_pipeline("Precursor", status="strong yes")
    await db.upsert_pipeline("Precursor", status="closed", notes="Wired")
    results = await db.get_pipeline(investor="Precursor")
    assert results[0].status == "closed"
    assert results[0].notes == "Wired"


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_decision(db):
    decision_id = await db.insert_decision("Use SQLite as default backend", surface="reid")
    assert decision_id > 0

    decisions = await db.get_decisions()
    assert len(decisions) == 1
    assert decisions[0].decision == "Use SQLite as default backend"


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_and_get_context(db):
    await db.set_context("sophylabs_call", "Friday March 28", category="deadline")
    items = await db.get_context()
    assert len(items) == 1
    assert items[0].key == "sophylabs_call"
    assert items[0].category == "deadline"


@pytest.mark.asyncio
async def test_set_context_upserts(db):
    await db.set_context("status", "planning")
    await db.set_context("status", "building")
    items = await db.get_context()
    assert len(items) == 1
    assert items[0].value == "building"


@pytest.mark.asyncio
async def test_get_context_by_category(db):
    await db.set_context("call", "Friday", category="deadline")
    await db.set_context("nomotic", "Trademarked BCP", category="competitive")

    deadlines = await db.get_context(category="deadline")
    assert len(deadlines) == 1
    assert deadlines[0].key == "call"


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_telemetry(db):
    await db.log_telemetry(
        event_type="tool_call",
        tool_or_resource="log_correction",
        surface="reid",
        response_status="ok",
        latency_ms=12.5,
    )
    # Telemetry is fire-and-forget; just verify no error raised


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_schema_version(db):
    version = await db.get_schema_version()
    assert version >= 1


# ---------------------------------------------------------------------------
# PRAGMA busy_timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_busy_timeout_pragma_set(db):
    """PRAGMA busy_timeout should be set to handle database locking."""
    row = await db._fetchone("PRAGMA busy_timeout")
    assert row[0] == 5000




# ---------------------------------------------------------------------------
# find_corrections_by_keywords
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_corrections_by_keywords(db):
    await db.insert_correction(make_correction(
        id="C001", uuid="u1", domain="general",
        correction="Don't mock the database in tests",
        keywords='["database", "mock", "tests"]',
    ))
    await db.insert_correction(make_correction(
        id="C002", uuid="u2", domain="general",
        correction="Use Crimson Pro for headlines",
        keywords='["crimson", "headlines"]',
    ))

    results = await db.find_corrections_by_keywords(
        keywords=["database", "mock"], domain="general",
    )
    assert len(results) == 1
    assert results[0].id == "C001"


@pytest.mark.asyncio
async def test_find_corrections_by_keywords_empty_returns_empty(db):
    await db.insert_correction(make_correction(id="C001", uuid="u1"))
    results = await db.find_corrections_by_keywords(keywords=[], domain=None)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_find_corrections_by_keywords_excludes_quarantined(db):
    await db.insert_correction(make_correction(
        id="C001", uuid="u1", domain="general",
        keywords='["database"]', quarantined=1, quarantine_reason="test",
    ))
    results = await db.find_corrections_by_keywords(
        keywords=["database"], domain="general",
    )
    assert len(results) == 0
