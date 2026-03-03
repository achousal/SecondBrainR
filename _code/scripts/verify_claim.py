"""Mark claims as human-verified with verifier identity and timestamp.

Sets verified_by: human, verified_who: <full name>, verified_date: <today>
on one or more claim notes.

Usage:
  uv run python scripts/verify_claim.py --who "Your Name" FILE
  uv run python scripts/verify_claim.py --who "Your Name" \
    --batch "source_class=hypothesis,confidence=speculative"
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def verify_note(path: Path, who: str, date_str: str) -> bool:
    """Set verified_by, verified_who, verified_date on a claim note.

    Returns True if the note was modified, False if skipped.
    """
    content = path.read_text(encoding="utf-8")
    match = _FM_PATTERN.match(content)
    if not match:
        return False

    fm_text = match.group(1)
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return False

    if not isinstance(fm, dict):
        return False

    # Update fields
    fm["verified_by"] = "human"
    fm["verified_who"] = who
    fm["verified_date"] = date_str

    # Rebuild the full content with updated frontmatter
    body = content[match.end() :]
    new_fm = yaml.dump(
        fm, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    new_content = f"---\n{new_fm}---\n{body}"

    path.write_text(new_content, encoding="utf-8")
    return True


def find_batch_claims(notes_dir: Path, filters: dict[str, str]) -> list[Path]:
    """Find claims matching filter criteria."""
    results: list[Path] = []

    for note_path in sorted(notes_dir.glob("*.md")):
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError:
            continue

        match = _FM_PATTERN.match(content)
        if not match:
            continue

        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue

        if not isinstance(fm, dict):
            continue

        # Check all filters match
        if all(fm.get(k) == v for k, v in filters.items()):
            results.append(note_path)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark claims as human-verified")
    parser.add_argument(
        "--who",
        required=True,
        help="Full name of the verifier (e.g., 'Your Name')",
    )
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Verification date (default: today, YYYY-MM-DD)",
    )
    parser.add_argument(
        "--batch",
        help="Comma-separated key=value filters "
        "(e.g., 'source_class=hypothesis,confidence=speculative')",
    )
    parser.add_argument(
        "--notes-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "notes",
        help="Path to notes directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be verified without writing",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Specific note files to verify",
    )
    args = parser.parse_args()

    targets: list[Path] = []

    if args.batch:
        # Parse filters
        filters: dict[str, str] = {}
        for pair in args.batch.split(","):
            k, v = pair.strip().split("=", 1)
            filters[k.strip()] = v.strip()
        targets = find_batch_claims(args.notes_dir, filters)
        print(f"Batch filter matched {len(targets)} claims")
    elif args.files:
        targets = [Path(f) for f in args.files if Path(f).exists()]
    else:
        print("Provide either --batch filters or specific file paths", file=sys.stderr)
        sys.exit(1)

    if not targets:
        print("No matching claims found")
        sys.exit(0)

    verified = 0
    for path in targets:
        if args.dry_run:
            print(f"  WOULD VERIFY: {path.name}")
            verified += 1
            continue

        if verify_note(path, args.who, args.date):
            print(f"  VERIFIED: {path.name}")
            verified += 1
        else:
            print(f"  SKIPPED (no frontmatter): {path.name}")

    mode = "DRY RUN" if args.dry_run else "DONE"
    print(f"\n{mode}: {verified} claims verified by {args.who} on {args.date}")


if __name__ == "__main__":
    main()
