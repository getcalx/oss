"""OSS server factory -- 3 resources, 3 tools.
This is the subset that ships in the getcalx OSS package.
Resources: briefing, rules, corrections
Tools: log_correction, promote_correction, get_briefing
"""
# NOTE: Do NOT use 'from __future__ import annotations' here.
# FastMCP 3.x needs runtime annotation introspection for @lifespan.

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from calx.serve import __version__
from calx.serve.config import ServerConfig
from calx.serve.db.migrate import migrate_from_files
from calx.serve.db.sqlite import SQLiteEngine
from calx.serve.resources.briefing import register_briefing_resource
from calx.serve.resources.corrections import register_corrections_resource
from calx.serve.resources.rules import register_rules_resource
from calx.serve.tools.get_briefing import register_get_briefing_tool
from calx.serve.tools.log_correction import register_log_correction_tool
from calx.serve.tools.promote_correction import register_promote_correction_tool


def create_oss_server(config: ServerConfig) -> FastMCP:
    """Create the OSS-scoped FastMCP server."""

    @lifespan
    async def db_lifespan(server: FastMCP):
        """Initialize database, run migration, yield context, close on shutdown."""
        db = SQLiteEngine(db_path=str(config.db_path))
        await db.initialize()
        await migrate_from_files(db, config.calx_dir)
        try:
            yield {"db": db, "config": config}
        finally:
            await db.close()

    auth = None
    if config.auth_token and config.transport != "stdio":
        from fastmcp.server.auth import StaticTokenVerifier
        auth = StaticTokenVerifier(
            tokens={config.auth_token: {"client_id": "calx-client"}},
        )

    mcp = FastMCP(
        name="calx",
        version=__version__,
        instructions=(
            "Behavioral governance compiler for AI agents. "
            "Compile corrections into enforceable mechanisms with provenance and rollbacks."
        ),
        auth=auth,
        lifespan=db_lifespan,
    )

    # OSS resources (3)
    register_briefing_resource(mcp)
    register_rules_resource(mcp)
    register_corrections_resource(mcp)

    # OSS tools (3)
    register_log_correction_tool(mcp)
    register_promote_correction_tool(mcp)
    register_get_briefing_tool(mcp)

    return mcp
