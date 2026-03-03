"""Backfill epistemic provenance fields on existing claim notes.

Adds verified_by, verified_who, source_class, and verified_date to all
claims in notes/ that lack them.  Non-destructive: appends fields to
existing frontmatter without rewriting other content.

Source class inference logic:
  - source matches [[H-*]] or [[H0*]]       -> hypothesis
  - source matches [[2026-*]] (lit notes)    -> published
  - source matches [[EXP-*]]                 -> empirical
  - source matches [[lit-survey-*]]          -> published
  - no source or other                       -> synthesis

Usage:
  uv run python scripts/backfill_provenance.py [--dry-run] [--notes-dir PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Source class inference from the source wiki-link target
_SOURCE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\[\[H-"), "hypothesis"),
    (re.compile(r"^\[\[H0"), "hypothesis"),
    (re.compile(r"^\[\[EXP-"), "empirical"),
    (re.compile(r"^\[\[lit-survey-"), "published"),
    (re.compile(r"^\[\[2026-"), "published"),
    (re.compile(r"^\[\[202[0-9]-"), "published"),
]


def infer_source_class(source_value: str) -> str:
    """Infer source_class from the source field value."""
    source_value = source_value.strip()
    if not source_value:
        return "synthesis"
    for pattern, cls in _SOURCE_RULES:
        if pattern.search(source_value):
            return cls
    return "synthesis"


def backfill_note(path: Path, *, dry_run: bool = False) -> dict[str, str] | None:
    """Add provenance fields to a single note.  Returns changes made or None."""
    content = path.read_text(encoding="utf-8")
    match = _FM_PATTERN.match(content)
    if not match:
        return None

    fm_text = match.group(1)
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return None

    if not isinstance(fm, dict):
        return None

    # Only process claim-like notes (have description, skip MOCs/indexes)
    if fm.get("type") in ("moc", "hub", "enrichment"):
        return None

    changes: dict[str, str] = {}
    source_val = fm.get("source", "")

    if "source_class" not in fm:
        sc = infer_source_class(str(source_val))
        changes["source_class"] = sc

    if "verified_by" not in fm:
        changes["verified_by"] = "agent"

    if "verified_who" not in fm:
        changes["verified_who"] = "null"

    if "verified_date" not in fm:
        changes["verified_date"] = "null"

    if not changes:
        return None

    if dry_run:
        return changes

    # Build new frontmatter lines to insert before the closing ---
    new_lines: list[str] = []
    for key, val in changes.items():
        if val == "null":
            new_lines.append(f"{key}: null")
        else:
            new_lines.append(f'{key}: "{val}"')

    insert_block = "\n".join(new_lines)

    # Insert before closing --- of frontmatter
    # The frontmatter ends at match.end(), which is after the closing ---\n
    # We need to insert before the closing ---
    pre = content[: match.end()]
    post = content[match.end() :]

    # Find the closing --- in the pre section
    # Structure: ---\n{fm_text}\n---\n
    closing_idx = pre.rfind("---")
    new_content = pre[:closing_idx] + insert_block + "\n" + pre[closing_idx:] + post

    path.write_text(new_content, encoding="utf-8")
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill epistemic provenance fields")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing",
    )
    parser.add_argument(
        "--notes-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "notes",
        help="Path to notes directory",
    )
    args = parser.parse_args()

    notes_dir: Path = args.notes_dir
    if not notes_dir.is_dir():
        print(f"Notes directory not found: {notes_dir}", file=sys.stderr)
        sys.exit(1)

    updated = 0
    skipped = 0
    errors = 0

    source_class_counts: dict[str, int] = {}

    for note_path in sorted(notes_dir.glob("*.md")):
        try:
            result = backfill_note(note_path, dry_run=args.dry_run)
        except Exception as exc:
            print(f"  ERROR {note_path.name}: {exc}", file=sys.stderr)
            errors += 1
            continue

        if result is None:
            skipped += 1
            continue

        updated += 1
        sc = result.get("source_class", "?")
        source_class_counts[sc] = source_class_counts.get(sc, 0) + 1

        if args.dry_run:
            print(f"  WOULD UPDATE {note_path.name}: {result}")

    mode = "DRY RUN" if args.dry_run else "DONE"
    print(f"\n{mode}: {updated} updated, {skipped} skipped, {errors} errors")
    print(f"Source class distribution: {source_class_counts}")


if __name__ == "__main__":
    main()
