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
from calx.templates.claude_md_scaffold import generate_claude_md_scaffold
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
@click.option("--non-interactive", is_flag=True, help="Skip prompts, use defaults")
@click.option("--phone-home", is_flag=True, help="Enable anonymous usage tracking")
def init(domains: tuple[str, ...], non_interactive: bool, phone_home: bool):
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
    elif non_interactive:
        domain_list = detected if detected else ["general"]
    else:
        if detected:
            click.echo(f"Detected domains: {', '.join(detected)}")
            confirmed = click.confirm("Use these domains?", default=True)
            if confirmed:
                domain_list = detected
            else:
                raw = click.prompt("Enter domains (comma-separated)", default="general")
                domain_list = [d.strip() for d in raw.split(",") if d.strip()]
        else:
            raw = click.prompt("Enter domains (comma-separated)", default="general")
            domain_list = [d.strip() for d in raw.split(",") if d.strip()]

    # Agent naming
    if non_interactive:
        agent_naming = "self"
    else:
        click.echo("\nAgent naming preference:")
        click.echo("  1. self — Agent names itself")
        click.echo("  2. developer — You name the agent")
        click.echo("  3. none — No naming")
        choice = click.prompt("Choice", default="1", type=click.Choice(["1", "2", "3"]))
        agent_naming = {"1": "self", "2": "developer", "3": "none"}[choice]

    # Referral source
    if non_interactive:
        referral = ""
    else:
        click.echo("\nHow did you hear about Calx?")
        click.echo("  1. paper  2. colleague  3. github  4. social  5. other")
        ref_choice = click.prompt(
            "Choice", default="5", type=click.Choice(["1", "2", "3", "4", "5"])
        )
        referral = {"1": "paper", "2": "colleague", "3": "github", "4": "social", "5": "other"}[
            ref_choice
        ]

    # Claude plan → token discipline
    plan_thresholds = {
        "1": ("max", 200_000, 250_000, 1_000_000),
        "2": ("pro", 80_000, 100_000, 200_000),
        "3": ("team", 200_000, 250_000, 1_000_000),
        "4": ("enterprise", 150_000, 200_000, 500_000),
    }
    if non_interactive:
        # Default to Pro (conservative) — users can change via calx config
        td_soft, td_ceil, td_window = 80_000, 100_000, 200_000
    else:
        click.echo("\nClaude plan:")
        click.echo("  1. Max (1M context)")
        click.echo("  2. Pro (200k context)")
        click.echo("  3. Team (1M context)")
        click.echo("  4. Enterprise")
        plan_choice = click.prompt("Choice", default="1", type=click.Choice(["1", "2", "3", "4"]))
        _, td_soft, td_ceil, td_window = plan_thresholds[plan_choice]

    from calx.core.config import TokenDiscipline
    token_discipline = TokenDiscipline(
        soft_cap=td_soft, ceiling=td_ceil, model_context_window=td_window,
    )

    # Build domain_paths from detected paths for the selected domains
    domain_paths = {d: detected_paths[d] for d in domain_list if d in detected_paths}

    # Create config
    config = default_config(domain_list, phone_home=phone_home, domain_paths=domain_paths)
    config.token_discipline = token_discipline
    config.agent_naming = agent_naming
    config.referral_source = referral

    # Create directory structure
    calx_dir.mkdir(parents=True, exist_ok=True)
    (calx_dir / "rules").mkdir(exist_ok=True)
    (calx_dir / "health").mkdir(exist_ok=True)
    (calx_dir / "hooks").mkdir(exist_ok=True)
    (calx_dir / "method").mkdir(exist_ok=True)

    # Save config
    save_config(calx_dir, config)

    # .gitignore for .calx/ — corrections and health state are local
    gitignore = calx_dir / ".gitignore"
    gitignore.write_text(
        "# Commit: calx.json, rules/, method/, README\n"
        "# Ignore: local state and event logs\n"
        "corrections.jsonl\n"
        "health/\n"
        "hooks/\n",
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

    # Scaffold CLAUDE.md if none exists
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.exists():
        scaffold = generate_claude_md_scaffold(project_dir.name, domain_list)
        claude_md.write_text(scaffold, encoding="utf-8")
        click.echo("Created CLAUDE.md scaffold")

    # Phone home — send install event
    from calx.core.phone_home import send_event

    send_event(calx_dir, "install")

    if config.phone_home:
        click.echo(
            "Anonymous usage tracking enabled. "
            "Disable with: calx config --set phone_home false"
        )

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
