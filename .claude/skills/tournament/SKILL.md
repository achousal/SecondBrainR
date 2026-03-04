---
name: tournament
description: "Rank hypotheses through pairwise scientific debate with Elo ratings"
version: "1.0"
generated_from: "co-scientist-v2.0"
user-invocable: false
model: sonnet
context: fork
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
  - Write
argument-hint: "[--matches N] [--goal slug] [--federated]"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- co-scientist parameters
   - `co_scientist.default_match_count`: matches per round (default: 5)
   - `co_scientist.elo.starting`: 1200
   - `co_scientist.elo.k_factor`: 32
   - `co_scientist.tournament.top_tier_threshold`: 0.25 (top N% get multi-turn debate)
   - `co_scientist.handoff.mode`: manual | suggested | automatic

2. **`_research/goals/`** -- active research goal
   - Parse `project_tag` from goal frontmatter for hypothesis filtering
   - If `--goal [slug]` provided, use that goal; otherwise read active goal

3. **`_research/hypotheses/`** -- hypothesis pool
   - Parse frontmatter: id, title, elo, status, matches, wins, losses, quarantine, research_goal, tags
   - Exclude quarantined hypotheses (see Quarantine Guard)

4. **`_code/templates/tournament-match.md`** -- match note template

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` contains `--matches N` -> run N matches (else use `co_scientist.default_match_count`)
- If `$ARGUMENTS` contains `--goal [slug]` -> scope to that research goal
- If `$ARGUMENTS` contains `--federated` -> use federated mode (see below)
- If `$ARGUMENTS` contains `--handoff` -> emit CO-SCIENTIST HANDOFF block at end

**Execute these steps:**

1. Load co-scientist config from `ops/config.yaml`.
2. Read active research goal. Read all hypotheses for that goal.
3. Apply Quarantine Guard: exclude `quarantine: true` hypotheses.
4. Verify >= 2 eligible hypotheses exist. If not: HANDOFF `status: no-data`, stop.
5. Generate matchups using `generate_matchups()` -- prioritizes under-matched and similar-Elo pairs.
6. If no match count specified: ask user how many matches to run (suggest config default).
7. For each match:
   a. Present both hypotheses side by side (title, statement, mechanism, predictions).
   b. Determine tier: if both in top 25% by Elo -> multi-turn debate; else -> single-turn comparison.
   c. Conduct structured debate across dimensions: novelty, correctness, testability, impact.
   d. Determine winner with justification.
   e. Present verdict to user -- user can override.
   f. Compute Elo changes via `compute_elo()`.
   g. Verify Elo sum preservation: `abs(delta_a + delta_b) < 0.01`.
   h. Update both hypothesis frontmatter: elo, matches, wins/losses.
   i. Save match log to `_research/tournaments/{date}-{match_id}.md`.
8. Update `_research/hypotheses/_index.md` leaderboard table (sorted by Elo descending).
9. Show updated leaderboard to user.
10. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /tournament -- Elo Tournament Ranking Agent

Rank hypotheses through pairwise scientific debate with Elo ratings. Competitive falsification -- pairwise adversarial comparison forces relative ranking. The Elo system produces a stable ordering that surfaces the strongest ideas for evolution and identifies weak ones for pruning.

## Architecture

Implements the Ranking/Tournament agent from the co-scientist system (arXiv:2502.18864).

## Vault Paths

- Hypotheses: `_research/hypotheses/`
- Match logs: `_research/tournaments/`
- Template: `_code/templates/tournament-match.md`
- Leaderboard: `_research/hypotheses/_index.md`
- Research goals: `_research/goals/`

## Code

- `_code/src/engram_r/elo.py` -- `compute_elo()`, `generate_matchups()`, `expected_score()`
- `_code/src/engram_r/hypothesis_parser.py` -- read/update hypothesis notes
- `_code/src/engram_r/note_builder.py` -- `build_tournament_match_note()`
- `_code/src/engram_r/obsidian_client.py` -- vault I/O

## Quarantine Guard

Before including any hypothesis in tournament matchups, check its frontmatter for `quarantine: true`. Quarantined hypotheses are federation imports that have not been human-verified and must not participate in ranking.

**Action:** When reading hypotheses in step 1, skip any with `quarantine: true` in YAML frontmatter. Log: "Skipping quarantined hypothesis [id] -- awaiting human review." Do NOT include quarantined hypotheses in matchup generation, Elo calculations, or leaderboard updates.

## Tiered Comparison

- **Top tier** (top 25% by Elo, threshold from config): Multi-turn debate -- deeper analysis, edge case examination, assumption scrutiny. At least 2 debate rounds per dimension.
- **Standard tier** (bottom 75%): Single-turn pairwise comparison -- quicker assessment across all dimensions.

Threshold comes from `co_scientist.tournament.top_tier_threshold` in config.

## Elo System

- Starting Elo: from `co_scientist.elo.starting` (default: 1200)
- K-factor: from `co_scientist.elo.k_factor` (default: 32)
- Rating sum is preserved across matches (zero-sum system).
- Use `expected_score()` for probability calculations.
- Elo changes are symmetric: `abs(delta_a) == abs(delta_b)`.

## Debate Structure

For each match, evaluate across 4 dimensions:

1. **Novelty** -- Is the hypothesis genuinely new? Does it propose something the field hasn't considered?
2. **Correctness** -- Is the mechanism plausible? Are the assumptions valid? Does evidence support it?
3. **Testability** -- Can the predictions be falsified? Are the proposed experiments feasible?
4. **Impact** -- If true, how significant would this be for the field? Does it change practice?

For each dimension: state which hypothesis is stronger and why.
Final verdict: which hypothesis wins overall, with justification.

## Match Log Format

Frontmatter: `type: tournament-match`, `date`, `research_goal`, `hypothesis_a`, `hypothesis_b`, `winner`, `elo_change_a`, `elo_change_b`, `tier` (top|standard), `mode` (local|federated).

Sections: Debate Summary, Novelty Comparison, Correctness, Testability, Impact, Verdict, Justification.

## Leaderboard Format (in _research/hypotheses/_index.md)

```markdown
| Rank | ID | Title | Elo | Gen | Status | Matches | W/L |
```

Sorted by Elo descending. Updated after each tournament round.

## Federated Mode (`--federated`)

When invoked with `--federated`, the tournament includes `type: foreign-hypothesis` notes imported from peer vaults via `/federation-sync`.

Key differences from local mode:
- Matches update `elo_federated` and `matches_federated` instead of `elo` and `matches`.
- Local hypotheses also get `elo_federated` / `matches_federated` fields added on first federated match (starting at their current `elo` value).
- Match logs include `mode: federated` in frontmatter.
- Leaderboard is written to `_research/hypotheses/_federated-leaderboard.md` (separate from the local `_index.md` leaderboard).
- Foreign hypotheses are read-only -- their `elo` (source vault rating) is never modified.

This keeps local and federated rankings independent.

## Project Scoping

If a `project_tag` is set on the active research goal, only include hypotheses tagged with it in matchup generation. This prevents cross-project hypothesis mixing in tournaments.

## Quality Gates

### Gate 1: Minimum Pool Size
Tournament requires >= 2 eligible (non-quarantined) hypotheses. If < 2: HANDOFF `status: no-data`.

### Gate 2: Elo Sum Preservation
After each match, verify: `abs(delta_a + delta_b) < 0.01`. If violated: recalculate using `compute_elo()`.

### Gate 3: Match Log Completeness
Every match must be saved as a log note in `_research/tournaments/`. No unrecorded debates.

### Gate 4: Leaderboard Consistency
After updating the leaderboard, verify Elo values in `_index.md` match the frontmatter of each hypothesis. If mismatch: use frontmatter as source of truth.

### Gate 5: User Override Recorded
If the user overrides a verdict, record the override in the match log: `override: true`, `original_verdict: hyp-{id}`.

### Gate 6: Quarantine Enforcement
No quarantined hypothesis may appear in any matchup, Elo calculation, or leaderboard entry.

## Error Handling

| Error | Action |
|-------|--------|
| < 2 eligible hypotheses | HANDOFF `status: no-data`. Suggest running /generate first |
| `compute_elo()` failure | Report error, present debate without Elo update. HANDOFF `status: partial` |
| `generate_matchups()` failure | Fall back to random pairing (avoid re-matching recent pairs). Log fallback |
| Match log write failure | Warn user. Debate result is primary -- continue with Elo updates |
| `_index.md` update failure | Warn user. Hypothesis frontmatter is source of truth for Elo |
| Quarantined hypothesis in pool | Skip silently with log message. Not an error |

## Critical Constraints

- **Always let the user override the verdict.** Agent judgment is advisory.
- **Verify Elo sum preservation after every match.** Zero-sum invariant is non-negotiable.
- **Log every match.** No unrecorded debates.
- **Present matches one at a time** with full context (not batched summaries).
- **Never include quarantined hypotheses** in matchups or Elo calculations.
- **K-factor and starting Elo must come from config.** Never hard-code.
- **Filter by `project_tag`** when scoping the hypothesis pool.

## CO-SCIENTIST HANDOFF

When `--handoff` is present in `$ARGUMENTS`, emit after all work:

```
CO-SCIENTIST HANDOFF
skill: tournament
goal: [[{goal-slug}]]
date: {YYYY-MM-DD}
status: {complete | partial | failed | no-data}
summary: {one sentence, e.g., "ran 5 matches, top hypothesis hyp-001 (Elo 1264)"}

outputs:
  - _research/tournaments/{match-log-id}.md -- {hyp-A} vs {hyp-B}: {winner}

leaderboard_snapshot:
  - hyp-{id}: {elo} ({+/-delta})

quality_gate_results:
  - gate: minimum-pool-size -- {pass | no-data: only N hypotheses}
  - gate: elo-sum-preservation -- {pass | fail: match-ids with violation}
  - gate: match-log-completeness -- {pass | fail: unlogged match count}
  - gate: leaderboard-consistency -- {pass | fail: mismatched ids}
  - gate: user-override-recorded -- {pass | n/a (no overrides)}
  - gate: quarantine-enforcement -- {pass | fail: quarantined ids included}

recommendations:
  next_suggested: {meta-review | evolve | generate} -- {why}

learnings:
  - {observation about hypothesis quality patterns or tournament dynamics} | NONE
```

## Skill Graph

Invoked by: /research
Invokes: (none -- leaf agent)
Reads: _research/hypotheses/, _research/goals/
Writes: _research/tournaments/, _research/hypotheses/ (frontmatter: elo, matches, wins, losses), _research/hypotheses/_index.md
