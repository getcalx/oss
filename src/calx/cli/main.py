"""Calx CLI — behavioral governance for AI coding agents."""

from __future__ import annotations

import click

from calx import __version__


@click.group()
@click.version_option(__version__, prog_name="calx")
def cli():
    """Calx — behavioral governance for AI coding agents."""


# Import and register subcommands
from calx.cli.init_cmd import init  # noqa: E402

cli.add_command(init)


# Hidden hook group for internal callbacks
@cli.group(hidden=True, name="_hook")
def hook_group():
    """Internal hook callbacks."""
