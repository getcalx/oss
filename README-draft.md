# Calx

Persistent learning for AI coding agents.

You correct your AI agent. It learns — for that session. Next session, same mistake. You correct it again. The correction never transfers between sessions, between agents, or between projects.

Calx fixes this. It captures corrections, detects when the same mistake recurs, promotes recurring corrections into rules, and injects those rules at the start of every session. Your agent stops making the same mistake twice.

```bash
# Initialize in your project
calx init

# Correct your agent (one command, zero prompts)
calx correct "don't mock the database in integration tests"
# → Logged C014. Matches C007: "don't mock the database." (3rd occurrence — promotion eligible.)

# Next session start, your agent sees:
# ┌─────────────────────────────────────────────┐
# │ tests-R003: No database mocks in integration │
# │ Source: C007, C011, C014 | Status: active    │
# │                                               │
# │ Integration tests hit real databases. Mock    │
# │ tests passed while prod migrations failed.   │
# └─────────────────────────────────────────────┘

# Review what's accumulated
calx status
# → 14 corrections across 3 domains. 4 rules active. 2 pending promotion.

# Promote recurring corrections to rules
calx distill
```

## Why this exists

We gave an AI agent 237 rules learned from another agent. It made 44 new mistakes — 13 in categories the rules explicitly covered.

Rules transfer as documentation. The behavioral calibration — the felt consequence of being corrected in context — does not. A rule like "always verify the patch target matches the import path" is correct but insufficient. The agent reads it, follows it mechanically, and still gets it wrong in novel contexts.

This isn't a tooling problem. It's a learning problem. Process rules have ~50% persistence. Architectural fixes (structural changes that eliminate the error class entirely) have zero recurrence. Calx tracks this distinction and surfaces it.

Full findings: [The Behavioral Plane](https://doi.org/10.5281/zenodo.15054630) | Evidence: [github.com/getcalx/calx-paper-evidence](https://github.com/getcalx/calx-paper-evidence)

## Install

```bash
pip install getcalx
```

Requires Python 3.10+. Works with Claude Code for now. Support for Cursor, Copilot, Windsurf, or any agent that supports session hooks is planned.

## How it works

### The learning loop

**Capture** → **Detect** → **Promote** → **Inject**

1. You correct your agent mid-session. Calx logs the correction to an append-only event log (`corrections.jsonl`). Three capture layers ensure nothing is lost: explicit command, session-end prompt, and dirty-exit recovery.

2. Calx silently matches new corrections against existing ones using keyword similarity. When the same correction recurs 3+ times, it surfaces for promotion — once, at the end of your current task, as a single yes/no decision. Never mid-flow.

3. On approval, the correction graduates to a rule in `.calx/rules/{domain}.md`, written in your own words from the most recent correction. The temporal chain (every prior correction in the sequence) is preserved as provenance.

4. At the start of every session, domain-specific rules are injected into the agent's context via hooks. The agent reads and applies them before writing any code.

Each pass through this loop tightens the correction surface. Corrections compound within the relationship between you and your agent — not by transferring rules, but by reducing the space where mistakes can happen.

### Orchestration via hooks

Hooks encode your methodology as automation. Without them, you remember to check things. With them, the system checks for you.

| Hook | Trigger | What it does |
|------|---------|-------------|
| `session-start` | SessionStart | Injects rules, shows effectiveness signal, checks for dirty exit, surfaces promotion candidates |
| `session-end` | Stop | Checks uncommitted changes, reminds about undistilled corrections, writes clean-exit marker |
| `orientation-gate` | PreToolUse (Edit/Write) | Blocks file edits until rules are read — pure bash, no Python on the hot path |
| `collapse-guard` | PreToolUse (Edit/Write) | Warns if an edit would shrink a rules file by >20% — advisory, never blocks |

Hooks install into `.claude/settings.json` without clobbering existing configuration. `calx init` handles this automatically.

### Scoped rules via AGENTS.md

Rules live where the code lives. Calx syncs rules from `.calx/rules/` to `AGENTS.md` files co-located in your source directories:

```
src/
├── api/
│   ├── AGENTS.md          ← rules for API work
│   ├── routes.py
│   └── middleware.py
├── services/
│   ├── AGENTS.md          ← rules for service layer
│   └── auth.py
└── db/
    ├── AGENTS.md          ← rules for data access
    └── migrations/
```

When you dispatch a subagent to work on `src/api/`, it reads `src/api/AGENTS.md` and gets exactly the rules it needs — nothing more. The main window acts as orchestrator; subagents do focused work with scoped context.

```bash
# Sync rules to AGENTS.md files in source directories
calx sync

# Generate a dispatch prompt for a domain agent
calx dispatch api
# → Outputs: rules, task scope, file list, explicit prohibitions

# Generate a cross-domain foil review prompt
calx dispatch --review api
```

### Rule health

Not all rules age the same way. Calx tracks two types:

- **Architectural rules** don't decay from dormancy. An eliminated error class producing zero corrections means the rule is working. They decay from recurrence (rule violated), conflict, or supersession.
- **Process rules** decay from all of the above plus age. A process rule that hasn't been reinforced in 30 days loses health — it may be stale, or the workflow changed.

```bash
calx health score        # Per-rule health scores
calx health conflicts    # Detect contradicting rules
calx health staleness    # Flag dormant process rules
calx health coverage     # Verify rule ↔ correction traceability
calx health conversion   # Surface process rules that should become architectural fixes
```

## Features

- **Append-only event log** — `corrections.jsonl` is truly immutable. State derived by replay. No rewrites, no mutations.
- **Three-tier distillation** — Silent recurrence counting (automatic) → binary promote/reject (you decide) → weekly batch review (you curate)
- **Micro-reward at capture** — Immediate feedback: what it matched, how many times, whether it's promotion-eligible
- **Token discipline** — Soft cap and ceiling warnings prevent context compaction from destroying correction signal. Auto-configured by model detection.
- **Domain auto-detection** — `calx init` inspects your project structure and suggests domains. Override with `-d "api,services,db"`.
- **CLAUDE.md scaffolding** — Generates a behavioral CLAUDE.md with session flow, self-capture instructions, anti-patterns, and token discipline
- **Method documentation** — `.calx/method/` contains 4 methodology docs auto-generated during init: how-we-document, orchestration, dispatch, review
- **Tool-agnostic** — Works with any agent that supports session hooks. Not locked to one IDE or model provider.
- **Self-capture** — The generated CLAUDE.md instructs agents to run `calx correct` when corrected. No human action required for most corrections.

## Project structure

```
.calx/
├── calx.json              # Configuration (domains, token discipline, thresholds)
├── corrections.jsonl       # Append-only event log (gitignored)
├── rules/
│   └── {domain}.md         # Promoted rules per domain (committed)
├── health/
│   ├── state.json          # Health scores per rule
│   └── .last_clean_exit    # Session state marker
├── method/
│   ├── how-we-document.md  # Three-tier learning model
│   ├── orchestration.md    # Session lifecycle and hooks
│   ├── dispatch.md         # Agent dispatch scaffolding
│   └── review.md           # Foil review methodology
└── hooks/
    ├── session-start.sh
    ├── session-end.sh
    ├── orientation-gate.sh
    └── collapse-guard.sh
```

## Commands

| Command | What it does |
|---------|-------------|
| `calx init` | Initialize `.calx/`, detect domains, scaffold CLAUDE.md, install hooks |
| `calx correct <text>` | Log a correction with automatic recurrence detection |
| `calx distill` | Promote recurring corrections or run weekly review (`--review`) |
| `calx status` | Corrections, rules, pending promotions at a glance |
| `calx sync` | Write AGENTS.md files to source directories from `.calx/rules/` |
| `calx dispatch <domain>` | Generate scoped dispatch prompt for builder or foil agent |
| `calx health <sub>` | Rule health: `score`, `conflicts`, `staleness`, `coverage`, `dedup`, `conversion` |
| `calx config` | View or modify configuration (`--get`, `--set`) |
| `calx stats` | Local metrics: corrections by domain, recurrence rates, trends |

## Why Calx over alternatives?

| Approach | What it does | What it misses |
|----------|-------------|---------------|
| **Editing CLAUDE.md by hand** | Works. Rules persist across sessions. | No recurrence detection. No health tracking. No signal when rules conflict or go stale. Scales to ~20 rules before it becomes a wall of text agents skim. |
| **Agent memory tools** (Mem0, etc.) | Store and retrieve information across sessions. | Assume rules transfer between agents. Our evidence says they don't — 30% of new corrections fell in categories with explicit rules. Memory is information-plane. Corrections are behavioral-plane. |
| **Doing nothing** | Zero overhead. | ~2.9 corrections per task, every task, forever. That's the error floor without intervention. |
| **Calx** | Captures corrections, detects recurrence, promotes to rules, injects via hooks, scopes to directories, tracks health. | Doesn't try to transfer behavioral calibration. Accelerates its formation instead. |

## Open source model

The full methodology ships free and open source, forever. No caps, no feature gates on the learning loop.

- **Free**: Correction capture (all three layers), three-tier distillation, rule injection via hooks, all orchestration hooks, dispatch scaffolding, CLAUDE.md generation, basic health checks, AGENTS.md sync. Single user, local.
- **Pro** (coming): Advanced health analytics, error floor tracking, process-to-architectural conversion surfacing, cross-device sync.
- **Team** (coming): Cross-person correction analytics, organizational telemetry, methodology compliance, admin controls.

Everything on your machine with your corrections is free. Everything crossing a boundary — agents, machines, people — is paid.

## Development

```bash
pip install -e ".[dev]"

pytest                    # 323 tests
ruff check src/ tests/    # Lint
mypy src/calx/            # Type check
```

## Contributing

Contributions welcome. Please open an issue first for anything beyond small fixes — this helps ensure alignment before you invest time.

## License

MIT
