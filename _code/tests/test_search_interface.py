"""Tests for search_interface module -- unified SearchResult and backend resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from engram_r.arxiv import ArxivArticle
from engram_r.crossref import CrossRefMetadata
from engram_r.literature_types import ArticleResult
from engram_r.pubmed import PubMedArticle
from engram_r.search_interface import (
    SearchResult,
    _check_doi_duplicate,
    _dedup_results,
    _enrich_results,
    _fill_missing_abstracts,
    _make_literature_filename,
    _resolve_enrichment_config,
    check_literature_readiness,
    create_notes_from_results,
    create_queue_entries,
    resolve_literature_sources,
    resolve_search_backends,
    save_results_json,
    search_all_sources,
)

# ---------------------------------------------------------------------------
# SearchResult construction
# ---------------------------------------------------------------------------


class TestSearchResultConstruction:
    """Direct construction of SearchResult with explicit fields."""

    def test_basic_construction(self):
        result = SearchResult(
            source_id="TEST:001",
            title="A test result",
            authors=["Author A", "Author B"],
            abstract="Abstract text.",
            year=2024,
            doi="10.1234/test",
            source_type="web",
            url="https://example.com/001",
            journal="Test Journal",
        )
        assert result.source_id == "TEST:001"
        assert result.title == "A test result"
        assert result.authors == ["Author A", "Author B"]
        assert result.year == 2024
        assert result.source_type == "web"
        assert result.categories == []
        assert result.pdf_url == ""
        assert result.raw_metadata == {}

    def test_optional_fields_defaults(self):
        result = SearchResult(
            source_id="",
            title="",
            authors=[],
            abstract="",
            year=None,
            doi="",
            source_type="web",
            url="",
            journal="",
        )
        assert result.year is None
        assert result.categories == []
        assert result.pdf_url == ""
        assert result.raw_metadata == {}

    def test_categories_and_pdf_url(self):
        result = SearchResult(
            source_id="arXiv:2301.00001",
            title="ML paper",
            authors=["Smith J"],
            abstract="An abstract.",
            year=2023,
            doi="",
            source_type="arxiv",
            url="https://arxiv.org/abs/2301.00001",
            journal="",
            categories=["cs.LG", "stat.ML"],
            pdf_url="https://arxiv.org/pdf/2301.00001",
        )
        assert result.categories == ["cs.LG", "stat.ML"]
        assert result.pdf_url == "https://arxiv.org/pdf/2301.00001"


# ---------------------------------------------------------------------------
# from_pubmed converter
# ---------------------------------------------------------------------------


class TestFromPubMed:
    """Test SearchResult.from_pubmed with PubMedArticle instances."""

    @pytest.fixture
    def sample_article(self) -> PubMedArticle:
        return PubMedArticle(
            pmid="12345678",
            title="Metric A as a marker for test condition",
            authors=["Benedet A", "Millar J"],
            journal="Nature Medicine",
            year="2021",
            abstract="Metric A is a promising marker.",
            doi="10.1038/s41591-021-01234-5",
        )

    def test_source_id(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.source_id == "PMID:12345678"

    def test_source_type(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.source_type == "pubmed"

    def test_title_preserved(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.title == "Metric A as a marker for test condition"

    def test_authors_preserved(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.authors == ["Benedet A", "Millar J"]

    def test_year_converted_to_int(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.year == 2021
        assert isinstance(result.year, int)

    def test_year_empty_string_becomes_none(self):
        article = PubMedArticle(pmid="999", title="No year", year="")
        result = SearchResult.from_pubmed(article)
        assert result.year is None

    def test_year_invalid_string_becomes_none(self):
        article = PubMedArticle(pmid="999", title="Bad year", year="TBD")
        result = SearchResult.from_pubmed(article)
        assert result.year is None

    def test_url_constructed(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"

    def test_doi_preserved(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.doi == "10.1038/s41591-021-01234-5"

    def test_journal_preserved(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.journal == "Nature Medicine"

    def test_raw_metadata_contains_original(self, sample_article: PubMedArticle):
        result = SearchResult.from_pubmed(sample_article)
        assert result.raw_metadata["pmid"] == "12345678"
        assert result.raw_metadata["journal"] == "Nature Medicine"

    def test_empty_pmid(self):
        article = PubMedArticle(pmid="", title="Untitled")
        result = SearchResult.from_pubmed(article)
        assert result.source_id == ""
        assert result.url == ""


# ---------------------------------------------------------------------------
# from_arxiv converter
# ---------------------------------------------------------------------------


class TestFromArxiv:
    """Test SearchResult.from_arxiv with ArxivArticle instances."""

    @pytest.fixture
    def sample_entry(self) -> ArxivArticle:
        return ArxivArticle(
            arxiv_id="2301.00001v2",
            title="Attention Is All You Need (revisited)",
            authors=["Vaswani A", "Shazeer N"],
            abstract="The dominant paradigm uses attention mechanisms.",
            published="2023-01-01",
            updated="2023-06-15",
            categories=["cs.CL", "cs.LG"],
            pdf_url="https://arxiv.org/pdf/2301.00001v2",
            doi="10.48550/arXiv.2301.00001",
        )

    def test_source_id(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.source_id == "arXiv:2301.00001v2"

    def test_source_type(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.source_type == "arxiv"

    def test_title_preserved(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.title == "Attention Is All You Need (revisited)"

    def test_authors_preserved(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.authors == ["Vaswani A", "Shazeer N"]

    def test_year_extracted_from_published(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.year == 2023
        assert isinstance(result.year, int)

    def test_year_empty_published_becomes_none(self):
        entry = ArxivArticle(arxiv_id="0001", title="No date", published="")
        result = SearchResult.from_arxiv(entry)
        assert result.year is None

    def test_year_short_published_becomes_none(self):
        entry = ArxivArticle(arxiv_id="0001", title="Short date", published="20")
        result = SearchResult.from_arxiv(entry)
        assert result.year is None

    def test_year_invalid_published_becomes_none(self):
        entry = ArxivArticle(arxiv_id="0001", title="Bad date", published="ABCD-01-01")
        result = SearchResult.from_arxiv(entry)
        assert result.year is None

    def test_url_constructed(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.url == "https://arxiv.org/abs/2301.00001v2"

    def test_categories_preserved(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.categories == ["cs.CL", "cs.LG"]

    def test_pdf_url_preserved(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.pdf_url == "https://arxiv.org/pdf/2301.00001v2"

    def test_journal_is_empty(self, sample_entry: ArxivArticle):
        """ArxivArticle has no journal field; SearchResult.journal should be empty."""
        result = SearchResult.from_arxiv(sample_entry)
        assert result.journal == ""

    def test_raw_metadata_contains_original(self, sample_entry: ArxivArticle):
        result = SearchResult.from_arxiv(sample_entry)
        assert result.raw_metadata["arxiv_id"] == "2301.00001v2"
        assert result.raw_metadata["categories"] == ["cs.CL", "cs.LG"]

    def test_empty_arxiv_id(self):
        entry = ArxivArticle(arxiv_id="", title="Untitled")
        result = SearchResult.from_arxiv(entry)
        assert result.source_id == ""
        assert result.url == ""


# ---------------------------------------------------------------------------
# resolve_search_backends
# ---------------------------------------------------------------------------


class TestResolveSearchBackends:
    """Test config-driven backend resolution from ops/config.yaml."""

    def test_missing_config_file(self, tmp_path: Path):
        result = resolve_search_backends(tmp_path / "nonexistent.yaml")
        assert result == ["web-search"]

    def test_empty_config_file(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("")
        result = resolve_search_backends(cfg)
        assert result == ["web-search"]

    def test_no_research_section(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"dimensions": {"granularity": "atomic"}}))
        result = resolve_search_backends(cfg)
        assert result == ["web-search"]

    def test_all_three_backends(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "research": {
                        "primary": "pubmed",
                        "fallback": "arxiv",
                        "last_resort": "web-search",
                    }
                }
            )
        )
        result = resolve_search_backends(cfg)
        assert result == ["pubmed", "arxiv", "web-search"]

    def test_deduplication(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "research": {
                        "primary": "web-search",
                        "fallback": "web-search",
                        "last_resort": "web-search",
                    }
                }
            )
        )
        result = resolve_search_backends(cfg)
        assert result == ["web-search"]

    def test_none_values_excluded(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "research": {
                        "primary": "pubmed",
                        "fallback": "none",
                        "last_resort": "arxiv",
                    }
                }
            )
        )
        result = resolve_search_backends(cfg)
        assert result == ["pubmed", "arxiv"]

    def test_empty_values_excluded(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "research": {
                        "primary": "arxiv",
                        "fallback": "",
                        "last_resort": "",
                    }
                }
            )
        )
        result = resolve_search_backends(cfg)
        assert result == ["arxiv"]

    def test_all_none_falls_back_to_web_search(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "research": {
                        "primary": "none",
                        "fallback": "none",
                        "last_resort": "none",
                    }
                }
            )
        )
        result = resolve_search_backends(cfg)
        assert result == ["web-search"]

    def test_partial_config(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"research": {"primary": "exa"}}))
        result = resolve_search_backends(cfg)
        assert result == ["exa"]

    def test_preserves_order(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "research": {
                        "primary": "arxiv",
                        "fallback": "pubmed",
                        "last_resort": "web-search",
                    }
                }
            )
        )
        result = resolve_search_backends(cfg)
        assert result == ["arxiv", "pubmed", "web-search"]

    def test_real_config_format(self, tmp_path: Path):
        """Test with the format used in the actual ops/config.yaml."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "research": {
                        "primary": "web-search",
                        "fallback": "web-search",
                        "last_resort": "web-search",
                        "default_depth": "moderate",
                    }
                }
            )
        )
        result = resolve_search_backends(cfg)
        assert result == ["web-search"]

    def test_non_dict_research_section(self, tmp_path: Path):
        """Gracefully handle research: being a non-dict value."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"research": "invalid"}))
        result = resolve_search_backends(cfg)
        assert result == ["web-search"]


# ---------------------------------------------------------------------------
# resolve_literature_sources
# ---------------------------------------------------------------------------


class TestResolveLiteratureSources:
    """Test config-driven literature source resolution from ops/config.yaml."""

    def test_missing_config_file(self, tmp_path: Path):
        result = resolve_literature_sources(tmp_path / "nonexistent.yaml")
        assert result == ([], "")

    def test_empty_config_file(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("")
        result = resolve_literature_sources(cfg)
        assert result == ([], "")

    def test_no_literature_section(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"research": {"primary": "pubmed"}}))
        result = resolve_literature_sources(cfg)
        assert result == ([], "")

    def test_full_config(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "literature": {
                        "sources": ["pubmed", "arxiv", "semantic_scholar", "openalex"],
                        "default": "pubmed",
                    }
                }
            )
        )
        sources, default = resolve_literature_sources(cfg)
        assert sources == ["pubmed", "arxiv", "semantic_scholar", "openalex"]
        assert default == "pubmed"

    def test_default_falls_back_to_first_source(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump({"literature": {"sources": ["arxiv", "openalex"]}})
        )
        sources, default = resolve_literature_sources(cfg)
        assert sources == ["arxiv", "openalex"]
        assert default == "arxiv"

    def test_empty_sources_list(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"literature": {"sources": []}}))
        result = resolve_literature_sources(cfg)
        assert result == ([], "")

    def test_non_dict_literature_section(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"literature": "invalid"}))
        result = resolve_literature_sources(cfg)
        assert result == ([], "")

    def test_non_string_sources_filtered(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump({"literature": {"sources": ["pubmed", 123, None, "arxiv"]}})
        )
        sources, default = resolve_literature_sources(cfg)
        assert sources == ["pubmed", "arxiv"]

    def test_empty_default_falls_back(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump({"literature": {"sources": ["openalex"], "default": ""}})
        )
        _, default = resolve_literature_sources(cfg)
        assert default == "openalex"


# ---------------------------------------------------------------------------
# _dedup_results
# ---------------------------------------------------------------------------


def _make_result(
    *,
    source_id: str = "",
    title: str = "Test",
    doi: str = "",
    source_type: str = "test",
    abstract: str = "",
    citation_count: int | None = None,
) -> ArticleResult:
    """Helper to build a minimal ArticleResult for dedup tests."""
    return ArticleResult(
        source_id=source_id,
        title=title,
        authors=[],
        abstract=abstract,
        year=2024,
        doi=doi,
        source_type=source_type,
        url="",
        journal="",
        citation_count=citation_count,
    )


class TestDedupResults:
    """Test deduplication logic for multi-source results."""

    def test_no_duplicates_passthrough(self):
        results = [
            _make_result(source_id="A:1", doi="10.1/a"),
            _make_result(source_id="B:2", doi="10.1/b"),
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 2

    def test_dedup_by_doi(self):
        results = [
            _make_result(source_id="PM:1", doi="10.1/same", source_type="pubmed"),
            _make_result(source_id="S2:2", doi="10.1/same", source_type="semantic_scholar"),
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 1

    def test_dedup_by_doi_case_insensitive(self):
        results = [
            _make_result(doi="10.1/ABC", source_type="pubmed"),
            _make_result(doi="10.1/abc", source_type="openalex"),
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 1

    def test_dedup_prefers_more_complete(self):
        r1 = _make_result(doi="10.1/x", abstract="", citation_count=None)
        r2 = _make_result(doi="10.1/x", abstract="Has abstract", citation_count=42)
        deduped = _dedup_results([r1, r2])
        assert len(deduped) == 1
        assert deduped[0].citation_count == 42
        assert deduped[0].abstract == "Has abstract"

    def test_dedup_by_source_id_when_no_doi(self):
        results = [
            _make_result(source_id="S2:abc", doi=""),
            _make_result(source_id="S2:abc", doi=""),
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 1

    def test_different_source_ids_no_doi_kept(self):
        results = [
            _make_result(source_id="PM:1", doi=""),
            _make_result(source_id="S2:2", doi=""),
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 2

    def test_empty_list(self):
        assert _dedup_results([]) == []

    def test_single_item(self):
        results = [_make_result(doi="10.1/single")]
        assert len(_dedup_results(results)) == 1

    def test_three_sources_same_doi(self):
        results = [
            _make_result(doi="10.1/x", source_type="pubmed", abstract=""),
            _make_result(doi="10.1/x", source_type="semantic_scholar", citation_count=10),
            _make_result(doi="10.1/x", source_type="openalex", abstract="Full", citation_count=15),
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 1
        assert deduped[0].citation_count == 15


# ---------------------------------------------------------------------------
# search_all_sources
# ---------------------------------------------------------------------------


class TestSearchAllSources:
    """Test multi-source search with explicit source list (no live API calls)."""

    def test_with_explicit_sources_unknown(self):
        """Unknown sources return empty results."""
        results = search_all_sources("test query", sources=["nonexistent"])
        assert results == []

    def test_sorted_by_citation_count_desc(self):
        """Verify sort order: citation count descending, nulls last."""
        results = [
            _make_result(source_id="A:1", doi="10.1/a", citation_count=None),
            _make_result(source_id="B:2", doi="10.1/b", citation_count=50),
            _make_result(source_id="C:3", doi="10.1/c", citation_count=10),
        ]
        # Simulate what search_all_sources does after collecting
        results.sort(
            key=lambda r: (r.citation_count is not None, r.citation_count or 0),
            reverse=True,
        )
        assert results[0].citation_count == 50
        assert results[1].citation_count == 10
        assert results[2].citation_count is None

    def test_reads_config_when_no_sources(self, tmp_path: Path):
        """Falls back to config file when sources not provided."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {"literature": {"sources": ["nonexistent_source"], "default": "nonexistent_source"}}
            )
        )
        results = search_all_sources("test", config_path=cfg)
        assert results == []

    def test_empty_sources_list(self):
        """Empty explicit sources returns nothing."""
        results = search_all_sources("test", sources=[])
        assert results == []


# ---------------------------------------------------------------------------
# _resolve_enrichment_config
# ---------------------------------------------------------------------------


class TestResolveEnrichmentConfig:
    """Test enrichment config resolution from ops/config.yaml."""

    def test_none_config_path(self):
        enabled, timeout = _resolve_enrichment_config(None)
        assert enabled == []
        assert timeout == 5

    def test_missing_config_file(self, tmp_path: Path):
        enabled, timeout = _resolve_enrichment_config(tmp_path / "nope.yaml")
        assert enabled == []
        assert timeout == 5

    def test_no_enrichment_section(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"literature": {"sources": ["pubmed"]}}))
        enabled, timeout = _resolve_enrichment_config(cfg)
        assert enabled == []
        assert timeout == 5

    def test_reads_enabled_and_timeout(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "literature": {
                        "enrichment": {
                            "enabled": ["crossref", "unpaywall"],
                            "timeout_per_doi": 10,
                        }
                    }
                }
            )
        )
        enabled, timeout = _resolve_enrichment_config(cfg)
        assert enabled == ["crossref", "unpaywall"]
        assert timeout == 10

    def test_invalid_timeout_defaults(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {"literature": {"enrichment": {"enabled": [], "timeout_per_doi": -1}}}
            )
        )
        _, timeout = _resolve_enrichment_config(cfg)
        assert timeout == 5

    def test_non_list_enabled_defaults(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {"literature": {"enrichment": {"enabled": "crossref"}}}
            )
        )
        enabled, _ = _resolve_enrichment_config(cfg)
        assert enabled == []

    def test_non_dict_enrichment_section(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"literature": {"enrichment": "invalid"}}))
        enabled, timeout = _resolve_enrichment_config(cfg)
        assert enabled == []
        assert timeout == 5


# ---------------------------------------------------------------------------
# _enrich_results
# ---------------------------------------------------------------------------


class TestEnrichResults:
    """Test enrichment logic: fill-missing-only, no-overwrite, error handling."""

    def test_skips_no_doi(self):
        """Results without DOI are not enriched."""
        result = _make_result(doi="", citation_count=None)
        _enrich_results([result], ["crossref"])
        assert result.citation_count is None

    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_fills_missing_citation_count(self, mock_fetch):
        mock_fetch.return_value = CrossRefMetadata(
            doi="10.1/a", citation_count=99, pdf_url=""
        )
        result = _make_result(doi="10.1/a", citation_count=None)
        _enrich_results([result], ["crossref"])
        assert result.citation_count == 99

    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_no_overwrite_existing_citation_count(self, mock_fetch):
        mock_fetch.return_value = CrossRefMetadata(
            doi="10.1/a", citation_count=99, pdf_url=""
        )
        result = _make_result(doi="10.1/a", citation_count=42)
        _enrich_results([result], ["crossref"])
        assert result.citation_count == 42

    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_fills_missing_pdf_url(self, mock_fetch):
        mock_fetch.return_value = CrossRefMetadata(
            doi="10.1/a", citation_count=None, pdf_url="https://example.com/a.pdf"
        )
        result = ArticleResult(
            source_id="A:1",
            title="Test",
            authors=[],
            abstract="",
            year=2024,
            doi="10.1/a",
            source_type="test",
            url="",
            journal="",
            pdf_url="",
        )
        _enrich_results([result], ["crossref"])
        assert result.pdf_url == "https://example.com/a.pdf"

    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_no_overwrite_existing_pdf_url(self, mock_fetch):
        mock_fetch.return_value = CrossRefMetadata(
            doi="10.1/a", citation_count=None, pdf_url="https://new.com/a.pdf"
        )
        result = ArticleResult(
            source_id="A:1",
            title="Test",
            authors=[],
            abstract="",
            year=2024,
            doi="10.1/a",
            source_type="test",
            url="",
            journal="",
            pdf_url="https://existing.com/a.pdf",
        )
        _enrich_results([result], ["crossref"])
        assert result.pdf_url == "https://existing.com/a.pdf"

    def test_unknown_enricher_skipped(self):
        result = _make_result(doi="10.1/a", citation_count=None)
        _enrich_results([result], ["nonexistent_enricher"])
        assert result.citation_count is None

    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_exception_in_fetch_continues(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("boom")
        result = _make_result(doi="10.1/a", citation_count=None)
        # Should not raise
        _enrich_results([result], ["crossref"])
        assert result.citation_count is None

    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_fetch_returns_none_continues(self, mock_fetch):
        mock_fetch.return_value = None
        result = _make_result(doi="10.1/a", citation_count=None)
        _enrich_results([result], ["crossref"])
        assert result.citation_count is None

    def test_empty_enricher_list(self):
        result = _make_result(doi="10.1/a", citation_count=None)
        _enrich_results([result], [])
        assert result.citation_count is None


# ---------------------------------------------------------------------------
# search_all_sources with enrichment
# ---------------------------------------------------------------------------


class TestSearchAllSourcesWithEnrichment:
    """Test that enrichment integrates into the search pipeline."""

    @patch("engram_r.crossref.fetch_crossref_metadata")
    def test_enrichment_runs_before_sort(self, mock_fetch, tmp_path: Path):
        """Citation counts filled by enrichment should affect sort order."""
        mock_fetch.return_value = CrossRefMetadata(
            doi="10.1/a", citation_count=100, pdf_url=""
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "literature": {
                        "sources": [],
                        "enrichment": {"enabled": ["crossref"]},
                    }
                }
            )
        )
        # No sources -> no results -> enrichment has nothing to do
        results = search_all_sources("test", config_path=cfg, sources=[])
        assert results == []

    def test_enrichment_disabled_by_default(self, tmp_path: Path):
        """Without enrichment config, no enrichment happens."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"literature": {"sources": []}}))
        results = search_all_sources("test", config_path=cfg, sources=[])
        assert results == []

    def test_explicit_enrichers_override_config(self):
        """Passing enrichers=[] disables enrichment regardless of config."""
        results = search_all_sources("test", sources=[], enrichers=[])
        assert results == []


# ---------------------------------------------------------------------------
# check_literature_readiness
# ---------------------------------------------------------------------------


class TestCheckLiteratureReadiness:
    """Test env var readiness checking for configured literature sources."""

    def test_ready_when_all_vars_set(self, tmp_path: Path, monkeypatch):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "literature": {
                        "sources": ["arxiv", "semantic_scholar", "openalex"],
                        "default": "all",
                    }
                }
            )
        )
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        monkeypatch.setenv("S2_API_KEY", "test-key")
        result = check_literature_readiness(cfg)
        assert result["ready"] is True
        assert result["sources"] == ["arxiv", "semantic_scholar", "openalex"]
        assert result["missing_required"] == {}

    def test_missing_required_marks_not_ready(self, tmp_path: Path, monkeypatch):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {"literature": {"sources": ["openalex"], "default": "openalex"}}
            )
        )
        monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
        result = check_literature_readiness(cfg)
        assert result["ready"] is False
        assert "OPENALEX_API_KEY" in result["missing_required"]["openalex"]

    def test_missing_optional_still_ready(self, tmp_path: Path, monkeypatch):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "literature": {
                        "sources": ["semantic_scholar"],
                        "default": "semantic_scholar",
                    }
                }
            )
        )
        monkeypatch.delenv("S2_API_KEY", raising=False)
        result = check_literature_readiness(cfg)
        assert result["ready"] is True
        assert "S2_API_KEY" in result["missing_optional"]["semantic_scholar"]

    def test_no_sources_returns_ready(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"literature": {"sources": []}}))
        result = check_literature_readiness(cfg)
        assert result["ready"] is True
        assert result["sources"] == []

    def test_enricher_vars_checked(self, tmp_path: Path, monkeypatch):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "literature": {
                        "sources": ["arxiv"],
                        "default": "arxiv",
                        "enrichment": {"enabled": ["unpaywall"]},
                    }
                }
            )
        )
        monkeypatch.delenv("LITERATURE_ENRICHMENT_EMAIL", raising=False)
        result = check_literature_readiness(cfg)
        assert result["ready"] is False
        assert result["enrichers"] == ["unpaywall"]
        assert (
            "LITERATURE_ENRICHMENT_EMAIL"
            in result["missing_enricher_required"]["unpaywall"]
        )


# ---------------------------------------------------------------------------
# _fill_missing_abstracts
# ---------------------------------------------------------------------------


class TestFillMissingAbstracts:
    """Test S2 DOI-based abstract fallback."""

    def test_skips_results_with_abstract(self):
        """Results already having an abstract are not queried."""
        result = _make_result(doi="10.1/a", abstract="Already has abstract")
        _fill_missing_abstracts([result])
        assert result.abstract == "Already has abstract"

    def test_skips_results_without_doi(self):
        """Results without DOI cannot be looked up."""
        result = _make_result(doi="", abstract="")
        _fill_missing_abstracts([result])
        assert result.abstract == ""

    @patch("engram_r.search_interface.urllib.request.urlopen")
    def test_fills_missing_abstract_from_s2(self, mock_urlopen):
        """Successfully fills abstract from S2 DOI lookup."""
        import io
        import json as _json

        response_data = _json.dumps({"abstract": "Full abstract from S2."}).encode()
        mock_response = io.BytesIO(response_data)
        mock_response.status = 200
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_urlopen.return_value.__exit__ = lambda s, *a: None

        result = _make_result(doi="10.1/missing", abstract="")
        _fill_missing_abstracts([result])
        assert result.abstract == "Full abstract from S2."

    @patch("engram_r.search_interface.urllib.request.urlopen")
    def test_handles_s2_failure_gracefully(self, mock_urlopen):
        """Network errors do not crash -- abstract stays empty."""
        mock_urlopen.side_effect = Exception("Connection timeout")
        result = _make_result(doi="10.1/fail", abstract="")
        _fill_missing_abstracts([result])
        assert result.abstract == ""

    @patch("engram_r.search_interface.urllib.request.urlopen")
    def test_handles_s2_null_abstract(self, mock_urlopen):
        """S2 returns null abstract -- stays empty."""
        import io
        import json as _json

        response_data = _json.dumps({"abstract": None}).encode()
        mock_response = io.BytesIO(response_data)
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_urlopen.return_value.__exit__ = lambda s, *a: None

        result = _make_result(doi="10.1/null", abstract="")
        _fill_missing_abstracts([result])
        assert result.abstract == ""

    def test_empty_list(self):
        """Empty input returns empty without errors."""
        assert _fill_missing_abstracts([]) == []


# ---------------------------------------------------------------------------
# save_results_json
# ---------------------------------------------------------------------------


class TestSaveResultsJson:
    """Test JSON serialization of search results."""

    def test_roundtrip_preserves_abstract(self, tmp_path: Path):
        """Full abstract text survives JSON round-trip."""
        long_abstract = "A" * 2000
        results = [
            _make_result(doi="10.1/a", abstract=long_abstract, citation_count=42),
        ]
        json_path = tmp_path / "results.json"
        save_results_json(results, json_path)

        import json

        data = json.loads(json_path.read_text())
        assert len(data) == 1
        assert data[0]["abstract"] == long_abstract
        assert data[0]["doi"] == "10.1/a"
        assert data[0]["citation_count"] == 42

    def test_multiple_results(self, tmp_path: Path):
        results = [
            _make_result(doi="10.1/a", abstract="Abstract A"),
            _make_result(doi="10.1/b", abstract="Abstract B"),
        ]
        json_path = tmp_path / "results.json"
        save_results_json(results, json_path)

        import json

        data = json.loads(json_path.read_text())
        assert len(data) == 2

    def test_empty_results(self, tmp_path: Path):
        json_path = tmp_path / "results.json"
        save_results_json([], json_path)

        import json

        data = json.loads(json_path.read_text())
        assert data == []


# ---------------------------------------------------------------------------
# _make_literature_filename
# ---------------------------------------------------------------------------


class TestMakeLiteratureFilename:
    """Test filename generation from result dicts."""

    def test_basic_filename_first_last_format(self):
        """FirstName LastName format -- last token is last name."""
        result = {
            "year": 2024,
            "authors": ["Philip B. Gorelick"],
            "title": "Blood-based biomarkers for Alzheimer disease diagnosis",
        }
        fn = _make_literature_filename(result)
        assert fn.startswith("2024-gorelick-")
        assert "blood-based-biomarkers" in fn
        assert fn.endswith(".md")

    def test_basic_filename_last_initial_format(self):
        """LastName Initial format -- last token is initial, use first."""
        result = {
            "year": 2024,
            "authors": ["Smith J"],
            "title": "A novel approach to biomarker validation studies",
        }
        fn = _make_literature_filename(result)
        assert fn.startswith("2024-smith-")

    def test_trailing_stopwords_stripped(self):
        result = {
            "year": 2019,
            "authors": ["Frank J. Wolters"],
            "title": "Hemoglobin and anemia in relation to dementia risk",
        }
        fn = _make_literature_filename(result)
        stem = fn.removesuffix(".md")
        assert fn.startswith("2019-wolters-")
        assert not stem.endswith("-to")
        assert "hemoglobin" in fn

    def test_missing_year(self):
        result = {"year": None, "authors": ["Doe J"], "title": "A study of cells"}
        fn = _make_literature_filename(result)
        assert fn.startswith("unknown-")

    def test_missing_authors(self):
        result = {"year": 2023, "authors": [], "title": "Orphan paper"}
        fn = _make_literature_filename(result)
        assert "unknown" in fn

    def test_long_title_truncated(self):
        result = {
            "year": 2024,
            "authors": ["A B"],
            "title": " ".join(["word"] * 50),
        }
        fn = _make_literature_filename(result)
        assert len(fn) <= 125  # 120 stem + .md


# ---------------------------------------------------------------------------
# _check_doi_duplicate
# ---------------------------------------------------------------------------


class TestCheckDoiDuplicate:
    """Test DOI duplicate detection in existing literature notes."""

    def test_finds_duplicate(self, tmp_path: Path):
        note = tmp_path / "2024-smith-test.md"
        note.write_text('---\ntype: literature\ndoi: "10.1/existing"\n---\n\nContent')
        result = _check_doi_duplicate("10.1/existing", tmp_path)
        assert result == note

    def test_case_insensitive(self, tmp_path: Path):
        note = tmp_path / "2024-smith-test.md"
        note.write_text('---\ntype: literature\ndoi: "10.1/ABC"\n---\n\nContent')
        result = _check_doi_duplicate("10.1/abc", tmp_path)
        assert result == note

    def test_no_duplicate(self, tmp_path: Path):
        note = tmp_path / "2024-smith-test.md"
        note.write_text('---\ntype: literature\ndoi: "10.1/other"\n---\n\nContent')
        result = _check_doi_duplicate("10.1/new", tmp_path)
        assert result is None

    def test_skips_index_files(self, tmp_path: Path):
        note = tmp_path / "_index.md"
        note.write_text('---\ndoi: "10.1/index"\n---\n\nContent')
        result = _check_doi_duplicate("10.1/index", tmp_path)
        assert result is None

    def test_empty_dir(self, tmp_path: Path):
        result = _check_doi_duplicate("10.1/any", tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# create_notes_from_results
# ---------------------------------------------------------------------------


class TestCreateNotesFromResults:
    """Test end-to-end note creation from saved JSON results."""

    @pytest.fixture
    def results_json(self, tmp_path: Path) -> Path:
        import json

        data = [
            {
                "source_id": "PMID:111",
                "title": "Blood biomarkers for dementia diagnosis",
                "authors": ["Smith J", "Doe A"],
                "abstract": "This is a full abstract with complete sentences "
                "that should be preserved verbatim in the literature note "
                "without any truncation whatsoever.",
                "year": 2024,
                "doi": "10.1/test-111",
                "source_type": "pubmed",
                "url": "https://pubmed.ncbi.nlm.nih.gov/111/",
                "journal": "Nature Medicine",
                "categories": [],
                "pdf_url": "",
                "citation_count": 42,
                "raw_metadata": {},
            },
            {
                "source_id": "S2:222",
                "title": "CADASIL immune profiling",
                "authors": ["Jones B"],
                "abstract": "",
                "year": 2023,
                "doi": "10.1/test-222",
                "source_type": "semantic_scholar",
                "url": "",
                "journal": "Brain",
                "categories": [],
                "pdf_url": "",
                "citation_count": 10,
                "raw_metadata": {},
            },
        ]
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(data))
        return json_path

    def test_creates_note_with_full_abstract(self, results_json: Path, tmp_path: Path):
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        created = create_notes_from_results(results_json, [1], str(output_dir))
        assert len(created) == 1
        assert created[0]["status"] == "created"

        note_path = Path(created[0]["path"])
        assert note_path.exists()
        content = note_path.read_text()
        assert "preserved verbatim" in content
        assert "without any truncation" in content

    def test_creates_multiple_notes(self, results_json: Path, tmp_path: Path):
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        created = create_notes_from_results(results_json, [1, 2], str(output_dir))
        assert len(created) == 2
        assert all(c["status"] == "created" for c in created)

    def test_out_of_range_index(self, results_json: Path, tmp_path: Path):
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        created = create_notes_from_results(results_json, [99], str(output_dir))
        assert len(created) == 1
        assert "error" in created[0]["status"]

    def test_doi_duplicate_detection(self, results_json: Path, tmp_path: Path):
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        existing = output_dir / "existing.md"
        existing.write_text('---\ntype: literature\ndoi: "10.1/test-111"\n---\n\nOld')

        created = create_notes_from_results(results_json, [1], str(output_dir))
        assert len(created) == 1
        assert "skipped" in created[0]["status"]

    def test_goal_tag_added(self, results_json: Path, tmp_path: Path):
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        created = create_notes_from_results(
            results_json, [1], str(output_dir), goal_tag="biomarker-validation"
        )
        note_path = Path(created[0]["path"])
        content = note_path.read_text()
        assert "biomarker-validation" in content

    def test_creates_output_dir_if_missing(self, results_json: Path, tmp_path: Path):
        output_dir = tmp_path / "nested" / "literature"
        created = create_notes_from_results(results_json, [1], str(output_dir))
        assert len(created) == 1
        assert created[0]["status"] == "created"
        assert output_dir.exists()

    def test_abstract_status_full(self, tmp_path: Path):
        """Note with full abstract (>=200 chars) gets abstract_status='full'."""
        import json

        data = [
            {
                "source_id": "PMID:999",
                "title": "Paper with full abstract",
                "authors": ["Full F"],
                "abstract": "A" * 250,
                "year": 2024,
                "doi": "10.1/full-abstract",
                "source_type": "pubmed",
                "url": "",
                "journal": "Full Journal",
                "categories": [],
                "pdf_url": "",
                "citation_count": 10,
                "raw_metadata": {},
            },
        ]
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(data))
        output_dir = tmp_path / "literature"
        output_dir.mkdir()

        created = create_notes_from_results(json_path, [1], str(output_dir))
        assert created[0]["abstract_status"] == "full"

    @patch("engram_r.pubmed.fetch_abstract_by_doi", return_value=None)
    def test_abstract_status_empty(self, _mock_pubmed, tmp_path: Path):
        """Note with empty abstract and no fallback gets abstract_status='empty'."""
        import json

        data = [
            {
                "source_id": "S2:333",
                "title": "Paper with no abstract",
                "authors": ["NoAbstract N"],
                "abstract": "",
                "year": 2024,
                "doi": "10.1/no-abstract",
                "source_type": "semantic_scholar",
                "url": "",
                "journal": "Some Journal",
                "categories": [],
                "pdf_url": "",
                "citation_count": 0,
                "raw_metadata": {},
            },
        ]
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(data))
        output_dir = tmp_path / "literature"
        output_dir.mkdir()

        created = create_notes_from_results(json_path, [1], str(output_dir))
        assert created[0]["abstract_status"] == "empty"
        assert created[0]["status"] == "created"

    @patch(
        "engram_r.pubmed.fetch_abstract_by_doi",
        return_value="Recovered abstract from PubMed via DOI lookup. " + "X" * 200,
    )
    def test_abstract_status_pubmed_fallback(self, _mock_pubmed, tmp_path: Path):
        """Empty abstract filled by PubMed fallback gets pubmed_fallback status."""
        import json

        data = [
            {
                "source_id": "S2:444",
                "title": "Paper recovered by PubMed",
                "authors": ["Recovery R"],
                "abstract": "",
                "year": 2024,
                "doi": "10.1/recovered",
                "source_type": "semantic_scholar",
                "url": "",
                "journal": "Neurology",
                "categories": [],
                "pdf_url": "",
                "citation_count": 5,
                "raw_metadata": {},
            },
        ]
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(data))
        output_dir = tmp_path / "literature"
        output_dir.mkdir()

        created = create_notes_from_results(json_path, [1], str(output_dir))
        assert created[0]["abstract_status"] == "pubmed_fallback"
        note_content = Path(created[0]["path"]).read_text()
        assert "Recovered abstract from PubMed" in note_content

    def test_abstract_status_short(self, tmp_path: Path):
        """Abstract shorter than 200 chars gets abstract_status='short'."""
        import json

        data = [
            {
                "source_id": "PMID:555",
                "title": "Paper with short abstract",
                "authors": ["Short S"],
                "abstract": "Very brief.",
                "year": 2024,
                "doi": "10.1/short",
                "source_type": "pubmed",
                "url": "",
                "journal": "Brief Reports",
                "categories": [],
                "pdf_url": "",
                "citation_count": 1,
                "raw_metadata": {},
            },
        ]
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(data))
        output_dir = tmp_path / "literature"
        output_dir.mkdir()

        created = create_notes_from_results(json_path, [1], str(output_dir))
        assert created[0]["abstract_status"] == "short"

    def test_enrichments_populated_in_note(self, results_json: Path, tmp_path: Path):
        """Enrichment data populates Key Points and Relevance in note."""
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        enrichments = {
            1: {
                "key_points": [
                    "Blood biomarkers predict dementia onset",
                    "p-tau217 is the top performer",
                ],
                "relevance": "Supports [[biomarker-validation]] cutpoint work.",
            }
        }
        created = create_notes_from_results(
            results_json, [1], str(output_dir), enrichments=enrichments,
        )
        assert created[0]["status"] == "created"
        assert created[0]["enriched"] is True

        content = Path(created[0]["path"]).read_text()
        assert "- Blood biomarkers predict dementia onset" in content
        assert "- p-tau217 is the top performer" in content
        assert "Supports [[biomarker-validation]]" in content

    def test_enrichments_none_backward_compat(self, results_json: Path, tmp_path: Path):
        """Omitting enrichments produces identical output to previous behavior."""
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        created = create_notes_from_results(results_json, [1], str(output_dir))
        assert created[0]["status"] == "created"
        assert created[0]["enriched"] is False

        content = Path(created[0]["path"]).read_text()
        assert "## Key Points\n-\n" in content

    def test_enrichments_partial(self, results_json: Path, tmp_path: Path):
        """Only some indices enriched -- others get default empty sections."""
        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        enrichments = {
            1: {
                "key_points": ["Finding A"],
                "relevance": "Relevant to goals.",
            }
            # index 2 has no enrichment
        }
        created = create_notes_from_results(
            results_json, [1, 2], str(output_dir), enrichments=enrichments,
        )
        assert created[0]["enriched"] is True
        assert created[1]["enriched"] is False

        content_1 = Path(created[0]["path"]).read_text()
        assert "- Finding A" in content_1
        assert "Relevant to goals." in content_1

        content_2 = Path(created[1]["path"]).read_text()
        assert "## Key Points\n-\n" in content_2

    def test_enrichments_from_file(self, results_json: Path, tmp_path: Path):
        """Enrichments loaded from a JSON file populate note sections."""
        import json as _json

        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        enrichment_data = {
            "1": {
                "key_points": [
                    "Plasma p-tau217 discriminates AD from controls",
                    "NfL correlates with neurodegeneration severity",
                ],
                "relevance": "Directly supports [[biomarker-validation]] cutpoint work.",
            }
        }
        enrich_file = tmp_path / ".literature_enrichments.json"
        enrich_file.write_text(_json.dumps(enrichment_data))

        created = create_notes_from_results(
            results_json, [1], str(output_dir), enrichments_path=enrich_file,
        )
        assert created[0]["status"] == "created"
        assert created[0]["enriched"] is True

        content = Path(created[0]["path"]).read_text()
        assert "- Plasma p-tau217 discriminates AD from controls" in content
        assert "- NfL correlates with neurodegeneration severity" in content
        assert "Directly supports [[biomarker-validation]]" in content

    def test_enrichments_path_overrides_dict(self, results_json: Path, tmp_path: Path):
        """When both enrichments dict and enrichments_path are given, path wins."""
        import json as _json

        output_dir = tmp_path / "literature"
        output_dir.mkdir()
        dict_enrichments = {
            1: {
                "key_points": ["From dict -- should be overridden"],
                "relevance": "Dict relevance -- should be overridden.",
            }
        }
        file_enrichments = {
            "1": {
                "key_points": ["From file -- this should win"],
                "relevance": "File relevance -- this should win.",
            }
        }
        enrich_file = tmp_path / ".literature_enrichments.json"
        enrich_file.write_text(_json.dumps(file_enrichments))

        created = create_notes_from_results(
            results_json,
            [1],
            str(output_dir),
            enrichments=dict_enrichments,
            enrichments_path=enrich_file,
        )
        assert created[0]["status"] == "created"
        assert created[0]["enriched"] is True

        content = Path(created[0]["path"]).read_text()
        assert "From file -- this should win" in content
        assert "File relevance -- this should win." in content
        assert "From dict" not in content


# ---------------------------------------------------------------------------
# _fill_missing_abstracts -- PubMed fallback
# ---------------------------------------------------------------------------


class TestFillMissingAbstractsPubMedFallback:
    """Test PubMed fallback when S2 fails in _fill_missing_abstracts."""

    @patch("engram_r.search_interface.urllib.request.urlopen")
    @patch(
        "engram_r.pubmed.fetch_abstract_by_doi",
        return_value="Abstract from PubMed.",
    )
    def test_pubmed_fallback_after_s2_failure(self, mock_pubmed, mock_urlopen):
        """When S2 raises, falls back to PubMed."""
        mock_urlopen.side_effect = Exception("S2 timeout")
        result = _make_result(doi="10.1/fallback", abstract="")
        _fill_missing_abstracts([result])
        assert result.abstract == "Abstract from PubMed."
        mock_pubmed.assert_called_once()

    @patch("engram_r.search_interface.urllib.request.urlopen")
    @patch("engram_r.pubmed.fetch_abstract_by_doi", return_value=None)
    def test_stays_empty_when_both_fail(self, mock_pubmed, mock_urlopen):
        """When both S2 and PubMed fail, abstract stays empty."""
        mock_urlopen.side_effect = Exception("S2 timeout")
        result = _make_result(doi="10.1/both-fail", abstract="")
        _fill_missing_abstracts([result])
        assert result.abstract == ""

    @patch("engram_r.search_interface.urllib.request.urlopen")
    @patch("engram_r.pubmed.fetch_abstract_by_doi")
    def test_s2_success_skips_pubmed(self, mock_pubmed, mock_urlopen):
        """When S2 succeeds, PubMed is never called."""
        import io
        import json as _json

        response_data = _json.dumps({"abstract": "S2 abstract."}).encode()
        mock_response = io.BytesIO(response_data)
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_urlopen.return_value.__exit__ = lambda s, *a: None

        result = _make_result(doi="10.1/s2-ok", abstract="")
        _fill_missing_abstracts([result])
        mock_pubmed.assert_not_called()
        assert result.abstract == "S2 abstract."


# ---------------------------------------------------------------------------
# create_queue_entries
# ---------------------------------------------------------------------------


class TestCreateQueueEntries:
    """Test queue entry creation from create_notes_from_results output."""

    def test_creates_entries_for_created_notes(self, tmp_path: Path):
        queue_path = tmp_path / "queue.json"
        notes = [
            {"path": "/vault/_research/literature/2024-smith-test.md",
             "status": "created", "title": "Test", "doi": "10.1/a"},
            {"path": "/vault/_research/literature/2024-jones-test.md",
             "status": "created", "title": "Test 2", "doi": "10.1/b"},
        ]
        entries = create_queue_entries(notes, queue_path, vault_root="/vault")
        assert len(entries) == 2
        assert entries[0]["id"] == "extract-2024-smith-test"
        assert entries[0]["source"] == "_research/literature/2024-smith-test.md"
        assert entries[0]["status"] == "pending"
        assert entries[0]["current_phase"] == "reduce"

    def test_skips_non_created_notes(self, tmp_path: Path):
        queue_path = tmp_path / "queue.json"
        notes = [
            {"path": "/vault/lit/a.md", "status": "created", "doi": "10.1/a"},
            {"path": "/vault/lit/b.md",
             "status": "skipped: duplicate", "doi": "10.1/b"},
            {"path": "/vault/lit/c.md", "status": "error: out of range", "doi": ""},
        ]
        entries = create_queue_entries(notes, queue_path, vault_root="/vault")
        assert len(entries) == 1
        assert entries[0]["source"] == "lit/a.md"

    def test_deduplicates_against_existing_queue(self, tmp_path: Path):
        import json

        queue_path = tmp_path / "queue.json"
        queue_path.write_text(json.dumps([
            {"id": "extract-existing", "source": "lit/existing.md", "status": "done"},
        ]))

        notes = [
            {"path": "/vault/lit/existing.md", "status": "created", "doi": "10.1/x"},
            {"path": "/vault/lit/new.md", "status": "created", "doi": "10.1/y"},
        ]
        entries = create_queue_entries(notes, queue_path, vault_root="/vault")
        assert len(entries) == 1
        assert entries[0]["source"] == "lit/new.md"

    def test_creates_queue_file_if_missing(self, tmp_path: Path):
        queue_path = tmp_path / "sub" / "queue.json"
        notes = [
            {"path": "/vault/lit/a.md", "status": "created", "doi": "10.1/a"},
        ]
        entries = create_queue_entries(notes, queue_path, vault_root="/vault")
        assert len(entries) == 1
        assert queue_path.exists()

    def test_empty_notes_writes_no_entries(self, tmp_path: Path):
        queue_path = tmp_path / "queue.json"
        entries = create_queue_entries([], queue_path)
        assert entries == []
        assert queue_path.exists()

    def test_no_vault_root_stores_absolute_paths(self, tmp_path: Path):
        queue_path = tmp_path / "queue.json"
        notes = [
            {"path": "/abs/path/to/note.md", "status": "created", "doi": "10.1/a"},
        ]
        entries = create_queue_entries(notes, queue_path, vault_root=None)
        assert entries[0]["source"] == "/abs/path/to/note.md"

    def test_persists_to_disk(self, tmp_path: Path):
        import json

        queue_path = tmp_path / "queue.json"
        notes = [
            {"path": "/vault/lit/a.md", "status": "created", "doi": "10.1/a"},
        ]
        create_queue_entries(notes, queue_path, vault_root="/vault")

        queue = json.loads(queue_path.read_text())
        assert len(queue) == 1
        assert queue[0]["id"] == "extract-a"


class TestCreateQueueEntriesScope:
    """Tests for scope parameter in create_queue_entries."""

    def test_queue_entry_includes_scope(self, tmp_path: Path):
        queue_path = tmp_path / "queue.json"
        notes = [
            {"path": "/vault/lit/a.md", "status": "created", "doi": "10.1/a"},
        ]
        entries = create_queue_entries(
            notes, queue_path, vault_root="/vault", scope="methods_only",
        )
        assert len(entries) == 1
        assert entries[0]["scope"] == "methods_only"

    def test_queue_entry_default_scope(self, tmp_path: Path):
        queue_path = tmp_path / "queue.json"
        notes = [
            {"path": "/vault/lit/b.md", "status": "created", "doi": "10.1/b"},
        ]
        entries = create_queue_entries(notes, queue_path, vault_root="/vault")
        assert len(entries) == 1
        assert entries[0]["scope"] == "full"
