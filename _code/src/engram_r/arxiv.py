"""arXiv search via Atom API.

Uses urllib only. Reference: https://info.arxiv.org/help/api/index.html
"""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

ARXIV_API_BASE = "http://export.arxiv.org/api/query"

# Atom namespace
_NS = {"atom": "http://www.w3.org/2005/Atom"}


@dataclass
class ArxivArticle:
    """Parsed arXiv article."""

    arxiv_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    published: str = ""
    updated: str = ""
    categories: list[str] = field(default_factory=list)
    pdf_url: str = ""
    doi: str = ""


def search_arxiv(
    query: str,
    max_results: int = 10,
    sort_by: str = "relevance",
    sort_order: str = "descending",
) -> list[ArxivArticle]:
    """Search arXiv and return parsed articles.

    Args:
        query: arXiv search query (supports field prefixes like 'ti:', 'au:', 'all:').
        max_results: Maximum number of results.
        sort_by: Sort criterion ('relevance', 'lastUpdatedDate', 'submittedDate').
        sort_order: 'ascending' or 'descending'.

    Returns:
        List of ArxivArticle objects.
    """
    params = {
        "search_query": query,
        "start": "0",
        "max_results": str(max_results),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_API_BASE}?{urllib.parse.urlencode(params)}"
    logger.info("arXiv search: %s", query)

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()

    root = ET.fromstring(data)
    articles = []

    for entry in root.findall("atom:entry", _NS):
        articles.append(_parse_entry(entry))

    return articles


def _parse_entry(entry: ET.Element) -> ArxivArticle:
    """Parse an Atom entry element into an ArxivArticle."""
    # ID
    id_elem = entry.find("atom:id", _NS)
    raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
    # Extract just the arXiv ID from the URL
    arxiv_id = raw_id.replace("http://arxiv.org/abs/", "")

    # Title
    title_elem = entry.find("atom:title", _NS)
    title = ""
    if title_elem is not None and title_elem.text:
        title = " ".join(title_elem.text.split())  # normalize whitespace

    # Authors
    authors = []
    for author_elem in entry.findall("atom:author", _NS):
        name_elem = author_elem.find("atom:name", _NS)
        if name_elem is not None and name_elem.text:
            authors.append(name_elem.text.strip())

    # Abstract
    summary_elem = entry.find("atom:summary", _NS)
    abstract = ""
    if summary_elem is not None and summary_elem.text:
        abstract = " ".join(summary_elem.text.split())

    # Dates
    published_elem = entry.find("atom:published", _NS)
    published = ""
    if published_elem is not None and published_elem.text:
        published = published_elem.text.strip()[:10]  # YYYY-MM-DD

    updated_elem = entry.find("atom:updated", _NS)
    updated = ""
    if updated_elem is not None and updated_elem.text:
        updated = updated_elem.text.strip()[:10]

    # Categories
    categories = []
    for cat_elem in entry.findall("atom:category", _NS):
        term = cat_elem.get("term", "")
        if term:
            categories.append(term)

    # PDF link
    pdf_url = ""
    for link_elem in entry.findall("atom:link", _NS):
        if link_elem.get("title") == "pdf":
            pdf_url = link_elem.get("href", "")
            break

    # DOI
    doi = ""
    doi_elem = entry.find("{http://arxiv.org/schemas/atom}doi")
    if doi_elem is not None and doi_elem.text:
        doi = doi_elem.text.strip()

    return ArxivArticle(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        published=published,
        updated=updated,
        categories=categories,
        pdf_url=pdf_url,
        doi=doi,
    )
