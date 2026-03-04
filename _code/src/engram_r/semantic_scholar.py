"""Semantic Scholar search via Graph API.

Uses urllib only. Reference: https://api.semanticscholar.org/api-docs/graph
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

S2_API_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"

_FIELDS = (
    "title,abstract,authors,year,venue,journal,"
    "externalIds,citationCount,url,openAccessPdf"
)


@dataclass
class SemanticScholarArticle:
    """Parsed Semantic Scholar paper."""

    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    year: str = ""
    venue: str = ""
    doi: str = ""
    citation_count: int = 0
    url: str = ""
    pdf_url: str = ""


def search_semantic_scholar(
    query: str,
    max_results: int = 10,
) -> list[SemanticScholarArticle]:
    """Search Semantic Scholar and return parsed articles.

    Args:
        query: Free-text search query.
        max_results: Maximum number of results (API max 100).

    Returns:
        List of SemanticScholarArticle objects.
    """
    params = {
        "query": query,
        "limit": str(min(max_results, 100)),
        "fields": _FIELDS,
    }
    url = f"{S2_API_BASE}?{urllib.parse.urlencode(params)}"
    logger.info("Semantic Scholar search: %s", query)

    headers = _build_headers()
    data = _fetch_json(url, headers)

    papers = data.get("data") or []
    return [_parse_paper(p) for p in papers]


def _build_headers() -> dict[str, str]:
    """Build request headers, injecting API key if available."""
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _fetch_json(url: str, headers: dict[str, str]) -> dict:
    """Fetch URL and parse JSON response."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _parse_paper(paper: dict) -> SemanticScholarArticle:
    """Parse an S2 API paper dict into a SemanticScholarArticle."""
    # Authors: list of {"authorId": ..., "name": ...}
    authors = [a["name"] for a in (paper.get("authors") or []) if a.get("name")]

    # DOI from externalIds
    external_ids = paper.get("externalIds") or {}
    doi = external_ids.get("DOI", "")

    # Prefer journal name over venue
    journal_obj = paper.get("journal") or {}
    venue = journal_obj.get("name") or paper.get("venue") or ""

    # Open access PDF
    oa_pdf = paper.get("openAccessPdf") or {}
    pdf_url = oa_pdf.get("url", "")

    # Year as string to match PubMed/arXiv convention
    year_raw = paper.get("year")
    year = str(year_raw) if year_raw is not None else ""

    return SemanticScholarArticle(
        paper_id=paper.get("paperId", ""),
        title=paper.get("title") or "",
        authors=authors,
        abstract=paper.get("abstract") or "",
        year=year,
        venue=venue,
        doi=doi,
        citation_count=paper.get("citationCount") or 0,
        url=paper.get("url") or "",
        pdf_url=pdf_url,
    )
