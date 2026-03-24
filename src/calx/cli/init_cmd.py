"""calx init — project initialization."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from calx.core.agents_md import sync_agents_md
from calx.core.config import default_config, save_config
from calx.core.rules import Rule, write_rule
from calx.hooks.installer import install_hooks
from calx.templates.calx_readme import generate_calx_readme
from calx.templates.claude_md_scaffold import (
    generate_calx_section,
    generate_claude_md_scaffold,
    scan_conflicts,
)
from calx.templates.method_docs import dispatch, how_we_document, orchestration, review

_DOMAIN_PATTERNS = {
    "api",
    "services",
    "models",
    "db",
    "tests",
    "frontend",
    "backend",
    "core",
    "lib",
    "utils",
    "web",
    "mobile",
    "infra",
}


@click.command()
@click.option("--domains", "-d", multiple=True, help="Domains to configure")
def init(domains: tuple[str, ...]):
    """Initialize Calx in the current project."""
    project_dir = Path.cwd()
    calx_dir = project_dir / ".calx"

    if calx_dir.exists():
        click.echo("Calx is already initialized in this project.")
        click.echo("Run `calx config` to change settings.")
        return

    # Auto-detect domains
    detected, detected_paths = _detect_domains(project_dir)

    if domains:
        # Split comma-separated values: -d "api,frontend" or -d api -d frontend
        domain_list = [
            d.strip() for raw in domains for d in raw.split(",") if d.strip()
        ]
    else:
        domain_list = detected if detected else ["general"]

    # Build domain_paths from detected paths for the selected domains
    domain_paths = {d: detected_paths[d] for d in domain_list if d in detected_paths}

    # Create config with defaults
    config = default_config(domain_list, domain_paths=domain_paths)

    # Create directory structure
    calx_dir.mkdir(parents=True, exist_ok=True)
    (calx_dir / "rules").mkdir(exist_ok=True)
    (calx_dir / "health").mkdir(exist_ok=True)
    (calx_dir / "method").mkdir(exist_ok=True)

    # Save config
    save_config(calx_dir, config)

    # .gitignore for .calx/ — corrections and health state are local
    gitignore = calx_dir / ".gitignore"
    gitignore.write_text(
        "# Commit: calx.json, rules/, method/, README\n"
        "# Ignore: local state and event logs\n"
        "corrections.jsonl\n"
        "health/\n",
        encoding="utf-8",
    )

    # Generate README
    readme_content = generate_calx_readme(domain_list)
    (calx_dir / "README").write_text(readme_content, encoding="utf-8")

    # Write method documentation
    method_dir = calx_dir / "method"
    (method_dir / "how-we-document.md").write_text(how_we_document(), encoding="utf-8")
    (method_dir / "orchestration.md").write_text(orchestration(), encoding="utf-8")
    (method_dir / "dispatch.md").write_text(dispatch(), encoding="utf-8")
    (method_dir / "review.md").write_text(review(), encoding="utf-8")

    # Seed example rule
    first_domain = domain_list[0] if domain_list else "general"
    seed_rule = Rule(
        id=f"{first_domain}-R001",
        domain=first_domain,
        type="process",
        source_corrections=["seed"],
        added=date.today().isoformat(),
        status="active",
        title="Never rewrite a file from scratch — always delta edit",
        body=(
            "When modifying existing files, use targeted edits (Edit tool) rather than\n"
            "full rewrites (Write tool). Full rewrites lose accumulated content and\n"
            "introduce inconsistencies. This rule is pre-loaded so you can see the\n"
            "injection mechanism work immediately."
        ),
    )
    write_rule(calx_dir, seed_rule)

    # Sync AGENTS.md files to domain directories
    agents_written = sync_agents_md(calx_dir)
    for agents_path in agents_written:
        click.echo(f"  Wrote {agents_path.relative_to(project_dir)}")

    # Install hooks
    result = install_hooks(project_dir)

    # CLAUDE.md: scaffold or append Calx section
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.exists():
        scaffold = generate_claude_md_scaffold(
            project_dir.name, domain_list, config=config, domain_paths=domain_paths,
        )
        claude_md.write_text(scaffold, encoding="utf-8")
        click.echo("Created CLAUDE.md scaffold")
    else:
        existing = claude_md.read_text(encoding="utf-8")
        conflicts = scan_conflicts(existing)
        for warning in conflicts:
            click.echo(f"  Warning: {warning}")
        calx_section = generate_calx_section(domain_list, config=config)
        claude_md.write_text(existing.rstrip() + "\n" + calx_section, encoding="utf-8")
        click.echo("Added Calx section to existing CLAUDE.md")

    # Summary
    click.echo("\nCalx initialized!")
    click.echo(f"  Domains: {', '.join(domain_list)}")
    installed = len(result.hooks_installed)
    skipped = len(result.hooks_skipped)
    click.echo(f"  Hooks: {installed} installed, {skipped} skipped")
    click.echo(f"  Seed rule: {seed_rule.id}")
    click.echo("\nRun `calx status` to see your setup.")


def _detect_domains(project_dir: Path) -> tuple[list[str], dict[str, str]]:
    """Auto-detect domains from directory structure.

    Returns (sorted domain names, domain->relative_path mapping).
    """
    found: dict[str, str] = {}

    # Check top-level
    for item in project_dir.iterdir():
        if item.is_dir() and item.name in _DOMAIN_PATTERNS:
            found[item.name] = item.name

    # Check src/ if it exists
    src_dir = project_dir / "src"
    if src_dir.is_dir():
        for item in src_dir.iterdir():
            if item.is_dir() and item.name in _DOMAIN_PATTERNS and item.name not in found:
                found[item.name] = f"src/{item.name}"

    names = sorted(found.keys())
    paths = {k: found[k] for k in names}
    return names, paths
