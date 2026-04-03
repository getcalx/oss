# Calx

Your AI agent keeps making the same mistakes. Calx captures corrections, detects recurrence, and compiles them into enforceable mechanisms that actually change behavior.

```bash
pip install getcalx
```

## Quickstart

```bash
calx init
```

That's it. `calx init` scaffolds `.calx/`, registers an MCP server in `.claude/settings.json`, and installs session hooks. Claude Code starts the server automatically via stdio. Corrections, rules, and briefings flow over [MCP](https://modelcontextprotocol.io) backed by local SQLite.

```bash
# Log a correction (your agent can do this too via the MCP log_correction tool)
calx correct "don't mock the database in integration tests"
# -> Logged C014. Matches C007: "don't mock the database." (3rd occurrence)

# Compile recurring corrections into enforceable mechanisms
calx distill
# -> Promoted to tests-R003. Available in every future briefing.
```

Not using Claude Code? Run `calx serve` and point your MCP client at it:

```bash
calx serve                          # streamable-http on 127.0.0.1:4195
calx serve --transport stdio        # for Claude Desktop, Cursor, etc.
```

Requires Python 3.10+. Works with anything MCP-compatible. Built on [FastMCP](https://gofastmcp.com/getting-started/welcome).

## How it works

**Capture -> Recurrence -> Compilation -> Environmental Modification**

1. **Capture.** You correct your agent. Calx logs it to an append-only event log. Three capture layers ensure nothing is lost: explicit command, session-end prompt, and dirty-exit recovery. The agent can also capture corrections via `calx correct` or the MCP `log_correction` tool.

2. **Recurrence.** Calx matches new corrections against existing ones using keyword similarity. When the same correction recurs 3+ times, it surfaces once at a task boundary. Never mid-flow.

3. **Compilation.** Recurring corrections are diagnostic signals, not rules to memorize. Compilation means identifying what needs to change in the agent's environment so the error class is eliminated, not just documented.

4. **Environmental modification.** Compiled mechanisms modify how the agent operates: hooks that enforce behavior before code is written, rules scoped to the directories where they apply, token discipline that protects the learning loop. The agent's environment changes structurally. Text rules become documentation; hooks become enforcement.

Each pass through this loop tightens the correction surface. Without intervention, correction rates stay flat. With Calx, they drop as mechanisms compound.

## Why corrections are pair-specific

Corrections form between a specific person and a specific agent. We transferred 237 rules to a new agent. It made 44 new mistakes, 13 in categories the rules explicitly covered. Rules-as-documentation don't transfer behavior. The correction-enforcement loop within each dyad is what works. This is the feature, not the limitation. The methodology transfers; the raw rules don't.

## What Calx is NOT

- **Not a CLAUDE.md manager.** Calx doesn't organize your markdown files. It operates on the behavioral plane: hooks, enforcement gates, and compiled mechanisms that structurally modify agent behavior.
- **Not a prompt template library.** There are no "best practice" prompts to copy. Calx captures your corrections and compiles them into enforcement specific to how you work.

## Commands

| Command | What it does |
|---------|-------------|
| `calx init` | Initialize `.calx/`, detect domains, install hooks, register MCP server |
| `calx correct <text>` | Log a correction with automatic recurrence detection |
| `calx distill` | Compile recurring corrections into enforceable mechanisms (`--review` for weekly review) |
| `calx status` | Corrections, rules, pending promotions at a glance |
| `calx config` | View or modify configuration |
| `calx health` | Rule health: score, conflicts, staleness, coverage, dedup, conversion |
| `calx dispatch <domain>` | Generate scoped dispatch prompt with domain rules for a subagent |
| `calx stats` | Local metrics: corrections by domain, recurrence rates, trends |
| `calx sync` | Write AGENTS.md files to source directories from `.calx/rules/` |
| `calx serve` | Start the MCP server (`--host`, `--port`, `--transport`) |
| `calx telemetry` | Manage anonymous usage telemetry (view status, opt in/out) |
| `calx board` | Show the enforcement board grouped by status |
| `calx plan` | View and manage the enforcement plan |
| `calx promote` | Promote a correction to a rule, or list promotion candidates |
| `calx review` | Manage foil reviews, review gaps, and review history |
| `calx rules` | List rules and their enforcement status |

## MCP Server

Calx runs as an MCP server with local SQLite storage. `calx init` registers it automatically for Claude Code. Any MCP-compatible client can read rules, log corrections, and fetch briefings.

**Resources:** `calx://briefing/{surface}`, `calx://rules`, `calx://corrections`
**Tools:** `log_correction`, `promote_correction`, `get_briefing`

For editors other than Claude Code:

```bash
# Claude Desktop: add to claude_desktop_config.json
calx serve --transport stdio

# Any MCP client: connect to HTTP endpoint
calx serve
# -> http://127.0.0.1:4195/mcp (auth token in .calx/server.json)
```

Full reference: [docs/mcp-reference.md](docs/mcp-reference.md)

## Schema safety

Upgrades run migrations automatically. Your data is safe. The SQLite schema evolves with the package, and migrations are applied on first use after an upgrade. No manual steps required.

## What Calx collects

All correction data stays local. SQLite on disk. Nothing leaves your machine.

- **Corrections**: Stored in an append-only event log (`.calx/corrections.jsonl`) and SQLite (`.calx/calx.db`). Never transmitted.
- **Anonymous telemetry** (opt-in): Event type, tool/resource name, latency. No correction text. No code. No content. No personally identifiable information.
- **Opt out anytime**: `calx telemetry --off`
- Team tier (future): opt-in Postgres backend for shared state. You choose what syncs.

## Development

```bash
pip install -e ".[serve,dev]"

pytest                    # run tests
ruff check src/ tests/    # lint
mypy src/calx/            # type check
```

## Docs

- [Quickstart](docs/quickstart.md): Install to running MCP server in 2 minutes
- [Concepts](docs/concepts.md): The behavioral plane and why corrections are pair-specific
- [MCP Reference](docs/mcp-reference.md): Every resource and tool with parameters and examples
- [Correction Workflow](docs/correction-workflow.md): Full capture-to-rule lifecycle
- [Hooks](docs/hooks.md): What each hook does, how to configure and customize

## Contributing

Contributions welcome. Please open an issue first for anything beyond small fixes so we can align before you invest time.

## License

MIT
