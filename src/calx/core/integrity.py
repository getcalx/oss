"""JSONL corruption recovery for Calx."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IntegrityResult:
    is_clean: bool
    total_lines: int
    malformed_lines: list[int] = field(default_factory=list)


@dataclass
class RepairResult:
    repaired: bool
    removed_content: str | None = None


def check_jsonl_integrity(path: Path) -> IntegrityResult:
    """Scan a JSONL file for malformed lines."""
    if not path.exists():
        return IntegrityResult(is_clean=True, total_lines=0)

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return IntegrityResult(is_clean=True, total_lines=0)

    lines = text.splitlines()
    malformed: list[int] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            malformed.append(i)

    return IntegrityResult(
        is_clean=len(malformed) == 0,
        total_lines=len(lines),
        malformed_lines=malformed,
    )


def repair_jsonl(path: Path, dry_run: bool = False) -> RepairResult:
    """Remove malformed lines from a JSONL file."""
    if not path.exists():
        return RepairResult(repaired=False)

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    good_lines: list[str] = []
    removed_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
            good_lines.append(stripped)
        except json.JSONDecodeError:
            removed_lines.append(stripped)

    if not removed_lines:
        return RepairResult(repaired=False)

    if not dry_run:
        path.write_text(
            "\n".join(good_lines) + "\n" if good_lines else "",
            encoding="utf-8",
        )

    return RepairResult(
        repaired=True,
        removed_content="\n".join(removed_lines),
    )
