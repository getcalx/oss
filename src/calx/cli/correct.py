"""calx correct — explicit correction capture."""
from __future__ import annotations

import json

import click

from calx.capture.explicit import capture_explicit
from calx.core.config import find_calx_dir


@click.command()
@click.argument("message")
@click.option("--domain", "-d", default=None, help="Override auto-detected domain")
@click.option(
    "--type",
    "-t",
    "correction_type",
    default="process",
    type=click.Choice(["process", "architectural"]),
    help="Correction type",
)
@click.option("--context", "-c", default="", help="Additional context")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def correct(
    message: str,
    domain: str | None,
    correction_type: str,
    context: str,
    as_json: bool,
) -> None:
    """Log a correction. Golden path: calx correct 'message'"""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project. Run `calx init` first.", err=True)
        raise SystemExit(1)

    correction, feedback = capture_explicit(
        calx_dir,
        message,
        domain=domain,
        correction_type=correction_type,
        context=context,
    )

    if as_json:
        click.echo(
            json.dumps(
                {
                    "id": correction.id,
                    "domain": correction.domain,
                    "type": correction.type,
                    "description": correction.description,
                    "status": correction.status,
                    "feedback": feedback,
                },
                indent=2,
            )
        )
    else:
        click.echo(feedback)
