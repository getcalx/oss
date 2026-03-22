"""Error floor tracking for Calx."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from calx.core.state import load_state, save_state


@dataclass
class FloorTrajectory:
    current_rate: float
    trend: str  # "declining" | "plateau" | "increasing"
    is_at_floor: bool
    total_sessions: int
    history: list[dict] = field(default_factory=list)
    message: str | None = None


def record_session(calx_dir: Path, corrections_in_session: int) -> None:
    """Record a session's correction count in rate history."""
    state = load_state(calx_dir)
    state.correction_rate_history.append({
        "date": date.today().isoformat(),
        "corrections": corrections_in_session,
    })
    save_state(calx_dir, state)


def get_trajectory(calx_dir: Path) -> FloorTrajectory:
    """Analyze correction rate trajectory."""
    state = load_state(calx_dir)
    history = state.correction_rate_history
    total = len(history)

    if total == 0:
        return FloorTrajectory(
            current_rate=0.0, trend="declining",
            is_at_floor=False, total_sessions=0,
        )

    window = 5
    recent = history[-window:] if len(history) >= window else history
    current_rate = sum(h["corrections"] for h in recent) / len(recent)

    is_plateau = _detect_plateau(history, window)

    if is_plateau:
        trend = "plateau"
    elif total >= 2:
        older = history[:total // 2]
        newer = history[total // 2:]
        old_avg = sum(h["corrections"] for h in older) / len(older) if older else 0
        new_avg = sum(h["corrections"] for h in newer) / len(newer) if newer else 0
        if new_avg < old_avg:
            trend = "declining"
        elif new_avg > old_avg:
            trend = "increasing"
        else:
            trend = "plateau"
    else:
        trend = "declining"

    message = None
    if is_plateau:
        message = (
            f"Your correction rate has stabilized at ~{current_rate:.1f} per session "
            f"over the last {min(total, window * 3)} sessions. This may be your error floor. "
            f"Review your recurring process rules for architectural conversion opportunities."
        )

    return FloorTrajectory(
        current_rate=round(current_rate, 2), trend=trend, is_at_floor=is_plateau,
        total_sessions=total, history=history, message=message,
    )


def _detect_plateau(history: list[dict], window: int = 5) -> bool:
    """Detect plateau: std dev of rolling average < 0.5 for 3+ consecutive windows."""
    if len(history) < window * 3:
        return False

    rolling: list[float] = []
    for i in range(len(history) - window + 1):
        chunk = history[i:i + window]
        avg = sum(h["corrections"] for h in chunk) / window
        rolling.append(avg)

    if len(rolling) < 3:
        return False

    recent_rolling = rolling[-3:]
    try:
        std = statistics.stdev(recent_rolling)
        return std < 0.5
    except statistics.StatisticsError:
        return False
