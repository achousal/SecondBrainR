---
description: "Full redesign of the metabolic health indicator system -- 5-indicator model replaced with 7-indicator, 3-tier architecture"
type: development
status: complete
created: 2026-03-02
updated: 2026-03-02
---

# Metabolic Health Indicator System -- Redesign

## Motivation

The original 5-indicator model (QPR, VDR, CMR, HCR, SWR) had confirmed bugs and missing capabilities:

| Problem | Impact |
|---------|--------|
| SWR counts `.md` but sessions are `.json` | Permanently broken -- always returns 0 |
| `stale_note_count` never populated in `scan_vault()` | Stale-note signals never fire |
| SWR alarm generates no decision engine signal | Dead code path |
| No historical persistence or trend analysis | No longitudinal awareness |
| Graph health and inbox velocity unmeasured | Blind spots in vault health |

SWR (Sessions Written per Artifact) was conceptually confused -- many sessions are exploration, config, or planning, not claim production. TPV (Throughput Velocity) directly measures what SWR tried to proxy.

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Indicator count | 7 (was 5) | Added TPV, GCR, IPR; removed SWR |
| Tier model | 3 tiers | Governance (auto-suppress) vs awareness (user-facing) vs observational (logged only) |
| TPV over SWR | Claims processed per day | Directly measures throughput, not session-to-artifact ratio |
| GCR design | 1 - (orphans / total) | Reuses orphan scan already in daemon; avoids double-scanning |
| IPR design | inbox_rate / processing_rate | Rate ratio catches velocity mismatch, not absolute counts |
| Empty vault gating | TPV >= 5 notes, HCR >= 3 hypotheses | Prevents false alarms on new or small vaults |
| History storage | YAML in `ops/metabolic/` | Consistent with ops/ conventions; atomic writes via tmp+rename |
| Trend direction | "lower is better" vs "higher is better" per indicator | Enables correct "improving"/"declining" labels |
| Latest cache | `ops/metabolic/latest.yaml` | Session orient reads cache instead of full history |

---

## Indicator Model

### Tier 1: Governance (auto-suppress daemon generative tasks)

| Indicator | Definition | Alarm Key | Threshold |
|-----------|-----------|-----------|-----------|
| QPR | Days of backlog at current rate | `qpr_critical` | > 3.0 |
| CMR | New notes vs maintained per week | `cmr_hot` | > 10.0 |
| TPV | Claims processed per day | `tpv_stalled` | < 0.1 |

### Tier 2: Awareness (user-facing signals via /next)

| Indicator | Definition | Alarm Key | Threshold | Gate |
|-----------|-----------|-----------|-----------|------|
| HCR | % hypotheses with empirical engagement | `hcr_low` | < 15% | >= 3 hypotheses |
| GCR | 1 - (orphan_count / total_notes) | `gcr_fragmented` | < 0.3 | none |
| IPR | Inbox growth rate / processing rate | `ipr_overflow` | > 3.0 | none |

### Tier 3: Observational (logged, no automated action)

| Indicator | Definition | Notes |
|-----------|-----------|-------|
| VDR | % claims not human-verified | Informational only, never alarms |

### Empty Vault Behavior

All indicators return safe defaults (no alarms) when the vault is new or nearly empty. TPV requires >= 5 notes before `tpv_stalled` can fire. HCR requires >= 3 hypotheses before `hcr_low` can fire.

---

## Files Modified

| File | Change Type | Lines |
|------|-------------|-------|
| `_code/src/engram_r/metabolic_indicators.py` | Rewrite | ~350 |
| `_code/src/engram_r/metabolic_history.py` | New | ~250 |
| `_code/src/engram_r/daemon_config.py` | Update | ~20 |
| `_code/src/engram_r/daemon_scheduler.py` | Update | ~60 |
| `_code/src/engram_r/decision_engine.py` | Update | ~40 |
| `_code/scripts/hooks/session_orient.py` | Update | ~50 |
| `.claude/skills/stats/SKILL.md` | Update | ~30 |
| `ops/daemon-config.yaml` | Update | ~15 |
| `_code/tests/test_metabolic_indicators.py` | Rewrite | ~300 |
| `_code/tests/test_metabolic_history.py` | New | ~210 |
| `_code/tests/test_daemon_scheduler.py` | Update | ~30 |
| `_code/tests/test_decision_engine.py` | Update | ~30 |

---

## Key Module Changes

### metabolic_indicators.py

`MetabolicState` dataclass: replaced `swr` field with `tpv`, added `gcr`, `ipr`, `total_notes`, `total_hypotheses`.

New functions:
- `compute_tpv(queue_data, lookback_days)` -- completed tasks / lookback_days
- `compute_gcr(orphan_count, total_notes)` -- 1 - (orphans / total), defaults 1.0
- `compute_ipr(inbox_dir, notes_dir, lookback_days)` -- inbox ctime rate / note creation rate
- `_count_notes(notes_dir)` -- helper for total note count

Updated:
- `compute_hcr()` returns `tuple[float, int]` (value + total count) for gating
- `classify_alarms()` -- new params: `tpv_stalled`, `gcr_fragmented`, `ipr_overflow`, `min_notes_for_tpv`, `min_hypotheses_for_hcr`
- `compute_metabolic_state()` -- new `orphan_count` param, replaces `swr_archive` with new thresholds
- `ALARM_TIERS` dict maps alarm keys to tier numbers (1/2/3)

### metabolic_history.py (new)

Persistence and trend analysis:
- `MetabolicSnapshot` -- timestamp, session_id, indicators dict, alarm_keys
- `MetabolicTrend` -- indicator, current, previous, delta, direction, avg_7, avg_30
- `save_snapshot()` -- atomic write to `ops/metabolic/history.yaml` + `latest.yaml`, trims to max_snapshots
- `load_history()` / `load_latest()` -- readers with graceful fallback
- `compute_trends()` -- rolling averages (7-day, 30-day), direction semantics
- `format_trend_line()` -- condensed summary for session orient

### daemon_scheduler.py

- `scan_vault()`: stale_note_count now populated via mtime scan against `stale_notes_days` threshold
- Metabolic call passes `orphan_count=state.orphan_count` (avoids double-scanning)
- Governor: tier 1 alarms (`qpr_critical`, `cmr_hot`, `tpv_stalled`) suppress P1 generative tasks via set intersection
- Dashboard format updated for 7 indicators

### decision_engine.py

New signals:
- `metabolic_tpv` (session speed) -- /reduce or /ralph
- `metabolic_gcr` (multi_session speed) -- /reflect --connect-orphans
- `metabolic_ipr` (session speed) -- /reduce

`_build_state_summary()` includes `tpv`, `gcr`, `ipr` (replaces `swr`).

### session_orient.py

New `_metabolic_dashboard()` function reads `ops/metabolic/latest.yaml` and formats:
```
### Metabolic
  QPR 2.1d | CMR 3:1 | TPV 1.2/d | GCR 0.85 | IPR 1.5 | VDR 95%
  Trend: QPR improving, CMR stable
```

Gated on `claim_count > 0` (suppressed for empty vaults).

### daemon_config.py

`MetabolicConfig` updated:
- Removed: `swr_archive`
- Added: `tpv_stalled: 0.1`, `gcr_fragmented: 0.3`, `ipr_overflow: 3.0`, `history_max_snapshots: 90`

---

## Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_metabolic_indicators.py` | 50 | Pass |
| `test_metabolic_history.py` | 18 | Pass |
| `test_daemon_scheduler.py` | 132 | Pass |
| `test_decision_engine.py` | 98 | Pass |
| **Total metabolic-related** | **298** | **Pass** |

Key test classes:
- `TestComputeTPV` (6 tests) -- completions, no completions, high throughput, empty/none queue, old exclusion
- `TestComputeGCR` (4 tests) -- no orphans, all orphans, mixed, empty vault
- `TestComputeIPR` (4 tests) -- balanced, empty dirs, overflow, processing dominant
- `TestClassifyAlarms` -- TPV/HCR gating, GCR/IPR alarm conditions
- `TestSaveSnapshot` -- create, append, trim, latest cache
- `TestComputeTrends` -- improving, declining, stable, no history, rolling averages
- `TestFormatTrendLine` -- non-stable, all stable, no previous

---

## Verification

```bash
# Unit + integration tests
cd _code && uv run pytest tests/test_metabolic_indicators.py tests/test_metabolic_history.py tests/test_daemon_scheduler.py tests/test_decision_engine.py -v

# CLI smoke test
cd _code && uv run python -m engram_r.metabolic_indicators ..

# Full suite
cd _code && uv run pytest
```

| Check | Status |
|-------|--------|
| Unit tests (68 metabolic-specific) | Pass |
| Integration tests (230 daemon + decision engine) | Pass |
| Full test suite (1530 tests) | Pass |
| CLI returns JSON with 7 indicators | Verified |
| Decision engine includes new metabolic fields | Verified |
| History persistence (atomic writes, trim) | Tested |
| Empty vault -- no false alarms | Tested |

---

## Configuration Reference

`ops/daemon-config.yaml` metabolic section:

```yaml
metabolic:
  enabled: true
  qpr_critical: 3.0
  cmr_hot: 10.0
  tpv_stalled: 0.1
  hcr_low: 15.0
  gcr_fragmented: 0.3
  ipr_overflow: 3.0
  history_max_snapshots: 90
```
