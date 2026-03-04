"""Tests for hypothesis note parsing and manipulation."""

from datetime import date
from pathlib import Path

import pytest

from engram_r.hypothesis_parser import (
    HypothesisData,
    append_to_section,
    build_hypothesis_frontmatter,
    parse_hypothesis_note,
    update_frontmatter_field,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_note():
    return (FIXTURES / "sample_hypothesis.md").read_text()


class TestParseHypothesisNote:
    def test_parses_fixture(self, sample_note):
        data = parse_hypothesis_note(sample_note)
        assert isinstance(data, HypothesisData)
        assert data.id == "hyp-20260221-001"
        assert data.title == "Baseline measurement variability predicts six-month treatment response"
        assert data.elo == 1200
        assert data.status == "proposed"
        assert data.generation == 1
        assert data.matches == 0

    def test_body_contains_sections(self, sample_note):
        data = parse_hypothesis_note(sample_note)
        assert "## Statement" in data.body
        assert "## Mechanism" in data.body
        assert "## Review History" in data.body

    def test_review_scores_present(self, sample_note):
        data = parse_hypothesis_note(sample_note)
        scores = data.review_scores
        assert "novelty" in scores
        assert scores["novelty"] is None

    def test_missing_frontmatter_raises(self):
        with pytest.raises(ValueError, match="No valid YAML"):
            parse_hypothesis_note("# Just a heading\nNo frontmatter here.")

    def test_invalid_yaml_raises(self):
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_hypothesis_note("---\n: invalid: yaml: [[\n---\nBody")

    def test_non_dict_frontmatter_raises(self):
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            parse_hypothesis_note("---\n- just a list\n---\nBody")


class TestUpdateFrontmatterField:
    def test_updates_elo(self, sample_note):
        updated = update_frontmatter_field(sample_note, "elo", 1300)
        data = parse_hypothesis_note(updated)
        assert data.elo == 1300

    def test_updates_status(self, sample_note):
        updated = update_frontmatter_field(sample_note, "status", "active")
        data = parse_hypothesis_note(updated)
        assert data.status == "active"

    def test_adds_new_field(self, sample_note):
        updated = update_frontmatter_field(sample_note, "custom_field", "value")
        data = parse_hypothesis_note(updated)
        assert data.frontmatter["custom_field"] == "value"

    def test_preserves_body(self, sample_note):
        updated = update_frontmatter_field(sample_note, "elo", 9999)
        data = parse_hypothesis_note(updated)
        assert "Higher baseline variability" in data.body

    def test_no_frontmatter_raises(self):
        with pytest.raises(ValueError):
            update_frontmatter_field("No frontmatter", "key", "val")


class TestAppendToSection:
    def test_appends_to_review_history(self, sample_note):
        entry = "\n### 2026-02-21 Quick Screen\nLooks promising.\n"
        updated = append_to_section(sample_note, "Review History", entry)
        assert "Looks promising." in updated
        # Verify it's in the right place (before Evolution History)
        rh_pos = updated.index("## Review History")
        eh_pos = updated.index("## Evolution History")
        entry_pos = updated.index("Looks promising.")
        assert rh_pos < entry_pos < eh_pos

    def test_section_not_found_raises(self, sample_note):
        with pytest.raises(ValueError, match="not found"):
            append_to_section(sample_note, "Nonexistent Section", "text")

    def test_appends_to_last_section(self, sample_note):
        entry = "\nEvolved from hyp-000 by simplification.\n"
        updated = append_to_section(sample_note, "Evolution History", entry)
        assert "Evolved from hyp-000" in updated


class TestBuildHypothesisFrontmatter:
    def test_defaults(self):
        fm = build_hypothesis_frontmatter(
            title="Test", hyp_id="hyp-test-001", today=date(2026, 2, 21)
        )
        assert fm["type"] == "hypothesis"
        assert fm["elo"] == 1200
        assert fm["generation"] == 1
        assert fm["status"] == "proposed"
        assert fm["review_scores"]["novelty"] is None
        assert fm["created"] == "2026-02-21"

    def test_custom_tags(self):
        fm = build_hypothesis_frontmatter(
            title="T", hyp_id="h1", tags=["analysis", "marker"]
        )
        assert "hypothesis" in fm["tags"]
        assert "analysis" in fm["tags"]


class TestFederatedProperties:
    """Federated field accessors on HypothesisData."""

    def _make(self, extra_fm: dict | None = None) -> HypothesisData:
        fm = {
            "type": "hypothesis",
            "title": "Test",
            "id": "hyp-001",
            "status": "proposed",
            "elo": 1200,
            "matches": 0,
        }
        if extra_fm:
            fm.update(extra_fm)
        import yaml

        fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
        content = f"---\n{fm_str}---\n\n## Body\n"
        return parse_hypothesis_note(content)

    def test_elo_federated_present(self):
        data = self._make({"elo_federated": 1350.5})
        assert data.elo_federated == 1350.5

    def test_elo_federated_default(self):
        data = self._make()
        assert data.elo_federated == 0.0

    def test_matches_federated_present(self):
        data = self._make({"matches_federated": 7})
        assert data.matches_federated == 7

    def test_matches_federated_default(self):
        data = self._make()
        assert data.matches_federated == 0

    def test_is_foreign_true(self):
        data = self._make({"type": "foreign-hypothesis"})
        assert data.is_foreign is True

    def test_is_foreign_false_for_hypothesis(self):
        data = self._make({"type": "hypothesis"})
        assert data.is_foreign is False

    def test_source_vault_present(self):
        data = self._make({"source_vault": "collab-lab-uuid"})
        assert data.source_vault == "collab-lab-uuid"

    def test_source_vault_default(self):
        data = self._make()
        assert data.source_vault == ""
