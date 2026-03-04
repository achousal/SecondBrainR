"""Populate blocked literature stubs with full abstracts from Semantic Scholar.

Reads queue.json for blocked entries, fuzzy-matches queue source paths
to actual files on disk, fetches full abstracts by DOI (or title search
for papers without DOI), updates the literature note files, fixes queue
source paths, and flips queue status from blocked -> pending.

Usage:
    uv run --directory _code python scripts/maintenance/populate_stubs.py [--dry-run]
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # maintenance/ -> scripts/ -> _code/ -> vault
QUEUE_PATH = VAULT_ROOT / "ops" / "queue" / "queue.json"
LITERATURE_DIR = VAULT_ROOT / "_research" / "literature"

S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"

PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def _s2_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _normalize(s: str) -> str:
    """NFC-normalize and lowercase for comparison."""
    return unicodedata.normalize("NFC", s).lower()


def _extract_title_words(filename_stem: str) -> list[str]:
    """Extract title words from a filename stem, skipping year and author."""
    parts = filename_stem.split("-")
    # Skip year (first part) and author (second part)
    if len(parts) > 2:
        return parts[2:]
    return parts


def resolve_actual_file(queue_source: str, literature_dir: Path) -> Path | None:
    """Fuzzy-match a queue source path to an actual file on disk.

    Queue paths are often truncated or have single-letter author initials
    instead of full last names. This matches on the title-slug portion
    after the year-author prefix.
    """
    queue_stem = Path(queue_source).stem
    queue_norm = _normalize(queue_stem)

    # Direct match first
    direct = literature_dir / Path(queue_source).name
    if direct.exists():
        return direct

    # Extract year and title words from queue stem
    queue_title_words = _extract_title_words(queue_stem)
    if not queue_title_words:
        return None

    # Try to find a matching file by title-word overlap
    best_match: Path | None = None
    best_score = 0.0

    for md_file in literature_dir.glob("*.md"):
        if md_file.name.startswith("_"):
            continue
        file_stem = md_file.stem
        file_norm = _normalize(file_stem)

        # Quick check: does the queue stem (normalized) appear as a prefix?
        if file_norm.startswith(queue_norm):
            return md_file

        # Check year match
        queue_year = queue_stem[:4] if len(queue_stem) >= 4 else ""
        file_year = file_stem[:4] if len(file_stem) >= 4 else ""
        if queue_year != file_year:
            continue

        # Compare title words (after year-author)
        file_title_words = _extract_title_words(file_stem)
        queue_title_set = set(_normalize(w) for w in queue_title_words)
        file_title_set = set(_normalize(w) for w in file_title_words)

        if not queue_title_set or not file_title_set:
            continue

        # Jaccard similarity on title words
        intersection = query_title_set = queue_title_set & file_title_set
        union = queue_title_set | file_title_set
        score = len(intersection) / len(union) if union else 0.0

        # Also check: are all queue title words contained in the file?
        containment = len(queue_title_set & file_title_set) / len(queue_title_set)

        effective_score = max(score, containment)
        if effective_score > best_score:
            best_score = effective_score
            best_match = md_file

    if best_match and best_score >= 0.6:
        return best_match

    return None


def fetch_abstract_by_doi(doi: str, timeout: int = 10) -> str | None:
    """Fetch abstract from Semantic Scholar by DOI."""
    encoded = urllib.parse.quote(doi, safe="")
    url = f"{S2_BASE}/DOI:{encoded}?fields=abstract"
    try:
        req = urllib.request.Request(url, headers=_s2_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        abstract = data.get("abstract") or ""
        return abstract if abstract else None
    except Exception as e:
        logger.debug("S2 DOI lookup failed for %s: %s", doi, e)
        return None


def fetch_abstract_pubmed_doi(doi: str, timeout: int = 10) -> str | None:
    """Fetch abstract from PubMed by DOI (search then fetch)."""
    email = os.environ.get("NCBI_EMAIL", "")
    api_key = os.environ.get("NCBI_API_KEY", "")
    if not email:
        return None

    # Search for PMID by DOI
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": f"{doi}[doi]",
        "retmode": "json",
        "email": email,
        **({"api_key": api_key} if api_key else {}),
    })
    search_url = f"{PUBMED_ESEARCH}?{params}"
    try:
        req = urllib.request.Request(search_url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return None
        pmid = id_list[0]
    except Exception:
        return None

    # Fetch abstract by PMID
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "xml",
        "email": email,
        **({"api_key": api_key} if api_key else {}),
    })
    fetch_url = f"{PUBMED_EFETCH}?{params}"
    try:
        req = urllib.request.Request(fetch_url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_text = resp.read().decode("utf-8")

        # Parse abstract from XML
        abstract_parts = []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        for abstract_el in root.iter("Abstract"):
            for text_el in abstract_el.iter("AbstractText"):
                label = text_el.get("Label", "")
                text_content = "".join(text_el.itertext()).strip()
                if text_content:
                    if label:
                        abstract_parts.append(f"**{label}**: {text_content}")
                    else:
                        abstract_parts.append(text_content)

        if abstract_parts:
            return "\n\n".join(abstract_parts)
        return None
    except Exception:
        return None


def fetch_abstract_by_title(title: str, timeout: int = 10) -> str | None:
    """Fetch abstract from Semantic Scholar by title search."""
    encoded = urllib.parse.quote(title)
    url = f"{S2_SEARCH}?query={encoded}&limit=3&fields=title,abstract"
    try:
        req = urllib.request.Request(url, headers=_s2_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        papers = data.get("data", [])
        if not papers:
            return None
        title_lower = title.lower().strip()
        for paper in papers:
            p_title = (paper.get("title") or "").lower().strip()
            if p_title and _title_similarity(title_lower, p_title) > 0.7:
                abstract = paper.get("abstract") or ""
                if abstract:
                    return abstract
        return None
    except Exception as e:
        logger.debug("S2 title search failed for '%s': %s", title[:60], e)
        return None


def _title_similarity(a: str, b: str) -> float:
    """Simple word-overlap Jaccard similarity."""
    words_a = set(re.findall(r"\w+", a))
    words_b = set(re.findall(r"\w+", b))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def read_frontmatter(filepath: Path) -> dict:
    """Read YAML frontmatter from a markdown file."""
    text = filepath.read_text(errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        fm = yaml.safe_load(text[3:end])
        return fm if isinstance(fm, dict) else {}
    except Exception:
        return {}


def update_abstract_section(filepath: Path, abstract: str) -> bool:
    """Replace the Abstract section content in a literature note.

    Replaces everything between '## Abstract\\n' and '\\n## Key Points'
    with the new abstract text.
    """
    text = filepath.read_text(errors="replace")

    abs_match = re.search(r"(## Abstract\n)", text)
    kp_match = re.search(r"\n(## Key Points)", text)

    if abs_match is None or kp_match is None:
        logger.error("Could not find Abstract/Key Points sections in %s", filepath.name)
        return False

    abs_end = abs_match.end()
    kp_start = kp_match.start()

    new_text = text[:abs_end] + abstract + "\n" + text[kp_start:]

    filepath.write_text(new_text)
    return True


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not QUEUE_PATH.exists():
        logger.error("Queue file not found: %s", QUEUE_PATH)
        sys.exit(1)

    queue = json.loads(QUEUE_PATH.read_text())

    blocked = [e for e in queue if e.get("status") == "blocked"]
    logger.info("Found %d blocked queue entries", len(blocked))

    if not blocked:
        logger.info("Nothing to do")
        return

    results = {"populated": 0, "failed": 0, "skipped": 0, "details": []}

    for entry in blocked:
        source_rel = entry.get("source", "")

        # Resolve actual file path (handles truncated/mismatched queue paths)
        actual_path = resolve_actual_file(source_rel, LITERATURE_DIR)

        if actual_path is None:
            logger.warning("No matching file found for queue source: %s", source_rel)
            results["skipped"] += 1
            results["details"].append({"file": source_rel, "status": "no_match"})
            continue

        # Fix queue source path if it was wrong
        actual_rel = str(actual_path.relative_to(VAULT_ROOT))
        if actual_rel != source_rel:
            logger.info("  Queue path fix: %s -> %s", source_rel, actual_rel)
            entry["source"] = actual_rel

        fm = read_frontmatter(actual_path)
        doi = fm.get("doi", "")
        title = fm.get("title", "")

        logger.info("Processing: %s (DOI: %s)", actual_path.name, doi or "none")

        # Fetch abstract with cascade: S2 by DOI -> PubMed by DOI -> S2 by title
        abstract = None

        if doi:
            abstract = fetch_abstract_by_doi(doi)
            if abstract:
                logger.info("  -> Got abstract via S2 DOI (%d chars)", len(abstract))

        if not abstract and doi:
            abstract = fetch_abstract_pubmed_doi(doi)
            if abstract:
                logger.info("  -> Got abstract via PubMed DOI (%d chars)", len(abstract))

        if not abstract and title:
            abstract = fetch_abstract_by_title(title)
            if abstract:
                logger.info("  -> Got abstract via S2 title search (%d chars)", len(abstract))

        if not abstract:
            logger.warning("  -> FAILED: No abstract found for %s", actual_path.name)
            results["failed"] += 1
            results["details"].append({
                "file": actual_path.name,
                "doi": doi,
                "status": "no_abstract_found",
            })
            # Still fix the queue source path even if abstract fetch failed
            time.sleep(0.3)
            continue

        if dry_run:
            logger.info("  -> [DRY RUN] Would update with %d-char abstract", len(abstract))
            results["populated"] += 1
            results["details"].append({
                "file": actual_path.name,
                "doi": doi,
                "status": "dry_run_ok",
                "abstract_len": len(abstract),
            })
        else:
            if update_abstract_section(actual_path, abstract):
                entry["status"] = "pending"
                entry.pop("blocked_reason", None)
                results["populated"] += 1
                results["details"].append({
                    "file": actual_path.name,
                    "doi": doi,
                    "status": "populated",
                    "abstract_len": len(abstract),
                })
                logger.info("  -> Updated file and queue entry")
            else:
                results["failed"] += 1
                results["details"].append({
                    "file": actual_path.name,
                    "doi": doi,
                    "status": "file_update_failed",
                })

        # Rate limit: S2 allows ~100 req/5min without key, PubMed ~3/sec
        time.sleep(0.5)

    # Save updated queue
    if not dry_run:
        QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False))
        logger.info("Updated queue.json")

    # Summary
    logger.info(
        "\nSummary: %d populated, %d failed, %d skipped (of %d blocked)",
        results["populated"],
        results["failed"],
        results["skipped"],
        len(blocked),
    )

    failed_list = [
        d for d in results["details"]
        if d["status"] in ("no_abstract_found", "file_update_failed", "no_match")
    ]
    if failed_list:
        logger.info("\nFailed/skipped entries:")
        for f in failed_list:
            logger.info(
                "  - %s (DOI: %s) -- %s",
                f["file"],
                f.get("doi", ""),
                f["status"],
            )


if __name__ == "__main__":
    main()
