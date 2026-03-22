"""Rule conflict detection for Calx."""

from __future__ import annotations

import re
from dataclasses import dataclass

from calx.core.rules import Rule


@dataclass
class Conflict:
    rule_a: str
    rule_b: str
    reason: str


# Polarity pairs — action verbs that contradict each other
_POLARITY_PAIRS = [
    ("always", "never"),
    ("must", "must not"),
    ("use", "avoid"),
    ("do", "don't"),
    ("require", "forbid"),
]


def _extract_polarity(text: str) -> list[tuple[str, str]]:
    """Extract (keyword, polarity) pairs from text.

    Returns list of (subject, polarity) where polarity is one of the action verbs.
    E.g. "always use mocks" -> [("mocks", "always")]
    """
    results: list[tuple[str, str]] = []
    text_lower = text.lower()

    for positive, negative in _POLARITY_PAIRS:
        # Check for positive polarity
        # Pattern: polarity_word followed by words
        for polarity_word in (positive, negative):
            # Match "polarity_word <words>" patterns
            pattern = rf"\b{re.escape(polarity_word)}\b\s+(.+?)(?:[.,;!]|$)"
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                subject = match.group(1).strip()
                # Take first 3 significant words as the subject
                words = [w for w in subject.split()[:5] if len(w) > 2]
                if words:
                    subject_key = " ".join(words[:3])
                    results.append((subject_key, polarity_word))

    return results


def detect_conflicts(rules: list[Rule]) -> list[Conflict]:
    """Detect contradictions between rules based on keyword/polarity analysis.

    Two rules conflict when they reference similar subjects with opposing polarity
    (e.g., "always use mocks" vs "never use mocks").
    """
    conflicts: list[Conflict] = []

    # Extract polarities for all rules
    rule_polarities: list[tuple[Rule, list[tuple[str, str]]]] = []
    for rule in rules:
        text = f"{rule.title} {rule.body}"
        polarities = _extract_polarity(text)
        if polarities:
            rule_polarities.append((rule, polarities))

    # Compare all pairs
    for i, (rule_a, pol_a) in enumerate(rule_polarities):
        for j, (rule_b, pol_b) in enumerate(rule_polarities):
            if j <= i:
                continue

            # Check for opposing polarities on similar subjects
            for subject_a, polarity_a in pol_a:
                for subject_b, polarity_b in pol_b:
                    # Check if subjects overlap (share keywords)
                    words_a = set(subject_a.split())
                    words_b = set(subject_b.split())
                    overlap = words_a & words_b

                    if not overlap:
                        continue

                    # Check if polarities are opposing
                    for pos, neg in _POLARITY_PAIRS:
                        if (polarity_a == pos and polarity_b == neg) or (
                            polarity_a == neg and polarity_b == pos
                        ):
                            conflicts.append(
                                Conflict(
                                    rule_a=rule_a.id,
                                    rule_b=rule_b.id,
                                    reason=f"Opposing polarity on '{' '.join(overlap)}': "
                                    f"{rule_a.id} says '{polarity_a}' while "
                                    f"{rule_b.id} says '{polarity_b}'",
                                )
                            )

    return conflicts
