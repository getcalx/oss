"""Progressive promotion with confidence tiers.
Uses the ORIGINAL correction's confidence to determine promotion behavior.
The new recurrence confirms the pattern but doesn't change classification.
"""
from __future__ import annotations

from dataclasses import dataclass

from calx.serve.db.engine import RuleRow
from calx.serve.engine.conflict_detection import detect_conflicts

PROMOTION_THRESHOLD = 3


@dataclass
class PromotionAction:
    action: str  # "auto_promoted" | "conflict_blocked" | "queued_for_review" | "never_auto_promote" | "none"
    rule_id: str | None = None


async def check_auto_promotion(
    db: object,
    correction_id: str,
    threshold: int = PROMOTION_THRESHOLD,
) -> PromotionAction:
    """Check if a correction should be auto-promoted based on its confidence tier."""
    correction = await db.get_correction(correction_id)  # type: ignore[attr-defined]
    if not correction or correction.promoted:
        return PromotionAction(action="none")

    if correction.recurrence_count < threshold:
        return PromotionAction(action="none")

    if correction.confidence == "high":
        # Check for conflicts with existing rules before promoting
        existing_rules = await db.find_rules(domain=correction.domain, active_only=True)  # type: ignore[attr-defined]
        existing_texts = [r.rule_text for r in existing_rules]
        conflicts = detect_conflicts(correction.correction, existing_texts)
        if conflicts:
            return PromotionAction(action="conflict_blocked")

        learning_mode = getattr(correction, "learning_mode", "unknown") or "unknown"
        rule_id = await db.next_rule_id(correction.domain)  # type: ignore[attr-defined]
        await db.insert_rule(RuleRow(  # type: ignore[attr-defined]
            id=rule_id,
            rule_text=correction.correction,
            domain=correction.domain,
            surface=correction.surface,
            source_correction_id=correction_id,
            learning_mode=learning_mode,
            active=1,
        ))
        await db.update_correction(correction_id, promoted=1)  # type: ignore[attr-defined]
        return PromotionAction(action="auto_promoted", rule_id=rule_id)

    elif correction.confidence == "medium":
        return PromotionAction(action="queued_for_review")

    else:  # low
        return PromotionAction(action="never_auto_promote")
