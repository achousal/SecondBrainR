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
- If no query and no `--setup` -> ask user for search query

**Execute these steps:**

1. Load literature config from `ops/config.yaml` via `resolve_literature_sources()`.
2. Run preflight readiness check. If not ready: enter setup flow.
3. Present available sources to user: sources from config plus **all**. Default is `literature.default`.
4. Ask for search query (if not provided in arguments) and source selection.
5. Execute search via `search_all_sources()` with appropriate parameters.
6. Display results table: #, Title, Authors, Year, Source, Journal, DOI/ID, Citations.
7. Ask user which papers to save as literature notes.
8. For each selected paper: build note via `build_literature_note()`, save to `_research/literature/`.
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

- `_code/src/engram_r/search_interface.py` -- unified search interface, `check_literature_readiness()`, `resolve_literature_sources()`, `search_all_sources()`
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
Present available sources plus **all** option. Default is `literature.default` from config. If query provided in arguments, skip prompt.

### Step 3: Execute Search
Always call `search_all_sources()` from `search_interface.py`:
- **Single source**: `search_all_sources(query, sources=[chosen_source], config_path="ops/config.yaml")`
- **All sources**: `search_all_sources(query, config_path="ops/config.yaml")`

Both paths deduplicate by DOI, apply enrichment if configured, sort by citation count descending.

### Step 4: Display Results
Table columns: **#**, **Title**, **Authors**, **Year**, **Source**, **Journal**, **DOI/ID**, **Citations**.
Source column shows backend name (PubMed, Semantic Scholar, etc.). Citations shows count or "--" when unavailable.

### Step 5: User Selection
Ask which papers to save as notes. Accept comma-separated numbers or "all".

### Step 6: Build Notes
For each selected paper:
1. Build literature note via `build_literature_note()`, passing `source_type=result.source_type`.
2. Save to `_research/literature/{year}-{first_author_last_name}-{slug}.md`.
3. If `project_tag` inherited from `--goal`: add to note tags.

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
| `manual` | Print `Next: /reduce [literature-note-path]` for each saved note |
| `suggested` (default) | Print `Next: /reduce [path]` AND create queue entry in `ops/queue/queue.json` |
| `automatic` | Print `Next: /reduce [path]` (automatic execution not yet implemented) |

**Queue entry format** (for `suggested` mode):
```json
{
  "id": "extract-{literature-note-basename}",
  "type": "extract",
  "status": "pending",
  "source": "_research/literature/{filename}.md",
  "created": "[ISO timestamp]",
  "current_phase": "reduce",
  "completed_phases": []
}
```

**Output after all notes saved:**
```
Pipeline chaining:
- _research/literature/{note1}.md -> Next: /reduce _research/literature/{note1}.md
- _research/literature/{note2}.md -> Next: /reduce _research/literature/{note2}.md
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
  next_suggested: reduce -- "process literature notes into claims via /reduce"

learnings:
  - {observation about search results or source quality} | NONE
```

## Skill Graph

Invoked by: /research, user (standalone)
Invokes: /reduce (suggested chaining)
Reads: ops/config.yaml, external APIs (PubMed, arXiv, Semantic Scholar, OpenAlex)
Writes: _research/literature/, _research/literature/_index.md, ops/queue/queue.json (chaining entries)
