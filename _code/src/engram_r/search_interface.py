"""Unified search interface for literature backends.

Provides SearchResult (backward-compatible alias for ArticleResult),
resolve_search_backends() for config-driven backend selection, and
multi-source search with deduplication via search_all_sources().

The canonical type definition lives in literature_types.py. This module
re-exports it as SearchResult for backward compatibility with existing
code that imports from here.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path

import yaml

from engram_r.literature_types import ArticleResult

logger = logging.getLogger(__name__)

_ENRICHER_REGISTRY: dict[str, tuple[str, str]] = {
    "crossref": ("engram_r.crossref", "fetch_crossref_metadata"),
    "unpaywall": ("engram_r.unpaywall", "fetch_unpaywall_metadata"),
}

_SOURCE_ENV_VARS: dict[str, dict[str, list[str]]] = {
    "pubmed": {"required": ["NCBI_EMAIL"], "optional": ["NCBI_API_KEY"]},
    "arxiv": {"required": [], "optional": []},
    "semantic_scholar": {"required": [], "optional": ["S2_API_KEY"]},
    "openalex": {"required": ["OPENALEX_API_KEY"], "optional": []},
}

_ENRICHER_ENV_VARS: dict[str, dict[str, list[str]]] = {
    "crossref": {"required": [], "optional": ["LITERATURE_ENRICHMENT_EMAIL"]},
    "unpaywall": {"required": ["LITERATURE_ENRICHMENT_EMAIL"], "optional": []},
}

# Backward-compatible alias -- existing code imports SearchResult from here.
SearchResult = ArticleResult

# Maps config source names to (module, search_function, converter) for dispatch.
_SOURCE_REGISTRY: dict[str, tuple[str, str, str]] = {
    "pubmed": ("engram_r.pubmed", "search_and_fetch", "from_pubmed"),
    "arxiv": ("engram_r.arxiv", "search_arxiv", "from_arxiv"),
    "semantic_scholar": (
        "engram_r.semantic_scholar",
        "search_semantic_scholar",
        "from_semantic_scholar",
    ),
    "openalex": ("engram_r.openalex", "search_openalex", "from_openalex"),
}


def resolve_search_backends(
    config_path: Path | str,
) -> list[str]:
    """Read configured search backends from ops/config.yaml.

    Returns ordered list: [primary, fallback, last_resort].
    Backends with value "none" or empty are excluded. Duplicates
    are removed (first occurrence wins).

    Args:
        config_path: Path to ops/config.yaml.

    Returns:
        Ordered list of backend names (e.g. ["pubmed", "arxiv", "web-search"]).
        Falls back to ["web-search"] if the config file is missing or
        no backends are configured.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        return ["web-search"]

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    research = config.get("research", {})
    if not isinstance(research, dict):
        return ["web-search"]

    backends: list[str] = []
    for key in ("primary", "fallback", "last_resort"):
        value = research.get(key, "")
        if (
            isinstance(value, str)
            and value
            and value != "none"
            and value not in backends
        ):
            backends.append(value)

    return backends if backends else ["web-search"]


def resolve_literature_sources(
    config_path: Path | str,
) -> tuple[list[str], str]:
    """Read literature sources and default from ops/config.yaml.

    Reads the ``literature:`` section which lists enabled sources
    and the default source for the /literature skill.

    Args:
        config_path: Path to ops/config.yaml.

    Returns:
        Tuple of (enabled_sources, default_source).
        Returns ``([], "")`` if the config is missing or has no
        literature section.
    """
    config_path = Path(config_path)
    fallback: tuple[list[str], str] = ([], "")

    if not config_path.exists():
        return fallback

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    lit = config.get("literature", {})
    if not isinstance(lit, dict):
        return fallback

    sources = lit.get("sources", [])
    if not isinstance(sources, list) or not sources:
        return fallback

    # Filter to strings only
    sources = [s for s in sources if isinstance(s, str) and s]
    if not sources:
        return fallback

    default = lit.get("default", sources[0])
    if not isinstance(default, str) or not default:
        default = sources[0]

    return sources, default


def check_literature_readiness(config_path: Path | str) -> dict:
    """Check env var readiness for configured literature sources and enrichers.

    Returns dict with keys:
        sources: list[str] -- configured source names
        missing_required: dict[str, list[str]] -- source -> missing required vars
        missing_optional: dict[str, list[str]] -- source -> missing optional vars
        enrichers: list[str]
        missing_enricher_required: dict[str, list[str]]
        missing_enricher_optional: dict[str, list[str]]
        ready: bool -- True if no required vars missing for any configured source
    """
    sources, _ = resolve_literature_sources(config_path)
    enrichers, _ = _resolve_enrichment_config(config_path)

    missing_required: dict[str, list[str]] = {}
    missing_optional: dict[str, list[str]] = {}

    for source in sources:
        env_spec = _SOURCE_ENV_VARS.get(source, {"required": [], "optional": []})
        req_missing = [v for v in env_spec["required"] if not os.environ.get(v)]
        opt_missing = [v for v in env_spec["optional"] if not os.environ.get(v)]
        if req_missing:
            missing_required[source] = req_missing
        if opt_missing:
            missing_optional[source] = opt_missing

    missing_enricher_required: dict[str, list[str]] = {}
    missing_enricher_optional: dict[str, list[str]] = {}

    for enricher in enrichers:
        env_spec = _ENRICHER_ENV_VARS.get(enricher, {"required": [], "optional": []})
        req_missing = [v for v in env_spec["required"] if not os.environ.get(v)]
        opt_missing = [v for v in env_spec["optional"] if not os.environ.get(v)]
        if req_missing:
            missing_enricher_required[enricher] = req_missing
        if opt_missing:
            missing_enricher_optional[enricher] = opt_missing

    return {
        "sources": sources,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "enrichers": enrichers,
        "missing_enricher_required": missing_enricher_required,
        "missing_enricher_optional": missing_enricher_optional,
        "ready": len(missing_required) == 0 and len(missing_enricher_required) == 0,
    }


def _search_single_source(
    source_name: str,
    query: str,
    max_results: int,
) -> list[ArticleResult]:
    """Search a single source and convert results to ArticleResult.

    Dynamically imports the source module to avoid loading all backends
    at module import time. Returns an empty list if the source is
    unknown or the search fails.
    """
    import importlib

    registry_entry = _SOURCE_REGISTRY.get(source_name)
    if registry_entry is None:
        logger.warning("Unknown literature source: %s", source_name)
        return []

    module_path, func_name, converter_name = registry_entry
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        logger.warning("Could not import module for source: %s", source_name)
        return []

    search_fn = getattr(mod, func_name, None)
    if search_fn is None:
        logger.warning("Search function %s not found in %s", func_name, module_path)
        return []

    converter = getattr(ArticleResult, converter_name, None)
    if converter is None:
        logger.warning("Converter %s not found on ArticleResult", converter_name)
        return []

    try:
        raw_results = search_fn(query, max_results)
    except Exception:
        logger.exception("Search failed for source: %s", source_name)
        return []

    return [converter(r) for r in raw_results]


def _dedup_results(results: list[ArticleResult]) -> list[ArticleResult]:
    """Deduplicate ArticleResult list by DOI (primary) then source_id.

    When duplicates are found, keeps the result with more metadata
    (prefers: has citation_count > has abstract > first seen).
    """
    seen_dois: dict[str, int] = {}
    seen_source_ids: dict[str, int] = {}
    deduped: list[ArticleResult] = []

    def _completeness(r: ArticleResult) -> int:
        score = 0
        if r.citation_count is not None:
            score += 2
        if r.abstract:
            score += 1
        return score

    for result in results:
        # Check DOI dedup
        if result.doi:
            doi_lower = result.doi.lower()
            if doi_lower in seen_dois:
                existing_idx = seen_dois[doi_lower]
                if _completeness(result) > _completeness(deduped[existing_idx]):
                    deduped[existing_idx] = result
                continue
            seen_dois[doi_lower] = len(deduped)

        # Check source_id dedup (only if no DOI matched)
        if result.source_id:
            if result.source_id in seen_source_ids:
                existing_idx = seen_source_ids[result.source_id]
                if _completeness(result) > _completeness(deduped[existing_idx]):
                    deduped[existing_idx] = result
                continue
            seen_source_ids[result.source_id] = len(deduped)

        deduped.append(result)

    return deduped


def _resolve_enrichment_config(
    config_path: Path | str | None,
) -> tuple[list[str], int]:
    """Read enrichment settings from ops/config.yaml.

    Returns:
        Tuple of (enabled_enrichers, timeout_per_doi).
        Falls back to ([], 5) if config is missing or has no enrichment section.
    """
    fallback: tuple[list[str], int] = ([], 5)
    if config_path is None:
        return fallback

    config_path = Path(config_path)
    if not config_path.exists():
        return fallback

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    lit = config.get("literature", {})
    if not isinstance(lit, dict):
        return fallback

    enrichment = lit.get("enrichment", {})
    if not isinstance(enrichment, dict):
        return fallback

    enabled = enrichment.get("enabled", [])
    if not isinstance(enabled, list):
        enabled = []
    enabled = [e for e in enabled if isinstance(e, str) and e]

    timeout = enrichment.get("timeout_per_doi", 5)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        timeout = 5

    return enabled, int(timeout)


def _enrich_results(
    results: list[ArticleResult],
    enrichers: list[str],
    timeout: int = 5,
) -> list[ArticleResult]:
    """Enrich ArticleResult list by fetching metadata from enrichment APIs.

    For each enricher, iterates results with a DOI and fills MISSING fields
    only (never overwrites existing data). Enrichers run in the order given.

    Args:
        results: Deduplicated list of ArticleResult to enrich.
        enrichers: Ordered list of enricher names (e.g. ["crossref", "unpaywall"]).
        timeout: Per-DOI timeout in seconds.

    Returns:
        The same list, mutated in place (also returned for convenience).
    """
    import importlib

    email = os.environ.get("LITERATURE_ENRICHMENT_EMAIL", "")

    for enricher_name in enrichers:
        registry_entry = _ENRICHER_REGISTRY.get(enricher_name)
        if registry_entry is None:
            logger.warning("Unknown enricher: %s", enricher_name)
            continue

        module_path, func_name = registry_entry
        try:
            mod = importlib.import_module(module_path)
        except ImportError:
            logger.warning("Could not import enricher module: %s", module_path)
            continue

        fetch_fn = getattr(mod, func_name, None)
        if fetch_fn is None:
            logger.warning("Fetch function %s not found in %s", func_name, module_path)
            continue

        for result in results:
            if not result.doi:
                continue

            try:
                metadata = fetch_fn(result.doi, email=email, timeout=timeout)
            except Exception:
                logger.debug("Enricher %s failed for DOI %s", enricher_name, result.doi)
                continue

            if metadata is None:
                continue

            # Fill missing fields only -- never overwrite
            if result.citation_count is None and hasattr(metadata, "citation_count"):
                cc = getattr(metadata, "citation_count", None)
                if cc is not None:
                    result.citation_count = cc

            if not result.pdf_url and hasattr(metadata, "pdf_url"):
                pdf = getattr(metadata, "pdf_url", "")
                if pdf:
                    result.pdf_url = pdf

    return results


def _fill_missing_abstracts(
    results: list[ArticleResult],
    timeout: int = 5,
) -> list[ArticleResult]:
    """Fill empty abstracts via Semantic Scholar then PubMed DOI lookup.

    For each result that has a DOI but no abstract, queries the S2 paper
    detail endpoint first, then falls back to PubMed EFetch.
    Only fills missing abstracts -- never overwrites.

    Args:
        results: Deduplicated list of ArticleResult.
        timeout: Per-DOI timeout in seconds.

    Returns:
        The same list, mutated in place (also returned for convenience).
    """
    candidates = [r for r in results if not r.abstract and r.doi]
    if not candidates:
        return results

    headers: dict[str, str] = {"Accept": "application/json"}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    s2_base = "https://api.semanticscholar.org/graph/v1/paper"
    filled_s2 = 0
    filled_pubmed = 0

    for result in candidates:
        # Try Semantic Scholar first
        encoded_doi = urllib.parse.quote(result.doi, safe="")
        url = f"{s2_base}/DOI:{encoded_doi}?fields=abstract"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            abstract = data.get("abstract") or ""
            if abstract:
                result.abstract = abstract
                filled_s2 += 1
                logger.info("Filled abstract for DOI %s via S2 fallback", result.doi)
                continue
        except Exception:
            logger.debug("S2 abstract fallback failed for DOI %s", result.doi)

        # Fall back to PubMed EFetch
        try:
            from engram_r.pubmed import fetch_abstract_by_doi as pubmed_fetch

            abstract = pubmed_fetch(result.doi, timeout=timeout)
            if abstract:
                result.abstract = abstract
                filled_pubmed += 1
                logger.info(
                    "Filled abstract for DOI %s via PubMed fallback", result.doi
                )
                continue
        except Exception:
            logger.debug("PubMed abstract fallback failed for DOI %s", result.doi)

    total_filled = filled_s2 + filled_pubmed
    if total_filled:
        logger.info(
            "Filled %d/%d missing abstracts (S2: %d, PubMed: %d)",
            total_filled,
            len(candidates),
            filled_s2,
            filled_pubmed,
        )

    return results


def search_all_sources(
    query: str,
    max_results_per_source: int = 5,
    config_path: Path | str | None = None,
    sources: list[str] | None = None,
    enrichers: list[str] | None = None,
) -> list[ArticleResult]:
    """Search multiple literature sources, enrich, and deduplicate results.

    Searches each enabled source sequentially, converts to ArticleResult,
    deduplicates by DOI (primary) then source_id (fallback), optionally
    enriches via CrossRef/Unpaywall, and returns sorted by citation count
    descending (nulls last).

    Args:
        query: Free-text search query.
        max_results_per_source: Max results to fetch from each source.
        config_path: Path to ops/config.yaml for source list and
            enrichment config. Ignored for sources if ``sources`` is provided.
        sources: Explicit list of source names to search. Overrides config.
        enrichers: Explicit list of enricher names. Overrides config.
            Pass ``[]`` to disable enrichment.

    Returns:
        Deduplicated list of ArticleResult sorted by citation count.
    """
    if sources is None:
        if config_path is not None:
            enabled, _ = resolve_literature_sources(config_path)
        else:
            enabled = list(_SOURCE_REGISTRY.keys())
        sources = enabled

    all_results: list[ArticleResult] = []
    for source_name in sources:
        results = _search_single_source(source_name, query, max_results_per_source)
        all_results.extend(results)

    deduped = _dedup_results(all_results)

    # Enrichment: fill missing citation_count and pdf_url via DOI lookups
    if enrichers is None:
        enricher_list, enrich_timeout = _resolve_enrichment_config(config_path)
    else:
        enricher_list = enrichers
        _, enrich_timeout = _resolve_enrichment_config(config_path)

    if enricher_list:
        _enrich_results(deduped, enricher_list, timeout=enrich_timeout)

    # Fill missing abstracts via Semantic Scholar DOI lookup
    _fill_missing_abstracts(deduped, timeout=enrich_timeout)

    # Sort by citation count descending, nulls last
    def _sort_key(r: ArticleResult) -> tuple[bool, int]:
        return (r.citation_count is not None, r.citation_count or 0)

    deduped.sort(key=_sort_key, reverse=True)

    return deduped


# -- Result persistence and note creation ------------------------------------


def save_results_json(
    results: list[ArticleResult],
    output_path: Path | str,
) -> Path:
    """Serialize search results to JSON, preserving full abstracts.

    The agent should call this immediately after ``search_all_sources()``
    and BEFORE displaying any results table. Downstream note creation
    reads from this JSON to avoid abstract truncation in agent context.

    Args:
        results: List of ArticleResult from search_all_sources().
        output_path: Path to write JSON file.

    Returns:
        The output path (as Path).
    """
    output_path = Path(output_path)
    data = [asdict(r) for r in results]
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info("Saved %d search results to %s", len(results), output_path)
    return output_path


def _make_literature_filename(result_dict: dict) -> str:
    """Derive a literature note filename from a result dict.

    Format: ``{year}-{first_author_last}-{title_slug}.md``
    Falls back gracefully when year or authors are missing.
    """
    from engram_r.schema_validator import sanitize_title

    year = result_dict.get("year") or "unknown"
    authors = result_dict.get("authors") or []
    title = result_dict.get("title") or "untitled"

    # First author last name -- handle mixed formats:
    #   "Philip B. Gorelick"  -> last token "Gorelick"
    #   "Wolters F"           -> first token "Wolters" (last is initial)
    #   "Marta Segarra"       -> last token "Segarra"
    if authors:
        first_author = authors[0]
        parts = first_author.strip().split()
        last_token = parts[-1].rstrip(",.")
        # If last token is a single char (initial like "J" or "G"), use first token
        if len(last_token) <= 1 and len(parts) > 1:
            last_name = parts[0].lower().rstrip(",.")
        else:
            last_name = last_token.lower()
    else:
        last_name = "unknown"

    # Title slug: first ~10 words, strip trailing stopwords, sanitize
    trailing_stops = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
    title_words = re.sub(r"[^\w\s-]", "", title.lower()).split()[:10]
    while title_words and title_words[-1] in trailing_stops:
        title_words.pop()
    slug = "-".join(title_words) if title_words else "untitled"
    slug = sanitize_title(slug)

    # Assemble and truncate to reasonable length
    stem = f"{year}-{last_name}-{slug}"
    if len(stem) > 120:
        stem = stem[:120].rstrip("-")

    return f"{stem}.md"


def create_notes_from_results(
    results_json: str | Path,
    indices: list[int],
    output_dir: str | Path,
    goal_tag: str = "",
    enrichments: dict[int, dict] | None = None,
    enrichments_path: str | Path | None = None,
) -> list[dict]:
    """Build and write literature notes from saved search results.

    Reads full results from JSON (preserving complete abstracts),
    builds notes via ``build_literature_note()``, writes to output_dir.

    Args:
        results_json: Path to JSON from ``save_results_json()``.
        indices: 1-based indices of results to save.
        output_dir: Directory for literature notes (e.g. _research/literature/).
        goal_tag: Optional project tag to add to note tags.
        enrichments: Optional dict mapping 1-based index to enrichment data.
            Each value may contain ``key_points`` (list[str]) and/or
            ``relevance`` (str). When provided, these populate the
            Key Points and Relevance sections at creation time.
        enrichments_path: Optional path to a JSON file containing enrichments.
            JSON keys are stringified 1-based indices (converted to int on load).
            Takes precedence over ``enrichments`` dict if both are provided.

    Returns:
        List of dicts with keys: index, path, title, doi, status, enriched.
    """
    from engram_r.note_builder import build_literature_note

    results_json = Path(results_json)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load enrichments from file if provided (takes precedence over dict)
    if enrichments_path is not None:
        enrichments_path = Path(enrichments_path)
        raw = json.loads(enrichments_path.read_text())
        enrichments = {int(k): v for k, v in raw.items()}

    data = json.loads(results_json.read_text())

    created: list[dict] = []
    for idx in indices:
        if idx < 1 or idx > len(data):
            created.append(
                {
                    "index": idx,
                    "path": "",
                    "title": "",
                    "doi": "",
                    "status": f"error: index {idx} out of range (1-{len(data)})",
                }
            )
            continue

        result = data[idx - 1]  # 1-based to 0-based

        # Check for DOI duplicate in output_dir
        doi = result.get("doi", "")
        if doi:
            duplicate = _check_doi_duplicate(doi, output_dir)
            if duplicate:
                created.append(
                    {
                        "index": idx,
                        "path": str(duplicate),
                        "title": result.get("title", ""),
                        "doi": doi,
                        "status": f"skipped: duplicate DOI in {duplicate.name}",
                    }
                )
                continue

        # Abstract quality gate: warn and attempt fallback if empty/short
        abstract = result.get("abstract", "")
        abstract_status = "full"

        if not abstract and doi:
            logger.warning(
                "Empty abstract for '%s' (DOI: %s) -- attempting PubMed fallback",
                result.get("title", "")[:60],
                doi,
            )
            try:
                from engram_r.pubmed import fetch_abstract_by_doi as pubmed_fetch

                abstract = pubmed_fetch(doi) or ""
                if abstract:
                    abstract_status = "pubmed_fallback"
                    logger.info("  -> Filled via PubMed (%d chars)", len(abstract))
            except Exception:
                logger.debug("PubMed fallback failed for DOI %s", doi)

        if not abstract:
            abstract_status = "empty"
            logger.warning(
                "Writing note with EMPTY abstract: '%s' -- "
                "will block downstream /reduce extraction",
                result.get("title", "")[:60],
            )
        elif len(abstract) < 200 and abstract_status != "pubmed_fallback":
            abstract_status = "short"
            logger.warning(
                "Suspiciously short abstract (%d chars) for '%s' -- "
                "may be truncated",
                len(abstract),
                result.get("title", "")[:60],
            )

        tags = [goal_tag] if goal_tag else None
        paper_enrichment = (enrichments or {}).get(idx, {})
        # Derive description from abstract: first sentence, capped at 150 chars
        desc = ""
        if abstract:
            first_sentence = abstract.split(". ")[0]
            if not first_sentence.endswith("."):
                first_sentence += "."
            desc = first_sentence[:150]
        content = build_literature_note(
            title=result.get("title", ""),
            description=desc,
            doi=doi,
            authors=result.get("authors", []),
            year=result.get("year") or "",
            journal=result.get("journal", ""),
            abstract=abstract,
            tags=tags,
            source_type=result.get("source_type", ""),
            key_points=paper_enrichment.get("key_points"),
            relevance=paper_enrichment.get("relevance", ""),
        )

        filename = _make_literature_filename(result)
        filepath = output_dir / filename

        # Avoid overwrites
        if filepath.exists():
            stem = filepath.stem
            counter = 2
            while filepath.exists():
                filepath = output_dir / f"{stem}-{counter}.md"
                counter += 1

        filepath.write_text(content)
        logger.info("Created literature note: %s", filepath)

        created.append(
            {
                "index": idx,
                "path": str(filepath),
                "title": result.get("title", ""),
                "doi": doi,
                "status": "created",
                "abstract_status": abstract_status,
                "enriched": bool(paper_enrichment),
            }
        )

    return created


def _check_doi_duplicate(doi: str, literature_dir: Path) -> Path | None:
    """Check if a DOI already exists in any literature note's frontmatter.

    Args:
        doi: The DOI to check.
        literature_dir: Directory containing literature notes.

    Returns:
        Path to the existing note if duplicate found, None otherwise.
    """
    doi_lower = doi.lower().strip()
    for md_file in literature_dir.glob("*.md"):
        if md_file.name.startswith("_"):
            continue
        try:
            text = md_file.read_text(errors="replace")
            if not text.startswith("---"):
                continue
            end = text.find("---", 3)
            if end == -1:
                continue
            fm_text = text[3:end]
            fm = yaml.safe_load(fm_text)
            if isinstance(fm, dict):
                existing_doi = fm.get("doi", "")
                if (
                    isinstance(existing_doi, str)
                    and existing_doi.lower().strip() == doi_lower
                ):
                    return md_file
        except Exception:
            continue
    return None


# -- Queue entry creation -----------------------------------------------------


def create_queue_entries(
    created_notes: list[dict],
    queue_path: str | Path,
    vault_root: str | Path | None = None,
    scope: str = "full",
) -> list[dict]:
    """Append deduplicated extract queue entries for newly created literature notes.

    Uses the actual file paths from ``create_notes_from_results()`` return
    values, avoiding agent-constructed path mismatches.

    Args:
        created_notes: List of dicts from ``create_notes_from_results()``.
            Each must have keys: path, status. Only entries with
            status="created" are queued.
        queue_path: Path to ops/queue/queue.json.
        vault_root: Vault root for computing relative paths. If None,
            paths are stored as-is.

    Returns:
        List of newly created queue entry dicts (for logging/display).
    """
    from datetime import UTC, datetime

    queue_path = Path(queue_path)
    vault_root_path = Path(vault_root) if vault_root else None

    # Load existing queue
    if queue_path.exists():
        queue = json.loads(queue_path.read_text())
    else:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue = []

    # Collect existing source paths for dedup
    existing_sources = {e.get("source", "") for e in queue if isinstance(e, dict)}

    now = datetime.now(UTC).isoformat()
    new_entries: list[dict] = []

    for note in created_notes:
        if note.get("status") != "created":
            continue

        note_path = note.get("path", "")
        if not note_path:
            continue

        # Compute relative path from vault root
        if vault_root_path:
            try:
                rel_path = str(Path(note_path).relative_to(vault_root_path))
            except ValueError:
                rel_path = note_path
        else:
            rel_path = note_path

        # Dedup by source path
        if rel_path in existing_sources:
            logger.info("Queue entry already exists for %s -- skipping", rel_path)
            continue

        # Build queue ID from filename stem
        stem = Path(note_path).stem
        queue_id = f"extract-{stem}"

        entry = {
            "id": queue_id,
            "type": "extract",
            "status": "pending",
            "source": rel_path,
            "created": now,
            "current_phase": "reduce",
            "completed_phases": [],
            "scope": scope,
        }

        queue.append(entry)
        existing_sources.add(rel_path)
        new_entries.append(entry)

    # Write atomically
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False))
    logger.info("Added %d queue entries to %s", len(new_entries), queue_path)

    return new_entries
