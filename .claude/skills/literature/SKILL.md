---
name: literature
description: "Search PubMed, arXiv, Semantic Scholar, and OpenAlex, create structured literature notes"
version: "1.0"
generated_from: "co-scientist-v2.0"
user-invocable: true
model: sonnet
context: fork
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
  - Write
argument-hint: "[query] | --setup | --goal [slug]"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- literature and co-scientist parameters
   - `literature.sources`: list of enabled search backends (e.g., [arxiv, semantic_scholar, openalex])
   - `literature.default`: default source selection (all | single source name)
   - `research.primary`, `research.fallback`, `research.last_resort`: search tool cascade
   - `processing.chaining`: manual | suggested | automatic
   - `co_scientist.handoff.mode`: manual | suggested | automatic

2. **`_research/goals/`** -- active research goal (if `--goal` provided)
   - Parse `project_tag` from goal frontmatter for tag inheritance on literature notes

3. **Preflight readiness check** (always run -- source `.env` so keys are visible):
```
set -a && source _code/.env 2>/dev/null && set +a && uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import check_literature_readiness
print(json.dumps(check_literature_readiness('../ops/config.yaml')))
"
```

If `result.ready` is False OR `$ARGUMENTS` contains `--setup`: enter setup flow (see Setup section).
If `result.ready` is True AND no `--setup`: proceed to EXECUTE NOW silently.

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` contains `--setup` -> run setup flow, stop (unless query also present)
- If `$ARGUMENTS` contains `--goal [slug]` -> scope search to that research goal's domain
- If `$ARGUMENTS` contains `--handoff` -> emit CO-SCIENTIST HANDOFF block at end
- Remaining text in `$ARGUMENTS` -> search query
- If no query and no `--setup` -> read vault context for suggestions, then present query options

**Execute these steps:**

1. Load literature config from `ops/config.yaml` via `resolve_literature_sources()`.
2. Run preflight readiness check. If not ready: enter setup flow.
3. Present available sources to user: sources from config plus **all**. Default is `literature.default`.
4. Ask for search query (if not provided in arguments) and source selection.
5. Execute search via `search_all_sources()` with appropriate parameters. **CRITICAL**: Immediately save results to JSON via `save_results_json()` BEFORE displaying anything. This preserves full abstracts in Python memory. Use path `ops/queue/.literature_results.json`.
6. Display results table: #, Title, Authors, Year, Source, Journal, DOI/ID, Citations. (Show abstract preview in table but DO NOT use these previews for note creation.)
7. Ask user which papers to save as literature notes. Accept comma-separated numbers or "all".
8. Create notes via `create_notes_from_results()` passing the saved JSON path, selected indices, output_dir=`_research/literature/`, and goal_tag if applicable. **NEVER manually construct abstract text or pass abstracts as arguments** -- the function reads full abstracts from the JSON file.
9. Update `_research/literature/_index.md` (create if missing).
10. Execute pipeline chaining per `processing.chaining` mode.
11. Present saved note paths. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /literature -- Literature Search and Summarize

Search PubMed, arXiv, Semantic Scholar, and OpenAlex. Create structured literature notes with full provenance. Evidence gathering -- systematic search for published findings that grounds hypotheses in existing knowledge.

## Architecture

Implements the Literature agent supporting the co-scientist system (arXiv:2502.18864). Provides the empirical substrate that /generate, /review, and /evolve build upon.

## Vault Paths

- Literature notes: `_research/literature/`
- Template: `_code/templates/literature.md`
- Index: `_research/literature/_index.md`
- Research goals: `_research/goals/`

## Code

- `_code/src/engram_r/search_interface.py` -- unified search interface, `check_literature_readiness()`, `resolve_literature_sources()`, `search_all_sources()`, `save_results_json()`, `create_notes_from_results()`, `create_queue_entries()`
- `_code/src/engram_r/pubmed.py` -- PubMed search via NCBI EUTILS
- `_code/src/engram_r/arxiv.py` -- arXiv Atom API search
- `_code/src/engram_r/semantic_scholar.py` -- Semantic Scholar Graph API search
- `_code/src/engram_r/openalex.py` -- OpenAlex REST API search
- `_code/src/engram_r/note_builder.py` -- `build_literature_note()`
- `_code/src/engram_r/obsidian_client.py` -- Obsidian REST API

## Setup Flow

Triggered when `result.ready` is False or `$ARGUMENTS` contains `--setup`.

Read and follow `.claude/skills/literature/reference/setup-flow.md`.

## Search Workflow

### Step 1: Source Resolution
Read `ops/config.yaml` `literature:` section via `resolve_literature_sources()`. Returns enabled source list and default.

### Step 2: Query and Source Selection

**Context-aware suggestions (when no query provided):**

Before prompting, read vault state to offer targeted suggestions:

1. Read `self/goals.md` -- extract active research goals (title, scope, status)
2. Count existing literature notes: `ls _research/literature/*.md 2>/dev/null | grep -cv '_index' || echo 0`
3. For each active goal, read `_research/goals/{slug}.md` -- check `Key Literature` section

**Condition for showing suggestions:** Only show goal-based search suggestions when the total literature note count (step 2) is below 5. If >= 5 literature notes already exist, the vault has literature -- even if individual goal files have empty `Key Literature` sections. Empty `Key Literature` sections with existing literature is a wiring gap (fix with linking), not a search gap.

**If total literature count < 5 AND active goals exist** (true post-init state):
- Derive 1-2 specific search queries per goal from the goal's Objective and domain
- Present as a numbered menu with goal context:

```
Your active goals need literature grounding:

  1. goal-slug: "domain-specific search query targeting primary facet"
  2. goal-slug: "domain-specific search query targeting secondary facet"
  ...

Select numbers (comma-separated), type your own query, or "all" to run all suggestions.
```

- Queries should use domain-specific terms from the goal's Objective, not generic phrases
- Each query targets a distinct facet of the goal (e.g., primary biomarkers vs confounders)
- If `--goal [slug]` was provided, only suggest queries for that goal

**Otherwise:** fall back to standard prompt: "What is your search query?"

Present available sources plus **all** option. Default is `literature.default` from config. If query provided in arguments, skip all suggestion logic.

### Step 3: Execute Search and Persist Results
Always call `search_all_sources()` from `search_interface.py`:
- **Single source**: `search_all_sources(query, sources=[chosen_source], config_path="ops/config.yaml")`
- **All sources**: `search_all_sources(query, config_path="ops/config.yaml")`

Both paths deduplicate by DOI, apply enrichment if configured, fill missing abstracts via S2 DOI fallback, sort by citation count descending.

**CRITICAL**: Immediately after search, call `save_results_json(results, "ops/queue/.literature_results.json")` to persist full results including complete abstracts. All downstream note creation MUST read from this JSON -- never from agent-rendered text.

Example (single Python call):
```python
set -a && source _code/.env 2>/dev/null && set +a && uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import search_all_sources, save_results_json
results = search_all_sources('{query}', config_path='../ops/config.yaml')
save_results_json(results, '../ops/queue/.literature_results.json')
# Print summary for display (abstracts may be truncated here -- that is OK)
for i, r in enumerate(results, 1):
    abs_preview = (r.abstract[:80] + '...') if len(r.abstract) > 80 else r.abstract
    print(f'{i}. {r.title[:60]} | {r.year} | {r.source_type} | {r.doi} | {r.citation_count or \"--\"} | abstract: {\"yes\" if r.abstract else \"MISSING\"}')
print(f'Total: {len(results)} results saved to ops/queue/.literature_results.json')
"
```

### Step 4: Display Results
Table columns: **#**, **Title**, **Authors**, **Year**, **Source**, **Journal**, **DOI/ID**, **Citations**, **Abstract** (yes/no).
Source column shows backend name (PubMed, Semantic Scholar, etc.). Citations shows count or "--" when unavailable. Abstract column shows "yes" or "MISSING" to flag gaps.

### Step 5: User Selection
Ask which papers to save as notes. Accept comma-separated numbers or "all".

### Step 6: Build Notes via Python (preserves full abstracts)
Call `create_notes_from_results()` to build and write notes entirely in Python:

```python
set -a && source _code/.env 2>/dev/null && set +a && uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import create_notes_from_results
created = create_notes_from_results(
    results_json='../ops/queue/.literature_results.json',
    indices=[{comma_separated_indices}],
    output_dir='../_research/literature/',
    goal_tag='{goal_tag_or_empty}',
)
print(json.dumps(created, indent=2))
"
```

**NEVER manually call `build_literature_note()` with abstract text from agent context.** The `create_notes_from_results()` function reads the full abstract from the JSON file, builds the note, handles filename generation, checks for DOI duplicates, and warns on empty/short abstracts (with automatic PubMed fallback for empty abstracts).

The function returns a list of dicts with keys: `index`, `path`, `title`, `doi`, `status` (created/skipped/error), `abstract_status` (full/short/empty/pubmed_fallback).

### Step 7: Update Index
Update `_research/literature/_index.md` under "Recent Additions" with wiki-link to new note.

**If `_index.md` does not exist**, create it with:
- Frontmatter: `description: "Index of structured literature notes"`, `type: moc`, `created: {today}`
- Heading: `# Literature Index`
- Sections: `## Recent Additions`, `## By Topic`

## Note Structure

Each literature note has YAML frontmatter with: type, title, doi, authors, year, journal, tags, status (unread/reading/read/cited), created date.

Sections: Abstract, Key Points, Methods Notes, Relevance, Citations.

If PubMed returns structured abstracts (labeled sections), preserve the structure.

## Pipeline Chaining

After saving literature notes and updating `_index.md`, chain to the arscontexta pipeline so literature content feeds into the knowledge graph.

**For each saved literature note**, based on `processing.chaining` mode:

| Mode | Action |
|------|--------|
| `manual` | Print `Next: /ralph` to process queued literature notes (each starts with /reduce, then reflect/reweave/verify) |
| `suggested` (default) | Create queue entries via `create_queue_entries()`, then print `Next: /ralph` (or `/ralph N` for N notes). Each task starts at the reduce phase |
| `automatic` | Create queue entries via `create_queue_entries()`, then print `Next: /ralph` (automatic execution not yet implemented) |

**CRITICAL: Always use `create_queue_entries()` to write queue entries.** Never manually construct queue JSON. The function uses actual file paths from `create_notes_from_results()`, preventing path truncation and author-name mismatches.

```python
set -a && source _code/.env 2>/dev/null && set +a && uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import create_queue_entries
# 'created' is the list returned by create_notes_from_results() in the previous step
created = {created_json_list}
entries = create_queue_entries(
    created_notes=created,
    queue_path='../ops/queue/queue.json',
    vault_root='..',
)
print(json.dumps(entries, indent=2))
"
```

Alternatively, combine note creation and queue entry creation in a single Python call:

```python
set -a && source _code/.env 2>/dev/null && set +a && uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import create_notes_from_results, create_queue_entries
created = create_notes_from_results(
    results_json='../ops/queue/.literature_results.json',
    indices=[{comma_separated_indices}],
    output_dir='../_research/literature/',
    goal_tag='{goal_tag_or_empty}',
)
entries = create_queue_entries(
    created_notes=created,
    queue_path='../ops/queue/queue.json',
    vault_root='..',
)
print(json.dumps({'notes': created, 'queue_entries': entries}, indent=2))
"
```

**Output after all notes saved:**
```
Pipeline chaining:
- Queued: _research/literature/{note1}.md (reduce)
- Queued: _research/literature/{note2}.md (reduce)

Next: /ralph {N}  -- process all queued literature notes (reduce -> reflect -> reweave -> verify, fresh context per phase)
  Or: /reduce _research/literature/{note}.md  -- process a single note manually
```

## Quality Gates

### Gate 1: Source Readiness
At least one search source must be ready after preflight. If zero sources available, enter setup flow -- do not proceed with search.

### Gate 2: DOI Deduplication
Before saving, verify no existing literature note in `_research/literature/` has the same DOI. If duplicate found: warn user, skip saving unless user overrides.

### Gate 3: Note File Exists
After `build_literature_note()` and write, verify the file exists at the expected path. If write failed: report error, continue with remaining papers.

### Gate 4: Index Consistency
After updating `_index.md`, verify the new entry appears in the file. If `_index.md` update failed: warn user but do not block -- the literature note itself is the primary artifact.

## Error Handling

| Error | Action |
|-------|--------|
| API key missing for all sources | Enter setup flow. If `--handoff`: HANDOFF `status: failed`, summary: "no search sources available" |
| API key missing for selected source | Warn, offer alternative sources. Fallback to next available source |
| All sources return zero results | Report "no results found", suggest query refinement. HANDOFF `status: no-data` |
| `build_literature_note()` exception | Log error, skip that paper, continue with remaining. Include in HANDOFF summary |
| `_index.md` write failure | Warn user, continue. Literature note is the primary artifact |
| Network timeout on search | Retry once. If still fails: try fallback source. Report which source failed |

## Critical Constraints

- **Never write outside `_research/literature/`.** Literature notes belong in their designated directory.
- **Always include DOI or arXiv ID** in frontmatter when available. This is the deduplication key.
- **Always honor `processing.chaining` mode** for pipeline integration.
- **Never call plt.show()** or display interactive plots.
- **Always use `obsidian_client`** for vault writes when REST API is available; fall back to direct file writes otherwise.
- **Present results to user before saving** (unless `--handoff` mode).

## CO-SCIENTIST HANDOFF

When `--handoff` is present in `$ARGUMENTS`, emit after all work:

```
CO-SCIENTIST HANDOFF
skill: literature
goal: [[{goal-slug}]]
date: {YYYY-MM-DD}
status: {complete | partial | failed | no-data}
summary: {one sentence, e.g., "saved 3 literature notes from PubMed/arXiv search"}

outputs:
  - _research/literature/{note1}.md -- {short title}
  - _research/literature/{note2}.md -- {short title}

quality_gate_results:
  - gate: source-readiness -- {pass | fail: reason}
  - gate: doi-deduplication -- {pass | fail: N duplicates skipped}
  - gate: note-files-exist -- {pass | fail: reason}
  - gate: index-consistency -- {pass | fail: reason}

recommendations:
  next_suggested: ralph -- "process queued literature notes with /ralph (runs /reduce then reflect/reweave/verify, fresh context per phase)"

learnings:
  - {observation about search results or source quality} | NONE
```

## Skill Graph

Invoked by: /research, user (standalone)
Invokes: /reduce (suggested chaining)
Reads: ops/config.yaml, external APIs (PubMed, arXiv, Semantic Scholar, OpenAlex)
Writes: _research/literature/, _research/literature/_index.md, ops/queue/queue.json (chaining entries)
