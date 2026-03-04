"""CrossRef metadata enrichment via REST API.

Enrichment layer -- fetches citation counts and PDF URLs by DOI.
Not a search backend; post-processes results from other sources.

API: https://api.crossref.org/works/{doi}
No API key required. mailto parameter enables polite pool (faster).
Env var: LITERATURE_ENRICHMENT_EMAIL (shared with Unpaywall).
"""

from __future__ import annotations

import contextlib
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

CROSSREF_API_BASE = "https://api.crossref.org/works"


@dataclass
class CrossRefMetadata:
    """Metadata fetched from CrossRef for a single DOI."""

    doi: str
    citation_count: int | None = None
    pdf_url: str = ""


def _normalize_doi(doi: str) -> str:
    """Strip common URL prefixes from a DOI string."""
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
        if doi.startswith(prefix):
            return doi[len(prefix) :]
    return doi


def _build_url(doi: str, email: str = "") -> str:
    """Build CrossRef API URL for a DOI lookup."""
    encoded_doi = urllib.parse.quote(doi, safe="")
    url = f"{CROSSREF_API_BASE}/{encoded_doi}"
    if email:
        url += f"?mailto={urllib.parse.quote(email, safe='@.')}"
    return url


def _parse_crossref_response(data: dict[str, Any]) -> CrossRefMetadata:
    """Extract citation count and PDF URL from CrossRef API response."""
    message = data.get("message", {})
    doi = message.get("DOI", "")

    citation_count: int | None = None
    raw_count = message.get("is-referenced-by-count")
    if raw_count is not None:
        with contextlib.suppress(ValueError, TypeError):
            citation_count = int(raw_count)

    pdf_url = ""
    links = message.get("link", [])
    for link in links:
        content_type = link.get("content-type", "")
        if content_type == "application/pdf":
            version = link.get("content-version", "")
            candidate = link.get("URL", "")
            if candidate:
                pdf_url = candidate
                if version == "vor":
                    break

    return CrossRefMetadata(doi=doi, citation_count=citation_count, pdf_url=pdf_url)


def fetch_crossref_metadata(
    doi: str,
    email: str = "",
    timeout: int = 5,
) -> CrossRefMetadata | None:
    """Fetch metadata for a single DOI from CrossRef.

    Args:
        doi: Digital object identifier (with or without URL prefix).
        email: Contact email for CrossRef polite pool.
        timeout: Request timeout in seconds.

    Returns:
        CrossRefMetadata on success, None on any failure.
    """
    doi = _normalize_doi(doi.strip())
    if not doi:
        return None

    url = _build_url(doi, email)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception:
        logger.debug("CrossRef lookup failed for DOI: %s", doi)
        return None

    return _parse_crossref_response(data)
