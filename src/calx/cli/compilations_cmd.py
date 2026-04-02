"""calx compilations -- view compilation stats and candidates."""
from __future__ import annotations

import click

from calx.cli._http import _fail_unreachable, _get_json


@click.command("compilations")
def compilations():
    """Show compilation stats and candidates."""
    data = _get_json("/enforce/compilations")
    if data is None:
        _fail_unreachable()

    # Stats
    stats = data.get("stats", {})
    if stats:
        click.echo("Compilation stats:")
        for key, val in stats.items():
            click.echo(f"  {key}: {val}")

    # Candidates
    candidates = data.get("candidates", [])
    if candidates:
        click.echo(f"\nCandidates ({len(candidates)}):")
        for c in candidates:
            cid = c.get("id") or c.get("rule_id", "unknown")
            reason = c.get("reason") or c.get("message", "")
            click.echo(f"  {cid}: {reason}")
    elif not stats:
        click.echo("No compilation data.")
