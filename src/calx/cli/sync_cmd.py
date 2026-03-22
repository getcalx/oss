"""calx sync — write AGENTS.md files from .calx/rules/."""

from __future__ import annotations

import click

from calx.core.agents_md import sync_agents_md
from calx.core.config import find_calx_dir


@click.command()
@click.argument("domain", required=False)
def sync(domain: str | None):
    """Sync AGENTS.md files from .calx/rules/."""
    calx_dir = find_calx_dir()
    if calx_dir is None:
        click.echo("No .calx/ directory found. Run `calx init` first.")
        raise SystemExit(1)

    written = sync_agents_md(calx_dir, domain)

    if not written:
        if domain:
            click.echo(f"No domain_paths mapping for '{domain}'. Nothing to sync.")
        else:
            click.echo("No domain_paths configured. Nothing to sync.")
        click.echo("Set paths with: calx config --set domain_paths.api src/api")
        return

    for path in written:
        click.echo(f"  Wrote {path.relative_to(calx_dir.parent)}")
    click.echo(f"Synced {len(written)} AGENTS.md file(s).")
