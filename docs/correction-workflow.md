# Correction Workflow

Full loop: capture, recurrence detection, promotion, rule injection, health monitoring.

---

## 1. Capture

A correction enters the system through two paths:

**MCP tool** (agent-initiated):

```json
{
  "tool": "log_correction",
  "args": {
    "correction": "Never use relative imports in the serve package.",
    "domain": "general",
    "category": "structural",
    "confidence": "high"
  }
}
```

**CLI** (human-initiated):

```bash
calx correct "Never use relative imports in the serve package." -d general
```

Both paths write to the append-only event log and SQLite. Keywords are extracted from the correction text for similarity matching.

---

## 2. Recurrence detection

Every new correction is matched against existing corrections in the same domain.

**How it works:**

1. Extract keywords from the new correction text (stopwords removed, lowercased).
2. Compare against keyword sets of existing corrections using Jaccard similarity.
3. Threshold: **0.6** (60% keyword overlap).
4. If a match is found, the new correction is linked via `root_correction_id` and the original's `recurrence_count` increments.

**Example:**

```
Correction A: "Always use absolute imports in the serve package."
Keywords: {absolute, imports, serve, package}

Correction B: "Use absolute imports, not relative, in calx.serve modules."
Keywords: {absolute, imports, relative, calx, serve, modules}

Jaccard: |{absolute, imports, serve}| / |{absolute, imports, serve, package, relative, calx, modules}| = 3/7 = 0.43
```

At 0.43, this would NOT match. The threshold is deliberately conservative to avoid false positives. Close paraphrases with higher overlap will match.

---

## 3. Quarantine

Before any matching or storage, corrections are scanned for hostile content.

**Patterns caught:**

| Pattern | Example |
|---|---|
| Shell injection | `; rm -rf /` |
| External URLs | `https://evil.com/payload` (getcalx GitHub URLs exempted) |
| Credential references | `password: hunter2`, `api_key=...` |
| Prompt injection | `ignore all previous instructions` |
| Base64 payloads | 50+ character base64 strings |

Flagged corrections are stored with a quarantine flag. They are excluded from:
- Recurrence matching
- Briefings
- Auto-promotion

They remain in the database for audit purposes.

---

## 4. Auto-promotion

When a correction's recurrence count hits **3+**, the system checks the original correction's confidence tier:

| Confidence | At 3+ recurrences |
|---|---|
| `high` | Auto-promoted to a rule immediately. |
| `medium` | Queued for human review. |
| `low` | Never auto-promoted. Manual promotion only. |

The confidence is always read from the **original** correction in the recurrence chain, not the latest occurrence.

Auto-promoted rules use the original correction text as the rule text. The correction is marked as promoted.

---

## 5. Manual promotion

Promote any correction at any time, regardless of recurrence count or confidence.

**MCP tool:**

```json
{
  "tool": "promote_correction",
  "args": {
    "correction_id": "C001",
    "rule_text": "Always use absolute imports. No relative imports in calx.serve."
  }
}
```

**CLI:**

```bash
calx distill
```

`calx distill` walks through undistilled corrections interactively. You choose to promote, skip, or discard each one.

Quarantined corrections cannot be promoted.

---

## 6. Rule injection

Rules reach agents through two mechanisms:

**MCP briefing resource** (preferred): Agent reads `calx://briefing/{surface}` at session start. Rules are filtered by surface-domain mapping:

| Surface | Domains |
|---|---|
| reid | coordination, general |
| chat | strategy, general |
| cowork | content, general |

**File-based injection** (fallback): The `session-start` hook reads rules from `.calx/rules/*.md` and injects them into stderr. Used when the MCP server is not running.

The serve hooks check for a running server first. If reachable, they fetch the briefing via HTTP. If not, they fall back to file-based injection.

---

## 7. Health monitoring

Rules accumulate. Calx tracks rule health to prevent drift.

**Rule types:**
- Architectural: structural constraints (e.g. "no relative imports")
- Process: workflow patterns (e.g. "always run tests before commit")

**Health signals:**

| Signal | What it checks |
|---|---|
| Staleness | Rules that have not been reinforced by recent corrections. |
| Conflict detection | Rules that contradict each other within or across domains. |
| Coverage analysis | Domains with corrections but no rules (governance gaps). |
| Deduplication | Rules with overlapping intent that should be merged. |

Run a health check:

```bash
calx health
```

The `session-start` hook prompts for a weekly review when the rule set is stale. Run `calx distill --review` to merge duplicates, resolve conflicts, and archive stale rules.
