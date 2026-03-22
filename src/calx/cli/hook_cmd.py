"""Internal hook callbacks: session-start and session-end.

These are the CRITICAL PATH — invoked by shell hooks installed during `calx init`.
The shell templates call `calx _hook session-start` and `calx _hook session-end`.
"""

from __future__ import annotations

import json
import subprocess

import click

from calx.core.config import find_calx_dir, load_config
from calx.core.corrections import get_undistilled, materialize
from calx.core.integrity import check_jsonl_integrity, repair_jsonl
from calx.core.rules import read_all_rules, format_rule_block
from calx.core.state import check_clean_exit, remove_clean_exit, write_clean_exit
from calx.core.telemetry import build_payload, post_stats
from calx.distillation.recurrence import get_promotion_candidates


@click.group(hidden=True, name="_hook")
def hook_group():
    """Internal hook callbacks."""


@hook_group.command("session-start")
def hook_session_start():
    """Session start hook — rule injection, effectiveness signal, token discipline."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        return  # not a Calx project, exit silently

    config = load_config(calx_dir)
    output_parts: list[str] = []

    # 1. Dirty exit check
    exit_status = check_clean_exit(calx_dir)
    if not exit_status.was_clean:
        output_parts.append(
            "WARNING: Previous session did not exit cleanly. "
            "Corrections from that session may be uncaptured. "
            "Run `calx correct` to log any missed corrections."
        )

    # 2. JSONL integrity check
    corr_path = calx_dir / "corrections.jsonl"
    if corr_path.exists():
        result = check_jsonl_integrity(corr_path)
        if not result.is_clean:
            repair_jsonl(corr_path)
            output_parts.append(
                f"Repaired {len(result.malformed_lines)} malformed entries in corrections.jsonl"
            )

    # 3. Rule injection — the core mechanism
    all_rules = read_all_rules(calx_dir)
    if all_rules:
        output_parts.append("--- CALX RULES (read before working) ---")
        for domain_name in sorted({r.domain for r in all_rules}):
            domain_rules = [r for r in all_rules if r.domain == domain_name]
            output_parts.append(f"\n## {domain_name} ({len(domain_rules)} rules)")
            for rule in domain_rules:
                output_parts.append(format_rule_block(rule))
        output_parts.append("--- END CALX RULES ---")

    # 4. Effectiveness signal — per-domain correction delta
    all_corrections = materialize(calx_dir)
    if all_corrections:
        for domain_name in sorted(config.domains):
            domain_corrs = [c for c in all_corrections if c.domain == domain_name]
            if not domain_corrs:
                continue
            domain_rules = [r for r in all_rules if r.domain == domain_name]
            # Find last two distinct session_ids for this domain
            session_ids = list(dict.fromkeys(
                c.session_id for c in reversed(domain_corrs) if c.session_id
            ))
            prev_count = (
                len([c for c in domain_corrs if c.session_id == session_ids[0]])
                if session_ids else 0
            )
            before_count = (
                len([c for c in domain_corrs if c.session_id == session_ids[1]])
                if len(session_ids) > 1 else None
            )
            if before_count is not None:
                delta = (
                    "down" if prev_count < before_count
                    else "up" if prev_count > before_count
                    else "same"
                )
                output_parts.append(
                    f"{domain_name}: {prev_count} corrections last session "
                    f"({delta} from {before_count}). {len(domain_rules)} rules active."
                )
            elif prev_count > 0:
                output_parts.append(
                    f"{domain_name}: {prev_count} corrections last session. "
                    f"{len(domain_rules)} rules active."
                )

    # 5. Undistilled corrections
    undistilled = get_undistilled(calx_dir)
    if undistilled:
        output_parts.append(
            f"\n{len(undistilled)} corrections pending distillation. "
            "Run `calx distill` when ready."
        )

    # 6. Promotion candidates (Tier 2)
    candidates = get_promotion_candidates(calx_dir, config.promotion_threshold)
    if candidates:
        output_parts.append(
            f"\n{len(candidates)} corrections ready for promotion "
            f"(triggered {config.promotion_threshold}+ times)."
        )

    # 7. Token discipline instructions
    td = config.token_discipline
    output_parts.append(
        f"\n--- TOKEN DISCIPLINE ---\n"
        f"Soft cap: {td.soft_cap:,} tokens. When context feels heavy, "
        "commit and consider a handoff.\n"
        f"Ceiling: {td.ceiling:,} tokens. Stop. Commit everything. "
        "Write a handoff note. End the session.\n"
        "Context compaction permanently destroys learning signal.\n"
        "--- END TOKEN DISCIPLINE ---"
    )

    # 8. Remove stale clean-exit marker, write fresh session start
    remove_clean_exit(calx_dir)

    # Output everything
    if output_parts:
        click.echo("\n".join(output_parts))


@hook_group.command("session-end")
def hook_session_end():
    """Session end hook — uncommitted check, undistilled reminder, stats, clean exit."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        return

    output_parts: list[str] = []

    # 1. Uncommitted changes
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip():
            output_parts.append(
                "Uncommitted changes detected. Commit before ending session."
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass  # git not available or timed out — skip

    # 2. Undistilled corrections
    undistilled = get_undistilled(calx_dir)
    if undistilled:
        output_parts.append(f"{len(undistilled)} corrections pending distillation.")

    # 3. Stats POST (if opted in)
    config = load_config(calx_dir)
    if config.stats_opt_in:
        try:
            payload = build_payload(calx_dir)
            post_stats(payload)  # silent, never blocks
        except Exception:
            pass  # never let stats break session end

    # 4. Clean exit marker
    write_clean_exit(calx_dir)

    if output_parts:
        click.echo(json.dumps({"followup_message": "\n".join(output_parts)}))
