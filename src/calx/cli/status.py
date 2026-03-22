"""calx status — project overview."""
from __future__ import annotations

import json

import click

from calx.core.config import find_calx_dir, load_config
from calx.core.corrections import get_undistilled, materialize
from calx.core.rules import read_all_rules
from calx.core.state import check_clean_exit


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def status(as_json: bool) -> None:
    """Show Calx project status."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project. Run `calx init` first.", err=True)
        raise SystemExit(1)

    config = load_config(calx_dir)
    corrections = materialize(calx_dir)
    undistilled = get_undistilled(calx_dir)
    rules = read_all_rules(calx_dir)
    active_rules = [r for r in rules if r.status == "active"]
    exit_status = check_clean_exit(calx_dir)

    domains_with_rules = len({r.domain for r in active_rules})

    if as_json:
        click.echo(
            json.dumps(
                {
                    "domains": config.domains,
                    "corrections": {
                        "total": len(corrections),
                        "pending_distillation": len(undistilled),
                    },
                    "rules": {
                        "active": len(active_rules),
                        "domains": domains_with_rules,
                    },
                    "last_clean_exit": exit_status.last_exit_time,
                },
                indent=2,
            )
        )
    else:
        click.echo("Calx Status")
        click.echo(f"  Domains: {', '.join(config.domains) if config.domains else '(none)'}")
        click.echo(
            f"  Corrections: {len(corrections)} total, {len(undistilled)} pending distillation"
        )
        click.echo(f"  Rules: {len(active_rules)} active across {domains_with_rules} domain(s)")
        if exit_status.last_exit_time:
            click.echo(f"  Last clean exit: {exit_status.last_exit_time[:19]}")
