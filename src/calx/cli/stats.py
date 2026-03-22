"""calx stats — local metrics and anonymous sharing."""
from __future__ import annotations

import json

import click

from calx.core.config import find_calx_dir
from calx.core.corrections import materialize
from calx.core.rules import read_all_rules
from calx.core.telemetry import build_payload, post_stats


@click.command()
@click.option("--share", is_flag=True, help="POST anonymous stats")
@click.option("--json", "as_json", is_flag=True)
def stats(share: bool, as_json: bool):
    """Show local metrics and optionally share anonymous stats."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project.", err=True)
        raise SystemExit(1)

    corrections = materialize(calx_dir)
    rules = read_all_rules(calx_dir)

    type_split: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    recurrence_total = 0
    for c in corrections:
        type_split[c.type] = type_split.get(c.type, 0) + 1
        domain_counts[c.domain] = domain_counts.get(c.domain, 0) + 1
        if c.recurrence_of:
            recurrence_total += 1

    total = len(corrections)
    recurrence_rate = recurrence_total / total if total > 0 else 0.0

    # Try floor trajectory
    floor_info = None
    try:
        from calx.health.floor import get_trajectory

        trajectory = get_trajectory(calx_dir)
        floor_info = f"{trajectory.trend}"
        if trajectory.current_rate > 0:
            floor_info += f" at ~{trajectory.current_rate:.1f}"
    except ImportError:
        pass

    if as_json:
        data: dict = {
            "corrections": total,
            "type_split": type_split,
            "domain_counts": domain_counts,
            "recurrence_rate": round(recurrence_rate, 3),
            "rules": len(rules),
        }
        if floor_info:
            data["error_floor"] = floor_info
        click.echo(json.dumps(data, indent=2))
    else:
        arch = type_split.get("architectural", 0)
        proc = type_split.get("process", 0)
        click.echo("Calx Stats")
        click.echo(f"  Corrections: {total} ({arch} architectural, {proc} process)")
        for d, count in sorted(domain_counts.items()):
            click.echo(f"  {d}: {count}")
        click.echo(f"  Recurrence rate: {recurrence_rate:.0%}")
        if floor_info:
            click.echo(f"  Error floor trajectory: {floor_info}")

    if share:
        payload = build_payload(calx_dir)
        click.echo("\nSharing anonymous stats...")
        success = post_stats(payload)
        if success:
            click.echo("Stats shared successfully.")
        else:
            click.echo("Failed to share stats (endpoint may not be available yet).")
