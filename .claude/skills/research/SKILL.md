---
name: research
description: "Orchestrate the co-scientist generate-debate-evolve loop"
version: "1.0"
generated_from: "co-scientist-v2.0"
user-invocable: true
model: sonnet
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Skill
  - TaskCreate
  - TaskUpdate
  - TaskList
argument-hint: "[goal-slug | new]"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- co-scientist parameters
   - Full `co_scientist:` section (generation count, Elo params, review weights, tournament config, handoff mode)
   - `research.primary`, `research.fallback`: search backend configuration

2. **`_research/goals/`** -- existing research goals
   - Scan for active goals. Parse frontmatter: slug, title, domain, project_tag, status

3. **`_research/hypotheses/_index.md`** -- current leaderboard
   - If `_index.md` does not exist, create it (see State Initialization below)

4. **`_research/meta-reviews/`** -- latest meta-review
   - Parse recommendations for next step suggestion

5. **Dynamic context injection** (read inside Step 0, keep in working memory):

Latest meta-review feedback (if available):
!`ls -t "$VAULT_ROOT/_research/meta-reviews/"*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "No meta-reviews yet."`

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` contains `new` -> create new research goal workflow
- If `$ARGUMENTS` contains a goal slug -> load that goal and show co-scientist menu
- If `$ARGUMENTS` is empty -> list existing goals and ask user to select or create new
- Note: `--handoff` is not applicable to /research itself (supervisor does not hand off to itself)

**Execute these steps:**

1. Load co-scientist config from `ops/config.yaml`.
2. Determine target goal:
   a. If `new`: run goal creation workflow (see below).
   b. If slug provided: load that goal.
   c. If empty: list existing goals, ask user to select or create new.
3. Read latest meta-review for context.
4. Read `_index.md` leaderboard for current state.
5. Present co-scientist menu with state-aware suggestions.
6. When user selects an action: invoke the corresponding skill with `--handoff`.
7. Parse the CO-SCIENTIST HANDOFF block from the skill result.
8. Process handoff: display summary, check quality gates, log learnings.
9. Return to co-scientist menu with updated state.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /research -- Supervisor / Orchestrator

Orchestrate the co-scientist generate-debate-evolve loop interactively. Research design and supervision -- selects the next method step based on the current state of knowledge, closing the feedback loop between meta-review output and new generation cycles.

## Architecture

Implements the Supervisor agent from the co-scientist architecture (arXiv:2502.18864). It defines research goals and coordinates other agent skills via the CO-SCIENTIST HANDOFF protocol.

## Vault Paths

- Research goals: `_research/goals/`
- Leaderboard: `_research/hypotheses/_index.md`
- Meta-reviews: `_research/meta-reviews/`
- Template: `_code/templates/research-goal.md`
- Vault root: repository root (detected automatically)

## Code

- `_code/src/engram_r/note_builder.py` -- `build_research_goal_note()`
- `_code/src/engram_r/obsidian_client.py` -- vault I/O
- `_code/src/engram_r/hypothesis_parser.py` -- parse hypothesis notes

## Goal Creation Workflow

1. Ask the user for their research question or goal in natural language.
2. Clarify: domain, constraints, evaluation criteria, key background.
3. Ask if this goal is linked to a specific project (for `project_tag` inheritance).
4. Build a research goal note using `build_research_goal_note()`.
5. Save to `_research/goals/{slug}.md`.
6. Create `_index.md` if it does not exist (see State Initialization).
7. Present the co-scientist menu.

## State Initialization

If `_research/hypotheses/_index.md` does not exist, create it:
```markdown
---
description: "Elo-ranked hypothesis leaderboard and generation index"
type: "moc"
created: "{today}"
---

# Hypothesis Leaderboard

## Rankings

| Rank | Hypothesis | Elo | Goal | Gen | Status |
|------|-----------|-----|------|-----|--------|

## Recent Activity
```

## Co-Scientist Menu

After each operation, return to this menu. Include state-aware suggestions based on current vault state.

```
Co-Scientist: [[{goal-title}]]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

State: {N} hypotheses | Top: {hyp-id} (Elo {N}) | {M} matches played

1. Generate   -- Create new hypotheses          {suggest if < 3 hypotheses}
2. Review     -- Critically review hypotheses    {suggest if unreviewed exist}
3. Tournament -- Run Elo-ranked debates          {suggest if >= 2 reviewed}
4. Evolve     -- Refine top hypotheses           {suggest if >= 1 tournament round}
5. Landscape  -- Map hypothesis space            {suggest if >= 5 hypotheses}
6. Meta-review-- Synthesize feedback patterns    {suggest if >= 1 tournament round}
7. Leaderboard-- Show current Elo rankings
8. Literature -- Search and add papers

{State-based recommendation from meta-review, if available}
```

### State-Aware Suggestions

The menu should guide the user through the natural research progression:
- **No hypotheses**: suggest Generate
- **Unreviewed hypotheses exist**: suggest Review
- **Reviewed but no tournament**: suggest Tournament
- **Tournament data but no meta-review**: suggest Meta-review
- **Meta-review exists**: suggest Generate (with feedback) or Evolve (top performers)
- **5+ hypotheses**: suggest Landscape for clustering analysis

## Handoff Processing

When a child skill returns a CO-SCIENTIST HANDOFF block:

1. **Parse** the structured block (status, summary, outputs, quality gates, recommendations, learnings).
2. **Display** summary and quality gate results to user.
3. **Quality gate triage**:
   - All gates pass: report success, show recommendation for next step.
   - Any gate fails: highlight the failure, suggest remediation before proceeding.
4. **Learnings**: if the skill reported learnings, surface them and ask if they should be captured as observations.
5. **Recommendation**: present the skill's `next_suggested` as the default menu selection.
6. **Return to menu** with updated state.

## Self-Improving Loop

Before invoking any sub-skill, check `_research/meta-reviews/` for the latest meta-review note. If one exists:
- For /generate: include "Recommendations for Generation" content.
- For /evolve: include "Recommendations for Evolution" content.
- For /review mode 6: the review skill handles this internally.

This feedback injection is what makes each cycle of the loop better than the last.

## Quality Gates

### Gate 1: Goal Exists
A research goal must be active before any co-scientist operation. If no goal: prompt user to create one.

### Gate 2: Leaderboard Sync
Before displaying the leaderboard, verify `_index.md` Elo values match hypothesis frontmatter. If mismatch: rebuild leaderboard from frontmatter (source of truth).

### Gate 3: Handoff Integrity
When parsing a child skill's handoff, verify all required fields are present (skill, goal, date, status, summary). Missing fields: warn user but continue.

## Error Handling

| Error | Action |
|-------|--------|
| No research goals exist | Guide user through goal creation workflow |
| Goal slug not found | List available goals, ask user to select or create new |
| `_index.md` missing | Create it (see State Initialization). This is recovery, not an error |
| Child skill handoff missing | Warn user that structured result was not returned. Ask for manual status update |
| Child skill `status: failed` | Display failure reason. Suggest remediation. Do not auto-retry |
| Child skill `status: partial` | Display what completed and what was skipped. Ask user how to proceed |

## Critical Constraints

- **The user drives the loop -- never auto-advance** to the next stage without user selection.
- **Always present results and wait for approval** before proceeding to the next operation.
- **Record which step was last completed** so the user can resume across sessions.
- **Pass `--handoff` to every child skill invocation** for structured result parsing.
- **Never skip the meta-review feedback injection** when a meta-review exists.
- **Keep the menu state-aware** -- suggest the most valuable next action, not just a static list.

## Skill Graph

Invoked by: user (entry point)
Invokes: /generate, /review, /tournament, /evolve, /landscape, /meta-review, /literature
Reads: _research/goals/, _research/hypotheses/_index.md, _research/meta-reviews/
Writes: _research/goals/, _research/hypotheses/_index.md (initialization only)
