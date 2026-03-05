---
description: "Literature pipeline data flow -- multi-source search, abstract fallback chains, note creation, and queue entry for /literature skill"
type: development
status: complete
created: 2026-03-03
updated: 2026-03-05
---

# Literature Pipeline: Search, Fallbacks, and Note Population

Development tracking document for the `/literature` skill's data flow -- from multi-source search through abstract fallback chains to note creation and queue entry.

---

## Architecture Overview

```
User query
    |
    v
search_all_sources()                    <-- search_interface.py
    |--- PubMed (EUTILS)
    |--- arXiv (Atom API)
    |--- Semantic Scholar (Graph API)
    |--- OpenAlex (Works API)
    |
    v
_dedup_results()                        <-- DOI-primary, source_id-secondary
    |
    v
_enrich_results()                       <-- CrossRef + Unpaywall (citation count, PDF URL)
    |
    v
_fill_missing_abstracts()               <-- S2 DOI lookup -> PubMed EFetch fallback
    |
    v
save_results_json()                     <-- ops/queue/.literature_results.json
    |
    v
[Agent displays preview table, user selects indices]
    |
    v
create_notes_from_results()             <-- Reads from JSON, NOT agent context
    |--- Abstract quality gate           <-- PubMed fallback for empty, warns on short
    |--- DOI duplicate check
    |--- build_literature_note()         <-- note_builder.py
    |
    v
create_queue_entries()                  <-- ops/queue/queue.json
    |
    v
/ralph N                                <-- reduce -> reflect -> reweave -> verify
```

---

## Search Backends

### Configured Sources (`ops/config.yaml`)

```yaml
literature:
  sources: [pubmed, arxiv, semantic_scholar, openalex]
  default: all
  enrichment:
    enabled: [crossref, unpaywall]
    timeout_per_doi: 5
```

### Per-Backend Characteristics

| Backend | API | Auth | Abstract | DOI | Citations | PDF URL |
|---------|-----|------|----------|-----|-----------|---------|
| PubMed | EUTILS (esearch + efetch) | `NCBI_EMAIL` required, `NCBI_API_KEY` optional | Full structured (section labels bolded as Markdown) | From `ArticleIdList`, can be absent | No | No |
| arXiv | Atom feed | None | Always present | From arxiv namespace, often empty for preprints | No | Always (`/pdf/` URL) |
| Semantic Scholar | Graph API v1 | `S2_API_KEY` optional (rate-limited without) | Frequently `null` for older papers | From `externalIds.DOI` | `citationCount` (richest source) | From `openAccessPdf` |
| OpenAlex | Works API | `OPENALEX_API_KEY` required | Reconstructed from inverted index | Strips `https://doi.org/` prefix | `cited_by_count` (native) | `primary_location.pdf_url` or `open_access.oa_url` |

### Backend Registry

Backends are imported lazily via `_SOURCE_REGISTRY` in `search_interface.py`. Each entry maps to `(module_path, search_function, ArticleResult_converter)`. A backend failure is caught and logged; the pipeline continues with remaining sources.

---

## Deduplication

`_dedup_results()` runs a single pass over the merged result list:

1. **Primary key:** `doi.lower()` -- cross-source dedup works when DOI is present
2. **Secondary key:** `source_id` (e.g., `PMID:12345`, `S2:abc123`) -- same-source dedup only, since IDs are backend-namespaced
3. **Tie-breaking:** `_completeness()` score -- `citation_count is not None` (+2), `abstract is truthy` (+1). Higher-completeness entry replaces the stored entry in-place.

**Limitation:** Papers without DOI found in multiple sources will not be cross-deduplicated.

---

## Enrichment

`_enrich_results()` runs after dedup, before abstract fallback. For each result with a DOI:

| Enricher | Fills | Source |
|----------|-------|--------|
| CrossRef | `citation_count` (`is-referenced-by-count`), `pdf_url` (application/pdf link, prefers version of record) | `crossref.py` |
| Unpaywall | `pdf_url` (`best_oa_location.url_for_pdf`) | `unpaywall.py` |

Both enrichers only fill **missing** fields -- never overwrite existing values. They run sequentially for every DOI.

---

## Abstract Fallback Chain

There are two separate abstract-fill passes in the pipeline:

### Pass 1: At search time (`_fill_missing_abstracts`)

Runs as the last step of `search_all_sources()`, after enrichment. Targets results where `abstract` is empty AND `doi` is non-empty.

```
For each result with empty abstract + DOI:
    |
    +-- Attempt 1: Semantic Scholar paper detail
    |   GET /graph/v1/paper/DOI:{doi}?fields=abstract
    |   Success -> assign abstract, continue to next result
    |   Failure -> fall through
    |
    +-- Attempt 2: PubMed EFetch via DOI
        pubmed.fetch_abstract_by_doi(doi):
            esearch.fcgi?term={doi}[doi] -> get PMID
            fetch_articles([pmid]) -> extract abstract
        Success -> assign abstract, continue
        Failure -> give up, abstract stays empty
```

Logging: summary line at end with `Filled N/M missing abstracts (S2: X, PubMed: Y)`.

### Pass 2: At note-write time (`create_notes_from_results`)

A second PubMed-only fallback runs when creating notes. This catches cases where:
- The JSON was written from a session that skipped `search_all_sources()` (e.g., manual JSON)
- S2 was down during the search pass

```
For each note being created:
    |
    +-- If abstract empty AND doi present:
    |   Attempt PubMed fallback (fetch_abstract_by_doi)
    |   Success -> abstract_status = "pubmed_fallback"
    |   Failure -> abstract_status = "empty" (warning logged)
    |
    +-- If abstract present but < 200 chars AND not pubmed_fallback:
        abstract_status = "short" (warning logged)
    |
    +-- Otherwise:
        abstract_status = "full"
```

### Abstract Status Values

| Status | Meaning | Downstream Impact |
|--------|---------|-------------------|
| `full` | Abstract >= 200 chars from original source | Normal processing |
| `pubmed_fallback` | Empty abstract recovered via PubMed at write time | Normal processing (may be shorter than usual) |
| `short` | Abstract < 200 chars, possibly truncated | Warning only; note created, queued for /reduce |
| `empty` | No abstract available from any source | Warning: "will block downstream /reduce extraction" |

---

## Note Creation

`create_notes_from_results()` reads from `ops/queue/.literature_results.json` -- never from agent context. This is the critical design decision that prevents abstract truncation.

### Steps

1. Load JSON, iterate over user-selected indices (1-based)
2. DOI duplicate check: scan `_research/literature/*.md` frontmatter for matching DOI
3. Abstract quality gate (see above)
4. Build note via `note_builder.build_literature_note()`
5. Generate filename: `{year}-{first_author_last}-{title_slug}.md`
   - Author: last token of first author name; if single char (initial), use first token instead
   - Title: first 10 words, trailing stopwords stripped, max 120 char stem
6. Collision handling: append `-2`, `-3`, etc. if file exists
7. Write file, return metadata dict

### Note Template

```yaml
---
type: literature
title: "..."
doi: "..."
authors: [...]
year: "YYYY"
journal: "..."
tags: [literature, {source_type}, {goal_tag}]
status: unread
created: YYYY-MM-DD
---

## Abstract
{full abstract text}

## Key Points
-

## Methods Notes

## Relevance

## Citations
```

---

## Queue Entry Creation

`create_queue_entries()` accepts the return value of `create_notes_from_results()` and writes to `ops/queue/queue.json`.

- Only notes with `status == "created"` are queued (skipped/error entries excluded)
- Deduplicates against existing queue entries by `source` path
- Computes relative paths from vault root
- Queue ID: `extract-{filename_stem}`

### Queue Entry Format

```json
{
  "id": "extract-2024-smith-single-cell-rna-seq",
  "type": "extract",
  "status": "pending",
  "source": "_research/literature/2024-smith-single-cell-rna-seq.md",
  "created": "2026-03-03T...",
  "current_phase": "reduce",
  "completed_phases": []
}
```

---

## Known Limitations

### Active Issues

1. **No gate blocks empty-abstract notes from queuing.** Notes with `abstract_status: "empty"` are queued for `/reduce` with a warning only. The `/reduce` skill will likely extract zero claims from an empty abstract, wasting a processing cycle.

2. **OpenAlex abstract reconstruction loses punctuation fidelity.** The inverted-index format stores word positions but not whitespace or punctuation context. Reconstructed abstracts have spaces between all words, including before commas and periods.

3. **Cross-session deduplication is DOI-only.** Papers without DOI (preprints, some arXiv results) can be saved multiple times across sessions. The `_check_doi_duplicate()` scan does not check by title similarity.

4. **S2 `source_id` vs PubMed `source_id` do not cross-deduplicate.** Backend-namespaced IDs (`PMID:X` vs `S2:Y`) mean the same paper without a DOI appears as two distinct results.

### Resolved Issues (2026-03-03)

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| 31 literature stubs had empty/truncated abstracts | `_fill_missing_abstracts()` only tried S2, no PubMed fallback | Added PubMed EFetch as secondary fallback in `_fill_missing_abstracts()` |
| Empty abstracts written silently to notes | No quality gate in `create_notes_from_results()` | Added abstract quality gate with PubMed fallback + `abstract_status` tracking |
| Queue entry paths mismatched actual filenames | Agent manually constructed queue JSON from display context | Added `create_queue_entries()` that uses actual file paths from note creation |
| Agent wrote abstracts from display context (~400 char limit) | SKILL.md did not enforce Python-only note creation | SKILL.md updated to require `create_notes_from_results()`, never manual abstract passing |

---

## File Index

| File | Role |
|------|------|
| `_code/src/engram_r/search_interface.py` | Main orchestrator: search, dedup, enrich, abstract fallback, note creation, queue creation |
| `_code/src/engram_r/pubmed.py` | PubMed EUTILS search + `fetch_abstract_by_doi()` |
| `_code/src/engram_r/arxiv.py` | arXiv Atom API search |
| `_code/src/engram_r/semantic_scholar.py` | Semantic Scholar Graph API search |
| `_code/src/engram_r/openalex.py` | OpenAlex Works API search |
| `_code/src/engram_r/crossref.py` | CrossRef metadata enrichment |
| `_code/src/engram_r/unpaywall.py` | Unpaywall open-access PDF enrichment |
| `_code/src/engram_r/note_builder.py` | Note template builder |
| `_code/src/engram_r/literature_types.py` | `ArticleResult` dataclass + converters |
| `.claude/skills/literature/SKILL.md` | Agent orchestration instructions |
| `ops/config.yaml` | Source, enrichment, and pipeline configuration |
| `ops/queue/queue.json` | Processing queue state |
| `ops/queue/.literature_results.json` | Temporary search results (consumed by note creation) |

---

## Test Coverage

| Module | Test File | New Tests (2026-03-03) |
|--------|-----------|----------------------|
| `pubmed.fetch_abstract_by_doi` | `tests/test_pubmed.py::TestFetchAbstractByDoi` | 4 tests |
| `_fill_missing_abstracts` PubMed fallback | `tests/test_search_interface.py::TestFillMissingAbstractsPubMedFallback` | 3 tests |
| Abstract quality gate | `tests/test_search_interface.py::TestCreateNotesFromResults::test_abstract_status_*` | 4 tests |
| `create_queue_entries` | `tests/test_search_interface.py::TestCreateQueueEntries` | 7 tests |
