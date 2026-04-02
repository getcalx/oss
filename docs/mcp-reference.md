# MCP Reference

Complete reference for all Calx MCP resources and tools. The server is built on [FastMCP](https://gofastmcp.com/getting-started/welcome) with local SQLite storage via [aiosqlite](https://github.com/omnilib/aiosqlite).

---

## Resources

### `calx://briefing/{surface}`

Full state bundle for a surface. Fetch at conversation start.

**URI template:** `calx://briefing/{surface}`

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `surface` | string | yes | Which surface to brief. |

**Surfaces and their domain mappings:**

| Surface | Domains included |
|---|---|
| `reid` | coordination, general |
| `chat` | strategy, general |
| `cowork` | content, general |
| *(any other)* | general |

**Returns:** Markdown string with sections:
- Active Rules (filtered by surface domains, with compilation status)
- Recent Corrections (last 20, all surfaces)
- Since Last Session (corrections and rules added since this surface's last session end)
- Compilation Stats (total rules, compiled count, uncompiled candidates)
- Compilation Candidates (promoted rules without compilation events)
- Review Status (pending foil reviews)
- Orchestration Protocol (active plans, dispatched chunks, blocked items)
- Traction (latest metrics)
- Pipeline (top 5 entries)
- Recent Decisions (last 7 days)
- Hot Context

---

### `calx://rules{?domain}`

Active promoted rules, optionally filtered by domain.

**URI template:** `calx://rules{?domain}`

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `domain` | string | no | Filter rules to a specific domain. Omit for all active rules. |

**Returns:** Markdown string. Each rule formatted as:

```markdown
### R001 [reid]

Always use absolute imports in the serve package.

### R002

Never commit .env files to version control.
```

Returns `"No active rules."` when empty. Returns `"No active rules for domain X."` when filtered and empty.

---

### `calx://corrections{?domain}`

Recent corrections, optionally filtered by domain. Excludes quarantined corrections.

**URI template:** `calx://corrections{?domain}`

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `domain` | string | no | Filter corrections to a specific domain. Omit for all. |

**Returns:** Markdown string. Each correction formatted as:

```markdown
### C001 [general/structural]

Always use absolute imports, never relative imports in the serve package.

Surface: cli | Severity: medium | Confidence: high

### C002 [general/structural] (x3)

Use absolute imports instead of relative imports in calx.serve modules.

Surface: reid | Severity: medium | Confidence: high
```

Returns `"No recent corrections."` when empty. Limit: 50 most recent.

---

### `calx://board`

Current board state. Returns all active board items across domains with status and blocked reasons.

**URI template:** `calx://board`

**Parameters:** None.

**Returns:** Markdown string. Each item formatted as:

```markdown
### domain: item-description

Status: in_progress
Blocked: waiting on API design review
```

Returns `"No board items."` when empty.

---

## Tools

### `log_correction`

Record a behavioral correction. Runs recurrence detection and quarantine scan automatically.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `correction` | string | yes | -- | What went wrong and what to do instead. |
| `domain` | string | yes | -- | Routing domain (e.g. coordination, strategy, content, general). |
| `category` | string | yes | -- | One of: `factual`, `tonal`, `structural`, `procedural`. |
| `severity` | string | no | `"medium"` | One of: `low`, `medium`, `high`. |
| `confidence` | string | no | `"medium"` | One of: `low`, `medium`, `high`. Controls auto-promotion behavior. |
| `surface` | string | no | `"unknown"` | Which surface originated this (reid, chat, cowork, cli). |
| `task_context` | string | no | `null` | Description of the task during which this correction occurred. |

**Returns:**

New correction (no match):

```json
{
  "status": "ok",
  "correction_id": "C001"
}
```

Recurrence detected:

```json
{
  "status": "recurrence",
  "correction_id": "C002",
  "original_id": "C001",
  "count": 2
}
```

Quarantined (hostile content detected):

```json
{
  "status": "quarantined",
  ...
}
```

Validation error:

```json
{
  "status": "error",
  "message": "Invalid category 'typo'. Must be one of: factual, procedural, structural, tonal"
}
```

---

### `promote_correction`

Promote a correction to an active rule.

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `correction_id` | string | yes | The correction to promote (e.g. "C003"). |
| `rule_text` | string | yes | The rule text to create. |

**Returns:**

Success:

```json
{
  "status": "ok",
  "rule_id": "R001"
}
```

Not found:

```json
{
  "status": "not_found"
}
```

Error (e.g. quarantined correction):

```json
{
  "status": "error",
  "message": "Cannot promote quarantined correction."
}
```

---

### `compile_rule`

Mark a rule as compiled into a structural enforcement mechanism. This is the step where a text rule becomes an environmental constraint.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `rule_id` | string | yes | -- | The rule to compile (e.g. "R001"). |
| `mechanism_type` | string | yes | -- | One of: `code_change`, `config_change`, `hook_addition`, `architecture_change`. |
| `mechanism_description` | string | yes | -- | What was done to enforce this rule structurally. |
| `mechanism_reference` | string | no | `null` | File path, config key, or other pointer to the enforcement mechanism. |

**Returns:**

```json
{
  "status": "ok",
  "compilation_id": "CMP001"
}
```

---

### `deactivate_rule`

Deactivate a rule. The rule remains in the database for history but is excluded from briefings and injection.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `rule_id` | string | yes | -- | The rule to deactivate (e.g. "R001"). |
| `reason` | string | no | `null` | Why this rule is being deactivated. |

**Returns:**

```json
{
  "status": "ok",
  "rule_id": "R001",
  "deactivated": true
}
```

---

### `register_session`

Register a new session with the enforcement server. Called by the SessionStart hook.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `surface` | string | yes | -- | Which surface is starting (reid, chat, cowork, cli). |
| `session_id` | string | no | auto-generated | Override the session ID. Omit for auto-generation. |

**Returns:**

```json
{
  "status": "ok",
  "session_id": "S001"
}
```

---

### `end_session`

End a session. Writes handoff data for the next session on this surface.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | string | yes | -- | The session to end. |
| `what_changed` | string | no | `null` | Summary of what was modified this session. |
| `what_others_need` | string | no | `null` | Information other surfaces need to know. |
| `decisions_deferred` | string | no | `null` | Decisions that were not resolved this session. |
| `next_priorities` | string | no | `null` | What should happen next on this surface. |

**Returns:**

```json
{
  "status": "ok",
  "session_id": "S001",
  "duration_minutes": 42
}
```

---

### `get_briefing`

Fetch the full briefing for a surface. Tool-based fallback for MCP clients that do not support resources. Same output as `calx://briefing/{surface}`.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `surface` | string | no | `"default"` | Which surface to brief (reid, chat, cowork, default). |

**Returns:** Markdown string. Same format as the briefing resource.

---

### `update_board`

Add or update a board item. The board tracks work-in-progress across surfaces.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `domain` | string | yes | -- | Which domain this item belongs to. |
| `description` | string | yes | -- | What the item is. |
| `status` | string | yes | -- | Current status (e.g. `todo`, `in_progress`, `blocked`, `done`). |
| `blocked_reason` | string | no | `null` | Why this item is blocked. Only meaningful when status is `blocked`. |

**Returns:**

```json
{
  "status": "ok",
  "board_item_id": "B001"
}
```

---

### `create_plan`

Create an execution plan with chunks and dependency edges. Plans decompose a task into ordered work units.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `task_description` | string | yes | -- | What the plan accomplishes. |
| `chunks` | array | yes | -- | List of chunk objects, each with `id` (string) and `description` (string). |
| `dependency_edges` | array | yes | -- | List of `[from_chunk_id, to_chunk_id]` pairs defining execution order. |

**Returns:**

```json
{
  "status": "ok",
  "plan_id": "P001",
  "waves": [["chunk-1", "chunk-2"], ["chunk-3"]]
}
```

Chunks with no unmet dependencies form the first wave. Subsequent waves unlock as earlier chunks complete.

---

### `update_plan`

Update a plan's chunk status, attach specs, tests, or review references.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `plan_id` | string | yes | -- | The plan to update. |
| `chunk_id` | string | no | `null` | Which chunk to update. |
| `chunk_status` | string | no | `null` | New status for the chunk (e.g. `pending`, `dispatched`, `in_progress`, `blocked`, `done`). |
| `block_reason` | string | no | `null` | Why the chunk is blocked. |
| `spec_file` | string | no | `null` | Path to the spec file for this chunk. |
| `test_files` | string | no | `null` | Comma-separated paths to test files. |
| `review_id` | string | no | `null` | ID of the foil review for this chunk. |

**Returns:**

```json
{
  "status": "ok",
  "plan_id": "P001",
  "chunk_id": "chunk-1",
  "chunk_status": "done"
}
```

---

### `dispatch_chunk`

Dispatch a chunk for execution. Marks it as dispatched and returns the chunk details.

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `plan_id` | string | yes | The plan containing the chunk. |
| `chunk_id` | string | yes | Which chunk to dispatch. |

**Returns:**

```json
{
  "status": "ok",
  "plan_id": "P001",
  "chunk_id": "chunk-1",
  "description": "Implement the database schema"
}
```

---

### `redispatch_chunk`

Re-dispatch a previously completed or blocked chunk. Resets its status and makes it available for execution again.

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `plan_id` | string | yes | The plan containing the chunk. |
| `chunk_id` | string | yes | Which chunk to redispatch. |

**Returns:**

```json
{
  "status": "ok",
  "plan_id": "P001",
  "chunk_id": "chunk-1",
  "redispatched": true
}
```

---

### `verify_wave`

Verify that all chunks in a wave are complete. Used to gate progression to the next wave.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `plan_id` | string | yes | -- | The plan to verify. |
| `wave_id` | string | yes | -- | Which wave to check (zero-indexed). |
| `manual_notes` | string | no | `null` | Notes from manual verification. |

**Returns:**

```json
{
  "status": "ok",
  "wave_id": "0",
  "all_complete": true,
  "chunks": ["chunk-1", "chunk-2"],
  "next_wave": ["chunk-3"]
}
```

---

### `record_foil_review`

Record a review from a foil (adversarial reviewer). Foils pressure-test specs and implementations.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `spec_reference` | string | yes | -- | Path or identifier for the spec being reviewed. |
| `reviewer_domain` | string | yes | -- | Which domain the reviewer represents (e.g. `backend`, `frontend`, `security`). |
| `verdict` | string | yes | -- | One of: `approved`, `changes_requested`, `blocked`. |
| `findings` | string | no | `null` | What the reviewer found. |
| `round` | integer | no | `1` | Which review round this is. |

**Returns:**

```json
{
  "status": "ok",
  "review_id": "FR001",
  "verdict": "changes_requested"
}
```
