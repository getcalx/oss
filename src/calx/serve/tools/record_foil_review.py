"""record_foil_review tool -- record a completed foil review."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from datetime import datetime, timedelta, timezone

from calx.serve.db.engine import FoilReviewRow


async def handle_record_foil_review(
    db: object,
    spec_reference: str,
    reviewer_domain: str,
    verdict: str,
    findings: str | None = None,
    round: int = 1,
) -> dict:
    """Core handler for record_foil_review tool."""
    # Link to active session if one exists
    session_id = None
    active = await db.get_active_session()
    if active:
        session_id = active.id

    review = FoilReviewRow(
        spec_reference=spec_reference,
        reviewer_domain=reviewer_domain,
        verdict=verdict,
        findings=findings,
        round=round,
        session_id=session_id,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    review_id = await db.insert_foil_review(review)
    return {"status": "ok", "review_id": review_id}


async def get_review_gaps(db: object) -> list[dict]:
    """Find domains with >5 corrections and no review in 14+ days."""
    corrections = await db.find_corrections(limit=10000)
    reviews = await db.get_foil_reviews()

    # Count corrections per domain
    domain_counts: dict[str, int] = {}
    for c in corrections:
        domain_counts[c.domain] = domain_counts.get(c.domain, 0) + 1

    # Find latest review per domain
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=14)
    latest_review: dict[str, datetime] = {}
    for r in reviews:
        try:
            review_dt = datetime.fromisoformat(r.created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        domain = r.reviewer_domain
        if domain not in latest_review or review_dt > latest_review[domain]:
            latest_review[domain] = review_dt

    gaps = []
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        if count <= 5:
            continue
        last_review = latest_review.get(domain)
        if last_review and last_review >= threshold:
            continue
        gap = {
            "domain": domain,
            "correction_count": count,
            "last_review_date": last_review.strftime("%Y-%m-%d") if last_review else None,
            "days_since_review": (now - last_review).days if last_review else None,
        }
        gaps.append(gap)
    return gaps


def register_record_foil_review_tool(mcp: object) -> None:
    """Register record_foil_review MCP tool."""
    from fastmcp import Context

    @mcp.tool()
    async def record_foil_review(
        spec_reference: str,
        reviewer_domain: str,
        verdict: str,
        findings: str | None = None,
        round: int = 1,
        ctx: Context = None,
    ) -> dict:
        """Record a completed foil review.

        Args:
            spec_reference: What was reviewed (file path or description).
            reviewer_domain: Which foil profile was used.
            verdict: "approve" or "revise".
            findings: Specific findings with suggested fixes (if revise).
            round: Review round number.
        """
        db = ctx.lifespan_context["db"]
        return await handle_record_foil_review(
            db, spec_reference, reviewer_domain, verdict, findings, round,
        )
