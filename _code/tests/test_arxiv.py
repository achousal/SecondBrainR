"""Tests for arXiv module -- uses mock responses, no network calls."""

import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import pytest

from engram_r.arxiv import ArxivArticle, _parse_entry, search_arxiv

# Minimal Atom entry for testing
_SAMPLE_ENTRY_XML = """
<entry xmlns="http://www.w3.org/2005/Atom">
  <id>http://arxiv.org/abs/2502.18864v1</id>
  <title>Towards an AI co-scientist</title>
  <author><name>Juraj Gottweis</name></author>
  <author><name>Wei-Hung Weng</name></author>
  <summary>We present an AI co-scientist system that uses multi-agent debate.</summary>
  <published>2025-02-26T00:00:00Z</published>
  <updated>2025-02-26T00:00:00Z</updated>
  <category term="cs.AI"/>
  <category term="q-bio.QM"/>
  <link title="pdf" href="http://arxiv.org/pdf/2502.18864v1" rel="related"/>
</entry>
"""

_NS = {"atom": "http://www.w3.org/2005/Atom"}


class TestParseEntry:
    @pytest.fixture
    def entry(self):
        return ET.fromstring(_SAMPLE_ENTRY_XML)

    def test_parses_id(self, entry):
        article = _parse_entry(entry)
        assert article.arxiv_id == "2502.18864v1"

    def test_parses_title(self, entry):
        article = _parse_entry(entry)
        assert article.title == "Towards an AI co-scientist"

    def test_parses_authors(self, entry):
        article = _parse_entry(entry)
        assert len(article.authors) == 2
        assert "Juraj Gottweis" in article.authors

    def test_parses_abstract(self, entry):
        article = _parse_entry(entry)
        assert "multi-agent debate" in article.abstract

    def test_parses_date(self, entry):
        article = _parse_entry(entry)
        assert article.published == "2025-02-26"

    def test_parses_categories(self, entry):
        article = _parse_entry(entry)
        assert "cs.AI" in article.categories
        assert "q-bio.QM" in article.categories

    def test_parses_pdf_url(self, entry):
        article = _parse_entry(entry)
        assert "pdf/2502.18864" in article.pdf_url


class TestSearchArxiv:
    @patch("urllib.request.urlopen")
    def test_returns_articles(self, mock_urlopen):
        response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          {_SAMPLE_ENTRY_XML}
        </feed>"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_xml.encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_arxiv("all:co-scientist", max_results=1)
        assert len(results) == 1
        assert results[0].title == "Towards an AI co-scientist"

    @patch("urllib.request.urlopen")
    def test_empty_results(self, mock_urlopen):
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_xml.encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_arxiv("nonexistent_query_xyz", max_results=1)
        assert results == []
