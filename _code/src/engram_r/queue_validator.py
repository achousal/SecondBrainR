"""Validate enrichment entries in the processing queue.

Prevents phantom enrichment targets -- queue entries that reference notes
which do not exist on disk.  Called by the ``validate_queue.py`` PostToolUse
hook whenever ``ops/queue/queue.json`` is written.

Two pure functions (no I/O in the validation layer):

- ``find_new_enrichment_entries`` -- diff old vs new queue, return only
  genuinely new enrichment entries (existing-ID edits pass through).
- ``validate_enrichment_targets`` -- check that each entry's ``target``
  resolves to an on-disk ``.md`` file in ``notes/``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QueueValidationResult:
    """Result of validating enrichment queue entries."""

    valid: bool
    phantom_entries: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def find_new_enrichment_entries(
    old_queue: list[dict],
    new_queue: list[dict],
) -> list[dict]:
    """Return enrichment entries in *new_queue* whose IDs are absent from *old_queue*.

    Entries that already existed (same ``id``) pass through unchanged -- this
    prevents deadlocks when ralph updates an existing entry's status or adds
    a blocking note.  Only genuinely *new* enrichment entries are flagged.

    Non-enrichment entry types are never returned.
    """
    old_ids = {entry.get("id") for entry in old_queue if entry.get("id")}
    return [
        entry
        for entry in new_queue
        if entry.get("type") == "enrichment" and entry.get("id") not in old_ids
    ]


def validate_enrichment_targets(
    entries: list[dict],
    notes_dir: Path,
) -> QueueValidationResult:
    """Check that every enrichment entry's target exists as a ``.md`` file.

    Args:
        entries: Enrichment queue entries (from ``find_new_enrichment_entries``).
        notes_dir: Absolute path to the vault's ``notes/`` directory.

    Returns:
        ``QueueValidationResult`` with ``valid=True`` if all targets exist,
        otherwise populated ``phantom_entries`` list.
    """
    if not entries:
        return QueueValidationResult(valid=True)

    phantom: list[dict] = []

    for entry in entries:
        target = entry.get("target")
        if not target:
            phantom.append(
                {
                    "id": entry.get("id", "<no-id>"),
                    "target": None,
                    "expected_path": str(notes_dir),
                    "reason": "enrichment entry missing 'target' field",
                }
            )
            continue

        # NFC-normalize to match vault filename conventions
        target_nfc = unicodedata.normalize("NFC", target)
        expected = notes_dir / f"{target_nfc}.md"

        if not expected.exists():
            phantom.append(
                {
                    "id": entry.get("id", "<no-id>"),
                    "target": target,
                    "expected_path": str(expected),
                }
            )

    if phantom:
        return QueueValidationResult(valid=False, phantom_entries=phantom)

    return QueueValidationResult(valid=True)
