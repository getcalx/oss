"""Tests for calx.templates.method_docs."""

from calx.templates.method_docs import dispatch, how_we_document, orchestration, review


class TestHowWeDocument:
    def test_returns_non_empty_string(self):
        result = how_we_document()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_has_heading(self):
        result = how_we_document()
        assert "# How We Document" in result

    def test_covers_three_tiers(self):
        result = how_we_document()
        assert "Corrections" in result
        assert "Lessons" in result
        assert "Rules" in result

    def test_covers_distillation(self):
        result = how_we_document()
        assert "Distillation" in result

    def test_mentions_corrections_jsonl(self):
        result = how_we_document()
        assert "corrections.jsonl" in result


class TestOrchestration:
    def test_returns_non_empty_string(self):
        result = orchestration()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_has_heading(self):
        result = orchestration()
        assert "# Orchestration" in result

    def test_covers_hooks(self):
        result = orchestration()
        assert "Hook" in result or "hook" in result

    def test_covers_session_bootstrap(self):
        result = orchestration()
        assert "Session Bootstrap" in result

    def test_covers_context_collapse(self):
        result = orchestration()
        assert "Context Collapse" in result or "compaction" in result


class TestDispatch:
    def test_returns_non_empty_string(self):
        result = dispatch()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_has_heading(self):
        result = dispatch()
        assert "# Dispatch" in result

    def test_covers_cold_start(self):
        result = dispatch()
        assert "Cold-Start" in result

    def test_covers_context_isolation(self):
        result = dispatch()
        assert "Context Isolation" in result

    def test_covers_dependency_graphs(self):
        result = dispatch()
        assert "Dependency Graph" in result

    def test_covers_verification(self):
        result = dispatch()
        assert "Verify" in result


class TestReview:
    def test_returns_non_empty_string(self):
        result = review()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_has_heading(self):
        result = review()
        assert "# Review" in result

    def test_covers_foil_review(self):
        result = review()
        assert "foil" in result.lower()

    def test_covers_binary_output(self):
        result = review()
        assert "APPROVE" in result
        assert "REVISE" in result

    def test_covers_cross_domain(self):
        result = review()
        assert "Cross-Domain" in result

    def test_covers_review_rounds(self):
        result = review()
        assert "Review Rounds" in result
