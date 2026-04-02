"""Rule conflict detection: opposing action verbs in the same domain.

Detects contradictions like:
- "always use X" vs "never use X"
- "must do X" vs "must not do X"
- "use X" vs "avoid X"

Uses keyword overlap to determine if two rules address the same subject,
then checks for opposing action verbs.
"""
from __future__ import annotations

import re

# Opposing verb pairs: (positive, negative)
OPPOSING_PAIRS = [
    ({"always"}, {"never"}),
    ({"must"}, {"must not", "must_not", "mustn't"}),
    ({"use"}, {"avoid"}),
    ({"do"}, {"don't", "do not"}),
    ({"should"}, {"should not", "shouldn't"}),
    ({"require"}, {"prohibit", "forbid"}),
]


def _extract_subject_words(text: str) -> set[str]:
    """Extract non-verb content words from a rule text."""
    stopwords = {
        "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "and", "but", "or", "if",
        "always", "never", "must", "should", "use", "avoid", "do",
        "don't", "not", "require", "prohibit", "forbid",
    }
    words = set()
    for word in text.lower().split():
        cleaned = word.strip(".,;:!?\"'()-[]{}#*`")
        if cleaned and cleaned not in stopwords and len(cleaned) > 2:
            words.add(cleaned)
    return words


def _has_opposing_verbs(text_a: str, text_b: str) -> bool:
    """Check if two texts contain opposing action verbs.

    Handles both direct pair opposition (always vs never) and
    negation patterns (never use vs use, don't use vs use).
    """
    a_lower = text_a.lower()
    b_lower = text_b.lower()

    # Check direct pair opposition
    for positive_set, negative_set in OPPOSING_PAIRS:
        a_has_pos = any(p in a_lower for p in positive_set)
        a_has_neg = any(n in a_lower for n in negative_set)
        b_has_pos = any(p in b_lower for p in positive_set)
        b_has_neg = any(n in b_lower for n in negative_set)

        if (a_has_pos and b_has_neg) or (a_has_neg and b_has_pos):
            return True

    # Check negation + verb patterns: "never use" vs "use", "don't use" vs "use"
    negators = {"never", "don't", "do not", "must not", "should not", "shouldn't", "mustn't"}
    action_verbs = {"use", "mock", "deploy", "commit", "test", "write", "read", "edit", "rewrite"}

    for verb in action_verbs:
        a_has_verb = verb in a_lower
        b_has_verb = verb in b_lower
        if not (a_has_verb and b_has_verb):
            continue
        a_negated = any(f"{neg} {verb}" in a_lower for neg in negators)
        b_negated = any(f"{neg} {verb}" in b_lower for neg in negators)
        if a_negated != b_negated:
            return True

    return False


def _subject_overlap(text_a: str, text_b: str) -> float:
    """Jaccard similarity of subject words between two rule texts."""
    words_a = _extract_subject_words(text_a)
    words_b = _extract_subject_words(text_b)
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def detect_conflicts(
    proposed_text: str,
    existing_texts: list[str],
    subject_threshold: float = 0.3,
) -> list[str]:
    """Detect conflicts between a proposed rule and existing rules.

    Returns list of existing rule texts that conflict with the proposed text.
    A conflict requires both opposing action verbs AND overlapping subject matter.
    """
    conflicts = []
    for existing in existing_texts:
        if _has_opposing_verbs(proposed_text, existing):
            if _subject_overlap(proposed_text, existing) >= subject_threshold:
                conflicts.append(existing)
    return conflicts
