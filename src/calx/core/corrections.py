"""Event-sourced correction log for Calx.

corrections.jsonl is truly append-only — no rewrites, no mutations.
State is derived by replaying events.

Event types:
- "created"    — data: {uuid, domain, type, description, context, source, session_id}
- "recurrence" — data: {original_id}  (this correction is a recurrence of original_id)
- "distilled"  — data: {rule_ids: ["api-R001"]}
- "status"     — data: {status: "confirmed"|"provisional"|"dismissed"}
- "promoted"   — data: {rule_id: "api-R001"}  (Tier 2 approval)
- "rejected"   — data: {reason: "..."}  (Tier 2 rejection)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CorrectionEvent:
    """A single event in the correction log. Append-only."""
    timestamp: str
    event_type: str
    correction_id: str
    data: dict


@dataclass
class CorrectionState:
    """Materialized view — computed from replay, never stored."""
    id: str
    uuid: str
    timestamp: str
    domain: str
    type: str
    description: str
    context: str
    source: str
    status: str
    distilled_to: list[str] = field(default_factory=list)
    recurrence_of: str | None = None
    recurrence_count: int = 0
    session_id: str | None = None


def _corrections_path(calx_dir: Path) -> Path:
    return calx_dir / "corrections.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_event(calx_dir: Path, event: CorrectionEvent) -> None:
    """Append one event to corrections.jsonl with fsync for durability."""
    path = _corrections_path(calx_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps({
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "correction_id": event.correction_id,
        "data": event.data,
    }) + "\n"

    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def read_events(calx_dir: Path) -> list[CorrectionEvent]:
    """Read all events from corrections.jsonl. Skip malformed lines."""
    path = _corrections_path(calx_dir)
    if not path.exists():
        return []

    events: list[CorrectionEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
            events.append(CorrectionEvent(
                timestamp=data["timestamp"],
                event_type=data["event_type"],
                correction_id=data["correction_id"],
                data=data.get("data", {}),
            ))
        except (json.JSONDecodeError, KeyError):
            continue

    return events


def materialize(calx_dir: Path) -> list[CorrectionState]:
    """Replay all events and return current state per correction."""
    events = read_events(calx_dir)

    states: dict[str, CorrectionState] = {}
    recurrence_targets: dict[str, int] = {}  # original_id -> count

    for event in events:
        cid = event.correction_id

        if event.event_type == "created":
            d = event.data
            states[cid] = CorrectionState(
                id=cid,
                uuid=d.get("uuid", ""),
                timestamp=event.timestamp,
                domain=d.get("domain", ""),
                type=d.get("type", "process"),
                description=d.get("description", ""),
                context=d.get("context", ""),
                source=d.get("source", "explicit"),
                status="confirmed",
                session_id=d.get("session_id"),
            )
        elif event.event_type == "status" and cid in states:
            states[cid].status = event.data.get("status", states[cid].status)
        elif event.event_type == "distilled" and cid in states:
            rule_ids = event.data.get("rule_ids", [])
            states[cid].distilled_to.extend(rule_ids)
        elif event.event_type == "recurrence" and cid in states:
            original_id = event.data.get("original_id")
            states[cid].recurrence_of = original_id
            if original_id:
                recurrence_targets[original_id] = recurrence_targets.get(original_id, 0) + 1
        elif event.event_type == "promoted" and cid in states:
            rule_id = event.data.get("rule_id", "")
            if rule_id and rule_id not in states[cid].distilled_to:
                states[cid].distilled_to.append(rule_id)
        elif event.event_type == "rejected" and cid in states:
            # Reset promotion eligibility — recurrence count for this ID resets
            recurrence_targets[cid] = 0

    # Apply recurrence counts
    for cid, count in recurrence_targets.items():
        if cid in states:
            states[cid].recurrence_count = count

    return list(states.values())


def get_undistilled(calx_dir: Path) -> list[CorrectionState]:
    """Return corrections with status confirmed and no distilled_to."""
    return [
        c for c in materialize(calx_dir)
        if c.status == "confirmed" and not c.distilled_to
    ]


def get_by_domain(calx_dir: Path, domain: str) -> list[CorrectionState]:
    """Return corrections for a specific domain."""
    return [c for c in materialize(calx_dir) if c.domain == domain]


def get_recurrence_chain(calx_dir: Path, correction_id: str) -> list[CorrectionState]:
    """Follow recurrence_of links to build the full chain."""
    all_corrections = materialize(calx_dir)
    by_id = {c.id: c for c in all_corrections}

    # Find all corrections that are recurrences of this one
    chain = []
    target = by_id.get(correction_id)
    if target:
        chain.append(target)

    for c in all_corrections:
        if c.recurrence_of == correction_id:
            chain.append(c)

    chain.sort(key=lambda c: c.timestamp)
    return chain


def recurrence_count(calx_dir: Path, correction_id: str) -> int:
    """Count recurrence events targeting this correction ID."""
    events = read_events(calx_dir)
    return sum(
        1 for e in events
        if e.event_type == "recurrence" and e.data.get("original_id") == correction_id
    )


def create_correction(
    calx_dir: Path,
    *,
    domain: str,
    description: str,
    correction_type: str = "process",
    context: str = "",
    source: str = "explicit",
    session_id: str | None = None,
) -> CorrectionState:
    """Create a new correction. Convenience function that appends created + status events."""
    from calx.core.ids import generate_uuid, next_sequential_id

    existing = [c.id for c in materialize(calx_dir)]
    cid = next_sequential_id("C", existing)
    uuid = generate_uuid()
    ts = _now()

    # Append created event
    append_event(calx_dir, CorrectionEvent(
        timestamp=ts,
        event_type="created",
        correction_id=cid,
        data={
            "uuid": uuid,
            "domain": domain,
            "type": correction_type,
            "description": description,
            "context": context,
            "source": source,
            "session_id": session_id,
        },
    ))

    # Append confirmed status
    append_event(calx_dir, CorrectionEvent(
        timestamp=ts,
        event_type="status",
        correction_id=cid,
        data={"status": "confirmed"},
    ))

    return CorrectionState(
        id=cid,
        uuid=uuid,
        timestamp=ts,
        domain=domain,
        type=correction_type,
        description=description,
        context=context,
        source=source,
        status="confirmed",
        session_id=session_id,
    )
