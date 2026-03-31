# Calx

Your AI agent keeps making the same mistakes. Calx captures corrections, detects recurrence, and compiles them into rules and hooks that stick.

## Quickstart

```bash
pip install getcalx
calx init
```

That's it. `calx init` registers an MCP server in `.claude/settings.json`. Claude Code starts it automatically via stdio. Corrections, rules, and briefings flow over [MCP](https://modelcontextprotocol.io) backed by local SQLite. Built on [FastMCP](https://gofastmcp.com/getting-started/welcome).

```bash
# Log a correction (your agent can do this too via the MCP log_correction tool)
calx correct "don't mock the database in integration tests"
# → Logged C014. Matches C007: "don't mock the database." (3rd occurrence — promotion eligible.)

# Promote to a rule
calx distill
# → Promoted to tests-R003. Available in every future briefing.
```

Not using Claude Code? Run `calx serve` and point your MCP client at it:

```bash
calx serve                          # streamable-http on 127.0.0.1:4195
calx serve --transport stdio        # for Claude Desktop, Cursor, etc.
```

Requires Python 3.10+. Works with anything MCP-compatible.

## How it works

**Capture** -> **Detect** -> **Promote** -> **Inject**

1. You correct your agent. Calx logs it to an append-only event log. Three capture layers ensure nothing is lost: explicit command, session-end prompt, and dirty-exit recovery. The agent can also capture corrections itself via `calx correct` or the MCP `log_correction` tool.
2. Calx silently matches new corrections against existing ones using keyword similarity. When the same correction recurs 3+ times, it surfaces once at the end of your current task as a single yes/no. Never mid-flow.
3. On approval, the correction graduates to a rule in `.calx/rules/{domain}.md`, written in your own words. The full temporal chain is preserved as provenance.
4. At the start of every session, domain-specific rules are injected into the agent's context via hooks or MCP briefing. The agent reads and applies them before writing any code.

Each pass through this loop tightens the correction surface. Without intervention, you'll average ~2.9 corrections per task, every task, forever. With Calx, that number drops as rules compound.

## MCP Server

Calx runs as an MCP server built on [FastMCP](https://gofastmcp.com/getting-started/welcome) with local SQLite storage. `calx init` registers it automatically for Claude Code. The server provides the correction lifecycle over [MCP](https://modelcontextprotocol.io): any MCP-compatible client can read rules, log corrections, and fetch briefings.

**Resources:** `calx://briefing/{surface}`, `calx://rules`, `calx://corrections`
**Tools:** `log_correction`, `promote_correction`, `get_briefing`

For editors other than Claude Code, connect manually:

```bash
# Claude Desktop: add to claude_desktop_config.json
calx serve --transport stdio

# Any MCP client: connect to HTTP endpoint
calx serve
# → http://127.0.0.1:4195/mcp (auth token in .calx/server.json)
```

Full reference: [docs/mcp-reference.md](docs/mcp-reference.md)

## What this changes about how you work

Calx isn't just a correction logger. It encodes an orchestration methodology as automation so you stop managing your agent and start working with it.

**Token discipline.** Calx auto-detects your subscription tier and enforces context limits (Max: 200k soft / 250k ceiling, Pro: 80k / 100k). You never hit compaction, which means the correction signal, the thing that makes the learning loop work, is never destroyed by context summarization.

**Session lifecycle runs itself.** Session start injects rules, shows an effectiveness signal (corrections trending down per domain), and gates edits until rules are read. Session end captures uncommitted corrections, writes a clean-exit marker, and hands off state to the next session. If a session crashes, dirty-exit recovery prompts for anything that was lost.

**MCP server as the integration layer.** When `calx serve` is running, hooks fetch the briefing from the server instead of reading files directly. MCP clients get structured access to corrections, rules, and briefings. The server handles recurrence detection, quarantine scanning, and auto-promotion. Everything still works without the server (hooks fall back to file-based injection).

**Scoped rules, scoped agents.** Rules sync from `.calx/rules/` to `AGENTS.md` files co-located in your source directories. When you dispatch a subagent to work on `src/api/`, it reads `src/api/AGENTS.md` and gets exactly the rules it needs, nothing more. Your main window coordinates. Subagents do focused deep work.

```
src/
├── api/
│   ├── AGENTS.md          <- rules for API work
│   └── routes.py
├── services/
│   ├── AGENTS.md          <- rules for service layer
│   └── auth.py
└── db/
    ├── AGENTS.md          <- rules for data access
    └── migrations/
```

**Start in plan mode.** For any real implementation work, start in plan mode first. The orchestrator reads your rules, scopes the work, and decides what gets dispatched to subagents vs spun up as agent teams based on how isolated the task is. This is where you get the most out of Calx -- the rules inform the plan, not just the execution.

**Distillation runs in the background.** Recurrence detection is silent. Promotion surfaces at task boundaries, not mid-flow. Weekly review is a PR-style diff of your rule set. The system learns while you work.

## The evidence

We gave an AI agent 237 rules learned from another agent. It made 44 new mistakes, 13 in categories the rules explicitly covered. Process rules showed ~50% persistence. Architectural fixes had zero recurrence.

Rule text doesn't reliably transfer behavior. Compiled mechanisms can. Meta's HyperAgents (arXiv:2603.19461) showed that meta-level improvements transfer across domains when embodied in executable mechanisms, not rule text. Calx automates the path from correction to enforceable mechanism: capture, detect recurrence, promote to rules and hooks, inject with provenance.

[The Behavioral Plane (paper)](https://doi.org/10.5281/zenodo.19159223) | [Evidence repo](https://github.com/getcalx/calx-paper-evidence)

## What Calx collects

All data stays local. SQLite on disk. Nothing leaves your machine.

- **Corrections**: Stored in an append-only event log (`.calx/corrections.jsonl`) and SQLite (`.calx/calx.db`). Never transmitted.
- **Telemetry table**: Logs MCP interactions when the server is running: event type, tool/resource name, latency. No correction text. No code. No content.
- **No analytics. No phone-home. No remote collection.**
- Team tier (future): opt-in Postgres backend for shared state. You choose what syncs.

## Why Calx over alternatives?

| Approach | What it does | What it misses |
|----------|-------------|---------------|
| **Editing CLAUDE.md by hand** | Works. Rules persist across sessions. | No recurrence detection. No health tracking. No signal when rules conflict or go stale. Scales to ~20 rules before it becomes a wall of text agents skim. |
| **Agent memory tools** | Store and retrieve information across sessions. | Assumes corrections transfer as behavior. 30% of new corrections fell in categories with explicit rules. Memory is not mechanism. |
| **Agent self-improvement** | Compile mechanisms that transfer across domains. | Needs governance around it: who approved this mechanism? What's the provenance? Can it be rolled back? That's what Calx provides. |
| **Doing nothing** | Zero overhead. | ~2.9 corrections per task, every task, forever. That's the error floor without intervention. |
| **Calx** | Captures corrections, detects recurrence, promotes to rules, injects via hooks or MCP, enforces token discipline, automates the session lifecycle, scopes rules to directories, tracks health. | Accelerates behavioral formation within each agent relationship. Doesn't try to share raw rule text between agents. |

## Rule health

Not all rules age the same way. Architectural rules (structural fixes that eliminate an error class) don't decay from dormancy. Zero corrections means they're working. Process rules decay with age unless reinforced. Calx tracks the difference and surfaces when a recurring process rule should become an architectural fix instead.

## Commands

| Command | What it does |
|---------|-------------|
| `calx init` | Initialize `.calx/`, detect domains, scaffold CLAUDE.md, install hooks |
| `calx correct <text>` | Log a correction with automatic recurrence detection |
| `calx distill` | Promote recurring corrections or run weekly review (`--review`) |
| `calx status` | Corrections, rules, pending promotions at a glance |
| `calx serve` | Start the MCP server (`--host`, `--port`, `--transport`) |
| `calx sync` | Write AGENTS.md files to source directories from `.calx/rules/` |
| `calx dispatch <domain>` | Generate scoped prompt with domain rules for a subagent or teammate |
| `calx health <sub>` | Rule health: `score`, `conflicts`, `staleness`, `coverage`, `dedup`, `conversion` |
| `calx config` | View or modify configuration |
| `calx stats` | Local metrics: corrections by domain, recurrence rates, trends |

## Project structure

```
.calx/
├── calx.json              # Configuration (domains, token discipline, thresholds)
├── calx.db                # SQLite database (when serve is running)
├── server.json            # Server config and auth token
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
pip install -e ".[serve,dev]"

pytest                    # 419 tests
ruff check src/ tests/    # Lint
mypy src/calx/            # Type check
```

## Docs

- [Quickstart](docs/quickstart.md): Install to running MCP server in 2 minutes
- [MCP Reference](docs/mcp-reference.md): Every resource and tool with parameters and examples
- [Correction Workflow](docs/correction-workflow.md): Full capture-to-rule lifecycle
- [Hooks](docs/hooks.md): What each hook does, how to configure and customize

## Contributing

Contributions welcome. Please open an issue first for anything beyond small fixes so we can align before you invest time.

## License

MIT. The complete learning loop ships free with no feature gates.
