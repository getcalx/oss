# Changelog

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
