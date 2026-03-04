---
description: "Plan for expanding literature search beyond PubMed and arXiv to cross-domain academic APIs"
type: development
status: complete
created: 2026-02-28
---

# Literature Source Expansion

## Motivation

Expand literature search beyond PubMed and arXiv to cross-domain academic APIs. Broadens utility across research domains (social sciences, humanities, engineering, interdisciplinary work) and adds capabilities like citation graphs, open access link resolution, and preprint coverage.

## Architecture

All sources conform to a common interface defined in `literature_types.py`:

- **`ArticleResult`** dataclass -- unified result type with `source_id`, `title`, `authors`, `abstract`, `year`, `doi`, `source_type`, `url`, `journal`, `categories`, `pdf_url`, `citation_count`, `raw_metadata`
- **`LiteratureSource`** Protocol -- `name`, `requires_key`, `env_var`, `search()` returning `list[ArticleResult]`
- **Per-source modules** (`pubmed.py`, `arxiv.py`, `semantic_scholar.py`, `openalex.py`) -- each has its own dataclass + search function; `ArticleResult.from_*()` converters bridge to the unified type
- **Source registry** -- `_SOURCE_REGISTRY` in `search_interface.py` maps config names to `(module, search_fn, converter)` tuples; lazy-imports modules at search time
- **Enrichment layers** (`crossref.py`, `unpaywall.py`) -- post-process `ArticleResult` lists by DOI, filling missing `citation_count` and `pdf_url` via `_ENRICHER_REGISTRY`
- **Unified entry point** -- `search_all_sources()` handles single-source and multi-source modes, dedup, enrichment, and sort
- **Backward compat** -- `search_interface.py` re-exports `ArticleResult` as `SearchResult`
- **Note rendering** via `note_builder.build_literature_note()` -- source-agnostic, injects `source_type` tag
- **Config** -- `ops/config.yaml` `literature:` section lists enabled sources, default, and enrichment settings

Adding a search source requires: one Python module (~100-150 lines, stdlib only), a `from_*()` converter on `ArticleResult`, a `_SOURCE_REGISTRY` entry, and env var documentation. Adding an enricher requires: one Python module (~100 lines), a `_ENRICHER_REGISTRY` entry.

## Candidate Sources

### Tier 1 -- High value, clean APIs

| Source | Coverage | API Key | Rate Limits | Value |
|--------|----------|---------|-------------|-------|
| Semantic Scholar | 200M+ papers, all disciplines | Free, optional | 1 req/s shared without, 1 req/s dedicated with | Citation graph, recommendations, embeddings. Best single addition for cross-domain reach |
| OpenAlex | 250M+ works, all disciplines | None (email for polite pool) | Very generous | Fully open. Concepts, institutions, authors as entities. Successor to Microsoft Academic |

### Tier 2 -- Domain-specific value

| Source | Coverage | API Key | Value |
|--------|----------|---------|-------|
| bioRxiv/medRxiv | Life sciences preprints | None | Preprints not yet indexed by PubMed. Cold Spring Harbor API |
| Europe PMC | Extends PubMed + European preprints + patents | None | Broader biomedical + patent literature |

### Tier 3 -- Utility (enhances other sources)

| Source | Purpose | API Key |
|--------|---------|---------|
| CrossRef | DOI resolution, citation metadata | None (email for polite pool) |
| Unpaywall | Open access PDF links for any DOI | Email only |

### Not recommended

- **Google Scholar** -- no official API, scraping violates TOS
- **Scopus / Web of Science** -- institutional subscriptions, restrictive API access
- **IEEE / ACM** -- narrow coverage, institutional access often required

## Implementation Plan

### Phase 1 -- Formalize the interface (DONE)

Implemented 2026-02-28. Evolved `SearchResult` from `search_interface.py` into `ArticleResult` in a new `literature_types.py`. Added `from_semantic_scholar()` and `from_openalex()` converters alongside the existing `from_pubmed()` and `from_arxiv()`. Added a first-class `citation_count` field (replaces the planned `extra` dict for this common case). Defined `LiteratureSource` Protocol with `name`, `requires_key`, `env_var`, `search()`. Backward-compatible alias `SearchResult = ArticleResult` in `search_interface.py`.

- `_code/src/engram_r/literature_types.py` -- `ArticleResult` dataclass + `LiteratureSource` Protocol
- `_code/src/engram_r/search_interface.py` -- re-exports `ArticleResult` as `SearchResult`, keeps `resolve_search_backends()`
- `_code/tests/test_literature_types.py` -- 40 tests: all 4 converters, protocol conformance, alias identity, citation_count

### Phase 2 -- Source registry in config (DONE)

Implemented 2026-02-28. Added `literature:` section to `ops/config.yaml` with all four sources enabled and `default: pubmed`.

```yaml
literature:
  sources:
    - pubmed
    - arxiv
    - semantic_scholar
    - openalex
  default: pubmed
```

The `/literature` skill reads this list to populate the source selection prompt. Sources not in the list are hidden from the user but remain available programmatically.

### Phase 3 -- Semantic Scholar integration (DONE)

Implemented 2026-02-28.

- `_code/src/engram_r/semantic_scholar.py` (~118 lines) -- `SemanticScholarArticle` dataclass, `search_semantic_scholar()` function
- `_code/tests/test_semantic_scholar.py` -- 16 mock-based tests
- Stdlib only (`urllib`, `json`)
- API: `https://api.semanticscholar.org/graph/v1/paper/search`
- Fields: paperId, title, authors, abstract, year, venue, journal, externalIds (DOI), citationCount, url, openAccessPdf
- Env var: `S2_API_KEY` (optional, shared anonymous pool without, dedicated pool with)
- Extra capabilities to expose later: citation graph traversal, paper recommendations

### Phase 4 -- OpenAlex integration (DONE)

Second new source. Implemented 2026-02-28.

**API change (Feb 2026):** OpenAlex now requires a free API key via `api_key` query param. The old `mailto` polite pool is gone. Env var: `OPENALEX_API_KEY`.

- `_code/src/engram_r/openalex.py` (~120 lines)
- `_code/tests/test_openalex.py` (~170 lines)
- Stdlib only
- API: `https://api.openalex.org/works?search=...`
- Auth: `api_key` query param from `OPENALEX_API_KEY` env var (optional for testing)
- Fields: id, title, authorships, abstract_inverted_index (reconstructed to plaintext), publication_year, primary_location.source.display_name, doi
- Extra: cited_by_count, open_access PDF URL, landing page URL

### Phase 5 -- Enrichment layers (DONE) + remaining utility sources

**CrossRef and Unpaywall** implemented 2026-02-28 as enrichment layers (not search backends). They post-process `ArticleResult` lists by DOI, filling missing `citation_count` and `pdf_url` fields without overwriting existing data.

- `_code/src/engram_r/crossref.py` (~107 lines) -- `CrossRefMetadata` dataclass, `fetch_crossref_metadata()` function
- `_code/src/engram_r/unpaywall.py` (~96 lines) -- `UnpaywallMetadata` dataclass, `fetch_unpaywall_metadata()` function
- `_code/tests/test_crossref.py` -- 19 tests: DOI normalization, URL building, response parsing, network error handling
- `_code/tests/test_unpaywall.py` -- 15 tests: DOI normalization, email requirement, response parsing, edge cases
- Stdlib only (`urllib`, `json`)
- Enrichment wired into `search_all_sources()` via `_enrich_results()` and `_ENRICHER_REGISTRY` in `search_interface.py`
- Config: `ops/config.yaml` `literature.enrichment.enabled` list (empty by default, add `crossref` and/or `unpaywall` to activate)
- Env var: `LITERATURE_ENRICHMENT_EMAIL` (shared between CrossRef polite pool and Unpaywall TOS requirement)
- CrossRef API: `https://api.crossref.org/works/{doi}` -- no key, email for polite pool
- Unpaywall API: `https://api.unpaywall.org/v2/{doi}?email={email}` -- email mandatory per TOS
- Enrichment runs after dedup and before sort in `search_all_sources()`, never overwrites existing data

**Remaining (not implemented):**

- **bioRxiv/medRxiv**: `https://api.biorxiv.org/details/...` -- simple JSON API, no key. Would be a search source, not an enrichment layer.

### Phase 6 -- Skill and UX updates (DONE)

Implemented 2026-02-28.

- [x] Update `/literature` skill to present available sources from config (done -- SKILL.md lists all four)
- [x] Add "all" option that searches multiple sources and deduplicates by DOI
- [x] Display source name in the results table
- [x] Add source-specific tags to saved notes (e.g., `semantic_scholar`, `openalex`)

New code:
- `search_interface.py`: `resolve_literature_sources()`, `_search_single_source()`, `_dedup_results()`, `search_all_sources()`, `_resolve_enrichment_config()`, `_enrich_results()`, `_ENRICHER_REGISTRY`
- `note_builder.py`: added `source_type` parameter to `build_literature_note()`
- SKILL.md: updated workflow to always use `search_all_sources()` for both single-source and "all" modes, source column, source tags

Dedup strategy: DOI (primary, case-insensitive) -> source_id (fallback). When duplicates found, keeps the result with more metadata (citation_count > abstract > first seen). Results sorted by citation count descending, nulls last.

Config example including enrichment:
```yaml
literature:
  sources:
    - pubmed
    - arxiv
    - semantic_scholar
    - openalex
  default: pubmed
  enrichment:
    enabled: []               # Add crossref and/or unpaywall to activate
    timeout_per_doi: 5
```

### Phase 7 -- Inline setup flow in onboarding (DONE)

Implemented 2026-03-02. Eliminated the third-command gap: users previously had to run `/literature --setup` after `/onboard` + `/init` before their first search worked. Now API key configuration is offered inline during `/onboard` Turn 3, with a lightweight nudge in `/init` Phase 0.

**Design decisions:**
- Offer inline setup, never block -- user can always "skip" and configure later
- Show `export` commands for the user to paste in another terminal -- do not write to shell config files
- Include profile-specific guidance explaining WHY each source matters for the user's domain (e.g., "PubMed is the primary database for biomedical literature")

**New file:**
- `.claude/skills/literature/reference/setup-flow.md` (~116 lines) -- shared reference document with 5-step interactive setup loop (present status, profile guidance, export commands, re-check loop, additional setup options). Read by `/literature`, `/onboard`, and any future orchestrator.

**Edited files:**
- `.claude/skills/literature/SKILL.md` -- replaced inline 40-line Setup Flow section (lines 99-139) with 3-line reference to `setup-flow.md`. Trigger logic in Step 0 unchanged.
- `.claude/skills/onboard/SKILL.md` Turn 3 (lines 271-303) -- replaced "inform and defer" block with inline setup gate: `check_literature_readiness()` -> if ready proceed, if not -> read `setup-flow.md`, present status + domain guidance + export commands, interactive check/skip loop, store ready state for Phase 5 summary.
- `.claude/skills/onboard/SKILL.md` Phase 5 -- conditional "What's Next": if setup completed during Turn 3, omit `/literature --setup` note; if skipped, keep the nudge.
- `.claude/skills/init/SKILL.md` Phase 0 (after infrastructure check) -- added lightweight readiness nudge: one-line message with missing var count and names, no interactive loop.

**Flow:** `/onboard` Turn 3: domain profile activated -> `check_literature_readiness()` -> missing vars -> status table with profile-specific guidance -> export commands -> user pastes keys in another terminal -> says "check" -> re-run readiness, report delta -> repeat or "skip" -> proceed to Generate Approval. `/literature --setup` remains the standalone fallback (reads same `setup-flow.md`). `/init` prints a one-liner if keys are still missing.

**No Python changes.** `check_literature_readiness()` and domain profile `env_vars` already provide everything needed.

## API Key Management

### Current pattern (preserve this)

- Keys in `~/.zshenv_secrets` for interactive use
- Keys in `_code/.env` for daemon use
- Modules check `os.environ.get()` and degrade gracefully -- never hard-fail on missing key
- README documents what each key provides vs. the degraded experience

### New keys

| Env Var | Source | Required | Degraded behavior |
|---------|--------|----------|-------------------|
| `S2_API_KEY` | Semantic Scholar | No | Shared anonymous pool (1 req/s shared) instead of dedicated pool |
| `OPENALEX_API_KEY` | OpenAlex | No | Anonymous pool (lower rate limits) |
| `LITERATURE_ENRICHMENT_EMAIL` | CrossRef + Unpaywall | No | CrossRef: works without (no polite pool). Unpaywall: skipped entirely (email required by TOS) |

PubMed (`NCBI_API_KEY`) and arXiv need no new keys. bioRxiv needs no key.

## Testing Strategy

Per source module:
- Unit tests with fixture XML/JSON responses (no live API calls in CI)
- Test dataclass mapping and edge cases (missing fields, empty abstracts, structured abstracts)
- Integration smoke test (optional, live, skipped in CI via `@pytest.mark.integration`)

For the protocol:
- Test that each source module satisfies `isinstance(source, LiteratureSource)`
- Test `ArticleResult` -> `build_literature_note()` mapping for each source

### Current test coverage (219 tests across literature modules)

| Test file | Tests | Covers |
|---|---|---|
| `test_literature_types.py` | 40 | `ArticleResult` converters (all 4), `LiteratureSource` protocol, `SearchResult` alias |
| `test_search_interface.py` | 82 | `SearchResult` construction, `from_pubmed`, `from_arxiv`, `resolve_search_backends`, `resolve_literature_sources`, `_dedup_results`, `search_all_sources`, `_resolve_enrichment_config`, `_enrich_results` |
| `test_semantic_scholar.py` | 16 | `SemanticScholarArticle` parsing, API key injection, edge cases |
| `test_openalex.py` | 21 | `OpenAlexWork` parsing, abstract reconstruction, DOI stripping |
| `test_pubmed.py` | 11 | `PubMedArticle` parsing, API key handling |
| `test_arxiv.py` | 9 | `ArxivArticle` parsing, XML edge cases |
| `test_crossref.py` | 19 | DOI normalization, URL building, response parsing, `fetch_crossref_metadata` edge cases |
| `test_unpaywall.py` | 15 | DOI normalization, email requirement, response parsing, `fetch_unpaywall_metadata` edge cases |
| `test_note_builder.py` (literature subset) | 6 | `build_literature_note` structure, `source_type` tag injection, backward compat |

## Decisions to Make

- [x] Implementation order: Semantic Scholar first, or OpenAlex first (zero key friction)? **Decision: Semantic Scholar first** -- citation counts and cross-domain coverage provide the most immediate value for the co-scientist loop.
- [x] Should the `ArticleResult` dataclass live in `note_builder.py` or a new `literature_types.py`? **Decision: `literature_types.py`** -- separation of concerns; `note_builder` is rendering, `literature_types` is data modeling.
- [x] Should multi-source search ("search all") deduplicate by DOI, title similarity, or both? **Decision: DOI (primary, case-insensitive) then source_id (fallback).** Title similarity deferred -- DOI is reliable and fast; title fuzzy matching adds complexity for marginal gain at this stage.
- [x] Should CrossRef/Unpaywall be standalone sources or enrichment layers that augment results from other sources? **Decision: enrichment layers.** They post-process `ArticleResult` lists via DOI, filling missing `citation_count` and `pdf_url`. Not search backends -- they have no full-text search API. Wired into `search_all_sources()` via `_enrich_results()`.
- [x] Refactor existing PubMed/arXiv to the new protocol in-place, or keep backward compatibility wrappers? **Decision: backward-compatible alias.** `ArticleResult` evolved from `SearchResult` in `literature_types.py`; `search_interface.py` re-exports as `SearchResult`. Zero breakage -- existing imports unchanged.

## File Manifest

| File | Action | Purpose |
|------|--------|---------|
| `_code/src/engram_r/literature_types.py` | Done | `ArticleResult` dataclass, `LiteratureSource` protocol |
| `_code/src/engram_r/search_interface.py` | Done | Re-exports `ArticleResult` as `SearchResult`, source registry, dedup, enrichment pipeline, `search_all_sources()` |
| `_code/src/engram_r/pubmed.py` | Cleaned | Removed dead `search_and_fetch_unified()` wrapper (superseded by `_SOURCE_REGISTRY`) |
| `_code/src/engram_r/arxiv.py` | Cleaned | Removed dead `search_arxiv_unified()` wrapper (superseded by `_SOURCE_REGISTRY`) |
| `_code/src/engram_r/semantic_scholar.py` | Done | Semantic Scholar search module |
| `_code/src/engram_r/openalex.py` | Done | OpenAlex search module |
| `_code/src/engram_r/crossref.py` | Done | CrossRef DOI enrichment (citation counts, PDF URLs) |
| `_code/src/engram_r/unpaywall.py` | Done | Unpaywall DOI enrichment (open-access PDF URLs) |
| `_code/tests/test_semantic_scholar.py` | Done | Unit tests with fixture data (16 tests) |
| `_code/tests/test_openalex.py` | Done | Unit tests with fixture data (21 tests) |
| `_code/tests/test_crossref.py` | Done | Unit tests with fixture data (19 tests) |
| `_code/tests/test_unpaywall.py` | Done | Unit tests with fixture data (15 tests) |
| `_code/tests/test_literature_types.py` | Done | Protocol conformance tests (40 tests) |
| `_code/tests/test_search_interface.py` | Done | Search, dedup, enrichment tests (82 tests) |
| `ops/config.yaml` | Done | `literature.sources` + `literature.enrichment` sections |
| `.claude/skills/literature/reference/setup-flow.md` | Done | Shared inline setup flow reference (status, guidance, export commands, re-check loop) |
| `.claude/skills/literature/SKILL.md` | Done | Unified `search_all_sources()` path for single and multi-source, source column, source tags; setup flow extracted to reference |
| `.claude/skills/onboard/SKILL.md` | Done | Turn 3 inline setup gate with interactive check/skip loop; Phase 5 conditional nudge |
| `.claude/skills/init/SKILL.md` | Done | Phase 0 lightweight readiness nudge (one-line, no interactive loop) |
| `_code/README.md` | Done | All env vars documented |
| `_code/.env.example` | Done | Placeholders for `S2_API_KEY`, `OPENALEX_API_KEY`, `LITERATURE_ENRICHMENT_EMAIL` |
