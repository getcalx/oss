"""Tests for dataclass round-trip: fields written must be readable."""
from __future__ import annotations

import pytest

from calx.serve.db.engine import CorrectionRow, RuleRow


class TestCorrectionLearningModeRoundtrip:

    @pytest.mark.asyncio
    async def test_insert_with_learning_mode(self, db):
        c = CorrectionRow(
            id="C100", uuid="rt-u1", correction="Test",
            domain="general", category="structural",
            learning_mode="architectural",
        )
        await db.insert_correction(c)
        result = await db.get_correction("C100")
        assert result is not None
        assert result.learning_mode == "architectural"

    @pytest.mark.asyncio
    async def test_default_learning_mode(self, db):
        c = CorrectionRow(
            id="C101", uuid="rt-u2", correction="Test",
            domain="general", category="structural",
        )
        await db.insert_correction(c)
        result = await db.get_correction("C101")
        assert result.learning_mode == "unknown"

    @pytest.mark.asyncio
    async def test_find_corrections_has_learning_mode(self, db):
        c = CorrectionRow(
            id="C102", uuid="rt-u3", correction="Test",
            domain="general", category="structural",
            learning_mode="process",
        )
        await db.insert_correction(c)
        results = await db.find_corrections(domain="general")
        assert len(results) >= 1
        found = [r for r in results if r.id == "C102"][0]
        assert found.learning_mode == "process"


class TestRuleHealthFieldsRoundtrip:

    @pytest.mark.asyncio
    async def test_insert_with_health_fields(self, db):
        r = RuleRow(
            id="general-R100", rule_text="Test rule",
            domain="general", learning_mode="process",
            health_score=0.8, health_status="warning",
        )
        await db.insert_rule(r)
        result = await db.get_rule("general-R100")
        assert result is not None
        assert result.learning_mode == "process"
        assert result.health_score == 0.8
        assert result.health_status == "warning"

    @pytest.mark.asyncio
    async def test_default_health_fields(self, db):
        r = RuleRow(
            id="general-R101", rule_text="Test rule",
            domain="general",
        )
        await db.insert_rule(r)
        result = await db.get_rule("general-R101")
        assert result.learning_mode == "unknown"
        assert result.health_score == 1.0
        assert result.health_status == "healthy"
        assert result.last_validated_at is None
        assert result.compiled_at is None
        assert result.compiled_via is None
        assert result.compiled_from_mode is None
        assert result.recurrence_at_compilation is None

    @pytest.mark.asyncio
    async def test_find_rules_has_health_fields(self, db):
        r = RuleRow(
            id="general-R102", rule_text="Test",
            domain="general", health_score=0.5,
            health_status="critical",
        )
        await db.insert_rule(r)
        results = await db.find_rules(domain="general")
        found = [x for x in results if x.id == "general-R102"][0]
        assert found.health_score == 0.5
        assert found.health_status == "critical"

    @pytest.mark.asyncio
    async def test_compiled_fields_roundtrip(self, db):
        r = RuleRow(
            id="general-R103", rule_text="Test",
            domain="general",
        )
        await db.insert_rule(r)
        await db.update_rule(
            "general-R103",
            compiled_at="2026-03-31T17:00:00Z",
            compiled_via="Added pragma",
            compiled_from_mode="process",
            recurrence_at_compilation=3,
            health_status="compiled",
        )
        result = await db.get_rule("general-R103")
        assert result.compiled_at == "2026-03-31T17:00:00Z"
        assert result.compiled_via == "Added pragma"
        assert result.compiled_from_mode == "process"
        assert result.recurrence_at_compilation == 3
        assert result.health_status == "compiled"
