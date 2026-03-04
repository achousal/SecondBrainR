"""Tests for crossref module -- CrossRef metadata enrichment."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from engram_r.crossref import (
    CrossRefMetadata,
    _build_url,
    _normalize_doi,
    _parse_crossref_response,
    fetch_crossref_metadata,
)


# ---------------------------------------------------------------------------
# _normalize_doi
# ---------------------------------------------------------------------------


class TestNormalizeDoi:
    def test_strips_https_prefix(self):
        assert _normalize_doi("https://doi.org/10.1038/s41586") == "10.1038/s41586"

    def test_strips_http_prefix(self):
        assert _normalize_doi("http://doi.org/10.1038/s41586") == "10.1038/s41586"

    def test_strips_dx_prefix(self):
        assert _normalize_doi("https://dx.doi.org/10.1038/s41586") == "10.1038/s41586"

    def test_bare_doi_unchanged(self):
        assert _normalize_doi("10.1038/s41586") == "10.1038/s41586"

    def test_empty_string(self):
        assert _normalize_doi("") == ""


# ---------------------------------------------------------------------------
# _build_url
# ---------------------------------------------------------------------------


class TestBuildUrl:
    def test_basic_url(self):
        url = _build_url("10.1038/s41586", email="")
        assert url == "https://api.crossref.org/works/10.1038%2Fs41586"

    def test_mailto_included(self):
        url = _build_url("10.1038/s41586", email="user@example.com")
        assert "mailto=user@example.com" in url

    def test_doi_slash_encoded(self):
        url = _build_url("10.1234/sub/path", email="")
        assert "10.1234%2Fsub%2Fpath" in url


# ---------------------------------------------------------------------------
# _parse_crossref_response
# ---------------------------------------------------------------------------


class TestParseCrossrefResponse:
    def test_extracts_citation_count(self):
        data = {"message": {"DOI": "10.1038/x", "is-referenced-by-count": 42}}
        result = _parse_crossref_response(data)
        assert result.citation_count == 42

    def test_extracts_pdf_url(self):
        data = {
            "message": {
                "DOI": "10.1038/x",
                "link": [
                    {
                        "URL": "https://example.com/paper.pdf",
                        "content-type": "application/pdf",
                        "content-version": "vor",
                    }
                ],
            }
        }
        result = _parse_crossref_response(data)
        assert result.pdf_url == "https://example.com/paper.pdf"

    def test_prefers_vor_pdf(self):
        data = {
            "message": {
                "DOI": "10.1038/x",
                "link": [
                    {
                        "URL": "https://example.com/am.pdf",
                        "content-type": "application/pdf",
                        "content-version": "am",
                    },
                    {
                        "URL": "https://example.com/vor.pdf",
                        "content-type": "application/pdf",
                        "content-version": "vor",
                    },
                ],
            }
        }
        result = _parse_crossref_response(data)
        assert result.pdf_url == "https://example.com/vor.pdf"

    def test_missing_citation_count(self):
        data = {"message": {"DOI": "10.1038/x"}}
        result = _parse_crossref_response(data)
        assert result.citation_count is None

    def test_missing_links(self):
        data = {"message": {"DOI": "10.1038/x"}}
        result = _parse_crossref_response(data)
        assert result.pdf_url == ""

    def test_non_pdf_links_ignored(self):
        data = {
            "message": {
                "DOI": "10.1038/x",
                "link": [
                    {
                        "URL": "https://example.com/page",
                        "content-type": "text/html",
                        "content-version": "vor",
                    }
                ],
            }
        }
        result = _parse_crossref_response(data)
        assert result.pdf_url == ""

    def test_empty_message(self):
        data = {"message": {}}
        result = _parse_crossref_response(data)
        assert result.doi == ""
        assert result.citation_count is None
        assert result.pdf_url == ""


# ---------------------------------------------------------------------------
# fetch_crossref_metadata
# ---------------------------------------------------------------------------


class TestFetchCrossrefMetadata:
    def test_returns_none_on_empty_doi(self):
        assert fetch_crossref_metadata("") is None
        assert fetch_crossref_metadata("  ") is None

    @patch("engram_r.crossref.urllib.request.urlopen")
    def test_returns_none_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Connection refused")
        result = fetch_crossref_metadata("10.1038/s41586")
        assert result is None

    @patch("engram_r.crossref.urllib.request.urlopen")
    def test_strips_doi_prefix_before_lookup(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("not reached")
        fetch_crossref_metadata("https://doi.org/10.1038/s41586")
        # Verify the URL was built with normalized DOI
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert "doi.org" not in req.full_url
        assert "10.1038%2Fs41586" in req.full_url

    def test_dataclass_fields(self):
        meta = CrossRefMetadata(doi="10.1038/x", citation_count=5, pdf_url="http://a.pdf")
        assert meta.doi == "10.1038/x"
        assert meta.citation_count == 5
        assert meta.pdf_url == "http://a.pdf"
