# Cleanup Tracker

Cruft audit initiated 2026-03-04. Findings from parallel scan of Python code, ops infrastructure, skills, and dependencies.

---

## Immediately Removable

Safe deletions with no downstream dependencies.

- [x] Remove `UNATTENDED_PROMPT` constant -- `_code/src/engram_r/daemon_scheduler.py:85-92`, never referenced
- [x] Remove unused `import yaml` -- `_code/scripts/hooks/validate_write.py:28`, masked by `noqa: F401`
- [x] Delete unused test fixtures -- `_code/tests/fixtures/inbox_stub.md`, `_code/tests/fixtures/enriched_stub.md`
- [x] Delete `.bak` skill files -- `.claude/skills/init/SKILL.md.bak`, `.claude/skills/onboard/SKILL.md.bak` (superseded v1.0)
- [x] Delete stale literature caches -- `ops/queue/.literature_results_q*.json`, `.literature_enrichments_q*.json`, `.keller2024_*.json` (10 files, superseded)
- [x] Delete session heartbeat files -- `ops/sessions/*.json` (123 files, 105-byte stubs; kept `current.json`)
- [x] Delete empty stderr log -- `ops/daemon/logs/scheduler-stderr.log` (0 bytes)
- [x] Delete advisor cache -- `ops/advisor-cache.json` (auto-regenerated each session)
- [x] Stop tracking runtime state -- `_code/ops/advisor-cache.json` (added to `_code/.gitignore`, `git rm --cached`)

## Quick Fixes

Small edits, no architectural impact.

- [x] Fix hardcoded path in `/profile` skill -- `.claude/skills/profile/SKILL.md` has `/Users/andreschousal/EngramR` in bash blocks; replaced with `$(pwd)`
- [x] Add `*.bak` to root `.gitignore`
- [x] Add `ops/advisor-cache.json` to `_code/.gitignore`

## Technical Debt -- Duplication

Consolidation tasks. Not urgent but reduce maintenance surface.

- [x] Extract `_FM_RE` regex + `_read_frontmatter` into shared module `engram_r/frontmatter.py` -- consolidated from 6 files (daemon_scheduler, vault_advisor, metabolic_indicators, schedule_runner, experiment_resolver, stub_enricher)
- [x] Extract `_default_vault_path` into `engram_r/frontmatter.py` -- consolidated from 3 files (daemon_scheduler, decision_engine, vault_advisor)
- [~] Remove local `SLACK_READONLY_SKILLS` from `daemon_scheduler.py:53` -- intentional duplication to avoid early import of slack_skill_router at module load time; left as-is
- [~] Collapse `build_inbox_entries` shim -- trivial one-liner wrapper; not worth the test churn; left as-is

## Skill and Documentation Gaps

Missing files or stale references in skill definitions and docs.

- [x] Create `/enrich` skill stub or remove enrich phase from `/ralph` -- `ralph/SKILL.md` dispatches to it but no skill exists; enrichment tasks get stuck
- [x] Fix `ops/scripts/graph/` paths -- `/graph` skill references `ops/scripts/graph/*.sh` but scripts live at `ops/scripts/`; 7 advanced scripts (find-triangles, find-bridges, etc.) do not exist anywhere
- [x] Create or inline `interaction-constraints.md` for `/refactor` -- references `${CLAUDE_PLUGIN_ROOT}/reference/interaction-constraints.md` which does not exist
- [x] Update `docs/manual/skills.md` meta-commands section -- 8 plugin skills (architect, reseed, setup, ask, tutorial, add-domain, recommend, upgrade) documented as if local
- [x] Document `[ml]` optional extra for ROC plots -- `_code/src/engram_r/plot_builders.py:454` lazy-imports scikit-learn; undocumented in `_code/README.md`
- [x] Add tests for maintenance scripts -- `_code/scripts/maintenance/populate_stubs.py` and `fix_claim_structure.py` have no test coverage

## Quarantine (deferred)

Recovery-gated items. Do not remove until re-extraction from real sources is complete.

- [ ] Delete 42 quarantined claim files + 1 literature note in `ops/quarantine/` after real abstracts are fetched and claims re-extracted
- [ ] Delete `ops/quarantine/MANIFEST.md` after recovery is confirmed

---

## Completed

All "Immediately Removable" and "Quick Fixes" items completed 2026-03-04.
Duplication debt resolved 2026-03-04: created `engram_r/frontmatter.py`, consolidated _FM_RE (6 files), _read_frontmatter (4 files), _default_vault_path (3 files). Tests: 1883 passed.
All "Skill and Documentation Gaps" items completed 2026-03-04. Plan archived to `docs/development/archive/`.
