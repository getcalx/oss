# Handoff: Session 3 → Session 4

## What's Done

**239 tests passing. Full CLI working. `calx --help` shows all 8 commands.**

### Waves 1-2: Core Layer (54 tests)
All files in `src/calx/core/`: config, corrections, rules, events, state, telemetry, ids, integrity.

### Wave 3: Feature Layers (88 tests)
- `capture/` — explicit.py, session_end.py, recovery.py
- `distillation/` — similarity.py, recurrence.py
- `health/` — coverage.py, conflicts.py
- `hooks/` — installer.py + 4 shell templates (session_start, session_end, orientation_gate, collapse_guard)
- `dispatch/` — generator.py, review.py
- `templates/` — calx_readme.py, claude_md_scaffold.py

### Wave 4: CLI + Tier 2/3 + Remaining Health (97 tests)
- `cli/` — main.py, init_cmd.py, correct.py, status.py, distill.py, config_cmd.py, health.py (5 subcommands), dispatch_cmd.py, stats.py
- `distillation/` — promotion.py (Tier 2), review.py (Tier 3)
- `health/` — scoring.py, staleness.py, dedup.py, conversion.py, floor.py

All CLI commands wired in main.py. `calx --version` returns 0.1.0.

## What's Next (Wave 5: Polish + Integration)

| Chunk | What | Details |
|-------|------|---------|
| 5A | `calx _hook` commands | `_hook session-start` and `_hook session-end` — the Python callbacks the shell hooks invoke. This is the CRITICAL PATH. The spec has full implementation at lines ~1180-1302. These wire rule injection, dirty exit check, effectiveness signal, token discipline, promotion candidates, stats POST, clean exit. |
| 5B | Method docs | 4 markdown files copied to `.calx/method/` during init: how-we-document.md, orchestration.md, dispatch.md, review.md. Content from `~/calx-brain/product/methodology.md`. |
| 5C | Integration tests | End-to-end: init → correct → recurrence → promote → status → health. Verify the full flow works. |
| 5D | README.md | Project README for the repo (not the .calx/README). |

**5A is the most important.** The hooks ARE the product — they're what makes rules inject at session start and corrections surface at session end. Without them the shell templates call `calx _hook session-start` and get nothing back.

## Spec Location

`~/calx-brain/product/calx-cli-engineering-spec.md` (v2.0)
- `_hook session-start` implementation: lines ~1174-1266
- `_hook session-end` implementation: lines ~1270-1302

## Key Design Decisions (don't revisit)

- corrections.jsonl is event-sourced — zero rewrites, state by replay
- PreToolUse hooks are pure bash (no Python on Edit/Write hot path)
- Token discipline is injected instructions, not a runtime hook
- Three-tier distillation: silent counter → binary promote → weekly review
- Free tier ships everything except advanced health analytics
- Orientation gate scoped to project hash (multi-repo safe)

## Post-Merge Fixes Applied in Previous Sessions

- `capture/explicit.py` — RecurrenceResult used as dict, fixed to dataclass attribute access
- `cli/__init__.py` — trivial merge conflict (two docstrings) resolved
