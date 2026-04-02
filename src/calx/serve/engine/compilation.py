"""Compilation verification engine (Chunk 1C).

Tracks whether compiled rules (process -> architectural transitions)
actually hold. After compilation, a verification period monitors for
recurrence of the original correction pattern. Zero recurrence confirms
the compilation succeeded; recurrence triggers reactivation.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from calx.serve.db.engine import CompilationEventRow, DatabaseEngine, RuleRow
from calx.serve.engine.similarity import extract_keywords, jaccard_similarity

VERIFICATION_PERIOD_DAYS = 14
_SIMILARITY_THRESHOLD = 0.6


@dataclass
class VerificationResult:
    event_id: int
    rule_id: str
    status: str        # "in_verification" | "verified" | "failed"
    days_remaining: int
    recurrence_count: int


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string to a timezone-aware datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


async def check_post_compilation_recurrence(
    db: DatabaseEngine,
    correction_text: str,
    domain: str,
) -> list[CompilationEventRow]:
    """Check if a new correction matches any compiled rule's error pattern.

    For each compilation event in the same domain whose rule_text has
    keyword similarity >= threshold with correction_text, increment the
    post_compilation_recurrence counter.

    Returns the list of matching CompilationEventRow objects (after update).
    """
    all_events = await db.get_compilation_events()
    correction_keywords = extract_keywords(correction_text)
    matches: list[CompilationEventRow] = []

    for event in all_events:
        # Get the rule to check domain match
        rule = await db.get_rule(event.rule_id)
        if rule is None or rule.domain != domain:
            continue

        rule_keywords = extract_keywords(event.rule_text)
        similarity = jaccard_similarity(correction_keywords, rule_keywords)
        if similarity >= _SIMILARITY_THRESHOLD:
            new_count = event.post_compilation_recurrence + 1
            await db.update_compilation_event(
                event.id,
                post_compilation_recurrence=new_count,
            )
            # Return a copy reflecting the updated value
            updated = CompilationEventRow(
                id=event.id,
                rule_id=event.rule_id,
                source_correction_id=event.source_correction_id,
                rule_text=event.rule_text,
                learning_mode_before=event.learning_mode_before,
                mechanism_type=event.mechanism_type,
                mechanism_description=event.mechanism_description,
                mechanism_reference=event.mechanism_reference,
                recurrence_count_at_compilation=event.recurrence_count_at_compilation,
                rule_age_days=event.rule_age_days,
                correction_chain_length=event.correction_chain_length,
                post_compilation_recurrence=new_count,
                verified_at=event.verified_at,
                created_at=event.created_at,
            )
            matches.append(updated)

    return matches


async def check_verification_status(
    db: DatabaseEngine,
    now: datetime | None = None,
) -> list[VerificationResult]:
    """Check verification status for all unverified compilation events.

    - Past verification period + zero recurrence -> verified (set verified_at)
    - Past verification period + recurrence > 0 -> failed (reactivate rule)
    - Still within period -> in_verification with days_remaining
    """
    if now is None:
        now = datetime.now(timezone.utc)

    all_events = await db.get_compilation_events()
    results: list[VerificationResult] = []

    for event in all_events:
        if event.verified_at is not None:
            continue

        created = _parse_iso(event.created_at)
        elapsed = now - created
        deadline = timedelta(days=VERIFICATION_PERIOD_DAYS)

        if elapsed >= deadline:
            if event.post_compilation_recurrence == 0:
                # Verified: compilation held
                verified_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                await db.update_compilation_event(
                    event.id, verified_at=verified_ts,
                )
                results.append(VerificationResult(
                    event_id=event.id,
                    rule_id=event.rule_id,
                    status="verified",
                    days_remaining=0,
                    recurrence_count=0,
                ))
            else:
                # Failed: reactivate the rule
                await db.update_rule(
                    event.rule_id,
                    active=1,
                    health_status="warning",
                )
                results.append(VerificationResult(
                    event_id=event.id,
                    rule_id=event.rule_id,
                    status="failed",
                    days_remaining=0,
                    recurrence_count=event.post_compilation_recurrence,
                ))
        else:
            remaining = (deadline - elapsed).days
            results.append(VerificationResult(
                event_id=event.id,
                rule_id=event.rule_id,
                status="in_verification",
                days_remaining=remaining,
                recurrence_count=event.post_compilation_recurrence,
            ))

    return results


async def get_compilation_candidates(db: DatabaseEngine) -> list[RuleRow]:
    """Find active process-mode rules whose source corrections have recurrence.

    These are candidates for compilation (process -> architectural transition).
    Returns sorted by source correction recurrence_count descending.
    """
    all_rules = await db.find_rules(domain=None, active_only=True)
    process_rules = [r for r in all_rules if r.learning_mode == "process"]

    scored: list[tuple[RuleRow, int]] = []
    for rule in process_rules:
        if not rule.source_correction_id:
            continue
        correction = await db.get_correction(rule.source_correction_id)
        if correction is None:
            continue
        if correction.recurrence_count > 0:
            scored.append((rule, correction.recurrence_count))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [rule for rule, _count in scored]


async def get_compilation_stats(db: DatabaseEngine) -> dict:
    """Compute aggregate compilation statistics.

    Returns dict with: total, verified, in_verification, failed,
    success_rate, architectural_recurrence_rate, process_recurrence_rate.
    """
    all_events = await db.get_compilation_events()
    now = datetime.now(timezone.utc)
    deadline = timedelta(days=VERIFICATION_PERIOD_DAYS)

    total = len(all_events)
    verified = 0
    in_verification = 0
    failed = 0
    arch_recurrence = 0
    process_recurrence = 0
    arch_total = 0
    process_total = 0

    for event in all_events:
        if event.verified_at is not None:
            verified += 1
        else:
            created = _parse_iso(event.created_at)
            elapsed = now - created
            if elapsed >= deadline:
                if event.post_compilation_recurrence > 0:
                    failed += 1
                else:
                    # Past deadline, zero recurrence, but verified_at not set yet.
                    # This shouldn't normally happen if check_verification_status
                    # was run, but count as verified for stats.
                    verified += 1
            else:
                in_verification += 1

        # Recurrence rate by learning mode
        if event.learning_mode_before == "architectural":
            arch_total += 1
            if event.post_compilation_recurrence > 0:
                arch_recurrence += 1
        elif event.learning_mode_before == "process":
            process_total += 1
            if event.post_compilation_recurrence > 0:
                process_recurrence += 1

    completed = verified + failed
    success_rate = (verified / completed) if completed > 0 else 0.0
    arch_rate = (arch_recurrence / arch_total) if arch_total > 0 else 0.0
    process_rate = (process_recurrence / process_total) if process_total > 0 else 0.0

    return {
        "total_compilations": total,
        "verified": verified,
        "in_verification": in_verification,
        "failed": failed,
        "success_rate": success_rate,
        "architectural_recurrence_rate": arch_rate,
        "process_recurrence_rate": process_rate,
    }
