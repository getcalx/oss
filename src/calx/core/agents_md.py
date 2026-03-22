"""AGENTS.md co-location — sync rules to code directories."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from calx.core.config import load_config
from calx.core.rules import format_rule_block, read_rules


def generate_agents_md(calx_dir: Path, domain: str) -> str:
    """Generate AGENTS.md content from .calx/rules/{domain}.md rules."""
    rules = read_rules(calx_dir, domain)
    title = domain.capitalize()

    lines = [
        f"# AGENTS.md — {title} Conventions",
        "",
        "Managed by Calx. Do not edit directly — changes here will be overwritten.",
        f"Edit rules in `.calx/rules/{domain}.md` and run `calx sync`.",
        "",
    ]

    if rules:
        first_id = rules[0].id
        last_id = rules[-1].id
        today = date.today().isoformat()
        lines.append(
            f"Rule IDs: {first_id} through {last_id} | Last synced: {today}"
        )
        lines.append("")
        for rule in rules:
            lines.append(format_rule_block(rule))
    else:
        lines.append(f"No rules defined yet for `{domain}`.")
        lines.append("")

    return "\n".join(lines)


def sync_agents_md(calx_dir: Path, domain: str | None = None) -> list[Path]:
    """Write AGENTS.md files for configured domains. Returns paths written."""
    config = load_config(calx_dir)
    project_root = calx_dir.parent

    if domain:
        domains_to_sync = [domain] if domain in config.domain_paths else []
    else:
        domains_to_sync = list(config.domain_paths.keys())

    written: list[Path] = []
    for d in domains_to_sync:
        rel_path = config.domain_paths[d]
        target_dir = project_root / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)
        agents_md_path = target_dir / "AGENTS.md"
        content = generate_agents_md(calx_dir, d)
        agents_md_path.write_text(content, encoding="utf-8")
        written.append(agents_md_path)

    return written


def get_agents_md_path(calx_dir: Path, domain: str) -> Path | None:
    """Return the AGENTS.md path for a domain, or None if not configured."""
    config = load_config(calx_dir)
    rel_path = config.domain_paths.get(domain)
    if rel_path is None:
        return None
    project_root = calx_dir.parent
    return project_root / rel_path / "AGENTS.md"
