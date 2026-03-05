"""Validate Obsidian note frontmatter against known schemas.

Schemas are derived from the canonical builders in ``note_builder.py``.
Unknown note types or files without frontmatter pass silently (permissive).

Also provides the canonical boundary-layer functions for transforming
external representations (titles, YAML values, filenames) into safe
internal forms. All sanitization should flow through this module.
"""

from __future__ import annotations

import html
import html.parser
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# Characters that break filesystems when used in filenames.
# / is a directory separator on POSIX; \ on Windows; others break shells.
_UNSAFE_FILENAME_CHARS = r'/\:*?"<>|'

# Superset: title-unsafe chars per CLAUDE.md rules.  Includes the
# filesystem-unsafe set PLUS chars that are legal on disk but violate
# vault title conventions: . + [ ] ( ) { } ^
_UNSAFE_TITLE_CHARS = _UNSAFE_FILENAME_CHARS + r".+[](){}^"

# Pre-compiled pattern for consecutive hyphens (used after char replacement).
_MULTI_HYPHEN = re.compile(r"-{2,}")

# Pattern detecting an unquoted YAML value that contains a colon followed by
# a space (the YAML mapping indicator).  Applied line-by-line to raw
# frontmatter text *before* parsing, since these cause silent misparsing
# rather than errors.
# Matches lines like:  key: value: more stuff
# Does NOT match:      key: "value: more stuff"  (properly quoted)
_UNQUOTED_COLON = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*:\s+"  # key: <space>
    r"(?![\"'])"  # value does NOT start with a quote
    r"[^\n]*?:\s",  # value contains another colon-space
)

# Pattern detecting an unquoted value starting with # (YAML comment risk).
_UNQUOTED_HASH = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*:\s+"  # key: <space>
    r"(?![\"'])"  # value does NOT start with a quote
    r"#",  # value starts with hash
)


# ---------------------------------------------------------------------------
# Normalization primitives
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Apply NFC Unicode normalization to *text*.

    Single source of truth for Unicode normalization across the vault.
    All text that will become a filename, frontmatter value, or wiki-link
    target should pass through this function.

    >>> normalize_text("cafe\u0301") == "caf\u00e9"
    True
    """
    return unicodedata.normalize("NFC", text)


class _HTMLStripper(html.parser.HTMLParser):
    """Accumulates text content, discarding all tags and comments."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:  # noqa: D102
        self._parts.append(data)

    def handle_comment(self, data: str) -> None:  # noqa: D102
        pass  # discard HTML comments

    def get_text(self) -> str:
        return "".join(self._parts)


def strip_html(text: str) -> str:
    """Remove all HTML tags and unescape entities.

    Short-circuits when ``<`` is absent (common case for clean text).
    Uses only stdlib ``html.parser`` -- no external dependency.

    >>> strip_html("<b>bold</b>")
    'bold'
    >>> strip_html("no tags here")
    'no tags here'
    >>> strip_html("<script>alert('xss')</script>safe")
    "alert('xss')safe"
    >>> strip_html("&amp; &lt; &gt;")
    '& < >'
    """
    if not text or "<" not in text:
        return html.unescape(text) if text and "&" in text else text

    stripper = _HTMLStripper()
    stripper.feed(text)
    return html.unescape(stripper.get_text())


# ---------------------------------------------------------------------------
# Title and filename sanitization
# ---------------------------------------------------------------------------


def sanitize_title(title: str) -> str:
    """Replace filesystem-unsafe characters in a note title with hyphens.

    Applies NFC normalization, replaces characters that violate CLAUDE.md
    title rules (``/ \\ : * ? " < > | . + [ ] ( ) { } ^``), collapses
    consecutive hyphens, and strips leading/trailing hyphens.

    >>> sanitize_title("APP/PS1 mice")
    'APP-PS1 mice'
    >>> sanitize_title("AhR/NF-kappaB/NLRP3")
    'AhR-NF-kappaB-NLRP3'
    >>> sanitize_title("ratio (DCA:CA)")
    'ratio -DCA-CA'
    """
    title = normalize_text(title)
    for ch in _UNSAFE_TITLE_CHARS:
        title = title.replace(ch, "-")
    title = _MULTI_HYPHEN.sub("-", title)
    title = title.strip("-")
    return title


def validate_filename(file_path: str) -> list[str]:
    """Check a file path for unsafe characters in the filename component.

    Returns a list of error strings (empty if valid).  Also flags
    non-NFC Unicode in the filename.
    """
    errors: list[str] = []
    # Extract just the filename (last component)
    last_sep = file_path.replace("\\", "/").rfind("/")
    filename = file_path[last_sep + 1 :] if last_sep >= 0 else file_path

    # Check NFC normalization
    if filename != unicodedata.normalize("NFC", filename):
        errors.append(
            f"Filename contains non-NFC Unicode: {filename}. "
            f"Use normalize_text() to normalize before writing."
        )

    for ch in _UNSAFE_FILENAME_CHARS:
        if ch in ("/", "\\"):
            # These can't appear in the filename component extracted above
            continue
        if ch in filename:
            errors.append(
                f"Filename contains unsafe character '{ch}': {filename}. "
                f"Use sanitize_title() to replace with '-'."
            )
    return errors


# Reuse the frontmatter regex from hypothesis_parser.py
_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Content safety detectors (pre-parse)
# ---------------------------------------------------------------------------


def detect_yaml_safety_issues(content: str) -> list[str]:
    """Scan raw frontmatter text for unquoted colons and hashes.

    These cause silent misparsing rather than YAML errors, making them
    harder to catch after the fact.  Run this on raw content *before*
    ``yaml.safe_load()``.

    Args:
        content: Full note content (with ``---`` delimiters).

    Returns:
        List of human-readable issue descriptions (empty if clean).
    """
    fm_match = _FM_PATTERN.match(content)
    if not fm_match:
        return []

    issues: list[str] = []
    fm_text = fm_match.group(1)
    for lineno, line in enumerate(fm_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _UNQUOTED_COLON.match(stripped):
            issues.append(
                f"Line {lineno}: unquoted value contains ':' -- "
                f"FIX: WRAP THE VALUE IN DOUBLE QUOTES. "
                f"Example: description: \"your text here\". "
                f"Line: {stripped}"
            )
        if _UNQUOTED_HASH.match(stripped):
            issues.append(
                f"Line {lineno}: unquoted value starts with '#' -- "
                f"wrap the value in double quotes. Line: {stripped}"
            )
    return issues


def detect_unicode_issues(content: str) -> list[str]:
    """Detect non-NFC Unicode in frontmatter values.

    Args:
        content: Full note content (with ``---`` delimiters).

    Returns:
        List of human-readable issue descriptions (empty if clean).
    """
    fm_match = _FM_PATTERN.match(content)
    if not fm_match:
        return []

    issues: list[str] = []
    fm_text = fm_match.group(1)
    if fm_text != unicodedata.normalize("NFC", fm_text):
        issues.append(
            "Frontmatter contains non-NFC Unicode characters. "
            "Normalize text with normalize_text() before writing."
        )
    return issues


# ---------------------------------------------------------------------------
# Schema definitions -- required fields per note type
# ---------------------------------------------------------------------------
# Each entry maps a note ``type`` value to its list of required frontmatter
# field names.  Derived from ``note_builder.py`` builder function signatures
# and the frontmatter dicts they produce.

_SCHEMAS: dict[str, list[str]] = {
    "hypothesis": [
        "title",
        "id",
        "status",
        "elo",
        "created",
        "updated",
    ],
    "literature": [
        "title",
        "description",
        "status",
        "created",
    ],
    "experiment": [
        "title",
        "status",
        "created",
    ],
    "eda-report": [
        "title",
        "dataset",
        "created",
    ],
    "research-goal": [
        "title",
        "description",
        "status",
        "created",
    ],
    "tournament-match": [
        "date",
        "research_goal",
        "hypothesis_a",
        "hypothesis_b",
    ],
    "meta-review": [
        "date",
        "research_goal",
    ],
    "project": [
        "title",
        "description",
        "project_tag",
        "lab",
        "status",
        "project_path",
        "created",
        "updated",
    ],
    "lab": [
        "lab_slug",
        "pi",
        "created",
        "updated",
    ],
    "institution": [
        "name",
        "slug",
        "created",
        "updated",
    ],
    "foreign-hypothesis": [
        "title",
        "id",
        "status",
        "elo_federated",
        "elo_source",
        "matches_federated",
        "matches_source",
        "source_vault",
        "imported",
    ],
    "claim": ["description", "verified_by", "source_class", "confidence"],
    "evidence": ["description", "verified_by", "source_class", "confidence"],
    "methodology": ["description"],
    "contradiction": ["description"],
    "pattern": ["description"],
    "question": ["description"],
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of validating a note against its schema."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_note(
    content: str,
    note_type: str | None = None,
) -> ValidationResult:
    """Validate a note's frontmatter against known schemas.

    Args:
        content: Raw markdown content (may or may not have frontmatter).
        note_type: Override the ``type`` field from frontmatter.  When
            provided, the note is validated against this type's schema
            regardless of what ``type`` says in the frontmatter.

    Returns:
        A ``ValidationResult``.  ``valid=True`` when:
        - the content has no YAML frontmatter (not a structured note),
        - the frontmatter has no ``type`` field and no *note_type* override,
        - the type is not in the known schema registry.

        ``valid=False`` only when a known-type note is missing required
        fields defined in the schema.
    """
    if not content or not content.strip():
        return ValidationResult(valid=True)

    match = _FM_PATTERN.match(content)
    if not match:
        return ValidationResult(valid=True)

    fm_text = match.group(1)
    try:
        frontmatter = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return ValidationResult(valid=False, errors=["Invalid YAML frontmatter"])

    if not isinstance(frontmatter, dict):
        return ValidationResult(valid=True)

    effective_type = note_type or frontmatter.get("type")
    if effective_type is None:
        return ValidationResult(valid=True)

    schema = _SCHEMAS.get(effective_type)
    if schema is None:
        # Unknown type -- pass permissively
        return ValidationResult(valid=True)

    errors: list[str] = []
    for field_name in schema:
        if field_name not in frontmatter:
            errors.append(f"Missing required field: {field_name}")

    if errors:
        return ValidationResult(valid=False, errors=errors)

    return ValidationResult(valid=True)


# Types exempt from source-field warnings (navigation hubs, not claims).
_SOURCE_EXEMPT_TYPES = frozenset({"moc", "index", "hub", "topic-map"})

# Claim-family types that SHOULD have a source field.
_CLAIM_FAMILY_TYPES = frozenset(
    {"claim", "evidence", "methodology", "question", "contradiction", "pattern"}
)


def check_queue_provenance(
    claim_title: str,
    queue_dir: Path,
) -> ValidationResult:
    """Verify that a claim being written to notes/ has a queue task file.

    Checks that at least one task file in *queue_dir* references the claim
    title in its ``claim:`` frontmatter field.  This prevents pipeline
    bypass where a reduce subagent writes directly to notes/ instead of
    creating a task file first.

    Args:
        claim_title: The claim title (filename stem without .md).
        queue_dir: Path to ``ops/queue/`` directory.

    Returns:
        A ``ValidationResult``.  ``valid=True`` when a matching task file
        exists or the queue directory is absent (pre-init vaults).
    """
    if not queue_dir.is_dir():
        # Pre-init vault or queue not yet created -- skip check.
        return ValidationResult(valid=True)

    # Normalize for comparison: apply sanitize_title to both sides so that
    # filesystem-safe transformations (e.g. "0.94" -> "0-94") don't cause
    # mismatches between the queue task claim field and the note filename.
    normalized_title = sanitize_title(claim_title).strip().lower()

    for task_file in queue_dir.glob("*.md"):
        try:
            text = task_file.read_text(encoding="utf-8")
        except Exception:
            continue

        fm_match = _FM_PATTERN.match(text)
        if not fm_match:
            continue

        try:
            fm = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            continue

        if not isinstance(fm, dict):
            continue

        task_claim = fm.get("claim", "")
        if (
            isinstance(task_claim, str)
            and sanitize_title(task_claim).strip().lower() == normalized_title
        ):
            return ValidationResult(valid=True)

    return ValidationResult(
        valid=False,
        errors=[
            f"No queue task file found for claim '{claim_title}'. "
            f"Claims must route through the pipeline: "
            f"inbox/ -> /reduce (creates task file in ops/queue/) -> "
            f"create phase (writes to notes/). "
            f"Direct writes to notes/ are a pipeline compliance violation."
        ],
    )


def check_notes_provenance(content: str) -> ValidationResult:
    """Check that a notes/ file has required provenance fields.

    Enforces:
    - BLOCK (error) if no frontmatter at all.
    - BLOCK (error) if ``description`` is missing or empty.
    - WARN if ``source`` is missing and the note type is in the claim family
      (or type is absent, which defaults to claim-family behavior).
      MOC/navigation types are exempt from the source warning.

    Args:
        content: Raw markdown content of the note.

    Returns:
        A ``ValidationResult`` with errors (blocking) and warnings (advisory).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not content or not content.strip():
        return ValidationResult(valid=False, errors=["Empty file content"])

    match = _FM_PATTERN.match(content)
    if not match:
        return ValidationResult(
            valid=False, errors=["No YAML frontmatter found in notes/ file"]
        )

    fm_text = match.group(1)
    try:
        frontmatter = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return ValidationResult(valid=False, errors=["Invalid YAML frontmatter"])

    if not isinstance(frontmatter, dict):
        return ValidationResult(
            valid=False, errors=["Frontmatter is not a YAML mapping"]
        )

    # description is required for all notes/ files
    desc = frontmatter.get("description")
    if desc is None:
        errors.append("Missing required field: description")
    elif not str(desc).strip():
        errors.append("Empty description field")

    # source warning for claim-family types
    note_type = frontmatter.get("type", "")
    source = frontmatter.get("source")

    if (
        note_type not in _SOURCE_EXEMPT_TYPES
        and (note_type in _CLAIM_FAMILY_TYPES or not note_type)
        and not source
    ):
        warnings.append(
            "Missing 'source' field -- notes/ claims should trace to a source"
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Structural compliance checks (B1-B4)
# ---------------------------------------------------------------------------

# Regex to extract wiki-link targets from body text: [[target]] or [[target|alias]]
_WIKI_LINK_CONTENT_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Note types exempt from header and topics-footer checks (navigation hubs).
_HEADER_EXEMPT_TYPES = frozenset({"tension", "moc", "hub", "index", "topic-map"})

# Directories searched for wiki-link resolution.
_WIKI_LINK_SEARCH_DIRS = (
    "notes",
    "_research/literature",
    "_research/hypotheses",
    "_research/experiments",
    "self",
    "projects",
    "ops/methodology",
)


def _strip_accents(s: str) -> str:
    """NFD decompose and strip combining marks, then NFC normalize remainder.

    >>> _strip_accents("caf\u00e9") == "cafe"
    True
    """
    nfd = unicodedata.normalize("NFD", s)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def _build_stem_index(vault_root: Path) -> dict[str, str]:
    """Map normalized filename stems to actual stems for link resolution.

    Returns a dict where keys are lowercased, accent-stripped, space-to-hyphen
    normalized stems, and values are the original filename stems.  This enables
    fuzzy matching for common mismatches.
    """
    index: dict[str, str] = {}
    for search_dir in _WIKI_LINK_SEARCH_DIRS:
        d = vault_root / search_dir
        if not d.is_dir():
            continue
        for md_file in d.glob("*.md"):
            stem = md_file.stem
            # Index under multiple normalized forms
            lower = stem.lower()
            index[lower] = stem
            # Accent-stripped
            accent_stripped = _strip_accents(lower)
            if accent_stripped != lower:
                index[accent_stripped] = stem
            # Space-to-hyphen variant
            hyphenated = lower.replace(" ", "-")
            if hyphenated != lower:
                index[hyphenated] = stem
            # Accent-stripped + hyphenated
            combo = _strip_accents(hyphenated)
            if combo not in index:
                index[combo] = stem
    return index


def _get_body(content: str) -> str:
    """Extract body text after frontmatter."""
    fm_match = _FM_PATTERN.match(content)
    if fm_match:
        return content[fm_match.end():]
    return content


def _get_fm_type(content: str) -> str | None:
    """Extract the type field from frontmatter, or None."""
    fm_match = _FM_PATTERN.match(content)
    if not fm_match:
        return None
    try:
        fm = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError:
        return None
    if isinstance(fm, dict):
        return fm.get("type")
    return None


def check_title_echo(content: str) -> ValidationResult:
    """B1: BLOCK if the first non-blank body line starts with ``# ``.

    Claim notes should not echo their title as an H1 heading -- the title
    lives in the filename.

    Args:
        content: Full note content (with frontmatter).

    Returns:
        ValidationResult with error if title echo found.
    """
    body = _get_body(content)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            return ValidationResult(
                valid=False,
                errors=[
                    "Title echo: body starts with '# ' heading. "
                    "The title lives in the filename -- begin directly "
                    "with the argument body (no heading)."
                ],
            )
        # First non-blank line is not a heading -- pass
        return ValidationResult(valid=True)

    # Body is all blank lines -- pass
    return ValidationResult(valid=True)


def check_nonstandard_headers(content: str) -> ValidationResult:
    """B2: WARN if body contains ``## `` section headings.

    Claim notes should use prose structure, not section headings.
    Tension, moc, hub, index, and topic-map types are exempt.

    Args:
        content: Full note content (with frontmatter).

    Returns:
        ValidationResult with warning if non-standard headers found.
    """
    note_type = _get_fm_type(content)
    if note_type in _HEADER_EXEMPT_TYPES:
        return ValidationResult(valid=True)

    body = _get_body(content)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            return ValidationResult(
                valid=True,
                warnings=[
                    f"Non-standard section heading in claim body: '{stripped}'. "
                    f"Prefer prose structure with plain-text footer labels "
                    f"(Source:, Relevant Notes:, Topics:) instead of ## headings."
                ],
            )

    return ValidationResult(valid=True)


def check_wiki_link_targets(
    content: str,
    vault_root: Path,
) -> ValidationResult:
    """B3: BLOCK if any ``[[target]]`` in body or source: FM is unresolvable.

    Searches notes/, _research/literature/, _research/hypotheses/,
    _research/experiments/, self/, projects/, and ops/methodology/ for matching
    filenames.  Tries NFC, accent-stripped, and space-to-hyphen variants before
    failing.

    Args:
        content: Full note content (with frontmatter).
        vault_root: Path to vault root directory.

    Returns:
        ValidationResult with errors for each unresolvable link.
    """
    # Collect all wiki-link targets from body
    body = _get_body(content)
    targets: set[str] = set()
    for m in _WIKI_LINK_CONTENT_RE.finditer(body):
        targets.add(m.group(1).strip())

    # Also check source: frontmatter field
    fm_match = _FM_PATTERN.match(content)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1))
            if isinstance(fm, dict):
                source_val = fm.get("source", "")
                if isinstance(source_val, str):
                    for m in _WIKI_LINK_CONTENT_RE.finditer(source_val):
                        targets.add(m.group(1).strip())
        except yaml.YAMLError:
            pass

    if not targets:
        return ValidationResult(valid=True)

    # Build index of known stems
    stem_index = _build_stem_index(vault_root)

    errors: list[str] = []
    for target in sorted(targets):
        # Normalize target for lookup
        nfc_target = normalize_text(target)
        lower = nfc_target.lower()

        # Try exact (lowered) match
        if lower in stem_index:
            continue

        # Try accent-stripped
        accent_stripped = _strip_accents(lower)
        if accent_stripped in stem_index:
            continue

        # Try space-to-hyphen
        hyphenated = lower.replace(" ", "-")
        if hyphenated in stem_index:
            continue

        # Try accent-stripped + hyphenated
        combo = _strip_accents(hyphenated)
        if combo in stem_index:
            continue

        # Try hyphen-to-space (reverse)
        spaced = lower.replace("-", " ")
        if spaced in stem_index:
            continue

        errors.append(
            f"Dangling wiki-link: [[{target}]] -- no matching file found in "
            f"notes/, _research/literature/, _research/hypotheses/, "
            f"_research/experiments/, self/, projects/, or ops/methodology/."
        )

    if errors:
        return ValidationResult(valid=False, errors=errors)
    return ValidationResult(valid=True)


def check_topics_footer(content: str) -> ValidationResult:
    """B4: WARN if the note has no Topics footer with at least one link.

    Exempt: moc, hub, index, topic-map types.

    Args:
        content: Full note content (with frontmatter).

    Returns:
        ValidationResult with warning if Topics footer missing.
    """
    note_type = _get_fm_type(content)
    if note_type in _HEADER_EXEMPT_TYPES:
        return ValidationResult(valid=True)

    body = _get_body(content)

    # Look for "Topics:" followed (eventually) by "- [[" on a subsequent line
    lines = body.splitlines()
    found_topics = False
    for i, line in enumerate(lines):
        if line.strip().startswith("Topics:"):
            # Check remaining lines for a topic link
            for subsequent in lines[i + 1:]:
                stripped = subsequent.strip()
                if stripped.startswith("- [["):
                    found_topics = True
                    break
                if stripped and not stripped.startswith("-"):
                    break  # Non-list content after Topics: -- malformed
            break

    if not found_topics:
        return ValidationResult(
            valid=True,
            warnings=[
                "Missing Topics footer: claims should end with "
                "'Topics:\\n- [[topic-map]]' to prevent orphans."
            ],
        )
    return ValidationResult(valid=True)
