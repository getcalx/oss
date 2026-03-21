# Handoff: Session 1 → Session 2

## What's Done (Waves 1-2)

**54 tests passing. Package installs. Core layer complete.**

All files in `src/calx/core/`:
- `config.py` — CalxConfig dataclass, load/save/find
- `corrections.py` — event-sourced JSONL (append-only, fsync, materialize by replay)
- `rules.py` — markdown rule parser/writer (production AGENTS.md format)
- `events.py` — append-only instrumentation log
- `state.py` — health state + clean exit tracking
- `telemetry.py` — anonymous stats payload + POST
- `ids.py` — UUID, sequential IDs, session IDs
- `integrity.py` — JSONL corruption recovery

Package scaffolding: `pyproject.toml`, `Makefile`, `LICENSE`, `.gitignore`

## What's Next (Wave 3: Feature Layers)

Seven independent chunks, dispatch in parallel:

| Chunk | Module | Key Files |
|-------|--------|-----------|
| 3A | Capture | `capture/explicit.py`, `session_end.py`, `recovery.py` |
| 3B | Distillation Tier 1 | `distillation/similarity.py`, `recurrence.py` |
| 3C | Health (free) | `health/coverage.py` |
| 3D | Health (conflicts) | `health/conflicts.py` |
| 3E | Hooks | `hooks/installer.py` + 4 shell templates |
| 3F | Dispatch | `dispatch/generator.py`, `review.py` |
| 3G | Templates | `templates/calx_readme.py`, `claude_md_scaffold.py` |

After Wave 3: Wave 4 (CLI commands + Tier 2/3 distillation) and Wave 5 (method docs, README, integration test).

## Spec Location

`~/calx-brain/product/calx-cli-engineering-spec.md` (v3.1)

## Build Plan

`~/.claude/plans/mossy-stargazing-wirth.md`

## Key Design Decisions (don't revisit)

- corrections.jsonl is event-sourced — zero rewrites, state by replay
- PreToolUse hooks are pure bash (no Python on Edit/Write hot path)
- Token discipline is injected instructions, not a runtime hook
- Three-tier distillation: silent counter → binary promote → weekly review
- Free tier ships everything except advanced health analytics
- Orientation gate scoped to project hash (multi-repo safe)
