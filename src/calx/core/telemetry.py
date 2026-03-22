"""Anonymous stats payload construction and POST for Calx.

This module handles the ``calx stats --share`` flow (synchronous, user-initiated).
For background telemetry events, see :mod:`calx.core.phone_home`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

STATS_ENDPOINT = "https://calx.sh/api/v1/events"


@dataclass
class StatsPayload:
    """Anonymous stats payload."""
    install_id: str
    correction_count: int
    type_split: dict[str, int]
    recurrence_rate: float
    domain_counts: dict[str, int]
    error_floor: float | None
    days_active: int
    referral_source: str


def build_payload(calx_dir: Path) -> StatsPayload:
    """Construct stats payload from local data."""
    from calx.core.config import load_config
    from calx.core.corrections import materialize

    config = load_config(calx_dir)
    corrections = materialize(calx_dir)

    type_split: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    recurrence_total = 0

    for c in corrections:
        type_split[c.type] = type_split.get(c.type, 0) + 1
        domain_counts[c.domain] = domain_counts.get(c.domain, 0) + 1
        if c.recurrence_of:
            recurrence_total += 1

    total = len(corrections)
    recurrence_rate = recurrence_total / total if total > 0 else 0.0

    return StatsPayload(
        install_id=config.install_id,
        correction_count=total,
        type_split=type_split,
        recurrence_rate=recurrence_rate,
        domain_counts=domain_counts,
        error_floor=None,  # Pro feature, computed separately
        days_active=0,  # TODO: compute from event history
        referral_source=config.referral_source,
    )


def post_stats(payload: StatsPayload) -> bool:
    """POST anonymous stats to calx.sh/api/stats. Silent on failure."""
    try:
        data = json.dumps(asdict(payload)).encode("utf-8")
        req = urllib.request.Request(
            STATS_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def should_surface_benchmark(calx_dir: Path) -> bool:
    """Return True when correction count >= 50 (benchmark threshold)."""
    from calx.core.corrections import materialize
    return len(materialize(calx_dir)) >= 50
