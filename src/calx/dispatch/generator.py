"""Dispatch prompt generation for Calx."""

from __future__ import annotations

from pathlib import Path

from calx.core.config import load_config
from calx.core.rules import Rule, format_rule_block, read_rules

_DEFAULT_PROHIBITIONS = [
    "Do NOT commit",
    "Do NOT modify files outside the specified list",
    "Do NOT edit existing files unless explicitly listed — create only",
]


def generate_dispatch(
    calx_dir: Path,
    domain: str,
    task: str,
    files: list[str] | None = None,
    prohibitions: list[str] | None = None,
) -> str:
    """Generate a dispatch prompt for a domain agent.

    Includes: domain rules, task description, file scope, prohibitions, agent naming.
    """
    config = load_config(calx_dir)
    rules = read_rules(calx_dir, domain)

    parts: list[str] = []
    parts.append(f"# Dispatch: {domain}")

    # Rules section
    parts.append("\n## Rules")
    if rules:
        parts.append(_format_rules_section(rules))
    else:
        parts.append("No rules defined for this domain yet.")

    # Task section
    parts.append(f"\n## Task\n{task}")

    # Files section
    if files:
        parts.append("\n## Files")
        for f in files:
            parts.append(f"- {f}")

    # Prohibitions section
    active_prohibitions = prohibitions if prohibitions is not None else _DEFAULT_PROHIBITIONS
    parts.append("\n## Prohibitions")
    for p in active_prohibitions:
        parts.append(f"- {p}")

    # Agent naming
    if config.agent_naming == "self":
        parts.append("\n## Agent Naming\nName yourself based on your domain and role.")
    elif config.agent_naming == "developer":
        parts.append("\n## Agent Naming\nThe developer will name you.")
    # "none" = omit section

    return "\n".join(parts)


def _format_rules_section(rules: list[Rule]) -> str:
    """Format rules for injection into dispatch prompt."""
    blocks: list[str] = []
    for rule in rules:
        if rule.status == "active":  # Only inject active rules
            blocks.append(format_rule_block(rule))
    return "\n".join(blocks) if blocks else "No active rules."
