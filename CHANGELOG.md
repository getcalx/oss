# Changelog

## 0.2.2 (2026-03-23)

- Fixed Zenodo paper link in README

## 0.2.1 (2026-03-23)

- Weekly review prompt at session start — checks system clock, surfaces if 7+ days since last review
- Orientation gate simplified — dropped session ID matching, just checks for any recent marker

## 0.2.0 (2026-03-23)

### Operating system layer
- **CLAUDE.md scaffold rewritten** with behavioral instructions: session flow, self-capture, token discipline, orchestration model, anti-patterns
- **AGENTS.md co-location** — `calx sync` writes domain rules to code directories so subagents find them in context
- **Self-capture mechanism** — CLAUDE.md instructs agents to run `calx correct` when corrected. No human action required.
- **Session-end capture prompt** — asks about uncaptured corrections when none were logged
- **Dispatch prompts** now include AGENTS.md path, self-capture instruction, and token discipline
- **Promotion auto-syncs** AGENTS.md after writing rules

### New commands
- `calx sync [domain]` — write AGENTS.md files from `.calx/rules/`
- `calx health conversion` — surface process rules that should become architectural fixes

### Fixes from user testing
- **Hook paths are now absolute** — relative paths broke on Windows and when cwd != project root
- **Orientation gate marker** moved from `/tmp/` to `.calx/health/` — cross-platform, no path hashing
- **Comma-separated domain parsing** — `calx init -d "api,frontend"` now splits correctly
- **CLAUDE.md append** — existing CLAUDE.md gets Calx sections appended with conflict scanning instead of being skipped
- **Phone home defaults to false** — opt-in, not opt-out
- **Non-interactive defaults to Pro tier** (80k/100k) — conservative default
- **`--context` flag wired through** — was silently discarded
- **`promote()` guards empty corrections** — no crash on edge case
- **`config --set` validates integers** with range checks
- **`remove_clean_exit` moved to top** of session-start — crash during startup no longer leaves false clean state
- **`git status` scoped to project directory** in session-end hook
- **Date stamp in correction feedback** — `Logged C014 (2026-03-22)` for traceability

### Init improvements
- Auto-detects Claude plan (Max/Pro/Team/Enterprise) and sets token discipline thresholds
- Auto-populates `domain_paths` from detected directories
- Generates `.calx/.gitignore` (commit rules, ignore local state)

### Code quality
- 62 ruff errors resolved
- Rule ID regex accepts 3+ digits (was exactly 3)
- jq dependency documented for collapse guard

### Infrastructure
- Phone home module (`core/phone_home.py`) — anonymous, non-blocking, daemon thread
- `domain_paths` config field for AGENTS.md co-location mapping

## 0.1.0 (2026-03-21)

Initial implementation. Event-sourced corrections, three-tier distillation, hook-based session lifecycle, 8 CLI commands, health analysis suite.
