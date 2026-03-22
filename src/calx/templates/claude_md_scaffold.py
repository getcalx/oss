"""Generate CLAUDE.md scaffold for new Calx projects."""

from __future__ import annotations

from calx.core.config import CalxConfig


def generate_claude_md_scaffold(
    project_name: str,
    domains: list[str],
    config: CalxConfig | None = None,
    domain_paths: dict[str, str] | None = None,
) -> str:
    """Generate a CLAUDE.md scaffold.

    Only used when the project doesn't already have a CLAUDE.md.
    Provides full structure for Calx behavioral governance.
    """
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

This project uses [Calx](https://calx.sh) for behavioral governance.
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

## What NOT To Do

- Never rewrite a file from scratch — always delta edit.
- Never skip the plan, even for "small" changes.
- Never present findings and ask "want me to fix it?" — plan and build.
- Never do deep code work in the main window when subagents can handle it.
- Never let context compaction happen. Commit and handoff instead.
{domain_section}
## Development

<!-- Add project-specific build, test, and lint commands here -->
"""
