"""Tests for calx.core.corrections."""

import json
from pathlib import Path

from calx.core.corrections import (
    CorrectionEvent,
    append_event,
    create_correction,
    get_by_domain,
    get_recurrence_chain,
    get_undistilled,
    materialize,
    read_events,
    recurrence_count,
)


def test_append_and_read(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    event = CorrectionEvent(
        timestamp="2026-03-21T00:00:00+00:00",
        event_type="created",
        correction_id="C001",
        data={"domain": "api", "description": "test"},
    )
    append_event(calx_dir, event)

    events = read_events(calx_dir)
    assert len(events) == 1
    assert events[0].correction_id == "C001"
    assert events[0].event_type == "created"


def test_append_only_invariant(tmp_path: Path):
    """Verify the file is truly append-only — content only grows."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    path = calx_dir / "corrections.jsonl"

    event1 = CorrectionEvent(
        timestamp="2026-03-21T00:00:00+00:00",
        event_type="created",
        correction_id="C001",
        data={"domain": "api", "description": "first"},
    )
    append_event(calx_dir, event1)
    size_after_first = path.stat().st_size

    event2 = CorrectionEvent(
        timestamp="2026-03-21T00:00:01+00:00",
        event_type="status",
        correction_id="C001",
        data={"status": "confirmed"},
    )
    append_event(calx_dir, event2)
    size_after_second = path.stat().st_size

    assert size_after_second > size_after_first
    # First line is still intact
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["correction_id"] == "C001"
    assert first["event_type"] == "created"


def test_materialize(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c = create_correction(calx_dir, domain="api", description="don't mock db")
    states = materialize(calx_dir)
    assert len(states) == 1
    assert states[0].id == c.id
    assert states[0].domain == "api"
    assert states[0].status == "confirmed"


def test_distilled_event(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c = create_correction(calx_dir, domain="api", description="test")
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T01:00:00+00:00",
        event_type="distilled",
        correction_id=c.id,
        data={"rule_ids": ["api-R001"]},
    ))

    states = materialize(calx_dir)
    assert states[0].distilled_to == ["api-R001"]


def test_get_undistilled(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="first")
    c2 = create_correction(calx_dir, domain="api", description="second")

    # Distill c1
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T01:00:00+00:00",
        event_type="distilled",
        correction_id=c1.id,
        data={"rule_ids": ["api-R001"]},
    ))

    undistilled = get_undistilled(calx_dir)
    assert len(undistilled) == 1
    assert undistilled[0].id == c2.id


def test_recurrence_tracking(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="don't mock")
    c2 = create_correction(calx_dir, domain="api", description="stop mocking")

    # Mark c2 as recurrence of c1
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T01:00:00+00:00",
        event_type="recurrence",
        correction_id=c2.id,
        data={"original_id": c1.id},
    ))

    states = materialize(calx_dir)
    by_id = {s.id: s for s in states}

    assert by_id[c1.id].recurrence_count == 1
    assert by_id[c2.id].recurrence_of == c1.id
    assert recurrence_count(calx_dir, c1.id) == 1


def test_get_by_domain(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    create_correction(calx_dir, domain="api", description="api issue")
    create_correction(calx_dir, domain="tests", description="test issue")

    api_corrections = get_by_domain(calx_dir, "api")
    assert len(api_corrections) == 1
    assert api_corrections[0].domain == "api"


def test_recurrence_chain(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="don't mock v1")
    c2 = create_correction(calx_dir, domain="api", description="don't mock v2")
    c3 = create_correction(calx_dir, domain="api", description="don't mock v3")

    for c in [c2, c3]:
        append_event(calx_dir, CorrectionEvent(
            timestamp="2026-03-21T01:00:00+00:00",
            event_type="recurrence",
            correction_id=c.id,
            data={"original_id": c1.id},
        ))

    chain = get_recurrence_chain(calx_dir, c1.id)
    assert len(chain) == 3
    assert chain[0].id == c1.id


def test_rejected_resets_count(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="test")
    c2 = create_correction(calx_dir, domain="api", description="test again")

    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T01:00:00+00:00",
        event_type="recurrence",
        correction_id=c2.id,
        data={"original_id": c1.id},
    ))

    # Reject resets
    append_event(calx_dir, CorrectionEvent(
        timestamp="2026-03-21T02:00:00+00:00",
        event_type="rejected",
        correction_id=c1.id,
        data={"reason": "not ready"},
    ))

    states = materialize(calx_dir)
    by_id = {s.id: s for s in states}
    assert by_id[c1.id].recurrence_count == 0


def test_read_empty(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    assert read_events(calx_dir) == []
    assert materialize(calx_dir) == []


def test_create_correction_auto_ids(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    c1 = create_correction(calx_dir, domain="api", description="first")
    c2 = create_correction(calx_dir, domain="api", description="second")

    assert c1.id == "C001"
    assert c2.id == "C002"
    assert c1.uuid != c2.uuid
