"""Tests for calx.core.integrity."""

import json
from pathlib import Path

from calx.core.integrity import check_jsonl_integrity, repair_jsonl


def test_check_empty_file(tmp_path: Path):
    path = tmp_path / "test.jsonl"
    path.write_text("", encoding="utf-8")
    result = check_jsonl_integrity(path)
    assert result.is_clean
    assert result.total_lines == 0


def test_check_nonexistent_file(tmp_path: Path):
    path = tmp_path / "missing.jsonl"
    result = check_jsonl_integrity(path)
    assert result.is_clean


def test_check_valid_jsonl(tmp_path: Path):
    path = tmp_path / "test.jsonl"
    path.write_text(
        json.dumps({"a": 1}) + "\n" + json.dumps({"b": 2}) + "\n",
        encoding="utf-8",
    )
    result = check_jsonl_integrity(path)
    assert result.is_clean
    assert result.total_lines == 2


def test_check_malformed_last_line(tmp_path: Path):
    path = tmp_path / "test.jsonl"
    path.write_text(
        json.dumps({"a": 1}) + "\n" + '{"broken": tru',
        encoding="utf-8",
    )
    result = check_jsonl_integrity(path)
    assert not result.is_clean
    assert result.malformed_lines == [1]


def test_repair_removes_malformed(tmp_path: Path):
    path = tmp_path / "test.jsonl"
    good = json.dumps({"a": 1})
    bad = '{"broken": tru'
    path.write_text(f"{good}\n{bad}\n", encoding="utf-8")

    result = repair_jsonl(path)
    assert result.repaired
    assert result.removed_content == bad

    check = check_jsonl_integrity(path)
    assert check.is_clean
    assert check.total_lines == 1


def test_repair_dry_run(tmp_path: Path):
    path = tmp_path / "test.jsonl"
    content = json.dumps({"a": 1}) + "\n" + '{"broken": tru' + "\n"
    path.write_text(content, encoding="utf-8")

    result = repair_jsonl(path, dry_run=True)
    assert result.repaired
    assert path.read_text() == content


def test_repair_nothing_to_fix(tmp_path: Path):
    path = tmp_path / "test.jsonl"
    path.write_text(json.dumps({"a": 1}) + "\n", encoding="utf-8")
    result = repair_jsonl(path)
    assert not result.repaired
