"""Phase 4 -- briefing resource tests."""

import pytest

from calx.serve.resources.briefing import build_briefing


async def test_briefing_returns_core_sections(populated_db):
    result = await build_briefing(populated_db, "default")
    assert "## Active Rules" in result
    assert "## Recent Corrections" in result
    # Empty data sections should be omitted
    assert "## Traction" not in result
    assert "## Pipeline" not in result
    assert "## Recent Decisions" not in result
    assert "## Hot Context" not in result


async def test_briefing_default_sees_general_only(populated_db):
    result = await build_briefing(populated_db, "default")
    assert "general-R001" in result
    # default does NOT see strategy domain
    assert "strategy-R001" not in result


async def test_briefing_unknown_surface_falls_to_general(populated_db):
    result = await build_briefing(populated_db, "custom-surface")
    assert "general-R001" in result
    assert "strategy-R001" not in result


async def test_empty_db_returns_valid_briefing(db):
    result = await build_briefing(db, "default")
    assert "## Active Rules" in result
    assert "No active rules" in result


async def test_briefing_excludes_quarantined_corrections(populated_db):
    result = await build_briefing(populated_db, "default")
    # C005 is quarantined -- should not appear
    assert "C005" not in result


async def test_briefing_includes_non_quarantined_corrections(populated_db):
    result = await build_briefing(populated_db, "default")
    assert "C001" in result
    assert "C003" in result
