"""Unpaywall metadata enrichment via REST API.

Enrichment layer -- fetches open-access PDF URLs by DOI.
Not a search backend; post-processes results from other sources.

API: https://api.unpaywall.org/v2/{doi}?email={email}
No API key required. Email is mandatory per Unpaywall TOS.
Env var: LITERATURE_ENRICHMENT_EMAIL (shared with CrossRef).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

UNPAYWALL_API_BASE = "https://api.unpaywall.org/v2"


@dataclass
class UnpaywallMetadata:
    """Metadata fetched from Unpaywall for a single DOI."""

    doi: str
    pdf_url: str = ""
    is_oa: bool = False


def _normalize_doi(doi: str) -> str:
    """Strip common URL prefixes from a DOI string."""
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
        if doi.startswith(prefix):
            return doi[len(prefix) :]
    return doi


def _build_url(doi: str, email: str) -> str:
    """Build Unpaywall API URL for a DOI lookup."""
    encoded_doi = urllib.parse.quote(doi, safe="")
    encoded_email = urllib.parse.quote(email, safe="@.")
    return f"{UNPAYWALL_API_BASE}/{encoded_doi}?email={encoded_email}"


def _parse_unpaywall_response(data: dict[str, Any]) -> UnpaywallMetadata:
    """Extract PDF URL and OA status from Unpaywall API response."""
    doi = data.get("doi", "")
    is_oa = bool(data.get("is_oa", False))

    pdf_url = ""
    best_oa = data.get("best_oa_location")
    if isinstance(best_oa, dict):
        pdf_url = best_oa.get("url_for_pdf") or ""

    return UnpaywallMetadata(doi=doi, pdf_url=pdf_url, is_oa=is_oa)


def fetch_unpaywall_metadata(
    doi: str,
    email: str = "",
    timeout: int = 5,
) -> UnpaywallMetadata | None:
    """Fetch metadata for a single DOI from Unpaywall.

    Args:
        doi: Digital object identifier (with or without URL prefix).
        email: Contact email (required by Unpaywall TOS).
        timeout: Request timeout in seconds.

    Returns:
        UnpaywallMetadata on success, None on any failure.
        Returns None if email is empty (required by Unpaywall TOS).
    """
    if not email:
        logger.warning("Unpaywall requires an email address; skipping lookup")
        return None

    doi = _normalize_doi(doi.strip())
    if not doi:
        return None

    url = _build_url(doi, email)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception:
        logger.debug("Unpaywall lookup failed for DOI: %s", doi)
        return None

    return _parse_unpaywall_response(data)
