"""Shared correction lifecycle logic.
Orchestrates: quarantine -> recurrence -> promotion.
Used by both MCP tools and (future) CLI commands.
"""
from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime, timezone

import aiosqlite

from calx.serve.db.engine import CorrectionRow, DatabaseEngine
from calx.serve.engine.similarity import extract_keywords

MAX_ID_RETRIES = 3


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _next_correction_id(db: DatabaseEngine) -> str:
    """Generate the next sequential correction ID.

    Uses max_correction_num() which counts ALL corrections including quarantined,
    avoiding ID collisions when quarantined rows are skipped by find_corrections().
    """
    max_num = await db.max_correction_num()
    return f"C{max_num + 1:03d}"


async def log_correction(
    db: DatabaseEngine,
    correction: str,
    domain: str,
    category: str,
    severity: str = "medium",
    confidence: str = "medium",
    surface: str = "unknown",
    task_context: str | None = None,
    briefing_state: str | None = None,
    recurrence_of: str | None = None,
    root_correction_id: str | None = None,
) -> str:
    """Create a new correction record. Returns the correction ID.

    Retries on UNIQUE constraint violation to handle concurrent ID generation.
    """
    keywords = json.dumps(sorted(extract_keywords(correction)))

    for attempt in range(MAX_ID_RETRIES):
        correction_id = await _next_correction_id(db)
        row = CorrectionRow(
            id=correction_id,
            uuid=uuid_mod.uuid4().hex,
            correction=correction,
            domain=domain,
            category=category,
            severity=severity,
            confidence=confidence,
            surface=surface,
            task_context=task_context,
            briefing_state=briefing_state,
            keywords=keywords,
            recurrence_of=recurrence_of,
            root_correction_id=root_correction_id or recurrence_of,
            created_at=_now(),
            updated_at=_now(),
        )
        try:
            await db.insert_correction(row)
            return correction_id
        except (aiosqlite.IntegrityError, Exception) as e:
            if "UNIQUE" in str(e) and attempt < MAX_ID_RETRIES - 1:
                continue
            raise
    # Unreachable, but satisfies type checkers
    raise RuntimeError("Failed to generate unique correction ID")


async def log_quarantined_correction(
    db: DatabaseEngine,
    correction: str,
    domain: str,
    category: str,
    severity: str,
    confidence: str,
    surface: str,
    task_context: str | None,
    quarantine_reason: str,
) -> dict:
    """Log a correction that failed quarantine scanning.

    Retries on UNIQUE constraint violation to handle concurrent ID generation.
    """
    keywords = json.dumps(sorted(extract_keywords(correction)))

    for attempt in range(MAX_ID_RETRIES):
        correction_id = await _next_correction_id(db)
        row = CorrectionRow(
            id=correction_id,
            uuid=uuid_mod.uuid4().hex,
            correction=correction,
            domain=domain,
            category=category,
            severity=severity,
            confidence=confidence,
            surface=surface,
            task_context=task_context,
            keywords=keywords,
            quarantined=1,
            quarantine_reason=quarantine_reason,
            created_at=_now(),
            updated_at=_now(),
        )
        try:
            await db.insert_correction(row)
            return {
                "status": "quarantined",
                "correction_id": correction_id,
                "reason": quarantine_reason,
            }
        except (aiosqlite.IntegrityError, Exception) as e:
            if "UNIQUE" in str(e) and attempt < MAX_ID_RETRIES - 1:
                continue
            raise
    raise RuntimeError("Failed to generate unique correction ID")
