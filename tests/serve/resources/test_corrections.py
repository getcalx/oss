"""Phase 4 -- corrections resource tests."""


from calx.serve.resources.corrections import _get_corrections


async def test_returns_recent_corrections(populated_db):
    result = await _get_corrections(populated_db)
    assert "C001" in result
    assert "C003" in result


async def test_filters_by_domain(populated_db):
    result = await _get_corrections(populated_db, domain="strategy")
    assert "C003" in result
    # C001 is general domain, not strategy
    assert "C001" not in result


async def test_excludes_quarantined(populated_db):
    # C005 is quarantined -- find_corrections filters quarantined=0 at SQL level
    result = await _get_corrections(populated_db)
    assert "C005" not in result


async def test_includes_recurrence_count(populated_db):
    # C001 has recurrence_count=3
    result = await _get_corrections(populated_db)
    assert "(x3)" in result


async def test_includes_domain_and_category(populated_db):
    result = await _get_corrections(populated_db, domain="strategy")
    assert "[strategy/tonal]" in result


async def test_empty_domain_returns_message(populated_db):
    result = await _get_corrections(populated_db, domain="nonexistent")
    assert "No recent corrections" in result


async def test_empty_db_returns_message(db):
    result = await _get_corrections(db)
    assert "No recent corrections" in result
