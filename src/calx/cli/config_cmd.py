"""calx config — settings management."""
from __future__ import annotations

import click

from calx.core.config import find_calx_dir, load_config, save_config


@click.command("config")
@click.option("--show", is_flag=True, help="Show current config")
@click.option("--set", "key_value", nargs=2, help="Set a config value: --set key value")
def config_cmd(show: bool, key_value: tuple[str, str] | None):
    """View or modify Calx configuration."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project. Run `calx init` first.", err=True)
        raise SystemExit(1)

    config = load_config(calx_dir)

    if key_value:
        key, value = key_value
        _set_config(calx_dir, config, key, value)
    else:
        # Default to showing config
        click.echo("Calx Config")
        click.echo(f"  Domains: {', '.join(config.domains)}")
        click.echo(f"  Agent naming: {config.agent_naming}")
        click.echo(f"  Promotion threshold: {config.promotion_threshold}")
        click.echo(f"  Max prompts/session: {config.max_prompts_per_session}")
        click.echo(f"  Staleness days: {config.staleness_days}")
        click.echo(f"  Stats opt-in: {config.stats_opt_in}")
        click.echo(f"  Phone home: {config.phone_home}")
        td = config.token_discipline
        click.echo(f"  Token soft cap: {td.soft_cap:,}")
        click.echo(f"  Token ceiling: {td.ceiling:,}")


def _set_config(calx_dir, config, key, value):
    """Set a single config value."""
    int_keys = {
        "promotion_threshold": (1, 100),
        "max_prompts_per_session": (1, 50),
        "staleness_days": (1, 365),
    }
    if key in int_keys:
        lo, hi = int_keys[key]
        try:
            parsed = int(value)
        except ValueError:
            click.echo(f"Invalid value for {key}: must be an integer", err=True)
            return
        if parsed < lo or parsed > hi:
            click.echo(f"Invalid value for {key}: must be between {lo} and {hi}", err=True)
            return
        setattr(config, key, parsed)
    elif key == "agent_naming":
        if value not in ("self", "developer", "none"):
            click.echo("Invalid value. Must be: self, developer, none", err=True)
            return
        config.agent_naming = value
    elif key == "stats_opt_in":
        config.stats_opt_in = value.lower() in ("true", "1", "yes")
    elif key == "phone_home":
        config.phone_home = value.lower() in ("true", "1", "yes")
    else:
        click.echo(f"Unknown config key: {key}", err=True)
        return

    save_config(calx_dir, config)
    click.echo(f"Set {key} = {value}")
