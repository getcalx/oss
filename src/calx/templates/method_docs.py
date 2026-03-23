"""Generate .calx/method/ documentation from Calx methodology."""

from __future__ import annotations


def how_we_document() -> str:
    """Return markdown content for how-we-document.md.

    Covers the three-tier distillation model: corrections -> lessons -> rules,
    and how each layer is captured and maintained.
    """
    return """\
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
"""


def orchestration() -> str:
    """Return markdown content for orchestration.md.

    Covers hooks, session lifecycle, and the coordination model.
    """
    return """\
# Orchestration

Calx uses hook-based orchestration to enforce correction engineering without
requiring manual discipline. Hooks fire at session boundaries and during work,
creating an automation layer that operates automatically.

## Session Bootstrap

Every session begins with automatic bootstrap:

- **Read coordination state** -- board summary, latest handoffs, timestamps
- **Check staleness** -- warn if handoffs are older than expected
- **Inject rules** -- domain-specific rules loaded and acknowledged
- **Verify state** -- check version control status against coordination claims

The bootstrap ensures no agent starts work based on stale assumptions.

## Session Shutdown

Every session ends with:

- **Update handoff** -- what happened, what other agents need
- **Update board** -- move items between status columns
- **Write clean-exit marker** -- timestamp for dirty-exit detection
- **Update memory/rules** -- if corrections were made, log them

If the session exits dirty (crash, timeout, terminal close), the next session's
bootstrap detects the missing clean-exit marker and prompts for recovery.

## Hook Types

Calx installs hooks that fire at specific points in the agent lifecycle:

- **Orientation gate** -- fires at session start, injects rules and verifies
  the agent reads them before editing files. Agents that skip rule reading are
  the primary source of boundary failures.
- **Correction capture** -- fires when the developer corrects agent behavior,
  logging the structured event to corrections.jsonl.
- **Session lifecycle** -- fires at session boundaries to manage handoffs,
  board state, and clean-exit markers.

## Context Collapse Prevention

The orchestration model exists primarily to prevent context compaction.
Compaction permanently destroys learning signal -- summaries discard the
correction details and edge cases that make the learning loop work.

Prevention rules enforced by hooks:

- **Token budget monitoring** -- warn when approaching the compaction danger
  zone (~80% of context window)
- **Delta edits only** -- never rewrite a context document from scratch; always
  use targeted edits
- **Size guards** -- check generated output size against expectations
- **One task per agent** -- never dispatch multiple unrelated tasks to the same
  context window

## Coordination Layer

- **Source of truth index** -- a single file defines where each concept is
  authoritatively defined
- **Handoff documents** -- written at session end, read at session start,
  verified against actual state
- **Board state** -- shared status tracking across all agents (blocked, in
  progress, needs review, done)
"""


def dispatch() -> str:
    """Return markdown content for dispatch.md.

    Covers how dispatch scaffolds work: cold-start prompts, dependency graphs,
    parallel execution, and verification between rounds.
    """
    return """\
# Dispatch

Dispatch is how work gets assigned to agents. The dispatch model enforces
context isolation, precise prompting, and verification between rounds.

## Cold-Start Dispatch

Every agent prompt includes:

1. **The rules file** for that agent's domain -- read completely before any work
   begins.
2. **The specific task** -- exact files to create or modify, exact changes
   expected, explicit scope boundaries.
3. **Explicit prohibitions** -- what NOT to do (e.g., "do NOT commit," "do NOT
   modify files outside this list").
4. **Source material** -- the spec, relevant contracts, implementation
   signatures the agent needs to reference.

## Context Isolation

Each agent operates in complete isolation:

- **Separate context windows.** No agent shares a conversation thread with
  another agent. Information flows through files, never through shared context.
- **Separate rule sets.** Each domain's rules reflect that domain's correction
  history.
- **Separate lessons history.** Each agent's lessons are append-only and
  domain-specific.

## Dependency Graphs

Every multi-agent task begins with an explicit dependency graph that determines:

- **Parallel dispatch** -- independent chunks dispatched simultaneously
- **Sequential dispatch** -- dependent chunks wait for predecessors to complete
  and verify
- **Verification points** -- after each wave, verify imports, registrations, and
  contracts before proceeding

## Parallel Execution

When chunks are independent (no shared files, no dependency relationship),
dispatch them simultaneously. Prefer parallel dispatch when:

- The dependency graph allows 3+ parallel dispatches
- Chunks are file-disjoint (no agent edits a file another agent is editing)
- Each chunk fits within the context budget

## Verify Between Rounds

After copying results from each dispatch round, verify before dispatching the
next round:

1. All new modules import cleanly
2. All registrations are wired (endpoints mounted, services importable)
3. No duplicate definitions
4. Contracts match (response shapes match downstream expectations)

Fix issues between rounds. Dispatching the next round on top of broken previous
work compounds failures.

## Handling Incomplete Work

When an agent returns incomplete work:

1. Diagnose what came back and why it was incomplete
2. Re-dispatch a fresh agent with an updated prompt reflecting where to pick up
3. Never repeat the original prompt (that produces the same failure)
4. Never fix incomplete work in the main window to avoid re-dispatch -- tokens
   are cheap, context overhead is the real cost

## One Task Per Agent

Never dispatch multiple unrelated tasks to the same agent. Each task gets its
own context window. This prevents context contamination, compaction from
multi-task growth, and unclear error attribution.
"""


def review() -> str:
    """Return markdown content for review.md.

    Covers the foil review system: cross-domain adversarial review, binary
    output, per-spec review, and review rounds.
    """
    return """\
# Review

Calx uses an adversarial foil review system to catch failures at domain
boundaries. Reviews are binary, cross-domain, and per-spec.

## What Foil Review Is

A foil is an adversarial reviewer assigned to review specs from a domain they
do NOT own. The foil's job is to find failures -- not to approve, not to suggest
improvements, not to be helpful. The foil catches what the builder cannot see
because the builder lacks the foil's domain expertise.

## Cross-Domain Dispatch

Same-domain review and cross-domain review catch entirely different failure
classes with zero overlap:

- **Same-domain foils** catch depth issues: SQL correctness, column drift,
  policy gaps, race conditions, accessibility, performance targets.
- **Cross-domain foils** catch width issues at boundaries: wire format
  mismatches, endpoint path errors, response shape errors, enum value
  mismatches, auth boundary assumptions.

A system with only same-domain review misses every boundary failure. A system
with only cross-domain review misses every domain-internal failure. Both are
required.

## Binary Output

Foils produce exactly one of two outputs:

- **APPROVE** -- no blocking issues found. The spec can proceed to build.
- **REVISE** -- blocking issues found, listed with specific findings and
  suggested fixes.

No "approve with minor suggestions." Binary forces the reviewer to make a
decision. If the issue matters enough to mention, it matters enough to block.

Reviews must include suggested fixes, not just blockers. A finding without a
fix is a complaint, not a review.

## One Spec Per Review

Never batch multiple specs into one review agent. Context compaction degrades
review quality for later specs in a batch.

Measured result: batch review (11 specs in one agent) found 29 blocking issues.
Per-spec review of the same 11 specs found 72 -- a 2.48x improvement. Two specs
flipped from APPROVE to REVISE when reviewed individually.

## Review Rounds

Reviews happen in rounds:

- **Round 1** catches the obvious issues
- **Round 2** catches issues hidden behind Round 1 fixes
- A spec that passes Round 1 is not necessarily ready

Track convergence across rounds. A healthy system shows declining issue counts
(e.g., 29 -> 7 -> 0). Flat or increasing counts mean the correction loop isn't
working for that domain.

## Two Types of Learning from Reviews

- **Architectural learning (permanent):** Corrections that change structure
  (replacing a library, consolidating patterns) permanently eliminate error
  classes. Zero recurrence.
- **Process learning (fragile):** Corrections that add checklist steps ("always
  grep for callers," "always verify column names") show ~50% persistence. The
  same errors recur despite rules existing.

Corrections that can be converted into structural fixes should be. Track which
rules are architectural vs process and monitor recurrence rates separately.
"""
