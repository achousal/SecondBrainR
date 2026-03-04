---
name: meta-review
description: "Synthesize patterns from tournament debates and reflection reviews"
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
argument-hint: "[--goal slug] [--since YYYY-MM-DD]"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- co-scientist parameters
   - `co_scientist.review.aggregate_weights`: understand which dimensions matter most
   - `co_scientist.handoff.mode`: manual | suggested | automatic

2. **`_research/goals/`** -- active research goal
   - If `--goal [slug]` provided, use that goal; otherwise read active goal

3. **Dynamic context injection** (read inside Step 0, keep in working memory):

Recent tournament match logs:
!`ls -t "$VAULT_ROOT/_research/tournaments/"*.md 2>/dev/null | head -5 | xargs cat 2>/dev/null || echo "No tournament matches yet."`

Previous meta-review (if available):
!`ls -t "$VAULT_ROOT/_research/meta-reviews/"*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "No previous meta-reviews."`

4. **`_research/hypotheses/`** -- all hypotheses with review histories
   - Parse frontmatter: id, title, elo, status, review_scores, review_flags, matches, wins, losses

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` contains `--goal [slug]` -> scope to that research goal
- If `$ARGUMENTS` contains `--since YYYY-MM-DD` -> only analyze data from that date forward
- If `$ARGUMENTS` contains `--handoff` -> emit CO-SCIENTIST HANDOFF block at end

**Execute these steps:**

1. Load co-scientist config from `ops/config.yaml`.
2. Read active research goal.
3. Read all tournament match logs from `_research/tournaments/` (filtered by goal and date if specified).
4. Read review histories from all hypothesis notes for the goal.
5. Read previous meta-review (if exists) for trend comparison.
6. Analyze patterns across both tournament debates and reviews (see Pattern Analysis below).
7. Generate structured meta-review note.
8. Present findings to user for approval.
9. Save to `_research/meta-reviews/{YYYY-MM-DD}.md`.
10. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /meta-review -- Meta-Review / Pattern Synthesis Agent

Synthesize patterns from tournament debates and reflection reviews into actionable feedback. Second-order learning -- meta-analysis of the review and debate process itself. Extracts actionable patterns that feed back into /generate, /review, and /evolve, making each cycle more effective than the last.

## Architecture

Implements the Meta-Review agent from the co-scientist system (arXiv:2502.18864). This is the key feedback mechanism that enables the self-improving loop without model fine-tuning.

## Vault Paths

- Tournament logs: `_research/tournaments/`
- Hypotheses: `_research/hypotheses/` (for review histories and Elo rankings)
- Output: `_research/meta-reviews/{YYYY-MM-DD}.md`
- Template: `_code/templates/meta-review.md`
- Research goals: `_research/goals/`

## Code

- `_code/src/engram_r/note_builder.py` -- `build_meta_review_note()`
- `_code/src/engram_r/hypothesis_parser.py` -- parse hypothesis review histories
- `_code/src/engram_r/obsidian_client.py` -- vault I/O

## Pattern Analysis

The meta-review must analyze and synthesize findings across these categories:

### 1. Recurring Weaknesses
- Common critique themes across hypotheses (which assumptions are most often flagged?).
- Frequently flagged assumptions (which ones keep failing verification?).
- Typical failure modes in debates (why do losers lose?).
- Review flags that appear in 3+ hypotheses -> systematic issue.

### 2. Key Literature
- Papers cited most frequently across hypotheses and debates.
- Papers that consistently differentiate winners from losers.
- Foundational references the research area depends on.
- Literature gaps: topics where hypotheses lack grounding.

### 3. Invalid Assumptions
- Assumptions flagged as invalid across multiple hypotheses.
- Assumptions that consistently lead to losses in tournaments.
- Pattern: if assumption X appears, the hypothesis tends to score low on Y dimension.

### 4. Winner Patterns
- What do winning hypotheses have in common?
- Which review dimensions (novelty, correctness, testability, impact) matter most for tournament success?
- What level of specificity tends to win? (broad vs narrow claims)
- Common structural features of high-Elo hypotheses.

### 5. Recommendations for /generate
Concrete, actionable advice:
- What types of hypotheses are missing from the pool?
- What grounding is needed for new hypotheses?
- What assumptions should new hypotheses avoid?
- What mechanisms or domains are under-explored?

### 6. Recommendations for /evolve
Concrete, actionable advice:
- Which weaknesses should evolution address first?
- Which combination opportunities exist (hypotheses with complementary strengths)?
- What simplifications would be valuable?
- Which hypotheses are most promising for extension?

### 7. Trend Analysis (when previous meta-review exists)
- Is hypothesis quality improving across cycles?
- Are the same weaknesses persisting (stale patterns)?
- Have previous recommendations been addressed?
- New patterns that emerged since the last meta-review.

## Meta-Review Note Format

```markdown
---
description: "Meta-review synthesizing patterns from N tournament matches and M reviewed hypotheses"
type: "meta-review"
research_goal: "[[{goal-slug}]]"
date: "{YYYY-MM-DD}"
tournament_matches_analyzed: {N}
hypotheses_analyzed: {M}
previous_meta_review: "[[{previous-date}]]" or null
---

# Meta-Review: {YYYY-MM-DD}

## Summary
{2-3 sentence overview of key findings}

## Recurring Weaknesses
{bullet list with specific hypothesis IDs and patterns}

## Key Literature
{most-cited papers, literature gaps}

## Invalid Assumptions
{assumptions that consistently fail, with IDs}

## Winner Patterns
{structural and content features of high-Elo hypotheses}

## Recommendations for Generation
{actionable advice for /generate}

## Recommendations for Evolution
{actionable advice for /evolve}

## Trend Analysis
{comparison with previous meta-review, or "First meta-review -- no trend data"}
```

## The Self-Improving Loop

This meta-review output is read by:
- `/generate` -- via "Read latest meta-review" step in Runtime Configuration
- `/review` -- via mode 6 (tournament-informed review)
- `/evolve` -- via "Read latest meta-review" step in Runtime Configuration
- `/research` -- to inform next step selection

This creates a feedback loop where each cycle of generate-debate-evolve-meta-review improves quality without any model fine-tuning. The improvement mechanism is prompt injection via vault state: meta-review notes persist and are read by subsequent skill invocations.

## Quality Gates

### Gate 1: Minimum Data
Meta-review requires at least 1 tournament match OR 1 reviewed hypothesis. If neither exists: HANDOFF `status: no-data`.

### Gate 2: Specific Citations
Every pattern claim must reference specific hypothesis IDs, match IDs, or review entries. No ungrounded generalizations.

### Gate 3: Actionable Recommendations
Both "Recommendations for Generation" and "Recommendations for Evolution" must contain at least 1 concrete, actionable item each. "Generate better hypotheses" is not actionable. "Generate hypotheses testing mechanism X because current pool lacks coverage of pathway Y" is actionable.

### Gate 4: Trend Comparison
If a previous meta-review exists, the trend analysis section must explicitly compare: are previous recommendations being addressed? Are patterns persisting or resolving?

### Gate 5: Consistency with Data
Verify that claimed patterns actually appear in the data. If a pattern is claimed about winners, verify the cited hypotheses actually have high Elo. Cross-check review scores and flags.

## Error Handling

| Error | Action |
|-------|--------|
| No tournament matches AND no reviewed hypotheses | HANDOFF `status: no-data`. Suggest running /tournament or /review first |
| No tournament matches but reviewed hypotheses exist | Generate meta-review from review data only. Note limitation |
| No reviewed hypotheses but tournament matches exist | Generate meta-review from tournament data only. Note limitation |
| Previous meta-review load failure | Continue without trend analysis. Note absence |
| `build_meta_review_note()` failure | Report error, present meta-review as text. HANDOFF `status: partial` |

## Critical Constraints

- **Always cite specific hypothesis IDs and match IDs** when identifying patterns. No ungrounded claims.
- **Recommendations must be concrete and actionable.** Abstract advice is worse than no advice.
- **Compare to previous meta-reviews** when they exist. Track whether the system is improving.
- **Present findings to user before saving.** The meta-review shapes the entire feedback loop.
- **Never fabricate patterns.** If the data is insufficient, say so rather than hallucinating trends.
- **Scope to the active research goal.** Do not mix patterns across different research goals.

## CO-SCIENTIST HANDOFF

When `--handoff` is present in `$ARGUMENTS`, emit after all work:

```
CO-SCIENTIST HANDOFF
skill: meta-review
goal: [[{goal-slug}]]
date: {YYYY-MM-DD}
status: {complete | partial | failed | no-data}
summary: {one sentence, e.g., "synthesized patterns from 8 matches and 5 reviewed hypotheses, 3 key recommendations"}

outputs:
  - _research/meta-reviews/{YYYY-MM-DD}.md

analysis_scope:
  tournament_matches: {N}
  reviewed_hypotheses: {M}
  date_range: {earliest} to {latest}

quality_gate_results:
  - gate: minimum-data -- {pass | no-data: no matches or reviews}
  - gate: specific-citations -- {pass | fail: ungrounded claims count}
  - gate: actionable-recommendations -- {pass | fail: missing section}
  - gate: trend-comparison -- {pass | n/a (no previous meta-review)}
  - gate: consistency-with-data -- {pass | fail: mismatched claims}

recommendations:
  next_suggested: {generate | evolve | tournament} -- {why}

learnings:
  - {meta-observation about the research loop itself} | NONE
```

## Skill Graph

Invoked by: /research
Invokes: (none -- leaf agent)
Reads: _research/tournaments/, _research/hypotheses/ (review histories), _research/meta-reviews/ (previous), _research/goals/
Writes: _research/meta-reviews/
