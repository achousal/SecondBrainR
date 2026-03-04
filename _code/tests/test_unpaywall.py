"""Tests for unpaywall module -- Unpaywall metadata enrichment."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from engram_r.unpaywall import (
    UnpaywallMetadata,
    _build_url,
    _normalize_doi,
    _parse_unpaywall_response,
    fetch_unpaywall_metadata,
)


# ---------------------------------------------------------------------------
# _normalize_doi
# ---------------------------------------------------------------------------


class TestNormalizeDoi:
    def test_strips_https_prefix(self):
        assert _normalize_doi("https://doi.org/10.1038/s41586") == "10.1038/s41586"

    def test_bare_doi_unchanged(self):
        assert _normalize_doi("10.1038/s41586") == "10.1038/s41586"

    def test_empty_string(self):
        assert _normalize_doi("") == ""


# ---------------------------------------------------------------------------
# _build_url
# ---------------------------------------------------------------------------


class TestBuildUrl:
    def test_format(self):
        url = _build_url("10.1038/s41586", email="user@example.com")
        assert url.startswith("https://api.unpaywall.org/v2/")
        assert "10.1038%2Fs41586" in url
        assert "email=user@example.com" in url

    def test_doi_slash_encoded(self):
        url = _build_url("10.1234/sub/path", email="a@b.com")
        assert "10.1234%2Fsub%2Fpath" in url


# ---------------------------------------------------------------------------
# _parse_unpaywall_response
# ---------------------------------------------------------------------------


class TestParseUnpaywallResponse:
    def test_extracts_pdf_url(self):
        data = {
            "doi": "10.1038/x",
            "is_oa": True,
            "best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"},
        }
        result = _parse_unpaywall_response(data)
        assert result.pdf_url == "https://example.com/paper.pdf"
        assert result.is_oa is True

    def test_missing_best_oa_location(self):
        data = {"doi": "10.1038/x", "is_oa": False}
        result = _parse_unpaywall_response(data)
        assert result.pdf_url == ""
        assert result.is_oa is False

    def test_best_oa_location_no_pdf(self):
        data = {
            "doi": "10.1038/x",
            "is_oa": True,
            "best_oa_location": {"url": "https://example.com/page"},
        }
        result = _parse_unpaywall_response(data)
        assert result.pdf_url == ""

    def test_best_oa_location_not_dict(self):
        data = {"doi": "10.1038/x", "is_oa": False, "best_oa_location": None}
        result = _parse_unpaywall_response(data)
        assert result.pdf_url == ""

    def test_empty_response(self):
        result = _parse_unpaywall_response({})
        assert result.doi == ""
        assert result.pdf_url == ""
        assert result.is_oa is False


# ---------------------------------------------------------------------------
# fetch_unpaywall_metadata
# ---------------------------------------------------------------------------


class TestFetchUnpaywallMetadata:
    def test_returns_none_on_empty_doi(self):
        assert fetch_unpaywall_metadata("", email="a@b.com") is None
        assert fetch_unpaywall_metadata("  ", email="a@b.com") is None

    def test_returns_none_on_missing_email(self):
        result = fetch_unpaywall_metadata("10.1038/s41586", email="")
        assert result is None

    @patch("engram_r.unpaywall.urllib.request.urlopen")
    def test_returns_none_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Connection refused")
        result = fetch_unpaywall_metadata("10.1038/s41586", email="a@b.com")
        assert result is None

    @patch("engram_r.unpaywall.urllib.request.urlopen")
    def test_strips_doi_prefix_before_lookup(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("not reached")
        fetch_unpaywall_metadata("https://doi.org/10.1038/s41586", email="a@b.com")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert "doi.org" not in req.full_url.split("unpaywall.org")[1]
        assert "10.1038%2Fs41586" in req.full_url

    def test_dataclass_fields(self):
        meta = UnpaywallMetadata(doi="10.1038/x", pdf_url="http://a.pdf", is_oa=True)
        assert meta.doi == "10.1038/x"
        assert meta.pdf_url == "http://a.pdf"
        assert meta.is_oa is True
