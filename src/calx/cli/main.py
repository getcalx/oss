"""Calx CLI -- deprecated. Calx has moved to a cloud-hosted model."""

from __future__ import annotations

import click

_MESSAGE = """\
getcalx is deprecated.

Calx has moved to a cloud-hosted model.
Visit https://calx.sh for the new setup.

This package will receive no further updates."""


@click.command(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.version_option("0.8.0", prog_name="calx")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def cli(args):
    """getcalx is deprecated. Visit calx.sh for the new setup."""
    click.echo(_MESSAGE)
