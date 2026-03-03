"""OpenAlex search via REST API.

Uses urllib only. Reference: https://docs.openalex.org/api-entities/works
API key required (as of Feb 2026) via api_key query parameter.
Env var: OPENALEX_API_KEY.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

OPENALEX_API_BASE = "https://api.openalex.org/works"


@dataclass
class OpenAlexWork:
    """Parsed OpenAlex work."""

    openalex_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    year: str = ""
    journal: str = ""
    doi: str = ""
    cited_by_count: int = 0
    url: str = ""
    pdf_url: str = ""


def search_openalex(
    query: str,
    max_results: int = 10,
) -> list[OpenAlexWork]:
    """Search OpenAlex and return parsed works.

    Args:
        query: Free-text search query.
        max_results: Maximum number of results (API max 200).

    Returns:
        List of OpenAlexWork objects.
    """
    params: dict[str, str] = {
        "search": query,
        "per_page": str(min(max_results, 200)),
    }
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key

    url = f"{OPENALEX_API_BASE}?{urllib.parse.urlencode(params)}"
    logger.info("OpenAlex search: %s", query)

    data = _fetch_json(url)
    results = data.get("results") or []
    return [_parse_work(w) for w in results]


def _fetch_json(url: str) -> dict:
    """Fetch URL and parse JSON response."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """Reconstruct plaintext abstract from OpenAlex inverted index.

    The inverted index maps each word to a list of zero-based positions
    where it appears. We invert back to a word list ordered by position.
    """
    if not inverted_index:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))
    words.sort(key=lambda t: t[0])
    return " ".join(w for _, w in words)


def _parse_work(work: dict) -> OpenAlexWork:
    """Parse an OpenAlex API work dict into an OpenAlexWork."""
    # ID: strip URL prefix "https://openalex.org/W..."
    raw_id = work.get("id") or ""
    openalex_id = raw_id.replace("https://openalex.org/", "") if raw_id else ""

    # DOI: strip URL prefix "https://doi.org/..."
    raw_doi = work.get("doi") or ""
    doi = raw_doi.replace("https://doi.org/", "") if raw_doi else ""

    # Authors from authorships
    authorships = work.get("authorships") or []
    authors = []
    for authorship in authorships:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)

    # Abstract from inverted index
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

    # Year as string
    year_raw = work.get("publication_year")
    year = str(year_raw) if year_raw is not None else ""

    # Journal from primary_location
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    journal = source.get("display_name") or ""

    # PDF URL: prefer primary_location.pdf_url, fall back to open_access.oa_url
    pdf_url = primary_location.get("pdf_url") or ""
    if not pdf_url:
        open_access = work.get("open_access") or {}
        pdf_url = open_access.get("oa_url") or ""

    # Landing page URL
    url = work.get("landing_page_url") or raw_doi or ""

    return OpenAlexWork(
        openalex_id=openalex_id,
        title=work.get("title") or "",
        authors=authors,
        abstract=abstract,
        year=year,
        journal=journal,
        doi=doi,
        cited_by_count=work.get("cited_by_count") or 0,
        url=url,
        pdf_url=pdf_url,
    )
