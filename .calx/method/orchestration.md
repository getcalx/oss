# Orchestration

Calx uses hook-based orchestration to enforce behavioral governance without
requiring manual discipline. Hooks fire at session boundaries and during work,
creating a governance layer that operates automatically.

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
