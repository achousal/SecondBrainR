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
argument-hint: "[query] | --setup | --goal [slug] | --methods-only"
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
- If `$ARGUMENTS` contains `--methods-only` -> pass `scope="methods_only"` to `create_queue_entries()` in pipeline chaining step. Use for cross-domain papers where only methodology is relevant.
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
8. **Enrich selected papers** per Step 5.5 spec. Write the enrichments dict as JSON to `ops/queue/.literature_enrichments.json`. Pass `enrichments_path` to `create_notes_from_results()`.
9. Create notes via `create_notes_from_results()` passing the saved JSON path, selected indices, output_dir=`_research/literature/`, goal_tag if applicable, and `enrichments_path='ops/queue/.literature_enrichments.json'`. **NEVER manually construct abstract text or pass abstracts as arguments** -- the function reads full abstracts from the JSON file.
10. Update `_research/literature/_index.md` (create if missing).
11. Execute pipeline chaining per `processing.chaining` mode.
12. Present saved note paths. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

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

### When to Use /literature vs Full Text

- **Surveying a topic (breadth):** Use `/literature` to find relevant papers, save abstract-only notes, and build orientation claims fast.
- **Central paper to your argument (depth):** Drop the full-text PDF into `inbox/` and run `/seed then /ralph`. Methods, effect sizes, and evidence require full text.
- **Unsure:** Start with `/literature`. If a source accumulates 3+ citing claims, the system will flag it for full-text upgrade.

### Step 1: Source Resolution
Read `ops/config.yaml` `literature:` section via `resolve_literature_sources()`. Returns enabled source list and default.

### Step 2: Query and Source Selection

**Context-aware suggestions (when no query provided):**

Before prompting, call the vault advisor for goal-aware query suggestions:

1. Count existing literature notes: `ls _research/literature/*.md 2>/dev/null | grep -cv '_index' || echo 0`
2. Run the advisor:
```bash
VAULT_PATH="$(pwd)"
ADVISOR=$(cd _code && uv run python -m engram_r.vault_advisor "$VAULT_PATH" \
    --context literature --max 4 2>/dev/null)
ADVISOR_EXIT=$?
```

**Condition for showing suggestions:** Only show goal-based search suggestions when the total literature note count (step 1) is below 5. If >= 5 literature notes already exist, the vault has literature -- even if individual goal files have empty `Key Literature` sections. Empty `Key Literature` sections with existing literature is a wiring gap (fix with linking), not a search gap.

**If total literature count < 5 AND advisor returned suggestions** (`$ADVISOR_EXIT` is 0):
- Parse the JSON `suggestions` array from `$ADVISOR`
- Present as a numbered menu with goal context:

```
Your active goals need literature grounding:

  1. goal-slug: "query" -- rationale
  2. goal-slug: "query" -- rationale
  ...

Select numbers (comma-separated), type your own query, or "all" to run all suggestions.
```

- If `--goal [slug]` was provided, filter suggestions to only that goal_ref
- Each suggestion targets a distinct gap in a goal (key literature, background, objective depth)

**Advisor fallback:** If the advisor CLI fails (`$ADVISOR_EXIT` != 0 or Python unavailable), fall back to manual goal reading: read `self/goals.md` for active goals, read `_research/goals/{slug}.md` for each, derive 1-2 queries per goal from the Objective and domain.

**Otherwise (>= 5 lit notes or no goals):** fall back to standard prompt: "What is your search query?"

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
Always render results as an ASCII box-drawing table. Use Unicode box characters (e.g., `+-|` or `┌┬┐├┼┤└┴┘│─`).

Columns: **#**, **Title**, **Year**, **Source**, **DOI**, **Cites**, **Abstract** (yes/MISSING).
Source column shows backend name (PubMed, Semantic Scholar, etc.). Cites shows count or "--" when unavailable. Abstract column shows "yes" or "MISSING" to flag gaps. Wrap long titles within the cell rather than truncating.

### Step 5: User Selection
Ask which papers to save as notes. Accept comma-separated numbers or "all".

### Step 5.5: Enrich Selected Papers

For each selected paper, generate enrichment content before note creation:

1. **Key Points**: Read the abstract (from the saved JSON or search results). Extract 3-5 key factual findings as concise bullet strings (no leading `- ` -- the renderer adds it).
2. **Relevance**: Read active goals from `self/goals.md`. Write 2-4 sentences connecting the paper to active goals using wiki-links (e.g. `[[biomarker-validation]]`). If `--goal` was provided, prioritize that goal. If no goals match, write a generic scientific contribution statement.
3. Build a Python dict: `enrichments = {1: {"key_points": ["...", "..."], "relevance": "..."}, 2: {...}}` (1-based indices matching selected papers).

### Step 6: Build Notes via Python (preserves full abstracts)
Call `create_notes_from_results()` to build and write notes entirely in Python. Enrichments are loaded from a file -- no shell-escaping needed:

```python
set -a && source _code/.env 2>/dev/null && set +a && uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import create_notes_from_results
created = create_notes_from_results(
    results_json='../ops/queue/.literature_results.json',
    indices=[{comma_separated_indices}],
    output_dir='../_research/literature/',
    goal_tag='{goal_tag_or_empty}',
    enrichments_path='../ops/queue/.literature_enrichments.json',
)
print(json.dumps(created, indent=2))
"
```

**NEVER manually call `build_literature_note()` with abstract text from agent context.** The `create_notes_from_results()` function reads the full abstract from the JSON file, builds the note, handles filename generation, checks for DOI duplicates, and warns on empty/short abstracts (with automatic PubMed fallback for empty abstracts).

The function returns a list of dicts with keys: `index`, `path`, `title`, `doi`, `status` (created/skipped/error), `abstract_status` (full/short/empty/pubmed_fallback), `enriched` (bool).

### Step 7: Update Index
Update `_research/literature/_index.md` under "Recent Additions" with wiki-link to new note.

**If `_index.md` does not exist**, create it with:
- Frontmatter: `description: "Index of structured literature notes"`, `type: moc`, `created: {today}`
- Heading: `# Literature Index`
- Sections: `## Recent Additions`, `## By Topic`

## Note Structure

Each literature note has YAML frontmatter with: type, title, description, doi, authors, year, journal, tags, status (unread/reading/read/cited), created date.

Sections: Abstract, Key Points, Methods Notes, Relevance, Citations.

If PubMed returns structured abstracts (labeled sections), preserve the structure.

## Pipeline Chaining

After saving literature notes and updating `_index.md`, chain to the arscontexta pipeline so literature content feeds into the knowledge graph.

**For each saved literature note**, based on `processing.chaining` mode:

| Mode | Action |
|------|--------|
| `manual` | Print `Next: /ralph` to process queued literature notes (each starts with /reduce, then reflect/reweave/verify) |
| `suggested` (default) | Create queue entries via `create_queue_entries()`, then print `Next: /ralph` (or `/ralph N` for N notes). Each task starts at the reduce phase |
| `automatic` | Create queue entries via `create_queue_entries()`, then invoke `/ralph N` via Skill tool to process all queued notes. After ralph completes, invoke `/archive-batch {batch}` for each batch. See **Automatic Chaining Implementation** below |

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
    scope='{methods_only if --methods-only flag set, otherwise full}',
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
    enrichments_path='../ops/queue/.literature_enrichments.json',
)
entries = create_queue_entries(
    created_notes=created,
    queue_path='../ops/queue/queue.json',
    vault_root='..',
    scope='{methods_only if --methods-only flag set, otherwise full}',
)
print(json.dumps({'notes': created, 'queue_entries': entries}, indent=2))
"
```

**Output after all notes saved (manual/suggested modes):**

Count how many queued notes are at abstract scope (have `content_depth: abstract` in frontmatter). Include scope framing:

```
Pipeline chaining:
- Queued: _research/literature/{note1}.md (reduce)
- Queued: _research/literature/{note2}.md (reduce)
{If abstract_count > 0:}
  {abstract_count} note(s) queued at abstract scope -- orientation claims only.
  For methods, effect sizes, and evidence: drop full-text PDF in inbox/ and run /seed then /ralph.
  /reduce will show upgrade path after processing.

Next: /ralph {N}  -- process all queued literature notes (reduce -> reflect -> reweave -> verify, fresh context per phase)
  Or: /reduce _research/literature/{note}.md  -- process a single note manually
```

### Automatic Chaining Implementation

When `processing.chaining` is `automatic`, after `create_queue_entries()` completes:

1. Extract unique batch values from the created queue entries.
2. For each batch, run extraction then full processing:
   ```
   Skill("ralph", "1 --batch {batch} --type extract")
   ```
   After extract completes, count claim tasks for the batch, then:
   ```
   Skill("ralph", "{N} --batch {batch}")
   ```
3. After all ralph invocations complete, archive each batch:
   ```
   Skill("archive-batch", "{batch}")
   ```
4. If the Skill tool fails for any invocation, fall back to reading `.claude/skills/ralph/SKILL.md` directly and following the instructions inline (existing ralph fallback pattern).

**Output (automatic mode):**
```
Pipeline chaining (automatic):
- Processing: _research/literature/{note1}.md (reduce -> reflect -> reweave -> verify)
- Processing: _research/literature/{note2}.md (reduce -> reflect -> reweave -> verify)

[ralph output for each batch]

Archived: {batch1}, {batch2}
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
