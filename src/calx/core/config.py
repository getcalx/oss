"""Configuration management for Calx."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TokenDiscipline:
    """Token discipline thresholds."""

    soft_cap: int = 200_000
    ceiling: int = 250_000
    model_context_window: int = 1_000_000


@dataclass
class CalxConfig:
    """Root configuration stored in .calx/calx.json."""

    schema_version: str = "1.0"
    install_id: str = ""
    anonymous_id: str = ""
    domains: list[str] = field(default_factory=list)
    domain_paths: dict[str, str] = field(default_factory=dict)
    agent_naming: str = "self"  # "self" | "developer" | "none"
    token_discipline: TokenDiscipline = field(default_factory=TokenDiscipline)
    staleness_days: int = 30
    promotion_threshold: int = 3
    max_prompts_per_session: int = 3


def load_config(calx_dir: Path) -> CalxConfig:
    """Load configuration from .calx/calx.json.

    Returns default config if file doesn't exist or is malformed.
    """
    config_path = calx_dir / "calx.json"
    if not config_path.exists():
        return CalxConfig()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return CalxConfig()

    td_data = data.pop("token_discipline", {})
    td = TokenDiscipline(
        soft_cap=td_data.get("soft_cap", 200_000),
        ceiling=td_data.get("ceiling", 250_000),
        model_context_window=td_data.get("model_context_window", 1_000_000),
    )

    return CalxConfig(
        schema_version=data.get("schema_version", "1.0"),
        install_id=data.get("install_id", ""),
        anonymous_id=data.get("anonymous_id", ""),
        domains=data.get("domains", []),
        domain_paths=data.get("domain_paths", {}),
        agent_naming=data.get("agent_naming", "self"),
        token_discipline=td,
        staleness_days=data.get("staleness_days", 30),
        promotion_threshold=data.get("promotion_threshold", 3),
        max_prompts_per_session=data.get("max_prompts_per_session", 3),
    )


def save_config(calx_dir: Path, config: CalxConfig) -> None:
    """Save configuration to .calx/calx.json."""
    config_path = calx_dir / "calx.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(asdict(config), indent=2) + "\n",
        encoding="utf-8",
    )


def default_config(
    domains: list[str],
    *,
    domain_paths: dict[str, str] | None = None,
) -> CalxConfig:
    """Create a default configuration with the given domains."""
    from calx.core.ids import generate_uuid

    return CalxConfig(
        install_id=generate_uuid(),
        anonymous_id=generate_uuid(),
        domains=domains,
        domain_paths=domain_paths or {},
    )


def find_calx_dir() -> Path | None:
    """Walk up from cwd looking for a .calx/ directory."""
    current = Path.cwd()
    while True:
        candidate = current / ".calx"
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent
