"""Generate CLAUDE.md scaffold for new Calx projects."""

from __future__ import annotations


def generate_claude_md_scaffold(
    project_name: str,
    domains: list[str],
) -> str:
    """Generate a CLAUDE.md scaffold.

    Only used when the project doesn't already have a CLAUDE.md.
    Minimal — just enough structure for Calx to hook into.
    """
    domain_section = ""
    if domains:
        domain_lines = "\n".join(f"- **{d}**" for d in domains)
        domain_section = f"""
## Domains

{domain_lines}
"""

    return f"""# {project_name}

## Calx

This project uses [Calx](https://calx.sh) for behavioral governance.
Rules are loaded automatically at session start via hooks.
Corrections are captured with `calx correct "message"`.
{domain_section}
## Development

<!-- Add project-specific instructions here -->
"""
