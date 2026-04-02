"""Calx CLI — correction engineering for AI agents."""

from __future__ import annotations

import click

from calx import __version__


@click.group()
@click.version_option(__version__, prog_name="calx")
def cli():
    """Calx — correction engineering for AI agents."""


# Import and register subcommands
from calx.cli.config_cmd import config_cmd  # noqa: E402
from calx.cli.correct import correct  # noqa: E402
from calx.cli.dispatch_cmd import dispatch  # noqa: E402
from calx.cli.distill import distill  # noqa: E402
from calx.cli.health import health  # noqa: E402
from calx.cli.init_cmd import init  # noqa: E402
from calx.cli.serve_cmd import serve  # noqa: E402
from calx.cli.stats import stats  # noqa: E402
from calx.cli.status import status  # noqa: E402
from calx.cli.sync_cmd import sync  # noqa: E402
from calx.cli.telemetry_cmd import telemetry  # noqa: E402
from calx.cli.board_cmd import board  # noqa: E402
from calx.cli.compilations_cmd import compilations  # noqa: E402
from calx.cli.plan_cmd import plan  # noqa: E402
from calx.cli.promote_cmd import promote  # noqa: E402
from calx.cli.review_cmd import review  # noqa: E402
from calx.cli.rules_cmd import rules  # noqa: E402

cli.add_command(init)
cli.add_command(correct)
cli.add_command(distill)
cli.add_command(status)
cli.add_command(config_cmd)
cli.add_command(health)
cli.add_command(dispatch)
cli.add_command(stats)
cli.add_command(sync)
cli.add_command(serve)
cli.add_command(telemetry)
cli.add_command(board)
cli.add_command(compilations)
cli.add_command(plan)
cli.add_command(promote)
cli.add_command(review)
cli.add_command(rules)


# Import and register hook group
from calx.cli.hook_cmd import hook_group  # noqa: E402

cli.add_command(hook_group)
