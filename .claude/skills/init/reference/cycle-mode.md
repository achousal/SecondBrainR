# Cycle Mode Instructions

Reference file for /init --cycle mode. Extracted from init SKILL.md Cycle Mode (Steps C0-C6).

---

## Step C0: Read Cycle Context

Read the following files to build full cycle context:

1. `self/goals.md` -- current threads, completed work, active goals
2. All meta-reviews:
   ```bash
   ls -t _research/meta-reviews/*.md 2>/dev/null
   ```
   Read the 3 most recent meta-reviews.
3. Execution tracker:
   ```bash
   ls _research/experiments/execution-tracker.md 2>/dev/null
   ```
4. Daemon inbox:
   ```bash
   ls ops/daemon-inbox.md 2>/dev/null
   ```
5. Reminders:
   ```bash
   ls ops/reminders.md 2>/dev/null
   ```
6. Existing cycle summaries:
   ```bash
   ls _research/cycles/cycle-*.md 2>/dev/null
   ```

Determine CYCLE_NUMBER: count existing cycle summaries + 1. If no cycles directory exists, this is Cycle 1.

If no meta-reviews exist, warn:

```
No meta-reviews found. Cycle summaries are most valuable when preceded by meta-review synthesis.
Consider running /meta-review first.

Continue with limited cycle summary? (Y/n)
```

---

## Step C1: Generate Cycle Summary

Create `_research/cycles/` if it does not exist:
```bash
mkdir -p _research/cycles
```

Build a cycle summary note using the template at `_code/templates/cycle-summary.md`.

### C1a. Cycle Dates

Collect date range from user: YYYY-MM-DD to YYYY-MM-DD

### C1b. Compile Per-Program Status

For each active goal in `self/goals.md`:

- Read tournament standings from `_research/hypotheses/_index.md` (filter by goal)
- Read experiment results from `_research/experiments/` (filter by goal)
- Extract key findings from the latest meta-review for this goal
- Determine what carries forward vs. what is resolved

### C1c. Identify Persistent Blind Spots

Cross-reference meta-review recommendations across all programs. Patterns that recurred in multiple meta-reviews are persistent blind spots:

- Gatekeeper hypotheses generated late (positive-first bias)
- Methodological requirements independently rediscovered
- Cross-program awareness missing
- Confounders treated as limitations not design elements

### C1d. Write Cycle Summary

Present the draft cycle summary to user for review/edit.

Write to: `_research/cycles/cycle-{N}-summary.md`

**Frontmatter:**
```yaml
---
type: cycle-summary
cycle: {N}
programs: [{list of goal wiki-links}]
date_range: "{start} to {end}"
status: completed
created: {today YYYY-MM-DD}
---
```

---

## Step C2: Goals Transition

For each active research goal, determine status for the next cycle:

1. **Continue** -- "Active research continues with same scope"
2. **Pivot** -- "Scope or approach is changing (describe how)"
3. **Complete** -- "This goal has been achieved or is no longer pursued"
4. **New sub-goal** -- "Spawning a new sub-goal from this one"

Based on responses:
- **Continue:** no changes to goal file, update `self/goals.md` status line
- **Pivot:** update goal file with new scope, add pivot note to goals.md
- **Complete:** set goal status to `completed` in frontmatter, move from Active to Completed in goals.md
- **New sub-goal:** create new goal file via `/research`, link to parent

---

## Step C3: Refresh Assumption Inversions

The key cycle-transition action: re-run inversions with accumulated cycle knowledge.

### C3a. Collect Existing Inversions

Search for inversion claims created by previous /init runs or that contain falsification language:

```bash
grep -rl "confidence: speculative" notes/*.md 2>/dev/null | head -30
```

Read each to identify those that are assumption inversions (linked to orientation claims).

### C3b. Re-evaluate with Cycle Knowledge

For each existing inversion, check if cycle evidence has:
1. **Confirmed the inversion** -- the parent claim was falsified (update parent claim confidence)
2. **Refuted the inversion** -- evidence supports the parent claim (update inversion confidence to lower)
3. **Neither** -- inversion remains open

Present each to user with cycle evidence summary. Ask for disposition.

### C3c. Generate New Inversions

Based on cycle meta-review blind spots and new knowledge, generate fresh inversions for claims that were NOT previously inverted:

For each active goal, read its top-ranked hypotheses. For each top hypothesis, determine:

```
Hypothesis: "{hypothesis title}" (Elo: {score})

Given what we learned this cycle, what is the strongest argument AGAINST this hypothesis that we have not yet addressed?
```

Generate inversion claims following the Phase 4 format from seed mode.

---

## Step C4: Daemon Reconciliation (optional)

If `ops/daemon-inbox.md` exists and is non-empty:

Read daemon-inbox recommendations. Compare against meta-review recommendations and cycle summary blind spots.

Present discrepancies to user:

```
Daemon recommends: {action}
Meta-review recommends: {action}
Conflict: {description}

Which takes priority?
```

Options:
1. **Follow meta-review** -- "Human-reviewed synthesis takes precedence"
2. **Follow daemon** -- "Automated analysis identified something the review missed"
3. **Reconcile** -- "Merge both perspectives (explain how)"

If user wants to update daemon config:
- Read `ops/daemon-config.yaml`
- Make the requested changes
- Present diff for approval before writing

---

## Step C5: Update Reminders

Read `ops/reminders.md`. Based on cycle transition:

1. **Close completed reminders** -- mark items achieved during this cycle as done
2. **Add new reminders** from cycle summary carry-forward items
3. **Update deadlines** for items that shifted

Present changes to user before writing.

---

## Step C6: Cycle Transition Summary

Output:

```
=== /init --cycle Summary (Cycle {N}) ===

Date range: {start} to {end}
Programs: {list}

Cycle summary: _research/cycles/cycle-{N}-summary.md

Goal transitions:
{list: goal -> status}

Inversions:
  Existing reviewed: {count}
  Confirmed (parent falsified): {count}
  Refuted (parent supported): {count}
  Open: {count}
  New inversions created: {count}

Daemon reconciliation: {done/skipped/not needed}

Reminders updated: {count changes}

Claims created this session: {count}

Suggested next actions:
- /generate -- new hypotheses informed by cycle findings
- /literature -- search for papers on blind spot topics
- /init {goal} -- seed any newly created goals
=== End Summary ===
```

---

## Handoff Mode

If `--handoff` was included in arguments, append RALPH HANDOFF block after the summary:

```
=== RALPH HANDOFF: init ===
Target: {arguments}
Mode: {seed | cycle}

Work Done:
- {summary of actions taken}

Files Modified:
- {list of all files created/modified with action: CREATE or EDIT}

Claims Created:
- {list of claim titles}

Learnings:
- [Friction]: {any friction encountered} | NONE
- [Surprise]: {any surprises} | NONE
- [Methodology]: {any methodology insights} | NONE

Queue Updates:
- Suggest: {follow-up actions}
=== END HANDOFF ===
```
