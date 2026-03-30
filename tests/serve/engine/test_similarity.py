"""Tests for keyword-based similarity matching."""


def test_extract_keywords_strips_stopwords():
    from calx.serve.engine.similarity import extract_keywords

    keywords = extract_keywords("Don't mock the database in integration tests")
    assert "the" not in keywords
    assert "in" not in keywords
    assert "database" in keywords
    assert "integration" in keywords
    assert "tests" in keywords


def test_extract_keywords_strips_punctuation():
    from calx.serve.engine.similarity import extract_keywords

    keywords = extract_keywords("use real (production) connections, not mocks!")
    assert "real" in keywords
    assert "production" in keywords
    assert "connections" in keywords
    assert "mocks" in keywords


def test_extract_keywords_ignores_short_words():
    from calx.serve.engine.similarity import extract_keywords

    keywords = extract_keywords("do it as is on at")
    assert len(keywords) == 0


def test_jaccard_similarity_identical_sets():
    from calx.serve.engine.similarity import jaccard_similarity

    a = {"database", "integration", "tests"}
    assert jaccard_similarity(a, a) == 1.0


def test_jaccard_similarity_disjoint_sets():
    from calx.serve.engine.similarity import jaccard_similarity

    a = {"database", "integration"}
    b = {"frontend", "styling"}
    assert jaccard_similarity(a, b) == 0.0


def test_jaccard_similarity_partial_overlap():
    from calx.serve.engine.similarity import jaccard_similarity

    a = {"database", "integration", "tests"}
    b = {"database", "tests", "mocking"}
    # intersection = {database, tests} = 2, union = {database, integration, tests, mocking} = 4
    assert jaccard_similarity(a, b) == 0.5


def test_jaccard_similarity_empty_sets():
    from calx.serve.engine.similarity import jaccard_similarity

    assert jaccard_similarity(set(), set()) == 0.0
    assert jaccard_similarity({"a"}, set()) == 0.0
