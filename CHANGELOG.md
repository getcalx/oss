# Changelog

## 0.7.0 (2026-04-02)

- Removed compilation engine, learning mode classifier, and compile_rule tool from OSS package
- Removed `calx compilations` CLI command
- Compilation pipeline is now proprietary (available in Calx Pro)
- Stripped compilation stats and candidates from briefing resource
- 671 tests passing

## 0.6.0 (2026-04-01)

Breaking release. Schema v6, enforcement layer, compilation pipeline, orchestration infrastructure.

### Reframe
- Corrections are diagnostic signals for environmental modification, not rules to memorize
- Docs, README, and framing updated to reflect: text rules fail, compiled mechanisms work
- New `docs/concepts.md` explaining the behavioral plane, pair-specificity, and compilation

### Enforcement Layer (new)
- HTTP enforcement server on :4195 (Starlette/uvicorn) runs alongside MCP stdio
- Composite transport: `calx serve` runs MCP over stdio + HTTP enforcement in one process
- Session lifecycle: register_session, orientation gate, tool-call counting, collapse guard, end_session
- Atomic state files in `.calx/state/` for fast hook reads without server round-trips
- Consolidated `enforce.py` hook replaces `orientation_gate.py` + `collapse_guard.py`
- Auto-init on first `calx serve`: creates `.calx/`, registers hooks, generates auth token

### Compilation Pipeline (new)
- `compile_rule` tool: mark a rule as compiled with mechanism type (code_change, config_change, hook_addition, architecture_change)
- `CompilationEventRow` tracks compilation history with verification windows
- Post-compilation recurrence monitoring (14-day verification)
- Learning mode classification: architectural (permanent) vs process (needs reinforcement)
- Compilation candidates surfaced in briefing
- `calx compilations` CLI shows stats and candidates

### Orchestration Infrastructure (new)
- `create_plan` / `update_plan` / `dispatch_chunk` / `redispatch_chunk` / `verify_wave` tools
- Kahn's algorithm for dependency-aware wave computation
- Phase enforcement: spec -> test -> chunk -> plan -> build -> verify -> commit -> done
- File-disjoint validation: parallel chunks sharing files flagged on plan creation
- Chunk token budget estimation: oversized chunks flagged against session soft_cap
- `calx plan` CLI with --status, --complete, --block, --advance, --verify
- Orchestration protocol injection in briefing ("you are an orchestrator, not a builder")

### Foil Review (new)
- `record_foil_review` tool for adversarial cross-domain review records
- 5 default foil profiles shipped: backend, design, frontend, security, spec
- `calx review` CLI: --foil, --file, --record, --history, --gaps
- Review gaps surfaced in briefing (domains with >5 corrections and no review in 14+ days)

### Session Management (new)
- `register_session` / `end_session` tools with handoff support
- Session-end writes handoff (what_changed, what_others_need, decisions_deferred, next_priorities)
- "Since last session" section in briefing from latest handoff
- Dirty exit detection: previous session that didn't end cleanly
- Staleness warnings when handoffs are older than 24 hours

### Board State (new)
- `update_board` tool for cross-agent coordination
- `calx://board` MCP resource
- `calx board` CLI shows items grouped by status

### Health Scoring (expanded)
- Full health scoring engine: recurrence, conflict, superseded, and age-based staleness decay
- `score_all_rules()` runs at session end, persists scores to DB
- `calx rules --health` shows scores, `--role ROLE` filters by role
- Conflict detection before auto-promotion (prevents contradictory rules)
- `deactivate_rule` tool with reason tracking

### Telemetry (new)
- Privacy-first anonymous telemetry: counts, booleans, environment info only
- NEVER collects: correction text, rule text, file paths, project names
- `calx telemetry --show` to audit, `--off` to disable permanently
- Install ping (one-time) + session_end events (per-session)
- Endpoint: Supabase Edge Function

### Schema
- Schema v6 (was v2). SQL migration runner with SAVEPOINT wrapping, backup before migration
- Version guard: refuses to run if DB was created by a newer version
- Schema validation: verifies live schema matches dataclass expectations after migration
- New tables: sessions, handoffs, board_state, foil_reviews, compilation_events, plans
- New fields on corrections: learning_mode
- New fields on rules: learning_mode, health_status, last_validated_at, compiled_at, compiled_via, compiled_from_mode, recurrence_at_compilation, deactivation_reason, role

### CLI (6 new commands)
- `calx rules [--health] [--role ROLE]`
- `calx board`
- `calx promote [ID --text TEXT]`
- `calx compilations`
- `calx review [--foil NAME --file PATH | --record | --history | --gaps]`
- `calx plan [--status | --complete ID | --block ID | --advance | --verify N]`

### Dependencies
- Added: starlette>=0.37, uvicorn>=0.29
- Foil profiles and migration SQL files included in package data

### Docs
- README rewritten with new framing
- New: docs/concepts.md (behavioral plane, pair-specificity, compilation)
- New: docs/upgrading.md (migration guarantees, breaking changes)
- Updated: correction-workflow, mcp-reference, hooks, quickstart

## 0.5.1 (2026-03-30)

- Single version source in __init__.py
- FastMCP pin >=3.1,<4
- Import guard for calx.serve

## 0.4.0 (2026-03-30)

### MCP Server
- **`calx serve` command** starts an MCP server (streamable-http or stdio transport)
- 3 MCP resources: `calx://briefing/{surface}`, `calx://rules`, `calx://corrections`
- 3 MCP tools: `log_correction`, `promote_correction`, `get_briefing`
- SQLite backend with WAL mode, async via aiosqlite
- File-based migration imports existing `.calx/` data into SQLite on first run

### Positioning
- "Behavioral governance compiler" -- compile corrections into enforceable mechanisms
- HyperAgents complementary framing in README and evidence section

### Safety and robustness
- Auth token lazy generation (skip for stdio transport)
- Atomic recurrence count increment (SQL-level, no lost updates)
- Transaction boundaries on correction logging flow
- Column name whitelist on update methods (prevents injection)
- Retry-on-conflict for correction ID generation
- SQLite BUSY retry with exponential backoff (50/100/200ms)
- Per-surface rate limiting on log_correction (60/min)
- Content quarantine via `QuarantineScanner` protocol (swappable, regex default)
- Config field whitelist against dataclass fields
- Double-promotion guard on promote_correction
- SQL-level keyword filter for recurrence search (no more limit=100 cap)

### Health
- Auto-deactivation of rules at critical health (below 0.3)
- Warning surfaced in briefing for rules below 0.5

### Cleanup
- Founder-specific state removed from OSS (surface map, empty briefing sections)
- Unified similarity implementation (serve canonical, CLI imports from it)
- Unclosed file handles fixed in hooks
- Session start hook simplified (file-based only in v0.4.0)
- Telemetry disclosure section in README
- `docs/` folder: quickstart, mcp-reference, correction-workflow, hooks

### Dependencies
- `[serve]` optional extra: `fastmcp>=3.1`, `aiosqlite>=0.20`
- `pytest-asyncio>=0.23` added to dev deps

## 0.3.0 (2026-03-23)

- Strip all telemetry and phone-home code
- Non-interactive `calx init` (Claude can run it directly)
- Audit fixes

## 0.2.4 (2026-03-23)

- Status shows "not yet promoted" instead of confusing "pending distillation"
- Status shows "ready for promotion" when corrections hit recurrence threshold
- README: macOS/Linux only, Windows coming soon

## 0.2.3 (2026-03-23)

- Update check at session start — pings PyPI once per 24 hours, shows "Calx X.Y.Z available" if newer version exists
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
