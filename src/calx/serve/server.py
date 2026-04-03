"""OSS server factory -- 3 resources, 3 tools.

This is the subset that ships in the getcalx OSS package.
Resources: briefing, rules, corrections
Tools: log_correction, promote_correction, get_briefing
"""
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from calx.serve import __version__
from calx.serve.config import ServerConfig
from calx.serve.db.migrate import migrate_from_files
from calx.serve.db.sqlite import SQLiteEngine
from calx.serve.resources.briefing import register_briefing_resource
from calx.serve.resources.corrections import register_corrections_resource
from calx.serve.resources.rules import register_rules_resource
from calx.serve.tools.create_plan import register_create_plan_tool
from calx.serve.tools.deactivate_rule import register_deactivate_rule_tool
from calx.serve.tools.dispatch_chunk import register_dispatch_chunk_tool
from calx.serve.tools.end_session import register_end_session_tool
from calx.serve.tools.get_briefing import register_get_briefing_tool
from calx.serve.tools.log_correction import register_log_correction_tool
from calx.serve.tools.promote_correction import register_promote_correction_tool
from calx.serve.tools.redispatch_chunk import register_redispatch_chunk_tool
from calx.serve.tools.register_session import register_register_session_tool
from calx.serve.tools.update_board import register_update_board_tool
from calx.serve.tools.update_plan import register_update_plan_tool
from calx.serve.tools.verify_wave import register_verify_wave_tool


@lifespan
async def db_lifespan(server: FastMCP):
    """Initialize database, run migrations, yield context, close on shutdown."""
    external_db = getattr(server._calx_config, "_external_db", None)
    if external_db is not None:
        yield {"db": external_db}
        return

    db = SQLiteEngine(db_path=str(server._calx_config.db_path))
    await db.initialize()
    await migrate_from_files(db, server._calx_config.calx_dir)
    try:
        yield {"db": db}
    finally:
        await db.close()


def create_oss_server(config: ServerConfig) -> FastMCP:
    """Create the OSS-scoped FastMCP server."""
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
            "Agentic behavioral infrastructure. "
            "The behavioral plane for AI agents, over MCP."
        ),
        auth=auth,
        lifespan=db_lifespan,
    )
    # Stash config for lifespan access
    mcp._calx_config = config  # type: ignore[attr-defined]

    # OSS resources (3)
    register_briefing_resource(mcp)
    register_rules_resource(mcp)
    register_corrections_resource(mcp)

    # OSS tools (13)
    register_log_correction_tool(mcp)
    register_promote_correction_tool(mcp)
    register_get_briefing_tool(mcp)
    register_register_session_tool(mcp)
    register_end_session_tool(mcp)
    register_deactivate_rule_tool(mcp)
    register_update_board_tool(mcp)
    register_create_plan_tool(mcp)
    register_update_plan_tool(mcp)
    register_dispatch_chunk_tool(mcp)
    register_redispatch_chunk_tool(mcp)
    register_verify_wave_tool(mcp)

    return mcp
