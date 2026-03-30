"""log_correction tool -- record a behavioral correction from any surface."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

import time
from collections import defaultdict

from calx.serve.engine import correction_engine
from calx.serve.engine.promotion import check_auto_promotion, PROMOTION_THRESHOLD
from calx.serve.engine.quarantine import quarantine_scan
from calx.serve.engine.recurrence import check_recurrence

VALID_CATEGORIES = {"factual", "tonal", "structural", "procedural"}
VALID_SEVERITIES = {"low", "medium", "high"}
VALID_CONFIDENCES = {"low", "medium", "high"}

_RATE_LIMIT = 60  # max corrections per surface per minute
_RATE_WINDOW = 60  # seconds
_surface_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(surface: str) -> bool:
    """Returns True if rate limited."""
    now = time.monotonic()
    timestamps = _surface_timestamps[surface]
    # Prune old timestamps
    _surface_timestamps[surface] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_surface_timestamps[surface]) >= _RATE_LIMIT:
        return True
    _surface_timestamps[surface].append(now)
    return False


def _validate_enums(category: str, severity: str, confidence: str) -> str | None:
    """Validate enum fields. Returns error message or None."""
    if category not in VALID_CATEGORIES:
        return f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
    if severity not in VALID_SEVERITIES:
        return f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
    if confidence not in VALID_CONFIDENCES:
        return f"Invalid confidence '{confidence}'. Must be one of: {', '.join(sorted(VALID_CONFIDENCES))}"
    return None


async def handle_log_correction(
    db: object,
    correction: str,
    domain: str,
    category: str,
    severity: str = "medium",
    confidence: str = "medium",
    surface: str = "unknown",
    task_context: str | None = None,
) -> dict:
    """Core handler for log_correction tool."""
    # Rate limit per surface
    if _check_rate_limit(surface):
        return {
            "status": "rate_limited",
            "message": f"Rate limit exceeded for surface '{surface}'. Max {_RATE_LIMIT} corrections per minute.",
        }

    # Validate enums
    error = _validate_enums(category, severity, confidence)
    if error:
        return {"status": "error", "message": error}

    # Content quarantine check
    qr = quarantine_scan(correction)
    if qr.flagged:
        return await correction_engine.log_quarantined_correction(
            db, correction, domain, category, severity,
            confidence, surface, task_context, qr.reason,
        )

    # Wrap the full recurrence/insert/promotion flow in a transaction
    async with db.transaction():  # type: ignore[attr-defined]
        # Check recurrence
        recurrence = await check_recurrence(db, correction, domain)

        if recurrence.is_match:
            # Atomically increment existing correction's recurrence count
            new_count = await db.increment_recurrence_count(recurrence.original_id)  # type: ignore[attr-defined]
            # Log the new correction linked to original
            correction_id = await correction_engine.log_correction(
                db, correction, domain, category, severity,
                confidence, surface, task_context,
                recurrence_of=recurrence.original_id,
                root_correction_id=recurrence.original_id,
            )
            # Check progressive promotion
            if new_count >= PROMOTION_THRESHOLD:
                await check_auto_promotion(db, recurrence.original_id)

            return {
                "status": "recurrence",
                "correction_id": correction_id,
                "original_id": recurrence.original_id,
                "count": new_count,
            }
        else:
            correction_id = await correction_engine.log_correction(
                db, correction, domain, category, severity,
                confidence, surface, task_context,
            )
            return {"status": "ok", "correction_id": correction_id}


def register_log_correction_tool(mcp: object) -> None:
    """Register log_correction MCP tool."""
    from fastmcp import Context

    @mcp.tool()  # type: ignore[attr-defined]
    async def log_correction(
        correction: str,
        domain: str,
        category: str,
        severity: str = "medium",
        confidence: str = "medium",
        surface: str = "unknown",
        task_context: str | None = None,
        ctx: Context = None,
    ) -> dict:
        """Record a behavioral correction.

        Args:
            correction: What went wrong and what to do instead.
            domain: Routing domain (e.g., coordination, strategy, content, general).
            category: factual, tonal, structural, or procedural.
            severity: low, medium, or high.
            confidence: low (never auto-promote), medium (queue for review), high (auto-promote after threshold).
            surface: Which surface originated this (e.g., general, api, frontend, cli).
            task_context: Optional description of the task during which this correction occurred.
        """
        db = ctx.lifespan_context["db"]
        return await handle_log_correction(
            db, correction, domain, category, severity,
            confidence, surface, task_context,
        )
