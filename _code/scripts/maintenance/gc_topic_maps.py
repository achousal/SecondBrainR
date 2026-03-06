"""Garbage-collect dead wiki links in topic map (MOC) files.

Scans all notes with type: moc for [[wiki links]], checks whether each
linked file exists on disk, and reports dead links. Does NOT auto-remove
links -- intentional forward-references are preserved until a human decides.

Usage:
    uv run python scripts/maintenance/gc_topic_maps.py [VAULT_PATH]
    uv run python scripts/maintenance/gc_topic_maps.py [VAULT_PATH] --fix
    uv run python scripts/maintenance/gc_topic_maps.py [VAULT_PATH] --json

Flags:
    --fix   Remove lines containing dead links (creates .bak before editing)
    --json  Output results as JSON (for /health integration)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent.parent  # maintenance/ -> scripts/ -> _code/
sys.path.insert(0, str(_CODE_DIR / "src"))

from engram_r.schema_validator import _build_stem_index  # noqa: E402

# Directories where wiki-link targets can resolve.
_WIKI_LINK_SEARCH_DIRS = (
    "notes",
    "_research/literature",
    "_research/hypotheses",
    "_research/experiments",
    "self",
    "projects",
    "ops/methodology",
)

_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _is_moc(path: Path) -> bool:
    """Check if a markdown file has type: moc in its frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    fm = _FM_RE.match(text)
    if not fm:
        return False
    for line in fm.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("type:"):
            val = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            return val == "moc"
    return False


def _find_mocs(vault_root: Path) -> list[Path]:
    """Find all MOC files in the vault."""
    mocs: list[Path] = []
    notes_dir = vault_root / "notes"
    if not notes_dir.is_dir():
        return mocs
    for md in notes_dir.glob("*.md"):
        if _is_moc(md):
            mocs.append(md)
    return sorted(mocs)


def _extract_links(path: Path) -> list[tuple[int, str]]:
    """Extract (line_number, link_target) pairs from a file."""
    results: list[tuple[int, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return results
    for i, line in enumerate(lines, start=1):
        for match in _WIKI_LINK_RE.finditer(line):
            results.append((i, match.group(1)))
    return results


def _link_exists(target: str, vault_root: Path, stem_index: dict[str, str]) -> bool:
    """Check if a wiki-link target resolves to an existing file."""
    # Direct check across search dirs
    for search_dir in _WIKI_LINK_SEARCH_DIRS:
        d = vault_root / search_dir
        if not d.is_dir():
            continue
        if (d / f"{target}.md").exists():
            return True

    # Fuzzy check via stem index (handles accent/case/hyphen mismatches)
    normalized = target.lower().replace(" ", "-")
    if normalized in stem_index:
        return True

    return False


def gc_topic_maps(
    vault_root: Path,
) -> dict[str, list[dict[str, str | int]]]:
    """Scan MOCs for dead links. Returns {moc_stem: [{line, target}, ...]}."""
    stem_index = _build_stem_index(vault_root)
    mocs = _find_mocs(vault_root)
    results: dict[str, list[dict[str, str | int]]] = {}

    for moc in mocs:
        links = _extract_links(moc)
        dead: list[dict[str, str | int]] = []
        for line_no, target in links:
            if not _link_exists(target, vault_root, stem_index):
                dead.append({"line": line_no, "target": target})
        if dead:
            results[moc.stem] = dead

    return results


def _fix_dead_links(
    vault_root: Path, results: dict[str, list[dict[str, str | int]]]
) -> int:
    """Remove lines containing dead links from MOC files. Returns count removed."""
    removed = 0
    for moc_stem, dead_entries in results.items():
        moc_path = vault_root / "notes" / f"{moc_stem}.md"
        if not moc_path.exists():
            continue

        dead_lines = {int(e["line"]) for e in dead_entries}
        original = moc_path.read_text(encoding="utf-8")

        # Create backup
        backup = moc_path.with_suffix(".md.bak")
        backup.write_text(original, encoding="utf-8")

        lines = original.splitlines(keepends=True)
        kept = [line for i, line in enumerate(lines, start=1) if i not in dead_lines]
        moc_path.write_text("".join(kept), encoding="utf-8")
        removed += len(dead_lines)

    return removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Garbage-collect dead wiki links in topic maps"
    )
    parser.add_argument(
        "vault_path", nargs="?", default=".", help="Path to vault root"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Remove lines with dead links (creates .bak backup)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )
    args = parser.parse_args()

    vault_root = Path(args.vault_path).resolve()
    results = gc_topic_maps(vault_root)

    if args.json_output:
        print(json.dumps(results, indent=2))
    elif not results:
        print("No dead links found in topic maps.")
    else:
        total = sum(len(v) for v in results.values())
        print(f"Dead links found: {total} across {len(results)} topic map(s)\n")
        for moc_stem, dead in results.items():
            print(f"  {moc_stem}.md:")
            for entry in dead:
                print(f"    L{entry['line']}: [[{entry['target']}]]")
        print()
        if not args.fix:
            print("Run with --fix to remove dead link lines (creates .bak backups).")

    if args.fix and results:
        removed = _fix_dead_links(vault_root, results)
        print(f"\nRemoved {removed} dead link line(s). Backups saved as .md.bak.")

    sys.exit(1 if results and not args.fix else 0)


if __name__ == "__main__":
    main()
