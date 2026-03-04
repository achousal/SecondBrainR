---
status: archived
---

# Boundary Maturation Plan

Development log for the five-recommendation architectural plan addressing the vault's "epithelial immaturity" diagnosis. Originated 2026-02-26 from a four-sub-question investigation (session `053d4ad9`).

---

## Master Diagnosis

The vault's organs work -- the pipeline extracts claims, the health check finds breakage, the co-scientist generates hypotheses. What fails is the **membranes between them**: the boundaries where external content enters internal structures, where operational artifacts meet knowledge artifacts, and where one session's work meets the next.

A biologist would say: this is a 5-day-old organism in a growth sprint. Its biosynthetic output is remarkable (313 claims, 29 hypotheses, 2,476 cross-references, zero orphans, zero dangling links). But its barrier systems have not yet matured, and its metabolism is running hot.

The diagnosis emerged from four converging analyses:

| Sub-question | Biological Analog | Finding |
|---|---|---|
| Friction diagnosis | Membrane permeability failure | Three friction clusters (session capture, health scope, write safety) are one architectural gap: no systematic transformation boundary between external and internal representations |
| Enforcement architecture | Immune system asymmetry | Most critical rule (pipeline compliance) has zero enforcement; a less critical rule (slash-in-titles) has triple enforcement |
| Loading order | Procedural memory gap | 11 methodology notes (~6,500 tokens of hard-won behavioral corrections) are NOT auto-loaded; agent rediscovers them each session |
| Metabolic homeostasis | Anabolism-dominant growth | Creation:Maintenance ratio is 19.4:1 (healthy: 3-8:1); queue backlog is 91% the size of the knowledge graph |

---

## The Five Recommendations

### Summary Table

| # | Recommendation | Status | Addresses |
|---|---|---|---|
| 1 | Build the boundary layer | **COMPLETED** | Friction clusters 1-3 |
| 2 | Compile and auto-load methodology notes | **COMPLETED** | Procedural memory gap |
| 3 | Add pipeline compliance enforcement | **COMPLETED** | Highest-risk unenforced rule |
| 4 | Implement metabolic feedback in daemon | **COMPLETED** | Creation:Maintenance ratio |
| 5 | Consolidate dual hooks | **COMPLETED** | Redundant hook implementations |

---

## Recommendation #1: Build the Boundary Layer

**Goal:** Unify input sanitization into a single mandatory transformation point. Every write path, every health scan, every session record passes through this membrane.

**Status:** COMPLETED (2026-02-26)

### Plan

Create a canonical boundary layer in `schema_validator.py` that centralizes all input transformation:

1. Title sanitization: replace all CLAUDE.md-prohibited characters (`/ \ : * ? " < > | . + [ ] ( ) { } ^`) with hyphens, collapse consecutive hyphens, NFC-normalize
2. YAML safety detection: catch unquoted colons and hashes that silently misparse (pre-parse, before `yaml.safe_load()`)
3. Unicode normalization: NFC as single standard, enforced at the boundary
4. Filename validation: separate from title sanitization (filenames allow `.` for extensions)
5. Pipeline provenance: `check_notes_provenance()` for `notes/` files (description required, source warned)
6. Canonical claim constructor: `build_claim_note()` in `note_builder.py` that applies sanitization internally

### What Changed

**`_code/src/engram_r/schema_validator.py`** -- became the canonical boundary module:
- `normalize_text()` -- NFC normalization (single source of truth)
- `sanitize_title()` -- full CLAUDE.md title-rule enforcement
- `validate_filename()` -- filesystem-safe check on filename component
- `detect_yaml_safety_issues()` -- pre-parse colon/hash detection
- `detect_unicode_issues()` -- NFC check on frontmatter
- `check_notes_provenance()` -- description required, source warned for claim-family types

**`_code/src/engram_r/note_builder.py`** -- added `build_claim_note()`:
- Canonical constructor for claim notes from code paths (federation, tooling)
- Applies `sanitize_title()` and `normalize_text()` internally
- Returns `(safe_filename_stem, note_content_string)` tuple
- Generates full frontmatter with all epistemic provenance fields

**`_code/scripts/hooks/validate_write.py`** -- strengthened to call all boundary checks:
- Flat-directory violation check (catches `/` creating subdirectories)
- Filename unsafe character check
- YAML safety issue detection
- Unicode normalization check
- Schema validation
- Pipeline provenance check (when `pipeline_compliance: true` in config)

### Design Decisions

- **Permissive by default for unknown types.** Files without frontmatter or with unknown `type` fields pass silently. Only known schema types get field enforcement. Rationale: the vault has operational files that are not structured notes.
- **Block vs warn distinction.** Missing `description` in `notes/` is a blocking error. Missing `source` is a warning (only on Write, not Edit). Rationale: description is required for all claims; source is important but has legitimate exceptions (seed notes from conversation).
- **MOC types exempt from source warning.** Types `moc`, `index`, `hub`, `topic-map` never warn about missing `source`. Rationale: navigation hubs are structural, not evidential.
- **Title sanitization is aggressive.** Characters like `.`, `+`, `[`, `]`, `(`, `)`, `{`, `}`, `^` are all replaced with hyphens even though they are filesystem-safe. Rationale: CLAUDE.md title rules are stricter than filesystem rules to prevent Obsidian wiki-link breakage.

### Test Coverage

94 tests across `test_schema_validator.py` and `test_validate_write.py` covering:
- All 10 known schema types (hypothesis, literature, experiment, eda-report, research-goal, tournament-match, meta-review, project, lab, foreign-hypothesis)
- Missing field detection for each type
- Title sanitization for biology notation (`APP/PS1`, `AhR/NF-kappaB/NLRP3`, `DCA:CA`)
- Unsafe character detection in filenames
- YAML safety (unquoted colons, hashes, conventional commits)
- Unicode NFC normalization and detection
- Pipeline provenance (description required, source warnings, MOC exemptions)
- Hook integration tests (flat-dir violations, config toggles, tool_name-aware warnings)

863 tests total passing at 90% coverage at time of completion.

---

## Recommendation #2: Compile and Auto-Load Methodology Notes

**Goal:** Install the system's acquired procedural memory as reflexive session-start behavior instead of on-demand recall.

**Status:** COMPLETED (2026-02-26)

### Plan

1. Create `ops/methodology/_compiled.md` (~1,500 tokens) distilling all 11 methodology notes into actionable directives
2. Add it to session-start auto-loading (CLAUDE.md references it, session orient hook loads it)

### What Changed

**`ops/methodology/_compiled.md`** -- created. Three sections:
- **Mechanical Guards** (hook-enforced): slash-in-titles, Unicode normalization, YAML quoting, pipeline provenance. Listed for awareness since hooks enforce them automatically.
- **Behavioral Rules**: parallel workflow integrity, health report scoping, session mining via git history, symlinked repo bridges, daemon idle fallback, cross-repo experiment sync.
- **Experiment Conventions**: step-based naming, required artifacts, data provenance.

**Session start loading** -- the compiled file is referenced in CLAUDE.md under "Operational Space" and is auto-loaded by the session orient hook. The full text appears in the system prompt at every session start.

### Design Decisions

- **Compiled, not concatenated.** The 11 source notes total ~6,500 tokens. The compiled version is ~1,500 tokens. Each directive is distilled to its actionable essence. Rationale: context budget matters; verbose procedural memory crowds out working memory.
- **Source notes preserved.** The originals in `ops/methodology/` remain as the authoritative detailed versions. The compiled file says "Regenerate when source notes change significantly."
- **Hook-enforced vs behavioral distinction.** Mechanical guards (hooks block the action) are separated from behavioral rules (agent must remember). Rationale: for hook-enforced rules, the compiled note serves as awareness ("this is why it blocked you"); for behavioral rules, it serves as instruction.

### Source Notes (11 total)

| Filename | Topic |
|---|---|
| `slash-in-titles-creates-subdirectories.md` | `/` in titles creates accidental subdirs |
| `normalize-unicode-in-queue-ids-and-filenames.md` | NFC normalization requirement |
| `commit-message-strings-in-yaml-source-fields-require-quoting.md` | YAML quoting for colons |
| `parallel-workflow-integrity.md` | Reduce fans out, reflect fans in |
| `health-reports-are-diagnostic-artifacts-not-graph-nodes.md` | Health check scoping |
| `use-git-history-as-primary-session-mining-signal.md` | Git log as episodic memory |
| `symlinked-repos-require-wiki-link-bridges.md` | `_dev/` repo linking |
| `daemon-requires-consecutive-skip-idle-fallback.md` | Daemon tight-loop prevention |
| `experiment-output-conventions.md` | Step-based file naming, required artifacts |
| `derivation-rationale.md` | Why the vault is configured this way |
| `methodology.md` | Index note for the directory |

---

## Recommendation #3: Add Pipeline Compliance Enforcement

**Goal:** Mechanically enforce the highest-risk unenforced rule: "never write directly to `notes/`." All content must route through the pipeline.

**Status:** COMPLETED (2026-02-26, implemented as part of Recommendation #1)

### Plan

Add `check_notes_provenance()` to the boundary layer and wire it into the validate_write hook.

### What Changed

This was implemented within the Recommendation #1 boundary layer work:

- **`check_notes_provenance()`** in `schema_validator.py` enforces:
  - BLOCK: no frontmatter at all in a `notes/` file
  - BLOCK: `description` field missing or empty
  - WARN: `source` field missing for claim-family types (on Write only, not Edit)

- **`validate_write.py`** hook wiring:
  - Checks `pipeline_compliance` flag in `ops/config.yaml` (default: `true`)
  - Only runs provenance check on files whose relative path starts with `notes`
  - Source warnings emitted to stderr (non-blocking) only for `Write` tool, not `Edit`

- **`ops/config.yaml`** added:
  - `pipeline_compliance: true` -- toggle for the provenance check
  - Under `health:` section -- explicit graph/exclude directory lists

### Design Decisions

- **Merged into #1 rather than separate.** The provenance check is architecturally part of the boundary layer (it's a transformation boundary for `notes/` writes). Implementing it separately would have duplicated the hook integration work.
- **Warning-not-block for missing source.** The original plan proposed a flag-file provenance mechanism (transient marker left by the pipeline). This was deemed over-engineered. Instead: require `description` (block) and warn on missing `source` (advisory). Rationale: some legitimate code paths (seed, conversation capture) create notes without a full pipeline source chain.
- **Config-gated.** The `pipeline_compliance` flag allows disabling the check for debugging or migration. Default is `true`.

---

## Recommendation #4: Implement Metabolic Feedback in Daemon

**Goal:** Regulate the daemon's creation:maintenance ratio using quantitative health indicators. Queue Pressure Ratio > 3.0 halts generation. Meta-review conclusions feed back into daemon priority weights.

**Status:** COMPLETED (2026-02-27)

### Plan

All five metabolic indicators from the diagnosis, computed from vault filesystem state at daemon evaluation time. Indicators feed into the daemon's priority cascade via a "metabolic governor" that suppresses generative P1 tasks when alarm thresholds are breached.

### What Changed

**`_code/src/engram_r/metabolic_indicators.py`** -- new module, all 5 indicators:

| Indicator | Function | Source |
|---|---|---|
| QPR (Queue Pressure Ratio) | `compute_qpr()` | `ops/queue/queue.json` -- pending tasks / daily completion rate over lookback window |
| VDR (Verification Debt Ratio) | `compute_vdr()` | `notes/` frontmatter -- % of claims not `verified_by: human` |
| CMR (Creation:Maintenance Ratio) | `compute_cmr()` | `notes/` `created` dates + queue reflect/reweave completions |
| HCR (Hypothesis Conversion Rate) | `compute_hcr()` | `_research/hypotheses/` frontmatter -- % with status in {tested-positive, tested-negative, executing, sap-written} |
| SWR (Session Waste Ratio) | `compute_swr()` | `ops/sessions/` file count / (notes + hypotheses) artifact count |

- `MetabolicState` dataclass holds all 5 values plus `alarm_keys`
- `classify_alarms()` applies configurable thresholds to produce alarm keys
- `compute_metabolic_state()` is the public API -- computes all indicators from a vault path
- CLI entrypoint for `/stats` skill: `python -m engram_r.metabolic_indicators <vault>`

**`_code/src/engram_r/daemon_config.py`** -- added `MetabolicConfig` dataclass:
- `enabled` (default `True`), `lookback_days` (default 7)
- Threshold fields: `qpr_critical` (3.0), `cmr_hot` (10.0), `hcr_redirect` (15.0), `swr_archive` (5.0), `vdr_warn` (80.0)
- Loaded from `metabolic:` section in `ops/daemon-config.yaml`

**`_code/src/engram_r/daemon_scheduler.py`** -- metabolic governor integration:
- `VaultState` gains `metabolic` field (populated during `scan_vault_state()` when `config.metabolic.enabled`)
- `_check_p1()` (generative tasks: /generate, /evolve, /tournament) is suppressed when `qpr_critical` or `cmr_hot` alarms are active
- When P1 is suppressed, falls through to `_check_p1_experiments_only()` -- experiment resolution still fires even under metabolic alarm
- Dashboard line in `format_dashboard()` reports all 5 indicators and active alarms

**`_code/src/engram_r/decision_engine.py`** -- metabolic awareness:
- Generates metabolic-specific decisions when QPR, CMR, or HCR thresholds are breached
- Decisions include actionable recommendations (e.g., "QPR critical: halt generation, process queue")
- Summary output includes metabolic dashboard section

### Design Decisions

- **Vault filesystem, not git history.** Indicators computed from current vault state (file counts, frontmatter, queue.json) rather than git log analysis. Rationale: faster, simpler, and the vault's file-based conventions already encode the necessary temporal information (created dates, completion timestamps).
- **Config-driven thresholds.** All thresholds live in `daemon-config.yaml` under `metabolic:`, not hardcoded. Rationale: the operator can tune the governor without code changes.
- **VDR is informational only.** The verification debt ratio (currently ~95%) does not trigger alarms because human verification has not been practiced yet. It is reported in the dashboard but does not suppress any tasks. Rationale: alarming on a metric that cannot currently be actioned would create noise.
- **Metabolic governor suppresses P1, not all tasks.** P0 (critical health), P2 (maintenance), P3 (consolidation) all still fire. Only generative P1 tasks (/generate, /evolve, /tournament) are governed. Experiment resolution within P1 is explicitly exempt. Rationale: the governor's purpose is to rebalance creation vs consolidation, not halt all daemon activity.
- **All five indicators implemented.** The diagnosis asked "what is the minimum useful implementation?" -- the answer was "all five, since each is computationally trivial and tests the full metabolic model." No indicator was deferred.

### Test Coverage

Tests in `test_metabolic_indicators.py` and `test_daemon_scheduler.py`:

- **QPR**: recent completions, no completions (floor rate), all done, empty queue, disk read, old completions excluded
- **VDR**: all agent, mixed, all human, empty/missing dir, index skipped
- **CMR**: balanced, creation-dominant, maintenance-only
- **HCR**: low conversion, all converted statuses, empty/missing dir, non-hypothesis skipped
- **SWR**: normal ratio, high ratio, no sessions
- **Alarm classification**: multiple alarms, no alarms, QPR-only, custom thresholds, VDR not alarmed
- **Integration**: end-to-end with temp vault
- **Daemon scheduler**: metabolic governor suppresses P1, allows experiment resolution, CMR hot suppresses P1, disabled config bypass, None metabolic no effect
- **Decision engine**: metabolic dashboard with/without alarms, no dashboard when None
- **Config**: MetabolicConfig defaults, YAML override parsing

---

## Recommendation #5: Consolidate Dual Hooks

**Goal:** Each hook event (SessionStart, PostToolUse, Stop) gets one implementation (Python), not two competing scripts. Eliminate shell duplicates.

**Status:** COMPLETED (2026-02-27)

### What Changed

**Before:** 9 hook entries in `.claude/settings.json` -- 5 shell scripts + 4 Python scripts, with each event (SessionStart, PostToolUse, Stop) having competing implementations.

**After:** 4 Python-only entries:

| Event | Hook Script | Matcher |
|---|---|---|
| SessionStart | `session_orient.py` | -- |
| PostToolUse | `pipeline_bridge.py` | `Write` |
| PostToolUse | `validate_write.py` | `Write\|Edit` |
| PostToolUse | `auto_commit.py` | `Write\|Edit` |
| Stop | `session_capture.py` | -- |

**`_code/src/engram_r/hook_utils.py`** -- new shared module extracting duplicated logic:
- `find_vault_root()` -- marker walk-up with `PROJECT_DIR` env and git fallback
- `load_config()` -- `ops/config.yaml` loading with defaults
- `resolve_vault()` -- convenience wrapper returning both vault root and config

All four hook scripts import from `hook_utils` instead of duplicating vault discovery.

**Shell scripts deleted from disk:**
- `.claude/hooks/auto-commit.sh`
- `.claude/hooks/pipeline-bridge.sh`
- `.claude/hooks/session-capture.sh`
- `.claude/hooks/session-orient.sh`
- `.claude/hooks/validate-note.sh`

**Bug fix:** `.arscontexta` marker detection changed from `.is_dir()` to `.exists()` in:
- `hook_utils.py` (Python vault discovery)
- `session_orient.py` (vault validation)
- `ops/scripts/lib/vault-env.sh` (bash: `-d` to `-e`)

The marker is a file, not a directory. The original `.is_dir()` check silently failed, forcing fallback to git detection on every invocation.

**Shell-only logic absorbed into Python:**
- Truncated wiki-link detection (`[[some title...]]`) -- moved from `validate-note.sh` into `validate_write.py`
- Pipeline bridge queue injection -- new `pipeline_bridge.py` script (previously shell-only)

### Design Decisions

- **Python over shell.** Python hooks are more capable (YAML parsing, library imports, structured JSON output), more testable, and share code via `hook_utils`. Shell hooks had no test coverage.
- **Separate `pipeline_bridge.py` rather than merging into `validate_write.py`.** The bridge creates queue tasks on Write; the validator blocks invalid writes. Different responsibilities warrant different scripts despite both being PostToolUse hooks.
- **`--no-verify` preserved in `auto_commit.py`.** Auto-commit uses `git commit --no-verify` to avoid recursive hook invocation. This was inherited from the shell version and is intentional.

### Test Coverage

61 tests across 6 test files:
- `test_hook_utils.py` (10 tests) -- vault root discovery, marker detection, config loading, fallback paths
- `test_validate_write.py` (12 tests) -- schema validation, provenance, flat-dir, truncated links
- `test_auto_commit.py` (6 tests) -- tracked dir detection, gitignored skip, commit invocation
- `test_session_orient.py` (13 tests) -- orientation output, methodology loading, meta-review parsing
- `test_session_capture.py` (6 tests) -- session file creation, metadata capture
- `test_pipeline_bridge.py` (9 tests) -- queue injection, duplicate detection, matcher scope

990 tests total passing at 90% coverage at time of completion.

---

## Post-Completion Meta-Review (2026-02-27)

All five recommendations are COMPLETED. This section records the meta-review findings from examining the implementations together.

### Overall Assessment

The five fixes address the "epithelial immaturity" diagnosis effectively. The boundary layer exists, methodology auto-loads, pipeline compliance is enforced, metabolic feedback governs the daemon, and hooks are consolidated. 990 tests pass at 90% coverage. The architecture is sound.

But the pattern across all five fixes reveals a consistent class of residual issue: **partially-wired features and untested edge paths.**

### Cross-Cutting Patterns

**Pattern 1: Dead configuration / silent alarms (3 occurrences)**

| Fix | Dead Feature |
|---|---|
| #4 Metabolic | `swr_high` alarm computed but nothing acts on it |
| #4 Metabolic | `vdr_warn` config field exists but nothing reads it |
| #3 Pipeline | `source` field format not validated (wiki link vs raw string) |

Shape: a config/schema declares an intent, the computation runs, but the downstream wiring that makes it _do something_ was never connected.

**Pattern 2: Bypass paths not unified (2 occurrences)**

| Fix | Bypass |
|---|---|
| #1 Boundary | `claim_exchange.py` constructs notes manually, bypassing `build_claim_note` and `normalize_text` |
| #3 Pipeline | No transient flag for trusted pipeline callers; compliance is content-inspection only |

Fix #1's entire purpose was "single mandatory transformation point." The federation import path skips it.

**Pattern 3: Vacuous or weak test assertions (4 occurrences)**

| Fix | Test Issue |
|---|---|
| #3 Pipeline | `test_pipeline_compliance_false_skips_check` has conditional non-assertion |
| #5 Hooks | `test_relative_fallback` asserts `is_dir()` on any directory |
| #5 Hooks | `test_commits_file_in_tracked_dir` uses string-matching on call args |
| #2 Compiled | No test for `_load_methodology` |

Tests exist and pass, but some don't prove what they claim to prove.

**Pattern 4: Uncommitted work (1 occurrence)**

Fix #5's shell hook deletions and `vault-env.sh` changes are on disk but not staged/committed. Memory says "completed" but git state disagrees.

### Per-Fix Scorecard

| Fix | Delivered | Must-Fix | Should-Fix |
|---|---|---|---|
| #1 Boundary layer | Unified sanitization in `schema_validator` + `build_claim_note` + strengthened hook | 2 | 3 |
| #2 Compiled methodology | `_compiled.md` + `session_orient.py` loader | 2 | 3 |
| #3 Pipeline compliance | `check_notes_provenance` + config toggle | 2 | 3 |
| #4 Metabolic feedback | All 5 indicators + governor + dashboard | 2 | 3 |
| #5 Hook consolidation | 9 entries to 4 Python-only + `hook_utils.py` + marker fix | 2 | 3 |
| **Total** | | **10** | **15** |

### Priority Triage

**Tier 1 -- Fix now (correctness/integrity)**

1. `claim_exchange.py` bypasses `build_claim_note` (Fix #1) -- violates the boundary layer premise
2. Commit shell hook deletions + `vault-env.sh` (Fix #5) -- git state and memory disagree
3. Vacuous test in `test_pipeline_compliance_false` (Fix #3) -- provides no coverage guarantee

**Tier 2 -- Fix soon (completeness)**

4. `swr_high` alarm has no downstream effect (Fix #4)
5. `vdr_warn` config field is dead (Fix #4)
6. `_compiled.md` missing cross-repo sync checklist and parallelization table (Fix #2)
7. `_load_methodology` has no tests (Fix #2)
8. No section header for methodology block in orientation output (Fix #2)

**Tier 3 -- Fix when convenient (polish)**

9. Duplicated `_read_frontmatter` across `daemon_scheduler.py` and `metabolic_indicators.py`
10. CMR ctime fallback inflates creation counts for notes without `created` field
11. Dead `landscape` entry in `_FLAT_DIRS` set
12. `VaultState.metabolic` typed as `object | None` instead of `MetabolicState | None`
13. `auto_commit.py` `--no-verify` undocumented
14. `vault-env.sh` detection priority differs from `hook_utils.py`
15. Various weak test assertions (string-matching on call args, `is_dir()` on any directory)

### Verdict

The boundary maturation plan achieved its architectural goals. The vault now has membranes where it previously had none. The 10 must-fix items represent the difference between "built" and "sealed." The single most important action is wiring `claim_exchange.py` through `build_claim_note` -- without that, the boundary layer has a hole at the federation interface, which is exactly the external-content ingestion path the diagnosis identified as the root cause.

---

## Cross-Cutting Observations

### What Worked

- **Biological metaphor as diagnostic framework.** Mapping vault architecture to cellular biology (membranes, metabolism, immune system, proprioception) produced more actionable diagnoses than abstract "system design" language. The metaphor forced specificity about _what_ was failing and _why_.
- **Four-sub-question decomposition.** Breaking the diagnosis into friction/enforcement/loading/metabolism prevented tunnel vision on any single symptom.
- **Merging #1 and #3.** Pipeline compliance enforcement is architecturally part of the boundary layer. Implementing them together avoided duplicate hook wiring and produced a cleaner abstraction.
- **Sequential execution with focused context.** Each plan was developed and implemented in a dedicated session, preventing context contamination across fixes.
- **Test-first discipline.** Every fix shipped with dedicated tests. The test suite grew from ~863 to 990 tests across the five implementations.

### What Remains

- **10 must-fix items** from the meta-review (see Priority Triage above). Tier 1 items should be addressed before the next version bump.
- **The session capture chain** (diagnosed as "proprioceptive failure") is partially addressed by `_compiled.md` noting "use git history as primary session mining signal" but the root cause (Claude Code doesn't provide `transcript_path` to Stop hooks) remains an external limitation.

### Metabolic State at Diagnosis (2026-02-26 snapshot)

| Metric | Value | Assessment |
|---|---|---|
| Creation rate | 77.6 artifacts/day | Very high |
| Maintenance rate | 4.0 artifacts/day | Low |
| Creation:Maintenance ratio | 19.4:1 | Strongly anabolism-dominant |
| Queue backlog | 285 items (4.6 days of work) | 91% the size of the knowledge graph |
| Orphan rate | 0% | Perfect structural integrity |
| Link density | 7.9 links/claim | Richly connected |
| Verification debt | 95.5% agent-only | Zero human-verified claims |
| Hypothesis conversion | 10.3% (3/29 to SAP or tested) | Wide funnel, narrow bottom |
| Session waste | 583 stubs (1.5 per useful artifact) | Accumulating |
