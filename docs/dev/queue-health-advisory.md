---
description: "Detect and surface queue health -- blocked stubs, pending/blocked distinction -- advisory only, never blocks processing"
type: development
status: complete
created: 2026-03-03
updated: 2026-03-03
---

# Queue Health Advisory

## Motivation

31 reduce-phase tasks had unpopulated literature stubs. Three problems compounded:

| Problem | Impact |
|---------|--------|
| `_count_queue_pending()` calls `.get("tasks", [])` on a flat JSON list | `AttributeError` -- `queue_backlog` always 0 |
| Ralph silently skips blocked tasks | User sees "pending" but nothing processes |
| Decision engine and session orient don't distinguish blocked from pending | Misleading counts; no guidance to populate stubs first |
| Running reweave before populating stubs | Suboptimal connections -- reweave has less material to link |

Design constraint: **advisory only, never block**. The system surfaces blocked counts and recommends ordering but never prevents processing.

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stub detection method | Check `## Key Points` + `## Relevance` sections | These are the two required content sections in literature notes; both empty = stub |
| Blocked definition | `status == "blocked"` OR (pending + reduce phase + stub source) | Covers explicit blocks and implicit stub blocks |
| Signal speed | `multi_session` | Populating stubs via /literature is a multi-session task, not urgent |
| Recommended action | `/literature` | Stubs need content before /ralph can extract claims |
| Ralph behavior | Step 0 advisory, always continues | Never blocks processing; prints count + ordering suggestion |

---

## Changes

### `_code/src/engram_r/daemon_scheduler.py`

| Change | Lines | Description |
|--------|-------|-------------|
| Fix `_count_queue_pending` | ~324 | Handle flat-list format (was `.get("tasks", [])` on a list); exclude `"blocked"` status |
| `_is_literature_stub(text)` | new | Returns True if both `## Key Points` and `## Relevance` are empty |
| `_count_queue_blocked(queue_file)` | new | Counts explicitly blocked + pending reduce-phase tasks with stub sources |
| `VaultState.queue_blocked` | dataclass | New field, default 0 |
| `scan_vault()` | ~792 | Populates `state.queue_blocked` |
| `vault_summary_dict()` | ~1025 | Added `queue_blocked` key (8-key -> 9-key) |

### `_code/src/engram_r/decision_engine.py`

| Change | Lines | Description |
|--------|-------|-------------|
| `classify_signals()` | after ~246 | New `queue_blocked` signal (multi_session, action=/literature) |
| `_build_state_summary()` | ~580 | Added `queue_blocked` key |

### `_code/scripts/hooks/session_orient.py`

| Change | Lines | Description |
|--------|-------|-------------|
| Import | ~29 | `_count_queue_pending`, `_count_queue_blocked` from `daemon_scheduler` |
| `_vault_state_counts()` | ~161 | Added `queue_pending` and `queue_blocked` keys |
| Vault State output | ~350 | `Queue: N pending (M blocked)` -- blocked only shown when > 0 |
| Maintenance signals | ~372 | Advisory: "N queue tasks blocked on unpopulated stubs" |

### `.claude/skills/ralph/SKILL.md`

| Change | Section | Description |
|--------|---------|-------------|
| Step 0 | new, before Step 1 | Advisory-only stub count + ordering suggestion; always continues |
| Step 3 dry-run | output format | `Queue: X total tasks (Y pending, Z done, B blocked on stubs)` |

---

## Test Coverage

### `_code/tests/test_daemon_scheduler.py` (21 new/updated tests)

| Class | Tests | Covers |
|-------|-------|--------|
| `TestCountQueuePending` | 6 | Flat-list regression, dict format, blocked exclusion, empty, malformed |
| `TestIsLiteratureStub` | 5 | Empty text, populated, missing section, empty sections |
| `TestCountQueueBlocked` | 8 | Missing file, all ready, stubs, missing source, non-reduce ignored, explicit blocked, both formats |
| `TestVaultSummaryDict` | updated | 8-key -> 9-key assertion |
| `TestScanOnlyMode` | updated | 8-key -> 9-key assertion |

### `_code/tests/test_decision_engine.py` (3 new tests)

| Class | Tests | Covers |
|-------|-------|--------|
| `TestQueueBlockedSignal` | 3 | Signal fires at >0, no signal at 0, state summary key present |

### `_code/tests/test_session_orient.py` (1 updated)

| Test | Change |
|------|--------|
| `test_vault_state_counts_missing_dirs` | Expected dict now includes `queue_pending` and `queue_blocked` |

---

## Verification Commands

```bash
# Unit tests (primary)
cd _code && uv run pytest tests/test_daemon_scheduler.py tests/test_decision_engine.py tests/test_session_orient.py -x

# Decision engine JSON output
cd _code && uv run python -m engram_r.decision_engine . 2>/dev/null | python3 -m json.tool
# -> verify queue_blocked appears in state_summary

# Session orient output
cd _code && uv run python scripts/hooks/session_orient.py
# -> verify "Queue: N pending (M blocked)" in Vault State line

# Ralph dry run
# /ralph --dry-run -> verify advisory and blocked count in output
```

---

## Data Flow

```
queue.json (flat list)
    |
    +-- _count_queue_pending() --> VaultState.queue_backlog
    |       handles list AND dict formats; excludes done/archived/blocked
    |
    +-- _count_queue_blocked() --> VaultState.queue_blocked
            counts: explicit "blocked" status
                  + pending reduce-phase with stub source
                  (_is_literature_stub checks Key Points + Relevance)
    |
    +-- scan_vault() populates both fields
    |
    +-- Surfaces:
        +-- decision_engine.classify_signals() -> "queue_blocked" signal
        +-- decision_engine._build_state_summary() -> JSON key
        +-- vault_summary_dict() -> 9-key dict (audit, scan-only, idle)
        +-- session_orient -> "Queue: N pending (M blocked)" + advisory
        +-- ralph Step 0 -> advisory count + ordering suggestion
```

---

## Known Limitations

- Stub detection is heuristic: only checks `## Key Points` and `## Relevance` emptiness. A file with a single word in either section passes. This is intentional -- the goal is to catch completely empty stubs, not partially populated notes.
- `_count_queue_blocked` reads source files from disk for each reduce-phase task. For very large queues (1000+ reduce tasks) this could be slow. Current queue size (~50 tasks) is well within acceptable latency.
- Ralph Step 0 is a skill-level advisory (prompt text), not enforced in code. A model that ignores the advisory can proceed without printing it. This is by design -- advisory only.
