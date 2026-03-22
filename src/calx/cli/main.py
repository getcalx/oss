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
from calx.cli.correct import correct  # noqa: E402
from calx.cli.distill import distill  # noqa: E402
from calx.cli.status import status  # noqa: E402
from calx.cli.config_cmd import config_cmd  # noqa: E402
from calx.cli.health import health  # noqa: E402
from calx.cli.dispatch_cmd import dispatch  # noqa: E402
from calx.cli.stats import stats  # noqa: E402

cli.add_command(init)
cli.add_command(correct)
cli.add_command(distill)
cli.add_command(status)
cli.add_command(config_cmd)
cli.add_command(health)
cli.add_command(dispatch)
cli.add_command(stats)


# Hidden hook group for internal callbacks
@cli.group(hidden=True, name="_hook")
def hook_group():
    """Internal hook callbacks."""
