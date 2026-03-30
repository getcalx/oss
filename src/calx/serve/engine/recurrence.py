"""Recurrence detection for correction compounding.
Matches new corrections against existing ones in the same domain
using pre-computed keyword sets and Jaccard similarity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from calx.serve.engine.similarity import extract_keywords, jaccard_similarity

RECURRENCE_THRESHOLD = 0.6


@dataclass
class RecurrenceResult:
    is_match: bool
    original_id: str = ""
    new_count: int = 0
    similarity: float = 0.0


async def check_recurrence(
    db: object,
    correction_text: str,
    domain: str,
    threshold: float = RECURRENCE_THRESHOLD,
) -> RecurrenceResult:
    """Check if a new correction matches an existing one in the same domain.

    Uses pre-computed keywords column when available for O(1) keyword lookup.
    Uses root_correction_id for O(1) chain root resolution.
    """
    keywords = extract_keywords(correction_text)
    # Use keyword-filtered query to avoid the limit=100 recurrence cap.
    # Top 3 keywords narrow the SQL search window before Python-side Jaccard.
    keyword_list = sorted(keywords, key=len, reverse=True)[:3]
    existing = await db.find_corrections_by_keywords(  # type: ignore[attr-defined]
        keywords=keyword_list, domain=domain,
    )

    best_match = None
    best_score = 0.0

    for candidate in existing:
        # Use pre-computed keywords if available
        if candidate.keywords:
            try:
                candidate_keywords = set(json.loads(candidate.keywords))
            except (json.JSONDecodeError, TypeError):
                candidate_keywords = extract_keywords(candidate.correction)
        else:
            candidate_keywords = extract_keywords(candidate.correction)

        score = jaccard_similarity(keywords, candidate_keywords)
        if score > best_score and score >= threshold:
            best_score = score
            # Resolve to chain root via denormalized root_correction_id
            if candidate.root_correction_id:
                root = await db.get_correction(candidate.root_correction_id)  # type: ignore[attr-defined]
                best_match = root or candidate
            else:
                best_match = candidate

    if best_match:
        return RecurrenceResult(
            is_match=True,
            original_id=best_match.id,
            new_count=best_match.recurrence_count + 1,
            similarity=best_score,
        )
    return RecurrenceResult(is_match=False)
