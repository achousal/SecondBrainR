"""Tests for PubMed module -- uses fixture XML, no network calls."""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

from engram_r.pubmed import (
    PubMedArticle,
    _parse_article,
    fetch_abstract_by_doi,
    fetch_articles,
    search_pubmed,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseArticle:
    """Test XML parsing with fixture data."""

    @pytest.fixture
    def article_elem(self):
        tree = ET.parse(FIXTURES / "sample_pubmed_response.xml")
        root = tree.getroot()
        return root.find("PubmedArticle")

    def test_parses_pmid(self, article_elem):
        article = _parse_article(article_elem)
        assert article.pmid == "12345678"

    def test_parses_title(self, article_elem):
        article = _parse_article(article_elem)
        assert "Metric_A" in article.title

    def test_parses_authors(self, article_elem):
        article = _parse_article(article_elem)
        assert len(article.authors) == 2
        assert "Benedet A" in article.authors

    def test_parses_journal(self, article_elem):
        article = _parse_article(article_elem)
        assert article.journal == "Nature Medicine"

    def test_parses_year(self, article_elem):
        article = _parse_article(article_elem)
        assert article.year == "2021"

    def test_parses_abstract(self, article_elem):
        article = _parse_article(article_elem)
        assert "Metric_A is a promising marker" in article.abstract
        assert "**BACKGROUND**" in article.abstract

    def test_parses_doi(self, article_elem):
        article = _parse_article(article_elem)
        assert article.doi == "10.1038/s41591-021-01234-5"


class TestSearchPubmed:
    """Test search with mocked HTTP."""

    @patch("engram_r.pubmed._fetch_xml")
    def test_returns_pmids(self, mock_fetch):
        xml_str = """<eSearchResult>
            <IdList>
                <Id>111</Id>
                <Id>222</Id>
            </IdList>
        </eSearchResult>"""
        mock_fetch.return_value = ET.fromstring(xml_str)
        result = search_pubmed("Metric_A test condition", max_results=5)
        assert result == ["111", "222"]

    @patch("engram_r.pubmed._fetch_xml")
    def test_empty_results(self, mock_fetch):
        xml_str = "<eSearchResult><IdList></IdList></eSearchResult>"
        mock_fetch.return_value = ET.fromstring(xml_str)
        result = search_pubmed("nonexistent query xyz")
        assert result == []


class TestFetchArticles:
    def test_empty_pmids(self):
        assert fetch_articles([]) == []

    @patch("engram_r.pubmed._fetch_xml")
    def test_fetches_and_parses(self, mock_fetch):
        tree = ET.parse(FIXTURES / "sample_pubmed_response.xml")
        mock_fetch.return_value = tree.getroot()
        articles = fetch_articles(["12345678"])
        assert len(articles) == 1
        assert articles[0].pmid == "12345678"


class TestFetchAbstractByDoi:
    """Test DOI-based abstract lookup via PubMed."""

    @patch("engram_r.pubmed.fetch_articles")
    @patch("engram_r.pubmed.urllib.request.urlopen")
    def test_returns_abstract_when_found(self, mock_urlopen, mock_fetch):
        """Finds PMID by DOI, then returns abstract from fetch_articles."""
        import io

        search_xml = (
            b"<eSearchResult><IdList><Id>99999</Id></IdList></eSearchResult>"
        )
        mock_response = io.BytesIO(search_xml)
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_urlopen.return_value.__exit__ = lambda s, *a: None

        mock_fetch.return_value = [
            PubMedArticle(pmid="99999", title="Test", abstract="Full abstract text.")
        ]

        result = fetch_abstract_by_doi("10.1234/test-doi")
        assert result == "Full abstract text."

    @patch("engram_r.pubmed.urllib.request.urlopen")
    def test_returns_none_when_no_pmid(self, mock_urlopen):
        """No PMID found for DOI returns None."""
        import io

        search_xml = b"<eSearchResult><IdList></IdList></eSearchResult>"
        mock_response = io.BytesIO(search_xml)
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_urlopen.return_value.__exit__ = lambda s, *a: None

        result = fetch_abstract_by_doi("10.1234/no-match")
        assert result is None

    @patch("engram_r.pubmed.urllib.request.urlopen")
    def test_returns_none_on_network_error(self, mock_urlopen):
        """Network error returns None gracefully."""
        mock_urlopen.side_effect = Exception("Connection refused")
        result = fetch_abstract_by_doi("10.1234/error")
        assert result is None

    @patch("engram_r.pubmed.fetch_articles")
    @patch("engram_r.pubmed.urllib.request.urlopen")
    def test_returns_none_when_article_has_no_abstract(
        self, mock_urlopen, mock_fetch
    ):
        """Article exists but has empty abstract returns None."""
        import io

        search_xml = (
            b"<eSearchResult><IdList><Id>88888</Id></IdList></eSearchResult>"
        )
        mock_response = io.BytesIO(search_xml)
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_urlopen.return_value.__exit__ = lambda s, *a: None

        mock_fetch.return_value = [
            PubMedArticle(pmid="88888", title="No Abstract Paper", abstract="")
        ]

        result = fetch_abstract_by_doi("10.1234/no-abstract")
        assert result is None
