# How We Document

Calx uses a three-tier distillation model to convert developer corrections into
persistent, actionable rules. Each tier serves a different purpose.

## Tier 1: Corrections

A correction is a developer intervention that changes an agent's behavior.
Corrections are captured in `corrections.jsonl` as structured, append-only
events. Each correction records:

- **What happened** -- the specific failure
- **The correction** -- what the developer told the agent to do differently
- **The domain** -- which area of the system this applies to
- **The type** -- architectural (eliminates an error class permanently) or
  process (a procedural reminder)
- **Recurrence** -- whether this correction references a prior correction for
  the same conceptual failure

The structured format enables querying: which domains have the most
corrections? Which error classes recur despite rules? Which corrections are
architectural vs process?

## Tier 2: Lessons

Lessons are the narrative form of corrections. Each lesson captures:

- **What happened** -- the full context of the failure
- **Root cause** -- why the failure occurred (the structural condition that
  allowed it, not just the symptom)
- **The correction** -- what changed
- **Distilled to** -- which rule(s) this lesson produced
- **Recurrence chain** -- links to prior lessons addressing the same error class

Lessons are append-only. Never edit a historical lesson. If a lesson is wrong,
add a new lesson that corrects it. The history is data.

## Tier 3: Rules

Rules are the distilled, actionable form of lessons. Each rule is:

- Scoped to a specific domain
- Traceable to the corrections that produced it (bidirectional)
- Classified as architectural or process
- Given a health score that decays differently by type

Rules are injected into agent context at session start. The agent reads and
acknowledges rules before beginning work.

## Distillation

Distillation converts corrections into rules. Two modes:

- **Template mode (no LLM):** The system surfaces the correction alongside the
  most similar existing rule and a structured template. The developer completes
  and approves.
- **Draft mode (LLM-assisted):** The system retrieves the correction plus
  similar existing rules, drafts a rule, and presents it for developer approval.

Approval actions: Approve, Edit, Reject, Merge, Defer.

A conflict check runs before approval: the proposed rule is checked against
existing rules for contradictions. Contradictions surface during approval, not
after.

## Why Three Tiers

Corrections without distillation accumulate but never compound. Rules without
corrections are documentation, not learning -- transferred rules are followed
mechanically without the correction context that produced them. The three-tier
model preserves both the raw signal (corrections) and the actionable output
(rules) with full traceability between them.
