"""Tests for note builder functions."""

from datetime import date

import yaml

import pytest

from engram_r.note_builder import (
    build_claim_note,
    build_eda_report_note,
    build_experiment_note,
    build_foreign_hypothesis_note,
    build_hypothesis_note,
    build_lab_note,
    build_literature_note,
    build_meta_review_note,
    build_project_note,
    build_research_goal_note,
    build_tournament_match_note,
)


def _parse_frontmatter(content: str) -> dict:
    """Extract and parse YAML frontmatter from note content."""
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Missing frontmatter delimiters"
    return yaml.safe_load(parts[1])


class TestBuildLiteratureNote:
    def test_basic_structure(self):
        note = build_literature_note(
            title="Test Paper",
            doi="10.1234/test",
            authors=["Smith A", "Jones B"],
            year=2024,
            journal="Nature",
            abstract="An abstract.",
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "literature"
        assert fm["title"] == "Test Paper"
        assert fm["doi"] == "10.1234/test"
        assert fm["status"] == "unread"
        assert "## Abstract" in note
        assert "An abstract." in note

    def test_defaults(self):
        note = build_literature_note(title="Minimal")
        fm = _parse_frontmatter(note)
        assert fm["authors"] == []
        assert "literature" in fm["tags"]

    def test_source_type_tag_injected(self):
        note = build_literature_note(
            title="S2 Paper",
            source_type="semantic_scholar",
            today=date(2026, 2, 28),
        )
        fm = _parse_frontmatter(note)
        assert fm["tags"] == ["literature", "semantic_scholar"]

    def test_source_type_with_extra_tags(self):
        note = build_literature_note(
            title="OA Paper",
            source_type="openalex",
            tags=["markers"],
            today=date(2026, 2, 28),
        )
        fm = _parse_frontmatter(note)
        assert fm["tags"] == ["literature", "openalex", "markers"]

    def test_empty_source_type_no_extra_tag(self):
        note = build_literature_note(
            title="Plain Paper",
            source_type="",
            today=date(2026, 2, 28),
        )
        fm = _parse_frontmatter(note)
        assert fm["tags"] == ["literature"]

    def test_no_source_type_backward_compat(self):
        note = build_literature_note(
            title="Old Style",
            tags=["custom"],
            today=date(2026, 2, 28),
        )
        fm = _parse_frontmatter(note)
        assert fm["tags"] == ["literature", "custom"]


class TestBuildHypothesisNote:
    def test_full_structure(self):
        note = build_hypothesis_note(
            title="Test Hyp",
            hyp_id="hyp-001",
            statement="A bold claim.",
            mechanism="Via pathway X.",
            research_goal="[[goal-1]]",
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "hypothesis"
        assert fm["id"] == "hyp-001"
        assert fm["elo"] == 1200
        assert fm["generation"] == 1
        assert fm["review_scores"]["novelty"] is None
        assert "## Statement" in note
        assert "A bold claim." in note
        assert "## Mechanism" in note
        assert "## Review History" in note
        assert "## Evolution History" in note

    def test_defaults(self):
        note = build_hypothesis_note(title="T", hyp_id="h1")
        fm = _parse_frontmatter(note)
        assert fm["parents"] == []
        assert fm["children"] == []


class TestBuildExperimentNote:
    def test_structure(self):
        note = build_experiment_note(
            title="Exp 1",
            hypothesis_link="[[hyp-001]]",
            parameters={"alpha": 0.05, "n_iter": 1000},
            seed=42,
            objective="Test the thing.",
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "experiment"
        assert fm["seed"] == 42
        assert fm["parameters"]["alpha"] == 0.05
        assert "## Objective" in note


class TestBuildEdaReportNote:
    def test_structure(self):
        note = build_eda_report_note(
            title="EDA 1",
            dataset_path="/data/cohort.csv",
            n_rows=100,
            n_cols=12,
            redacted_columns=["SubjectID"],
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "eda-report"
        assert fm["n_rows"] == 100
        assert "SubjectID" in fm["redacted_columns"]
        assert "## Distributions" in note


class TestBuildResearchGoalNote:
    def test_structure(self):
        note = build_research_goal_note(
            title="Test Analysis",
            objective="Identify novel metric relationships.",
            domain="test-domain",
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "research-goal"
        assert fm["status"] == "active"
        assert fm["domain"] == "test-domain"
        assert "## Objective" in note


class TestBuildTournamentMatchNote:
    def test_structure(self):
        note = build_tournament_match_note(
            research_goal="[[goal-1]]",
            hypothesis_a="[[hyp-001]]",
            hypothesis_b="[[hyp-002]]",
            winner="hyp-001",
            elo_change_a=16.0,
            elo_change_b=-16.0,
            debate_summary="A was more novel.",
            verdict="Hypothesis A wins.",
            justification="Stronger literature grounding.",
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "tournament-match"
        assert fm["winner"] == "hyp-001"
        assert fm["elo_change_a"] == 16.0
        assert "## Verdict" in note


class TestBuildMetaReviewNote:
    def test_structure(self):
        note = build_meta_review_note(
            research_goal="[[goal-1]]",
            hypotheses_reviewed=10,
            matches_analyzed=15,
            recurring_weaknesses="Weak literature grounding.",
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "meta-review"
        assert fm["hypotheses_reviewed"] == 10
        assert "## Recurring Weaknesses" in note
        assert "Weak literature grounding." in note


class TestBuildLabNote:
    def test_basic_structure(self):
        note = build_lab_note(
            lab_slug="example-lab",
            pi="Test PI",
            institution="Test University",
            hpc_cluster="TestCluster",
            hpc_scheduler="",
            research_focus="Biomarker discovery",
            departments=["Department A", "Department B"],
            center_affiliations=["Test Condition Research Center"],
            external_affiliations=["Affiliated Research Center"],
            today=date(2026, 2, 23),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "lab"
        assert fm["lab_slug"] == "example-lab"
        assert fm["pi"] == "Test PI"
        assert fm["institution"] == "Test University"
        assert fm["departments"] == ["Department A", "Department B"]
        assert fm["center_affiliations"] == ["Test Condition Research Center"]
        assert fm["external_affiliations"] == ["Affiliated Research Center"]
        assert fm["hpc_cluster"] == "TestCluster"
        assert fm["hpc_scheduler"] == ""
        assert fm["created"] == "2026-02-23"
        assert fm["updated"] == "2026-02-23"
        assert "lab" in fm["tags"]
        assert "## Projects" in note
        assert "## Datasets" in note

    def test_defaults(self):
        note = build_lab_note(lab_slug="test")
        fm = _parse_frontmatter(note)
        assert fm["pi"] == ""
        assert fm["institution"] == ""
        assert fm["departments"] == []
        assert fm["center_affiliations"] == []
        assert fm["external_affiliations"] == []
        assert fm["hpc_cluster"] == ""
        assert fm["hpc_scheduler"] == ""
        assert fm["research_focus"] == ""
        assert "lab" in fm["tags"]

    def test_single_department(self):
        note = build_lab_note(
            lab_slug="test-lab-c",
            departments=["Microbiology"],
            today=date(2026, 2, 28),
        )
        fm = _parse_frontmatter(note)
        assert fm["departments"] == ["Microbiology"]
        assert fm["center_affiliations"] == []
        assert fm["external_affiliations"] == []

    def test_custom_tags(self):
        note = build_lab_note(lab_slug="test", tags=["custom"])
        fm = _parse_frontmatter(note)
        assert "lab" in fm["tags"]
        assert "custom" in fm["tags"]


class TestBuildProjectNote:
    def test_basic_structure(self):
        note = build_project_note(
            title="TestProject",
            project_tag="test-project",
            lab="TestLab",
            pi="TestLab",
            project_path="/Users/test/Projects/TestProject",
            language=["Python", "Bash"],
            hpc_path="/tmp/hpc/projects/test",
            description="ML pipeline for risk prediction.",
            has_claude_md=True,
            has_git=True,
            has_tests=True,
            tags=["test-lab"],
            today=date(2026, 2, 21),
        )
        fm = _parse_frontmatter(note)
        assert fm["type"] == "project"
        assert fm["title"] == "TestProject"
        assert fm["project_tag"] == "test-project"
        assert fm["lab"] == "TestLab"
        assert fm["pi"] == "TestLab"
        assert fm["status"] == "active"
        assert fm["project_path"] == "/Users/test/Projects/TestProject"
        assert fm["language"] == ["Python", "Bash"]
        assert fm["hpc_path"] == "/tmp/hpc/projects/test"
        assert fm["has_claude_md"] is True
        assert fm["has_git"] is True
        assert fm["has_tests"] is True
        assert fm["created"] == "2026-02-21"
        assert fm["updated"] == "2026-02-21"
        assert "project" in fm["tags"]
        assert "test-lab" in fm["tags"]
        assert "## Description" in note
        assert "ML pipeline for risk prediction." in note
        assert "## Research Goals" in note
        assert "## Status Log" in note

    def test_valid_statuses(self):
        for status in ("active", "maintenance", "archived"):
            note = build_project_note(
                title="T",
                project_tag="t",
                lab="L",
                project_path="/tmp/t",
                status=status,
                today=date(2026, 2, 21),
            )
            fm = _parse_frontmatter(note)
            assert fm["status"] == status

        with pytest.raises(ValueError, match="status must be one of"):
            build_project_note(
                title="T",
                project_tag="t",
                lab="L",
                project_path="/tmp/t",
                status="invalid",
            )

    def test_defaults(self):
        note = build_project_note(
            title="Minimal",
            project_tag="minimal",
            lab="Test",
            project_path="/tmp/minimal",
        )
        fm = _parse_frontmatter(note)
        assert fm["pi"] == ""
        assert fm["status"] == "active"
        assert fm["language"] == []
        assert fm["hpc_path"] == ""
        assert fm["scheduler"] == ""
        assert fm["linked_goals"] == []
        assert fm["linked_hypotheses"] == []
        assert fm["linked_experiments"] == []
        assert fm["has_claude_md"] is False
        assert fm["has_git"] is False
        assert fm["has_tests"] is False
        assert fm["scan_dirs"] == []
        assert fm["scan_exclude"] == []
        assert "project" in fm["tags"]

    def test_scan_fields(self):
        note = build_project_note(
            title="Scoped",
            project_tag="scoped",
            lab="Test",
            project_path="/tmp/scoped",
            scan_dirs=["analysis", "scripts"],
            scan_exclude=["docs/_build"],
            today=date(2026, 2, 27),
        )
        fm = _parse_frontmatter(note)
        assert fm["scan_dirs"] == ["analysis", "scripts"]
        assert fm["scan_exclude"] == ["docs/_build"]


# ---------------------------------------------------------------------------
# YAML safety: colon-containing values via yaml.dump (regression)
# ---------------------------------------------------------------------------


class TestYAMLSafetyInNoteBuilder:
    """Confirm _render_note (via yaml.dump) safely handles special characters."""

    def test_colon_in_title_is_quoted(self):
        """yaml.dump auto-quotes strings containing colons."""
        note = build_literature_note(
            title="docs: tighten am/pm references",
            doi="10.1234/test",
            today=date(2026, 2, 22),
        )
        fm = _parse_frontmatter(note)
        assert fm["title"] == "docs: tighten am/pm references"

    def test_colon_in_description(self):
        """Experiment objective with colons roundtrips safely."""
        note = build_experiment_note(
            title="Test",
            objective="Step 1: load data. Step 2: run analysis.",
            today=date(2026, 2, 22),
        )
        fm = _parse_frontmatter(note)
        assert "Step 1:" in note

    def test_brackets_in_research_goal(self):
        """Brackets in string values do not become YAML lists."""
        note = build_research_goal_note(
            title="[Draft] Test Analysis",
            objective="Identify markers.",
            today=date(2026, 2, 22),
        )
        fm = _parse_frontmatter(note)
        assert fm["title"] == "[Draft] Test Analysis"


class TestTournamentMatchMode:
    """Tournament match note mode parameter for federated tournaments."""

    def test_default_mode_is_local(self):
        note = build_tournament_match_note(
            research_goal="[[goal-1]]",
            hypothesis_a="[[hyp-001]]",
            hypothesis_b="[[hyp-002]]",
            today=date(2026, 2, 23),
        )
        fm = _parse_frontmatter(note)
        assert fm["mode"] == "local"

    def test_federated_mode(self):
        note = build_tournament_match_note(
            research_goal="[[goal-1]]",
            hypothesis_a="[[hyp-001]]",
            hypothesis_b="[[hyp-peer-001]]",
            mode="federated",
            today=date(2026, 2, 23),
        )
        fm = _parse_frontmatter(note)
        assert fm["mode"] == "federated"


# ---------------------------------------------------------------------------
# build_claim_note
# ---------------------------------------------------------------------------


class TestBuildClaimNote:
    """Tests for the canonical claim note builder."""

    def test_returns_tuple(self):
        stem, content = build_claim_note(
            title="test claim",
            description="a description",
            today=date(2026, 2, 26),
        )
        assert isinstance(stem, str)
        assert isinstance(content, str)

    def test_basic_structure(self):
        stem, content = build_claim_note(
            title="compound-A levels increase in TC samples",
            description="compound-A accumulation in target region correlates with score burden",
            body="The evidence shows progressive accumulation.",
            source="[[smith-2024-compounds]]",
            confidence="supported",
            source_class="published",
            today=date(2026, 2, 26),
        )
        fm = _parse_frontmatter(content)
        assert fm["type"] == "claim"
        assert fm["confidence"] == "supported"
        assert fm["source_class"] == "published"
        assert fm["verified_by"] == "agent"
        assert fm["created"] == "2026-02-26"
        assert "smith-2024-compounds" in fm["source"]
        assert "The evidence shows progressive accumulation." in content
        assert stem == "compound-A levels increase in TC samples"

    def test_title_sanitization(self):
        stem, content = build_claim_note(
            title="APP/PS1 mice show score (beta)",
            description="A finding about the mouse model",
            today=date(2026, 2, 26),
        )
        assert "/" not in stem
        assert "(" not in stem
        assert ")" not in stem
        assert stem == "APP-PS1 mice show score -beta"

    def test_nfc_normalization_in_description(self):
        stem, content = build_claim_note(
            title="test",
            description="cafe\u0301 study",
            today=date(2026, 2, 26),
        )
        fm = _parse_frontmatter(content)
        assert fm["description"] == "caf\u00e9 study"

    def test_nfc_normalization_in_title(self):
        stem, _ = build_claim_note(
            title="cafe\u0301 study",
            description="desc",
            today=date(2026, 2, 26),
        )
        assert "\u0301" not in stem

    def test_defaults(self):
        stem, content = build_claim_note(
            title="minimal claim",
            description="minimal desc",
            today=date(2026, 2, 26),
        )
        fm = _parse_frontmatter(content)
        assert fm["type"] == "claim"
        assert fm["confidence"] == "preliminary"
        assert fm["source_class"] == "synthesis"
        assert fm["verified_by"] == "agent"
        assert "source" not in fm  # no source when empty
        assert "verified_who" not in fm
        assert "verified_date" not in fm
        assert "tags" not in fm

    def test_all_claim_types(self):
        for claim_type in ("claim", "evidence", "methodology", "contradiction", "pattern"):
            _, content = build_claim_note(
                title=f"test {claim_type}",
                description="desc",
                claim_type=claim_type,
                today=date(2026, 2, 26),
            )
            fm = _parse_frontmatter(content)
            assert fm["type"] == claim_type

    def test_verification_fields(self):
        _, content = build_claim_note(
            title="verified claim",
            description="desc",
            verified_by="human",
            verified_who="Test Verifier",
            verified_date="2026-02-26",
            today=date(2026, 2, 26),
        )
        fm = _parse_frontmatter(content)
        assert fm["verified_by"] == "human"
        assert fm["verified_who"] == "Test Verifier"
        assert fm["verified_date"] == "2026-02-26"

    def test_footer_with_relevant_notes(self):
        _, content = build_claim_note(
            title="test",
            description="desc",
            relevant_notes=[
                ("score drives compound-A", "mechanistic basis"),
                ("compound-A activates PP2A", "downstream effect"),
            ],
            today=date(2026, 2, 26),
        )
        assert "[[score drives compound-A]] -- mechanistic basis" in content
        assert "[[compound-A activates PP2A]] -- downstream effect" in content

    def test_footer_with_topics(self):
        _, content = build_claim_note(
            title="test",
            description="desc",
            topics=["metrics-test-analysis"],
            today=date(2026, 2, 26),
        )
        assert "[[metrics-test-analysis]]" in content
        assert "Topics:" in content

    def test_footer_with_source(self):
        _, content = build_claim_note(
            title="test",
            description="desc",
            source="[[smith-2024]]",
            today=date(2026, 2, 26),
        )
        assert "Source: [[smith-2024]]" in content

    def test_yaml_safety_via_render(self):
        """Colons in description are safely handled by yaml.dump."""
        _, content = build_claim_note(
            title="test",
            description="feat: this has a colon",
            today=date(2026, 2, 26),
        )
        fm = _parse_frontmatter(content)
        assert fm["description"] == "feat: this has a colon"

    def test_tags_included(self):
        _, content = build_claim_note(
            title="test",
            description="desc",
            tags=["compounds", "TC"],
            today=date(2026, 2, 26),
        )
        fm = _parse_frontmatter(content)
        assert fm["tags"] == ["compounds", "TC"]


class TestBuildForeignHypothesisNote:
    """Tests for the foreign-hypothesis note builder."""

    def test_returns_tuple(self):
        stem, content = build_foreign_hypothesis_note(
            hyp_id="H-EXT-001",
            title="External hypothesis",
            source_vault="peer",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert isinstance(stem, str)
        assert isinstance(content, str)

    def test_basic_structure(self):
        stem, content = build_foreign_hypothesis_note(
            hyp_id="H-EXT-001",
            title="External hypothesis about compounds",
            status="active",
            elo=1350,
            matches=8,
            generation=2,
            research_goal="tc-lipids",
            tags=["hypothesis", "lipids"],
            statement="Compounds drive TC pathology.",
            mechanism="Via mitochondrial dysfunction.",
            predictions="sample-fluid compound-A correlates with marker-C.",
            assumptions="compound-A crosses test-barrier.",
            limitations="Small sample sizes.",
            source_vault="collab-lab",
            exported="2026-02-23T12:00:00+00:00",
        )
        fm = _parse_frontmatter(content)
        assert fm["type"] == "foreign-hypothesis"
        assert fm["title"] == "External hypothesis about compounds"
        assert fm["id"] == "H-EXT-001"
        assert fm["elo_federated"] == 1200
        assert fm["elo_source"] == 1350
        assert fm["matches_federated"] == 0
        assert fm["matches_source"] == 8
        assert fm["source_vault"] == "collab-lab"
        assert "foreign-hypothesis" in fm["tags"]
        assert "## Statement" in content
        assert "Compounds drive TC pathology." in content
        assert "## Mechanism" in content
        assert "## Federated Tournament History" in content
        assert stem == "H-EXT-001"

    def test_sanitizes_id_for_filename(self):
        stem, _ = build_foreign_hypothesis_note(
            hyp_id="H/EXT/001",
            title="Slash test",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert "/" not in stem
        assert ":" not in stem

    def test_strips_html_from_statement(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="HTML test",
            statement="<b>Bold</b> statement <script>xss</script>.",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert "<b>" not in content
        assert "<script>" not in content
        assert "Bold statement xss." in content

    def test_strips_html_from_mechanism(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="test",
            mechanism="<p>Mechanism</p>",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert "<p>" not in content
        assert "Mechanism" in content

    def test_strips_html_from_predictions(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="test",
            predictions="<em>Prediction</em>",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert "<em>" not in content
        assert "Prediction" in content

    def test_strips_html_from_assumptions(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="test",
            assumptions="<div>Assumption</div>",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert "<div>" not in content
        assert "Assumption" in content

    def test_strips_html_from_limitations(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="test",
            limitations="<a href='x'>Limit</a>",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert "<a " not in content
        assert "Limit" in content

    def test_nfc_normalization_on_body(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="test",
            statement="cafe\u0301 hypothesis",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        assert "\u0301" not in content
        assert "caf\u00e9" in content

    def test_quarantine_present_by_default(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="test",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        fm = _parse_frontmatter(content)
        assert fm.get("quarantine") is True

    def test_quarantine_absent_when_false(self):
        _, content = build_foreign_hypothesis_note(
            hyp_id="H-001",
            title="test",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
            quarantine=False,
        )
        fm = _parse_frontmatter(content)
        assert "quarantine" not in fm

    def test_schema_validation_passes(self):
        from engram_r.schema_validator import validate_note

        _, content = build_foreign_hypothesis_note(
            hyp_id="H-EXT-001",
            title="Schema test hypothesis",
            status="active",
            elo=1350,
            matches=8,
            source_vault="collab-lab",
            exported="2026-02-23T12:00:00+00:00",
        )
        result = validate_note(content)
        assert result.valid, f"Schema errors: {result.errors}"
