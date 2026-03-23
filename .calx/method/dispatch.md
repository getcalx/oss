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
