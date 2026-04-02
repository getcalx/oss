"""calx telemetry -- manage telemetry settings."""
from __future__ import annotations

import json
import sys

import click

from calx.core.config import find_calx_dir


@click.group("telemetry", invoke_without_command=True)
@click.option("--show", is_flag=True, help="Show telemetry config as JSON.")
@click.option("--off", is_flag=True, help="Disable telemetry permanently.")
@click.option("--on", is_flag=True, help="Re-enable telemetry.")
@click.pass_context
def telemetry(ctx, show: bool, off: bool, on: bool):
    """Manage anonymous usage telemetry."""
    calx_dir = find_calx_dir()
    if calx_dir is None:
        click.echo("No .calx/ directory found. Run `calx init` first.", err=True)
        sys.exit(1)

    calx_json_path = calx_dir / "calx.json"
    if not calx_json_path.exists():
        click.echo("No calx.json found. Run `calx init` first.", err=True)
        sys.exit(1)

    config = json.loads(calx_json_path.read_text())
    telemetry_config = config.get("telemetry", {})

    if show:
        click.echo(json.dumps(telemetry_config, indent=2))
        return

    if off:
        telemetry_config["enabled"] = False
        config["telemetry"] = telemetry_config
        calx_json_path.write_text(json.dumps(config, indent=2))
        click.echo("Telemetry disabled.", err=True)
        return

    if on:
        telemetry_config["enabled"] = True
        config["telemetry"] = telemetry_config
        calx_json_path.write_text(json.dumps(config, indent=2))
        click.echo("Telemetry enabled.", err=True)
        return

    # Default: show status
    enabled = telemetry_config.get("enabled", True)
    install_id = telemetry_config.get("install_id", "not set")
    click.echo(f"Telemetry: {'enabled' if enabled else 'disabled'}")
    click.echo(f"Install ID: {install_id}")
