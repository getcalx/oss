from calx.serve.engine.learning_mode import classify_correction


def test_factual_is_architectural():
    result = classify_correction("factual", "The API endpoint is /v2/users not /v1/users")
    assert result.mode == "architectural"
    assert result.confidence == "high"


def test_structural_is_architectural():
    result = classify_correction("structural", "Use dataclass not dict for row types")
    assert result.mode == "architectural"
    assert result.confidence == "high"


def test_tonal_is_process():
    result = classify_correction("tonal", "Don't use em dashes in documentation")
    assert result.mode == "process"
    assert result.confidence == "high"


def test_procedural_is_process():
    result = classify_correction("procedural", "Always run tests before committing")
    assert result.mode == "process"
    assert result.confidence == "high"


def test_keyword_override_to_architectural():
    """Procedural correction about schema -> upgrade to architectural."""
    result = classify_correction("procedural", "Run the schema migration before deploying")
    assert result.mode == "architectural"
    assert result.confidence == "medium"


def test_keyword_override_to_process():
    """Structural correction with checklist language -> downgrade to process."""
    result = classify_correction("structural", "Remember to always check the return value")
    assert result.mode == "process"
    assert result.confidence == "medium"


def test_unknown_category_defaults_to_process():
    result = classify_correction("unknown_category", "some correction")
    assert result.mode == "process"
