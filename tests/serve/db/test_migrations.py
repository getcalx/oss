"""Tests for SQL schema migrations.

Tests migration 002 which adds sessions, handoffs, board_state,
foil_reviews, compilation_events tables and new columns to
corrections and rules.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests.serve.conftest import make_correction, make_rule


@pytest_asyncio.fixture
async def db_v1():
    """Database at schema version 1 (only migration 001 applied).

    Bypasses initialize() (which runs all migrations) and manually
    connects, sets PRAGMAs, and runs only migration 001.
    """
    import aiosqlite
    from calx.serve.db.sqlite import SQLiteEngine
    from calx.serve.db.migrate import run_sql_migrations

    engine = SQLiteEngine(db_path=":memory:")
    engine._conn = await aiosqlite.connect(":memory:")
    engine._conn.row_factory = aiosqlite.Row
    await engine._conn.execute("PRAGMA journal_mode=WAL")
    await engine._conn.execute("PRAGMA busy_timeout=5000")
    await engine._conn.execute("PRAGMA foreign_keys=ON")
    await run_sql_migrations(engine, up_to=1)
    yield engine
    await engine.close()


@pytest_asyncio.fixture
async def db_v1_with_data(db_v1):
    """v1 database pre-loaded with corrections and rules.

    Uses raw SQL because the v1 schema does not have learning_mode
    or other columns added by later migrations.
    """
    await db_v1._execute(
        """INSERT INTO corrections (id, uuid, correction, domain, category, surface)
           VALUES ('C001', 'mig-u1', 'Don''t mock the database', 'general', 'procedural', 'reid')"""
    )
    await db_v1._execute(
        """INSERT INTO rules (id, rule_text, domain, surface, source_correction_id)
           VALUES ('general-R001', 'Use real DB connections', 'general', 'reid', 'C001')"""
    )
    return db_v1


class TestMigration002:
    """Migration 002: sessions + methodology tables."""

    @pytest.mark.asyncio
    async def test_sessions_table_created(self, db_v1):
        """Migration creates the sessions table."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1)
        # Should be able to insert into sessions
        await db_v1._execute(
            """INSERT INTO sessions (id, surface, surface_type, soft_cap, ceiling, started_at)
               VALUES ('sess1', 'claude-code', 'claude-code', 200000, 250000,
                       '2026-03-31T17:00:00Z')"""
        )
        row = await db_v1._fetchone("SELECT * FROM sessions WHERE id = 'sess1'")
        assert row is not None
        assert row["surface"] == "claude-code"
        assert row["oriented"] == 0
        assert row["tool_call_count"] == 0
        assert row["token_estimate"] == 0
        assert row["server_fail_mode"] == "open"
        assert row["collapse_fail_mode"] == "closed"

    @pytest.mark.asyncio
    async def test_handoffs_table_created(self, db_v1):
        """Migration creates the handoffs table."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1)
        # Create parent session first (FK enforced)
        await db_v1._execute(
            """INSERT INTO sessions (id, surface, surface_type, soft_cap, ceiling, started_at)
               VALUES ('sess1', 'claude-code', 'claude-code', 200000, 250000, '2026-03-31T17:00:00Z')"""
        )
        await db_v1._execute(
            """INSERT INTO handoffs (session_id, what_changed, created_at)
               VALUES ('sess1', 'Added auth module', '2026-03-31T17:00:00Z')"""
        )
        row = await db_v1._fetchone("SELECT * FROM handoffs WHERE session_id = 'sess1'")
        assert row is not None
        assert row["what_changed"] == "Added auth module"

    @pytest.mark.asyncio
    async def test_board_state_table_created(self, db_v1):
        """Migration creates the board_state table."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1)
        await db_v1._execute(
            """INSERT INTO board_state (domain, description, status, updated_at)
               VALUES ('general', 'Build auth', 'in_progress', '2026-03-31T17:00:00Z')"""
        )
        row = await db_v1._fetchone("SELECT * FROM board_state WHERE domain = 'general'")
        assert row is not None
        assert row["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_foil_reviews_table_created(self, db_v1):
        """Migration creates the foil_reviews table."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1)
        await db_v1._execute(
            """INSERT INTO foil_reviews (spec_reference, reviewer_domain, verdict, created_at)
               VALUES ('spec-001', 'backend', 'approve', '2026-03-31T17:00:00Z')"""
        )
        row = await db_v1._fetchone("SELECT * FROM foil_reviews WHERE spec_reference = 'spec-001'")
        assert row is not None
        assert row["verdict"] == "approve"

    @pytest.mark.asyncio
    async def test_compilation_events_table_created(self, db_v1):
        """Migration creates the compilation_events table."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1)
        # Create parent rule first (FK enforced)
        await db_v1._execute(
            """INSERT INTO rules (id, rule_text, domain, active)
               VALUES ('general-R001', 'Use real DB', 'general', 1)"""
        )
        await db_v1._execute(
            """INSERT INTO compilation_events
               (rule_id, rule_text, learning_mode_before, mechanism_type,
                mechanism_description, recurrence_count_at_compilation,
                rule_age_days, correction_chain_length, created_at)
               VALUES ('general-R001', 'Use real DB', 'process', 'code_change',
                       'Added WAL pragma to init', 2, 14, 3, '2026-03-31T17:00:00Z')"""
        )
        row = await db_v1._fetchone("SELECT * FROM compilation_events WHERE rule_id = 'general-R001'")
        assert row is not None
        assert row["mechanism_type"] == "code_change"
        assert row["post_compilation_recurrence"] == 0

    @pytest.mark.asyncio
    async def test_corrections_gets_learning_mode(self, db_v1_with_data):
        """Migration adds learning_mode column to corrections."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1_with_data)
        row = await db_v1_with_data._fetchone(
            "SELECT learning_mode FROM corrections WHERE id = 'C001'"
        )
        assert row is not None
        assert row["learning_mode"] == "unknown"

    @pytest.mark.asyncio
    async def test_rules_gets_new_columns(self, db_v1_with_data):
        """Migration adds health/compilation columns to rules."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1_with_data)
        row = await db_v1_with_data._fetchone(
            "SELECT learning_mode, health_score, health_status FROM rules WHERE id = 'general-R001'"
        )
        assert row is not None
        assert row["learning_mode"] == "unknown"
        assert row["health_score"] == 1.0
        assert row["health_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_existing_data_survives(self, db_v1_with_data):
        """Existing corrections and rules survive migration."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1_with_data)
        c = await db_v1_with_data._fetchone("SELECT * FROM corrections WHERE id = 'C001'")
        assert c is not None
        assert c["correction"] == "Don't mock the database"

        r = await db_v1_with_data._fetchone("SELECT * FROM rules WHERE id = 'general-R001'")
        assert r is not None
        assert r["rule_text"] == "Use real DB connections"

    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self, db_v1):
        """Running migration twice doesn't error."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1)
        await run_sql_migrations(db_v1)  # Should not raise

    @pytest.mark.asyncio
    async def test_schema_version_bumped(self, db_v1):
        """Schema version is at least 2 after migration 002."""
        from calx.serve.db.migrate import run_sql_migrations

        await run_sql_migrations(db_v1)
        version = await db_v1.get_schema_version()
        assert version >= 2


class TestMigration003:
    """Migration 003: methodology indexes."""

    @pytest.mark.asyncio
    async def test_indexes_created(self, db):
        """Migration 003 creates health/compilation indexes."""
        # db fixture already runs all migrations.
        # Verify indexes exist by checking sqlite_master.
        rows = await db._fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        index_names = {r["name"] for r in rows}
        assert "idx_rules_health_status" in index_names
        assert "idx_rules_learning_mode" in index_names
        assert "idx_compilation_events_verified" in index_names
        assert "idx_compilation_events_rule_id" in index_names

    @pytest.mark.asyncio
    async def test_migration_003_idempotent(self, db):
        """Running migration 003 again doesn't error."""
        from calx.serve.db.migrate import run_sql_migrations
        await run_sql_migrations(db)  # Should not raise

    @pytest.mark.asyncio
    async def test_schema_version_is_current(self, db):
        """Schema version matches SCHEMA_VERSION after all migrations."""
        from calx.serve.db.schema import SCHEMA_VERSION
        version = await db.get_schema_version()
        assert version == SCHEMA_VERSION


class TestMigration004:
    """Migration 004: deactivation_reason column on rules."""

    @pytest.mark.asyncio
    async def test_deactivation_reason_column_exists(self, db):
        """Migration 004 adds deactivation_reason column to rules."""
        assert db._conn is not None
        cursor = await db._conn.execute("PRAGMA table_info(rules)")
        columns = {row[1] for row in await cursor.fetchall()}
        assert "deactivation_reason" in columns

    @pytest.mark.asyncio
    async def test_deactivation_reason_roundtrip(self, db):
        """deactivation_reason persists through insert/update/read."""
        from calx.serve.db.engine import RuleRow
        rule = RuleRow(id="test-R001", rule_text="test", domain="test")
        await db.insert_rule(rule)
        await db.update_rule("test-R001", deactivation_reason="obsolete")
        fetched = await db.get_rule("test-R001")
        assert fetched.deactivation_reason == "obsolete"
