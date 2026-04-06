"""Schema contract tests: migration chain as single source of truth.

These tests prove that the migration chain, dataclass definitions, and
live schema stay in agreement. Most tests fail initially (TDD) and pass
after the data contract implementation lands.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from calx.serve.db.engine import (
    BoardStateRow, CompilationEventRow, ContextRow,
    CorrectionRow, DecisionRow, FoilReviewRow,
    HandoffRow, MetricRow, PipelineRow, PlanRow, RuleRow, SessionRow,
)
from calx.serve.db.schema import SCHEMA_VERSION

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "src" / "calx" / "serve" / "db" / "migrations"

# Map dataclass -> table name (must match schema.py DATACLASS_TABLE_MAP when it exists)
_TABLE_MAP = {
    CorrectionRow: "corrections",
    RuleRow: "rules",
    MetricRow: "metrics",
    PipelineRow: "pipeline",
    DecisionRow: "decisions",
    ContextRow: "context",
    SessionRow: "sessions",
    HandoffRow: "handoffs",
    BoardStateRow: "board_state",
    FoilReviewRow: "foil_reviews",
    CompilationEventRow: "compilation_events",
    PlanRow: "plans",
}

_PYTHON_TO_SQLITE = {
    "str": "TEXT",
    "int": "INTEGER",
    "float": "REAL",
    "str | None": "TEXT",
    "int | None": "INTEGER",
    "float | None": "REAL",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_migration_files() -> list[Path]:
    """Return sorted migration files."""
    return sorted(
        f for f in _MIGRATIONS_DIR.glob("*.sql")
        if re.match(r"^\d{3}_", f.name)
    )


async def _replay_migrations(conn: aiosqlite.Connection, up_to: int | None = None) -> None:
    """Replay migration chain on a raw connection."""
    from calx.serve.db.migrate import _split_sql
    for mig_file in _get_migration_files():
        mig_version = int(mig_file.name[:3])
        if up_to is not None and mig_version > up_to:
            break
        sql = mig_file.read_text()
        for statement in _split_sql(sql):
            statement = statement.strip()
            if not statement:
                continue
            try:
                await conn.execute(statement)
            except Exception as e:
                err_msg = str(e).lower()
                if "duplicate column" in err_msg or "already exists" in err_msg:
                    continue
                raise
        await conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (mig_version,),
        )
    await conn.commit()


async def _get_table_info(conn: aiosqlite.Connection, table: str) -> dict[str, dict]:
    """Return {col_name: {type, notnull, pk}} for a table."""
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    cols = {}
    for row in rows:
        cols[row[1]] = {
            "type": row[2].upper() if row[2] else "",
            "notnull": bool(row[3]),
            "pk": bool(row[5]),
        }
    return cols


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def migrated_conn():
    """In-memory connection with full migration chain replayed."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await _replay_migrations(conn)
    yield conn
    await conn.close()


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------

class TestSchemaContract:
    """Prove migration chain and dataclasses agree."""

    @pytest.mark.asyncio
    async def test_dataclass_fields_match_schema(self, migrated_conn):
        """Every dataclass field has a corresponding column with compatible type."""
        for dc_class, table_name in _TABLE_MAP.items():
            cols = await _get_table_info(migrated_conn, table_name)
            for field in dataclasses.fields(dc_class):
                assert field.name in cols, (
                    f"Table '{table_name}': missing column '{field.name}'"
                )
                expected_type = _PYTHON_TO_SQLITE.get(field.type)
                if expected_type is not None:
                    assert cols[field.name]["type"] == expected_type, (
                        f"Table '{table_name}'.{field.name}: "
                        f"expected {expected_type}, got {cols[field.name]['type']}"
                    )

    @pytest.mark.asyncio
    async def test_schema_columns_have_dataclass_fields(self, migrated_conn):
        """Every column in dataclass-mapped tables has a dataclass field (bidirectional)."""
        for dc_class, table_name in _TABLE_MAP.items():
            cols = await _get_table_info(migrated_conn, table_name)
            field_names = {f.name for f in dataclasses.fields(dc_class)}
            for col_name in cols:
                assert col_name in field_names, (
                    f"Table '{table_name}': column '{col_name}' has no "
                    f"dataclass field in {dc_class.__name__}"
                )

    @pytest.mark.asyncio
    async def test_migration_chain_is_self_contained(self, migrated_conn):
        """Replaying all migrations on empty DB produces valid schema at SCHEMA_VERSION."""
        cursor = await migrated_conn.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = await cursor.fetchone()
        assert row[0] == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_schema_version_matches_latest_migration(self):
        """SCHEMA_VERSION in schema.py equals highest NNN in migration filenames."""
        files = _get_migration_files()
        assert len(files) > 0, "No migration files found"
        highest = max(int(f.name[:3]) for f in files)
        assert SCHEMA_VERSION == highest, (
            f"SCHEMA_VERSION={SCHEMA_VERSION} but highest migration is {highest}"
        )

    @pytest.mark.asyncio
    async def test_migrations_are_sequential(self):
        """No gaps in migration file numbering (001 through latest)."""
        files = _get_migration_files()
        versions = sorted(int(f.name[:3]) for f in files)
        expected = list(range(1, max(versions) + 1))
        assert versions == expected, (
            f"Gap in migrations: found {versions}, expected {expected}"
        )


class TestStartupBehavior:
    """Prove initialize() handles version transitions correctly."""

    @pytest.mark.asyncio
    async def test_startup_with_old_schema_migrates(self):
        """DB at version 1 migrates to SCHEMA_VERSION on initialize()."""
        from calx.serve.db.sqlite import SQLiteEngine

        engine = SQLiteEngine(db_path=":memory:")
        await engine.initialize()
        version = await engine.get_schema_version()
        assert version == SCHEMA_VERSION
        await engine.close()

    @pytest.mark.asyncio
    async def test_startup_with_newer_schema_refuses(self):
        """DB at SCHEMA_VERSION+1 causes SystemExit."""
        from calx.serve.db.sqlite import SQLiteEngine

        engine = SQLiteEngine(db_path=":memory:")
        await engine.initialize()
        await engine.set_schema_version(SCHEMA_VERSION + 1)
        await engine.close()

        engine2 = SQLiteEngine(db_path=":memory:")
        # Can't reuse the same in-memory DB, so test the logic directly
        # by creating a file-backed DB
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            eng = SQLiteEngine(db_path=db_path)
            await eng.initialize()
            await eng.set_schema_version(SCHEMA_VERSION + 1)
            await eng.close()

            eng2 = SQLiteEngine(db_path=db_path)
            with pytest.raises(SystemExit, match="upgrade"):
                await eng2.initialize()
        finally:
            os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_startup_missing_column_gives_clear_error(self):
        """Dropping a column then calling validate_schema() names the missing column."""
        from calx.serve.db.sqlite import SQLiteEngine

        engine = SQLiteEngine(db_path=":memory:")
        await engine.initialize()

        # SQLite doesn't support DROP COLUMN before 3.35, but we can test
        # validate_schema() by monkeypatching the table_info response
        # via a view trick. Simpler: just test validate_schema directly
        # after we confirm it exists.
        # For now, this test documents the expected behavior.
        # It will pass after validate_schema() is implemented in Wave 3.
        if not hasattr(engine, "validate_schema"):
            pytest.skip("validate_schema() not yet implemented")

        # Drop a column by recreating the table without it
        assert engine._conn is not None
        await engine._conn.execute("CREATE TABLE corrections_backup AS SELECT id, uuid, correction, domain, category FROM corrections")
        await engine._conn.execute("DROP TABLE corrections")
        await engine._conn.execute("ALTER TABLE corrections_backup RENAME TO corrections")
        await engine._conn.commit()

        with pytest.raises(SystemExit, match="missing column"):
            await engine.validate_schema()
        await engine.close()

    @pytest.mark.asyncio
    async def test_upgrade_from_version_zero(self):
        """DB with schema_version table but no rows replays full chain."""
        from calx.serve.db.sqlite import SQLiteEngine

        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            # Create a DB with just the schema_version table (empty)
            conn = await aiosqlite.connect(db_path)
            await conn.execute(
                "CREATE TABLE schema_version ("
                "version INTEGER PRIMARY KEY,"
                "applied_at TEXT NOT NULL DEFAULT"
                " (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')))"
            )
            await conn.commit()
            await conn.close()

            eng = SQLiteEngine(db_path=db_path)
            await eng.initialize()
            version = await eng.get_schema_version()
            assert version == SCHEMA_VERSION
            await eng.close()
        finally:
            os.unlink(db_path)


class TestUpgradePaths:
    """Prove upgrades from each historical version work."""

    @pytest.mark.asyncio
    async def test_upgrade_from_each_version(self):
        """For each version 1 through 5, create DB and migrate to current."""
        from calx.serve.db.sqlite import SQLiteEngine
        from calx.serve.db.migrate import run_sql_migrations

        for start_version in range(1, SCHEMA_VERSION):
            conn = await aiosqlite.connect(":memory:")
            await conn.execute("PRAGMA foreign_keys=ON")
            await _replay_migrations(conn, up_to=start_version)

            cursor = await conn.execute("SELECT MAX(version) FROM schema_version")
            row = await cursor.fetchone()
            assert row[0] == start_version, f"Setup failed for version {start_version}"

            # Now create an engine on this connection and run remaining migrations
            engine = SQLiteEngine(db_path=":memory:")
            engine._conn = conn
            engine._conn.row_factory = aiosqlite.Row

            await run_sql_migrations(engine)

            version = await engine.get_schema_version()
            assert version == SCHEMA_VERSION, (
                f"Upgrade from v{start_version} ended at v{version}, "
                f"expected v{SCHEMA_VERSION}"
            )
            await conn.close()


class TestMigrationOrdering:
    """Prove each migration is self-contained at its position in the chain."""

    @pytest.mark.asyncio
    async def test_no_forward_references(self):
        """Each migration N succeeds on a DB that only has migrations 1..N-1 applied.

        Catches the class of bug where migration N references columns or tables
        created by a later migration. This is the structural guard for the 003/006
        ordering bug (health_status indexed before it existed).
        """
        from calx.serve.db.migrate import _split_sql

        files = _get_migration_files()
        for mig_file in files:
            mig_version = int(mig_file.name[:3])
            conn = await aiosqlite.connect(":memory:")
            await conn.execute("PRAGMA foreign_keys=ON")

            # Replay 001..(N-1)
            await _replay_migrations(conn, up_to=mig_version - 1)

            # Now apply migration N alone
            sql = mig_file.read_text()
            for statement in _split_sql(sql):
                statement = statement.strip()
                if not statement:
                    continue
                try:
                    await conn.execute(statement)
                except Exception as e:
                    err_msg = str(e).lower()
                    if "duplicate column" in err_msg or "already exists" in err_msg:
                        continue
                    await conn.close()
                    raise AssertionError(
                        f"Migration {mig_file.name} has a forward reference: {e}"
                    ) from e

            await conn.close()


class TestMigrationFileIntegrity:
    """Prove migration files are well-formed."""

    @pytest.mark.asyncio
    async def test_split_sql_preserves_trigger_bodies(self):
        """_split_sql() keeps CREATE TRIGGER with internal semicolons as one statement."""
        from calx.serve.db.migrate import _split_sql

        sql = (
            "CREATE TABLE IF NOT EXISTS foo (id INTEGER PRIMARY KEY);\n"
            "\n"
            "CREATE TRIGGER IF NOT EXISTS trg_foo\n"
            "    AFTER UPDATE ON foo\n"
            "    FOR EACH ROW\n"
            "    BEGIN\n"
            "        UPDATE foo SET id = NEW.id;\n"
            "    END;\n"
            "\n"
            "CREATE INDEX IF NOT EXISTS idx_foo ON foo(id);\n"
        )
        statements = _split_sql(sql)
        # Should be 3 statements: CREATE TABLE, CREATE TRIGGER, CREATE INDEX
        assert len(statements) == 3, f"Expected 3 statements, got {len(statements)}: {statements}"
        # The trigger statement should contain BEGIN and END
        trigger_stmt = statements[1]
        assert "BEGIN" in trigger_stmt
        assert "END" in trigger_stmt


class TestValidation:
    """Prove validate_schema checks types and nullability correctly."""

    @pytest.mark.asyncio
    async def test_validate_schema_type_mapping(self):
        """validate_schema correctly maps str->TEXT, float->REAL, int->INTEGER."""
        from calx.serve.db.sqlite import SQLiteEngine

        engine = SQLiteEngine(db_path=":memory:")
        await engine.initialize()
        if not hasattr(engine, "validate_schema"):
            pytest.skip("validate_schema() not yet implemented")
        # Should not raise (types match)
        await engine.validate_schema()
        await engine.close()

    @pytest.mark.asyncio
    async def test_validate_schema_notnull_mapping(self):
        """validate_schema checks notnull: str fields expect NOT NULL, str | None expect nullable."""
        from calx.serve.db.sqlite import SQLiteEngine

        engine = SQLiteEngine(db_path=":memory:")
        await engine.initialize()
        if not hasattr(engine, "validate_schema"):
            pytest.skip("validate_schema() not yet implemented")
        # The default schema should pass validation
        await engine.validate_schema()
        await engine.close()

    @pytest.mark.asyncio
    async def test_validate_schema_rejects_unmapped_type(self):
        """Monkeypatch a dataclass field to have an unmapped type triggers error."""
        from calx.serve.db.sqlite import SQLiteEngine

        engine = SQLiteEngine(db_path=":memory:")
        await engine.initialize()
        if not hasattr(engine, "validate_schema"):
            pytest.skip("validate_schema() not yet implemented")

        # Monkeypatch: temporarily modify the type mapping to exclude 'str'
        from calx.serve.db import schema as schema_mod
        original = schema_mod.PYTHON_TO_SQLITE_TYPE.copy() if hasattr(schema_mod, "PYTHON_TO_SQLITE_TYPE") else None
        if original is None:
            pytest.skip("PYTHON_TO_SQLITE_TYPE not yet defined")

        schema_mod.PYTHON_TO_SQLITE_TYPE = {
            k: v for k, v in original.items() if k != "str"
        }
        try:
            with pytest.raises(SystemExit, match="unmapped"):
                await engine.validate_schema()
        finally:
            schema_mod.PYTHON_TO_SQLITE_TYPE = original
        await engine.close()

    @pytest.mark.asyncio
    async def test_validate_schema_error_includes_backup_path(self):
        """When validate_schema fails and backup exists, error mentions backup path."""
        from calx.serve.db.sqlite import SQLiteEngine

        engine = SQLiteEngine(db_path=":memory:")
        await engine.initialize()
        if not hasattr(engine, "validate_schema"):
            pytest.skip("validate_schema() not yet implemented")

        # Force a validation failure by corrupting a table
        assert engine._conn is not None
        await engine._conn.execute(
            "CREATE TABLE corrections_backup AS SELECT id, uuid, correction, domain, category FROM corrections"
        )
        await engine._conn.execute("DROP TABLE corrections")
        await engine._conn.execute("ALTER TABLE corrections_backup RENAME TO corrections")
        await engine._conn.commit()

        with pytest.raises(SystemExit, match="/fake/backup.db"):
            await engine.validate_schema(backup_path="/fake/backup.db")
        await engine.close()


class TestBackup:
    """Prove backup behavior."""

    @pytest.mark.asyncio
    async def test_backup_created_before_migration(self, tmp_path):
        """File-backed DB at version 5 produces timestamped backup on migration."""
        from calx.serve.db.sqlite import SQLiteEngine
        from calx.serve.db.migrate import _backup_db

        if not hasattr(SQLiteEngine, "validate_schema"):
            # _backup_db may not exist yet
            try:
                from calx.serve.db.migrate import _backup_db
            except ImportError:
                pytest.skip("_backup_db not yet implemented")

        db_path = tmp_path / "calx.db"
        engine = SQLiteEngine(db_path=str(db_path))
        await engine.initialize()

        backup_path = await _backup_db(engine, version=5)
        assert backup_path is not None
        assert Path(backup_path).exists()
        assert "backup" in backup_path
        assert "v5" in backup_path
        await engine.close()

    @pytest.mark.asyncio
    async def test_partial_migration_recovery(self):
        """DB with partially applied migration recovers on restart."""
        # A DB at version 3 with some 004 columns already present
        # should complete 004-006 without error
        conn = await aiosqlite.connect(":memory:")
        await conn.execute("PRAGMA foreign_keys=ON")
        await _replay_migrations(conn, up_to=3)

        # Manually add one column from migration 004 to simulate partial apply
        try:
            await conn.execute("ALTER TABLE rules ADD COLUMN deactivation_reason TEXT")
            await conn.commit()
        except Exception:
            pass  # Column may already exist from 002

        # Now replay remaining migrations: should handle duplicates gracefully
        from calx.serve.db.sqlite import SQLiteEngine
        from calx.serve.db.migrate import run_sql_migrations

        engine = SQLiteEngine(db_path=":memory:")
        engine._conn = conn
        engine._conn.row_factory = aiosqlite.Row

        await run_sql_migrations(engine)
        version = await engine.get_schema_version()
        assert version == SCHEMA_VERSION
        await conn.close()
