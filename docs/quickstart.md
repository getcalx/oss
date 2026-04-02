# Quickstart

Install to running enforcement layer in 2 minutes. Built on [FastMCP](https://gofastmcp.com/getting-started/welcome) with local SQLite.

## Install

```bash
pip install getcalx
```

## Initialize (Claude Code)

```bash
cd your-project
calx init
```

This creates `.calx/` with config and an empty corrections database, then registers the Calx MCP server and hooks in `.claude/settings.json`. Claude Code starts the server automatically via stdio transport. No manual server management needed.

Done. Start a Claude Code session and Calx is running.

### The first session will feel empty

That's expected. Calx has no corrections yet, no rules, no recurrence data. The briefing will be mostly blank. The enforcement hooks are active but have nothing to enforce yet.

After `calx init`, corrections compound into rules automatically. The first few sessions build the foundation. By session 5-10, the system has learned your patterns and starts enforcing them structurally.

### What `.calx/` looks like after ~10 sessions

```
.calx/
  calx.db              # SQLite: corrections, rules, sessions, compilations
  calx.json            # Config: token discipline, domains, surfaces
  server.json          # MCP server config (host, port, auth)
  corrections.jsonl    # Append-only event log (backup/audit)
  hooks/
    session-start.sh   # SessionStart hook
    session-end.sh     # Stop hook
    enforce.sh         # PreToolUse enforcement gate
  rules/
    general.md         # Auto-generated rule files (fallback injection)
    coordination.md
```

The database will contain your correction chains, promoted rules, compilation records, and session history. The rules directory contains markdown files generated from active rules for file-based injection when the MCP server is not running.

---

## Connect: Other editors

For editors other than Claude Code, run the server manually.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "calx": {
      "command": "calx",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

No auth token needed for stdio transport.

### Cursor, Windsurf, generic MCP clients

Start the HTTP server:

```bash
calx serve
```

Default: `http://127.0.0.1:4195/mcp`, streamable-http transport. Auth token auto-generated and saved to `.calx/server.json` on first run.

Get your auth token:

```bash
cat .calx/server.json | python3 -c "import sys,json; print(json.load(sys.stdin)['auth_token'])"
```

Point your MCP client at:

```
URL:       http://127.0.0.1:4195/mcp
Transport: streamable-http
Auth:      Bearer <token from .calx/server.json>
```

---

## The correction lifecycle

Once connected, here is the full loop in action.

### 1. Log a correction

Call the `log_correction` tool:

```json
{
  "correction": "Always use absolute imports, never relative imports in the serve package.",
  "domain": "general",
  "category": "structural",
  "severity": "medium",
  "confidence": "high"
}
```

Response:

```json
{
  "status": "ok",
  "correction_id": "C001"
}
```

### 2. See it in the briefing

Read the `calx://briefing/default` resource or call the `get_briefing` tool:

```markdown
## Active Rules

No active rules.

## Recent Corrections

- **C001** [general/structural]: Always use absolute imports, never relative imports in the serve package.
```

### 3. Trigger recurrence

Log the same correction again (different wording, same intent):

```json
{
  "correction": "Use absolute imports instead of relative imports in calx.serve modules.",
  "domain": "general",
  "category": "structural",
  "severity": "medium",
  "confidence": "high"
}
```

Response:

```json
{
  "status": "recurrence",
  "correction_id": "C002",
  "original_id": "C001",
  "count": 2
}
```

Calx detected the similarity and linked it to the original. At 3 recurrences with high confidence, this auto-promotes to a rule.

### 4. Manual promotion

Promote any correction immediately:

```json
{
  "correction_id": "C001",
  "rule_text": "Always use absolute imports in the serve package. No relative imports."
}
```

Response:

```json
{
  "status": "ok",
  "rule_id": "R001"
}
```

The rule now appears in every future briefing.

### 5. Compile the rule

Promotion makes the rule visible. Compilation makes it structural. Tell Calx how the rule is now enforced:

```json
{
  "tool": "compile_rule",
  "args": {
    "rule_id": "R001",
    "mechanism_type": "hook_addition",
    "mechanism_description": "PreToolUse hook rejects Edit calls with relative imports in calx.serve paths"
  }
}
```

The rule is now tracked as structurally enforced. It no longer depends on the agent remembering it.

---

## Key commands

```bash
calx init              # Initialize calx in current project
calx serve             # Start MCP server (HTTP transport)
calx correct "..."     # Log a correction from the CLI
calx distill           # Walk through undistilled corrections
calx health            # Rule health check
calx status            # Show current state (rules, corrections, sessions)
```

---

## What to expect

Sessions 1-3: You log corrections manually. The briefing starts populating. Hooks enforce token discipline but have few rules to inject.

Sessions 4-7: Recurrence detection kicks in. High-confidence corrections auto-promote. The enforcement gate starts blocking edits until rules are read. The system is learning.

Sessions 8+: The rule set reflects your actual patterns. Compilation events track which rules are structurally enforced. Health checks surface stale rules and governance gaps. The environment is doing the work, not the agent's memory.
