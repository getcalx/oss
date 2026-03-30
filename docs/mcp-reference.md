# MCP Reference

Complete reference for all calx MCP resources and tools.

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
- Active Rules (filtered by surface domains)
- Recent Corrections (last 20, all surfaces)
- Traction (latest metrics)
- Pipeline (top 5 entries)
- Recent Decisions (last 7 days)
- Hot Context

**Example response:**

```markdown
## Active Rules

- **R001** (general): Always use absolute imports in the serve package.

## Recent Corrections

- **C003** [general/structural] (x3): Use absolute imports, not relative.

## Traction

No metrics recorded.

## Pipeline

No pipeline entries.

## Recent Decisions

No recent decisions.

## Hot Context

No active context.
```

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

### `get_briefing`

Fetch the full briefing for a surface. Tool-based fallback for MCP clients that do not support resources. Same output as `calx://briefing/{surface}`.

**Parameters:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `surface` | string | no | `"default"` | Which surface to brief (reid, chat, cowork, default). |

**Returns:** Markdown string. Same format as the briefing resource.
