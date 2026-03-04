"""DOI stub enrichment for inbox files.

Fetches abstracts and metadata for inbox DOI stubs (created during
lab onboarding) so they can be meaningfully processed by /reduce.

API call order: Semantic Scholar -> PubMed (abstract),
                CrossRef (citation count, PDF URL),
                Unpaywall (OA status, PDF URL fallback).
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from engram_r.frontmatter import FM_RE as _FM_RE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches DOI patterns in URLs or bare DOIs
_DOI_RE = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/)?"  # optional URL prefix
    r"(10\.\d{4,9}/[^\s\"'<>]+)",        # DOI body
)

S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class StubInfo:
    """Parsed inbox stub ready for enrichment."""

    path: Path
    title: str
    doi: str
    source_url: str
    authors: str
    journal: str
    year: str
    lab: str


@dataclass
class EnrichmentResult:
    """Result of enriching a single DOI stub."""

    stub: StubInfo
    abstract: str = ""
    citation_count: int | None = None
    pdf_url: str = ""
    is_oa: bool = False
    content_depth: str = "stub"  # "abstract" | "stub"
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DOI extraction
# ---------------------------------------------------------------------------


def extract_doi_from_url(url: str) -> str | None:
    """Extract a DOI from a URL or bare DOI string.

    Handles doi.org, dx.doi.org, and publisher URLs containing DOIs.
    Strips trailing punctuation that may have been copied with the URL.

    Args:
        url: URL or string potentially containing a DOI.

    Returns:
        Bare DOI string (e.g. "10.1234/test") or None if no DOI found.
    """
    if not url:
        return None
    m = _DOI_RE.search(url)
    if not m:
        return None
    doi = m.group(1)
    # Strip trailing punctuation that is not part of a DOI
    doi = doi.rstrip(".,;:)")
    return doi


# ---------------------------------------------------------------------------
# Inbox stub parsing
# ---------------------------------------------------------------------------


def parse_inbox_stub(path: Path) -> StubInfo | None:
    """Parse an inbox .md file and return StubInfo if it is a DOI stub.

    A DOI stub is an import-type file with a source_url containing a DOI
    and no abstract section with content.

    Args:
        path: Path to the inbox markdown file.

    Returns:
        StubInfo if the file is an enrichable DOI stub, None otherwise.
    """
    try:
        text = path.read_text(errors="replace")
    except OSError:
        logger.warning("Cannot read file: %s", path)
        return None

    fm_match = _FM_RE.match(text)
    if not fm_match:
        return None

    try:
        fm = yaml.safe_load(fm_match.group(1))
        if not isinstance(fm, dict):
            return None
    except yaml.YAMLError:
        logger.warning("Malformed YAML in %s", path)
        return None

    # Must be an import stub
    if fm.get("source_type") != "import":
        return None

    # Must have a source URL with a DOI
    source_url = fm.get("source_url", "")
    doi = extract_doi_from_url(source_url)
    if not doi:
        return None

    # Skip if already enriched (has content_depth set)
    if fm.get("content_depth"):
        return None

    # Skip if already has an abstract section with content
    body = text[fm_match.end():]
    abstract_match = re.search(r"## Abstract\s*\n(.+?)(?=\n## |\Z)", body, re.DOTALL)
    if abstract_match and abstract_match.group(1).strip():
        return None

    # Extract title from first H1
    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    return StubInfo(
        path=path,
        title=title,
        doi=doi,
        source_url=source_url,
        authors=fm.get("authors", ""),
        journal=fm.get("journal", ""),
        year=str(fm.get("year", "")),
        lab=fm.get("lab", ""),
    )


def scan_inbox_stubs(inbox_dir: Path) -> list[StubInfo]:
    """Scan inbox/ for all DOI stubs needing enrichment.

    Args:
        inbox_dir: Path to the inbox directory.

    Returns:
        List of StubInfo sorted by year (newest first).
    """
    if not inbox_dir.is_dir():
        return []

    stubs: list[StubInfo] = []
    for md_file in sorted(inbox_dir.glob("*.md")):
        stub = parse_inbox_stub(md_file)
        if stub is not None:
            stubs.append(stub)

    # Sort by year descending (newest first)
    stubs.sort(key=lambda s: s.year, reverse=True)
    return stubs


# ---------------------------------------------------------------------------
# Abstract fetching (S2 -> PubMed fallback)
# ---------------------------------------------------------------------------


def _fetch_abstract_s2(doi: str, timeout: int = 10) -> str | None:
    """Fetch abstract from Semantic Scholar by DOI.

    Args:
        doi: Digital object identifier.
        timeout: HTTP timeout in seconds.

    Returns:
        Abstract text if found, None otherwise.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    encoded_doi = urllib.parse.quote(doi, safe="")
    url = f"{S2_BASE}/DOI:{encoded_doi}?fields=abstract"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        abstract = data.get("abstract") or ""
        if abstract:
            return abstract
    except Exception:
        logger.debug("S2 abstract fetch failed for DOI %s", doi)
    return None


def _fetch_abstract_pubmed(doi: str, timeout: int = 10) -> str | None:
    """Fetch abstract from PubMed by DOI (fallback).

    Args:
        doi: Digital object identifier.
        timeout: HTTP timeout in seconds.

    Returns:
        Abstract text if found, None otherwise.
    """
    try:
        from engram_r.pubmed import fetch_abstract_by_doi

        return fetch_abstract_by_doi(doi, timeout=timeout)
    except Exception:
        logger.debug("PubMed abstract fetch failed for DOI %s", doi)
    return None


# ---------------------------------------------------------------------------
# Single DOI enrichment
# ---------------------------------------------------------------------------


def enrich_single_doi(
    stub: StubInfo,
    timeout: int = 10,
) -> EnrichmentResult:
    """Fetch abstract and metadata for a single DOI stub.

    API call order:
    1. Abstract: Semantic Scholar -> PubMed (fallback)
    2. Metadata: CrossRef (citation count, PDF URL)
    3. OA status: Unpaywall (OA flag, PDF URL fallback)

    Args:
        stub: Parsed inbox stub info.
        timeout: Per-request timeout in seconds.

    Returns:
        EnrichmentResult with fetched data and content_depth.
    """
    result = EnrichmentResult(stub=stub)
    email = os.environ.get("LITERATURE_ENRICHMENT_EMAIL", "")

    # 1. Abstract: S2 -> PubMed
    try:
        abstract = _fetch_abstract_s2(stub.doi, timeout=timeout)
    except (TimeoutError, OSError) as exc:
        abstract = None
        result.errors.append(f"S2 abstract fetch failed: {exc}")
    if not abstract:
        try:
            abstract = _fetch_abstract_pubmed(stub.doi, timeout=timeout)
        except (TimeoutError, OSError) as exc:
            abstract = None
            result.errors.append(f"PubMed abstract fetch failed: {exc}")
    if abstract:
        result.abstract = abstract
        result.content_depth = "abstract"
    else:
        result.errors.append(f"No abstract found for DOI {stub.doi}")
        result.content_depth = "stub"

    # 2. CrossRef metadata
    try:
        from engram_r.crossref import fetch_crossref_metadata

        cr = fetch_crossref_metadata(stub.doi, email=email, timeout=timeout)
        if cr is not None:
            result.citation_count = cr.citation_count
            if cr.pdf_url:
                result.pdf_url = cr.pdf_url
    except Exception as exc:
        result.errors.append(f"CrossRef failed: {exc}")
        logger.debug("CrossRef fetch failed for DOI %s: %s", stub.doi, exc)

    # 3. Unpaywall OA status
    if email:
        try:
            from engram_r.unpaywall import fetch_unpaywall_metadata

            up = fetch_unpaywall_metadata(
                stub.doi, email=email, timeout=timeout,
            )
            if up is not None:
                result.is_oa = up.is_oa
                if up.pdf_url and not result.pdf_url:
                    result.pdf_url = up.pdf_url
        except Exception as exc:
            result.errors.append(f"Unpaywall failed: {exc}")
            logger.debug("Unpaywall fetch failed for DOI %s: %s", stub.doi, exc)

    return result


# ---------------------------------------------------------------------------
# Apply enrichment to stub file (in-place update)
# ---------------------------------------------------------------------------


def apply_enrichment_to_stub(result: EnrichmentResult) -> Path:
    """Write enrichment data back to the inbox stub file in-place.

    Updates the frontmatter with content_depth and metadata.
    Adds an Abstract section if an abstract was fetched.

    Args:
        result: EnrichmentResult from enrich_single_doi.

    Returns:
        Path to the updated file.
    """
    path = result.stub.path
    text = path.read_text(errors="replace")

    fm_match = _FM_RE.match(text)
    if not fm_match:
        msg = f"No frontmatter found in {path}"
        raise ValueError(msg)

    fm = yaml.safe_load(fm_match.group(1))
    if not isinstance(fm, dict):
        fm = {}

    # Update frontmatter
    fm["content_depth"] = result.content_depth
    if result.citation_count is not None:
        fm["citation_count"] = result.citation_count
    if result.is_oa:
        fm["is_oa"] = True
    if result.pdf_url:
        fm["pdf_url"] = result.pdf_url

    # Rebuild file
    fm_str = yaml.dump(
        fm, default_flow_style=False, sort_keys=False, allow_unicode=True
    ).rstrip()

    body = text[fm_match.end():]

    # Add abstract section if we have one and it doesn't exist yet
    if result.abstract:
        # Check if abstract section already exists with content
        abstract_match = re.search(
            r"## Abstract\s*\n(.+?)(?=\n## |\Z)", body, re.DOTALL
        )
        if not abstract_match or not abstract_match.group(1).strip():
            # Find insertion point: after the URL line, before ## Notes
            notes_match = re.search(r"\n## Notes", body)
            if notes_match:
                insert_pos = notes_match.start()
                body = (
                    body[:insert_pos]
                    + f"\n\n## Abstract\n\n{result.abstract}\n"
                    + body[insert_pos:]
                )
            else:
                # Append before end
                body = body.rstrip() + f"\n\n## Abstract\n\n{result.abstract}\n"

    new_content = f"---\n{fm_str}\n---\n{body}"
    path.write_text(new_content)
    return path


# ---------------------------------------------------------------------------
# Batch enrichment
# ---------------------------------------------------------------------------


def enrich_inbox_stubs(
    inbox_dir: Path,
    timeout: int = 10,
) -> list[EnrichmentResult]:
    """Batch enrich all DOI stubs in inbox/.

    Args:
        inbox_dir: Path to the inbox directory.
        timeout: Per-request timeout in seconds.

    Returns:
        List of EnrichmentResult for all processed stubs.
    """
    stubs = scan_inbox_stubs(inbox_dir)
    results: list[EnrichmentResult] = []

    for stub in stubs:
        logger.info("Enriching: %s (DOI: %s)", stub.title, stub.doi)
        result = enrich_single_doi(stub, timeout=timeout)
        results.append(result)

    return results
