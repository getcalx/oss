"""calx://briefing/{surface} -- full state bundle for a surface."""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime-evaluated type annotations to detect Context params.

from datetime import datetime, timezone

from calx.serve.db.engine import (
    CorrectionRow,
    HandoffRow,
    RuleRow,
)
from calx.serve.engine.bootstrap import bootstrap_session
from calx.serve.engine.compilation import get_compilation_stats, get_compilation_candidates


SURFACE_DOMAIN_MAP: dict[str, list[str]] = {}


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


def _format_handoff_section(handoff: HandoffRow | None) -> str:
    """Format 'Since Last Session' section from latest handoff."""
    if not handoff:
        return "## Since Last Session\n\nNo prior session handoff."
    lines = ["## Since Last Session\n"]
    lines.append(f"**What changed:** {handoff.what_changed}")
    if handoff.what_others_need:
        lines.append(f"**What others need:** {handoff.what_others_need}")
    if handoff.decisions_deferred:
        lines.append(f"**Decisions deferred:** {handoff.decisions_deferred}")
    if handoff.next_priorities:
        lines.append(f"**Next priorities:** {handoff.next_priorities}")
    return "\n".join(lines)


def _format_compilation_stats_section(stats: dict) -> str:
    """Format compilation statistics section."""
    if stats.get("total_compilations", 0) == 0:
        return "## Compilation Stats\n\nNo compilations yet."
    lines = ["## Compilation Stats\n"]
    lines.append(f"- Total: {stats['total_compilations']}")
    lines.append(f"- Verified: {stats['verified']}")
    lines.append(f"- In verification: {stats['in_verification']}")
    lines.append(f"- Failed: {stats['failed']}")
    if stats.get("success_rate") is not None:
        lines.append(f"- Success rate: {stats['success_rate']:.0%}")
    lines.append(f"- Architectural recurrence rate: {stats.get('architectural_recurrence_rate', 0):.1f}")
    lines.append(f"- Process recurrence rate: {stats.get('process_recurrence_rate', 0):.1f}")
    return "\n".join(lines)


def _format_orchestration_section(plan) -> str:
    """Format orchestration protocol and plan state."""
    import json
    from calx.serve.engine.orchestration import compute_waves, get_next_dispatchable

    if not plan:
        return ""

    lines = ["## Orchestration Protocol\n"]
    lines.append("You are an orchestrator. Read the plan. Dispatch agents for implementation. "
                 "Verify results. Commit. Do not write implementation code in this window.")
    lines.append("Dispatch one task per agent. Each agent gets its own context window with its own rules.")
    lines.append("")

    chunks = json.loads(plan.chunks)
    edges = json.loads(plan.dependency_edges)
    waves = compute_waves(chunks, edges)

    lines.append(f"**Plan:** {plan.task_description}")
    lines.append(f"**Phase:** {plan.phase}")
    lines.append(f"**Wave:** {plan.current_wave}/{len(waves)}")

    done = sum(1 for c in chunks if c.get("status") == "done")
    total = len(chunks)
    lines.append(f"**Chunks:** {done}/{total} done")

    # Blocked chunks
    blocked = [c for c in chunks if c.get("status") == "blocked"]
    if blocked:
        lines.append("")
        lines.append("### Blocked")
        for c in blocked:
            lines.append(f"- **{c['id']}**: {c.get('block_reason', 'unknown')}. Re-dispatch with `calx redispatch {c['id']}`.")

    # Next dispatchable
    next_disp = get_next_dispatchable(chunks, edges, plan.current_wave - 1)
    if next_disp:
        lines.append("")
        lines.append("### Next Dispatchable")
        for cid in next_disp:
            chunk = next((c for c in chunks if c["id"] == cid), None)
            desc = chunk.get("description", "") if chunk else ""
            lines.append(f"- `calx dispatch {cid}`: {desc}")

    # Phase guidance
    from calx.serve.engine.orchestration import PHASE_ORDER
    phase_idx = PHASE_ORDER.index(plan.phase)
    if plan.phase == "spec":
        lines.append("\n**Next:** Set spec_file on the plan to advance to test phase.")
    elif plan.phase == "test":
        lines.append("\n**Next:** Set test_files on the plan to advance to chunk phase.")
    elif plan.phase == "chunk":
        lines.append("\n**Next:** Define chunks with dependency graph to advance to plan phase.")
    elif plan.phase == "plan":
        lines.append("\n**Next:** Record a foil review (verdict: approve) to advance to build phase.")
    elif plan.phase == "build":
        if next_disp:
            lines.append(f"\n**Next:** Dispatch {len(next_disp)} chunk(s).")
        else:
            lines.append("\n**Next:** All chunks in current wave dispatched. Complete them to advance to verify.")
    elif plan.phase == "verify":
        lines.append(f"\n**Next:** Run `calx verify {plan.current_wave}` to verify wave {plan.current_wave}.")
    elif plan.phase == "commit":
        lines.append("\n**Next:** Commit verified work.")

    return "\n".join(lines)


def _format_compilation_candidates_section(candidates: list[RuleRow]) -> str:
    """Format compilation candidates section."""
    if not candidates:
        return "## Compilation Candidates\n\nNo compilation candidates."
    lines = ["## Compilation Candidates\n"]
    for r in candidates:
        lines.append(f"- **{r.id}** ({r.domain}): {r.rule_text}")
    return "\n".join(lines)


async def build_briefing(db: object, surface: str) -> str:
    """Build the full briefing for a surface."""
    sections = []

    # Active rules filtered by surface-relevant domains
    domains = SURFACE_DOMAIN_MAP.get(surface, ["general"])
    all_rules = await db.find_rules(active_only=True)  # type: ignore[attr-defined]
    relevant_rules = [r for r in all_rules if r.domain in domains]
    sections.append(_format_rules_section(relevant_rules))

    # Recent corrections (last 20, across all surfaces)
    recent = await db.find_corrections(limit=20)  # type: ignore[attr-defined]
    sections.append(_format_corrections_section(recent))

    # Bootstrap data (handoff, dirty exit, health warnings)
    bootstrap = await bootstrap_session(db)

    # Since Last Session
    sections.append(_format_handoff_section(bootstrap.last_handoff))

    # Dirty exit warning
    if bootstrap.dirty_exit:
        sections.insert(0, f"## Dirty Exit Detected\n\nPrevious session ({bootstrap.dirty_session_id}) did not end cleanly.")

    # Health warnings
    if bootstrap.rules_needing_attention:
        lines = ["## Rules Needing Attention\n"]
        for r in bootstrap.rules_needing_attention:
            lines.append(f"- **{r.id}** ({r.health_status}, score={r.health_score:.1f}): {r.rule_text}")
        sections.append("\n".join(lines))

    # Compilation stats
    stats = await get_compilation_stats(db)
    sections.append(_format_compilation_stats_section(stats))

    # Compilation candidates
    candidates = await get_compilation_candidates(db)
    sections.append(_format_compilation_candidates_section(candidates))

    # Review status
    from calx.serve.tools.record_foil_review import get_review_gaps
    gaps = await get_review_gaps(db)
    if gaps:
        lines = ["## Review Status\n"]
        for g in gaps:
            last = f" (last review: {g['last_review_date']})" if g["last_review_date"] else " (never reviewed)"
            lines.append(f"- **{g['domain']}**: {g['correction_count']} corrections{last}")
        sections.append("\n".join(lines))

    # Orchestration (plan state + protocol)
    plan = await db.get_active_plan()
    orchestration = _format_orchestration_section(plan)
    if orchestration:
        sections.append(orchestration)

    return "\n\n".join(sections)


def register_briefing_resource(mcp: object) -> None:
    """Register calx://briefing/{surface} resource."""
    from fastmcp import Context

    @mcp.resource("calx://briefing/{surface}")  # type: ignore[attr-defined]
    async def get_briefing(surface: str, ctx: Context) -> str:
        """Full state bundle for a surface. Fetch at conversation start."""
        db = ctx.lifespan_context["db"]
        return await build_briefing(db, surface)
