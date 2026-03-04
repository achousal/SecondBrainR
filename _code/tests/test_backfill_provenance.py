"""Tests for backfill_provenance script."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Import from scripts directory
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backfill_provenance import backfill_note, infer_source_class


class TestInferSourceClass:
    """Test source class inference from source field values."""

    def test_hypothesis_h_dash(self) -> None:
        assert infer_source_class('[[H-TC-004b-factor-A]]') == "hypothesis"

    def test_hypothesis_h_zero(self) -> None:
        assert infer_source_class('[[H001-test-mechanism]]') == "hypothesis"

    def test_published_lit_note(self) -> None:
        assert infer_source_class('[[2026-wang-mechanism]]') == "published"

    def test_published_lit_survey(self) -> None:
        assert infer_source_class('[[lit-survey-key-markers]]') == "published"

    def test_empirical_experiment(self) -> None:
        assert infer_source_class('[[EXP-002-treatment]]') == "empirical"

    def test_empty_source(self) -> None:
        assert infer_source_class("") == "synthesis"

    def test_unknown_source(self) -> None:
        assert infer_source_class('[[some-random-note]]') == "synthesis"


class TestBackfillNote:
    """Test backfilling provenance on individual notes."""

    def _write_note(self, path: Path, fm: dict, body: str = "Body text.") -> None:
        fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
        path.write_text(f"---\n{fm_str}---\n\n{body}\n", encoding="utf-8")

    def test_adds_all_fields(self, tmp_path: Path) -> None:
        note = tmp_path / "test.md"
        self._write_note(note, {
            "description": "Test claim",
            "type": "claim",
            "confidence": "supported",
            "source": "[[2026-wang-mechanism]]",
        })
        result = backfill_note(note)
        assert result is not None
        assert result["source_class"] == "published"
        assert result["verified_by"] == "agent"

        # Verify file was updated
        content = note.read_text(encoding="utf-8")
        assert 'source_class: "published"' in content
        assert 'verified_by: "agent"' in content
        assert "verified_who: null" in content
        assert "verified_date: null" in content

    def test_hypothesis_source(self, tmp_path: Path) -> None:
        note = tmp_path / "test.md"
        self._write_note(note, {
            "description": "Test claim",
            "type": "claim",
            "source": "[[H-TC-006-factor-response]]",
        })
        result = backfill_note(note)
        assert result is not None
        assert result["source_class"] == "hypothesis"

    def test_skips_moc(self, tmp_path: Path) -> None:
        note = tmp_path / "index.md"
        self._write_note(note, {"description": "Index", "type": "moc"})
        result = backfill_note(note)
        assert result is None

    def test_skips_already_backfilled(self, tmp_path: Path) -> None:
        note = tmp_path / "test.md"
        self._write_note(note, {
            "description": "Test",
            "type": "claim",
            "source_class": "published",
            "verified_by": "agent",
            "verified_who": None,
            "verified_date": None,
        })
        result = backfill_note(note)
        assert result is None

    def test_dry_run_no_write(self, tmp_path: Path) -> None:
        note = tmp_path / "test.md"
        self._write_note(note, {
            "description": "Test",
            "type": "claim",
            "source": "[[2026-something]]",
        })
        original = note.read_text(encoding="utf-8")
        result = backfill_note(note, dry_run=True)
        assert result is not None
        assert note.read_text(encoding="utf-8") == original

    def test_preserves_existing_content(self, tmp_path: Path) -> None:
        note = tmp_path / "test.md"
        self._write_note(
            note,
            {"description": "Test", "type": "claim", "source": "[[2026-x]]"},
            body="Important body with [[wiki links]] preserved.",
        )
        backfill_note(note)
        content = note.read_text(encoding="utf-8")
        assert "Important body with [[wiki links]] preserved." in content
