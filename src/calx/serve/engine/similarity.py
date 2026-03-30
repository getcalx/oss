"""Keyword-based similarity matching for recurrence detection.
Sub-millisecond, no embeddings, no LLM calls. Configurable threshold.
Ported from calx CLI distillation/similarity.py with threshold adjusted to 0.6.
"""
from __future__ import annotations

STOPWORDS = {
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "can", "will",
    "just", "don", "should", "now", "do", "did", "has", "have",
    "that", "this", "and", "but", "or", "if", "was", "be", "been",
}


def extract_keywords(text: str) -> set[str]:
    """Extract keywords from text after stop-word removal and punctuation stripping."""
    words: set[str] = set()
    for word in text.lower().split():
        cleaned = word.strip(".,;:!?\"'()-[]{}#*`")
        if cleaned and cleaned not in STOPWORDS and len(cleaned) > 2:
            words.add(cleaned)
    return words


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity coefficient between two keyword sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)
