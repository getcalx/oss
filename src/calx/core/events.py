"""Append-only event log for Calx instrumentation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Event:
    """An instrumentation event."""
    timestamp: str
    event: str  # "session_start", "session_end", "correction_captured", etc.
    data: dict


def log_event(calx_dir: Path, event: Event) -> None:
    """Append one event to events.jsonl."""
    path = calx_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps({
        "timestamp": event.timestamp,
        "event": event.event,
        "data": event.data,
    }) + "\n"

    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def read_events(calx_dir: Path, event_type: str | None = None) -> list[Event]:
    """Read events from events.jsonl, optionally filtered by type."""
    path = calx_dir / "events.jsonl"
    if not path.exists():
        return []

    events: list[Event] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
            evt = Event(
                timestamp=data["timestamp"],
                event=data["event"],
                data=data.get("data", {}),
            )
            if event_type is None or evt.event == event_type:
                events.append(evt)
        except (json.JSONDecodeError, KeyError):
            continue

    return events
