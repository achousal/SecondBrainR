"""Unified types for the literature search subsystem.

Defines ArticleResult (the canonical result dataclass across all backends)
and LiteratureSource (the Protocol that each backend module can satisfy).
"""

from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ArticleResult:
    """Unified literature search result across backends.

    Every literature backend (PubMed, arXiv, Semantic Scholar, OpenAlex)
    converts its native response into this common shape. Downstream code
    (note_builder, skill templates) depends only on this type.

    Attributes:
        source_id: Backend-specific identifier (e.g. "PMID:12345", "S2:abc123").
        title: Article title.
        authors: List of author names.
        abstract: Full abstract text.
        year: Publication year as integer, or None if unavailable.
        doi: Digital object identifier, empty string if unavailable.
        source_type: Backend name ("pubmed", "arxiv", "semantic_scholar", "openalex").
        url: Canonical URL for the article.
        journal: Journal or venue name, empty string if unavailable.
        categories: Subject categories (primarily arXiv).
        pdf_url: Direct PDF link if available.
        citation_count: Citation count if the backend provides it, else None.
        raw_metadata: Original backend-specific data preserved for inspection.
    """

    source_id: str
    title: str
    authors: list[str]
    abstract: str
    year: int | None
    doi: str
    source_type: str
    url: str
    journal: str
    categories: list[str] = field(default_factory=list)
    pdf_url: str = ""
    citation_count: int | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    # -- Converters from backend-specific dataclasses --------------------------

    @classmethod
    def from_pubmed(cls, article: Any) -> ArticleResult:
        """Convert a PubMedArticle dataclass to ArticleResult.

        Args:
            article: A PubMedArticle instance from engram_r.pubmed with
                attributes: pmid, title, authors, abstract, journal, year, doi.
                The year field is a string in PubMedArticle.
        """
        pmid = getattr(article, "pmid", "")
        year_str = getattr(article, "year", "")
        year: int | None = None
        if year_str:
            with contextlib.suppress(ValueError, TypeError):
                year = int(year_str)

        raw = asdict(article) if hasattr(article, "__dataclass_fields__") else {}

        return cls(
            source_id=f"PMID:{pmid}" if pmid else "",
            title=getattr(article, "title", ""),
            authors=getattr(article, "authors", []),
            abstract=getattr(article, "abstract", ""),
            year=year,
            doi=getattr(article, "doi", ""),
            source_type="pubmed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            journal=getattr(article, "journal", ""),
            raw_metadata=raw,
        )

    @classmethod
    def from_arxiv(cls, entry: Any) -> ArticleResult:
        """Convert an ArxivArticle dataclass to ArticleResult.

        Args:
            entry: An ArxivArticle instance from engram_r.arxiv with
                attributes: arxiv_id, title, authors, abstract, categories,
                published, doi, pdf_url.
        """
        arxiv_id = getattr(entry, "arxiv_id", "")
        published = getattr(entry, "published", "")
        year: int | None = None
        if published and len(published) >= 4:
            with contextlib.suppress(ValueError, TypeError):
                year = int(published[:4])

        raw = asdict(entry) if hasattr(entry, "__dataclass_fields__") else {}

        return cls(
            source_id=f"arXiv:{arxiv_id}" if arxiv_id else "",
            title=getattr(entry, "title", ""),
            authors=getattr(entry, "authors", []),
            abstract=getattr(entry, "abstract", ""),
            year=year,
            doi=getattr(entry, "doi", ""),
            source_type="arxiv",
            url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            journal="",
            categories=getattr(entry, "categories", []),
            pdf_url=getattr(entry, "pdf_url", ""),
            raw_metadata=raw,
        )

    @classmethod
    def from_semantic_scholar(cls, article: Any) -> ArticleResult:
        """Convert a SemanticScholarArticle dataclass to ArticleResult.

        Args:
            article: A SemanticScholarArticle instance from
                engram_r.semantic_scholar with attributes: paper_id, title,
                authors, abstract, year, venue, doi, citation_count, url,
                pdf_url. The year field is a string.
        """
        paper_id = getattr(article, "paper_id", "")
        year_str = getattr(article, "year", "")
        year: int | None = None
        if year_str:
            with contextlib.suppress(ValueError, TypeError):
                year = int(year_str)

        raw = asdict(article) if hasattr(article, "__dataclass_fields__") else {}

        return cls(
            source_id=f"S2:{paper_id}" if paper_id else "",
            title=getattr(article, "title", ""),
            authors=getattr(article, "authors", []),
            abstract=getattr(article, "abstract", ""),
            year=year,
            doi=getattr(article, "doi", ""),
            source_type="semantic_scholar",
            url=getattr(article, "url", ""),
            journal=getattr(article, "venue", ""),
            citation_count=getattr(article, "citation_count", None) or None,
            pdf_url=getattr(article, "pdf_url", ""),
            raw_metadata=raw,
        )

    @classmethod
    def from_openalex(cls, work: Any) -> ArticleResult:
        """Convert an OpenAlexWork dataclass to ArticleResult.

        Args:
            work: An OpenAlexWork instance from engram_r.openalex with
                attributes: openalex_id, title, authors, abstract, year,
                journal, doi, cited_by_count, url, pdf_url.
                The year field is a string.
        """
        oa_id = getattr(work, "openalex_id", "")
        year_str = getattr(work, "year", "")
        year: int | None = None
        if year_str:
            with contextlib.suppress(ValueError, TypeError):
                year = int(year_str)

        raw = asdict(work) if hasattr(work, "__dataclass_fields__") else {}

        return cls(
            source_id=f"OpenAlex:{oa_id}" if oa_id else "",
            title=getattr(work, "title", ""),
            authors=getattr(work, "authors", []),
            abstract=getattr(work, "abstract", ""),
            year=year,
            doi=getattr(work, "doi", ""),
            source_type="openalex",
            url=getattr(work, "url", ""),
            journal=getattr(work, "journal", ""),
            citation_count=getattr(work, "cited_by_count", None) or None,
            pdf_url=getattr(work, "pdf_url", ""),
            raw_metadata=raw,
        )


@runtime_checkable
class LiteratureSource(Protocol):
    """Protocol that literature backend modules can satisfy.

    A conforming source provides metadata about itself and a search method
    that returns ArticleResult objects.
    """

    @property
    def name(self) -> str:
        """Short identifier, e.g. 'pubmed', 'semantic_scholar'."""
        ...

    @property
    def requires_key(self) -> bool:
        """Whether an API key is required (vs. optional/none)."""
        ...

    @property
    def env_var(self) -> str | None:
        """Environment variable name for the API key, or None."""
        ...

    def search(self, query: str, max_results: int = 10) -> list[ArticleResult]:
        """Search this source and return unified results."""
        ...
