"""Plan table roundtrip tests."""
from __future__ import annotations

import json
import pytest
import pytest_asyncio

from calx.serve.db.engine import PlanRow, RuleRow


class TestPlanRoundtrip:

    @pytest.mark.asyncio
    async def test_insert_and_get_plan(self, db):
        """PlanRow insert/get roundtrip."""
        plan = PlanRow(
            task_description="Build orchestration",
            chunks=json.dumps([{"id": "chunk_a", "status": "pending"}]),
            dependency_edges=json.dumps([]),
        )
        plan_id = await db.insert_plan(plan)
        assert plan_id > 0

        fetched = await db.get_plan(plan_id)
        assert fetched is not None
        assert fetched.task_description == "Build orchestration"
        assert fetched.phase == "spec"
        assert fetched.status == "active"

    @pytest.mark.asyncio
    async def test_get_active_plan(self, db):
        """get_active_plan returns the active plan."""
        plan = PlanRow(
            task_description="Active plan",
            chunks="[]",
            dependency_edges="[]",
        )
        plan_id = await db.insert_plan(plan)
        active = await db.get_active_plan()
        assert active is not None
        assert active.id == plan_id

    @pytest.mark.asyncio
    async def test_get_active_plan_none(self, db):
        """get_active_plan returns None when no active plan."""
        active = await db.get_active_plan()
        assert active is None

    @pytest.mark.asyncio
    async def test_update_plan(self, db):
        """update_plan updates fields."""
        plan = PlanRow(
            task_description="Test",
            chunks="[]",
            dependency_edges="[]",
        )
        plan_id = await db.insert_plan(plan)
        await db.update_plan(plan_id, phase="build", current_wave=2)
        fetched = await db.get_plan(plan_id)
        assert fetched.phase == "build"
        assert fetched.current_wave == 2

    @pytest.mark.asyncio
    async def test_get_active_plan_skips_completed(self, db):
        """Completed plans are not returned by get_active_plan."""
        plan = PlanRow(
            task_description="Done plan",
            chunks="[]",
            dependency_edges="[]",
            status="completed",
        )
        await db.insert_plan(plan)
        active = await db.get_active_plan()
        assert active is None


class TestRuleRoleField:

    @pytest.mark.asyncio
    async def test_rule_role_roundtrip(self, db):
        """RuleRow role field persists through insert/update/read."""
        from tests.serve.conftest import make_rule
        rule = make_rule(id="test-R001", rule_text="test", domain="test", role="builder")
        await db.insert_rule(rule)
        fetched = await db.get_rule("test-R001")
        assert fetched.role == "builder"

    @pytest.mark.asyncio
    async def test_rule_role_null_default(self, db):
        """RuleRow with no role set returns None."""
        from tests.serve.conftest import make_rule
        rule = make_rule(id="test-R002", rule_text="test2", domain="test")
        await db.insert_rule(rule)
        fetched = await db.get_rule("test-R002")
        assert fetched.role is None

    @pytest.mark.asyncio
    async def test_rule_role_update(self, db):
        """Rule role can be updated."""
        from tests.serve.conftest import make_rule
        rule = make_rule(id="test-R003", rule_text="test3", domain="test")
        await db.insert_rule(rule)
        await db.update_rule("test-R003", role="reviewer")
        fetched = await db.get_rule("test-R003")
        assert fetched.role == "reviewer"


class TestMigration005:

    @pytest.mark.asyncio
    async def test_plans_table_exists(self, db):
        """Migration 005 creates plans table."""
        assert db._conn is not None
        cursor = await db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='plans'"
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_role_column_exists(self, db):
        """Migration 005 adds role column to rules."""
        assert db._conn is not None
        cursor = await db._conn.execute("PRAGMA table_info(rules)")
        columns = {row[1] for row in await cursor.fetchall()}
        assert "role" in columns

    @pytest.mark.asyncio
    async def test_schema_version_is_current(self, db):
        """Schema version matches SCHEMA_VERSION after migration."""
        from calx.serve.db.schema import SCHEMA_VERSION
        version = await db.get_schema_version()
        assert version == SCHEMA_VERSION
