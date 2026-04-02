"""Plan orchestration: wave computation, dependency tracking, phase enforcement."""
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


PHASE_ORDER = ["spec", "test", "chunk", "plan", "build", "verify", "commit", "done"]


def compute_waves(chunks: list[dict], edges: list[list[str]]) -> list[list[str]]:
    """Topological sort of chunks into wave groups.

    Each wave contains chunks whose dependencies are all in earlier waves.
    Independent chunks land in the same wave for parallel dispatch.

    Returns list of waves, each wave is a list of chunk IDs.
    """
    if not chunks:
        return []

    chunk_ids = [c["id"] for c in chunks]
    in_degree: dict[str, int] = {cid: 0 for cid in chunk_ids}
    successors: dict[str, list[str]] = defaultdict(list)

    for src, dst in edges:
        in_degree[dst] += 1
        successors[src].append(dst)

    # Kahn's algorithm, grouped by level
    queue = deque(cid for cid in chunk_ids if in_degree[cid] == 0)
    waves: list[list[str]] = []

    while queue:
        wave = sorted(queue)  # deterministic ordering within a wave
        waves.append(wave)
        next_queue: deque[str] = deque()
        for cid in wave:
            for succ in successors[cid]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    next_queue.append(succ)
        queue = next_queue

    processed = sum(len(w) for w in waves)
    if processed != len(chunk_ids):
        missing = set(chunk_ids) - {cid for w in waves for cid in w}
        raise ValueError(f"Cycle detected in dependency graph involving chunks: {', '.join(sorted(missing))}")

    return waves


def get_next_dispatchable(
    chunks: list[dict], edges: list[list[str]], current_wave: int,
) -> list[str]:
    """Get chunk IDs safe to dispatch in parallel.

    Criteria: in current wave, status=pending, all dependencies met (done),
    file-disjoint from each other.
    """
    waves = compute_waves(chunks, edges)
    if current_wave >= len(waves):
        return []

    wave_ids = set(waves[current_wave])
    chunk_map = {c["id"]: c for c in chunks}

    # Filter to pending chunks in the current wave
    candidates = [
        cid for cid in wave_ids
        if chunk_map[cid]["status"] == "pending"
    ]

    # Enforce file-disjoint: greedily pick chunks that don't overlap files
    claimed_files: set[str] = set()
    result: list[str] = []
    for cid in sorted(candidates):
        chunk_files = set(chunk_map[cid].get("files", []))
        if chunk_files & claimed_files:
            continue
        claimed_files |= chunk_files
        result.append(cid)

    return result


def validate_file_disjoint(chunks: list[dict]) -> list[dict]:
    """Check for shared files among chunks that could be parallel.

    Returns list of warnings: [{"file": "path", "chunks": ["a", "b"]}]
    """
    file_to_chunks: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        for f in chunk.get("files", []):
            file_to_chunks[f].append(chunk["id"])

    warnings = []
    for filepath, chunk_ids in sorted(file_to_chunks.items()):
        if len(chunk_ids) > 1:
            warnings.append({"file": filepath, "chunks": sorted(chunk_ids)})

    return warnings


def check_phase_entry(plan_data: dict, target_phase: str) -> tuple[bool, str]:
    """Check if entry criteria are met for target_phase.

    Returns (allowed, reason).
    """
    if target_phase == "spec":
        return True, "spec phase is always allowed"

    if target_phase == "test":
        if not plan_data.get("spec_file"):
            return False, "spec_file must be set before entering test phase"
        if not Path(plan_data["spec_file"]).exists():
            return False, f"spec_file does not exist on disk: {plan_data['spec_file']}"
        return True, "spec_file is set and exists"

    if target_phase == "chunk":
        if not plan_data.get("test_files"):
            return False, "test_files must be set before entering chunk phase"
        # Parse test_files if it's JSON string
        test_files = plan_data["test_files"]
        if isinstance(test_files, str):
            try:
                test_files = json.loads(test_files)
            except (json.JSONDecodeError, TypeError):
                test_files = [test_files]
        for tf in test_files:
            if not Path(tf).exists():
                return False, f"test file does not exist on disk: {tf}"
        return True, "test_files are set and exist"

    if target_phase == "plan":
        chunks_raw = plan_data.get("chunks", "[]")
        if isinstance(chunks_raw, str):
            chunks = json.loads(chunks_raw)
        else:
            chunks = chunks_raw
        if not chunks:
            return False, "chunks array must be non-empty before entering plan phase"
        return True, "chunks are defined"

    if target_phase == "build":
        if plan_data.get("review_id") is None:
            return False, "review_id must be set (foil review with approve verdict) before entering build phase"
        verdict = plan_data.get("review_verdict", "unknown")
        if verdict != "approve":
            return False, f"foil review verdict must be 'approve' (got '{verdict}')"
        return True, "review_id is set and review verdict is approve"

    if target_phase == "verify":
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

        waves = compute_waves(chunks, edges)
        current_wave = plan_data.get("current_wave", 1)
        # current_wave is 1-indexed, waves list is 0-indexed
        wave_idx = current_wave - 1
        if wave_idx < 0 or wave_idx >= len(waves):
            return False, f"current_wave {current_wave} is out of range"

        wave_chunk_ids = set(waves[wave_idx])
        chunk_map = {c["id"]: c for c in chunks}
        not_done = [
            cid for cid in wave_chunk_ids
            if chunk_map.get(cid, {}).get("status") != "done"
        ]
        if not_done:
            return False, f"chunks not done in wave {current_wave}: {', '.join(not_done)}"
        return True, f"all chunks in wave {current_wave} are done"

    if target_phase == "commit":
        wv_raw = plan_data.get("wave_verification")
        if not wv_raw:
            return False, "wave verification must be completed before entering commit phase"
        if isinstance(wv_raw, str):
            wv = json.loads(wv_raw)
        else:
            wv = wv_raw
        current_wave = plan_data.get("current_wave", 1)
        wave_key = str(current_wave)
        wave_result = wv.get(wave_key, {})
        if wave_result.get("overall") != "pass":
            return False, f"wave {current_wave} verification did not pass"
        return True, f"wave {current_wave} verification passed"

    if target_phase == "done":
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

        waves = compute_waves(chunks, edges)
        wv_raw = plan_data.get("wave_verification")
        if not wv_raw:
            return False, "wave verification must be completed for all waves before entering done phase"
        if isinstance(wv_raw, str):
            wv = json.loads(wv_raw)
        else:
            wv = wv_raw

        for i in range(len(waves)):
            wave_key = str(i + 1)
            wave_result = wv.get(wave_key, {})
            if wave_result.get("overall") != "pass":
                return False, f"wave {i + 1} not verified (pass required for all waves)"
        return True, "all waves verified"

    return False, f"unknown phase: {target_phase}"


async def advance_phase(db: Any, plan_id: int) -> tuple[str, str]:
    """Try to advance the plan to the next phase.

    Returns (new_phase, message) or (current_phase, reason_blocked).
    When phase advances to 'done', status is also set to 'completed'.
    """
    plan_row = await db.get_plan(plan_id)
    if plan_row is None:
        return "unknown", f"plan {plan_id} not found"

    # Convert PlanRow to dict for check_phase_entry
    plan_data = {
        "id": plan_row.id,
        "task_description": plan_row.task_description,
        "chunks": plan_row.chunks,
        "dependency_edges": plan_row.dependency_edges,
        "phase": plan_row.phase,
        "spec_file": plan_row.spec_file,
        "test_files": plan_row.test_files,
        "review_id": plan_row.review_id,
        "current_wave": plan_row.current_wave,
        "wave_verification": plan_row.wave_verification,
        "status": plan_row.status,
    }

    # Look up review verdict if review_id is set
    if plan_row.review_id is not None:
        reviews = await db.get_foil_reviews()
        for r in reviews:
            if r.id == plan_row.review_id:
                plan_data["review_verdict"] = r.verdict
                break

    current_phase = plan_row.phase
    current_idx = PHASE_ORDER.index(current_phase)
    if current_idx >= len(PHASE_ORDER) - 1:
        return current_phase, "already at final phase"

    next_phase = PHASE_ORDER[current_idx + 1]
    allowed, reason = check_phase_entry(plan_data, next_phase)

    if not allowed:
        return current_phase, reason

    update_fields: dict[str, Any] = {"phase": next_phase}
    if next_phase == "done":
        update_fields["status"] = "completed"

    await db.update_plan(plan_id, **update_fields)
    return next_phase, f"advanced to {next_phase}"
