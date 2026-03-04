# Plan: Fix All 6 Skill and Documentation Gaps

## Context

The cleanup tracker (`docs/development/cleanup-tracker.md`) has 6 open items under "Skill and Documentation Gaps." Item 1 is blocking 35 queue tasks. Items 2-5 are small doc/path fixes. Item 6 adds missing test coverage.

---

## Execution Order

```
Step 1: Item 1 -- create /enrich skill (unblocks 35 stuck tasks)
Step 2: Items 2-5 in parallel (independent doc/path fixes)
Step 3: Item 6 -- tests for maintenance scripts
Step 4: Run tests, update cleanup tracker
```

---

## Item 1: Create `/enrich` skill

**Create:** `.claude/skills/enrich/SKILL.md`

**Structure** (mirrors `reweave/SKILL.md` pattern):
- YAML header: `name: enrich`, `user-invocable: false`, `allowed-tools: Read, Write, Edit, Grep, Glob`, `context: fork`
- Step 0: Read `ops/derivation-manifest.md` + `ops/config.yaml` (processing depth)
- EXECUTE NOW section with `$ARGUMENTS` parsing (`--handoff` flag detection)
- 8-step workflow:
  1. Read task file (enrichment schema: `target_note`, `addition`, `source_lines`, `source_task`)
  2. Locate target note in `notes/` via Glob
  3. Read source lines from archive
  4. Integrate addition into target note body (prose, not list append)
  5. Optionally update YAML (`confidence`, `source_class` -- never `verified_by`)
  6. Assess `post_enrich_action`: NONE | title-sharpen | split-recommended | merge-candidate
  7. Update task file `## Enrich` section
  8. Output RALPH HANDOFF block
- Quality gates: target must exist, no fabrication, note coherence, wiki-link safety, YAML safety
- Handoff format: `=== RALPH HANDOFF: enrich ===` ... `=== END HANDOFF ===`
- Pipeline chaining section

**Key invariant:** No new files created. One note modified, one task file updated.

---

## Item 2: Fix `/graph` script paths

**Modify:** `.claude/skills/graph/SKILL.md`

3 path corrections (replace_all where each appears):
- `ops/scripts/graph/link-density.sh` -> `ops/scripts/link-density.sh`
- `ops/scripts/graph/orphan-notes.sh` -> `ops/scripts/orphan-notes.sh`
- `ops/scripts/graph/dangling-links.sh` -> `ops/scripts/dangling-links.sh`

Leave 7 advanced script refs unchanged (inline fallback works).

---

## Item 3: Create `interaction-constraints.md` + fix refactor path

**Create:** `ops/methodology/interaction-constraints.md`
- Hard blocks (2 entries: atomic+2-tier+high-volume, dense-schema+manual+high-throughput)
- Soft warns (3 entries: dense-schema+convention, high-density+quick-depth, atomic+no-topic-maps)
- Cascade effects (4 entries: granularity->nav, schema->automation, depth->queue, density->reweave)

**Modify:** `.claude/skills/refactor/SKILL.md` line 157
- From: `${CLAUDE_PLUGIN_ROOT}/reference/interaction-constraints.md`
- To: `ops/methodology/interaction-constraints.md`

---

## Item 4: Update `docs/manual/skills.md`

**Modify:** `docs/manual/skills.md`

- Add "Plugin Skills (arscontexta)" subsection header before the stub entries
- Add `| Requires | arscontexta plugin |` row to tables for: /tutorial, /add-domain, /recommend, /upgrade, /ask, /setup, /reseed, /help, /health, /architect
- Fill empty Output descriptions for /tutorial, /add-domain, /recommend, /upgrade

---

## Item 5: Document `[ml]` optional extra in README

**Modify:** `_code/README.md`

Insert "Optional Extras" section after line 150 (Environment variables) with table:

| Extra | Install | Provides |
|-------|---------|----------|
| `[ml]` | `uv sync --extra ml` | scikit-learn -- enables `build_roc()` with raw arrays |
| `[dev]` | `uv sync --extra dev` | pytest, pytest-cov, ruff, black |
| `[bot]` | `uv sync --extra bot` | slack-bolt, anthropic -- Slack integration |

Also fix `populate_stubs.py` line 9 usage string: `scripts/populate_stubs.py` -> `scripts/maintenance/populate_stubs.py`

---

## Item 6: Tests for maintenance scripts

**Create:** `_code/tests/test_populate_stubs.py` (~100 lines)
- Import script via `importlib.util.spec_from_file_location`
- Test `_normalize()`: lowercase, NFC normalization
- Test `_extract_title_words()`: year-author skip, short stem fallback
- Test `_title_similarity()`: identical, disjoint, partial overlap, empty
- Test `resolve_actual_file()`: direct match, fuzzy match, no match (all via `tmp_path`)
- Test `update_abstract_section()`: replaces abstract, returns False if sections missing

**Create:** `_code/tests/test_fix_claim_structure.py` (~100 lines)
- Import script via `importlib.util.spec_from_file_location`
- Helper `_make_claim(notes_dir, name, fm, body)` for fixtures
- Test `strip_title_echo()`: removes heading, dry_run no-op, no-heading unchanged
- Test `fix_headers()`: replaces `## Source`, skips tension type
- Test `add_topics()`: adds footer, skips if present, skips moc type

---

## Verification

1. `cd _code && uv run pytest tests/ -v` -- all tests pass including new ones
2. `grep "ops/scripts/graph/link-density" .claude/skills/graph/SKILL.md` -- no results
3. `grep "CLAUDE_PLUGIN_ROOT" .claude/skills/refactor/SKILL.md` -- no results
4. `grep "arscontexta" docs/manual/skills.md` -- returns plugin section
5. `grep "\[ml\]" _code/README.md` -- returns extras table
6. Update cleanup tracker: check off all 6 items
