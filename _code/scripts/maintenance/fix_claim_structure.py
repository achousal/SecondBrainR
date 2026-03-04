"""Bulk retroactive fix for claim structural compliance issues.

CLI flags:
    --strip-title-echo   Remove '# heading' first body line from notes/
    --fix-links          Auto-fix accent and space-hyphen wiki-link mismatches
    --fix-headers        Convert '## Source' / '## Relevant Notes' to plain text
    --add-topics         Add stub Topics footer to files missing it
    --dry-run            Show what would change without modifying files

Usage:
    uv run python scripts/fix_claim_structure.py --dry-run --strip-title-echo
    uv run python scripts/fix_claim_structure.py --strip-title-echo --fix-links
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

# Add src to path
_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_CODE_DIR / "src"))

from engram_r.schema_validator import (  # noqa: E402
    _build_stem_index,
    _FM_PATTERN,
    _strip_accents,
    _WIKI_LINK_CONTENT_RE,
    normalize_text,
)

# Default vault root (two levels up from _code/scripts/)
_DEFAULT_VAULT = _CODE_DIR.parent


def _get_notes_files(vault_root: Path) -> list[Path]:
    """Return all .md files in notes/."""
    notes_dir = vault_root / "notes"
    if not notes_dir.is_dir():
        return []
    return sorted(notes_dir.glob("*.md"))


def _split_fm_body(content: str) -> tuple[str, str] | None:
    """Split content into frontmatter block and body. Returns None if no FM."""
    m = _FM_PATTERN.match(content)
    if not m:
        return None
    fm_block = content[: m.end()]
    body = content[m.end() :]
    return fm_block, body


def strip_title_echo(vault_root: Path, dry_run: bool) -> int:
    """Remove '# heading' first body line from notes/ files."""
    count = 0
    for f in _get_notes_files(vault_root):
        content = f.read_text(encoding="utf-8")
        parts = _split_fm_body(content)
        if parts is None:
            continue
        fm_block, body = parts

        lines = body.split("\n")
        # Find first non-blank line
        first_idx = None
        for i, line in enumerate(lines):
            if line.strip():
                first_idx = i
                break
        if first_idx is None:
            continue
        if not lines[first_idx].strip().startswith("# "):
            continue

        # Remove the heading line (and one trailing blank if present)
        del lines[first_idx]
        if first_idx < len(lines) and not lines[first_idx].strip():
            del lines[first_idx]

        new_content = fm_block + "\n".join(lines)
        count += 1
        if dry_run:
            print(f"  [strip-title-echo] {f.name}")
        else:
            f.write_text(new_content, encoding="utf-8")
    return count


def fix_links(vault_root: Path, dry_run: bool) -> int:
    """Auto-fix accent and space-hyphen wiki-link mismatches."""
    stem_index = _build_stem_index(vault_root)
    count = 0

    for f in _get_notes_files(vault_root):
        content = f.read_text(encoding="utf-8")
        new_content = content

        for m in _WIKI_LINK_CONTENT_RE.finditer(content):
            target = m.group(1).strip()
            nfc_target = normalize_text(target)
            lower = nfc_target.lower()

            # Already resolvable
            if lower in stem_index:
                continue

            # Try variants
            resolved = None
            for variant in [
                _strip_accents(lower),
                lower.replace(" ", "-"),
                _strip_accents(lower.replace(" ", "-")),
                lower.replace("-", " "),
            ]:
                if variant in stem_index:
                    resolved = stem_index[variant]
                    break

            if resolved and resolved != target:
                old_link = f"[[{target}"
                new_link = f"[[{resolved}"
                new_content = new_content.replace(old_link, new_link, 1)
                count += 1
                if dry_run:
                    print(f"  [fix-link] {f.name}: [[{target}]] -> [[{resolved}]]")

        if not dry_run and new_content != content:
            f.write_text(new_content, encoding="utf-8")
    return count


def fix_headers(vault_root: Path, dry_run: bool) -> int:
    """Convert '## Source' / '## Relevant Notes' to plain text in non-tension claims."""
    count = 0
    replacements = {
        "## Source": "Source:",
        "## Relevant Notes": "Relevant Notes:",
    }

    for f in _get_notes_files(vault_root):
        content = f.read_text(encoding="utf-8")
        # Skip tensions
        m = _FM_PATTERN.match(content)
        if m:
            try:
                import yaml

                fm = yaml.safe_load(m.group(1))
                if isinstance(fm, dict) and fm.get("type") == "tension":
                    continue
            except Exception:
                pass

        new_content = content
        for old, new in replacements.items():
            if old in new_content:
                new_content = new_content.replace(old, new)
                count += 1
                if dry_run:
                    print(f"  [fix-header] {f.name}: '{old}' -> '{new}'")

        if not dry_run and new_content != content:
            f.write_text(new_content, encoding="utf-8")
    return count


def add_topics(vault_root: Path, dry_run: bool) -> int:
    """Add stub Topics footer to files missing it."""
    count = 0
    for f in _get_notes_files(vault_root):
        content = f.read_text(encoding="utf-8")
        parts = _split_fm_body(content)
        if parts is None:
            continue

        # Skip if Topics: already present
        if "Topics:" in parts[1]:
            continue

        # Skip navigation types
        m = _FM_PATTERN.match(content)
        if m:
            try:
                import yaml

                fm = yaml.safe_load(m.group(1))
                if isinstance(fm, dict) and fm.get("type") in {
                    "moc",
                    "hub",
                    "index",
                    "topic-map",
                    "tension",
                }:
                    continue
            except Exception:
                pass

        count += 1
        if dry_run:
            print(f"  [add-topics] {f.name}")
        else:
            # Append Topics stub
            new_content = content.rstrip("\n") + "\n\nTopics:\n"
            f.write_text(new_content, encoding="utf-8")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk fix structural compliance issues in notes/ claims."
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=_DEFAULT_VAULT,
        help="Vault root directory (default: auto-detect).",
    )
    parser.add_argument(
        "--strip-title-echo",
        action="store_true",
        help="Remove '# heading' first body line.",
    )
    parser.add_argument(
        "--fix-links",
        action="store_true",
        help="Auto-fix accent and space-hyphen wiki-link mismatches.",
    )
    parser.add_argument(
        "--fix-headers",
        action="store_true",
        help="Convert ## Source / ## Relevant Notes to plain text.",
    )
    parser.add_argument(
        "--add-topics",
        action="store_true",
        help="Add stub Topics footer to files missing it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files.",
    )
    args = parser.parse_args()

    if not any([args.strip_title_echo, args.fix_links, args.fix_headers, args.add_topics]):
        parser.error("At least one fix flag is required.")

    vault = args.vault.resolve()
    mode = "DRY RUN" if args.dry_run else "APPLY"
    print(f"[{mode}] Vault: {vault}")

    total = 0
    if args.strip_title_echo:
        n = strip_title_echo(vault, args.dry_run)
        print(f"  strip-title-echo: {n} files")
        total += n

    if args.fix_links:
        n = fix_links(vault, args.dry_run)
        print(f"  fix-links: {n} links")
        total += n

    if args.fix_headers:
        n = fix_headers(vault, args.dry_run)
        print(f"  fix-headers: {n} replacements")
        total += n

    if args.add_topics:
        n = add_topics(vault, args.dry_run)
        print(f"  add-topics: {n} files")
        total += n

    print(f"Total changes: {total}")


if __name__ == "__main__":
    main()
