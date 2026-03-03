"""Unit tests for engram_r.queue_validator.

Tests the two pure functions:
- find_new_enrichment_entries: old/new queue diffing
- validate_enrichment_targets: on-disk target existence checks
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engram_r.queue_validator import (
    QueueValidationResult,
    find_new_enrichment_entries,
    validate_enrichment_targets,
)


# ---------------------------------------------------------------------------
# TestFindNewEnrichmentEntries
# ---------------------------------------------------------------------------


class TestFindNewEnrichmentEntries:
    """Diff old vs new queue, returning only genuinely new enrichment entries."""

    def test_empty_queues(self):
        result = find_new_enrichment_entries([], [])
        assert result == []

    def test_new_enrichment_entry_found(self):
        old = [{"id": "extract-001", "type": "extract"}]
        new = [
            {"id": "extract-001", "type": "extract"},
            {"id": "enrich-001", "type": "enrichment", "target": "some claim"},
        ]
        result = find_new_enrichment_entries(old, new)
        assert len(result) == 1
        assert result[0]["id"] == "enrich-001"

    def test_existing_id_excluded(self):
        """An enrichment entry that already existed is NOT flagged."""
        old = [{"id": "enrich-001", "type": "enrichment", "target": "some claim"}]
        new = [
            {
                "id": "enrich-001",
                "type": "enrichment",
                "target": "some claim",
                "status": "blocked",
            }
        ]
        result = find_new_enrichment_entries(old, new)
        assert result == []

    def test_non_enrichment_types_excluded(self):
        """Extract, reflect, and other types are never returned."""
        old = []
        new = [
            {"id": "extract-001", "type": "extract"},
            {"id": "reflect-001", "type": "reflect"},
            {"id": "verify-001", "type": "verify"},
        ]
        result = find_new_enrichment_entries(old, new)
        assert result == []

    def test_deadlock_prevention_modified_existing_entry(self):
        """Modifying an existing enrichment entry (same ID) passes through.

        This is the critical deadlock prevention case: ralph editing status
        or adding notes to an existing entry keeps the same ID, so it should
        NOT be flagged as a new entry requiring target validation.
        """
        old = [
            {
                "id": "enrich-paper-001",
                "type": "enrichment",
                "status": "pending",
                "target": "some claim about mechanisms",
            }
        ]
        new = [
            {
                "id": "enrich-paper-001",
                "type": "enrichment",
                "status": "done",
                "target": "some claim about mechanisms",
                "completed": "2026-03-03T12:00:00",
            }
        ]
        result = find_new_enrichment_entries(old, new)
        assert result == []

    def test_multiple_new_enrichment_entries(self):
        old = [{"id": "extract-001", "type": "extract"}]
        new = [
            {"id": "extract-001", "type": "extract"},
            {"id": "enrich-001", "type": "enrichment", "target": "claim a"},
            {"id": "enrich-002", "type": "enrichment", "target": "claim b"},
        ]
        result = find_new_enrichment_entries(old, new)
        assert len(result) == 2

    def test_entry_without_id_skipped(self):
        """Entries missing an id field are not matched by old_ids."""
        old = []
        new = [{"type": "enrichment", "target": "orphan"}]
        result = find_new_enrichment_entries(old, new)
        # Entry has no id, so it's not in old_ids (empty set doesn't contain None)
        # But type is enrichment and id (None) is not in old_ids, so it IS returned
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestValidateEnrichmentTargets
# ---------------------------------------------------------------------------


class TestValidateEnrichmentTargets:
    """Check that enrichment targets exist as .md files on disk."""

    def test_all_targets_exist(self, tmp_path: Path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "some claim about mechanisms.md").write_text("content")
        (notes_dir / "another claim.md").write_text("content")

        entries = [
            {"id": "enrich-001", "target": "some claim about mechanisms"},
            {"id": "enrich-002", "target": "another claim"},
        ]
        result = validate_enrichment_targets(entries, notes_dir)
        assert result.valid is True
        assert result.phantom_entries == []

    def test_missing_target_detected(self, tmp_path: Path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "existing claim.md").write_text("content")

        entries = [
            {"id": "enrich-001", "target": "nonexistent claim"},
        ]
        result = validate_enrichment_targets(entries, notes_dir)
        assert result.valid is False
        assert len(result.phantom_entries) == 1
        assert result.phantom_entries[0]["id"] == "enrich-001"
        assert result.phantom_entries[0]["target"] == "nonexistent claim"

    def test_multiple_phantoms(self, tmp_path: Path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()

        entries = [
            {"id": "enrich-001", "target": "phantom a"},
            {"id": "enrich-002", "target": "phantom b"},
            {"id": "enrich-003", "target": "phantom c"},
        ]
        result = validate_enrichment_targets(entries, notes_dir)
        assert result.valid is False
        assert len(result.phantom_entries) == 3

    def test_empty_entries(self, tmp_path: Path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()

        result = validate_enrichment_targets([], notes_dir)
        assert result.valid is True

    def test_entry_without_target_field(self, tmp_path: Path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()

        entries = [{"id": "enrich-001"}]
        result = validate_enrichment_targets(entries, notes_dir)
        assert result.valid is False
        assert len(result.phantom_entries) == 1
        assert result.phantom_entries[0]["target"] is None
        assert "missing" in result.phantom_entries[0]["reason"]

    def test_nfc_normalization(self, tmp_path: Path):
        """NFC-normalized target should match an NFC-normalized filename."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        # Write file with NFC-composed name
        (notes_dir / "caf\u00e9 claim.md").write_text("content")

        # Target uses NFD decomposed form (e + combining acute)
        entries = [{"id": "enrich-001", "target": "cafe\u0301 claim"}]
        result = validate_enrichment_targets(entries, notes_dir)
        assert result.valid is True

    def test_mixed_valid_and_phantom(self, tmp_path: Path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "real claim.md").write_text("content")

        entries = [
            {"id": "enrich-001", "target": "real claim"},
            {"id": "enrich-002", "target": "phantom claim"},
        ]
        result = validate_enrichment_targets(entries, notes_dir)
        assert result.valid is False
        assert len(result.phantom_entries) == 1
        assert result.phantom_entries[0]["target"] == "phantom claim"

    def test_result_dataclass_structure(self):
        """QueueValidationResult has expected fields."""
        result = QueueValidationResult(valid=True)
        assert result.valid is True
        assert result.phantom_entries == []
        assert result.errors == []
