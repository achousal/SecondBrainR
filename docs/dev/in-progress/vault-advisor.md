---
description: "Master feature doc for vault_advisor.py -- goal frontier, pipeline tips, session tips, and orient UX. Centralizes all content-value ranking and session stigmergy."
type: development
status: active
created: 2026-03-03
updated: 2026-03-05
---

# Vault Advisor

Master feature doc covering `vault_advisor.py`, its channels, and the session orient UX that surfaces advisor output to the user.

---

## Motivation

The decision engine (`decision_engine.py`) answers "what action class?" (e.g., run `/literature`). It never says *what* to search for. The vault advisor centralizes "what content is most valuable to work on next?" into one testable module that any skill can call.

| Problem | Impact |
|---------|--------|
| `/literature` has ad-hoc goal-reading logic | Duplicated logic, fragile, untestable |
| `/next` surfaces no content-specific suggestions | User gets "do /literature" but not "search for p-tau217 confounders" |
| No centralized "what is most valuable?" module | Every skill reinvents goal parsing |
| Session orient mixed maintenance signals with tips | Redundant lines, action buried, rationale hidden |

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope Phase 1 to goal frontier only | Single channel | Gall's Law -- start simple, add channels at friction points |
| Structural gap detection (section presence) | Not semantic | Semantic depth detection deferred; structural is testable and sufficient |
| Priority formula: `(goal_rank * 10) + gap_weight` | Simple arithmetic | Legible, predictable ordering; resist premature sophistication |
| Caching via `ops/advisor-cache.json` | PID + date session key | Invalidates daily; atomic write prevents corruption |
| Graceful degradation in skill integration | Fallback to existing logic | Advisor failure must never block `/next` or `/literature` |
| Command-leading tip format | `/command -- description` | Scannable; user sees action before explanation |
| Single Next Action section in orient | Only highest-priority tip | One clear action > ranked list; reduces decision fatigue |
| Replace maintenance signals with tips | Delete all signal blocks | Tips cover every signal case; keeping both is redundant |

---

## Implementation Status

| Feature | Status | Files |
|---------|--------|-------|
| Goal frontier channel | Complete | `vault_advisor.py`, `test_vault_advisor.py` |
| Pipeline tip channel | Complete | `vault_advisor.py`, `test_vault_advisor.py` |
| Session tip channel | Complete | `vault_advisor.py`, `test_vault_advisor.py` |
| Session tips UX consolidation | Complete | `vault_advisor.py`, `session_orient.py`, both test files |
| `queue_blocked` tip | Complete | `vault_advisor.py`, `test_vault_advisor.py` |
| Command-leading tip format | Complete | `vault_advisor.py`, `test_vault_advisor.py` |
| `--format human` CLI flag | Complete | `vault_advisor.py` |
| Retrieval-demand upgrade guidance | Complete | `vault_advisor.py`, `test_vault_advisor.py`, `literature/SKILL.md` |
| Next Action section in orient | Complete | `session_orient.py`, `test_session_orient.py` |
| Maintenance signals removed | Complete | `session_orient.py`, `test_session_orient.py` |
| `/next` skill integration | Pending | `.claude/skills/next/SKILL.md` |
| `/literature` skill integration | Pending | `.claude/skills/literature/SKILL.md` |

---

## Channel 1: Goal Frontier (`goal_frontier`)

### Dataclasses

```python
@dataclass
class GoalProfile:
    goal_id: str            # filename stem
    title: str              # from frontmatter
    domain: str             # from frontmatter
    status: str             # "active" | other
    objective: str          # Objective section body
    has_background: bool
    has_key_literature: bool
    path: Path

@dataclass
class Suggestion:
    channel: str       # "goal_frontier" | "pipeline_tip" | "session_tip"
    query: str         # concrete search/generate query
    rationale: str     # one sentence why
    priority: int      # lower = more urgent
    goal_ref: str      # goal_id or ""
    scope: str         # "full" | "methods_only"
```

### Public API

| Function | Purpose |
|----------|---------|
| `parse_goal_file(path) -> GoalProfile \| None` | Parse one goal .md |
| `scan_goal_frontier(vault_path, goals_priority) -> list[GoalProfile]` | Scan `_research/goals/`, active goals in priority order |
| `detect_gaps(profile) -> list[str]` | Gap labels: `missing_key_literature`, `missing_background`, `thin_objective` |
| `generate_suggestions(profiles, context, max) -> list[Suggestion]` | Rank gaps across goals, format for context |
| `advise(vault_path, ...) -> (list[Suggestion], bool)` | Top-level: scan + gaps + suggestions, with caching |

### Gap priority formula

`priority = (goal_rank * 10) + gap_weight` where gap_weight: `missing_key_literature=1`, `missing_background=2`, `thin_objective=3`.

### Context formatting

| Context | Query style |
|---------|-------------|
| `literature` / `learn` | Search query from objective + domain |
| `generate` | Hypothesis prompt from objective |
| `reflect` | Reflection question |
| `reweave` | Linking prompt |
| `reduce` | Processing directive |

---

## Channel 2: Pipeline Tips (`pipeline_tip`)

Scans per-claim task files in `ops/queue/` to detect phase-ordering opportunities across sources.

### API

| Function | Purpose |
|----------|---------|
| `scan_queue_phases(vault_path) -> QueuePhaseState` | Aggregate phase state from task files |
| `detect_pipeline_tips(phase_state) -> list[PipelineTip]` | Detect phase-ordering opportunities |
| `generate_pipeline_suggestions(tips, max) -> list[Suggestion]` | Convert to Suggestion objects |

### Tip conditions

| Tip ID | Condition | Priority |
|--------|-----------|----------|
| `reduce_before_reflect` | 2+ sources reflect-pending AND any source create-pending | 0 |
| `batch_reflect_ready` | 2+ sources reflect-pending AND none create-pending | 1 |
| `reweave_after_reflect` | reflect-pending AND reweave-pending coexist | 2 |

Integration: `advise(include_pipeline_tips=True)` or CLI `--include-pipeline-tips`. Auto-enabled for `--context ralph`.

---

## Channel 3: Session Tips (`session_tip`)

Evaluates vault state snapshot to surface maintenance-level actionable tips.

### API

| Function | Purpose |
|----------|---------|
| `_find_high_demand_abstract_sources(vault_path, threshold=3) -> list[tuple[str, int]]` | Scan `_research/literature/` for abstract-only notes cited by 3+ claims in `notes/` |
| `build_vault_snapshot(vault_path) -> VaultSnapshot` | Count md files, queue blocked, recent reduce, high-demand abstract sources |
| `detect_session_tips(snapshot) -> list[SessionTip]` | Evaluate 9 conditions, return sorted tips |
| `generate_session_suggestions(tips, max) -> list[Suggestion]` | Convert to Suggestion objects |

### VaultSnapshot fields

```python
@dataclass
class VaultSnapshot:
    claim_count: int = 0
    inbox_count: int = 0
    observation_count: int = 0
    tension_count: int = 0
    queue_pending: int = 0
    hypothesis_count: int = 0
    has_recent_reduce: bool = False
    queue_blocked_count: int = 0
    abstract_only_source_count: int = 0
    high_demand_abstract_sources: list[tuple[str, int]] = field(default_factory=list)
```

### Tip conditions

| Tip ID | Condition | Priority | Message format |
|--------|-----------|----------|----------------|
| `reduce_inbox` | inbox > 0 AND no recent reduce | 0 | `/reduce -- N inbox items waiting` |
| `full_text_upgrade_demand` | high_demand_abstract_sources non-empty | 1 | `High-demand abstract-only sources need full text: [[stem]] (N claims), ...` |
| `abstract_accumulation_warning` | abstract_only_source_count >= 5 AND no recent reduce | 1 | `N abstract-only sources accumulating without processing...` |
| `unblock_queue` | queue_pending > 0 | 1 | `/ralph -- N queue tasks pending` |
| `queue_blocked` | queue_blocked_count > 0 | 1 | `/literature -- N blocked queue task(s) need stub content before /ralph` |
| `generate_hypotheses` | claims >= 20 AND hypotheses == 0 | 1 | `/generate -- N claims accumulated, no hypotheses yet` |
| `full_text_upgrade` | abstract_only_source_count > 0 | 2 | `N abstract-only source(s) in inbox...` |
| `rethink_observations` | observations >= 10 | 2 | `/rethink -- N observations pending` |
| `rethink_tensions` | tensions >= 5 | 2 | `/rethink -- N tensions pending` |

Most messages are command-leading: `/command -- description`. Awareness tips (`full_text_upgrade_demand`, `abstract_accumulation_warning`, `full_text_upgrade`) start with a descriptive count or label. Every `SessionTip` includes a `rationale` field.

### Retrieval-demand upgrade guidance

The `full_text_upgrade_demand` tip detects when abstract-only literature sources become load-bearing -- heavily cited by claims in `notes/`. The mechanism:

1. `_find_high_demand_abstract_sources()` scans `_research/literature/` for `content_depth: abstract` notes.
2. For each, counts how many `notes/` claims cite it via `source: "[[stem]]"` frontmatter.
3. Sources with 3+ citations are returned sorted descending.
4. The tip names the top 3 sources with cite counts.

The `abstract_accumulation_warning` tip fires when 5+ abstract-only sources accumulate without recent reduce activity, signaling a methods-and-evidence debt.

The generic `full_text_upgrade` tip (priority 2) remains as a lower-urgency reminder for any abstract-only sources.

---

## Session Orient UX

### Before (maintenance signals + buried tip)

```
### Vault State
  Claims: 201 | Inbox: 19 | Observations: 3 | Tensions: 1 | Queue: 165 pending
  -> Inbox has unprocessed items
  -> 10+ observations pending -- consider running /rethink
  Tip: 165 queue tasks pending -- run /ralph to process them
```

### After (Next Action section)

```
### Vault State
  Claims: 201 | Inbox: 19 | Observations: 3 | Tensions: 1 | Queue: 165 pending

### Next Action
  /ralph -- 165 queue tasks pending
  (Pending queue tasks block downstream phases. Processing them unblocks reflect and reweave.)
```

### Changes to `session_orient.py`

| Change | Description |
|--------|-------------|
| Deleted 4 maintenance signal blocks | `-> Inbox has...`, `-> 10+ observations...`, `-> 5+ tensions...`, `-> N blocked...` |
| `_session_tip()` replaced by `_build_next_action_section()` | Returns `list[str]` with header, message, rationale, or `[]` if no tips |
| `main()` call site | `parts.extend(_build_next_action_section(vault))` after Vault State section |
| Empty vault guard preserved | `/onboard` signal is a bootstrap guard, not a tip |

### Design rationale

- **One action**: research on attention management says one clear action beats a wall of text.
- **Command-leading**: user scans for the `/command` first, reads description second.
- **Rationale visible**: builds trust and learning; user understands *why* not just *what*.
- **Never crashes**: `_build_next_action_section` catches all exceptions; orient must never fail.

---

## CLI

```bash
# Standard advisor output (JSON)
python -m engram_r.vault_advisor VAULT_PATH --context literature --max 4 [--no-cache]

# All session tips (JSON)
python -m engram_r.vault_advisor VAULT_PATH --all-tips --no-cache

# All session tips (human-readable)
python -m engram_r.vault_advisor VAULT_PATH --all-tips --no-cache --format human

# With pipeline tips
python -m engram_r.vault_advisor VAULT_PATH --context ralph --no-cache
```

Output JSON: `{"context": "...", "suggestions": [...], "cached": bool}`
Exit codes: 0 = suggestions, 2 = no gaps/tips, 1 = error

---

## Test Coverage

### `test_vault_advisor.py`

| Test Class | Key Tests |
|------------|-----------|
| `TestParseGoalFile` | Title/domain extraction, empty/populated sections, malformed files |
| `TestDetectGaps` | All 3 gaps, 0 gaps, partial gaps |
| `TestScanGoalFrontier` | Priority order, only active goals, empty/missing dirs |
| `TestGenerateSuggestions` | Primary ranks higher, max respected, zero gaps = empty |
| `TestContextFormatting` | Parametric over 6 contexts |
| `TestCaching` | Cache hit/miss, context change, atomic write, `--no-cache` |
| `TestCLI` | JSON structure, exit codes, flags |
| `TestScanQueuePhases` | Empty queue, mixed phases, enrichment tasks |
| `TestDetectPipelineTips` | All 3 tip conditions, no-tip cases |
| `TestPipelineTipsIntegration` | `advise()` with flag, CLI ralph context |
| `TestScanExtractScopes` | Scope field parsing, defaults, invalid |
| `TestBuildVaultSnapshot` | Correct counts, missing dirs, recent reduce, abstract-only, high-demand sources |
| `TestDetectSessionTips` | All 9 tip conditions, healthy vault, priority sort, message format |
| `TestSessionTipsIntegration` | `advise()` with flag, CLI `--all-tips` |
| `TestHighDemandAbstractSources` | No lit dir, no abstracts, below/at threshold, sorted, full-text excluded, index skipped, no notes dir |
| `TestHighDemandSessionTips` | Demand tip fires/suppressed, priority vs generic, message content, top-3 limit, accumulation warning fires/suppressed/below threshold/format |
| `TestHighDemandSnapshotIntegration` | `build_vault_snapshot` populates high-demand sources |

### `test_session_orient.py`

| Test | Covers |
|------|--------|
| `test_main_includes_vault_state` | Vault State counts present, old signals absent, Next Action present |
| `test_session_tip_appears_when_triggered` | Next Action with `/reduce` + rationale |
| `test_no_tip_when_nothing_triggers` | No Next Action section on healthy vault |
| `test_session_tip_import_failure_does_not_crash` | Broken import returns `[]`, orient still works |
| `test_no_maintenance_signal_strings` | Old `-> ...` strings never appear |

---

## Verification

```bash
# Unit tests
cd _code && uv run pytest tests/test_vault_advisor.py tests/test_session_orient.py -v

# CLI smoke test: JSON
cd _code && uv run python -m engram_r.vault_advisor ../. --all-tips --no-cache

# CLI smoke test: human
cd _code && uv run python -m engram_r.vault_advisor ../. --all-tips --no-cache --format human

# Session orient live
cd _code && uv run python scripts/hooks/session_orient.py
```

---

## Research Grounding

- **Gall's Law** -- Phase 1 scope is one channel. Additional channels activate when friction demands.
- **Throughput over accumulation** -- routes effort toward highest-value gaps.
- **Friction-driven adoption** -- addresses documented friction, not speculative needs.
- **Condition-based triggers** -- evaluates vault state, not time-based schedules.
- **Processing effort follows retrieval demand** -- high-priority goal gaps surface first.
- **Attention management** -- one clear action with rationale beats a wall of signals.
- **Retrieval-demand stigmergy** -- citation count from claims to literature sources is a usage signal that identifies which abstract-only sources have become load-bearing and need full-text upgrade.

---

## Development Opportunities

### Near-term (low effort)

| Opportunity | Value | Notes |
|-------------|-------|-------|
| Multi-tip Next Action | Medium | Show top 2-3 tips instead of just highest-priority; useful when inbox + queue + observations all need attention |
| Tip deduplication | Low | `unblock_queue` and `queue_blocked` can co-fire; suppress `unblock_queue` when `queue_blocked` is active |
| `--format human` for main output | Low | Extend human formatting beyond `--all-tips` to the main `advise()` output path |
| `/next` skill integration | High | `/next` consumes advisor suggestions in Step 2 when engine recommends `/literature` or `/generate` |
| `/literature` skill integration | High | Replace manual goal-reading block with advisor call; fallback on failure |

### Medium-term

| Opportunity | Value | Notes |
|-------------|-------|-------|
| Tip history tracking | Medium | Log which tips fired per session in `ops/sessions/`; detect recurring tips user never acts on |
| Tip suppression rules | Medium | If user ran `/reduce` in last 2 hours, suppress `reduce_inbox` even if inbox non-empty |
| Conditional tip escalation | High | Same tip fires 5+ sessions without action -- escalate priority or add impact estimate |
| Unified tip system | Medium | Merge `PipelineTip` and `SessionTip` into one type; currently two parallel systems |
| `claim_coverage` channel | Medium | Detect goals with < N supporting claims after 20+ claims exist |
| `stale_frontier` channel | Medium | Flag goals whose newest claim is > 30 days old |

### Long-term

| Opportunity | Value | Notes |
|-------------|-------|-------|
| `topic_gap` channel | Medium | MOCs with unbalanced sub-areas after 3+ topic maps with 10+ entries |
| `hypothesis_opportunity` channel | Medium | Goals with literature but no hypotheses after first /generate cycle |
| `contradiction_surface` channel | Medium | Unresolved contradictions near goals |
| Graph-aware suggestions (Phase 3) | High | Use wiki-link topology: cluster analysis, bridge detection, dangling link signals |
| Co-scientist integration (Phase 4) | High | Advisor becomes strategic attention allocator for `/research`, `/generate`, `/tournament` |
| Metabolic-aware tips | Medium | Suppress low-priority tips when metabolic indicators show vault is healthy |
| Tip-driven `/next` | High | `/next` uses the full tip list as its primary signal source instead of separate condition logic |

### Development guardrails

Track the ratio of system modification to content creation. Phase 2+ channels should only be built after the vault has sufficient content to exercise them. Building claim coverage detection before claims exist is speculative complexity.

The discriminator: infrastructure that directly enables throughput is justified. Infrastructure that reorganizes complexity without increasing output is productivity porn.

---

## Known Limitations

- Only the single highest-priority tip is shown in orient output. Multiple urgent conditions surface only the top one.
- `_build_next_action_section` catches all exceptions silently. Broken `vault_advisor` produces no Next Action section with no error. Intentional -- orient must never crash.
- `queue_blocked_count` requires importing `daemon_scheduler._count_queue_blocked`, creating a dependency. Import is wrapped in try/except to preserve independence.
- `--format human` only applies to `--all-tips` mode.
- Stub detection for `queue_blocked` is heuristic (checks `## Key Points` and `## Relevance` emptiness). A single word in either section passes. Intentional -- catches completely empty stubs, not partial notes.
