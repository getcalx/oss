"""Tests for calx.core.telemetry."""

from pathlib import Path

from calx.core.config import CalxConfig, save_config
from calx.core.corrections import create_correction
from calx.core.telemetry import build_payload, should_surface_benchmark


def test_build_payload_empty(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    save_config(calx_dir, CalxConfig(install_id="test-id"))

    payload = build_payload(calx_dir)
    assert payload.install_id == "test-id"
    assert payload.correction_count == 0
    assert payload.recurrence_rate == 0.0


def test_build_payload_with_corrections(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    save_config(calx_dir, CalxConfig(install_id="test-id", referral_source="paper"))

    create_correction(calx_dir, domain="api", description="test1")
    create_correction(calx_dir, domain="api", description="test2", correction_type="architectural")
    create_correction(calx_dir, domain="tests", description="test3")

    payload = build_payload(calx_dir)
    assert payload.correction_count == 3
    assert payload.type_split.get("process", 0) == 2
    assert payload.type_split.get("architectural", 0) == 1
    assert payload.domain_counts == {"api": 2, "tests": 1}
    assert payload.referral_source == "paper"


def test_should_surface_benchmark_under_threshold(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    assert not should_surface_benchmark(calx_dir)


def test_should_surface_benchmark_at_threshold(tmp_path: Path):
    calx_dir = tmp_path / ".calx"
    calx_dir.mkdir()
    for i in range(50):
        create_correction(calx_dir, domain="api", description=f"correction {i}")
    assert should_surface_benchmark(calx_dir)
