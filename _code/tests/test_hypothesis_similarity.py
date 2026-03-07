"""Tests for hypothesis similarity and convergence detection."""

from pathlib import Path

import pytest

from engram_r.hypothesis_parser import (
    ConvergenceEntry,
    _extract_list_items,
    _extract_section,
    _jaccard,
    _tokenize,
    append_convergence_entry,
    compute_hypothesis_similarity,
    get_lineage_streak,
    parse_hypothesis_note,
    read_convergence_log,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parent_hyp():
    return parse_hypothesis_note((FIXTURES / "sample_hypothesis.md").read_text())


@pytest.fixture
def child_hyp():
    return parse_hypothesis_note((FIXTURES / "sample_hypothesis_child.md").read_text())


@pytest.fixture
def divergent_hyp():
    return parse_hypothesis_note((FIXTURES / "sample_hypothesis_divergent.md").read_text())


class TestJaccard:
    def test_identical_sets(self):
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        assert _jaccard({"a", "b", "c"}, {"b", "c", "d"}) == 0.5

    def test_both_empty(self):
        assert _jaccard(set(), set()) == 1.0

    def test_one_empty(self):
        assert _jaccard({"a"}, set()) == 0.0


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello World 123")
        assert tokens == {"hello", "world", "123"}

    def test_punctuation_stripped(self):
        tokens = _tokenize("p-tau217, GFAP -- markers")
        assert "p" in tokens
        assert "tau217" in tokens
        assert "gfap" in tokens

    def test_empty(self):
        assert _tokenize("") == set()


class TestExtractSection:
    def test_mechanism(self, parent_hyp):
        mech = _extract_section(parent_hyp.body, "Mechanism")
        assert "dynamic range" in mech

    def test_missing_section(self, parent_hyp):
        assert _extract_section(parent_hyp.body, "Nonexistent") == ""

    def test_predictions(self, parent_hyp):
        preds = _extract_section(parent_hyp.body, "Testable Predictions")
        assert "responders" in preds


class TestExtractListItems:
    def test_checkbox_items(self):
        text = "- [ ] First item\n- [x] Second item\n"
        items = _extract_list_items(text)
        assert "first item" in items
        assert "second item" in items

    def test_plain_items(self):
        text = "- Assumption 1: something -- Status: supported\n"
        items = _extract_list_items(text)
        assert len(items) == 1

    def test_empty(self):
        assert _extract_list_items("") == set()


class TestComputeHypothesisSimilarity:
    def test_identical(self, parent_hyp):
        sim = compute_hypothesis_similarity(parent_hyp, parent_hyp)
        assert sim == pytest.approx(1.0)

    def test_similar_parent_child(self, parent_hyp, child_hyp):
        sim = compute_hypothesis_similarity(parent_hyp, child_hyp)
        assert 0.5 < sim < 1.0

    def test_divergent_low_similarity(self, parent_hyp, divergent_hyp):
        sim = compute_hypothesis_similarity(parent_hyp, divergent_hyp)
        assert sim < 0.3

    def test_symmetry(self, parent_hyp, child_hyp):
        sim_ab = compute_hypothesis_similarity(parent_hyp, child_hyp)
        sim_ba = compute_hypothesis_similarity(child_hyp, parent_hyp)
        assert sim_ab == pytest.approx(sim_ba)

    def test_returns_float_in_range(self, parent_hyp, child_hyp):
        sim = compute_hypothesis_similarity(parent_hyp, child_hyp)
        assert 0.0 <= sim <= 1.0


class TestConvergenceLog:
    def test_read_empty_file(self, tmp_path):
        log = tmp_path / "convergence-log.md"
        assert read_convergence_log(log) == []

    def test_read_nonexistent(self, tmp_path):
        log = tmp_path / "does-not-exist.md"
        assert read_convergence_log(log) == []

    def test_write_and_read_roundtrip(self, tmp_path):
        log = tmp_path / "convergence-log.md"
        entry = ConvergenceEntry(
            date="2026-03-07",
            parent_id="hyp-001",
            child_id="hyp-002",
            lineage_root="hyp-001",
            similarity=0.85,
            streak=1,
            evolution_mode="grounding-enhancement",
        )
        append_convergence_entry(log, entry)

        entries = read_convergence_log(log)
        assert len(entries) == 1
        assert entries[0].parent_id == "hyp-001"
        assert entries[0].similarity == pytest.approx(0.85)

    def test_append_multiple(self, tmp_path):
        log = tmp_path / "convergence-log.md"
        for i in range(3):
            entry = ConvergenceEntry(
                date=f"2026-03-0{i+1}",
                parent_id=f"hyp-{i:03d}",
                child_id=f"hyp-{i+1:03d}",
                lineage_root="hyp-000",
                similarity=0.91 + i * 0.01,
                streak=i + 1,
                evolution_mode="combination",
            )
            append_convergence_entry(log, entry)

        entries = read_convergence_log(log)
        assert len(entries) == 3
        assert entries[2].streak == 3

    def test_malformed_json(self, tmp_path):
        log = tmp_path / "convergence-log.md"
        log.write_text("# Convergence Log\n\n```json\nnot valid json\n```\n")
        assert read_convergence_log(log) == []


class TestGetLineageStreak:
    def _make_entries(self, similarities: list[float], root: str = "hyp-000"):
        return [
            ConvergenceEntry(
                date=f"2026-03-{i+1:02d}",
                parent_id=f"hyp-{i:03d}",
                child_id=f"hyp-{i+1:03d}",
                lineage_root=root,
                similarity=s,
                streak=0,
                evolution_mode="grounding-enhancement",
            )
            for i, s in enumerate(similarities)
        ]

    def test_all_converged(self):
        entries = self._make_entries([0.92, 0.95, 0.91])
        assert get_lineage_streak(entries, "hyp-000") == 3

    def test_streak_broken(self):
        entries = self._make_entries([0.92, 0.80, 0.95])
        assert get_lineage_streak(entries, "hyp-000") == 1

    def test_no_entries(self):
        assert get_lineage_streak([], "hyp-000") == 0

    def test_wrong_lineage(self):
        entries = self._make_entries([0.95, 0.95], root="hyp-999")
        assert get_lineage_streak(entries, "hyp-000") == 0

    def test_mixed_lineages(self):
        entries_a = self._make_entries([0.92, 0.93], root="hyp-a")
        entries_b = self._make_entries([0.50], root="hyp-b")
        all_entries = entries_a + entries_b
        assert get_lineage_streak(all_entries, "hyp-a") == 2
        assert get_lineage_streak(all_entries, "hyp-b") == 0

    def test_exactly_threshold(self):
        entries = self._make_entries([0.90, 0.90, 0.90])
        assert get_lineage_streak(entries, "hyp-000") == 3

    def test_just_below_threshold(self):
        entries = self._make_entries([0.89])
        assert get_lineage_streak(entries, "hyp-000") == 0
