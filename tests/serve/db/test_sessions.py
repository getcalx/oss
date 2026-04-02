"""Tests for session, handoff, board state, foil review, and compilation event CRUD."""
from __future__ import annotations

import pytest
import pytest_asyncio

from calx.serve.db.engine import (
    BoardStateRow,
    CompilationEventRow,
    FoilReviewRow,
    HandoffRow,
    SessionRow,
)


def _now():
    return "2026-03-31T17:00:00Z"


def make_session(**overrides) -> SessionRow:
    defaults = dict(
        id="sess_test1",
        surface="claude-code",
        surface_type="claude-code",
        soft_cap=200000,
        ceiling=250000,
        started_at=_now(),
    )
    defaults.update(overrides)
    return SessionRow(**defaults)


class TestSessionCRUD:

    @pytest.mark.asyncio
    async def test_insert_and_get_session(self, db):
        s = make_session()
        await db.insert_session(s)
        result = await db.get_session("sess_test1")
        assert result is not None
        assert result.id == "sess_test1"
        assert result.surface == "claude-code"
        assert result.oriented == 0
        assert result.tool_call_count == 0
        assert result.server_fail_mode == "open"
        assert result.collapse_fail_mode == "closed"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, db):
        result = await db.get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_session(self, db):
        await db.insert_session(make_session())
        await db.update_session("sess_test1", oriented=1, tool_call_count=5)
        result = await db.get_session("sess_test1")
        assert result.oriented == 1
        assert result.tool_call_count == 5

    @pytest.mark.asyncio
    async def test_get_active_session(self, db):
        await db.insert_session(make_session(id="sess1"))
        await db.insert_session(make_session(id="sess2"))
        # End sess1
        await db.update_session("sess1", ended_at=_now())
        active = await db.get_active_session()
        assert active is not None
        assert active.id == "sess2"

    @pytest.mark.asyncio
    async def test_get_active_session_none(self, db):
        active = await db.get_active_session()
        assert active is None

    @pytest.mark.asyncio
    async def test_end_session(self, db):
        await db.insert_session(make_session())
        await db.update_session("sess_test1", ended_at=_now())
        result = await db.get_session("sess_test1")
        assert result.ended_at == _now()


class TestHandoffCRUD:

    @pytest.mark.asyncio
    async def test_insert_and_get_handoff(self, db):
        await db.insert_session(make_session())
        h = HandoffRow(
            session_id="sess_test1",
            what_changed="Added auth module",
            what_others_need="Update API contracts",
            decisions_deferred="OAuth vs JWT",
            next_priorities="Build login flow",
            created_at=_now(),
        )
        hid = await db.insert_handoff(h)
        assert hid > 0

        latest = await db.get_latest_handoff()
        assert latest is not None
        assert latest.what_changed == "Added auth module"
        assert latest.session_id == "sess_test1"

    @pytest.mark.asyncio
    async def test_get_latest_handoff_by_session(self, db):
        await db.insert_session(make_session(id="sess1"))
        await db.insert_session(make_session(id="sess2"))
        await db.insert_handoff(HandoffRow(
            session_id="sess1", what_changed="Change 1", created_at=_now(),
        ))
        await db.insert_handoff(HandoffRow(
            session_id="sess2", what_changed="Change 2", created_at=_now(),
        ))
        h = await db.get_latest_handoff(session_id="sess1")
        assert h.what_changed == "Change 1"

    @pytest.mark.asyncio
    async def test_get_latest_handoff_none(self, db):
        result = await db.get_latest_handoff()
        assert result is None


class TestBoardStateCRUD:

    @pytest.mark.asyncio
    async def test_insert_and_get_board_item(self, db):
        item = BoardStateRow(
            domain="general",
            description="Build enforcement layer",
            status="in_progress",
            updated_at=_now(),
        )
        item_id = await db.insert_board_item(item)
        assert item_id > 0

        board = await db.get_board_state()
        assert len(board) == 1
        assert board[0].description == "Build enforcement layer"

    @pytest.mark.asyncio
    async def test_get_board_state_filtered(self, db):
        await db.insert_board_item(BoardStateRow(
            domain="general", description="Task 1", status="in_progress", updated_at=_now(),
        ))
        await db.insert_board_item(BoardStateRow(
            domain="general", description="Task 2", status="done", updated_at=_now(),
        ))
        in_progress = await db.get_board_state(status="in_progress")
        assert len(in_progress) == 1
        assert in_progress[0].description == "Task 1"

    @pytest.mark.asyncio
    async def test_update_board_item(self, db):
        item_id = await db.insert_board_item(BoardStateRow(
            domain="general", description="Task 1", status="in_progress", updated_at=_now(),
        ))
        await db.update_board_item(item_id, status="done")
        board = await db.get_board_state(status="done")
        assert len(board) == 1


class TestFoilReviewCRUD:

    @pytest.mark.asyncio
    async def test_insert_and_get_foil_review(self, db):
        review = FoilReviewRow(
            spec_reference="spec-001",
            reviewer_domain="backend",
            verdict="revise",
            findings="Missing error handling",
            round=1,
            created_at=_now(),
        )
        rid = await db.insert_foil_review(review)
        assert rid > 0

        reviews = await db.get_foil_reviews()
        assert len(reviews) == 1
        assert reviews[0].verdict == "revise"

    @pytest.mark.asyncio
    async def test_get_foil_reviews_by_spec(self, db):
        await db.insert_foil_review(FoilReviewRow(
            spec_reference="spec-001", reviewer_domain="backend",
            verdict="revise", created_at=_now(),
        ))
        await db.insert_foil_review(FoilReviewRow(
            spec_reference="spec-002", reviewer_domain="frontend",
            verdict="approve", created_at=_now(),
        ))
        reviews = await db.get_foil_reviews(spec_reference="spec-001")
        assert len(reviews) == 1
        assert reviews[0].reviewer_domain == "backend"


class TestCompilationEventCRUD:

    @pytest.mark.asyncio
    async def test_insert_and_get_compilation_event(self, db):
        from tests.serve.conftest import make_correction, make_rule
        # Need a rule to reference
        await db.insert_correction(make_correction(id="C001", uuid="ce-u1"))
        await db.insert_rule(make_rule(
            id="general-R001", source_correction_id="C001",
        ))

        event = CompilationEventRow(
            rule_id="general-R001",
            source_correction_id="C001",
            rule_text="Use real DB connections",
            learning_mode_before="process",
            mechanism_type="code_change",
            mechanism_description="Added WAL pragma to init",
            recurrence_count_at_compilation=2,
            rule_age_days=14,
            correction_chain_length=3,
            created_at=_now(),
        )
        eid = await db.insert_compilation_event(event)
        assert eid > 0

        events = await db.get_compilation_events()
        assert len(events) == 1
        assert events[0].mechanism_type == "code_change"
        assert events[0].post_compilation_recurrence == 0

    @pytest.mark.asyncio
    async def test_get_compilation_events_by_rule(self, db):
        from tests.serve.conftest import make_correction, make_rule
        await db.insert_correction(make_correction(id="C001", uuid="ce-u2"))
        await db.insert_rule(make_rule(id="general-R001", source_correction_id="C001"))
        await db.insert_correction(make_correction(id="C002", uuid="ce-u3"))
        await db.insert_rule(make_rule(id="general-R002", source_correction_id="C002"))

        await db.insert_compilation_event(CompilationEventRow(
            rule_id="general-R001", rule_text="Rule 1",
            learning_mode_before="process", mechanism_type="code_change",
            mechanism_description="Fix 1", recurrence_count_at_compilation=2,
            rule_age_days=10, correction_chain_length=2, created_at=_now(),
        ))
        await db.insert_compilation_event(CompilationEventRow(
            rule_id="general-R002", rule_text="Rule 2",
            learning_mode_before="process", mechanism_type="config_change",
            mechanism_description="Fix 2", recurrence_count_at_compilation=1,
            rule_age_days=5, correction_chain_length=1, created_at=_now(),
        ))

        events = await db.get_compilation_events(rule_id="general-R001")
        assert len(events) == 1
        assert events[0].rule_text == "Rule 1"

    @pytest.mark.asyncio
    async def test_update_compilation_event(self, db):
        from tests.serve.conftest import make_correction, make_rule
        await db.insert_correction(make_correction(id="C001", uuid="ce-u4"))
        await db.insert_rule(make_rule(id="general-R001", source_correction_id="C001"))

        eid = await db.insert_compilation_event(CompilationEventRow(
            rule_id="general-R001", rule_text="Rule 1",
            learning_mode_before="process", mechanism_type="code_change",
            mechanism_description="Fix 1", recurrence_count_at_compilation=2,
            rule_age_days=10, correction_chain_length=2, created_at=_now(),
        ))
        await db.update_compilation_event(eid, post_compilation_recurrence=1)

        events = await db.get_compilation_events()
        assert events[0].post_compilation_recurrence == 1
