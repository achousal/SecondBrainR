"""Populate blocked literature stubs with full abstracts from Semantic Scholar.

Reads queue.json for blocked entries, fetches full abstracts by DOI
(or title search for papers without DOI), updates the literature note
files, and flips queue status from blocked -> pending.

Usage:
    uv run --directory _code python scripts/populate_stubs.py [--dry-run]
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent
QUEUE_PATH = VAULT_ROOT / "ops" / "queue" / "queue.json"
LITERATURE_DIR = VAULT_ROOT / "_research" / "literature"

S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


def _s2_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


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
        # Match by title similarity (case-insensitive containment)
        title_lower = title.lower().strip()
        for paper in papers:
            p_title = (paper.get("title") or "").lower().strip()
            if p_title and (
                p_title in title_lower
                or title_lower in p_title
                or _title_similarity(title_lower, p_title) > 0.8
            ):
                abstract = paper.get("abstract") or ""
                if abstract:
                    return abstract
        # Fallback: return first result with abstract
        for paper in papers:
            abstract = paper.get("abstract") or ""
            if abstract:
                logger.warning(
                    "Title match uncertain for '%s' -- using first S2 result",
                    title[:60],
                )
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

    # Find the abstract section boundaries
    abs_match = re.search(r"(## Abstract\n)", text)
    kp_match = re.search(r"\n(## Key Points)", text)

    if abs_match is None or kp_match is None:
        logger.error("Could not find Abstract/Key Points sections in %s", filepath.name)
        return False

    abs_end = abs_match.end()
    kp_start = kp_match.start()

    # Build new content
    new_text = text[:abs_end] + abstract + "\n" + text[kp_start:]

    filepath.write_text(new_text)
    return True


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not QUEUE_PATH.exists():
        logger.error("Queue file not found: %s", QUEUE_PATH)
        sys.exit(1)

    queue = json.loads(QUEUE_PATH.read_text())

    # Find all blocked entries
    blocked = [e for e in queue if e.get("status") == "blocked"]
    logger.info("Found %d blocked queue entries", len(blocked))

    if not blocked:
        logger.info("Nothing to do")
        return

    results = {"populated": 0, "failed": 0, "skipped": 0, "details": []}

    for entry in blocked:
        source_rel = entry.get("source", "")
        source_path = VAULT_ROOT / source_rel

        if not source_path.exists():
            logger.warning("Source file not found: %s", source_rel)
            results["skipped"] += 1
            results["details"].append({"file": source_rel, "status": "file_not_found"})
            continue

        fm = read_frontmatter(source_path)
        doi = fm.get("doi", "")
        title = fm.get("title", "")

        logger.info("Processing: %s (DOI: %s)", source_path.name, doi or "none")

        # Fetch abstract
        abstract = None
        if doi:
            abstract = fetch_abstract_by_doi(doi)
            if abstract:
                logger.info("  -> Got abstract via DOI (%d chars)", len(abstract))

        if not abstract and title:
            abstract = fetch_abstract_by_title(title)
            if abstract:
                logger.info("  -> Got abstract via title search (%d chars)", len(abstract))

        if not abstract:
            logger.warning("  -> FAILED: No abstract found for %s", source_path.name)
            results["failed"] += 1
            results["details"].append({
                "file": source_path.name,
                "doi": doi,
                "status": "no_abstract_found",
            })
            continue

        if dry_run:
            logger.info("  -> [DRY RUN] Would update with %d-char abstract", len(abstract))
            results["populated"] += 1
            results["details"].append({
                "file": source_path.name,
                "doi": doi,
                "status": "dry_run_ok",
                "abstract_len": len(abstract),
            })
        else:
            if update_abstract_section(source_path, abstract):
                # Update queue entry
                entry["status"] = "pending"
                entry.pop("blocked_reason", None)
                results["populated"] += 1
                results["details"].append({
                    "file": source_path.name,
                    "doi": doi,
                    "status": "populated",
                    "abstract_len": len(abstract),
                })
                logger.info("  -> Updated file and queue entry")
            else:
                results["failed"] += 1
                results["details"].append({
                    "file": source_path.name,
                    "doi": doi,
                    "status": "file_update_failed",
                })

        # Rate limit: S2 allows ~100 req/5min without key
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

    # Print details for failed entries
    failed = [d for d in results["details"] if d["status"] in ("no_abstract_found", "file_update_failed")]
    if failed:
        logger.info("\nFailed entries:")
        for f in failed:
            logger.info("  - %s (DOI: %s) -- %s", f["file"], f.get("doi", ""), f["status"])


if __name__ == "__main__":
    main()
