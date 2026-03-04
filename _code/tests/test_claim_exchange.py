"""Tests for claim_exchange module -- export/import for cross-vault federation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from engram_r.claim_exchange import (
    ClaimExchangeError,
    ExportedClaim,
    _strip_wiki_links,
    export_claim,
    export_claims,
    export_to_yaml,
    import_claims,
    load_exported_claims,
)
from engram_r.schema_validator import sanitize_title

_NOW = datetime(2026, 2, 23, 12, 0, 0, tzinfo=UTC)

_SAMPLE_NOTE = """\
---
description: "compound-A levels increase in TC samples"
type: evidence
confidence: supported
source: "[[smith-2024-compounds]]"
source_class: published
verified_by: human
verified_who: "Test Verifier"
verified_date: "2026-02-25"
tags:
  - compounds
  - TC
---

compound-A accumulation in target region is associated with
[[score plaque burden]] in post-mortem tissue.

Relevant Claims:
- [[score drives compound-A synthesis]] -- mechanistic basis
"""


class TestStripWikiLinks:
    """Test wiki-link to plain text conversion."""

    def test_simple_link(self) -> None:
        assert _strip_wiki_links("see [[foo bar]]") == "see foo bar"

    def test_display_text(self) -> None:
        assert _strip_wiki_links("see [[foo|Bar]]") == "see Bar"

    def test_multiple_links(self) -> None:
        text = "[[a]] and [[b|B]] plus [[c]]"
        assert _strip_wiki_links(text) == "a and B plus c"

    def test_no_links(self) -> None:
        assert _strip_wiki_links("plain text") == "plain text"

    def test_nested_brackets(self) -> None:
        assert _strip_wiki_links("[[x]]") == "x"


class TestExportClaim:
    """Test single claim export."""

    def test_basic_export(self) -> None:
        claim = export_claim(
            _SAMPLE_NOTE,
            title="compound-A levels increase in TC samples",
            source_vault="main",
            now=_NOW,
        )
        assert claim.title == "compound-A levels increase in TC samples"
        assert claim.description == "compound-A levels increase in TC samples"
        assert claim.type == "evidence"
        assert claim.confidence == "supported"
        assert claim.source == "smith-2024-compounds"  # wiki-link stripped
        assert claim.source_class == "published"
        assert claim.verified_by == "human"
        assert claim.verified_who == "Test Verifier"
        assert claim.verified_date == "2026-02-25"
        assert claim.tags == ["compounds", "TC"]
        assert claim.source_vault == "main"
        assert "score plaque burden" in claim.body  # link stripped
        assert "[[" not in claim.body  # no wiki-links in body

    def test_exported_timestamp(self) -> None:
        claim = export_claim(
            _SAMPLE_NOTE,
            title="test",
            source_vault="v",
            now=_NOW,
        )
        assert claim.exported == "2026-02-23T12:00:00+00:00"

    def test_minimal_note(self) -> None:
        content = "---\ndescription: minimal\n---\n\nBody text.\n"
        claim = export_claim(content, title="minimal claim", source_vault="v", now=_NOW)
        assert claim.title == "minimal claim"
        assert claim.description == "minimal"
        assert claim.type == "claim"
        assert claim.body == "Body text."

    def test_no_frontmatter_raises(self) -> None:
        with pytest.raises(ClaimExchangeError, match="frontmatter"):
            export_claim("no frontmatter here", title="x", source_vault="v")

    def test_invalid_yaml_raises(self) -> None:
        content = "---\n: :\n---\n\nbody\n"
        with pytest.raises(ClaimExchangeError):
            export_claim(content, title="x", source_vault="v")


class TestExportClaims:
    """Test bulk export from a vault directory."""

    @pytest.fixture()
    def vault(self, tmp_path: Path) -> Path:
        notes = tmp_path / "notes"
        notes.mkdir()
        # Create 3 notes
        (notes / "claim-a.md").write_text(
            '---\ndescription: "A"\ntype: claim\nconfidence: supported\n'
            "tags: [x]\n---\n\nBody A.\n"
        )
        (notes / "claim-b.md").write_text(
            '---\ndescription: "B"\ntype: evidence\nconfidence: established\n'
            "tags: [y]\n---\n\nBody B.\n"
        )
        (notes / "claim-c.md").write_text(
            '---\ndescription: "C"\ntype: claim\nconfidence: preliminary\n'
            "tags: [x, z]\n---\n\nBody C.\n"
        )
        return tmp_path

    def test_exports_all(self, vault: Path) -> None:
        claims = export_claims(vault, source_vault="test", now=_NOW)
        assert len(claims) == 3

    def test_filter_by_type(self, vault: Path) -> None:
        claims = export_claims(
            vault, source_vault="test", filter_type="evidence", now=_NOW
        )
        assert len(claims) == 1
        assert claims[0].type == "evidence"

    def test_filter_by_confidence(self, vault: Path) -> None:
        claims = export_claims(
            vault,
            source_vault="test",
            filter_confidence="supported",
            now=_NOW,
        )
        assert len(claims) == 1
        assert claims[0].confidence == "supported"

    def test_filter_by_tags(self, vault: Path) -> None:
        claims = export_claims(vault, source_vault="test", filter_tags=["x"], now=_NOW)
        assert len(claims) == 2  # claim-a and claim-c

    def test_filter_by_multiple_tags(self, vault: Path) -> None:
        claims = export_claims(
            vault, source_vault="test", filter_tags=["x", "z"], now=_NOW
        )
        assert len(claims) == 1  # only claim-c has both

    def test_missing_notes_dir(self, tmp_path: Path) -> None:
        claims = export_claims(tmp_path, source_vault="test")
        assert claims == []

    def test_skips_malformed_notes(self, vault: Path) -> None:
        (vault / "notes" / "bad.md").write_text("no frontmatter")
        claims = export_claims(vault, source_vault="test", now=_NOW)
        assert len(claims) == 3  # bad note skipped


class TestYamlRoundTrip:
    """Test YAML serialization/deserialization."""

    def test_round_trip(self) -> None:
        original = [
            ExportedClaim(
                title="test claim",
                description="desc",
                type="evidence",
                confidence="supported",
                source="Smith 2024",
                source_class="published",
                verified_by="human",
                verified_who="Test Verifier",
                verified_date="2026-02-25",
                tags=["a", "b"],
                body="Body text here.",
                source_vault="main",
                exported="2026-02-23T12:00:00+00:00",
            )
        ]
        yaml_str = export_to_yaml(original)
        loaded = load_exported_claims(yaml_str)
        assert len(loaded) == 1
        assert loaded[0].title == original[0].title
        assert loaded[0].description == original[0].description
        assert loaded[0].type == original[0].type
        assert loaded[0].confidence == original[0].confidence
        assert loaded[0].source == original[0].source
        assert loaded[0].source_class == original[0].source_class
        assert loaded[0].verified_by == original[0].verified_by
        assert loaded[0].verified_who == original[0].verified_who
        assert loaded[0].verified_date == original[0].verified_date
        assert loaded[0].tags == original[0].tags
        assert loaded[0].body == original[0].body
        assert loaded[0].source_vault == original[0].source_vault

    def test_load_invalid_yaml(self) -> None:
        with pytest.raises(ClaimExchangeError):
            load_exported_claims(":::bad")

    def test_load_non_list(self) -> None:
        with pytest.raises(ClaimExchangeError, match="list"):
            load_exported_claims("key: value")

    def test_load_skips_non_dict_items(self) -> None:
        result = load_exported_claims("- title: ok\n- just a string\n")
        assert len(result) == 1

    def test_load_skips_items_without_title(self) -> None:
        result = load_exported_claims("- description: no title\n")
        assert len(result) == 0

    def test_empty_list(self) -> None:
        result = load_exported_claims("[]")
        assert result == []


class TestExportPiiSanitization:
    """PII sanitization on export."""

    _NOTE_WITH_PII = """\
---
description: "Contact alice@example.com for compound data"
type: claim
confidence: supported
source: "Smith 2024"
verified_by: human
verified_who: "Dr. Alice Smith"
verified_date: "2026-02-25"
---

Call (555) 123-4567 for raw data. SSN: 111-22-3333.
MRN: 12345 enrolled in study.
"""

    def test_verified_who_cleared(self) -> None:
        claim = export_claim(
            self._NOTE_WITH_PII,
            title="pii claim",
            source_vault="v",
            now=_NOW,
            sanitize_pii=True,
        )
        assert claim.verified_who == ""
        assert claim.verified_date == ""

    def test_body_redacted(self) -> None:
        claim = export_claim(
            self._NOTE_WITH_PII,
            title="pii claim",
            source_vault="v",
            now=_NOW,
            sanitize_pii=True,
        )
        assert "555" not in claim.body
        assert "111-22-3333" not in claim.body
        assert "12345" not in claim.body
        assert "[REDACTED]" in claim.body

    def test_description_redacted(self) -> None:
        claim = export_claim(
            self._NOTE_WITH_PII,
            title="pii claim",
            source_vault="v",
            now=_NOW,
            sanitize_pii=True,
        )
        assert "alice@example.com" not in claim.description
        assert "[REDACTED]" in claim.description

    def test_disabled_preserves_fields(self) -> None:
        claim = export_claim(
            self._NOTE_WITH_PII,
            title="pii claim",
            source_vault="v",
            now=_NOW,
            sanitize_pii=False,
        )
        assert claim.verified_who == "Dr. Alice Smith"
        assert claim.verified_date == "2026-02-25"
        assert "alice@example.com" in claim.description


class TestExportQuarantineFilter:
    """Quarantined notes are excluded from export by default."""

    @pytest.fixture()
    def vault(self, tmp_path: Path) -> Path:
        notes = tmp_path / "notes"
        notes.mkdir()
        (notes / "normal.md").write_text(
            '---\ndescription: "Normal"\ntype: claim\n---\n\nBody.\n'
        )
        (notes / "quarantined.md").write_text(
            '---\ndescription: "Q"\ntype: claim\nquarantine: true\n---\n\nBody.\n'
        )
        return tmp_path

    def test_quarantined_skipped_by_default(self, vault: Path) -> None:
        claims = export_claims(vault, source_vault="test", now=_NOW)
        assert len(claims) == 1
        assert claims[0].title == "normal"

    def test_quarantined_included_when_disabled(self, vault: Path) -> None:
        claims = export_claims(
            vault, source_vault="test", filter_quarantined=False, now=_NOW
        )
        assert len(claims) == 2

    def test_non_quarantined_unaffected(self, vault: Path) -> None:
        claims = export_claims(vault, source_vault="test", now=_NOW)
        titles = [c.title for c in claims]
        assert "normal" in titles
        assert "quarantined" not in titles


class TestImportClaims:
    """Test importing claims into a vault."""

    @pytest.fixture()
    def vault(self, tmp_path: Path) -> Path:
        (tmp_path / "notes").mkdir()
        return tmp_path

    def _make_claim(self, title: str = "test claim") -> ExportedClaim:
        return ExportedClaim(
            title=title,
            description="A test description",
            type="claim",
            confidence="supported",
            source="Smith 2024",
            source_class="published",
            verified_by="human",
            verified_who="Test Verifier",
            verified_date="2026-02-25",
            tags=["lipids"],
            body="Body content here.",
            source_vault="other-vault",
            exported="2026-02-23T12:00:00+00:00",
        )

    def test_creates_note_file(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims)
        assert len(created) == 1
        assert created[0].exists()

    def test_quarantine_flag_added(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims, quarantine=True)
        content = created[0].read_text(encoding="utf-8")
        assert "quarantine: true" in content

    def test_quarantine_flag_omitted(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims, quarantine=False)
        content = created[0].read_text(encoding="utf-8")
        assert "quarantine" not in content

    def test_source_vault_in_frontmatter(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims)
        content = created[0].read_text(encoding="utf-8")
        assert "source_vault: other-vault" in content

    def test_preserves_body(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims)
        content = created[0].read_text(encoding="utf-8")
        assert "Body content here." in content

    def test_does_not_overwrite_by_default(self, vault: Path) -> None:
        note_path = vault / "notes" / "test claim.md"
        note_path.write_text("existing content")
        claims = [self._make_claim()]
        created = import_claims(vault, claims, overwrite=False)
        assert len(created) == 0
        assert note_path.read_text() == "existing content"

    def test_overwrite_replaces(self, vault: Path) -> None:
        note_path = vault / "notes" / "test claim.md"
        note_path.write_text("existing content")
        claims = [self._make_claim()]
        created = import_claims(vault, claims, overwrite=True)
        assert len(created) == 1
        assert "Body content here." in created[0].read_text()

    def test_creates_notes_dir_if_missing(self, tmp_path: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(tmp_path, claims)
        assert len(created) == 1
        assert (tmp_path / "notes").is_dir()

    def test_multiple_claims(self, vault: Path) -> None:
        claims = [self._make_claim("claim one"), self._make_claim("claim two")]
        created = import_claims(vault, claims)
        assert len(created) == 2

    def test_frontmatter_is_valid_yaml(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims)
        content = created[0].read_text(encoding="utf-8")
        # Parse the frontmatter
        match = __import__("re").match(
            r"^---\s*\n(.*?)\n---\s*\n", content, __import__("re").DOTALL
        )
        assert match is not None
        fm = yaml.safe_load(match.group(1))
        assert isinstance(fm, dict)
        assert fm["type"] == "claim"
        assert fm["confidence"] == "supported"

    def test_imported_timestamp(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims)
        content = created[0].read_text(encoding="utf-8")
        assert "imported:" in content

    def test_provenance_fields_in_imported_note(self, vault: Path) -> None:
        claims = [self._make_claim()]
        created = import_claims(vault, claims)
        content = created[0].read_text(encoding="utf-8")
        assert "source_class: published" in content
        assert "verified_by: human" in content
        assert "verified_who: Test Verifier" in content
        assert "verified_date: '2026-02-25'" in content or "verified_date: 2026-02-25" in content


class TestImportAppliesSanitization:
    """A1: imported claims go through build_claim_note sanitization."""

    def test_import_applies_nfc_normalization(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        (vault / "notes").mkdir(parents=True)
        # Title with decomposed e-acute (e + combining accent)
        claim = ExportedClaim(
            title="cafe\u0301 hypothesis",
            description="NFC test",
            type="claim",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_claims(vault, [claim])
        assert len(created) == 1
        content = created[0].read_text(encoding="utf-8")
        # Description should be NFC-normalized
        assert "\u0301" not in content

    def test_import_sanitizes_title_for_filename(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        (vault / "notes").mkdir(parents=True)
        claim = ExportedClaim(
            title="claim/with/slashes:and:colons",
            description="Filename safety test",
            type="claim",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_claims(vault, [claim])
        assert len(created) == 1
        # Filename must not contain / or :
        assert "/" not in created[0].name
        assert ":" not in created[0].name

    def test_import_produces_valid_schema(self, tmp_path: Path) -> None:
        from engram_r.schema_validator import validate_note

        vault = tmp_path / "vault"
        (vault / "notes").mkdir(parents=True)
        claim = ExportedClaim(
            title="schema validation test",
            description="Full provenance claim",
            type="evidence",
            confidence="supported",
            source="Smith 2024",
            source_class="published",
            verified_by="human",
            verified_who="Test User",
            verified_date="2026-02-25",
            tags=["test"],
            body="Evidence body.",
            source_vault="remote-vault",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_claims(vault, [claim])
        content = created[0].read_text(encoding="utf-8")
        result = validate_note(content)
        assert result.valid, f"Schema errors: {result.errors}"


class TestImportRejectsInvalidSchema:
    """A3: import raises on invalid schema."""

    def test_import_rejects_claim_missing_description(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from engram_r.schema_validator import ValidationResult

        vault = tmp_path / "vault"
        (vault / "notes").mkdir(parents=True)
        claim = ExportedClaim(
            title="test claim",
            description="Valid description",
            type="claim",
            source_vault="test",
            exported="2026-02-23T12:00:00+00:00",
        )
        fake_result = ValidationResult(
            valid=False, errors=["missing description"]
        )
        with (
            patch(
                "engram_r.claim_exchange.validate_note",
                return_value=fake_result,
            ),
            pytest.raises(ClaimExchangeError, match="fails schema"),
        ):
            import_claims(vault, [claim])


class TestImportedNoteSchemaValidation:
    """B2 canary: imported notes must pass schema validation."""

    def test_imported_note_passes_schema_validation(self, tmp_path: Path) -> None:
        from engram_r.schema_validator import validate_note

        vault = tmp_path / "vault"
        (vault / "notes").mkdir(parents=True)
        claim = ExportedClaim(
            title="test schema canary",
            description="A test description for validation",
            type="claim",
            confidence="supported",
            source="Smith 2024",
            source_class="published",
            verified_by="agent",
            tags=["test"],
            body="Body content.",
            source_vault="other-vault",
            exported="2026-02-23T12:00:00+00:00",
        )
        created = import_claims(vault, [claim])
        assert len(created) == 1
        content = created[0].read_text(encoding="utf-8")
        result = validate_note(content)
        assert result.valid, f"Schema errors: {result.errors}"


class TestSanitizeTitle:
    """Test title sanitization via canonical schema_validator function."""

    def test_slashes(self) -> None:
        assert "/" not in sanitize_title("a/b/c")

    def test_colons(self) -> None:
        assert ":" not in sanitize_title("a:b")

    def test_brackets(self) -> None:
        assert "[" not in sanitize_title("a[b]c")

    def test_preserves_hyphens(self) -> None:
        assert sanitize_title("a-b-c") == "a-b-c"

    def test_preserves_spaces(self) -> None:
        assert sanitize_title("hello world") == "hello world"

    def test_nfc_normalization(self) -> None:
        """NFC normalization is applied to titles."""
        result = sanitize_title("cafe\u0301")
        assert "\u0301" not in result
        assert "caf\u00e9" == result


class TestFullRoundTrip:
    """Test complete export -> YAML -> load -> import cycle."""

    def test_round_trip_preserves_content(self, tmp_path: Path) -> None:
        # Source vault with a claim
        src = tmp_path / "src"
        (src / "notes").mkdir(parents=True)
        note_content = (
            "---\n"
            'description: "compound-A levels rise in TC"\n'
            "type: evidence\n"
            "confidence: supported\n"
            'source: "[[smith-2024]]"\n'
            "tags:\n"
            "  - compounds\n"
            "---\n\n"
            "compound-A is linked to [[score pathology]].\n"
        )
        (src / "notes" / "compound-a-rises-in-tc.md").write_text(note_content)

        # Export
        claims = export_claims(src, source_vault="lab-a", now=_NOW)
        assert len(claims) == 1

        # Serialize + deserialize
        yaml_str = export_to_yaml(claims)
        loaded = load_exported_claims(yaml_str)
        assert len(loaded) == 1

        # Import into target vault
        dst = tmp_path / "dst"
        created = import_claims(dst, loaded)
        assert len(created) == 1

        # Verify imported content
        content = created[0].read_text(encoding="utf-8")
        assert "compound-A levels rise in TC" in content
        assert "source_vault: lab-a" in content
        assert "quarantine: true" in content
        assert "score pathology" in content  # link stripped but text preserved
        assert "[[" not in content  # no wiki-links in imported note
        assert "smith-2024" in content  # source as citation
