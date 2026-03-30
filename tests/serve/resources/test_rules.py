"""Phase 4 -- rules resource tests."""

import pytest

from calx.serve.resources.rules import _get_rules


async def test_returns_active_rules(populated_db):
    result = await _get_rules(populated_db)
    assert "general-R001" in result
    assert "strategy-R001" in result


async def test_filters_by_domain(populated_db):
    result = await _get_rules(populated_db, domain="general")
    assert "general-R001" in result
    assert "strategy-R001" not in result


async def test_filters_strategy_domain(populated_db):
    result = await _get_rules(populated_db, domain="strategy")
    assert "strategy-R001" in result
    assert "general-R001" not in result


async def test_empty_domain_returns_message(populated_db):
    result = await _get_rules(populated_db, domain="nonexistent")
    assert "No active rules" in result
    assert "nonexistent" in result


async def test_empty_db_returns_message(db):
    result = await _get_rules(db)
    assert "No active rules" in result


async def test_rules_include_rule_text(populated_db):
    result = await _get_rules(populated_db, domain="general")
    assert "Use real database connections in integration tests" in result


async def test_rules_include_surface_tag(populated_db):
    result = await _get_rules(populated_db, domain="general")
    # format_rules_markdown adds [surface] tag when surface is set
    assert "[reid]" in result
