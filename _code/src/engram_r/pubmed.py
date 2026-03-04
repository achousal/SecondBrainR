"""PubMed search via NCBI EUTILS API.

Uses urllib only (no external HTTP library). Respects API key for 10 req/s.
Reference: https://www.ncbi.nlm.nih.gov/books/NBK25500/
"""

from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass
class PubMedArticle:
    """Parsed PubMed article summary."""

    pmid: str
    title: str
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: str = ""
    abstract: str = ""
    doi: str = ""


def _build_params(base_params: dict[str, str]) -> dict[str, str]:
    """Add API key and email from environment if available."""
    params = dict(base_params)
    api_key = os.environ.get("NCBI_API_KEY", "")
    email = os.environ.get("NCBI_EMAIL", "")
    if api_key:
        params["api_key"] = api_key
    if email:
        params["email"] = email
    return params


def _fetch_xml(url: str) -> ET.Element:
    """Fetch and parse XML from a URL."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return ET.fromstring(data)


def search_pubmed(
    query: str,
    max_results: int = 10,
) -> list[str]:
    """Search PubMed and return a list of PMIDs.

    Args:
        query: PubMed search query.
        max_results: Maximum number of results.

    Returns:
        List of PMID strings.
    """
    params = _build_params(
        {
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "retmode": "xml",
        }
    )
    url = f"{EUTILS_BASE}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    logger.info("PubMed search: %s", query)

    root = _fetch_xml(url)
    id_list = root.find("IdList")
    if id_list is None:
        return []
    return [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]


def fetch_articles(pmids: list[str]) -> list[PubMedArticle]:
    """Fetch article details for a list of PMIDs.

    Args:
        pmids: List of PubMed IDs.

    Returns:
        List of PubMedArticle objects.
    """
    if not pmids:
        return []

    params = _build_params(
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
    )
    url = f"{EUTILS_BASE}/efetch.fcgi?{urllib.parse.urlencode(params)}"
    logger.info("Fetching %d articles", len(pmids))

    root = _fetch_xml(url)
    articles = []

    for article_elem in root.iter("PubmedArticle"):
        articles.append(_parse_article(article_elem))

    return articles


def _parse_article(elem: ET.Element) -> PubMedArticle:
    """Parse a PubmedArticle XML element."""
    medline = elem.find("MedlineCitation")
    if medline is None:
        return PubMedArticle(pmid="", title="")

    pmid_elem = medline.find("PMID")
    pmid = pmid_elem.text if pmid_elem is not None and pmid_elem.text else ""

    article = medline.find("Article")
    if article is None:
        return PubMedArticle(pmid=pmid, title="")

    # Title
    title_elem = article.find("ArticleTitle")
    title = title_elem.text if title_elem is not None and title_elem.text else ""

    # Authors
    authors = []
    author_list = article.find("AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            last = author.find("LastName")
            fore = author.find("ForeName")
            parts = []
            if last is not None and last.text:
                parts.append(last.text)
            if fore is not None and fore.text:
                parts.append(fore.text[0])
            if parts:
                authors.append(" ".join(parts))

    # Journal
    journal_elem = article.find("Journal/Title")
    journal = ""
    if journal_elem is not None and journal_elem.text:
        journal = journal_elem.text

    # Year
    year = ""
    pub_date = article.find("Journal/JournalIssue/PubDate/Year")
    if pub_date is not None and pub_date.text:
        year = pub_date.text

    # Abstract
    abstract_parts = []
    abstract_elem = article.find("Abstract")
    if abstract_elem is not None:
        for text_elem in abstract_elem.findall("AbstractText"):
            if text_elem.text:
                label = text_elem.get("Label", "")
                if label:
                    abstract_parts.append(f"**{label}**: {text_elem.text}")
                else:
                    abstract_parts.append(text_elem.text)
    abstract = "\n\n".join(abstract_parts)

    # DOI
    doi = ""
    article_id_list = elem.find("PubmedData/ArticleIdList")
    if article_id_list is not None:
        for aid in article_id_list.findall("ArticleId"):
            if aid.get("IdType") == "doi" and aid.text:
                doi = aid.text
                break

    return PubMedArticle(
        pmid=pmid,
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        abstract=abstract,
        doi=doi,
    )


def fetch_abstract_by_doi(doi: str, timeout: int = 10) -> str | None:
    """Fetch abstract from PubMed by DOI (search for PMID, then EFetch).

    Args:
        doi: The DOI to look up.
        timeout: HTTP timeout in seconds.

    Returns:
        Abstract text if found, None otherwise.
    """
    # Step 1: search for PMID by DOI
    params = _build_params({"db": "pubmed", "term": f"{doi}[doi]", "retmode": "xml"})
    search_url = f"{EUTILS_BASE}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(search_url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            root = ET.fromstring(resp.read())
        id_list = root.find("IdList")
        if id_list is None:
            return None
        pmids = [el.text for el in id_list.findall("Id") if el.text]
        if not pmids:
            return None
    except Exception:
        logger.debug("PubMed DOI search failed for %s", doi)
        return None

    # Step 2: fetch article and extract abstract
    try:
        articles = fetch_articles(pmids[:1])
        if articles and articles[0].abstract:
            return articles[0].abstract
    except Exception:
        logger.debug("PubMed EFetch failed for DOI %s", doi)

    return None


def search_and_fetch(
    query: str,
    max_results: int = 10,
) -> list[PubMedArticle]:
    """Convenience: search + fetch in one call.

    Args:
        query: PubMed search query.
        max_results: Maximum results.

    Returns:
        List of PubMedArticle objects.
    """
    pmids = search_pubmed(query, max_results=max_results)
    if not pmids:
        return []
    return fetch_articles(pmids)
