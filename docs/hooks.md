# Hooks

Calx hooks wire into Claude Code's lifecycle events to inject rules, guard context, and capture corrections.

---

## Overview

`calx init` installs four hooks into `.claude/settings.json` and copies shell scripts to `.calx/hooks/`.

| Hook | Fires on | Purpose |
|---|---|---|
| session-start | `SessionStart` | Inject rules, show effectiveness signal |
| session-end | `Stop` | Capture uncommitted corrections, clean exit |
| orientation-gate | `PreToolUse` (Edit/Write) | Block edits until rules are read |
| collapse-guard | `PreToolUse` (Edit/Write) | Enforce token discipline |

---

## CLI hooks

Shell scripts in `.calx/hooks/`. Installed by `calx init`. Called by Claude Code via `.claude/settings.json`.

### session-start

**File:** `.calx/hooks/session-start.sh`
**Trigger:** `SessionStart`
**Calls:** `calx _hook session-start`

What it does:

1. Removes the previous clean-exit marker (dirty exit = safety net).
2. Checks for update (cached, non-blocking).
3. Warns if the previous session did not exit cleanly.
4. Runs JSONL integrity check on `corrections.jsonl`. Repairs if needed.
5. Injects all active rules, grouped by domain.
6. Shows effectiveness signal: correction count delta from last session.
7. Lists undistilled corrections and promotion candidates.
8. Prompts for weekly review if rule set is stale (7+ days since last check).
9. Prints token discipline config (soft cap and ceiling).

### session-end

**File:** `.calx/hooks/session-end.sh`
**Trigger:** `Stop`
**Calls:** `calx _hook session-end`

What it does:

1. Checks for uncommitted git changes. Warns if found.
2. Lists undistilled corrections.
3. Prompts for missed corrections if none were captured this session.
4. Writes clean-exit marker.

### orientation-gate

**File:** `.calx/hooks/orientation-gate.sh`
**Trigger:** `PreToolUse` (matcher: `Edit|Write`)

Two-phase design for performance:

- **Hot path** (shell script): Checks for `.calx/.oriented` sentinel. If present and current session, exits immediately (<10ms).
- **Cold path** (Python): Runs only on first edit of a session. Prints rules to stderr, then writes the sentinel.

This ensures the agent has read the rules before making any file changes.

### collapse-guard

**File:** `.calx/hooks/collapse-guard.sh`
**Trigger:** `PreToolUse` (matcher: `Edit|Write`)

Reads `CLAUDE_TURN_COUNT` from the environment and compares against token discipline thresholds from `.calx/calx.json`:

```json
{
  "token_discipline": {
    "soft_cap": 200000,
    "ceiling": 250000
  }
}
```

Uses a rough heuristic of ~4000 tokens per turn.

- **At soft cap:** `"Approaching token limit. Consider committing progress."`
- **At ceiling:** `"CEILING REACHED. Commit everything. Write handoff. End session."`

---

## Serve hooks

Python modules under `calx.serve.hooks`. Same four hooks, but MCP-aware.

### Behavior

Each serve hook follows this logic:

1. Find `.calx/` directory (walk up from cwd, or check `CALX_DIR` env var).
2. Read server config from `.calx/server.json`.
3. Check if `calx serve` is running (HTTP health check to `http://{host}:{port}/health`).
4. If running: fetch briefing/data from server via HTTP.
5. If not running: fall back to file-based rule injection.

### Running serve hooks

```bash
python3 -m calx.serve.hooks.session_start
python3 -m calx.serve.hooks.session_end
python3 -m calx.serve.hooks.orientation_gate
python3 -m calx.serve.hooks.collapse_guard
```

### Configuration

Serve hooks read config from two sources:

**`.calx/server.json`:**

```json
{
  "host": "127.0.0.1",
  "port": 4195,
  "auth_token": "auto-generated-token",
  "transport": "streamable-http"
}
```

**Environment variables** (override file config):

| Variable | Default | Description |
|---|---|---|
| `CALX_HOST` | `127.0.0.1` | Server host |
| `CALX_PORT` | `4195` | Server port |
| `CALX_TRANSPORT` | `streamable-http` | Transport type |
| `CALX_AUTH_TOKEN` | (auto-generated) | Auth token |
| `CALX_DIR` | (auto-detected) | Path to `.calx/` directory |

---

## Settings.json structure

After `calx init`, your `.claude/settings.json` hooks section looks like:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/absolute/path/to/.calx/hooks/session-start.sh"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "/absolute/path/to/.calx/hooks/orientation-gate.sh"
          },
          {
            "type": "command",
            "command": "/absolute/path/to/.calx/hooks/collapse-guard.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/absolute/path/to/.calx/hooks/session-end.sh"
          }
        ]
      }
    ]
  }
}
```

Hooks use absolute paths to prevent resolution failures when Claude Code's cwd changes.

---

## Customizing

Hook scripts are plain shell. Edit directly:

```bash
# List installed hooks
calx hook list

# Edit a hook
calx hook edit session-start
```

Or edit the files in `.calx/hooks/` with any editor.

Re-running `calx init` will not clobber existing hooks. It merges new entries into `settings.json` and overwrites hook script templates only if they have changed.
