"""Tests for calx.core.events."""

from pathlib import Path

from calx.core.events import Event, log_event, read_events


def test_log_and_read(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    evt = Event(
        timestamp="2026-03-21T00:00:00+00:00",
        event="session_start",
        data={"model": "opus"},
    )
    log_event(calx_dir, evt)

    events = read_events(calx_dir)
    assert len(events) == 1
    assert events[0].event == "session_start"
    assert events[0].data["model"] == "opus"


def test_filter_by_type(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    log_event(calx_dir, Event("t1", "session_start", {}))
    log_event(calx_dir, Event("t2", "correction_captured", {}))
    log_event(calx_dir, Event("t3", "session_start", {}))

    starts = read_events(calx_dir, "session_start")
    assert len(starts) == 2


def test_read_empty(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    assert read_events(calx_dir) == []
