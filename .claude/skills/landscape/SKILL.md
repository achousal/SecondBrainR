---
name: landscape
description: "Map the hypothesis space to identify clusters, gaps, and redundancies"
version: "1.0"
generated_from: "co-scientist-v2.0"
user-invocable: true
model: sonnet
context: fork
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
  - Write
argument-hint: "[goal-slug] | --all"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- co-scientist parameters
   - `co_scientist.elo.starting`: Elo baseline for redundancy flagging (default: 1200)
   - `co_scientist.tournament.top_tier_threshold`: threshold for tier classification (default: 0.25)
   - `co_scientist.handoff.mode`: manual | suggested | automatic

2. **`_research/goals/`** -- active research goal(s)
   - Parse `project_tag` from goal frontmatter for hypothesis filtering
   - If `$ARGUMENTS` contains a goal slug, use that goal; otherwise read active goal

3. **`_research/hypotheses/`** -- all hypothesis notes for the goal
   - Parse frontmatter: id, title, elo, generation, status, tags, assumptions, research_goal
   - Skip hypotheses where `quarantine: true`

If no goals exist: emit CO-SCIENTIST HANDOFF with `status: no-data`, stop.
If goal slug not found: list available goals, ask user to pick one, or emit HANDOFF `status: failed`.

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` is a goal slug -> landscape that goal only
- If `$ARGUMENTS` contains `--all` -> landscape all goals sequentially
- If `$ARGUMENTS` contains `--handoff` -> emit CO-SCIENTIST HANDOFF block at end
- If `$ARGUMENTS` is empty -> use the active research goal (most recently modified in `_research/goals/`)

**Execute these steps:**

1. Load co-scientist config from `ops/config.yaml`.
2. Identify target goal(s) from arguments or active goal.
3. Read all hypothesis notes for the goal (filter by `project_tag` if set, exclude quarantined).
4. If fewer than 2 hypotheses: report "insufficient hypotheses for landscape analysis" and emit HANDOFF `status: no-data`.
5. Analyze and cluster hypotheses by content similarity (Step 1 below).
6. Identify gaps, redundancies, and suggested directions (Steps 2-4).
7. Write landscape output to `_research/landscape/{goal-slug}.md`.
8. Update `_research/landscape.md` index with goal entry.
9. Present findings to user.
10. Run quality gates. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /landscape -- Proximity / Clustering Agent

Map the hypothesis space to identify clusters, gaps, and redundancies. Inductive gap analysis -- pattern recognition across the hypothesis space to direct /generate toward productive new areas and flag /evolve combination opportunities.

## Architecture

Implements the Proximity agent from the co-scientist system (arXiv:2502.18864). Reads hypothesis notes, performs content-based clustering, identifies structural gaps, and flags redundancies.

## Vault Paths

- Hypotheses: `_research/hypotheses/`
- Per-goal landscapes: `_research/landscape/{goal-slug}.md`
- Landscape index: `_research/landscape.md`
- Research goals: `_research/goals/`

## Code

- `_code/src/engram_r/hypothesis_parser.py` -- parse all hypothesis notes
- `_code/src/engram_r/obsidian_client.py` -- vault I/O

## Step 1: Content-Based Clustering

Cluster hypotheses by analyzing multiple content dimensions simultaneously. Do NOT cluster by tags alone.

**Clustering dimensions** (weighted):
- Shared mechanism keywords and pathway references (high weight)
- Common assumptions (high weight)
- Overlapping literature citations (medium weight)
- Similar domain keywords and tags (medium weight)
- Elo tier proximity (low weight -- informational only, not a clustering criterion)

**Cluster naming**: Each cluster gets a descriptive name reflecting its shared mechanism or theme, not a generic label.

**Minimum cluster size**: 2 hypotheses. Singletons are listed as "Unaffiliated" with a note on why they don't cluster.

## Step 2: Gap Identification

For each gap, provide:
- Description of the missing research area
- Which existing clusters it sits between (if applicable)
- Why it matters for the research goal
- Specific prompt for /generate to fill the gap

Sources of gap signal:
- Research goal sub-questions without hypothesis coverage
- Mechanism types present in literature but absent in hypotheses
- Missing connections between existing clusters
- Under-explored assumptions that could be relaxed or inverted

## Step 3: Redundancy Detection

Flag pairs of hypotheses as potentially redundant when:
- Elo ratings within 50 points AND >80% tag overlap
- Titles share >80% semantic similarity
- Core mechanisms are effectively identical despite different framing

For each redundancy pair:
- List both hypothesis IDs and titles
- Explain what overlaps
- Suggest: merge via /evolve combination mode, or differentiate by sharpening distinct claims

## Step 4: Suggested Directions

Concrete, actionable prompts for downstream skills:
- **For /generate**: Specific prompts to fill each identified gap
- **For /evolve combination mode**: Specific pairs worth merging
- **For /evolve simplification mode**: Over-complex hypotheses that could benefit from distillation

## Landscape Output Format

Write to `_research/landscape/{goal-slug}.md`:

```yaml
---
description: "Hypothesis landscape for {goal title}"
type: "landscape"
research_goal: "[[{goal-slug}]]"
hypothesis_count: {N}
cluster_count: {N}
gap_count: {N}
redundancy_count: {N}
created: "{YYYY-MM-DD}"
---
```

### Sections

```markdown
# Landscape: {goal title}

Generated: {YYYY-MM-DD} | Hypotheses analyzed: {N}

## Clusters

### {Cluster Name}
**Members**: [[hyp-id-1]], [[hyp-id-2]], ...
**Common theme**: {description}
**Average Elo**: {N}
**Distinguishing feature**: {what makes this cluster distinct}

## Gaps
- {Gap description} -- suggested /generate prompt: "{prompt}"

## Redundancies
- [[hyp-id-A]] <-> [[hyp-id-B]] -- {overlap description}. Suggest: /evolve --mode 2 --combine {id-A} {id-B}

## Suggested Directions
- /generate: {specific prompt}
- /evolve: {specific action}
```

Update `_research/landscape.md` index table with:
```
| Goal | Clusters | Gaps | Redundancies | Date |
```

## Quality Gates

### Gate 1: Minimum Clusters
If 4+ hypotheses exist, at least 2 clusters must be identified. A single mega-cluster indicates insufficient content analysis. Re-examine mechanism differences.

### Gate 2: Gap Coverage
If 6+ hypotheses exist, at least 1 gap must be identified. A mature hypothesis space with zero gaps is suspicious -- check research goal sub-questions for uncovered territory.

### Gate 3: Redundancy Flagging
For every pair where Elo is within 50 AND tag overlap >80%, a redundancy entry must exist. Automated check: compare all hypothesis pairs matching criteria.

### Gate 4: Output Written
Landscape file must be written to `_research/landscape/{goal-slug}.md` before HANDOFF. Verify file exists after write.

## Error Handling

| Error | Action |
|-------|--------|
| No active research goal | List goals from `_research/goals/`, ask user to select. If `--handoff`: HANDOFF `status: failed`, summary: "no active research goal" |
| Goal slug not found | List available goals with slugs. If `--handoff`: HANDOFF `status: failed` |
| Empty hypotheses directory | HANDOFF `status: no-data`, summary: "no hypotheses found for goal" |
| Fewer than 2 hypotheses | Report count, suggest running /generate first. HANDOFF `status: no-data` |
| All hypotheses quarantined | HANDOFF `status: no-data`, summary: "all hypotheses quarantined" |
| Write failure on landscape file | Report error, present landscape in conversation. HANDOFF `status: partial` |

## Critical Constraints

- **Never modify hypothesis files.** Landscape is read-only over the hypothesis space.
- **Always include Suggested Directions.** A landscape without actionable next steps is incomplete.
- **Always use content-based clustering**, not just tags. Tags are one signal among many.
- **Always filter by `project_tag`** when the goal has one set.
- **Always exclude quarantined hypotheses** from analysis.
- **Present findings to user before saving** (unless `--handoff` mode).

## CO-SCIENTIST HANDOFF

When `--handoff` is present in `$ARGUMENTS`, emit after all work:

```
CO-SCIENTIST HANDOFF
skill: landscape
goal: [[{goal-slug}]]
date: {YYYY-MM-DD}
status: {complete | partial | failed | no-data}
summary: {one sentence}

outputs:
  - _research/landscape/{goal-slug}.md -- landscape analysis ({N} clusters, {N} gaps, {N} redundancies)

quality_gate_results:
  - gate: minimum-clusters -- {pass | fail: reason}
  - gate: gap-coverage -- {pass | fail: reason}
  - gate: redundancy-flagging -- {pass | fail: reason}
  - gate: output-written -- {pass | fail: reason}

recommendations:
  next_suggested: {generate | evolve | tournament} -- {why}

learnings:
  - {observation about hypothesis space worth noting} | NONE
```

## Skill Graph

Invoked by: /research, user (standalone)
Invokes: (none -- leaf agent)
Reads: _research/hypotheses/, _research/goals/
Writes: _research/landscape/, _research/landscape.md
