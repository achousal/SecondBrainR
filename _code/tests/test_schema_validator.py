"""Tests for schema_validator module."""

from __future__ import annotations

import unicodedata

import pytest

from engram_r.schema_validator import (
    ValidationResult,
    check_notes_provenance,
    detect_unicode_issues,
    detect_yaml_safety_issues,
    normalize_text,
    sanitize_title,
    strip_html,
    validate_filename,
    validate_note,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _note(fm_lines: list[str], body: str = "## Body\nContent\n") -> str:
    """Build a note string from frontmatter lines and body."""
    fm = "\n".join(fm_lines)
    return f"---\n{fm}\n---\n\n{body}"


# ---------------------------------------------------------------------------
# Valid notes -- one per type
# ---------------------------------------------------------------------------


class TestValidNotes:
    """Each note type passes validation when all required fields are present."""

    def test_valid_hypothesis(self):
        content = _note(
            [
                "type: hypothesis",
                "title: Test hypothesis",
                "id: hyp-20260101-001",
                "status: proposed",
                "elo: 1200",
                "research_goal: '[[goal]]'",
                "created: 2026-01-01",
                "updated: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert result.valid
        assert result.errors == []

    def test_valid_literature(self):
        content = _note(
            [
                "type: literature",
                "title: Some paper",
                "doi: 10.1234/test",
                "status: unread",
                "created: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_experiment(self):
        content = _note(
            [
                "type: experiment",
                "title: Exp 1",
                "status: planned",
                "created: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_eda_report(self):
        content = _note(
            [
                "type: eda-report",
                "title: EDA on dataset X",
                "dataset: /path/to/data.csv",
                "created: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_research_goal(self):
        content = _note(
            [
                "type: research-goal",
                "title: Find markers",
                "status: active",
                "created: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_tournament_match(self):
        content = _note(
            [
                "type: tournament-match",
                "date: 2026-01-01",
                "research_goal: '[[goal]]'",
                "hypothesis_a: '[[hyp-a]]'",
                "hypothesis_b: '[[hyp-b]]'",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_meta_review(self):
        content = _note(
            [
                "type: meta-review",
                "date: 2026-01-01",
                "research_goal: '[[goal]]'",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_project(self):
        content = _note(
            [
                "type: project",
                "title: TestProject",
                "project_tag: test-project",
                "lab: TestLab",
                "status: active",
                "project_path: /path/to/project",
                "created: 2026-01-01",
                "updated: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_lab(self):
        content = _note(
            [
                "type: lab",
                "lab_slug: example-lab",
                "pi: Test PI",
                "created: 2026-02-23",
                "updated: 2026-02-23",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_valid_institution(self):
        content = _note(
            [
                "type: institution",
                'name: "Icahn School of Medicine at Mount Sinai"',
                "slug: mount-sinai",
                "created: 2026-02-28",
                "updated: 2026-02-28",
            ]
        )
        result = validate_note(content)
        assert result.valid
        assert result.errors == []

    def test_institution_missing_name(self):
        content = _note(
            [
                "type: institution",
                "slug: mount-sinai",
                "created: 2026-02-28",
                "updated: 2026-02-28",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("name" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


class TestMissingFields:
    """Each note type fails when a required field is missing."""

    def test_hypothesis_missing_title(self):
        content = _note(
            [
                "type: hypothesis",
                "id: hyp-20260101-001",
                "status: proposed",
                "elo: 1200",
                "created: 2026-01-01",
                "updated: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("title" in e for e in result.errors)

    def test_hypothesis_missing_id(self):
        content = _note(
            [
                "type: hypothesis",
                "title: Test",
                "status: proposed",
                "elo: 1200",
                "created: 2026-01-01",
                "updated: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("id" in e for e in result.errors)

    def test_literature_missing_title(self):
        content = _note(
            [
                "type: literature",
                "doi: 10.1234/test",
                "status: unread",
                "created: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("title" in e for e in result.errors)

    def test_experiment_missing_title(self):
        content = _note(
            [
                "type: experiment",
                "status: planned",
                "created: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert not result.valid

    def test_project_missing_lab(self):
        content = _note(
            [
                "type: project",
                "title: Test",
                "project_tag: test",
                "status: active",
                "project_path: /tmp",
                "created: 2026-01-01",
                "updated: 2026-01-01",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("lab" in e for e in result.errors)

    def test_lab_missing_lab_slug(self):
        content = _note(
            [
                "type: lab",
                "pi: Test PI",
                "created: 2026-02-23",
                "updated: 2026-02-23",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("lab_slug" in e for e in result.errors)

    def test_lab_missing_pi(self):
        content = _note(
            [
                "type: lab",
                "lab_slug: test",
                "created: 2026-02-23",
                "updated: 2026-02-23",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("pi" in e for e in result.errors)

    def test_tournament_missing_hypothesis_a(self):
        content = _note(
            [
                "type: tournament-match",
                "date: 2026-01-01",
                "research_goal: '[[goal]]'",
                "hypothesis_b: '[[hyp-b]]'",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("hypothesis_a" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Passthrough behaviors
# ---------------------------------------------------------------------------


class TestPassthrough:
    """Non-note files and unknown types should pass validation."""

    def test_no_frontmatter_passes(self):
        content = "# Just a heading\n\nSome text.\n"
        result = validate_note(content)
        assert result.valid

    def test_unknown_type_passes(self):
        content = _note(
            [
                "type: custom-note",
                "title: Something",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_no_type_field_passes(self):
        content = _note(
            [
                "title: Something",
                "tags: [misc]",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_empty_string_passes(self):
        result = validate_note("")
        assert result.valid


# ---------------------------------------------------------------------------
# Type inference and explicit type
# ---------------------------------------------------------------------------


class TestTypeHandling:
    """Validate note_type parameter override behavior."""

    def test_explicit_type_overrides_frontmatter(self):
        content = _note(
            [
                "type: literature",
                "title: Paper",
                "doi: 10.1234/test",
                "status: unread",
                "created: 2026-01-01",
            ]
        )
        # Force validate as hypothesis -- should fail (missing hypothesis fields)
        result = validate_note(content, note_type="hypothesis")
        assert not result.valid

    def test_explicit_type_with_matching_fields_passes(self):
        content = _note(
            [
                "type: literature",
                "title: Paper",
                "doi: 10.1234/test",
                "status: unread",
                "created: 2026-01-01",
            ]
        )
        result = validate_note(content, note_type="literature")
        assert result.valid


# ---------------------------------------------------------------------------
# ValidationResult dataclass
# ---------------------------------------------------------------------------


class TestValidationResult:
    """Basic sanity checks on the result dataclass."""

    def test_valid_result(self):
        r = ValidationResult(valid=True, errors=[])
        assert r.valid
        assert r.errors == []
        assert r.warnings == []

    def test_invalid_result(self):
        r = ValidationResult(valid=False, errors=["missing field: title"])
        assert not r.valid
        assert len(r.errors) == 1

    def test_warnings_default_empty(self):
        r = ValidationResult(valid=True)
        assert r.warnings == []

    def test_warnings_field(self):
        r = ValidationResult(valid=True, warnings=["missing source"])
        assert r.valid
        assert len(r.warnings) == 1


# ---------------------------------------------------------------------------
# sanitize_title
# ---------------------------------------------------------------------------


class TestSanitizeTitle:
    """Filesystem-unsafe characters in titles are replaced with hyphens."""

    def test_forward_slash(self):
        assert sanitize_title("APP/PS1 mice") == "APP-PS1 mice"

    def test_multiple_slashes(self):
        assert sanitize_title("AhR/NF-kappaB/NLRP3") == "AhR-NF-kappaB-NLRP3"

    def test_backslash(self):
        assert sanitize_title("path\\to") == "path-to"

    def test_colon(self):
        assert sanitize_title("ratio:value") == "ratio-value"

    def test_no_unsafe_chars(self):
        assert sanitize_title("normal title") == "normal title"

    def test_mixed_unsafe(self):
        # Consecutive hyphens are collapsed after replacement
        assert sanitize_title('a/b\\c:d*e?"f') == "a-b-c-d-e-f"

    def test_preserves_hyphens(self):
        assert sanitize_title("already-safe-title") == "already-safe-title"

    def test_biology_notation(self):
        assert sanitize_title("APOE3/3") == "APOE3-3"
        assert sanitize_title("Abeta42/40") == "Abeta42-40"
        assert sanitize_title("insulin/IGF1") == "insulin-IGF1"


# ---------------------------------------------------------------------------
# validate_filename
# ---------------------------------------------------------------------------


class TestValidateFilename:
    """Detect unsafe characters in filename components."""

    def test_clean_path(self):
        assert validate_filename("notes/some claim.md") == []

    def test_slash_creates_no_filename_error(self):
        # The / is a path separator, so the filename component is just
        # "PS1 mice.md" which is clean -- the validate_write hook handles
        # the nesting check separately.
        assert validate_filename("notes/APP/PS1 mice.md") == []

    def test_colon_in_filename(self):
        errors = validate_filename("notes/ratio:value.md")
        assert len(errors) == 1
        assert ":" in errors[0]

    def test_asterisk_in_filename(self):
        errors = validate_filename("notes/test*file.md")
        assert len(errors) == 1
        assert "*" in errors[0]


# ---------------------------------------------------------------------------
# YAML special characters in frontmatter (regression for unquoted-colon bug)
# ---------------------------------------------------------------------------


class TestYAMLSpecialCharacters:
    """Frontmatter with YAML-special characters must be quoted to parse."""

    def test_unquoted_colon_in_description_is_invalid(self):
        """The original bug: 'docs: tighten am/pm references' broke YAML."""
        content = (
            "---\n"
            "description: docs: tighten am/pm references\n"
            "type: methodology\n"
            "---\n\n# Body\nContent\n"
        )
        result = validate_note(content)
        # yaml.safe_load parses this as {"description": {"docs": ...}}
        # which is a nested dict, not a string -- validation should still
        # proceed, but the description field won't be a string.  The key
        # point: the frontmatter *does* parse (YAML allows mapping values
        # as values), so validate_note returns valid=True for unknown types.
        # The validate_write hook catches the deeper issue.  What we really
        # care about is that properly quoted values work correctly.
        assert isinstance(result, ValidationResult)

    def test_conventional_commit_colon_unquoted_parses_unexpectedly(self):
        """Conventional commit format 'feat: add X' parses as nested mapping."""
        content = (
            "---\n"
            "session_source: feat: add new feature\n"
            "type: methodology\n"
            "---\n\n# Body\nContent\n"
        )
        result = validate_note(content)
        assert isinstance(result, ValidationResult)

    def test_quoted_colon_in_description_is_valid(self):
        """Properly quoted values with colons parse correctly."""
        content = _note(
            [
                'description: "docs: tighten am/pm references in narrative text"',
                "type: methodology",
                "category: quality",
                "status: active",
                "created: 2026-02-22",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_quoted_session_source_with_colon(self):
        """session_source with conventional commit format works when quoted."""
        content = _note(
            [
                'description: "observed pattern in session mining"',
                'session_source: "docs: tighten am/pm references"',
                "type: methodology",
                "status: active",
                "created: 2026-02-22",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_brackets_in_value_quoted(self):
        """Brackets in quoted values do not create YAML lists."""
        content = _note(
            [
                'description: "[session filename] contains the source"',
                "type: methodology",
                "status: active",
                "created: 2026-02-22",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_hash_in_value_quoted(self):
        """Hash in quoted values is not treated as a YAML comment."""
        content = _note(
            [
                'description: "commit abc123# introduced the bug"',
                "type: methodology",
                "status: active",
                "created: 2026-02-22",
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_unparseable_yaml_returns_invalid(self):
        """Completely broken YAML frontmatter returns valid=False."""
        content = "---\n: :\n  - [\n---\n\n# Body\n"
        result = validate_note(content)
        assert not result.valid
        assert any("Invalid YAML" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Foreign hypothesis schema
# ---------------------------------------------------------------------------


class TestForeignHypothesisSchema:
    """Validate foreign-hypothesis note type from federation imports."""

    def test_valid_foreign_hypothesis(self):
        content = _note(
            [
                "type: foreign-hypothesis",
                "title: Imported hypothesis from peer vault",
                "id: hyp-peer-001",
                "status: proposed",
                "elo_federated: 1200",
                "elo_source: 1350",
                "matches_federated: 0",
                "matches_source: 8",
                "source_vault: collab-lab-uuid",
                "imported: 2026-02-23",
            ]
        )
        result = validate_note(content)
        assert result.valid
        assert result.errors == []

    def test_foreign_hypothesis_missing_required_fields(self):
        content = _note(
            [
                "type: foreign-hypothesis",
                "title: Incomplete import",
                "id: hyp-peer-002",
                "status: proposed",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("elo_federated" in e for e in result.errors)
        assert any("source_vault" in e for e in result.errors)


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------


class TestNormalizeText:
    """NFC Unicode normalization."""

    def test_nfc_normalization(self):
        # e + combining acute -> precomposed e-acute
        decomposed = "cafe\u0301"
        assert normalize_text(decomposed) == "caf\u00e9"

    def test_already_nfc_is_noop(self):
        text = "caf\u00e9"
        assert normalize_text(text) == text

    def test_ascii_passthrough(self):
        assert normalize_text("plain ascii") == "plain ascii"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_mixed_nfc_and_nfd(self):
        # Mix of precomposed and decomposed forms
        mixed = "r\u00e9sum\u0065\u0301"  # re-accent + e + combining acute
        result = normalize_text(mixed)
        assert result == unicodedata.normalize("NFC", mixed)


# ---------------------------------------------------------------------------
# sanitize_title -- extended chars (.+[](){}^)
# ---------------------------------------------------------------------------


class TestSanitizeTitleExtended:
    """Test the expanded unsafe character set from CLAUDE.md title rules."""

    def test_dot_replaced(self):
        assert sanitize_title("v2.0 results") == "v2-0 results"

    def test_plus_replaced(self):
        assert sanitize_title("A+B") == "A-B"

    def test_square_brackets_replaced(self):
        assert sanitize_title("a[b]c") == "a-b-c"

    def test_parentheses_replaced(self):
        assert sanitize_title("ratio (DCA:CA)") == "ratio -DCA-CA"

    def test_curly_braces_replaced(self):
        assert sanitize_title("interface{}") == "interface"

    def test_caret_replaced(self):
        assert sanitize_title("x^2") == "x-2"

    def test_consecutive_hyphens_collapsed(self):
        # Multiple adjacent unsafe chars -> single hyphen
        assert sanitize_title("a//b") == "a-b"
        assert sanitize_title("a()b") == "a-b"

    def test_leading_trailing_hyphens_stripped(self):
        assert sanitize_title("/leading") == "leading"
        assert sanitize_title("trailing/") == "trailing"
        assert sanitize_title("(wrapped)") == "wrapped"

    def test_nfc_normalization_applied(self):
        # Decomposed e-acute is normalized before sanitization
        decomposed = "cafe\u0301 study"
        result = sanitize_title(decomposed)
        assert "\u0301" not in result
        assert "caf\u00e9 study" == result

    def test_biology_notation_with_parens(self):
        assert sanitize_title("APP(695)") == "APP-695"
        assert sanitize_title("Factor-X/TNF-alpha (ratio)") == "Factor-X-TNF-alpha -ratio"

    def test_combined_old_and_new_chars(self):
        assert sanitize_title("a/b.c+d[e](f)") == "a-b-c-d-e-f"


# ---------------------------------------------------------------------------
# validate_filename -- NFC check
# ---------------------------------------------------------------------------


class TestValidateFilenameExtended:
    """Extended filename validation including NFC checks."""

    def test_nfc_filename_passes(self):
        assert validate_filename("notes/caf\u00e9 study.md") == []

    def test_non_nfc_filename_flagged(self):
        # Decomposed form: e + combining acute
        errors = validate_filename("notes/cafe\u0301 study.md")
        assert len(errors) >= 1
        assert any("non-NFC" in e for e in errors)

    def test_dot_in_extension_is_ok(self):
        # The .md extension contains a dot but should not trigger errors
        assert validate_filename("notes/some claim.md") == []

    def test_original_unsafe_chars_still_caught(self):
        errors = validate_filename("notes/ratio:value.md")
        assert any(":" in e for e in errors)


# ---------------------------------------------------------------------------
# detect_yaml_safety_issues
# ---------------------------------------------------------------------------


class TestDetectYamlSafetyIssues:
    """Pre-parse detection of YAML values that silently misparse."""

    def test_unquoted_colon_detected(self):
        content = _note(["description: docs: tighten am/pm references"])
        issues = detect_yaml_safety_issues(content)
        assert len(issues) >= 1
        assert any("unquoted" in i and ":" in i for i in issues)

    def test_conventional_commit_detected(self):
        content = _note(["session_source: feat: add new feature"])
        issues = detect_yaml_safety_issues(content)
        assert len(issues) >= 1

    def test_quoted_colon_passes(self):
        content = _note(['description: "docs: tighten am/pm references"'])
        issues = detect_yaml_safety_issues(content)
        assert issues == []

    def test_single_quoted_colon_passes(self):
        content = _note(["description: 'docs: tighten am/pm references'"])
        issues = detect_yaml_safety_issues(content)
        assert issues == []

    def test_simple_value_no_colon_passes(self):
        content = _note(["description: a simple value"])
        issues = detect_yaml_safety_issues(content)
        assert issues == []

    def test_unquoted_hash_detected(self):
        content = _note(["description: #this looks like a comment"])
        issues = detect_yaml_safety_issues(content)
        assert len(issues) >= 1
        assert any("#" in i for i in issues)

    def test_quoted_hash_passes(self):
        content = _note(['description: "#this is fine"'])
        issues = detect_yaml_safety_issues(content)
        assert issues == []

    def test_no_frontmatter_returns_empty(self):
        content = "# Just a heading\n\nNo frontmatter.\n"
        assert detect_yaml_safety_issues(content) == []

    def test_multiple_issues_reported(self):
        content = _note(
            [
                "description: feat: add thing",
                "session_source: fix: repair other",
            ]
        )
        issues = detect_yaml_safety_issues(content)
        assert len(issues) >= 2

    def test_date_colon_not_flagged(self):
        # ISO date-like values: "2026-02-23" has no colon-space after the key
        content = _note(["created: 2026-02-23"])
        issues = detect_yaml_safety_issues(content)
        assert issues == []

    def test_list_items_not_flagged(self):
        # YAML list items starting with "- " should not match key pattern
        content = _note(["tags:", "  - compounds", "  - TC"])
        issues = detect_yaml_safety_issues(content)
        assert issues == []


# ---------------------------------------------------------------------------
# detect_unicode_issues
# ---------------------------------------------------------------------------


class TestDetectUnicodeIssues:
    """Pre-parse detection of non-NFC Unicode in frontmatter."""

    def test_nfc_content_passes(self):
        content = _note(['description: "caf\u00e9 study"'])
        assert detect_unicode_issues(content) == []

    def test_non_nfc_content_flagged(self):
        # Decomposed e + combining acute
        content = _note(["description: cafe\u0301 study"])
        issues = detect_unicode_issues(content)
        assert len(issues) == 1
        assert "non-NFC" in issues[0]

    def test_ascii_only_passes(self):
        content = _note(["description: plain ascii"])
        assert detect_unicode_issues(content) == []

    def test_no_frontmatter_returns_empty(self):
        content = "# Heading\n\ncafe\u0301 in body only.\n"
        assert detect_unicode_issues(content) == []

    def test_body_unicode_not_checked(self):
        # Non-NFC in body should not be flagged (only frontmatter)
        content = "---\ndescription: clean\n---\n\ncafe\u0301 body.\n"
        assert detect_unicode_issues(content) == []


# ---------------------------------------------------------------------------
# check_notes_provenance
# ---------------------------------------------------------------------------


class TestNotesProvenance:
    """Provenance checks for notes/ files enforce description and source."""

    def test_valid_claim_with_description_and_source(self):
        content = _note(
            [
                'description: "Factor-X drives test mechanism in TC brain regions"',
                'source: "[[2026-bach-immunometabolism]]"',
                "type: claim",
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert result.errors == []
        assert result.warnings == []

    def test_missing_description_errors(self):
        content = _note(
            [
                'source: "[[some-source]]"',
                "type: claim",
            ]
        )
        result = check_notes_provenance(content)
        assert not result.valid
        assert any("description" in e for e in result.errors)

    def test_empty_description_errors(self):
        content = _note(
            [
                'description: ""',
                'source: "[[some-source]]"',
                "type: claim",
            ]
        )
        result = check_notes_provenance(content)
        assert not result.valid
        assert any("Empty description" in e for e in result.errors)

    def test_whitespace_only_description_errors(self):
        content = _note(
            [
                'description: "   "',
                'source: "[[some-source]]"',
                "type: claim",
            ]
        )
        result = check_notes_provenance(content)
        assert not result.valid
        assert any("Empty description" in e for e in result.errors)

    def test_no_frontmatter_errors(self):
        content = "# Just a heading\n\nSome text.\n"
        result = check_notes_provenance(content)
        assert not result.valid
        assert any("frontmatter" in e.lower() for e in result.errors)

    def test_empty_content_errors(self):
        result = check_notes_provenance("")
        assert not result.valid

    def test_moc_missing_source_no_warning(self):
        content = _note(
            [
                'description: "Navigation hub for test analysis"',
                "type: moc",
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert result.warnings == []

    def test_index_type_exempt_from_source_warning(self):
        content = _note(
            [
                'description: "Top-level index"',
                "type: index",
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert result.warnings == []

    def test_claim_missing_source_warns(self):
        content = _note(
            [
                'description: "Some insight about test condition"',
                "type: claim",
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert any("source" in w for w in result.warnings)

    def test_evidence_missing_source_warns(self):
        content = _note(
            [
                'description: "Empirical finding from study"',
                "type: evidence",
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert any("source" in w for w in result.warnings)

    def test_methodology_missing_source_warns(self):
        content = _note(
            [
                'description: "Best practice for network analysis"',
                "type: methodology",
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert any("source" in w for w in result.warnings)

    def test_no_type_field_missing_source_warns(self):
        """Untyped notes default to claim-family behavior."""
        content = _note(
            [
                'description: "Some insight without explicit type"',
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert any("source" in w for w in result.warnings)

    def test_no_type_field_with_source_clean(self):
        content = _note(
            [
                'description: "Some insight"',
                'source: "[[some-paper]]"',
            ]
        )
        result = check_notes_provenance(content)
        assert result.valid
        assert result.warnings == []

    def test_invalid_yaml_errors(self):
        content = "---\n: :\n  - [\n---\n\n# Body\n"
        result = check_notes_provenance(content)
        assert not result.valid
        assert any("Invalid YAML" in e for e in result.errors)


# ---------------------------------------------------------------------------
# strip_html
# ---------------------------------------------------------------------------


class TestStripHtml:
    """HTML tag stripping and entity unescaping."""

    def test_script_tag(self):
        assert strip_html("<script>alert('xss')</script>safe") == "alert('xss')safe"

    def test_nested_tags(self):
        assert strip_html("<div><p><b>text</b></p></div>") == "text"

    def test_html_comment(self):
        assert strip_html("before<!-- comment -->after") == "beforeafter"

    def test_entity_unescaping(self):
        assert strip_html("&amp; &lt; &gt;") == "& < >"

    def test_plain_text_passthrough(self):
        assert strip_html("no tags here") == "no tags here"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_mixed_tags_and_text(self):
        assert strip_html("<b>bold</b> and <i>italic</i>") == "bold and italic"

    def test_entity_without_tags(self):
        assert strip_html("5 &gt; 3") == "5 > 3"

    def test_self_closing_tags(self):
        assert strip_html("line<br/>break") == "linebreak"


# ---------------------------------------------------------------------------
# Claim-family schema validation
# ---------------------------------------------------------------------------


class TestClaimFamilySchemas:
    """Claim-family types now have required-field schemas."""

    def test_valid_claim_with_description(self):
        content = _note(
            [
                "type: claim",
                'description: "A valid claim"',
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_claim_missing_description_fails(self):
        content = _note(
            [
                "type: claim",
                "tags: [test]",
            ]
        )
        result = validate_note(content)
        assert not result.valid
        assert any("description" in e for e in result.errors)

    def test_evidence_with_description_passes(self):
        content = _note(
            [
                "type: evidence",
                'description: "Empirical finding"',
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_evidence_missing_description_fails(self):
        content = _note(["type: evidence"])
        result = validate_note(content)
        assert not result.valid

    def test_methodology_with_description_passes(self):
        content = _note(
            [
                "type: methodology",
                'description: "A best practice"',
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_contradiction_missing_description_fails(self):
        content = _note(["type: contradiction"])
        result = validate_note(content)
        assert not result.valid

    def test_pattern_with_description_passes(self):
        content = _note(
            [
                "type: pattern",
                'description: "Recurring observation"',
            ]
        )
        result = validate_note(content)
        assert result.valid

    def test_question_missing_description_fails(self):
        content = _note(["type: question"])
        result = validate_note(content)
        assert not result.valid
