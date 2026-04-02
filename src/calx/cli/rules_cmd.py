"""calx rules -- query rule health from the enforcement server."""
from __future__ import annotations

import click

from calx.cli._http import _fail_unreachable, _get_json


@click.command("rules")
@click.option("--health", is_flag=True, help="Show decay factors per rule")
@click.option("--role", default=None, help="Filter rules by role")
def rules(health: bool, role: str | None):
    """List rules and their enforcement status."""
    params = f"?role={role}" if role else ""
    data = _get_json(f"/enforce/rule-health{params}")
    if data is None:
        _fail_unreachable()

    items = data.get("rules", data if isinstance(data, list) else [])
    if not items:
        click.echo("No rules found.")
        return

    for r in items:
        rid = r.get("id", "unknown")
        status = r.get("status", "unknown")
        score = r.get("score")
        score_str = f" score={score:.2f}" if score is not None else ""
        click.echo(f"  {rid}: {status}{score_str}")
        if health:
            for factor in r.get("decay_factors", []):
                click.echo(f"    - {factor}")
