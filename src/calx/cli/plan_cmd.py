"""calx plan -- plan management via the enforcement server."""
from __future__ import annotations

import json

import click

from calx.cli._http import _fail_unreachable, _get_json, _post_json


@click.command("plan")
@click.option("--status", is_flag=True, help="Show detailed plan status")
@click.option("--complete", default=None, metavar="ID", help="Mark a chunk as done")
@click.option("--block", default=None, metavar="ID", help="Mark a chunk as blocked")
@click.option("--reason", default=None, help="Block reason (use with --block)")
@click.option("--advance", is_flag=True, help="Advance to the next plan wave")
@click.option("--verify", default=None, type=int, metavar="N", help="Verify wave N")
def plan(
    status: bool,
    complete: str | None,
    block: str | None,
    reason: str | None,
    advance: bool,
    verify: int | None,
):
    """View and manage the enforcement plan."""
    if complete:
        result = _post_json("/enforce/plan/update", {
            "chunk_id": complete,
            "chunk_status": "done",
        })
        if result is None:
            _fail_unreachable()
        click.echo(result.get("message", f"Chunk {complete} marked done."))
        return

    if block:
        if not reason:
            click.echo("--reason is required with --block.", err=True)
            raise SystemExit(1)
        result = _post_json("/enforce/plan/update", {
            "chunk_id": block,
            "chunk_status": "blocked",
            "block_reason": reason,
        })
        if result is None:
            _fail_unreachable()
        click.echo(result.get("message", f"Chunk {block} marked blocked."))
        return

    if advance:
        result = _post_json("/enforce/plan/advance", {})
        if result is None:
            _fail_unreachable()
        click.echo(result.get("message", "Advanced to next wave."))
        return

    if verify is not None:
        result = _post_json("/enforce/verify", {
            "plan_id": "current",
            "wave_id": verify,
        })
        if result is None:
            _fail_unreachable()
        click.echo(json.dumps(result, indent=2))
        return

    # Default: show plan overview (--status shows detailed)
    data = _get_json("/enforce/plan")
    if data is None:
        _fail_unreachable()

    if status:
        click.echo(json.dumps(data, indent=2))
        return

    # Brief overview
    plan_name = data.get("name") or data.get("plan_id", "current plan")
    click.echo(f"Plan: {plan_name}")
    chunks = data.get("chunks", [])
    if chunks:
        done = sum(1 for c in chunks if c.get("status") == "done")
        blocked = sum(1 for c in chunks if c.get("status") == "blocked")
        total = len(chunks)
        click.echo(f"  {done}/{total} done, {blocked} blocked")
        for c in chunks:
            cid = c.get("id") or c.get("chunk_id", "?")
            cs = c.get("status", "pending")
            label = c.get("title") or c.get("description", "")
            icon = {"done": "+", "blocked": "!", "pending": " "}.get(cs, " ")
            label_str = f" {label}" if label else ""
            click.echo(f"  [{icon}] {cid}: {cs}{label_str}")
    else:
        wave = data.get("current_wave") or data.get("wave")
        if wave is not None:
            click.echo(f"  Current wave: {wave}")
        click.echo("  No chunks in response. Use --status for full detail.")
