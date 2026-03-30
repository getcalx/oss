"""Server configuration with env/file loading and token generation."""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field, fields as dataclass_fields
from pathlib import Path


def _find_calx_dir() -> Path | None:
    """Find .calx/ directory. Checks CALX_DIR env var first, then walks up from cwd."""
    env_dir = os.environ.get("CALX_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / ".calx"
        if candidate.is_dir():
            return candidate
    return None


def _save_token(calx_dir: Path, token: str) -> None:
    """Persist generated auth token to server.json."""
    server_json = calx_dir / "server.json"
    data: dict = {}
    if server_json.exists():
        with open(server_json) as f:
            data = json.load(f)
    data["auth_token"] = token
    calx_dir.mkdir(parents=True, exist_ok=True)
    with open(server_json, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(server_json, 0o600)


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 4195
    transport: str = "streamable-http"
    backend: str = "sqlite"
    db_path: Path = field(default_factory=lambda: Path(".calx/calx.db"))
    postgres_url: str = ""
    redis_url: str = ""
    auth_token: str = ""
    calx_dir: Path = field(default_factory=lambda: Path(".calx"))
    otel_enabled: bool = True
    otel_endpoint: str = ""
    telemetry_retention_days: int = 90

    @classmethod
    def from_env_and_file(cls, calx_dir: Path | None = None) -> ServerConfig:
        """Load config from .calx/server.json, override with env vars."""
        config = cls()

        if calx_dir:
            config.calx_dir = calx_dir
        else:
            config.calx_dir = _find_calx_dir() or Path(".calx")

        config.db_path = config.calx_dir / "calx.db"

        # Load server.json if it exists
        server_json = config.calx_dir / "server.json"
        if server_json.exists():
            with open(server_json) as f:
                data = json.load(f)
            allowed_fields = {f.name for f in dataclass_fields(cls)}
            for key, value in data.items():
                if key in allowed_fields:
                    if key in ("db_path", "calx_dir"):
                        setattr(config, key, Path(value))
                    else:
                        setattr(config, key, value)

        # Env var overrides (CALX_PORT, CALX_BACKEND, etc.)
        env_fields = [
            "host", "port", "transport", "backend",
            "postgres_url", "redis_url", "auth_token",
        ]
        for field_name in env_fields:
            env_key = f"CALX_{field_name.upper()}"
            env_val = os.environ.get(env_key)
            if env_val:
                if field_name == "port":
                    setattr(config, field_name, int(env_val))
                else:
                    setattr(config, field_name, env_val)

        return config

    def ensure_auth_token(self) -> None:
        """Generate and persist an auth token if none is set."""
        if self.auth_token:
            return
        self.auth_token = secrets.token_urlsafe(32)
        try:
            _save_token(self.calx_dir, self.auth_token)
        except OSError:
            pass
