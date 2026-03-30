"""Keyword-based similarity matching for Calx corrections."""

from __future__ import annotations

from calx.core.corrections import CorrectionState
from calx.serve.engine.similarity import extract_keywords, jaccard_similarity

SIMILARITY_THRESHOLD = 0.5


def find_most_similar(
    description: str,
    corrections: list[CorrectionState],
    top_k: int = 3,
) -> list[tuple[CorrectionState, float]]:
    """Find most similar corrections by Jaccard similarity on keyword sets."""
    query_kw = extract_keywords(description)
    if not query_kw:
        return []
    scored = []
    for corr in corrections:
        corr_kw = extract_keywords(corr.description)
        if not corr_kw:
            continue
        sim = jaccard_similarity(query_kw, corr_kw)
        if sim >= SIMILARITY_THRESHOLD:
            scored.append((corr, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
