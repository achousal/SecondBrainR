---
description: "Literature search backends, enrichment pipeline, and unified search interface"
type: manual
created: 2026-03-01
---

# Literature Search

`/literature` searches academic databases and creates structured literature
notes with full provenance. Results are deduplicated by DOI, optionally
enriched with citation counts and open-access PDF URLs, and sorted by citation
count.

---

## Search backends

| Backend | API | Auth | What it returns |
| --- | --- | --- | --- |
| **PubMed** | [NCBI EUTILS](https://www.ncbi.nlm.nih.gov/books/NBK25500/) (esearch + efetch, XML) | `NCBI_API_KEY` + `NCBI_EMAIL` (optional; raises rate limit from 3 to 10 req/s) | PMID, title, authors, journal, year, structured abstract, DOI |
| **arXiv** | [Atom feed](http://export.arxiv.org/api/query) | None | arXiv ID, title, authors, abstract, dates, categories, PDF URL, DOI |
| **Semantic Scholar** | [Graph API v1](https://api.semanticscholar.org/) | `S2_API_KEY` (optional; dedicated rate limit) | Paper ID, title, authors, abstract, venue, year, DOI, citation count, OA PDF URL |
| **OpenAlex** | [REST API](https://docs.openalex.org/) | `OPENALEX_API_KEY` | OpenAlex ID, title, authors, reconstructed abstract, journal, year, DOI, cited-by count, PDF URL |

All backends use stdlib `urllib` only -- no third-party HTTP dependency. 30-second timeout per request.

---

## Enrichment

Two optional post-processing layers fill gaps in search results:

| Enricher      | API                     | Auth                                                         | What it adds                                        |
| ------------- | ----------------------- | ------------------------------------------------------------ | --------------------------------------------------- |
| **CrossRef**  | [CrossRef](https://api.crossref.org/) `/works/{doi}` | `LITERATURE_ENRICHMENT_EMAIL` (optional; faster rate limits) | Citation count, PDF URL (prefers version-of-record) |
| **Unpaywall** | [Unpaywall](https://unpaywall.org/) `/v2/{doi}`      | `LITERATURE_ENRICHMENT_EMAIL` (required per TOS)             | Open-access PDF URL, OA status                      |

Enable enrichers in `ops/config.yaml` under `literature.enrichment.enabled`.
Enrichment never overwrites existing data -- it only fills missing fields.

---

## Unified pipeline

`search_all_sources()` in `search_interface.py` is the main entry point:

1. Reads enabled sources from `ops/config.yaml` (`literature.sources`)
2. Dynamically imports each backend module
3. Deduplicates by DOI (primary) then source ID (fallback), keeping the most
   complete result (scores: has citation_count +2, has abstract +1)
4. Enriches missing fields via CrossRef and/or Unpaywall
5. Sorts by citation count descending (nulls last)

Backend priority for `/literature` is configured per domain profile:
`research.primary`, `research.fallback`, `research.last_resort`.

---

## Configuration

Literature search behavior is configured in two places:

- **ops/config.yaml** -- `literature.sources` (enabled backends), `literature.enrichment` (enrichers and timeout), `research.*` (backend priority chain)
- **Domain profile** (`_code/profiles/{domain}/profile.yaml`) -- `research.primary`, `research.fallback`, `research.last_resort` set the tool cascade

See [Configuration](configuration.md) for full config reference.

---

## See Also

- [Skills Reference](skills.md) -- `/literature` command details
- [Setup Guide](setup-guide.md) -- environment variables for API keys
- [Configuration](configuration.md) -- search stack and enrichment settings
