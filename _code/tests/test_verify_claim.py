"""Tests for verify_claim script."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verify_claim import find_batch_claims, verify_note


class TestVerifyNote:
    """Test marking individual claims as human-verified."""

    def _write_note(self, path: Path, fm: dict, body: str = "Body.") -> None:
        fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
        path.write_text(f"---\n{fm_str}---\n\n{body}\n", encoding="utf-8")

    def _read_fm(self, path: Path) -> dict:
        import re
        content = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        assert match is not None
        return yaml.safe_load(match.group(1))

    def test_sets_verified_fields(self, tmp_path: Path) -> None:
        note = tmp_path / "test.md"
        self._write_note(note, {
            "description": "Test",
            "type": "claim",
            "verified_by": "agent",
            "verified_who": None,
            "verified_date": None,
        })
        result = verify_note(note, "Andres Chousal", "2026-02-25")
        assert result is True

        fm = self._read_fm(note)
        assert fm["verified_by"] == "human"
        assert fm["verified_who"] == "Andres Chousal"
        assert fm["verified_date"] == "2026-02-25"

    def test_preserves_other_fields(self, tmp_path: Path) -> None:
        note = tmp_path / "test.md"
        self._write_note(note, {
            "description": "Important claim",
            "type": "evidence",
            "confidence": "supported",
            "source": "[[2026-wang]]",
            "source_class": "published",
            "verified_by": "agent",
            "verified_who": None,
            "verified_date": None,
        })
        verify_note(note, "Andres Chousal", "2026-02-25")
        fm = self._read_fm(note)
        assert fm["description"] == "Important claim"
        assert fm["type"] == "evidence"
        assert fm["confidence"] == "supported"
        assert fm["source_class"] == "published"

    def test_skips_no_frontmatter(self, tmp_path: Path) -> None:
        note = tmp_path / "plain.md"
        note.write_text("No frontmatter here.", encoding="utf-8")
        result = verify_note(note, "Andres Chousal", "2026-02-25")
        assert result is False


class TestFindBatchClaims:
    """Test batch claim discovery with filters."""

    def _write_note(self, path: Path, fm: dict) -> None:
        fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
        path.write_text(f"---\n{fm_str}---\n\nBody.\n", encoding="utf-8")

    def test_finds_matching_claims(self, tmp_path: Path) -> None:
        self._write_note(tmp_path / "a.md", {
            "description": "A",
            "source_class": "hypothesis",
            "confidence": "speculative",
            "verified_by": "agent",
        })
        self._write_note(tmp_path / "b.md", {
            "description": "B",
            "source_class": "published",
            "confidence": "supported",
            "verified_by": "human",
        })
        self._write_note(tmp_path / "c.md", {
            "description": "C",
            "source_class": "hypothesis",
            "confidence": "speculative",
            "verified_by": "agent",
        })

        results = find_batch_claims(
            tmp_path,
            {"source_class": "hypothesis", "confidence": "speculative"},
        )
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"a.md", "c.md"}

    def test_empty_on_no_match(self, tmp_path: Path) -> None:
        self._write_note(tmp_path / "a.md", {
            "description": "A",
            "source_class": "published",
        })
        results = find_batch_claims(tmp_path, {"source_class": "hypothesis"})
        assert len(results) == 0
