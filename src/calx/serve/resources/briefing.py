"""calx://briefing/{surface} -- full state bundle for a surface."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from datetime import datetime, timedelta, timezone

from calx.serve.db.engine import (
    ContextRow,
    CorrectionRow,
    DecisionRow,
    MetricRow,
    PipelineRow,
    RuleRow,
)
from calx.serve.engine.health import auto_deactivate_unhealthy_rules


SURFACE_DOMAIN_MAP: dict[str, list[str]] = {
    "default": ["general"],
}


def _seven_days_ago() -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=7)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_rules_section(rules: list[RuleRow]) -> str:
    if not rules:
        return "## Active Rules\n\nNo active rules."
    lines = ["## Active Rules\n"]
    for r in rules:
        lines.append(f"- **{r.id}** ({r.domain}): {r.rule_text}")
    return "\n".join(lines)


def _format_corrections_section(corrections: list[CorrectionRow]) -> str:
    if not corrections:
        return "## Recent Corrections\n\nNo recent corrections."
    lines = ["## Recent Corrections\n"]
    for c in corrections:
        recurrence = f" (x{c.recurrence_count})" if c.recurrence_count > 1 else ""
        lines.append(f"- **{c.id}** [{c.domain}/{c.category}]{recurrence}: {c.correction}")
    return "\n".join(lines)


def _format_traction_section(metrics: list[MetricRow]) -> str:
    if not metrics:
        return "## Traction\n\nNo metrics recorded."
    lines = ["## Traction\n"]
    for m in metrics:
        # Suppress GitHub stars -- NEVER include
        if "github_star" in m.name.lower() or "stars" in m.name.lower():
            continue
        lines.append(f"- **{m.name}**: {m.value}")
    return "\n".join(lines)


def _format_pipeline_section(pipeline: list[PipelineRow]) -> str:
    if not pipeline:
        return "## Pipeline\n\nNo pipeline entries."
    lines = ["## Pipeline\n"]
    for p in pipeline:
        status = p.status or "unknown"
        gate = f" | Gate: {p.gate}" if p.gate else ""
        lines.append(f"- **{p.investor}**: {status}{gate}")
    return "\n".join(lines)


def _format_decisions_section(decisions: list[DecisionRow]) -> str:
    if not decisions:
        return "## Recent Decisions\n\nNo recent decisions."
    lines = ["## Recent Decisions\n"]
    for d in decisions:
        ctx = f" ({d.context})" if d.context else ""
        lines.append(f"- {d.decision}{ctx}")
    return "\n".join(lines)


def _format_context_section(context: list[ContextRow]) -> str:
    if not context:
        return "## Hot Context\n\nNo active context."
    lines = ["## Hot Context\n"]
    for c in context:
        cat = f" [{c.category}]" if c.category else ""
        lines.append(f"- **{c.key}**{cat}: {c.value}")
    return "\n".join(lines)


def _format_health_section(actions: list[dict]) -> str:
    lines = ["## Rule Health\n"]
    for a in actions:
        if a["action"] == "deactivated":
            lines.append(
                f"- **{a['rule_id']}**: Auto-deactivated "
                f"(health: {a['health_score']:.2f}). "
                f"Reactivate with promote_correction."
            )
        elif a["action"] == "warning":
            lines.append(
                f"- **{a['rule_id']}**: Needs attention "
                f"(health: {a['health_score']:.2f})."
            )
    return "\n".join(lines)


async def build_briefing(db: object, surface: str) -> str:
    """Build the full briefing for a surface."""
    sections = []

    # Auto-deactivate unhealthy rules before building the briefing
    health_actions = await auto_deactivate_unhealthy_rules(db)
    if health_actions:
        sections.append(_format_health_section(health_actions))

    # Active rules filtered by surface-relevant domains
    domains = SURFACE_DOMAIN_MAP.get(surface, ["general"])
    all_rules = await db.find_rules(active_only=True)  # type: ignore[attr-defined]
    relevant_rules = [r for r in all_rules if r.domain in domains]
    sections.append(_format_rules_section(relevant_rules))

    # Recent corrections (last 20, across all surfaces)
    recent = await db.find_corrections(limit=20)  # type: ignore[attr-defined]
    sections.append(_format_corrections_section(recent))

    # Only include sections that have data
    metrics = await db.get_latest_metrics()  # type: ignore[attr-defined]
    if metrics:
        sections.append(_format_traction_section(metrics))

    pipeline = await db.get_pipeline()  # type: ignore[attr-defined]
    if pipeline:
        sections.append(_format_pipeline_section(pipeline[:5]))

    decisions = await db.get_decisions(since=_seven_days_ago())  # type: ignore[attr-defined]
    if decisions:
        sections.append(_format_decisions_section(decisions))

    context = await db.get_context()  # type: ignore[attr-defined]
    if context:
        sections.append(_format_context_section(context))

    return "\n\n".join(sections)


def register_briefing_resource(mcp: object) -> None:
    """Register calx://briefing/{surface} resource."""
    from fastmcp import Context

    @mcp.resource("calx://briefing/{surface}")  # type: ignore[attr-defined]
    async def get_briefing(surface: str, ctx: Context) -> str:
        """Full state bundle for a surface. Fetch at conversation start."""
        db = ctx.lifespan_context["db"]
        return await build_briefing(db, surface)
