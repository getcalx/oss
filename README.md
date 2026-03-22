# Calx

Behavioral governance layer for AI coding agents. Makes corrections compound.

Calx captures the corrections you make to AI agents, detects when the same mistake recurs, and promotes recurring corrections into rules that get injected at the start of every session. Your agent stops making the same mistake twice.

## The problem

You correct an AI agent. It learns -- for that session. Next session, same mistake. You correct it again. The correction doesn't transfer between sessions, between agents, or between projects. Your knowledge leaks.

## How Calx works

1. **Capture** -- `calx correct "don't mock the database in integration tests"` logs the correction to an append-only event log (`corrections.jsonl`)
2. **Detect** -- Calx matches new corrections against existing ones. When the same correction recurs 3+ times, it surfaces for promotion
3. **Promote** -- Recurring corrections become rules, written to `.calx/rules/{domain}.md`
4. **Inject** -- At session start, all active rules are injected into the agent's context via hooks

This is the **learning loop**: correct -> detect recurrence -> promote to rule -> inject at session start -> fewer corrections needed.

## Install

```bash
pip install getcalx
```

## Quick start

```bash
# Initialize Calx in your project
calx init

# Log a correction
calx correct "always validate API inputs before processing"

# Check status
calx status

# Run distillation (promote recurring corrections to rules)
calx distill

# View health of your rule set
calx health score
```

## Architecture

```
.calx/
├── calx.json              # Configuration
├── corrections.jsonl       # Append-only event log (never rewritten)
├── rules/
│   └── {domain}.md         # Promoted rules per domain
├── health/
│   ├── state.json          # Health scores
│   └── .last_clean_exit    # Session state marker
└── method/
    ├── how-we-document.md  # Learning loop methodology
    ├── orchestration.md    # Hook and session management
    ├── dispatch.md         # Agent dispatch scaffolding
    └── review.md           # Review process
```

**Event-sourced corrections** -- `corrections.jsonl` is truly append-only. State is derived by replaying events. No rewrites, no mutations.

**Three-tier distillation:**
- **Tier 1** -- Silent recurrence counter (automatic)
- **Tier 2** -- Binary promote/reject at threshold (developer approves)
- **Tier 3** -- Weekly review of rule effectiveness

**Hook-based orchestration:**
- `session-start` -- Rule injection, dirty exit check, effectiveness signal, token discipline
- `session-end` -- Uncommitted changes check, undistilled reminder, clean exit marker
- `orientation-gate` / `collapse-guard` -- Pure bash PreToolUse hooks (no Python on the hot path)

## Commands

| Command | Description |
|---------|-------------|
| `calx init` | Initialize Calx in current project |
| `calx correct <text>` | Log a correction |
| `calx status` | Show project status |
| `calx distill` | Promote recurring corrections to rules |
| `calx config` | View or modify configuration |
| `calx health` | Health analysis (score, conflicts, staleness, dedup, coverage) |
| `calx dispatch` | Generate dispatch prompt for a domain agent |
| `calx stats` | Show local metrics |

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/calx/
```

## License

MIT
