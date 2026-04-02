# Concepts

This document explains why Calx works the way it does. For usage, see the [Quickstart](quickstart.md) or the [README](../README.md).

## The behavioral plane

AI agents operate on two planes.

The **information plane** is where rules, docs, and context live. CLAUDE.md files, system prompts, conversation history. This is what the agent knows.

The **behavioral plane** is what the agent actually does. How it responds to ambiguity, which patterns it defaults to, what it checks before acting.

Text rules live on the information plane. You can write "always run tests before committing" in a markdown file. The agent reads it. Sometimes it follows it. Sometimes it doesn't. The rule is information, not behavior.

Calx operates on the behavioral plane. Session-start hooks inject rules and gate edits until they're acknowledged. Token discipline prevents context compaction from destroying learning signal. Enforcement gates structurally prevent error classes from recurring. The agent's environment changes, not just its instructions.

The distinction matters because information doesn't reliably produce behavior. Mechanisms do.

## Why corrections are pair-specific

Corrections form between a specific person and a specific agent. They encode a working relationship: your preferences, your codebase patterns, your tolerance for certain tradeoffs.

We tested this directly. 237 rules learned from one agent were transferred to a new agent. The new agent made 44 new mistakes. 13 of those fell in categories the rules explicitly covered. Process rules (procedural reminders like "run tests first") showed roughly 50% persistence. The rules were read. They just didn't produce the same behavior.

This isn't a limitation. It's the core insight. Rules-as-documentation don't transfer behavior between agents. The correction-enforcement loop within each person-agent dyad is what works. Each relationship builds its own behavioral surface through captured corrections, detected recurrence, and compiled enforcement.

The methodology transfers. The raw rules don't.

## Architectural vs process corrections

Not all corrections age the same way.

**Architectural corrections** are structural changes that permanently eliminate an error class. A hook that runs tests before allowing commits. A schema migration that prevents invalid states. A gate that blocks file edits until rules are loaded. These have near-100% effectiveness because the error literally cannot happen anymore. Zero recurrence after implementation is the expected signal, not a sign the rule is stale.

**Process corrections** are procedural reminders: "check the return type," "don't use mocks in integration tests," "keep functions under 50 lines." These reduce errors but don't eliminate them. They show roughly 50% persistence across sessions and decay with time unless reinforced.

Calx tracks both and monitors recurrence to distinguish them. When a process correction recurs despite being promoted to a rule, that's a signal: it should become an architectural fix instead. The goal is to move corrections up the hierarchy from process reminders to structural enforcement.

## The compilation pipeline

Corrections are diagnostic signals, not rules to memorize. The pipeline:

**Capture.** A correction is logged. Three layers ensure nothing is lost: explicit `calx correct` command, session-end prompt for uncommitted corrections, and dirty-exit recovery for crashes.

**Recurrence detection.** Each new correction is matched against existing ones using keyword similarity. Calx tracks frequency, temporal patterns, and domain clustering. A correction that recurs 3+ times is a pattern, not an accident.

**Compilation.** This is the step most tools skip. Compilation means analyzing the recurring correction and identifying what needs to change in the agent's environment so the error can't happen again. Not "add a rule that says don't do X." Instead: "what structural modification would make X impossible?"

**Environmental modification.** The compiled mechanism is installed: a hook, a gate, a scoped rule with enforcement, a schema constraint. The agent's operating environment is different after compilation. The correction surface shrinks.

The product is the compilation step. Capture is table stakes. Recurrence detection is pattern matching. But going from "this keeps happening" to "here's the structural change that prevents it" is where behavioral governance lives.

## Token discipline

Context compaction permanently destroys learning signal. When a model summarizes away the details of a correction (the exact wording, the provenance chain, the temporal context), that information is gone. The correction becomes a vague summary that doesn't produce the same behavioral effect.

Calx enforces token discipline to protect the learning loop:

- **Soft cap at 200K tokens.** At this threshold, Calx signals that context is getting heavy. Non-essential context can be shed.
- **Hard ceiling at 250K tokens.** Session should end and hand off to a new session before hitting compaction. The clean-exit marker and session state ensure continuity.

The point is simple: if the correction signal gets compacted, the learning loop breaks. Token discipline keeps the signal intact long enough to compile it into a mechanism that persists independently of context.

## Orchestration

Calx includes multi-agent orchestration for implementation work.

**Plans.** The orchestrator reads the enforcement plan (`.calx/method/` files), scopes work into chunks, and decides what gets dispatched to subagents vs handled directly. Each chunk gets the domain rules relevant to its scope.

**Dispatch.** `calx dispatch <domain>` generates a scoped prompt with exactly the rules a subagent needs. Subagents do focused deep work in their domain. The orchestrator coordinates across domains.

**Waves.** Work is organized into dependency waves. Independent chunks run in parallel. Dependent chunks wait for their prerequisites. The orchestrator manages the graph.

**Foil review.** After builders complete their work, foil reviewers do adversarial cross-domain review. A backend reviewer checks frontend work. A systems reviewer checks API contracts. Foils look for the things domain experts miss because they're too close to the code.

The orchestration methodology is documented in `.calx/method/`:
- `orchestration.md`: Session lifecycle and hooks
- `dispatch.md`: Agent dispatch scaffolding
- `review.md`: Foil review methodology
- `how-we-document.md`: Three-tier learning model
