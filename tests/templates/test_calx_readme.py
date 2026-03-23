"""Tests for calx.templates.calx_readme."""

from calx.templates.calx_readme import generate_calx_readme


def test_readme_has_correction_engineering_heading():
    result = generate_calx_readme(["api"])
    assert "# .calx/ — Correction Engineering" in result


def test_readme_lists_domains():
    result = generate_calx_readme(["api", "services", "infra"])
    assert "api, services, infra" in result


def test_readme_empty_domains_shows_none_configured():
    result = generate_calx_readme([])
    assert "(none configured)" in result


def test_readme_contains_pip_install():
    result = generate_calx_readme(["api"])
    assert "pip install getcalx" in result


def test_readme_contains_calx_sh_reference():
    result = generate_calx_readme(["api"])
    assert "calx.sh" in result
