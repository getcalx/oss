"""Tests for calx.capture.explicit."""

from pathlib import Path
from unittest.mock import patch

from calx.capture.explicit import _auto_detect_domain, capture_explicit
from calx.core.config import CalxConfig, default_config, save_config


def _setup_calx_dir(tmp_path: Path, domains: list[str] | None = None) -> Path:
    """Create a .calx dir with config."""
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = default_config(domains or ["api", "services"])
    save_config(calx_dir, config)
    return calx_dir


def test_capture_creates_correction(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path)
    correction, feedback = capture_explicit(calx_dir, "don't mock the database")
    assert correction.id == "C001"
    assert correction.description == "don't mock the database"
    assert correction.source == "explicit"
    assert correction.status == "confirmed"


def test_capture_feedback_no_match(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path, ["api"])
    correction, feedback = capture_explicit(calx_dir, "test message")
    date_str = correction.timestamp[:10]
    assert feedback == f"Logged {correction.id} ({date_str}) in api domain."


def test_auto_detect_domain_from_cwd(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path, ["api", "services"])
    api_dir = tmp_path / "api" / "routes"
    api_dir.mkdir(parents=True)

    with patch("calx.capture.explicit.Path.cwd", return_value=api_dir):
        result = _auto_detect_domain(calx_dir)

    assert result == "api"


def test_auto_detect_returns_none_outside_project(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path, ["api"])

    with patch("calx.capture.explicit.Path.cwd", return_value=Path("/some/other/path")):
        result = _auto_detect_domain(calx_dir)

    assert result is None


def test_fallback_to_first_domain(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path, ["services", "api"])
    # cwd is project root — no domain subdirectory match
    with patch("calx.capture.explicit.Path.cwd", return_value=tmp_path):
        correction, feedback = capture_explicit(calx_dir, "some correction")

    assert correction.domain == "services"
    assert "services" in feedback


def test_explicit_domain_override(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path, ["api", "services"])
    correction, feedback = capture_explicit(
        calx_dir, "test override", domain="services"
    )
    assert correction.domain == "services"
    assert "services" in feedback


def test_type_override(tmp_path: Path):
    calx_dir = _setup_calx_dir(tmp_path, ["api"])
    correction, _ = capture_explicit(
        calx_dir, "use structured logging", correction_type="convention"
    )
    assert correction.type == "convention"


def test_fallback_general_when_no_domains(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    config = CalxConfig(install_id="test")
    save_config(calx_dir, config)

    correction, feedback = capture_explicit(calx_dir, "no domains configured")
    assert correction.domain == "general"
    assert "general" in feedback
