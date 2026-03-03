"""Tests for OpenAlex module -- uses mock responses, no network calls."""

import json
from unittest.mock import patch, MagicMock

import pytest

from engram_r.openalex import (
    OpenAlexWork,
    _parse_work,
    _reconstruct_abstract,
    search_openalex,
)

_SAMPLE_INVERTED_INDEX = {
    "Astrocyte": [0],
    "reactivity": [1],
    "increases": [2],
    "with": [3],
    "amyloid": [4],
    "plaque": [5],
    "density": [6],
    "in": [7],
    "AD": [8],
    "cortex.": [9],
}

_SAMPLE_WORK = {
    "id": "https://openalex.org/W2741809807",
    "title": "Marker reactivity in test condition tissue",
    "authorships": [
        {"author": {"id": "https://openalex.org/A1", "display_name": "Jane Smith"}},
        {"author": {"id": "https://openalex.org/A2", "display_name": "John Doe"}},
    ],
    "abstract_inverted_index": _SAMPLE_INVERTED_INDEX,
    "publication_year": 2023,
    "doi": "https://doi.org/10.1234/example.2023.001",
    "primary_location": {
        "source": {"display_name": "Acta Neuropathologica"},
        "pdf_url": "https://example.com/paper.pdf",
    },
    "open_access": {"oa_url": "https://example.com/oa.pdf"},
    "cited_by_count": 85,
    "landing_page_url": "https://doi.org/10.1234/example.2023.001",
}


class TestReconstructAbstract:
    def test_normal_reconstruction(self):
        result = _reconstruct_abstract(_SAMPLE_INVERTED_INDEX)
        assert result == (
            "Astrocyte reactivity increases with amyloid plaque density in AD cortex."
        )

    def test_empty_dict(self):
        assert _reconstruct_abstract({}) == ""

    def test_none_input(self):
        assert _reconstruct_abstract(None) == ""

    def test_single_word(self):
        assert _reconstruct_abstract({"hello": [0]}) == "hello"

    def test_repeated_word(self):
        result = _reconstruct_abstract({"the": [0, 2], "cat": [1]})
        assert result == "the cat the"


class TestParseWork:
    def test_parses_openalex_id(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.openalex_id == "W2741809807"

    def test_parses_title(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.title == "Marker reactivity in test condition tissue"

    def test_parses_authors(self):
        work = _parse_work(_SAMPLE_WORK)
        assert len(work.authors) == 2
        assert "Jane Smith" in work.authors
        assert "John Doe" in work.authors

    def test_parses_abstract(self):
        work = _parse_work(_SAMPLE_WORK)
        assert "Astrocyte reactivity" in work.abstract
        assert "AD cortex." in work.abstract

    def test_strips_doi_prefix(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.doi == "10.1234/example.2023.001"

    def test_strips_id_prefix(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.openalex_id == "W2741809807"

    def test_parses_year_as_string(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.year == "2023"

    def test_parses_journal(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.journal == "Acta Neuropathologica"

    def test_parses_cited_by_count(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.cited_by_count == 85

    def test_parses_pdf_url(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.pdf_url == "https://example.com/paper.pdf"

    def test_parses_landing_page_url(self):
        work = _parse_work(_SAMPLE_WORK)
        assert work.url == "https://doi.org/10.1234/example.2023.001"

    def test_handles_none_abstract(self):
        sample = {**_SAMPLE_WORK, "abstract_inverted_index": None}
        work = _parse_work(sample)
        assert work.abstract == ""

    def test_handles_none_year(self):
        sample = {**_SAMPLE_WORK, "publication_year": None}
        work = _parse_work(sample)
        assert work.year == ""

    def test_handles_none_authorships(self):
        sample = {**_SAMPLE_WORK, "authorships": None}
        work = _parse_work(sample)
        assert work.authors == []

    def test_handles_empty_authorships(self):
        sample = {**_SAMPLE_WORK, "authorships": []}
        work = _parse_work(sample)
        assert work.authors == []

    def test_skips_authors_without_name(self):
        sample = {
            **_SAMPLE_WORK,
            "authorships": [
                {"author": {"display_name": None}},
                {"author": {"display_name": "Valid Author"}},
            ],
        }
        work = _parse_work(sample)
        assert work.authors == ["Valid Author"]

    def test_handles_none_primary_location(self):
        sample = {**_SAMPLE_WORK, "primary_location": None}
        work = _parse_work(sample)
        assert work.journal == ""

    def test_falls_back_to_oa_url_for_pdf(self):
        sample = {
            **_SAMPLE_WORK,
            "primary_location": {
                "source": {"display_name": "Some Journal"},
                "pdf_url": None,
            },
        }
        work = _parse_work(sample)
        assert work.pdf_url == "https://example.com/oa.pdf"

    def test_handles_no_pdf_at_all(self):
        sample = {
            **_SAMPLE_WORK,
            "primary_location": {
                "source": {"display_name": "Some Journal"},
                "pdf_url": None,
            },
            "open_access": None,
        }
        work = _parse_work(sample)
        assert work.pdf_url == ""

    def test_handles_missing_doi(self):
        sample = {**_SAMPLE_WORK, "doi": None}
        work = _parse_work(sample)
        assert work.doi == ""

    def test_handles_missing_id(self):
        sample = {**_SAMPLE_WORK, "id": None}
        work = _parse_work(sample)
        assert work.openalex_id == ""


class TestSearchOpenAlex:
    @patch("engram_r.openalex.urllib.request.urlopen")
    def test_returns_works(self, mock_urlopen):
        response_data = json.dumps({"results": [_SAMPLE_WORK]}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_openalex("sample marker analysis", max_results=1)
        assert len(results) == 1
        assert results[0].title == "Marker reactivity in test condition tissue"

    @patch("engram_r.openalex.urllib.request.urlopen")
    def test_empty_results(self, mock_urlopen):
        response_data = json.dumps({"results": []}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_openalex("nonexistent_query_xyz", max_results=1)
        assert results == []

    @patch("engram_r.openalex.urllib.request.urlopen")
    def test_handles_null_results_field(self, mock_urlopen):
        response_data = json.dumps({"meta": {"count": 0}}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = search_openalex("nothing", max_results=1)
        assert results == []

    @patch.dict("os.environ", {"OPENALEX_API_KEY": "test-key-abc"})
    @patch("engram_r.openalex.urllib.request.urlopen")
    def test_includes_api_key_in_url(self, mock_urlopen):
        response_data = json.dumps({"results": []}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        search_openalex("test", max_results=1)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert "api_key=test-key-abc" in request_obj.full_url

    @patch.dict("os.environ", {}, clear=True)
    @patch("engram_r.openalex.urllib.request.urlopen")
    def test_no_api_key_when_env_missing(self, mock_urlopen):
        response_data = json.dumps({"results": []}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        search_openalex("test", max_results=1)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert "api_key" not in request_obj.full_url
