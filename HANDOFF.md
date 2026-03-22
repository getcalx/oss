# Handoff: Session 2 → Session 3

## What's Done

### Waves 1-2: Core Layer (54 tests)
All files in `src/calx/core/`:
- `config.py` — CalxConfig dataclass, load/save/find
- `corrections.py` — event-sourced JSONL (append-only, fsync, materialize by replay)
- `rules.py` — markdown rule parser/writer (production AGENTS.md format)
- `events.py` — append-only instrumentation log
- `state.py` — health state + clean exit tracking
- `telemetry.py` — anonymous stats payload + POST
- `ids.py` — UUID, sequential IDs, session IDs
- `integrity.py` — JSONL corruption recovery

### Wave 3: Feature Layers (88 new tests, 142 total)
All seven chunks built in parallel and merged:

| Chunk | Module | Files | Tests |
|-------|--------|-------|-------|
| 3A | Capture | `capture/explicit.py`, `session_end.py`, `recovery.py` | 15 |
| 3B | Distillation Tier 1 | `distillation/similarity.py`, `recurrence.py` | 17 |
| 3C | Health (free) | `health/coverage.py` | 7 |
| 3D | Health (conflicts) | `health/conflicts.py` | 11 |
| 3E | Hooks | `hooks/installer.py` + 4 shell templates | 9 |
| 3F | Dispatch | `dispatch/generator.py`, `review.py` | 19 |
| 3G | Templates | `templates/calx_readme.py`, `claude_md_scaffold.py` | 10 |

Post-merge fix: `capture/explicit.py` had to be patched to use `RecurrenceResult` dataclass attributes instead of dict subscripts (the capture and distillation agents built independently).

## What's Next (Wave 4: CLI Commands + Tier 2/3 Distillation)

| Chunk | Module | Key Files |
|-------|--------|-----------|
| 4A | CLI main + init | `cli/main.py`, `cli/init_cmd.py` |
| 4B | CLI correct + status | `cli/correct.py`, `cli/status.py` |
| 4C | CLI distill | `cli/distill.py` |
| 4D | CLI health + config | `cli/health.py`, `cli/config_cmd.py` |
| 4E | CLI dispatch + stats | `cli/dispatch_cmd.py`, `cli/stats.py` |
| 4F | Distillation Tier 2 | `distillation/promotion.py` |
| 4G | Distillation Tier 3 | `distillation/review.py` |
| 4H | Health (remaining) | `health/scoring.py`, `health/staleness.py`, `health/dedup.py`, `health/conversion.py`, `health/floor.py` |

After Wave 4: Wave 5 (method docs, README, integration tests, `calx _hook` commands).

## Spec Location

`~/calx-brain/product/calx-cli-engineering-spec.md` (v2.0)

## Key Design Decisions (don't revisit)

- corrections.jsonl is event-sourced — zero rewrites, state by replay
- PreToolUse hooks are pure bash (no Python on Edit/Write hot path)
- Token discipline is injected instructions, not a runtime hook
- Three-tier distillation: silent counter → binary promote → weekly review
- Free tier ships everything except advanced health analytics
- Orientation gate scoped to project hash (multi-repo safe)
