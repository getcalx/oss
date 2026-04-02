"""Phase 4 -- MCP server creation and configuration tests."""

import json

from calx.serve.config import ServerConfig
from calx.serve.server import create_oss_server


def test_create_oss_server_returns_fastmcp():
    from fastmcp import FastMCP

    config = ServerConfig(auth_token="test-token-123", transport="stdio")
    server = create_oss_server(config)
    assert isinstance(server, FastMCP)
    assert server.name == "calx"


def test_create_oss_server_stashes_config():
    """Config is stashed on the server instance for lifespan access."""
    config = ServerConfig(auth_token="test-token-123", transport="stdio")
    server = create_oss_server(config)
    assert hasattr(server, "_calx_config")
    assert server._calx_config is config


def test_server_config_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CALX_PORT", "9999")
    monkeypatch.setenv("CALX_AUTH_TOKEN", "env-token")
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = ServerConfig.from_env_and_file(calx_dir=calx_dir)
    assert config.port == 9999
    assert config.auth_token == "env-token"


def test_server_config_no_auto_token(tmp_path):
    """from_env_and_file should NOT auto-generate a token (lazy generation)."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = ServerConfig.from_env_and_file(calx_dir=calx_dir)
    assert config.auth_token == ""


def test_ensure_auth_token_generates_and_persists(tmp_path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = ServerConfig.from_env_and_file(calx_dir=calx_dir)
    config.ensure_auth_token()
    assert config.auth_token  # non-empty
    assert len(config.auth_token) > 20  # urlsafe token
    server_json = calx_dir / "server.json"
    assert server_json.exists()
    data = json.loads(server_json.read_text())
    assert data["auth_token"] == config.auth_token


def test_ensure_auth_token_noop_when_set(tmp_path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = ServerConfig.from_env_and_file(calx_dir=calx_dir)
    config.auth_token = "already-set"
    config.ensure_auth_token()
    assert config.auth_token == "already-set"


def test_server_config_loads_from_file(tmp_path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    (calx_dir / "server.json").write_text(json.dumps({
        "port": 8888,
        "auth_token": "file-token",
    }))
    config = ServerConfig.from_env_and_file(calx_dir=calx_dir)
    assert config.port == 8888
    assert config.auth_token == "file-token"


def test_env_overrides_file(tmp_path, monkeypatch):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    (calx_dir / "server.json").write_text(json.dumps({"port": 8888}))
    monkeypatch.setenv("CALX_PORT", "7777")
    config = ServerConfig.from_env_and_file(calx_dir=calx_dir)
    assert config.port == 7777


def test_server_config_defaults():
    config = ServerConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 4195
    assert config.transport == "streamable-http"
    assert config.backend == "sqlite"


def test_no_future_annotations_in_fastmcp_files():
    """Guard: from __future__ import annotations breaks FastMCP 3.x introspection.

    Files in resources/, tools/, and server.py must NOT have this import.
    FastMCP needs runtime annotation evaluation to build parameter schemas.
    This is C006. Third time this has come up.
    """
    from pathlib import Path

    serve_root = Path(__file__).resolve().parent.parent.parent / "src" / "calx" / "serve"
    forbidden_dirs = [serve_root / "resources", serve_root / "tools"]
    forbidden_files = [serve_root / "server.py"]

    violations = []
    for d in forbidden_dirs:
        for f in d.glob("*.py"):
            content = f.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if line.strip() == "from __future__ import annotations":
                    violations.append(f"{f.relative_to(serve_root)}:{i}")

    for f in forbidden_files:
        if f.exists():
            content = f.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if line.strip() == "from __future__ import annotations":
                    violations.append(f"{f.relative_to(serve_root)}:{i}")

    assert not violations, (
        f"from __future__ import annotations found in FastMCP files (C006): {violations}"
    )


def test_fastmcp_imports_resolve():
    """Guard: verify all FastMCP imports we depend on still exist.

    Catches API removals/renames across FastMCP upgrades before they
    hit production. Pin is >=3.1,<4 but minor versions can still break.
    """
    from fastmcp import FastMCP  # noqa: F811
    from fastmcp import Context
    from fastmcp.server.lifespan import lifespan
    from fastmcp.server.auth import StaticTokenVerifier

    assert FastMCP is not None
    assert Context is not None
    assert lifespan is not None
    assert StaticTokenVerifier is not None
