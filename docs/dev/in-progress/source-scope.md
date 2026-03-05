# Source-Level Scope for Methods-Only Extraction

## Status: Implemented (v1)

## Problem

Cross-domain papers (e.g., proteomics validation in dermal sarcoma) are methodologically
relevant to research goals but not disease-specific. Full extraction produces off-domain
claims that pollute the knowledge graph.

## Solution

A `scope` field flows through the file-based communication bus:

```
/seed --methods-only  or  /literature --methods-only
  -> extract task file:  scope: "methods_only"
  -> queue.json entry:   scope: "methods_only"
  -> /reduce reads scope, restricts to methodology categories
```

### Closed Enum

| Value | Behavior |
|-------|----------|
| `full` | Default. All extraction categories active. |
| `methods_only` | Only methodology-comparisons + design-patterns extracted. |

## Files Changed

### Python (`_code/src/engram_r/`)

- **vault_advisor.py**: `Suggestion.scope` field (default "full"), serialized in
  `save_cache()` and CLI output. New `scan_extract_scopes()` function reads
  `ops/queue/*.md` extract tasks and returns `{task_id: scope}` dict.
- **search_interface.py**: `create_queue_entries()` accepts `scope` parameter,
  writes it into each queue entry.

### Skills (`.claude/skills/`)

- **seed/SKILL.md**: `--methods-only` flag, scope in task file frontmatter + queue entry.
- **literature/SKILL.md**: `--methods-only` flag, passed to `create_queue_entries()`.
- **reduce/SKILL.md**: Reads scope from extract task file. When `methods_only`,
  restricts extraction to methodology categories. Scope-filtered candidates excluded
  from skip-rate denominator.

### Tests (`_code/tests/`)

- **test_vault_advisor.py**: `TestScanExtractScopes` (7 tests), `TestSuggestionScope` (4 tests).
- **test_search_interface.py**: `TestCreateQueueEntriesScope` (2 tests).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Closed enum | `full \| methods_only` | Queryable, enforceable, validated |
| Scope on task file | Task file is source of truth | Stigmergy: file IS the communication |
| Explicit flag (not auto-classify) | User-driven in v1 | Auto-classification deferred |
| Scope-filtered != skipped | Separate accounting | Prevents false skip-rate violations |
| Default "full" | Backward compat | Old files work unchanged |

## Known Extension Points

- **reduce logic is a binary branch**: The current `/reduce` implementation branches on
  `scope == "methods_only"` vs everything else (treated as `full`). Adding new scope
  values (e.g., `statistics_only`, `data_only`) requires converting this to a dispatch
  table or match statement that maps each scope value to its allowed extraction categories.
  The `scope: str` field already supports arbitrary values -- the constraint is in the
  reduce skill's branching logic, not the data model.

## Future Work

- Auto-classification: infer scope from source content keywords
- Additional scope values (e.g., `statistics_only`, `results_only`, `data_only`)
- Vault advisor integration: surface scope in suggestions
