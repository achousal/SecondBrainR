---
name: review
description: "Critically evaluate hypotheses through multiple review lenses"
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
argument-hint: "[hyp-id | all | unreviewed] [--mode 1-6] [--goal slug]"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- co-scientist parameters
   - `co_scientist.review.aggregate_weights`: scoring weights for overall calculation
     - `correctness: 0.30`, `testability: 0.25`, `novelty: 0.25`, `impact: 0.20`
   - `co_scientist.handoff.mode`: manual | suggested | automatic

2. **`_research/goals/`** -- active research goal
   - Parse `project_tag` from goal frontmatter for hypothesis filtering
   - If `--goal [slug]` provided, use that goal; otherwise read active goal

3. **Dynamic context injection** (read inside Step 0, keep in working memory):

Latest meta-review feedback (if available):
!`ls -t "$VAULT_ROOT/_research/meta-reviews/"*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "No meta-reviews yet."`

If no meta-review exists: disable mode 6 in the mode menu (tournament-informed review requires meta-review data).

4. **`_research/hypotheses/`** -- target hypotheses
   - Parse frontmatter: id, title, elo, status, review_scores, review_flags, research_goal, tags

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` contains a hypothesis ID (e.g., `hyp-20260301-001`) -> review that hypothesis
- If `$ARGUMENTS` contains `all` -> review all hypotheses for the active goal
- If `$ARGUMENTS` contains `unreviewed` -> review only hypotheses with null review_scores
- If `$ARGUMENTS` contains `--mode N` (1-6) -> use that review mode
- If `$ARGUMENTS` contains `--goal [slug]` -> scope to that research goal
- If `$ARGUMENTS` contains `--handoff` -> emit CO-SCIENTIST HANDOFF block at end
- If no target specified -> ask user which hypothesis to review

**Execute these steps:**

1. Load co-scientist config from `ops/config.yaml` (specifically `review.aggregate_weights`).
2. Read active research goal. Identify target hypotheses from arguments.
3. Read meta-review feedback (if exists) -- needed for mode 6.
4. If no review mode specified: present mode menu (disable mode 6 if no meta-review).
5. For each target hypothesis and selected mode:
   a. Read the hypothesis note.
   b. Apply the review mode (see Review Modes below).
   c. Compute aggregate overall score using config weights.
   d. Present review results to user for approval before saving.
   e. Append timestamped review entry to "## Review History" section.
   f. Update `review_scores` and `review_flags` in frontmatter.
6. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /review -- Multi-Mode Hypothesis Review Agent

Critically evaluate hypotheses through multiple review lenses. Deductive verification -- testing internal consistency and evidence fit. Provides the quality signal that drives tournament rankings and evolution priorities.

## Architecture

Implements the Reflection agent from the co-scientist system (arXiv:2502.18864). Supports 6 review modes, each applying a different analytical lens.

## Vault Paths

- Hypotheses: `_research/hypotheses/`
- Meta-reviews: `_research/meta-reviews/`
- Research goals: `_research/goals/`

## Code

- `_code/src/engram_r/hypothesis_parser.py` -- parse and update hypothesis notes
- `_code/src/engram_r/search_interface.py` -- unified search interface for mode 2
- `_code/src/engram_r/obsidian_client.py` -- vault I/O

## Review Modes

### Mode 1: Quick Screen
- Rapid assessment without external tools.
- Score: novelty, correctness, testability, impact, overall (1-10 each).
- Flag obvious issues (missing citations, vague predictions, unsupported claims).

### Mode 2: Literature Review
- Search configured literature backends for the hypothesis claim.
- Flag if hypothesis is already published, partially known, or contradicted by evidence.
- Update `review_flags` accordingly (e.g., `prior-art-found`, `contradicted-by-PMID-XXXXX`).
- Cite source identifiers for all flagged findings.

### Mode 3: Deep Verification
- Decompose hypothesis into constituent assumptions.
- For each assumption, search for supporting and contradicting evidence.
- Flag invalid or unsupported assumptions.
- Score based on assumption validity rate.

### Mode 4: Observation Review
- User provides experimental data or observations.
- Assess whether the hypothesis explains the data better than alternatives.
- Score based on explanatory power relative to competing hypotheses.

### Mode 5: Simulation Review
- Walk through the proposed mechanism step by step.
- Identify failure modes, bottlenecks, and implausible steps.
- Assess logical consistency of the causal chain.
- Score based on mechanism plausibility.

### Mode 6: Tournament-Informed Review
- Read latest meta-review patterns.
- Apply learned critique themes from previous tournaments.
- Score based on patterns that distinguish winners from losers.
- **Requires**: at least one meta-review in `_research/meta-reviews/`. Disabled if none exists.

## Scoring System

All scores use a 1-10 scale. Null means unreviewed.

**Individual dimensions**: novelty, correctness, testability, impact.

**Aggregate overall score** (weighted mean from config):
```
overall = (correctness * 0.30) + (testability * 0.25) + (novelty * 0.25) + (impact * 0.20)
```

Weights MUST come from `co_scientist.review.aggregate_weights` in config. Do not hard-code.

## Review Entry Format

Appended to the hypothesis "## Review History" section:

```markdown
### {YYYY-MM-DD} {Mode Name}
**Scores**: novelty={N}, correctness={N}, testability={N}, impact={N}, overall={N}
**Flags**: {list or "none"}
**Summary**: {2-3 sentence assessment}
**Key concerns**: {bullet list}
```

## Project Scoping

If a `project_tag` is set on the active research goal, filter hypotheses to those tagged with it when reviewing "all" or "unreviewed". This prevents cross-project hypothesis mixing during batch reviews.

## Quality Gates

### Gate 1: Score Completeness
After review, all 5 score fields (novelty, correctness, testability, impact, overall) must be non-null. Partial scoring is not allowed.

### Gate 2: Aggregate Formula Compliance
The overall score must equal the weighted sum of dimension scores using config weights. Verify: `abs(overall - weighted_sum) < 0.1`. If mismatch: recalculate.

### Gate 3: Review History Append
A new Review History entry must be appended BEFORE frontmatter scores are updated. If the hypothesis has no "## Review History" section: create it. The entry provides the reasoning behind the scores.

### Gate 4: Review Flags Format
`review_flags` in frontmatter must be a YAML list (e.g., `["assumption-X-invalid", "prior-art-found"]`), not a string. Empty flags should be `[]`, not null.

### Gate 5: Literature Citations (Mode 2)
In literature review mode, every flag must reference a specific source identifier. Flags like "contradicted" without a citation fail this gate.

## Error Handling

| Error | Action |
|-------|--------|
| Hypothesis ID not found | List available hypotheses for the goal. If `--handoff`: HANDOFF `status: failed` |
| `update_frontmatter_field` failure | Report error, present review in conversation as text. HANDOFF `status: partial` |
| Missing "## Review History" section | Create the section before appending. This is not an error -- older hypotheses may lack it |
| No meta-review for mode 6 | Inform user mode 6 is unavailable. Offer alternative modes. Do not fail |
| Literature search failure in mode 2 | Warn, complete review with available data. Note in review entry: "literature search unavailable" |

## Critical Constraints

- **Never update scores without appending Review History first.** The reasoning trail is the primary artifact.
- **Never apply mode 6 without a meta-review.** Tournament-informed review requires tournament pattern data.
- **Always use weights from config** for the aggregate formula. Never hard-code weights.
- **Always present review results** to user before saving to vault.
- **`review_flags` must be a YAML list**, not a string or null.
- **Filter by `project_tag`** when batch-reviewing "all" or "unreviewed".

## CO-SCIENTIST HANDOFF

When `--handoff` is present in `$ARGUMENTS`, emit after all work:

```
CO-SCIENTIST HANDOFF
skill: review
goal: [[{goal-slug}]]
date: {YYYY-MM-DD}
status: {complete | partial | failed | no-data}
summary: {one sentence, e.g., "reviewed 5 hypotheses via mode 1 (quick screen), avg overall: 6.8"}

outputs:
  - hyp-{id} -- reviewed (overall: {N}, flags: {count})

quality_gate_results:
  - gate: score-completeness -- {pass | fail: hyp-ids with missing scores}
  - gate: aggregate-formula -- {pass | fail: mismatched hyp-ids}
  - gate: review-history-append -- {pass | fail: reason}
  - gate: review-flags-format -- {pass | fail: reason}
  - gate: literature-citations -- {pass | fail | n/a (mode != 2)}

recommendations:
  next_suggested: {tournament | evolve | generate} -- {why}

learnings:
  - {observation about hypothesis quality patterns} | NONE
```

## Skill Graph

Invoked by: /research
Invokes: (none -- leaf agent)
Reads: _research/hypotheses/, _research/meta-reviews/, _research/goals/
Writes: _research/hypotheses/ (frontmatter: review_scores, review_flags, Review History section)
