# Quickstart

Install to running MCP server in 2 minutes.

## Install

```bash
pip install getcalx[serve]
```

## Initialize

```bash
cd your-project
calx init
```

This creates `.calx/` with config, hooks, and an empty corrections log.

## Start the server

```bash
calx serve
```

Default: `http://127.0.0.1:4195`, streamable-http transport. Override with `--host`, `--port`, or `--transport stdio`.

An auth token is auto-generated and saved to `.calx/server.json` on first run.

---

## Connect: Claude Code

1. Start the server:

```bash
calx serve
```

2. Get your auth token:

```bash
cat .calx/server.json | python3 -c "import sys,json; print(json.load(sys.stdin)['auth_token'])"
```

3. Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "calx": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:4195/mcp",
      "headers": {
        "Authorization": "Bearer <your-auth-token>"
      }
    }
  }
}
```

Claude Code will now have access to calx tools and resources.

## Connect: Claude Desktop

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

## Connect: Generic MCP client

Point any MCP client at:

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
