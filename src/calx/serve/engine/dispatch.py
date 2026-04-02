"""Dispatch prompt assembly for orchestration chunks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

ROLE_PROHIBITIONS = {
    "builder": "Do NOT make product decisions, orchestrate other agents, or modify files outside your scope.",
    "reviewer": "Do NOT write implementation code. Produce binary APPROVE or REVISE with specific findings and suggested fixes.",
    "orchestrator": "Do NOT write implementation code. Dispatch, verify, and commit.",
}

ROLE_DESCRIPTIONS = {
    "builder": "You are a builder. Write implementation code, tests, and documentation as specified. Stay within your file scope.",
    "reviewer": "You are a reviewer. Evaluate the work product against acceptance criteria. Produce APPROVE or REVISE with actionable findings.",
    "orchestrator": "You are an orchestrator. Dispatch work to builders, verify results, and manage the plan lifecycle.",
}


async def build_dispatch_prompt(db: Any, plan: dict, chunk: dict) -> str:
    """Assemble a complete dispatch prompt for a chunk.

    Includes: role assignment, task description, domain rules (filtered by role),
    files, acceptance criteria, prohibitions, worktree advisory.
    """
    role = chunk.get("role", "builder")
    task_description = plan.get("task_description", "")
    domain = chunk.get("domain", "general")

    # Fetch and filter rules
    rules = await db.find_rules(domain=domain, active_only=True)
    if role:
        rules = [r for r in rules if r.role is None or r.role == role]

    # Build rules section
    rules_lines = []
    for r in rules:
        rules_lines.append(f"- [{r.id}] {r.rule_text}")
    rules_section = "\n".join(rules_lines) if rules_lines else "(no domain rules)"

    # Files section
    files = chunk.get("files", [])
    files_section = "\n".join(f"- {f}" for f in files) if files else "(no files specified)"

    # Acceptance criteria
    criteria = chunk.get("acceptance_criteria", [])
    criteria_lines = []
    for i, c in enumerate(criteria, 1):
        criteria_lines.append(f"{i}. {c}")
    criteria_section = "\n".join(criteria_lines) if criteria_lines else "(none)"

    # Prohibitions
    prohib_lines = [
        "- Do NOT modify files outside the list above",
        "- Do NOT commit changes",
        "- Delta edits only (Edit tool, not Write tool for existing files)",
    ]
    for p in chunk.get("prohibitions", []):
        prohib_lines.append(f"- {p}")
    role_prohib = ROLE_PROHIBITIONS.get(role)
    if role_prohib:
        prohib_lines.append(f"- {role_prohib}")
    prohibitions_section = "\n".join(prohib_lines)

    # Role description
    role_desc = ROLE_DESCRIPTIONS.get(role, f"You are a {role}.")

    # Worktree advisory
    all_new = all(not Path(f).exists() for f in files) if files else True
    any_existing = any(Path(f).exists() for f in files) if files else False

    if any_existing:
        worktree_advisory = "Warning: edits to existing files must be verified in the main window."
    elif all_new and files:
        worktree_advisory = "Recommended: run this agent in an isolated worktree."
    else:
        worktree_advisory = ""

    prompt = f"""You are a {role} working on: {task_description}

## Your Task: {chunk.get('description', '')}

## Rules
{rules_section}

## Files to create/modify
{files_section}

## Acceptance Criteria
{criteria_section}

## Prohibitions
{prohibitions_section}

## Role: {role}
{role_desc}

## Worktree Advisory
{worktree_advisory}"""

    return prompt


async def build_redispatch_prompt(db: Any, plan: dict, chunk: dict) -> str:
    """Assemble an updated prompt for a blocked chunk.

    Includes: what was completed, what failed and why, remaining criteria,
    block reason, original prohibitions.
    """
    role = chunk.get("role", "builder")
    task_description = plan.get("task_description", "")
    domain = chunk.get("domain", "general")
    block_reason = chunk.get("block_reason", "unknown")
    completed_criteria = set(chunk.get("completed_criteria", []))

    # Remaining acceptance criteria
    all_criteria = chunk.get("acceptance_criteria", [])
    remaining = [c for c in all_criteria if c not in completed_criteria]

    # Fetch and filter rules
    rules = await db.find_rules(domain=domain, active_only=True)
    if role:
        rules = [r for r in rules if r.role is None or r.role == role]

    rules_lines = []
    for r in rules:
        rules_lines.append(f"- [{r.id}] {r.rule_text}")
    rules_section = "\n".join(rules_lines) if rules_lines else "(no domain rules)"

    # Files
    files = chunk.get("files", [])
    files_section = "\n".join(f"- {f}" for f in files) if files else "(no files specified)"

    # Remaining criteria
    remaining_lines = []
    for i, c in enumerate(remaining, 1):
        remaining_lines.append(f"{i}. {c}")
    remaining_section = "\n".join(remaining_lines) if remaining_lines else "(all criteria met)"

    # Completed criteria
    completed_lines = []
    for c in sorted(completed_criteria):
        completed_lines.append(f"- [DONE] {c}")
    completed_section = "\n".join(completed_lines) if completed_lines else "(none completed)"

    # Prohibitions
    prohib_lines = [
        "- Do NOT modify files outside the list above",
        "- Do NOT commit changes",
        "- Delta edits only (Edit tool, not Write tool for existing files)",
    ]
    for p in chunk.get("prohibitions", []):
        prohib_lines.append(f"- {p}")
    role_prohib = ROLE_PROHIBITIONS.get(role)
    if role_prohib:
        prohib_lines.append(f"- {role_prohib}")
    prohibitions_section = "\n".join(prohib_lines)

    prompt = f"""REDISPATCH: You are a {role} working on: {task_description}

## Your Task: {chunk.get('description', '')}

## Block Reason
{block_reason}

## What Was Completed
{completed_section}

## Remaining Acceptance Criteria
{remaining_section}

## Rules
{rules_section}

## Files to create/modify
{files_section}

## Prohibitions
{prohibitions_section}

Fix the issues described in the block reason and complete the remaining acceptance criteria."""

    return prompt
