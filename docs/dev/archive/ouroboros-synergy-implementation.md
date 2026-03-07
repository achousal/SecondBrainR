# Ouroboros Synergy Implementation Plan

**Source:** docs/dev/ouroboros-synergy-analysis.md
**Date:** 2026-03-07
**Status:** Complete

---

## Feature 1: Socratic Pre-Specification (default in /init)

**What:** Interview phase that scores research goal readiness before seeding. Runs by default for new goals; skip with `--no-interview`.

### Changes

**`.claude/skills/init/SKILL.md`:**
- Mode Selection table: add `--no-interview` flag to skip interview
- Add Phase 0.5 (INTERVIEW) between Orient and Goal Selection
- Interview runs per-goal inside the goal loop (Step 1.5), after goal is selected but before core questions
- 5 scored dimensions:
  1. Falsifiability: "What would falsify this goal?"
  2. Assumption clarity: "What do you already know that you're treating as uncertain?"
  3. Scope boundary: "What adjacent goals did you exclude, and why?"
  4. Constraint clarity: "What data do you have vs. need?"
  5. Relevance test: "What would make this goal irrelevant?"
- 3-point rubric: clear (2) / partial (1) / vague (0)
- Gate: proceed when >= 4 of 5 dimensions score "clear"
- If gate fails: surface weak dimensions, let user refine, re-score
- If gate passes: summarize scores, proceed to core questions

### Design decisions
- Default on, `--no-interview` to skip (user decision: default)
- No Python code -- pure prompt pattern with scoring logic in skill
- Interview happens per-goal, not once globally, because each goal has different readiness
- Already-seeded goals skip interview (re-init path)

### Effort
Low -- ~60 lines added to SKILL.md

---

## Feature 2: Convergence Detection for /evolve

**What:** After each evolution cycle, compute similarity between child and parent. Track in a convergence log. Surface signal when 3 consecutive cycles hit >= 0.90 similarity.

### Changes

**`_code/src/engram_r/hypothesis_parser.py`:**
- Add `compute_hypothesis_similarity(parent_path: Path, child_path: Path) -> float`
- Weighted Jaccard comparison:
  - Title tokens: 0.15
  - Mechanism section: 0.30
  - Predictions set overlap: 0.25
  - Assumptions set overlap: 0.15
  - Literature refs set overlap: 0.15
- Add `read_convergence_log(log_path: Path, hypothesis_lineage: str) -> list[dict]`
- Add `append_convergence_entry(log_path: Path, entry: dict) -> None`

**`_research/convergence-log.md`:**
- New file, table format tracking: date, parent_id, child_id, similarity, streak, mode
- Lineage tracked by root hypothesis ID (earliest ancestor)

**`.claude/skills/evolve/SKILL.md`:**
- Add Step 7.5 (convergence check) after Gate 7 (Novelty vs Parent)
- After saving evolved hypothesis:
  1. Call `compute_hypothesis_similarity(parent, child)`
  2. Read convergence log for this lineage
  3. If similarity >= 0.90: increment streak; else reset to 0
  4. Append entry to convergence log
  5. If streak >= 3: surface message --
     "Hypothesis has converged (3 consecutive cycles >= 0.90 similarity).
      Consider promoting to experiment or identifying what new evidence would shift it."
- Add convergence info to HANDOFF block

**`_code/tests/test_hypothesis_similarity.py`:**
- Test Jaccard helper
- Test similarity with identical hypotheses (expect 1.0)
- Test similarity with completely different hypotheses (expect ~0.0)
- Test similarity with partial overlap
- Test convergence log read/append
- Test streak calculation

### Design decisions
- Convergence log file, not frontmatter (user decision)
- Single log file at `_research/convergence-log.md` -- append-only
- Lineage tracking by root ancestor ID for multi-generation chains
- 0.90 threshold (slightly lower than Ouroboros' 0.95 -- research hypotheses have more natural variation than software specs)
- Streak resets to 0 on any cycle below threshold

### Effort
Low-medium -- ~60 lines Python + ~30 lines SKILL.md + ~80 lines tests

---

## Implementation Order

1. Feature 2 first (Python code + tests, then SKILL.md edit)
2. Feature 1 second (SKILL.md edit only)
3. Final: update ouroboros-synergy-analysis.md status column
