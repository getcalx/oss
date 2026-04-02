"""Tests for deactivate_rule MCP tool."""
from __future__ import annotations

import pytest

from tests.serve.conftest import make_rule


class TestDeactivateRule:

    @pytest.mark.asyncio
    async def test_deactivate_rule(self, db):
        from calx.serve.tools.deactivate_rule import handle_deactivate_rule

        await db.insert_rule(make_rule(id="general-R001"))
        result = await handle_deactivate_rule(db, rule_id="general-R001")
        assert result["status"] == "ok"
        assert result["active"] == 0

        rule = await db.get_rule("general-R001")
        assert rule.active == 0

    @pytest.mark.asyncio
    async def test_deactivate_rule_with_reason(self, db):
        from calx.serve.tools.deactivate_rule import handle_deactivate_rule

        await db.insert_rule(make_rule(id="general-R001"))
        result = await handle_deactivate_rule(
            db, rule_id="general-R001", reason="Superseded by R002",
        )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_deactivate_rule_not_found(self, db):
        from calx.serve.tools.deactivate_rule import handle_deactivate_rule

        result = await handle_deactivate_rule(db, rule_id="nope")
        assert result["status"] == "not_found"
