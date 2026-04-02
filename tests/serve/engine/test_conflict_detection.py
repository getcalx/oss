"""Tests for rule conflict detection."""
from __future__ import annotations

import pytest

from calx.serve.engine.conflict_detection import detect_conflicts


class TestConflictDetection:

    def test_no_conflict(self):
        existing = ["Use real database connections in tests"]
        proposed = "Always validate input at API boundaries"
        conflicts = detect_conflicts(proposed, existing)
        assert len(conflicts) == 0

    def test_always_never_conflict(self):
        existing = ["Never use em dashes in writing"]
        proposed = "Always use em dashes for emphasis"
        conflicts = detect_conflicts(proposed, existing)
        assert len(conflicts) == 1

    def test_must_must_not_conflict(self):
        existing = ["You must not mock the database"]
        proposed = "You must mock the database in unit tests"
        conflicts = detect_conflicts(proposed, existing)
        assert len(conflicts) == 1

    def test_use_avoid_conflict(self):
        existing = ["Avoid using global state"]
        proposed = "Use global state for configuration"
        conflicts = detect_conflicts(proposed, existing)
        assert len(conflicts) == 1

    def test_no_conflict_different_subjects(self):
        existing = ["Always use TypeScript for frontend"]
        proposed = "Never use JavaScript for backend"
        conflicts = detect_conflicts(proposed, existing)
        assert len(conflicts) == 0

    def test_multiple_conflicts(self):
        existing = [
            "Never use em dashes",
            "Avoid global state",
        ]
        proposed = "Always use em dashes and global state"
        conflicts = detect_conflicts(proposed, existing)
        assert len(conflicts) >= 1
