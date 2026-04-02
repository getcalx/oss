"""Build anonymous telemetry payload from DB state.

Privacy: NEVER includes text content, file paths, project names.
Only counts, booleans, and environment info.
"""
from __future__ import annotations

import platform
import uuid
from pathlib import Path


async def build_telemetry_payload(
    db: object,
    calx_dir: Path | None = None,
    session_duration_minutes: int = 0,
    tool_call_count: int = 0,
) -> dict:
    """Build the v1 telemetry payload from DB state.

    Returns a dict matching the v1 schema from calx-telemetry-receiving-prd.md.
    Gracefully degrades when DB methods are missing (schema v2 vs v6).
    """
    # Counts
    corrections = await db.find_corrections(limit=10000)
    rules = await db.find_rules(active_only=False)

    plans_list = []
    try:
        active = await db.get_active_plan()
        if active:
            plans_list.append(active)
    except Exception:
        pass

    total_corrections = len(corrections)
    total_rules = len(rules)
    architectural = sum(
        1 for c in corrections
        if getattr(c, "learning_mode", "unknown") == "architectural"
    )
    process = sum(
        1 for c in corrections
        if getattr(c, "learning_mode", "unknown") == "process"
    )

    # Compilation events count
    total_compilations = 0
    try:
        compilation_events = await db.get_compilation_events()
        total_compilations = len(compilation_events)
    except Exception:
        pass

    # Features used (bool: table has rows)
    features_used = {
        "corrections": total_corrections > 0,
        "rules": total_rules > 0,
        "plans": len(plans_list) > 0,
        "dispatch": False,
        "verify": False,
        "compile": total_compilations > 0,
        "review": False,
        "board": False,
    }

    # Check dispatch: any chunk status != "pending"
    if plans_list:
        import json
        for p in plans_list:
            chunks = json.loads(p.chunks) if isinstance(p.chunks, str) else p.chunks
            if any(c.get("status") != "pending" for c in chunks):
                features_used["dispatch"] = True
            if p.wave_verification:
                features_used["verify"] = True

    # Check review
    try:
        reviews = await db.get_foil_reviews()
        features_used["review"] = len(reviews) > 0
    except Exception:
        pass

    # Check board
    try:
        board = await db.get_board_state()
        features_used["board"] = len(board) > 0
    except Exception:
        pass

    # Collapse guard fires
    collapse_fires = 0
    try:
        rows = await db._fetchall(
            "SELECT COUNT(*) FROM telemetry WHERE event_type LIKE '%collapse%'"
        )
        if rows:
            collapse_fires = rows[0][0]
    except Exception:
        pass

    # Dirty exits
    dirty_exits = 0
    try:
        rows = await db._fetchall(
            "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL"
        )
        if rows:
            dirty_exits = rows[0][0]
    except Exception:
        pass

    # Install ID from calx.json
    install_id = str(uuid.uuid4())
    if calx_dir:
        import json
        calx_json_path = calx_dir / "calx.json"
        if calx_json_path.exists():
            try:
                config = json.loads(calx_json_path.read_text())
                install_id = config.get("telemetry", {}).get("install_id", install_id)
            except Exception:
                pass

    # Days since install
    days_since_install = 0
    try:
        row = await db._fetchone("SELECT MIN(started_at) FROM sessions")
        if row and row[0]:
            from datetime import datetime, timezone
            earliest = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days_since_install = max(0, (now - earliest).days)
    except Exception:
        pass

    return {
        "v": 1,
        "event_type": "session_end",
        "install_id": install_id,
        "payload_id": str(uuid.uuid4()),
        "calx_version": _get_calx_version(),
        "os": platform.system().lower(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "days_since_install": days_since_install,
        "session_duration_minutes": session_duration_minutes,
        "tool_call_count": tool_call_count,
        "features_used": features_used,
        "counts": {
            "total_corrections": total_corrections,
            "total_rules": total_rules,
            "total_compilations": total_compilations,
            "total_plans": len(plans_list),
            "architectural_corrections": architectural,
            "process_corrections": process,
        },
        "collapse_guard_fires": collapse_fires,
        "dirty_exits": dirty_exits,
    }


def _get_calx_version() -> str:
    try:
        from calx import __version__
        return __version__
    except Exception:
        return "unknown"
