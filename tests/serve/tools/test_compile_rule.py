"""Tests for compile_rule MCP tool."""
from __future__ import annotations

import pytest

from tests.serve.conftest import make_correction, make_rule


class TestCompileRule:

    @pytest.mark.asyncio
    async def test_compile_rule(self, db):
        from calx.serve.tools.compile_rule import handle_compile_rule

        await db.insert_correction(make_correction(id="C001", uuid="cr-u1"))
        await db.insert_rule(make_rule(
            id="general-R001", source_correction_id="C001",
        ))

        result = await handle_compile_rule(
            db,
            rule_id="general-R001",
            mechanism_type="code_change",
            mechanism_description="Added WAL pragma to init",
        )
        assert result["status"] == "ok"
        assert result["rule_archived"] is True

        # Rule should be archived
        rule = await db.get_rule("general-R001")
        assert rule.active == 0

        # Compilation event should exist
        events = await db.get_compilation_events(rule_id="general-R001")
        assert len(events) == 1
        assert events[0].mechanism_type == "code_change"

    @pytest.mark.asyncio
    async def test_compile_rule_not_found(self, db):
        from calx.serve.tools.compile_rule import handle_compile_rule

        result = await handle_compile_rule(
            db,
            rule_id="nope",
            mechanism_type="code_change",
            mechanism_description="Fix",
        )
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_compile_rule_invalid_type(self, db):
        from calx.serve.tools.compile_rule import handle_compile_rule

        await db.insert_correction(make_correction(id="C001", uuid="cr-u2"))
        await db.insert_rule(make_rule(
            id="general-R001", source_correction_id="C001",
        ))

        result = await handle_compile_rule(
            db,
            rule_id="general-R001",
            mechanism_type="invalid_type",
            mechanism_description="Fix",
        )
        assert result["status"] == "error"
