"""calx promote -- promote corrections to rules."""
from __future__ import annotations

import click

from calx.cli._http import _fail_unreachable, _get_json, _post_json


@click.command("promote")
@click.argument("correction_id", required=False, default=None)
@click.option("--text", default=None, help="Rule text for the promoted correction")
def promote(correction_id: str | None, text: str | None):
    """Promote a correction to a rule, or list promotion candidates."""
    if correction_id is None:
        # List candidates
        data = _get_json("/enforce/promotion-candidates")
        if data is None:
            _fail_unreachable()

        candidates = data.get("candidates", data if isinstance(data, list) else [])
        if not candidates:
            click.echo("No promotion candidates.")
            return

        click.echo("Promotion candidates:")
        for c in candidates:
            cid = c.get("correction_id") or c.get("id", "unknown")
            count = c.get("recurrence_count") or c.get("count", "")
            summary = c.get("summary") or c.get("text", "")
            count_str = f" (x{count})" if count else ""
            click.echo(f"  {cid}{count_str}: {summary}")
        return

    # Promote a specific correction
    if not text:
        click.echo("--text is required when promoting a correction.", err=True)
        raise SystemExit(1)

    result = _post_json("/enforce/promote", {
        "correction_id": correction_id,
        "rule_text": text,
    })
    if result is None:
        _fail_unreachable()

    click.echo(result.get("message", "Promoted."))
