"""calx serve -- start the MCP server."""

import sys

import click


@click.command()
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=4195, type=int, help="Bind port.")
@click.option(
    "--transport",
    default="streamable-http",
    type=click.Choice(["streamable-http", "stdio"]),
    help="MCP transport protocol.",
)
def serve(host: str, port: int, transport: str):
    """Start the Calx MCP server."""
    try:
        from calx.serve.config import ServerConfig
        from calx.serve.server import create_oss_server
    except ImportError:
        click.echo(
            "MCP server dependencies not installed.\n"
            "Run: pip install getcalx[serve]",
            err=True,
        )
        sys.exit(1)

    config = ServerConfig.from_env_and_file()
    config.host = host
    config.port = port
    config.transport = transport

    if transport != "stdio":
        config.ensure_auth_token()

    server = create_oss_server(config)

    if transport == "stdio":
        server.run(transport="stdio")
    else:
        click.echo(f"Calx MCP server on {host}:{port}", err=True)
        if config.auth_token:
            click.echo(f"Auth token: {config.auth_token[:8]}...", err=True)
        server.run(
            transport="streamable-http",
            host=host,
            port=port,
        )
