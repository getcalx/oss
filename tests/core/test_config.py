"""Tests for calx.core.config."""

import json
from pathlib import Path

from calx.core.config import (
    CalxConfig,
    TokenDiscipline,
    default_config,
    load_config,
    save_config,
)


def test_default_config():
    config = default_config(["api", "services"])
    assert config.domains == ["api", "services"]
    assert config.schema_version == "1.0"
    assert config.install_id  # non-empty UUID
    assert config.promotion_threshold == 3
    assert config.max_prompts_per_session == 3


def test_save_and_load(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    config = CalxConfig(
        install_id="abc123",
        domains=["api", "tests"],
        agent_naming="developer",
        stats_opt_in=True,
        referral_source="paper",
    )
    save_config(calx_dir, config)

    loaded = load_config(calx_dir)
    assert loaded.install_id == "abc123"
    assert loaded.domains == ["api", "tests"]
    assert loaded.agent_naming == "developer"
    assert loaded.stats_opt_in is True
    assert loaded.referral_source == "paper"


def test_load_missing_file(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = load_config(calx_dir)
    assert config.schema_version == "1.0"
    assert config.domains == []


def test_load_malformed_json(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    (calx_dir / "calx.json").write_text("{broken", encoding="utf-8")
    config = load_config(calx_dir)
    assert config.schema_version == "1.0"


def test_token_discipline_roundtrip(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()

    config = CalxConfig(
        token_discipline=TokenDiscipline(
            soft_cap=80_000,
            ceiling=100_000,
            model_context_window=200_000,
        )
    )
    save_config(calx_dir, config)

    loaded = load_config(calx_dir)
    assert loaded.token_discipline.soft_cap == 80_000
    assert loaded.token_discipline.ceiling == 100_000
    assert loaded.token_discipline.model_context_window == 200_000


def test_save_creates_parent_dirs(tmp_path: Path):
    calx_dir = tmp_path / "project" / ".calx"
    config = CalxConfig(domains=["api"])
    save_config(calx_dir, config)
    assert (calx_dir / "calx.json").exists()


def test_config_json_is_valid(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    save_config(calx_dir, CalxConfig(domains=["api"]))

    data = json.loads((calx_dir / "calx.json").read_text())
    assert data["domains"] == ["api"]
