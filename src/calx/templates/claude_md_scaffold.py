"""Generate CLAUDE.md scaffold and Calx sections for new and existing projects."""

from __future__ import annotations

import re

from calx.core.config import CalxConfig

# Patterns that may conflict with Calx behavioral instructions
_CONFLICT_PATTERNS = [
    (re.compile(r"token.{0,20}(limit|cap|ceiling|budget)", re.IGNORECASE),
     "token discipline reference"),
    (re.compile(r"(do not|don't|never).{0,30}(bash|shell|command)", re.IGNORECASE),
     "bash restriction (may block correction capture)"),
    (re.compile(r"calx", re.IGNORECASE),
     "existing Calx reference"),
    (re.compile(r"compaction|compact.{0,10}context", re.IGNORECASE),
     "context compaction reference"),
]


def scan_conflicts(existing_content: str) -> list[str]:
    """Scan existing CLAUDE.md for potential conflicts with Calx instructions."""
    warnings: list[str] = []
    for line_num, line in enumerate(existing_content.splitlines(), 1):
        for pattern, description in _CONFLICT_PATTERNS:
            if pattern.search(line):
                warnings.append(f"Line {line_num}: found {description}")
                break  # one warning per line
    return warnings


def generate_calx_section(
    domains: list[str],
    config: CalxConfig | None = None,
) -> str:
    """Generate Calx-specific sections for appending to an existing CLAUDE.md."""
    if config is None:
        config = CalxConfig()

    soft_cap = f"{config.token_discipline.soft_cap:,}"
    ceiling = f"{config.token_discipline.ceiling:,}"
    domain_csv = ", ".join(domains) if domains else "general"

    return f"""
## Calx

This project uses [Calx](https://calx.sh) for correction engineering.
Rules are injected automatically at session start via hooks. An orientation
gate blocks file edits until rules have been read.

## Correction Capture

When the developer corrects you — tells you to stop doing something,
change your approach, or points out a mistake — log it immediately:

```bash
calx correct "description of what went wrong and what to do instead" -d DOMAIN
```

Rules:
- Run this via the Bash tool. Do not ask permission. Do not skip it.
- Use the developer's exact words, not a paraphrase.
- If unsure whether something is a correction, log it anyway.
- The -d flag routes it to the right domain. Use the domain most relevant to the mistake.

Available domains: {domain_csv}

## Token Discipline

Soft cap: {soft_cap} tokens. When context feels heavy, commit progress and consider a handoff.
Ceiling: {ceiling} tokens. Stop. Commit everything. Write a handoff note. End the session.
Context compaction permanently destroys learning signal.

## First-time setup

If this is a fresh Calx installation, ask the user what Claude plan they're on
(Max, Pro, Team, or Enterprise) so token limits are set correctly.

Default assumes Max plan. For Pro plan:
`calx config --set token_discipline.soft_cap 80000`
`calx config --set token_discipline.ceiling 100000`
`calx config --set token_discipline.model_context_window 200000`

## What NOT To Do

- Never rewrite a file from scratch — always delta edit.
- Never skip the plan, even for "small" changes.
- Never present findings and ask "want me to fix it?" — plan and build.
- Never do deep code work in the main window when subagents can handle it.
- Never let context compaction happen. Commit and handoff instead.

Calx is early. Feedback, ideas, bugs: @spenceships on X or github.com/getcalx/calx/issues
"""


def generate_claude_md_scaffold(
    project_name: str,
    domains: list[str],
    config: CalxConfig | None = None,
    domain_paths: dict[str, str] | None = None,
) -> str:
    """Generate a full CLAUDE.md scaffold for projects without one."""
    if config is None:
        config = CalxConfig()

    soft_cap = f"{config.token_discipline.soft_cap:,}"
    ceiling = f"{config.token_discipline.ceiling:,}"
    domain_csv = ", ".join(domains) if domains else "general"

    # Domain section
    domain_section = ""
    if domains:
        if domain_paths:
            domain_lines = "\n".join(
                f"- **{d}** — rules at `{domain_paths[d]}/AGENTS.md`"
                if d in domain_paths
                else f"- **{d}**"
                for d in domains
            )
        else:
            domain_lines = "\n".join(f"- **{d}**" for d in domains)
        domain_section = f"""
## Domains

{domain_lines}
"""

    return f"""# {project_name}

## Calx

This project uses [Calx](https://calx.sh) for correction engineering.
Rules are injected automatically at session start via hooks. An orientation
gate blocks file edits until rules have been read.

## Session Flow

1. Rules inject at session start. Read them before doing anything.
2. Understand the task. Ask if anything is unclear.
3. Plan before building. Break work into chunks of 1-3 files.
4. Build each chunk. Run tests after each one.
5. Verify results. Check imports, check integration points.
6. Commit when the chunk is complete and tests pass.

## Correction Capture

When the developer corrects you — tells you to stop doing something,
change your approach, or points out a mistake — log it immediately:

```bash
calx correct "description of what went wrong and what to do instead" -d DOMAIN
```

Rules:
- Run this via the Bash tool. Do not ask permission. Do not skip it.
- Use the developer's exact words, not a paraphrase.
- If unsure whether something is a correction, log it anyway.
- The -d flag routes it to the right domain. Use the domain most relevant to the mistake.

Available domains: {domain_csv}

## Token Discipline

Soft cap: {soft_cap} tokens. When context feels heavy, commit progress and consider a handoff.
Ceiling: {ceiling} tokens. Stop. Commit everything. Write a handoff note. End the session.
Context compaction permanently destroys learning signal. The orchestration model
exists to prevent compaction from ever happening.

## Orchestration

For multi-file or multi-domain tasks:
1. Break into chunks of 1-3 files each.
2. Dispatch subagents for deep code work. Main window orchestrates.
3. Each subagent prompt includes: the AGENTS.md for its target directory,
   exact files in scope, explicit prohibitions (do NOT commit, do NOT
   edit files outside scope).
4. Verify results between dispatch rounds before proceeding.
5. Deep code generation in the main window is an anti-pattern.

## First-time setup

If this is a fresh Calx installation, ask the user what Claude plan they're on
(Max, Pro, Team, or Enterprise) so token limits are set correctly.

Default assumes Max plan. For Pro plan:
`calx config --set token_discipline.soft_cap 80000`
`calx config --set token_discipline.ceiling 100000`
`calx config --set token_discipline.model_context_window 200000`

## What NOT To Do

- Never rewrite a file from scratch — always delta edit.
- Never skip the plan, even for "small" changes.
- Never present findings and ask "want me to fix it?" — plan and build.
- Never do deep code work in the main window when subagents can handle it.
- Never let context compaction happen. Commit and handoff instead.

Calx is early. Feedback, ideas, bugs: @spenceships on X or github.com/getcalx/calx/issues
{domain_section}
## Development

<!-- Add project-specific build, test, and lint commands here -->
"""
