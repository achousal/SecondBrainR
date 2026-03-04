"""Tests for Semantic Scholar module -- uses mock responses, no network calls."""

import json
from unittest.mock import patch, MagicMock

import pytest

from engram_r.semantic_scholar import (
    SemanticScholarArticle,
    _parse_paper,
    search_semantic_scholar,
)

_SAMPLE_PAPER = {
    "paperId": "abc123def456",
    "title": "Metric A as a marker for test condition",
    "authors": [
        {"authorId": "1", "name": "Jane Smith"},
        {"authorId": "2", "name": "John Doe"},
    ],
    "abstract": "Metric A is a promising marker for test condition.",
    "year": 2024,
    "venue": "Conference on Research Methods",
    "journal": {"name": "Journal of Research Methods"},
    "externalIds": {"DOI": "10.1234/jnc.2024.001", "PubMed": "39000001"},
    "citationCount": 42,
    "url": "https://www.semanticscholar.org/paper/abc123def456",
    "openAccessPdf": {"url": "https://example.com/paper.pdf"},
}


class TestParsePaper:
    def test_parses_paper_id(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert article.paper_id == "abc123def456"

    def test_parses_title(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert article.title == "Metric A as a marker for test condition"

    def test_parses_authors(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert len(article.authors) == 2
        assert "Jane Smith" in article.authors
        assert "John Doe" in article.authors

    def test_parses_abstract(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert "Metric A" in article.abstract

    def test_parses_year_as_string(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert article.year == "2024"

    def test_prefers_journal_over_venue(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert article.venue == "Journal of Research Methods"

    def test_falls_back_to_venue_when_no_journal(self):
        paper = {**_SAMPLE_PAPER, "journal": None}
        article = _parse_paper(paper)
        assert article.venue == "Conference on Research Methods"

    def test_extracts_doi_from_external_ids(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert article.doi == "10.1234/jnc.2024.001"

    def test_parses_citation_count(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert article.citation_count == 42

    def test_parses_pdf_url(self):
        article = _parse_paper(_SAMPLE_PAPER)
        assert article.pdf_url == "https://example.com/paper.pdf"

    def test_handles_none_abstract(self):
        paper = {**_SAMPLE_PAPER, "abstract": None}
        article = _parse_paper(paper)
        assert article.abstract == ""

    def test_handles_none_year(self):
        paper = {**_SAMPLE_PAPER, "year": None}
        article = _parse_paper(paper)
        assert article.year == ""

    def test_handles_missing_open_access_pdf(self):
        paper = {**_SAMPLE_PAPER, "openAccessPdf": None}
        article = _parse_paper(paper)
        assert article.pdf_url == ""

    def test_handles_missing_external_ids(self):
        paper = {**_SAMPLE_PAPER, "externalIds": None}
        article = _parse_paper(paper)
        assert article.doi == ""

    def test_handles_empty_authors(self):
        paper = {**_SAMPLE_PAPER, "authors": []}
        article = _parse_paper(paper)
        assert article.authors == []

    def test_skips_authors_without_name(self):
        paper = {
            **_SAMPLE_PAPER,
            "authors": [{"authorId": "1", "name": None}, {"authorId": "2", "name": "Valid"}],
        }
        article = _parse_paper(paper)
        assert article.authors == ["Valid"]


class TestSearchSemanticScholar:
    @patch("engram_r.semantic_scholar.urllib.request.urlopen")
    def test_returns_articles(self, mock_urlopen):
        response_data = json.dumps({"data": [_SAMPLE_PAPER]}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_semantic_scholar("Metric A test condition", max_results=1)
        assert len(results) == 1
        assert results[0].title == "Metric A as a marker for test condition"

    @patch("engram_r.semantic_scholar.urllib.request.urlopen")
    def test_empty_results(self, mock_urlopen):
        response_data = json.dumps({"data": []}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_semantic_scholar("nonexistent_query_xyz", max_results=1)
        assert results == []

    @patch("engram_r.semantic_scholar.urllib.request.urlopen")
    def test_handles_null_data_field(self, mock_urlopen):
        response_data = json.dumps({"total": 0}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_semantic_scholar("nothing", max_results=1)
        assert results == []

    @patch.dict("os.environ", {"S2_API_KEY": "test-key-123"})
    @patch("engram_r.semantic_scholar.urllib.request.urlopen")
    def test_includes_api_key_header(self, mock_urlopen):
        response_data = json.dumps({"data": []}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        search_semantic_scholar("test", max_results=1)

        # Verify the Request object was created with the API key header
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert request_obj.get_header("X-api-key") == "test-key-123"
