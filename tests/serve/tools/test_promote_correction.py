"""Phase 4 tests for promote_correction tool handler."""


from calx.serve.tools.promote_correction import handle_promote_correction


async def test_promotes_correction_to_rule(populated_db):
    result = await handle_promote_correction(
        populated_db, correction_id="C004",
        rule_text="Always report 82,000 lines, never 43K",
    )
    assert result["status"] == "ok"
    assert result["rule_id"].startswith("general-R")


async def test_rule_inherits_surface(populated_db):
    result = await handle_promote_correction(
        populated_db, correction_id="C003",
        rule_text="Don't negotiate cap in pitches",
    )
    assert result["status"] == "ok"
    rule = await populated_db.get_rule(result["rule_id"])
    assert rule.surface == "chat"  # inherited from C003


async def test_not_found_for_nonexistent(populated_db):
    result = await handle_promote_correction(
        populated_db, correction_id="C999",
        rule_text="whatever",
    )
    assert result["status"] == "not_found"


async def test_error_for_quarantined(populated_db):
    result = await handle_promote_correction(
        populated_db, correction_id="C005",
        rule_text="whatever",
    )
    assert result["status"] == "error"
    assert "quarantined" in result["message"].lower()


async def test_rule_gets_sequential_id(populated_db):
    # general already has R001, so next should be R002
    result = await handle_promote_correction(
        populated_db, correction_id="C004",
        rule_text="test rule",
    )
    assert result["rule_id"] == "general-R002"


async def test_already_promoted_correction_rejected(populated_db):
    """Promoting the same correction twice returns already_promoted."""
    # First promotion succeeds
    result1 = await handle_promote_correction(
        populated_db, correction_id="C004",
        rule_text="First promotion",
    )
    assert result1["status"] == "ok"

    # Second promotion is blocked
    result2 = await handle_promote_correction(
        populated_db, correction_id="C004",
        rule_text="Duplicate promotion",
    )
    assert result2["status"] == "already_promoted"
    assert "already promoted" in result2["message"].lower()
