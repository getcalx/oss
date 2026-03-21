"""Health state and session management for Calx."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RuleHealthData:
    """Health data for a single rule."""
    score: float = 1.0
    last_reinforcement: str | None = None
    recurrence_count: int = 0
    has_conflict: bool = False


@dataclass
class HealthState:
    """Persisted health state."""
    schema_version: str = "1.0"
    last_health_check: str | None = None
    rule_scores: dict[str, RuleHealthData] = field(default_factory=dict)
    correction_rate_history: list[dict] = field(default_factory=list)


@dataclass
class CleanExitStatus:
    """Result of checking whether previous session exited cleanly."""
    was_clean: bool
    last_exit_time: str | None = None


def _health_dir(calx_dir: Path) -> Path:
    d = calx_dir / "health"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_state(calx_dir: Path) -> HealthState:
    """Load health state from .calx/health/state.json."""
    path = _health_dir(calx_dir) / "state.json"
    if not path.exists():
        return HealthState()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return HealthState()

    rule_scores = {}
    for rid, rd in data.get("rule_scores", {}).items():
        rule_scores[rid] = RuleHealthData(
            score=rd.get("score", 1.0),
            last_reinforcement=rd.get("last_reinforcement"),
            recurrence_count=rd.get("recurrence_count", 0),
            has_conflict=rd.get("has_conflict", False),
        )

    return HealthState(
        schema_version=data.get("schema_version", "1.0"),
        last_health_check=data.get("last_health_check"),
        rule_scores=rule_scores,
        correction_rate_history=data.get("correction_rate_history", []),
    )


def save_state(calx_dir: Path, state: HealthState) -> None:
    """Save health state to .calx/health/state.json."""
    path = _health_dir(calx_dir) / "state.json"

    scores_dict = {}
    for rid, rd in state.rule_scores.items():
        scores_dict[rid] = {
            "score": rd.score,
            "last_reinforcement": rd.last_reinforcement,
            "recurrence_count": rd.recurrence_count,
            "has_conflict": rd.has_conflict,
        }

    data = {
        "schema_version": state.schema_version,
        "last_health_check": state.last_health_check,
        "rule_scores": scores_dict,
        "correction_rate_history": state.correction_rate_history,
    }

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_clean_exit(calx_dir: Path) -> None:
    """Write clean exit timestamp."""
    path = _health_dir(calx_dir) / ".last_clean_exit"
    path.write_text(
        datetime.now(timezone.utc).isoformat() + "\n",
        encoding="utf-8",
    )


def check_clean_exit(calx_dir: Path) -> CleanExitStatus:
    """Check if the previous session exited cleanly."""
    path = _health_dir(calx_dir) / ".last_clean_exit"
    if not path.exists():
        return CleanExitStatus(was_clean=False)

    try:
        ts = path.read_text(encoding="utf-8").strip()
        return CleanExitStatus(was_clean=True, last_exit_time=ts)
    except OSError:
        return CleanExitStatus(was_clean=False)


def remove_clean_exit(calx_dir: Path) -> None:
    """Remove clean exit marker (called at session start)."""
    path = _health_dir(calx_dir) / ".last_clean_exit"
    if path.exists():
        path.unlink()
