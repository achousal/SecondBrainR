"""Tests for DOI stub enrichment."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from engram_r.stub_enricher import (
    EnrichmentResult,
    StubInfo,
    apply_enrichment_to_stub,
    enrich_single_doi,
    extract_doi_from_url,
    parse_inbox_stub,
    scan_inbox_stubs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_STUB = textwrap.dedent("""\
    ---
    source_type: "import"
    source_url: "https://link.springer.com/article/10.1007/s11357-025-01840-1"
    authors: "Smith A, Jones B"
    journal: "Nature"
    year: 2025
    lab: "Test Lab"
    generated: "2026-03-04T08:58:56"
    status: "pending"
    ---

    # Test paper title

    **Authors:** Smith A, Jones B
    **Journal:** Nature (2025)
    **URL:** https://link.springer.com/article/10.1007/s11357-025-01840-1

    ## Notes

    Imported from lab website.
""")

_NON_IMPORT_STUB = textwrap.dedent("""\
    ---
    source_type: "research"
    source_url: "https://doi.org/10.1234/test"
    ---

    # Not an import
""")

_NO_URL_STUB = textwrap.dedent("""\
    ---
    source_type: "import"
    authors: "Smith A"
    ---

    # No URL paper
""")

_HAS_ABSTRACT_STUB = textwrap.dedent("""\
    ---
    source_type: "import"
    source_url: "https://doi.org/10.1234/test"
    ---

    # Paper with abstract

    ## Abstract

    This paper already has an abstract.

    ## Notes

    Done.
""")

_ALREADY_ENRICHED_STUB = textwrap.dedent("""\
    ---
    source_type: "import"
    source_url: "https://doi.org/10.1234/test"
    content_depth: "abstract"
    ---

    # Already enriched paper
""")

_MALFORMED_YAML_STUB = textwrap.dedent("""\
    ---
    source_type: [invalid yaml
    ---

    # Bad yaml
""")


@pytest.fixture
def inbox_dir(tmp_path: Path) -> Path:
    """Create an inbox directory with test stubs."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return inbox


@pytest.fixture
def stub_file(inbox_dir: Path) -> Path:
    """Create a single valid stub file."""
    p = inbox_dir / "2025-test-paper.md"
    p.write_text(_VALID_STUB)
    return p


# ---------------------------------------------------------------------------
# TestExtractDoiFromUrl
# ---------------------------------------------------------------------------


class TestExtractDoiFromUrl:
    def test_doi_org_url(self):
        assert extract_doi_from_url(
            "https://doi.org/10.1007/s11357-025-01840-1"
        ) == "10.1007/s11357-025-01840-1"

    def test_dx_doi_org_url(self):
        assert extract_doi_from_url(
            "https://dx.doi.org/10.1234/test.123"
        ) == "10.1234/test.123"

    def test_publisher_url_with_doi(self):
        assert extract_doi_from_url(
            "https://link.springer.com/article/10.1007/s11357-025-01840-1"
        ) == "10.1007/s11357-025-01840-1"

    def test_trailing_punctuation_stripped(self):
        assert extract_doi_from_url(
            "https://doi.org/10.1234/test."
        ) == "10.1234/test"

    def test_trailing_comma_stripped(self):
        assert extract_doi_from_url(
            "https://doi.org/10.1234/test,"
        ) == "10.1234/test"

    def test_trailing_semicolon_stripped(self):
        assert extract_doi_from_url(
            "https://doi.org/10.1234/test;"
        ) == "10.1234/test"

    def test_trailing_paren_stripped(self):
        assert extract_doi_from_url(
            "https://doi.org/10.1234/test)"
        ) == "10.1234/test"

    def test_no_doi_returns_none(self):
        assert extract_doi_from_url("https://example.com/no-doi") is None

    def test_empty_string(self):
        assert extract_doi_from_url("") is None

    def test_none_input(self):
        assert extract_doi_from_url(None) is None

    def test_bare_doi(self):
        assert extract_doi_from_url("10.1234/test") == "10.1234/test"

    def test_http_doi_url(self):
        assert extract_doi_from_url(
            "http://doi.org/10.1234/test"
        ) == "10.1234/test"


# ---------------------------------------------------------------------------
# TestParseInboxStub
# ---------------------------------------------------------------------------


class TestParseInboxStub:
    def test_valid_stub(self, stub_file: Path):
        result = parse_inbox_stub(stub_file)
        assert result is not None
        assert result.doi == "10.1007/s11357-025-01840-1"
        assert result.title == "Test paper title"
        assert result.authors == "Smith A, Jones B"
        assert result.journal == "Nature"
        assert result.year == "2025"
        assert result.lab == "Test Lab"

    def test_non_import_type(self, inbox_dir: Path):
        p = inbox_dir / "non-import.md"
        p.write_text(_NON_IMPORT_STUB)
        assert parse_inbox_stub(p) is None

    def test_no_url(self, inbox_dir: Path):
        p = inbox_dir / "no-url.md"
        p.write_text(_NO_URL_STUB)
        assert parse_inbox_stub(p) is None

    def test_has_abstract_already(self, inbox_dir: Path):
        p = inbox_dir / "has-abstract.md"
        p.write_text(_HAS_ABSTRACT_STUB)
        assert parse_inbox_stub(p) is None

    def test_already_enriched(self, inbox_dir: Path):
        p = inbox_dir / "enriched.md"
        p.write_text(_ALREADY_ENRICHED_STUB)
        assert parse_inbox_stub(p) is None

    def test_malformed_yaml(self, inbox_dir: Path):
        p = inbox_dir / "bad.md"
        p.write_text(_MALFORMED_YAML_STUB)
        assert parse_inbox_stub(p) is None

    def test_nonexistent_file(self, tmp_path: Path):
        p = tmp_path / "does-not-exist.md"
        assert parse_inbox_stub(p) is None

    def test_no_frontmatter(self, inbox_dir: Path):
        p = inbox_dir / "no-fm.md"
        p.write_text("# Just a heading\n\nNo frontmatter.")
        assert parse_inbox_stub(p) is None


# ---------------------------------------------------------------------------
# TestScanInboxStubs
# ---------------------------------------------------------------------------


class TestScanInboxStubs:
    def test_finds_multiple_stubs(self, inbox_dir: Path):
        for year in [2024, 2025, 2023]:
            content = _VALID_STUB.replace("year: 2025", f"year: {year}")
            p = inbox_dir / f"{year}-paper.md"
            p.write_text(content)
        stubs = scan_inbox_stubs(inbox_dir)
        assert len(stubs) == 3
        # Sorted newest first
        assert stubs[0].year == "2025"
        assert stubs[1].year == "2024"
        assert stubs[2].year == "2023"

    def test_skips_non_stubs(self, inbox_dir: Path):
        (inbox_dir / "valid.md").write_text(_VALID_STUB)
        (inbox_dir / "non-import.md").write_text(_NON_IMPORT_STUB)
        stubs = scan_inbox_stubs(inbox_dir)
        assert len(stubs) == 1

    def test_empty_inbox(self, inbox_dir: Path):
        assert scan_inbox_stubs(inbox_dir) == []

    def test_nonexistent_directory(self, tmp_path: Path):
        assert scan_inbox_stubs(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# TestEnrichSingleDoi
# ---------------------------------------------------------------------------


class TestEnrichSingleDoi:
    def _make_stub(self, tmp_path: Path) -> StubInfo:
        p = tmp_path / "test.md"
        p.write_text(_VALID_STUB)
        return StubInfo(
            path=p,
            title="Test",
            doi="10.1234/test",
            source_url="https://doi.org/10.1234/test",
            authors="Smith A",
            journal="Nature",
            year="2025",
            lab="Test Lab",
        )

    @patch("engram_r.stub_enricher._fetch_abstract_s2")
    @patch("engram_r.stub_enricher._fetch_abstract_pubmed")
    def test_s2_success(self, mock_pubmed, mock_s2, tmp_path: Path):
        mock_s2.return_value = "Abstract from S2"
        stub = self._make_stub(tmp_path)
        result = enrich_single_doi(stub, timeout=5)
        assert result.abstract == "Abstract from S2"
        assert result.content_depth == "abstract"
        mock_pubmed.assert_not_called()

    @patch("engram_r.stub_enricher._fetch_abstract_s2")
    @patch("engram_r.stub_enricher._fetch_abstract_pubmed")
    def test_pubmed_fallback(self, mock_pubmed, mock_s2, tmp_path: Path):
        mock_s2.return_value = None
        mock_pubmed.return_value = "Abstract from PubMed"
        stub = self._make_stub(tmp_path)
        result = enrich_single_doi(stub, timeout=5)
        assert result.abstract == "Abstract from PubMed"
        assert result.content_depth == "abstract"

    @patch("engram_r.stub_enricher._fetch_abstract_s2")
    @patch("engram_r.stub_enricher._fetch_abstract_pubmed")
    def test_both_fail(self, mock_pubmed, mock_s2, tmp_path: Path):
        mock_s2.return_value = None
        mock_pubmed.return_value = None
        stub = self._make_stub(tmp_path)
        result = enrich_single_doi(stub, timeout=5)
        assert result.abstract == ""
        assert result.content_depth == "stub"
        assert any("No abstract" in e for e in result.errors)

    @patch("engram_r.stub_enricher._fetch_abstract_s2")
    @patch("engram_r.stub_enricher._fetch_abstract_pubmed")
    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_crossref_enrichment(
        self, mock_cr, mock_pubmed, mock_s2, tmp_path: Path
    ):
        mock_s2.return_value = "Abstract"
        cr_result = MagicMock()
        cr_result.citation_count = 42
        cr_result.pdf_url = "https://example.com/paper.pdf"
        mock_cr.return_value = cr_result

        stub = self._make_stub(tmp_path)
        result = enrich_single_doi(stub, timeout=5)
        assert result.citation_count == 42
        assert result.pdf_url == "https://example.com/paper.pdf"

    @patch("engram_r.stub_enricher._fetch_abstract_s2")
    @patch("engram_r.stub_enricher._fetch_abstract_pubmed")
    @patch("engram_r.crossref.fetch_crossref_metadata")
    @patch("engram_r.unpaywall.fetch_unpaywall_metadata")
    def test_unpaywall_oa_status(
        self, mock_up, mock_cr, mock_pubmed, mock_s2, tmp_path: Path, monkeypatch
    ):
        mock_s2.return_value = "Abstract"
        mock_cr.return_value = None
        up_result = MagicMock()
        up_result.is_oa = True
        up_result.pdf_url = "https://oa.example.com/paper.pdf"
        mock_up.return_value = up_result

        monkeypatch.setenv("LITERATURE_ENRICHMENT_EMAIL", "test@example.com")
        stub = self._make_stub(tmp_path)
        result = enrich_single_doi(stub, timeout=5)
        assert result.is_oa is True
        assert result.pdf_url == "https://oa.example.com/paper.pdf"

    @patch("engram_r.stub_enricher._fetch_abstract_s2")
    @patch("engram_r.stub_enricher._fetch_abstract_pubmed")
    def test_timeout_handling(self, mock_pubmed, mock_s2, tmp_path: Path):
        mock_s2.side_effect = TimeoutError("timeout")
        mock_pubmed.return_value = None

        stub = self._make_stub(tmp_path)
        # Should not raise -- errors are captured
        result = enrich_single_doi(stub, timeout=1)
        assert result.content_depth == "stub"


# ---------------------------------------------------------------------------
# TestApplyEnrichmentToStub
# ---------------------------------------------------------------------------


class TestApplyEnrichmentToStub:
    def _make_result(self, stub_path: Path) -> EnrichmentResult:
        stub = StubInfo(
            path=stub_path,
            title="Test paper title",
            doi="10.1007/s11357-025-01840-1",
            source_url="https://link.springer.com/article/10.1007/s11357-025-01840-1",
            authors="Smith A, Jones B",
            journal="Nature",
            year="2025",
            lab="Test Lab",
        )
        return EnrichmentResult(
            stub=stub,
            abstract="This is the fetched abstract.",
            citation_count=42,
            pdf_url="https://example.com/paper.pdf",
            is_oa=True,
            content_depth="abstract",
        )

    def test_adds_abstract_section(self, inbox_dir: Path):
        p = inbox_dir / "stub.md"
        p.write_text(_VALID_STUB)
        result = self._make_result(p)
        apply_enrichment_to_stub(result)

        text = p.read_text()
        assert "## Abstract" in text
        assert "This is the fetched abstract." in text

    def test_adds_content_depth_to_frontmatter(self, inbox_dir: Path):
        p = inbox_dir / "stub.md"
        p.write_text(_VALID_STUB)
        result = self._make_result(p)
        apply_enrichment_to_stub(result)

        text = p.read_text()
        fm_match = pytest.importorskip("re").match(
            r"^---\s*\n(.*?)\n---", text, pytest.importorskip("re").DOTALL
        )
        fm = yaml.safe_load(fm_match.group(1))
        assert fm["content_depth"] == "abstract"

    def test_adds_metadata_to_frontmatter(self, inbox_dir: Path):
        p = inbox_dir / "stub.md"
        p.write_text(_VALID_STUB)
        result = self._make_result(p)
        apply_enrichment_to_stub(result)

        text = p.read_text()
        import re as re_mod

        fm_match = re_mod.match(r"^---\s*\n(.*?)\n---", text, re_mod.DOTALL)
        fm = yaml.safe_load(fm_match.group(1))
        assert fm["citation_count"] == 42
        assert fm["is_oa"] is True
        assert fm["pdf_url"] == "https://example.com/paper.pdf"

    def test_preserves_existing_frontmatter(self, inbox_dir: Path):
        p = inbox_dir / "stub.md"
        p.write_text(_VALID_STUB)
        result = self._make_result(p)
        apply_enrichment_to_stub(result)

        text = p.read_text()
        import re as re_mod

        fm_match = re_mod.match(r"^---\s*\n(.*?)\n---", text, re_mod.DOTALL)
        fm = yaml.safe_load(fm_match.group(1))
        assert fm["source_type"] == "import"
        assert fm["journal"] == "Nature"
        assert fm["year"] == 2025

    def test_idempotent_second_apply(self, inbox_dir: Path):
        p = inbox_dir / "stub.md"
        p.write_text(_VALID_STUB)
        result = self._make_result(p)
        apply_enrichment_to_stub(result)
        first_text = p.read_text()

        # Apply again
        apply_enrichment_to_stub(result)
        second_text = p.read_text()

        # Abstract should appear only once
        assert second_text.count("## Abstract") == 1

    def test_stub_depth_on_failed_enrichment(self, inbox_dir: Path):
        p = inbox_dir / "stub.md"
        p.write_text(_VALID_STUB)
        stub = StubInfo(
            path=p,
            title="Test",
            doi="10.1234/test",
            source_url="https://doi.org/10.1234/test",
            authors="",
            journal="",
            year="",
            lab="",
        )
        result = EnrichmentResult(stub=stub, content_depth="stub")
        apply_enrichment_to_stub(result)

        text = p.read_text()
        import re as re_mod

        fm_match = re_mod.match(r"^---\s*\n(.*?)\n---", text, re_mod.DOTALL)
        fm = yaml.safe_load(fm_match.group(1))
        assert fm["content_depth"] == "stub"
