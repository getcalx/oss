"""Tests for database schema creation and initialization."""

import pytest


@pytest.mark.asyncio
async def test_schema_creates_all_tables(db):
    """All 7 data tables + schema_version table exist after init."""
    expected_tables = {
        "corrections", "rules", "metrics", "pipeline",
        "decisions", "context", "telemetry", "schema_version",
    }
    rows = await db._fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {row[0] for row in rows}
    assert expected_tables.issubset(table_names)


@pytest.mark.asyncio
async def test_wal_mode_enabled(tmp_path):
    """WAL journal mode is set for concurrent reader/writer support.

    Note: in-memory SQLite doesn't support WAL, so this test uses a file-backed db.
    """
    from calx.serve.db.sqlite import SQLiteEngine

    engine = SQLiteEngine(db_path=tmp_path / "test.db")
    await engine.initialize()
    rows = await engine._fetchall("PRAGMA journal_mode")
    journal_mode = rows[0][0]
    await engine.close()
    assert journal_mode == "wal"


@pytest.mark.asyncio
async def test_corrections_updated_at_trigger(db):
    """Updating a correction row auto-sets updated_at via trigger."""
    from tests.serve.conftest import make_correction

    c = make_correction(id="C099", uuid="trigger-test")
    await db.insert_correction(c)

    original = await db.get_correction("C099")
    original_updated = original.updated_at

    await db.update_correction("C099", recurrence_count=5)

    updated = await db.get_correction("C099")
    assert updated.recurrence_count == 5
    assert updated.updated_at >= original_updated


@pytest.mark.asyncio
async def test_rules_updated_at_trigger(db):
    """Updating a rule row auto-sets updated_at via trigger."""
    from tests.serve.conftest import make_rule

    r = make_rule(id="test-R099", domain="test")
    await db.insert_rule(r)

    original = await db.get_rule("test-R099")

    # Deactivate the rule
    await db.update_rule("test-R099", active=0)

    updated = await db.get_rule("test-R099")
    assert updated.active == 0
    assert updated.updated_at >= original.updated_at


@pytest.mark.asyncio
async def test_corrections_indexes_exist(db):
    """Key indexes exist on corrections table."""
    rows = await db._fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='corrections'"
    )
    index_names = {row[0] for row in rows}
    assert "idx_corrections_domain" in index_names
    assert "idx_corrections_surface" in index_names
    assert "idx_corrections_root" in index_names
    assert "idx_corrections_created" in index_names


@pytest.mark.asyncio
async def test_schema_version_tracked(db):
    """Schema version is recorded after initialization."""
    version = await db.get_schema_version()
    assert version >= 1
