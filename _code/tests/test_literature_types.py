"""Tests for literature_types -- ArticleResult converters and LiteratureSource Protocol."""

from __future__ import annotations

import pytest

from engram_r.literature_types import ArticleResult, LiteratureSource
from engram_r.openalex import OpenAlexWork
from engram_r.search_interface import SearchResult
from engram_r.semantic_scholar import SemanticScholarArticle

# ---------------------------------------------------------------------------
# ArticleResult identity -- SearchResult alias
# ---------------------------------------------------------------------------


class TestSearchResultAlias:
    """SearchResult imported from search_interface must be ArticleResult."""

    def test_alias_is_same_class(self):
        assert SearchResult is ArticleResult

    def test_alias_constructable(self):
        r = SearchResult(
            source_id="TEST:1",
            title="Test",
            authors=[],
            abstract="",
            year=None,
            doi="",
            source_type="test",
            url="",
            journal="",
        )
        assert isinstance(r, ArticleResult)


# ---------------------------------------------------------------------------
# citation_count field
# ---------------------------------------------------------------------------


class TestCitationCount:
    """The citation_count field defaults to None and propagates from backends."""

    def test_default_is_none(self):
        r = ArticleResult(
            source_id="",
            title="",
            authors=[],
            abstract="",
            year=None,
            doi="",
            source_type="test",
            url="",
            journal="",
        )
        assert r.citation_count is None

    def test_explicit_value(self):
        r = ArticleResult(
            source_id="",
            title="",
            authors=[],
            abstract="",
            year=None,
            doi="",
            source_type="test",
            url="",
            journal="",
            citation_count=42,
        )
        assert r.citation_count == 42


# ---------------------------------------------------------------------------
# from_semantic_scholar converter
# ---------------------------------------------------------------------------


class TestFromSemanticScholar:
    """Test ArticleResult.from_semantic_scholar with SemanticScholarArticle."""

    @pytest.fixture
    def sample_article(self) -> SemanticScholarArticle:
        return SemanticScholarArticle(
            paper_id="abc123def456",
            title="Graph neural networks for drug discovery",
            authors=["Li X", "Chen Y", "Wang Z"],
            abstract="We propose a novel GNN architecture.",
            year="2023",
            venue="Nature Machine Intelligence",
            doi="10.1038/s42256-023-00001-1",
            citation_count=150,
            url="https://www.semanticscholar.org/paper/abc123def456",
            pdf_url="https://example.com/paper.pdf",
        )

    def test_source_id(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.source_id == "S2:abc123def456"

    def test_source_type(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.source_type == "semantic_scholar"

    def test_title_preserved(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.title == "Graph neural networks for drug discovery"

    def test_authors_preserved(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.authors == ["Li X", "Chen Y", "Wang Z"]

    def test_abstract_preserved(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.abstract == "We propose a novel GNN architecture."

    def test_year_converted_to_int(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.year == 2023
        assert isinstance(result.year, int)

    def test_year_empty_string_becomes_none(self):
        article = SemanticScholarArticle(paper_id="x", title="No year", year="")
        result = ArticleResult.from_semantic_scholar(article)
        assert result.year is None

    def test_year_invalid_becomes_none(self):
        article = SemanticScholarArticle(paper_id="x", title="Bad year", year="TBD")
        result = ArticleResult.from_semantic_scholar(article)
        assert result.year is None

    def test_doi_preserved(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.doi == "10.1038/s42256-023-00001-1"

    def test_url_preserved(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.url == "https://www.semanticscholar.org/paper/abc123def456"

    def test_journal_from_venue(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.journal == "Nature Machine Intelligence"

    def test_citation_count_propagated(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.citation_count == 150

    def test_citation_count_zero_becomes_none(self):
        article = SemanticScholarArticle(
            paper_id="x", title="No cites", citation_count=0
        )
        result = ArticleResult.from_semantic_scholar(article)
        assert result.citation_count is None

    def test_pdf_url_preserved(self, sample_article: SemanticScholarArticle):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.pdf_url == "https://example.com/paper.pdf"

    def test_raw_metadata_contains_original(
        self, sample_article: SemanticScholarArticle
    ):
        result = ArticleResult.from_semantic_scholar(sample_article)
        assert result.raw_metadata["paper_id"] == "abc123def456"
        assert result.raw_metadata["citation_count"] == 150

    def test_empty_paper_id(self):
        article = SemanticScholarArticle(paper_id="", title="Untitled")
        result = ArticleResult.from_semantic_scholar(article)
        assert result.source_id == ""
        assert result.url == ""


# ---------------------------------------------------------------------------
# from_openalex converter
# ---------------------------------------------------------------------------


class TestFromOpenAlex:
    """Test ArticleResult.from_openalex with OpenAlexWork."""

    @pytest.fixture
    def sample_work(self) -> OpenAlexWork:
        return OpenAlexWork(
            openalex_id="W2741809807",
            title="The spread of true and false news online",
            authors=["Vosoughi S", "Roy D", "Aral S"],
            abstract="We investigated the spread of news stories.",
            year="2018",
            journal="Science",
            doi="10.1126/science.aap9559",
            cited_by_count=8500,
            url="https://doi.org/10.1126/science.aap9559",
            pdf_url="https://example.com/oa.pdf",
        )

    def test_source_id(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.source_id == "OpenAlex:W2741809807"

    def test_source_type(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.source_type == "openalex"

    def test_title_preserved(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.title == "The spread of true and false news online"

    def test_authors_preserved(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.authors == ["Vosoughi S", "Roy D", "Aral S"]

    def test_abstract_preserved(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.abstract == "We investigated the spread of news stories."

    def test_year_converted_to_int(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.year == 2018
        assert isinstance(result.year, int)

    def test_year_empty_becomes_none(self):
        work = OpenAlexWork(openalex_id="W1", title="No year", year="")
        result = ArticleResult.from_openalex(work)
        assert result.year is None

    def test_year_invalid_becomes_none(self):
        work = OpenAlexWork(openalex_id="W1", title="Bad year", year="unknown")
        result = ArticleResult.from_openalex(work)
        assert result.year is None

    def test_doi_preserved(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.doi == "10.1126/science.aap9559"

    def test_url_preserved(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.url == "https://doi.org/10.1126/science.aap9559"

    def test_journal_preserved(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.journal == "Science"

    def test_citation_count_propagated(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.citation_count == 8500

    def test_citation_count_zero_becomes_none(self):
        work = OpenAlexWork(openalex_id="W1", title="No cites", cited_by_count=0)
        result = ArticleResult.from_openalex(work)
        assert result.citation_count is None

    def test_pdf_url_preserved(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.pdf_url == "https://example.com/oa.pdf"

    def test_raw_metadata_contains_original(self, sample_work: OpenAlexWork):
        result = ArticleResult.from_openalex(sample_work)
        assert result.raw_metadata["openalex_id"] == "W2741809807"
        assert result.raw_metadata["cited_by_count"] == 8500

    def test_empty_openalex_id(self):
        work = OpenAlexWork(openalex_id="", title="Untitled")
        result = ArticleResult.from_openalex(work)
        assert result.source_id == ""


# ---------------------------------------------------------------------------
# LiteratureSource Protocol conformance
# ---------------------------------------------------------------------------


class _MockSource:
    """Minimal implementation satisfying the LiteratureSource Protocol."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def requires_key(self) -> bool:
        return False

    @property
    def env_var(self) -> str | None:
        return None

    def search(self, query: str, max_results: int = 10) -> list[ArticleResult]:
        return []


class TestLiteratureSourceProtocol:
    """Verify the runtime-checkable Protocol works correctly."""

    def test_mock_satisfies_protocol(self):
        source = _MockSource()
        assert isinstance(source, LiteratureSource)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), LiteratureSource)

    def test_mock_search_returns_list(self):
        source = _MockSource()
        results = source.search("test query")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_mock_metadata(self):
        source = _MockSource()
        assert source.name == "mock"
        assert source.requires_key is False
        assert source.env_var is None
