# Calx

Your AI agent keeps making the same mistakes. Calx makes it stop.

You correct your AI agent. It learns for that session. Next session, same mistake. You correct it again. The correction never transfers between sessions, between agents, or between projects.

Calx captures corrections, detects when the same mistake recurs, promotes recurring corrections into rules, and injects those rules at the start of every session automatically.

```bash
calx correct "don't mock the database in integration tests"
# → Logged C014 (2026-03-22). Matches C007: "don't mock the database." (3rd occurrence — promotion eligible.)

# Next session, your agent loads the rule automatically. No manual editing. No copy-paste.
```

## Install

```bash
pip install getcalx
calx init
```

Requires Python 3.10+. Works with Claude Code. Cursor, Copilot, and Windsurf support planned. Any agent with session hooks can integrate.

## How it works

**Capture** → **Detect** → **Promote** → **Inject**

- You correct your agent. Calx logs it to an append-only event log. Three capture layers ensure nothing is lost: explicit command, session-end prompt, and dirty-exit recovery. The agent can also capture corrections itself. The generated CLAUDE.md instructs agents to run `calx correct` when corrected, so most corrections require no human action.
- Calx silently matches new corrections against existing ones. When the same correction recurs 3+ times, it surfaces once at the end of your current task as a single yes/no. Never mid-flow.
- On approval, the correction graduates to a rule in `.calx/rules/{domain}.md`, written in your own words. The full temporal chain is preserved as provenance.
- At the start of every session, domain-specific rules are injected into the agent's context via hooks. The agent reads and applies them before writing any code.

Each pass through this loop tightens the correction surface. Without intervention, you'll average ~2.9 corrections per task, every task, forever. With Calx, that number drops as rules compound.

## What this changes about how you work

Calx isn't just a correction logger. It encodes an orchestration methodology as automation so you stop managing your agent and start working with it.

**Token discipline.** Calx auto-detects your subscription tier and enforces context limits (Max: 200k soft / 250k ceiling, Pro: 80k / 100k). You never hit compaction, which means the correction signal, the thing that makes the learning loop work, is never destroyed by context summarization.

**Session lifecycle runs itself.** Session start injects rules, shows an effectiveness signal (corrections trending down per domain), and gates edits until rules are read. Session end captures uncommitted corrections, writes a clean-exit marker, and hands off state to the next session. If a session crashes, dirty-exit recovery prompts for anything that was lost.

**Scoped rules, scoped agents.** Rules sync from `.calx/rules/` to `AGENTS.md` files co-located in your source directories. When you dispatch a subagent to work on `src/api/`, it reads `src/api/AGENTS.md` and gets exactly the rules it needs, nothing more. Your main window coordinates. Subagents do focused deep work.

```
src/
├── api/
│   ├── AGENTS.md          ← rules for API work
│   └── routes.py
├── services/
│   ├── AGENTS.md          ← rules for service layer
│   └── auth.py
└── db/
    ├── AGENTS.md          ← rules for data access
    └── migrations/
```

**Distillation runs in the background.** Recurrence detection is silent. Promotion surfaces at task boundaries, not mid-flow. Weekly review is a PR-style diff of your rule set. The system learns while you work.

## Rule health

Not all rules age the same way. Architectural rules (structural fixes that eliminate an error class) don't decay from dormancy. Zero corrections means they're working. Process rules decay with age unless reinforced. Calx tracks the difference and surfaces when a recurring process rule should become an architectural fix instead.

## Why Calx over alternatives?

Other approaches assume corrections compound and transfer between agents. Share rules, everyone gets better. Our evidence shows they don't. We gave an agent 237 transferred rules and 30% of new corrections fell in categories those rules explicitly covered. So Calx automates the formation process instead of trying to share the output.

| Approach | What it does | What it misses |
|----------|-------------|---------------|
| **Editing CLAUDE.md by hand** | Works. Rules persist across sessions. | No recurrence detection. No health tracking. No signal when rules conflict or go stale. Scales to ~20 rules before it becomes a wall of text agents skim. |
| **Compound engineering** | Document corrections, share rules across agents. | Assumes rules transfer as behavior. Our evidence says they transfer as documentation only. The agent reads them, follows them mechanically, and still gets them wrong in novel contexts. |
| **Agent memory tools** (Mem0, etc.) | Store and retrieve information across sessions. | Same transfer assumption, different mechanism. **30% of new corrections fell in categories with explicit rules.** |
| **Doing nothing** | Zero overhead. | ~2.9 corrections per task, every task, forever. That's the error floor without intervention. |
| **Calx** | Captures corrections, detects recurrence, promotes to rules, injects via hooks, enforces token discipline, automates the session lifecycle, scopes rules to directories, tracks health. | Doesn't try to transfer corrections between agents. Accelerates behavioral formation within each relationship instead. |

## The evidence

We gave an AI agent 237 rules learned from another agent. It made 44 new mistakes, 13 in categories the rules explicitly covered. Process rules showed ~50% persistence. Architectural fixes had zero recurrence.

[The Behavioral Plane (paper)](https://doi.org/10.5281/zenodo.15054630) | [Evidence repo](https://github.com/getcalx/calx-paper-evidence)

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
| `calx config` | View or modify configuration |
| `calx stats` | Local metrics: corrections by domain, recurrence rates, trends |

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

## Development

```bash
pip install -e ".[dev]"

pytest                    # 323 tests
ruff check src/ tests/    # Lint
mypy src/calx/            # Type check
```

## Contributing

Contributions welcome. Please open an issue first for anything beyond small fixes so we can align before you invest time.

## License

MIT. The complete learning loop ships free with no feature gates.
