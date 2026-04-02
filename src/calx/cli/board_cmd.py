"""calx board -- display the enforcement board."""
from __future__ import annotations

import click

from calx.cli._http import _fail_unreachable, _get_json


@click.command("board")
def board():
    """Show the enforcement board grouped by status."""
    data = _get_json("/enforce/board")
    if data is None:
        _fail_unreachable()

    groups = data.get("groups", data if isinstance(data, dict) else {})
    if not groups:
        click.echo("Board is empty.")
        return

    for status, items in groups.items():
        click.echo(f"\n[{status}]")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    label = item.get("id") or item.get("title") or str(item)
                    click.echo(f"  - {label}")
                else:
                    click.echo(f"  - {item}")
        else:
            click.echo(f"  {items}")
