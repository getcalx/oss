"""Tests for calx.distillation.similarity."""

from __future__ import annotations

from calx.core.corrections import CorrectionState
from calx.distillation.similarity import _extract_keywords, find_most_similar


def _make_correction(cid: str, description: str, domain: str = "api") -> CorrectionState:
    return CorrectionState(
        id=cid,
        uuid=f"uuid-{cid}",
        timestamp="2026-03-21T00:00:00+00:00",
        domain=domain,
        type="process",
        description=description,
        context="",
        source="explicit",
        status="confirmed",
    )


def test_extract_keywords_strips_stopwords():
    result = _extract_keywords("the quick brown fox is a very fast animal")
    # "the", "is", "a", "very" are stopwords
    assert "the" not in result
    assert "is" not in result
    assert "very" not in result
    assert "quick" in result
    assert "brown" in result
    assert "fox" in result
    assert "fast" in result
    assert "animal" in result


def test_extract_keywords_strips_punctuation():
    result = _extract_keywords("don't mock the database! use real connections.")
    assert "dont" in result
    assert "mock" in result
    assert "database" in result
    assert "real" in result
    assert "connections" in result
    # Punctuation characters should be gone
    for word in result:
        assert word.isalnum()


def test_extract_keywords_drops_single_char():
    result = _extract_keywords("a b c hello world")
    # "a" is a stopword, "b" and "c" are single-char
    assert "b" not in result
    assert "c" not in result
    assert "hello" in result
    assert "world" in result


def test_find_most_similar_returns_matches_above_threshold():
    corrections = [
        _make_correction("C001", "mock database tests integration"),
        _make_correction("C002", "always validate input parameters"),
        _make_correction("C003", "mock database connections integration"),
    ]
    query = "mock database integration tests"
    results = find_most_similar(query, corrections)

    assert len(results) >= 1
    # C001 and C003 share keywords with the query
    matched_ids = {r[0].id for r in results}
    assert "C001" in matched_ids or "C003" in matched_ids
    # All scores should be >= 0.3
    for _, score in results:
        assert score >= 0.3


def test_find_most_similar_empty_for_no_matches():
    corrections = [
        _make_correction("C001", "always validate input parameters"),
        _make_correction("C002", "use proper logging framework"),
    ]
    query = "deploy containers kubernetes cluster"
    results = find_most_similar(query, corrections)
    assert results == []


def test_find_most_similar_respects_top_k():
    # Create many similar corrections
    corrections = [
        _make_correction(f"C{i:03d}", f"mock database connection variant {i}")
        for i in range(1, 10)
    ]
    query = "mock database connection variant testing"
    results = find_most_similar(query, corrections, top_k=2)
    assert len(results) <= 2


def test_find_most_similar_empty_description():
    corrections = [
        _make_correction("C001", "don't mock the database"),
    ]
    results = find_most_similar("", corrections)
    assert results == []


def test_find_most_similar_stopword_only_description():
    corrections = [
        _make_correction("C001", "don't mock the database"),
    ]
    # All words are either stopwords or single-char
    results = find_most_similar("the is a to of", corrections)
    assert results == []


def test_find_most_similar_sorted_descending():
    corrections = [
        _make_correction("C001", "mock database connection handler"),
        _make_correction("C002", "mock database connection handler integration tests validate"),
    ]
    query = "mock database connection handler"
    results = find_most_similar(query, corrections)
    if len(results) >= 2:
        assert results[0][1] >= results[1][1]
