"""Deterministic health checks for vault notes.

Runs schema validation, wiki-link resolution, description quality,
link density, and topic-map connection checks.  Importable as a library
or invoked as a CLI:

    python -m engram_r.verify_health notes/some-claim.md --vault-root .
    python -m engram_r.verify_health --all --vault-root .
    python -m engram_r.verify_health --all --vault-root . --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from engram_r.schema_validator import (
    ValidationResult,
    detect_unicode_issues,
    detect_yaml_safety_issues,
    validate_note,
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CheckItem:
    """Single check result."""

    name: str
    status: str  # PASS | WARN | FAIL
    detail: str


@dataclass
class HealthReport:
    """Aggregated health report for one note."""

    note_path: Path
    checks: list[CheckItem] = field(default_factory=list)

    @property
    def overall(self) -> str:
        if any(c.status == "FAIL" for c in self.checks):
            return "FAIL"
        if any(c.status == "WARN" for c in self.checks):
            return "WARN"
        return "PASS"

    @property
    def failures(self) -> list[CheckItem]:
        return [c for c in self.checks if c.status == "FAIL"]

    @property
    def warnings(self) -> list[CheckItem]:
        return [c for c in self.checks if c.status == "WARN"]


# ---------------------------------------------------------------------------
# Wiki-link extraction
# ---------------------------------------------------------------------------

# Matches fenced code blocks (``` ... ```)
_FENCED_BLOCK = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)

# Matches inline code (`...`)
_INLINE_CODE = re.compile(r"`[^`]+`")

# Matches [[target]] or [[target|alias]]
_WIKI_LINK = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


def extract_wiki_links(content: str) -> list[str]:
    """Extract wiki-link targets from markdown, excluding code blocks.

    Returns targets in order of appearance.  Aliased links like
    ``[[target|alias]]`` return just the target portion.
    """
    if not content:
        return []

    # Strip fenced code blocks first, then inline code
    cleaned = _FENCED_BLOCK.sub("", content)
    cleaned = _INLINE_CODE.sub("", cleaned)

    return _WIKI_LINK.findall(cleaned)


# ---------------------------------------------------------------------------
# Link resolution
# ---------------------------------------------------------------------------


def resolve_links(
    targets: list[str],
    vault_root: Path,
    graph_dirs: list[str],
) -> list[str]:
    """Check which link targets have no corresponding .md file.

    Searches ``{vault_root}/{graph_dir}/**/{target}.md`` for each
    graph_dir.  Returns list of unresolved target names.
    """
    if not targets:
        return []

    missing: list[str] = []
    for target in targets:
        found = False
        for gdir in graph_dirs:
            search_root = vault_root / gdir
            if not search_root.is_dir():
                continue
            # Check direct child first (fast path)
            if (search_root / f"{target}.md").exists():
                found = True
                break
            # Recursive search for nested directories
            matches = list(search_root.rglob(f"{target}.md"))
            if matches:
                found = True
                break
        if not found:
            missing.append(target)
    return missing


# ---------------------------------------------------------------------------
# Description quality
# ---------------------------------------------------------------------------


def check_description_quality(
    title: str,
    description: str,
) -> list[CheckItem]:
    """Assess description quality relative to the title.

    Checks: restatement, length, trailing period, multi-sentence.
    """
    checks: list[CheckItem] = []

    if not description:
        checks.append(CheckItem("desc_present", "FAIL", "No description"))
        return checks

    # Restatement detection (case-insensitive)
    title_norm = title.strip().lower()
    desc_norm = description.strip().lower()
    if title_norm == desc_norm:
        checks.append(
            CheckItem(
                "desc_restatement",
                "FAIL",
                "Description restates the title verbatim",
            )
        )
    else:
        checks.append(
            CheckItem("desc_restatement", "PASS", "Description differs from title")
        )

    # Length checks
    desc_len = len(description.strip())
    if desc_len < 20:
        checks.append(
            CheckItem(
                "desc_length",
                "WARN",
                f"Description is short ({desc_len} chars, recommend >= 20)",
            )
        )
    elif desc_len > 200:
        checks.append(
            CheckItem(
                "desc_length",
                "WARN",
                f"Description is long ({desc_len} chars, recommend <= 200)",
            )
        )
    else:
        checks.append(
            CheckItem(
                "desc_length",
                "PASS",
                f"Description length ok ({desc_len} chars)",
            )
        )

    # Trailing period
    if description.strip().endswith("."):
        checks.append(
            CheckItem(
                "desc_trailing_period",
                "WARN",
                "Description ends with a trailing period (convention: omit)",
            )
        )

    # Multi-sentence (more than one period followed by a space or end)
    sentences = re.split(r"(?<=[.!?])\s+", description.strip())
    if len(sentences) > 1:
        checks.append(
            CheckItem(
                "desc_multi_sentence",
                "WARN",
                f"Description has {len(sentences)} sentences (recommend: 1 sentence)",
            )
        )

    return checks


# ---------------------------------------------------------------------------
# Link density
# ---------------------------------------------------------------------------


def check_link_density(
    links: list[str],
    min_links: int = 2,
) -> list[CheckItem]:
    """Check whether a note has enough wiki links.

    Args:
        links: Extracted wiki-link targets.
        min_links: Minimum recommended links (default 2).
    """
    unique = set(links)
    count = len(unique)
    if count < min_links:
        return [
            CheckItem(
                "link_density",
                "WARN",
                f"Only {count} unique wiki link(s), recommend >= {min_links}",
            )
        ]
    return [
        CheckItem(
            "link_density",
            "PASS",
            f"{count} unique wiki links",
        )
    ]


# ---------------------------------------------------------------------------
# Topics section
# ---------------------------------------------------------------------------


_TOPICS_HEADER = re.compile(r"^Topics:\s*$", re.MULTILINE)


def extract_topics_section(content: str) -> list[str]:
    """Parse the Topics footer for wiki-link references.

    Looks for a ``Topics:`` header and extracts ``[[target]]`` from
    subsequent list items.
    """
    match = _TOPICS_HEADER.search(content)
    if not match:
        return []

    # Everything after "Topics:" header
    after = content[match.end() :]
    topics: list[str] = []
    for line in after.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Stop at next section header or horizontal rule
        if stripped.startswith("#") or stripped == "---":
            break
        link_match = _WIKI_LINK.search(stripped)
        if link_match:
            topics.append(link_match.group(1))
    return topics


# ---------------------------------------------------------------------------
# Topic map connection
# ---------------------------------------------------------------------------


def check_topic_map_connection(
    note_title: str,
    topics_refs: list[str],
    vault_root: Path,
) -> list[CheckItem]:
    """Verify topic map references exist and point to real files.

    Args:
        note_title: The title of the note being checked.
        topics_refs: Wiki-link targets from the Topics section.
        vault_root: Root of the vault.
    """
    checks: list[CheckItem] = []

    if not topics_refs:
        checks.append(
            CheckItem(
                "topic_connection",
                "WARN",
                "No Topics section found -- claim should reference"
                " at least one topic map",
            )
        )
        return checks

    for ref in topics_refs:
        # Search for the topic map file anywhere in the vault
        matches = list(vault_root.rglob(f"{ref}.md"))
        if matches:
            checks.append(
                CheckItem(
                    "topic_file_exists",
                    "PASS",
                    f"Topic map '{ref}' exists",
                )
            )
        else:
            checks.append(
                CheckItem(
                    "topic_file_exists",
                    "WARN",
                    f"Topic map '{ref}' not found in vault",
                )
            )

    return checks


# ---------------------------------------------------------------------------
# Orchestrator -- single note
# ---------------------------------------------------------------------------

# Frontmatter regex (shared with schema_validator)
_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def verify_note_health(
    note_path: Path,
    vault_root: Path,
    graph_dirs: list[str],
) -> HealthReport:
    """Run all deterministic health checks on a single note.

    Permissive-first: files without frontmatter or with unknown types
    pass silently.
    """
    checks: list[CheckItem] = []

    if not note_path.exists():
        checks.append(CheckItem("file_exists", "FAIL", "File does not exist"))
        return HealthReport(note_path=note_path, checks=checks)

    content = note_path.read_text(encoding="utf-8")

    if not content.strip():
        # Empty file -- pass silently (permissive)
        return HealthReport(note_path=note_path, checks=checks)

    # --- Schema validation (from schema_validator) ---
    schema_result: ValidationResult = validate_note(content)
    if not schema_result.valid:
        for err in schema_result.errors:
            checks.append(CheckItem("schema", "FAIL", err))
    else:
        checks.append(CheckItem("schema", "PASS", "Schema valid"))

    # --- YAML safety ---
    yaml_issues = detect_yaml_safety_issues(content)
    for issue in yaml_issues:
        checks.append(CheckItem("yaml_safety", "WARN", issue))

    unicode_issues = detect_unicode_issues(content)
    for issue in unicode_issues:
        checks.append(CheckItem("unicode", "WARN", issue))

    # --- Parse frontmatter for description ---
    fm_match = _FM_PATTERN.match(content)
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            frontmatter = None

        if isinstance(frontmatter, dict):
            desc = frontmatter.get("description", "")
            if desc and isinstance(desc, str):
                title = note_path.stem
                checks.extend(check_description_quality(title, desc))
    else:
        # No frontmatter -- permissive pass
        return HealthReport(note_path=note_path, checks=checks)

    # --- Unresolved terms ---
    if isinstance(frontmatter, dict):
        unresolved = frontmatter.get("unresolved_terms")
        if isinstance(unresolved, list) and unresolved:
            terms_str = ", ".join(str(t) for t in unresolved)
            checks.append(
                CheckItem(
                    "unresolved_terms",
                    "WARN",
                    f"Unresolved acronyms/abbreviations: {terms_str} "
                    f"-- confirm meaning and clear field",
                )
            )

    # --- Wiki links ---
    links = extract_wiki_links(content)
    checks.extend(check_link_density(links))

    # Resolve links
    missing = resolve_links(links, vault_root, graph_dirs)
    if missing:
        for m in missing:
            checks.append(
                CheckItem(
                    "link_resolution",
                    "FAIL",
                    f"Dangling link: [[{m}]] -- missing target file",
                )
            )
    else:
        checks.append(CheckItem("link_resolution", "PASS", "All links resolve"))

    # --- Topics section ---
    topics = extract_topics_section(content)
    checks.extend(check_topic_map_connection(note_path.stem, topics, vault_root))

    return HealthReport(note_path=note_path, checks=checks)


# ---------------------------------------------------------------------------
# Batch verification
# ---------------------------------------------------------------------------


def verify_batch(
    vault_root: Path,
    graph_dirs: list[str],
    target_dirs: list[str] | None = None,
) -> list[HealthReport]:
    """Run health checks on all .md files in target directories.

    Args:
        vault_root: Root of the vault.
        graph_dirs: Directories used for link resolution.
        target_dirs: Directories to scan for notes. Defaults to graph_dirs.
    """
    if target_dirs is None:
        target_dirs = graph_dirs

    reports: list[HealthReport] = []
    for tdir in target_dirs:
        dir_path = vault_root / tdir
        if not dir_path.is_dir():
            continue
        for md_file in sorted(dir_path.rglob("*.md")):
            report = verify_note_health(md_file, vault_root, graph_dirs)
            reports.append(report)
    return reports


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_DEFAULT_HEALTH_CONFIG: dict = {
    "graph_directories": ["notes", "_research", "self", "projects"],
    "exclude_directories": ["ops", ".claude", "_code/templates"],
}


def load_health_config(vault_root: Path) -> dict:
    """Read health config from ops/config.yaml.

    Falls back to defaults if the file or health section is missing.
    """
    config_path = vault_root / "ops" / "config.yaml"
    if not config_path.exists():
        return dict(_DEFAULT_HEALTH_CONFIG)

    try:
        with open(config_path, encoding="utf-8") as f:
            full_config = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return dict(_DEFAULT_HEALTH_CONFIG)

    health = full_config.get("health")
    if not isinstance(health, dict):
        return dict(_DEFAULT_HEALTH_CONFIG)

    return {
        "graph_directories": health.get(
            "graph_directories",
            _DEFAULT_HEALTH_CONFIG["graph_directories"],
        ),
        "exclude_directories": health.get(
            "exclude_directories",
            _DEFAULT_HEALTH_CONFIG["exclude_directories"],
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_report(report: HealthReport, use_json: bool = False) -> str:
    """Format a single report for display."""
    if use_json:
        return json.dumps(
            {
                "note": str(report.note_path),
                "overall": report.overall,
                "checks": [
                    {"name": c.name, "status": c.status, "detail": c.detail}
                    for c in report.checks
                ],
            },
            indent=2,
        )

    lines: list[str] = []
    lines.append(f"  {report.overall}  {report.note_path}")
    for c in report.checks:
        if c.status != "PASS":
            lines.append(f"    {c.status:>4}  {c.name}: {c.detail}")
    return "\n".join(lines)


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="engram_r.verify_health",
        description="Deterministic health checks for vault notes",
    )
    parser.add_argument(
        "note",
        nargs="?",
        help="Path to a specific note to verify",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Verify all notes in target directories",
    )
    parser.add_argument(
        "--vault-root",
        default=".",
        help="Vault root directory (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="use_json",
        help="Output results as JSON",
    )

    args = parser.parse_args()
    vault_root = Path(args.vault_root).resolve()

    config = load_health_config(vault_root)
    graph_dirs = config["graph_directories"]

    if args.all:
        reports = verify_batch(vault_root, graph_dirs)
        if not reports:
            print("No notes found.")
            return

        fail_count = sum(1 for r in reports if r.overall == "FAIL")
        warn_count = sum(1 for r in reports if r.overall == "WARN")
        pass_count = sum(1 for r in reports if r.overall == "PASS")

        if args.use_json:
            all_json = []
            for r in reports:
                all_json.append(
                    {
                        "note": str(r.note_path),
                        "overall": r.overall,
                        "checks": [
                            {"name": c.name, "status": c.status, "detail": c.detail}
                            for c in r.checks
                        ],
                    }
                )
            print(json.dumps(all_json, indent=2))
        else:
            for r in reports:
                print(_format_report(r))

            print(f"\nSummary: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL")

        if fail_count > 0:
            sys.exit(1)

    elif args.note:
        note_path = Path(args.note)
        if not note_path.is_absolute():
            note_path = vault_root / note_path
        report = verify_note_health(note_path, vault_root, graph_dirs)
        print(_format_report(report, use_json=args.use_json))
        if report.overall == "FAIL":
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
