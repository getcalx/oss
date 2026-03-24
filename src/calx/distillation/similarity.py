"""Keyword-based similarity matching for Calx corrections."""

from __future__ import annotations

from calx.core.corrections import CorrectionState

# ~50 common English stopwords
STOPWORDS: set[str] = {
    "a", "an", "the", "is", "it", "in", "to", "of", "and", "or", "for",
    "on", "at", "by", "with", "from", "as", "that", "this", "be", "are",
    "was", "were", "been", "has", "have", "had", "do", "does", "did",
    "not", "but", "if", "no", "so", "up", "out", "about", "into",
    "when", "what", "which", "who", "will", "can", "should", "would",
    "could", "all", "each", "every", "both", "few", "more", "most",
    "some", "any", "than", "too", "very",
}


def extract_keywords(text: str) -> set[str]:
    """Extract non-stopword lowercase tokens from text."""
    words = set()
    for word in text.lower().split():
        # Strip punctuation
        cleaned = "".join(c for c in word if c.isalnum())
        if cleaned and cleaned not in STOPWORDS and len(cleaned) > 1:
            words.add(cleaned)
    return words


def find_most_similar(
    description: str,
    corrections: list[CorrectionState],
    top_k: int = 3,
) -> list[tuple[CorrectionState, float]]:
    """Find most similar corrections by Jaccard similarity on keyword sets.

    Returns matches with similarity >= 0.3, sorted descending, limited to top_k.
    """
    query_kw = extract_keywords(description)
    if not query_kw:
        return []

    scored: list[tuple[CorrectionState, float]] = []
    for corr in corrections:
        corr_kw = extract_keywords(corr.description)
        if not corr_kw:
            continue
        intersection = query_kw & corr_kw
        union = query_kw | corr_kw
        sim = len(intersection) / len(union) if union else 0.0
        if sim >= 0.3:
            scored.append((corr, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
