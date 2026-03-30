"""Tests for file-based .calx/ to SQLite migration."""

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_migrate_corrections_from_jsonl(db, calx_dir: Path):
    """Corrections from .calx/corrections.jsonl are imported into SQLite."""
    from calx.serve.db.migrate import migrate_from_files

    result = await migrate_from_files(db, calx_dir)
    assert result.corrections_imported >= 2

    c1 = await db.get_correction("C001")
    assert c1 is not None
    assert "mock" in c1.correction.lower() or "database" in c1.correction.lower()


@pytest.mark.asyncio
async def test_migrate_rules_from_markdown(db, calx_dir: Path):
    """Rules from .calx/rules/*.md are imported into SQLite."""
    from calx.serve.db.migrate import migrate_from_files

    result = await migrate_from_files(db, calx_dir)
    assert result.rules_imported >= 1

    r = await db.get_rule("general-R001")
    assert r is not None
    assert "database" in r.rule_text.lower() or "integration" in r.rule_text.lower()


@pytest.mark.asyncio
async def test_migrate_is_idempotent(db, calx_dir: Path):
    """Running migration twice does not duplicate records."""
    from calx.serve.db.migrate import migrate_from_files

    await migrate_from_files(db, calx_dir)
    result2 = await migrate_from_files(db, calx_dir)
    assert result2.corrections_imported == 0
    assert result2.rules_imported == 0


@pytest.mark.asyncio
async def test_migrate_handles_missing_files(db, tmp_path: Path):
    """Migration handles a .calx/ dir with no corrections or rules."""
    from calx.serve.db.migrate import migrate_from_files

    empty_calx = tmp_path / ".calx"
    empty_calx.mkdir()

    result = await migrate_from_files(db, empty_calx)
    assert result.corrections_imported == 0
    assert result.rules_imported == 0


@pytest.mark.asyncio
async def test_migrate_precomputes_keywords(db, calx_dir: Path):
    """Imported corrections have pre-computed keywords column populated."""
    from calx.serve.db.migrate import migrate_from_files

    await migrate_from_files(db, calx_dir)
    c = await db.get_correction("C001")
    assert c.keywords is not None
    assert len(c.keywords) > 2  # Not empty JSON array
