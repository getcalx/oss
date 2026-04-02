"""Wave verification: import checks, test execution, duplicate detection."""
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


def run_import_check(files: list[str]) -> dict:
    """Check that all Python modules import cleanly.

    Converts file paths to module paths (src/calx/serve/foo.py -> calx.serve.foo)
    and runs `python -c "import {module}"`.

    Returns {"passed": bool, "failures": [{"file": str, "error": str}]}
    """
    failures = []

    for filepath in files:
        # Convert file path to module path
        module = filepath
        # Strip src/ prefix if present
        if module.startswith("src/"):
            module = module[4:]
        # Strip .py suffix
        if module.endswith(".py"):
            module = module[:-3]
        # Convert path separators to dots
        module = module.replace("/", ".").replace("\\", ".")
        # Remove __init__ suffix
        if module.endswith(".__init__"):
            module = module[:-9]

        result = subprocess.run(
            ["python", "-c", f"import {module}"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            failures.append({
                "file": filepath,
                "error": result.stderr.strip(),
            })

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


def run_test_check(test_files: list[str]) -> dict:
    """Run pytest on specified test files.

    Returns {"passed": bool, "failures": [{"test": str, "error": str}]}
    """
    if not test_files:
        return {"passed": True, "failures": []}

    result = subprocess.run(
        ["python", "-m", "pytest"] + test_files + ["-x", "-q"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    failures = []
    if result.returncode != 0:
        # Parse FAILED lines from output
        output = result.stdout + result.stderr
        failed_pattern = re.compile(r"FAILED\s+(\S+)")
        matches = failed_pattern.findall(output)
        if matches:
            for match in matches:
                failures.append({"test": match, "error": output})
        else:
            # Generic failure
            failures.append({"test": ",".join(test_files), "error": output})

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


def run_duplicate_check(files: list[str]) -> dict:
    """Scan for duplicate class/function definitions across files.

    Regex for ^class (\\w+) and ^def (\\w+) patterns.
    Flag when same name appears in two different files.

    Returns {"passed": bool, "duplicates": [{"name": str, "files": [str]}]}
    """
    name_to_files: dict[str, list[str]] = defaultdict(list)
    class_pattern = re.compile(r"^class\s+(\w+)")
    def_pattern = re.compile(r"^def\s+(\w+)")

    for filepath in files:
        try:
            content = Path(filepath).read_text()
        except (OSError, IOError):
            continue

        for line in content.splitlines():
            for pattern in (class_pattern, def_pattern):
                match = pattern.match(line)
                if match:
                    name = match.group(1)
                    if filepath not in name_to_files[name]:
                        name_to_files[name].append(filepath)

    duplicates = []
    for name, found_files in sorted(name_to_files.items()):
        if len(found_files) > 1:
            duplicates.append({"name": name, "files": sorted(found_files)})

    return {
        "passed": len(duplicates) == 0,
        "duplicates": duplicates,
    }


async def run_wave_verification(
    plan_data: dict,
    wave_id: int,
    manual_notes: str | None = None,
) -> dict:
    """Run all verification checks for a wave.

    Returns structured result:
    {
        "import_check": {...},
        "test_check": {...},
        "duplicate_check": {...},
        "manual": {"passed": bool, "notes": str},
        "overall": "pass" | "fail",
        "failing_chunks": [...],
        "redispatch_recommended": bool
    }
    """
    from calx.serve.engine.orchestration import compute_waves

    # Parse chunks from plan data
    chunks_raw = plan_data.get("chunks", "[]")
    if isinstance(chunks_raw, str):
        chunks = json.loads(chunks_raw)
    else:
        chunks = chunks_raw

    edges_raw = plan_data.get("dependency_edges", "[]")
    if isinstance(edges_raw, str):
        edges = json.loads(edges_raw)
    else:
        edges = edges_raw

    # Get wave groups and filter to requested wave
    waves = compute_waves(chunks, edges)
    wave_idx = wave_id - 1
    if wave_idx < 0 or wave_idx >= len(waves):
        return {
            "import_check": {"passed": True, "failures": []},
            "test_check": {"passed": True, "failures": []},
            "duplicate_check": {"passed": True, "duplicates": []},
            "manual": {"passed": manual_notes is not None, "notes": manual_notes or ""},
            "overall": "pass",
            "failing_chunks": [],
            "redispatch_recommended": False,
        }

    wave_chunk_ids = set(waves[wave_idx])
    chunk_map = {c["id"]: c for c in chunks}

    # Collect files only from this wave's chunks
    all_files = []
    test_files = []
    for cid in wave_chunk_ids:
        chunk = chunk_map.get(cid, {})
        for f in chunk.get("files", []):
            all_files.append(f)
            if "test" in Path(f).name.lower():
                test_files.append(f)

    # Run checks
    import_result = run_import_check(all_files)
    test_result = run_test_check(test_files)
    duplicate_result = run_duplicate_check(all_files)

    # Manual check
    manual_result = {
        "passed": manual_notes is not None,
        "notes": manual_notes or "",
    }

    # Determine overall
    all_passed = (
        import_result["passed"]
        and test_result["passed"]
        and duplicate_result["passed"]
    )
    overall = "pass" if all_passed else "fail"

    # Identify failing chunks from ALL failure types
    failing_chunks = []
    if not all_passed:
        failed_files = set()
        # Import failures
        for f in import_result.get("failures", []):
            failed_files.add(f["file"])
        # Test failures
        for f in test_result.get("failures", []):
            test_path = f.get("test", "")
            # Extract file path from test identifier (e.g., "tests/foo.py::test_bar" -> "tests/foo.py")
            if "::" in test_path:
                test_path = test_path.split("::")[0]
            failed_files.add(test_path)
        # Duplicate failures
        for d in duplicate_result.get("duplicates", []):
            for df in d.get("files", []):
                failed_files.add(df)

        # Map failed files to wave-specific chunks
        for cid in wave_chunk_ids:
            chunk = chunk_map.get(cid, {})
            chunk_files = set(chunk.get("files", []))
            if chunk_files & failed_files:
                if cid not in failing_chunks:
                    failing_chunks.append(cid)

    return {
        "import_check": import_result,
        "test_check": test_result,
        "duplicate_check": duplicate_result,
        "manual": manual_result,
        "overall": overall,
        "failing_chunks": failing_chunks,
        "redispatch_recommended": not all_passed,
    }
