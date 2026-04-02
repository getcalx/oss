"""calx review -- foil reviews, review gaps, and review history."""
from __future__ import annotations

from pathlib import Path

import click

from calx.cli._http import _fail_unreachable, _get_json, _post_json


@click.command("review")
@click.option("--foil", default=None, help="Foil name for review prompt or recording")
@click.option("--file", "file_path", default=None, type=click.Path(), help="File path to review")
@click.option("--record", is_flag=True, help="Record a foil review verdict")
@click.option("--verdict", default=None, help="Verdict for --record (e.g. pass, fail, partial)")
@click.option("--history", is_flag=True, help="Show foil review history")
@click.option("--gaps", is_flag=True, help="Show review gaps")
def review(
    foil: str | None,
    file_path: str | None,
    record: bool,
    verdict: str | None,
    history: bool,
    gaps: bool,
):
    """Manage foil reviews and review gaps."""
    if gaps:
        data = _get_json("/enforce/review-gaps")
        if data is None:
            _fail_unreachable()
        gap_list = data.get("gaps", data if isinstance(data, list) else [])
        if not gap_list:
            click.echo("No review gaps found.")
            return
        click.echo("Review gaps:")
        for g in gap_list:
            if isinstance(g, dict):
                label = g.get("id") or g.get("rule_id") or str(g)
                click.echo(f"  - {label}")
            else:
                click.echo(f"  - {g}")
        return

    if history:
        data = _get_json("/enforce/foil-reviews")
        if data is None:
            _fail_unreachable()
        reviews = data.get("reviews", data if isinstance(data, list) else [])
        if not reviews:
            click.echo("No review history.")
            return
        for r in reviews:
            foil_name = r.get("foil", "unknown")
            v = r.get("verdict", "unknown")
            ts = r.get("timestamp", "")
            click.echo(f"  {foil_name}: {v} ({ts})")
        return

    if record:
        if not foil:
            click.echo("--foil is required with --record.", err=True)
            raise SystemExit(1)
        if not verdict:
            click.echo("--verdict is required with --record.", err=True)
            raise SystemExit(1)
        result = _post_json("/enforce/foil-review", {
            "foil": foil,
            "verdict": verdict,
        })
        if result is None:
            _fail_unreachable()
        click.echo(result.get("message", "Review recorded."))
        return

    if foil and file_path:
        # Read foil definition and output as review prompt
        foil_path = Path(".calx") / "foils" / f"{foil}.md"
        if not foil_path.exists():
            click.echo(f"Foil definition not found: {foil_path}", err=True)
            raise SystemExit(1)
        foil_content = foil_path.read_text()
        click.echo(f"--- Review prompt for foil '{foil}' on {file_path} ---")
        click.echo(foil_content)
        click.echo(f"\nTarget file: {file_path}")
        click.echo("--- End review prompt ---")
        return

    # No valid flag combination
    click.echo(
        "Usage: calx review [--gaps | --history | --foil NAME --file PATH | --record --foil NAME --verdict V]",
        err=True,
    )
    raise SystemExit(1)
