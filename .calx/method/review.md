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
