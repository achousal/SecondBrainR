"""Tests for hypothesis_exchange module -- cross-vault hypothesis federation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from engram_r.hypothesis_exchange import (
    ExportedHypothesis,
    HypothesisExchangeError,
    export_hypotheses,
    export_hypothesis,
    export_to_yaml,
    import_hypotheses,
    load_exported_hypotheses,
)

_NOW = datetime(2026, 2, 23, 12, 0, 0, tzinfo=UTC)

_SAMPLE_HYP = """\
---
type: hypothesis
title: "Factor-X trans-signaling drives test mechanism in TC"
id: H-TEST-001
status: active
elo: 1350
matches: 8
wins: 6
losses: 2
generation: 2
research_goal: "[[tc-mechanism-hypothesis]]"
tags:
  - hypothesis
  - immunology
created: "2026-02-01"
updated: "2026-02-20"
review_scores:
  novelty: 7
  correctness: 8
  testability: 9
  impact: 8
  overall: 8
---

## Statement

Factor-X trans-signaling through [[soluble Factor-X receptor]] is the primary
driver of chronic test mechanism in TC brain regions.

## Mechanism

The sFactor-XR/Factor-X complex activates [[STAT3 signaling]] in neurons
that lack membrane-bound Factor-XR, creating a feed-forward loop.

## Testable Predictions
- [ ] sample-fluid sFactor-XR levels correlate with PET test mechanism signal
- [ ] sgp130 (trans-signaling blocker) reduces microglial activation in vitro

## Assumptions
- sFactor-XR crosses the test-barrier in sufficient quantities
- Trans-signaling dominates over classical signaling in TC

## Limitations & Risks
Risk of confounding by peripheral inflammation.
"""


class TestExportHypothesis:
    """Test single hypothesis export."""

    def test_basic_export(self) -> None:
        hyp = export_hypothesis(_SAMPLE_HYP, source_vault="main", now=_NOW)
        assert hyp.id == "H-TEST-001"
        assert hyp.title == "Factor-X trans-signaling drives test mechanism in TC"
        assert hyp.status == "active"
        assert hyp.elo == 1350.0
        assert hyp.matches == 8
        assert hyp.generation == 2
        assert hyp.source_vault == "main"

    def test_wiki_links_stripped(self) -> None:
        hyp = export_hypothesis(_SAMPLE_HYP, source_vault="main", now=_NOW)
        assert "[[" not in hyp.statement
        assert "[[" not in hyp.mechanism
        assert "soluble Factor-X receptor" in hyp.statement
        assert "STAT3 signaling" in hyp.mechanism

    def test_research_goal_stripped(self) -> None:
        hyp = export_hypothesis(_SAMPLE_HYP, source_vault="main", now=_NOW)
        assert hyp.research_goal == "tc-mechanism-hypothesis"

    def test_sections_extracted(self) -> None:
        hyp = export_hypothesis(_SAMPLE_HYP, source_vault="main", now=_NOW)
        assert "Factor-X trans-signaling" in hyp.statement
        assert "sFactor-XR/Factor-X complex" in hyp.mechanism
        assert "sample-fluid sFactor-XR levels" in hyp.predictions
        assert "sFactor-XR crosses the test-barrier" in hyp.assumptions
        assert "confounding" in hyp.limitations

    def test_no_frontmatter_raises(self) -> None:
        with pytest.raises(HypothesisExchangeError, match="frontmatter"):
            export_hypothesis("no frontmatter", source_vault="v")


class TestExportPiiSanitization:
    """PII sanitization on hypothesis export."""

    _HYP_WITH_PII = """\
---
type: hypothesis
title: "PII test hypothesis"
id: H-PII-001
status: proposed
elo: 1200
matches: 0
generation: 1
---

## Statement

Contact alice@example.com for details on this hypothesis.

## Mechanism

Call (555) 123-4567 for raw data.

## Testable Predictions
- MRN: 12345 shows elevated levels

## Assumptions
- Verified by SSN 111-22-3333 holder

## Limitations & Risks
No known PII in this section.
"""

    def test_body_sections_redacted(self) -> None:
        hyp = export_hypothesis(
            self._HYP_WITH_PII, source_vault="v", now=_NOW, sanitize_pii=True
        )
        assert "alice@example.com" not in hyp.statement
        assert "555" not in hyp.mechanism
        assert "12345" not in hyp.predictions
        assert "111-22-3333" not in hyp.assumptions
        assert "[REDACTED]" in hyp.statement

    def test_disabled_preserves(self) -> None:
        hyp = export_hypothesis(
            self._HYP_WITH_PII, source_vault="v", now=_NOW, sanitize_pii=False
        )
        assert "alice@example.com" in hyp.statement
        assert "555" in hyp.mechanism

    def test_clean_content_unchanged(self) -> None:
        hyp = export_hypothesis(
            _SAMPLE_HYP, source_vault="main", now=_NOW, sanitize_pii=True
        )
        # No PII in _SAMPLE_HYP, content should be unchanged
        assert "Factor-X trans-signaling" in hyp.statement
        assert "sFactor-XR/Factor-X complex" in hyp.mechanism


class TestExportHypotheses:
    """Test bulk export with filtering."""

    @pytest.fixture()
    def vault(self, tmp_path: Path) -> Path:
        hyp_dir = tmp_path / "_research" / "hypotheses"
        hyp_dir.mkdir(parents=True)

        for i, (elo, status) in enumerate(
            [(1400, "active"), (1200, "proposed"), (1100, "retired")]
        ):
            fm = {
                "type": "hypothesis",
                "title": f"Hypothesis {i}",
                "id": f"H-{i:03d}",
                "status": status,
                "elo": elo,
                "matches": i * 3,
                "generation": 1,
                "tags": ["hypothesis"],
            }
            fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
            content = f"---\n{fm_str}---\n\n## Statement\n\nTest {i}.\n"
            (hyp_dir / f"H-{i:03d}.md").write_text(content)

        # Also an _index.md that should be skipped
        (hyp_dir / "_index.md").write_text("# Index\n")
        return tmp_path

    def test_exports_all(self, vault: Path) -> None:
        hyps = export_hypotheses(vault, source_vault="test", now=_NOW)
        assert len(hyps) == 3

    def test_sorted_by_elo_descending(self, vault: Path) -> None:
        hyps = export_hypotheses(vault, source_vault="test", now=_NOW)
        elos = [h.elo for h in hyps]
        assert elos == sorted(elos, reverse=True)

    def test_filter_by_min_elo(self, vault: Path) -> None:
        hyps = export_hypotheses(vault, source_vault="test", min_elo=1200, now=_NOW)
        assert len(hyps) == 2
        assert all(h.elo >= 1200 for h in hyps)

    def test_max_count(self, vault: Path) -> None:
        hyps = export_hypotheses(vault, source_vault="test", max_count=1, now=_NOW)
        assert len(hyps) == 1
        assert hyps[0].elo == 1400  # top by Elo

    def test_skips_index_files(self, vault: Path) -> None:
        hyps = export_hypotheses(vault, source_vault="test", now=_NOW)
        ids = [h.id for h in hyps]
        assert all(not i.startswith("_") for i in ids)

    def test_missing_dir(self, tmp_path: Path) -> None:
        hyps = export_hypotheses(tmp_path, source_vault="test")
        assert hyps == []


class TestYamlRoundTrip:
    """Test YAML serialization/deserialization."""

    def test_round_trip(self) -> None:
        original = [
            ExportedHypothesis(
                id="H-001",
                title="Test hypothesis",
                elo=1400,
                matches=8,
                statement="It works.",
                source_vault="main",
                exported="2026-02-23T12:00:00+00:00",
            )
        ]
        yaml_str = export_to_yaml(original)
        loaded = load_exported_hypotheses(yaml_str)
        assert len(loaded) == 1
        assert loaded[0].id == "H-001"
        assert loaded[0].title == "Test hypothesis"
        assert loaded[0].elo == 1400
        assert loaded[0].statement == "It works."

    def test_load_invalid_yaml(self) -> None:
        with pytest.raises(HypothesisExchangeError):
            load_exported_hypotheses("{bad: [")

    def test_load_non_list(self) -> None:
        with pytest.raises(HypothesisExchangeError, match="list"):
            load_exported_hypotheses("key: value")

    def test_skips_items_without_id(self) -> None:
        result = load_exported_hypotheses("- title: no id\n")
        assert len(result) == 0


class TestImportHypotheses:
    """Test importing hypotheses as foreign-hypothesis notes."""

    @pytest.fixture()
    def vault(self, tmp_path: Path) -> Path:
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)
        return tmp_path

    def _make_hyp(self, hyp_id: str = "H-EXT-001") -> ExportedHypothesis:
        return ExportedHypothesis(
            id=hyp_id,
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

    def test_creates_note_file(self, vault: Path) -> None:
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps)
        assert len(created) == 1
        assert created[0].name == "H-EXT-001.md"

    def test_foreign_hypothesis_type(self, vault: Path) -> None:
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps)
        content = created[0].read_text(encoding="utf-8")
        assert "type: foreign-hypothesis" in content

    def test_federated_elo_fields(self, vault: Path) -> None:
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps)
        content = created[0].read_text(encoding="utf-8")
        assert "elo_federated: 1200" in content
        assert "elo_source: 1350" in content
        assert "matches_federated: 0" in content
        assert "matches_source: 8" in content

    def test_source_vault_preserved(self, vault: Path) -> None:
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps)
        content = created[0].read_text(encoding="utf-8")
        assert "source_vault: collab-lab" in content

    def test_body_sections_present(self, vault: Path) -> None:
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps)
        content = created[0].read_text(encoding="utf-8")
        assert "## Statement" in content
        assert "Compounds drive TC pathology." in content
        assert "## Mechanism" in content
        assert "## Federated Tournament History" in content

    def test_no_overwrite_by_default(self, vault: Path) -> None:
        note_path = vault / "_research" / "hypotheses" / "H-EXT-001.md"
        note_path.write_text("existing")
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps, overwrite=False)
        assert len(created) == 0
        assert note_path.read_text() == "existing"

    def test_overwrite_replaces(self, vault: Path) -> None:
        note_path = vault / "_research" / "hypotheses" / "H-EXT-001.md"
        note_path.write_text("existing")
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps, overwrite=True)
        assert len(created) == 1
        assert "Compounds drive TC pathology." in created[0].read_text()

    def test_creates_dir_if_missing(self, tmp_path: Path) -> None:
        hyps = [self._make_hyp()]
        created = import_hypotheses(tmp_path, hyps)
        assert len(created) == 1

    def test_tags_include_foreign_hypothesis(self, vault: Path) -> None:
        hyps = [self._make_hyp()]
        created = import_hypotheses(vault, hyps)
        content = created[0].read_text(encoding="utf-8")
        assert "foreign-hypothesis" in content


class TestImportSanitization:
    """A2: hypothesis imports sanitize filenames and normalize titles."""

    def test_import_sanitizes_id_for_filename(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        (vault / "_research" / "hypotheses").mkdir(parents=True)
        hyp = ExportedHypothesis(
            id="H/EXT/001",  # slashes in id
            title="Slash test",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_hypotheses(vault, [hyp])
        assert len(created) == 1
        assert "/" not in created[0].name
        assert ":" not in created[0].name

    def test_import_normalizes_title_nfc(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        (vault / "_research" / "hypotheses").mkdir(parents=True)
        hyp = ExportedHypothesis(
            id="H-NFC-001",
            title="cafe\u0301 hypothesis",  # decomposed e-acute
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_hypotheses(vault, [hyp])
        assert len(created) == 1
        content = created[0].read_text(encoding="utf-8")
        # Title in frontmatter should be NFC-normalized
        assert "\u0301" not in content
        assert "caf\u00e9" in content


class TestImportQuarantineAndSanitization:
    """WI-6: quarantine flag, HTML stripping, NFC normalization on import."""

    @pytest.fixture()
    def vault(self, tmp_path: Path) -> Path:
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)
        return tmp_path

    def test_quarantine_added_by_default(self, vault: Path) -> None:
        hyp = ExportedHypothesis(
            id="H-Q-001",
            title="Quarantine test",
            source_vault="peer",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_hypotheses(vault, [hyp])
        content = created[0].read_text(encoding="utf-8")
        assert "quarantine: true" in content

    def test_quarantine_absent_when_disabled(self, vault: Path) -> None:
        hyp = ExportedHypothesis(
            id="H-Q-002",
            title="Trusted import test",
            source_vault="peer",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_hypotheses(vault, [hyp], quarantine=False)
        content = created[0].read_text(encoding="utf-8")
        assert "quarantine: true" not in content

    def test_html_stripped_from_statement(self, vault: Path) -> None:
        hyp = ExportedHypothesis(
            id="H-HTML-001",
            title="HTML test",
            statement="<b>Bold</b> and <script>alert('x')</script>clean.",
            source_vault="peer",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_hypotheses(vault, [hyp])
        content = created[0].read_text(encoding="utf-8")
        assert "<b>" not in content
        assert "<script>" not in content
        assert "Bold" in content
        assert "clean." in content

    def test_html_stripped_from_mechanism(self, vault: Path) -> None:
        hyp = ExportedHypothesis(
            id="H-HTML-002",
            title="HTML mech test",
            mechanism="Via <em>receptor</em> binding.",
            source_vault="peer",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_hypotheses(vault, [hyp])
        content = created[0].read_text(encoding="utf-8")
        assert "<em>" not in content
        assert "receptor" in content

    def test_nfc_normalized_body(self, vault: Path) -> None:
        hyp = ExportedHypothesis(
            id="H-NFC-002",
            title="NFC body test",
            statement="cafe\u0301 mechanism drives pathology.",
            source_vault="peer",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_hypotheses(vault, [hyp])
        content = created[0].read_text(encoding="utf-8")
        assert "\u0301" not in content
        assert "caf\u00e9" in content


class TestImportRejectsInvalidSchema:
    """A3: import raises on invalid schema."""

    def test_import_rejects_hypothesis_invalid_schema(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from engram_r.schema_validator import ValidationResult

        vault = tmp_path / "vault"
        (vault / "_research" / "hypotheses").mkdir(parents=True)
        hyp = ExportedHypothesis(
            id="H-BAD-001",
            title="Invalid hypothesis",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        fake_result = ValidationResult(
            valid=False, errors=["missing title field"]
        )
        with (
            patch(
                "engram_r.hypothesis_exchange.validate_note",
                return_value=fake_result,
            ),
            pytest.raises(
                HypothesisExchangeError, match="fails schema"
            ),
        ):
            import_hypotheses(vault, [hyp])


class TestImportedHypothesisSchemaValidation:
    """B2 canary: imported hypotheses must pass schema validation."""

    def test_imported_hypothesis_passes_schema_validation(self, tmp_path: Path) -> None:
        from engram_r.schema_validator import validate_note

        vault = tmp_path / "vault"
        (vault / "_research" / "hypotheses").mkdir(parents=True)
        hyp = ExportedHypothesis(
            id="H-EXT-001",
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
        created = import_hypotheses(vault, [hyp])
        assert len(created) == 1
        content = created[0].read_text(encoding="utf-8")
        result = validate_note(content)
        assert result.valid, f"Schema errors: {result.errors}"


class TestFullRoundTrip:
    """Test complete export -> YAML -> load -> import cycle."""

    def test_round_trip_preserves_content(self, tmp_path: Path) -> None:
        # Source vault with a hypothesis
        src = tmp_path / "src"
        hyp_dir = src / "_research" / "hypotheses"
        hyp_dir.mkdir(parents=True)
        (hyp_dir / "H-001.md").write_text(_SAMPLE_HYP)

        # Export
        hyps = export_hypotheses(src, source_vault="lab-a", now=_NOW)
        assert len(hyps) == 1

        # Serialize + deserialize
        yaml_str = export_to_yaml(hyps)
        loaded = load_exported_hypotheses(yaml_str)
        assert len(loaded) == 1

        # Import into target vault
        dst = tmp_path / "dst"
        created = import_hypotheses(dst, loaded)
        assert len(created) == 1

        # Verify imported content
        content = created[0].read_text(encoding="utf-8")
        assert "foreign-hypothesis" in content
        assert "source_vault: lab-a" in content
        assert "elo_federated: 1200" in content
        assert "elo_source: 1350" in content
        assert "soluble Factor-X receptor" in content  # link text preserved
        assert "[[" not in content  # no wiki-links
