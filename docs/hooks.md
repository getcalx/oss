# Hooks

Hooks are behavioral conditioning, not configuration. They modify the agent's environment structurally so that correct behavior becomes the path of least resistance. Text instructions decay. Environmental constraints persist.

---

## Overview

`calx init` installs three hooks into `.claude/settings.json` and copies shell scripts to `.calx/hooks/`.

| Hook | Fires on | Purpose |
|---|---|---|
| session-start | `SessionStart` | Register session, inject rules, show enforcement signal |
| session-end | `Stop` | End session, write handoff, send telemetry |
| enforce | `PreToolUse` (Edit/Write) | Consolidated gate: orientation + token counting + collapse guard |

The enforcement layer is the product. Each hook exists to make the agent's environment reject bad behavior before the agent has to decide not to do it.

---

## enforce.py

**File:** `.calx/hooks/enforce.sh` (calls `calx _hook enforce`)
**Trigger:** `PreToolUse` (matcher: `Edit|Write`)

Consolidated PreToolUse gate that replaces the previous `orientation_gate.py` and `collapse_guard.py`. Three checks in one pass:

### Orientation check

On the first edit of a session, the agent has not yet read the rules. Enforce blocks the edit, prints all active rules to stderr, and writes the `.calx/.oriented` sentinel. Subsequent edits in the same session hit the hot path: sentinel exists, check passes in <10ms.

This is not a reminder. It is a gate. The edit does not proceed until rules are surfaced.

### Token counting

Reads `CLAUDE_TURN_COUNT` from the environment. Compares against thresholds from `.calx/calx.json`:

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

### Collapse guard

At ceiling, the hook outputs a blocking message. The agent cannot continue making edits without addressing the token situation. This prevents context collapse where the agent loses coherence in long sessions and starts undoing its own work.

---

## session-start

**File:** `.calx/hooks/session-start.sh`
**Trigger:** `SessionStart`
**Calls:** `calx _hook session-start`

What it does:

1. Registers the session with the enforcement server via `register_session`. Receives a session ID that tracks this session's corrections, rules, and handoff data.
2. Falls back to file-based injection if the server is unreachable. Reads rules from `.calx/rules/*.md` and injects them into stderr.
3. Removes the previous clean-exit marker (dirty exit = safety net).
4. Checks for update (cached, non-blocking).
5. Warns if the previous session did not exit cleanly.
6. Runs JSONL integrity check on `corrections.jsonl`. Repairs if needed.
7. Injects all active rules, grouped by domain.
8. Shows effectiveness signal: correction count delta from last session.
9. Lists undistilled corrections and promotion candidates.
10. Prompts for weekly review if rule set is stale (7+ days since last check).
11. Prints token discipline config (soft cap and ceiling).

The server registration is the key change from v0.5.x. When the enforcement server is running, the session is tracked centrally. Other surfaces can see that this surface is active, what it's working on, and what it changed when it ends.

---

## session-end

**File:** `.calx/hooks/session-end.sh`
**Trigger:** `Stop`
**Calls:** `calx _hook session-end`

What it does:

1. Ends the session via `end_session`. Writes handoff data: what changed, what other surfaces need to know, deferred decisions, next priorities.
2. Sends telemetry (correction counts, session duration, rule health summary).
3. Checks for uncommitted git changes. Warns if found.
4. Lists undistilled corrections.
5. Prompts for missed corrections if none were captured this session.
6. Writes clean-exit marker.

The handoff data persists in the database and appears in the next session's briefing for any surface. This is how context transfers between sessions without manual notes.

---

## How hooks connect to the thesis

Text rules tell an agent what to do. Hooks modify the environment so the agent cannot do the wrong thing, or is structurally nudged toward the right thing.

- **Enforce** does not ask the agent to remember rules. It blocks edits until rules are surfaced.
- **Session-start** does not rely on the agent choosing to read its briefing. It injects the briefing before the agent acts.
- **Session-end** does not hope the agent will write a handoff. It captures handoff data as part of the exit sequence.

Each hook is a point where the environment, not the agent's memory, governs behavior.

---

## Configuration

Hooks read config from two sources:

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
            "command": "/absolute/path/to/.calx/hooks/enforce.sh"
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
