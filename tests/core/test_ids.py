"""Tests for calx.core.ids."""

from calx.core.ids import generate_session_id, generate_uuid, next_sequential_id


def test_generate_uuid_format():
    uid = generate_uuid()
    assert len(uid) == 32
    assert uid.isalnum()


def test_generate_uuid_unique():
    ids = {generate_uuid() for _ in range(100)}
    assert len(ids) == 100


def test_next_sequential_id_empty():
    assert next_sequential_id("C", []) == "C001"


def test_next_sequential_id_existing():
    assert next_sequential_id("C", ["C001", "C002"]) == "C003"


def test_next_sequential_id_with_gaps():
    assert next_sequential_id("C", ["C001", "C005"]) == "C006"


def test_next_sequential_id_different_prefix():
    assert next_sequential_id("api-R", ["api-R001", "api-R002"]) == "api-R003"


def test_generate_session_id_format():
    sid = generate_session_id()
    assert len(sid) == 8
    assert all(c in "0123456789abcdef" for c in sid)


def test_generate_session_id_unique():
    ids = {generate_session_id() for _ in range(100)}
    assert len(ids) == 100
