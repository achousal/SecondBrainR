# Graph Wiring Instructions

Reference file for the init-wire sub-skill. Extracted from init SKILL.md Phase 5.

---

## Phase 5: Graph Wiring and Summary

### 5a. Phase Completion Gate

Count claims in CLAIMS_CREATED by role:
- ORIENTATION_COUNT = claims with `role: orientation` (from Phase 2)
- METHODOLOGY_COUNT = claims with `role: methodology` (from Phase 3a)
- CONFOUNDER_COUNT = claims with `role: confounder` (from Phase 3b)
- DATA_REALITY_COUNT = claims with `role: data-reality` (from Phase 3c)
- INVERSION_COUNT = claims with `role: inversion` (from Phase 4)

**Hard gate -- if METHODOLOGY_COUNT == 0 AND CONFOUNDER_COUNT == 0 AND INVERSION_COUNT == 0:**

```
ERROR: Phases 3 and 4 did not execute. The knowledge graph requires
methodology, confounder, and inversion claims alongside orientation claims.

Current counts:
  Orientation:    {ORIENTATION_COUNT}
  Methodology:    0
  Confounders:    0
  Data realities: {DATA_REALITY_COUNT}
  Inversions:     0

This is NOT optional. Return to Phase 3 and execute it now.
Do NOT produce a summary report until all phases have run.
```

Return to Phase 3 and execute. Do NOT proceed to 5b.

**Soft gate -- if total claims < 6:**

```
Note: Only {N} claims were created. A well-seeded knowledge graph typically has at least 6 foundation claims.

Consider running /init again with additional goals, or use /seed + /reduce to add literature-derived claims.
```

### 5b. Topic Map Updates

For each topic map referenced in the created claims:

1. Check if the topic map exists: `ls "notes/{topic-map-name}.md" 2>/dev/null`
2. If it exists, read it and append new claims to the appropriate role section. Group claims by their `role` field:
   - `role: orientation` -> `## Core Ideas (Orientation)` section
   - `role: methodology` -> `## Methodology` section
   - `role: confounder` -> `## Confounders` section
   - `role: data-reality` -> `## Data Realities` section (create if not present)
   - `role: inversion` -> `## Inversions` section (create if not present)

   Format for each entry:
   ```
   - [[{claim title}]] -- {context phrase explaining relevance}
   ```

3. If it does NOT exist and 5+ claims reference this topic, create it using `_code/templates/topic-map.md` schema:

   ```yaml
   ---
   description: "{scope of this topic map}"
   type: moc
   created: {today YYYY-MM-DD}
   ---
   ```

   Populate with role-grouped sections:

   ```markdown
   ## Core Ideas (Orientation)
   - [[{orientation claim}]] -- {context}

   ## Methodology
   - [[{methodology claim}]] -- {context}

   ## Confounders
   - [[{confounder claim}]] -- {context}

   ## Inversions
   - [[{inversion claim}]] -- {context}

   ## Open Questions
   ```

   Only include sections that have at least one claim. The role structure makes the graph's epistemic layers visible in the artifacts themselves.

4. If fewer than 5 claims reference a nonexistent topic map, add a `Topics:` entry pointing to the most relevant existing topic map instead. Do NOT create sparse topic maps.

### 5c. Project-to-Claim Bridge

**Purpose:** Wire project files to their associated research goals, connecting the two parallel namespaces (/onboard projects and /init claims).

For each goal in SELECTED_GOALS:

1. **Identify candidate projects.** Read lab-level index files to determine which lab owns the goal:
   ```bash
   grep -rl "{goal-slug}" projects/*/_index.md 2>/dev/null
   ```

   Then list all project files under matching lab directories:
   ```bash
   ls projects/{lab-slug}/*.md 2>/dev/null
   ```

2. **Match projects to goals.** A project matches a goal if:
   - The project is in the same lab directory AND its research domain overlaps with the goal's scope (infer from project description, data types, or keywords in the project frontmatter)
   - Only wire clear matches -- do NOT guess loose connections

3. **Check idempotency.** For each matched project, read its frontmatter:
   - If `linked_goals` already contains `"[[{goal-name}]]"`, skip (already wired)
   - If `linked_goals: []`, update to `linked_goals: ["[[{goal-name}]]"]`
   - If `linked_goals` has other entries, append: add `"[[{goal-name}]]"` to the existing list
   - If no `linked_goals` field exists, add it to frontmatter

4. **Track bridges.** Store count as PROJECT_BRIDGES_CREATED for summary. Bridge writes are low-risk metadata updates (adding goal links to project frontmatter) and are auto-applied without separate user approval. The orchestrator's Phase 6 summary surfaces all bridges created, giving the user visibility after the fact.

### 5d. Update Goal Files and goals.md

**Goal frontmatter update:** For each goal in SELECTED_GOALS, read `_research/goals/{goal-slug}.md` and add or update the `seeding_status` block in its frontmatter:

```yaml
seeding_status:
  orientation: complete     # Phase 2 ran and produced claims
  methodology: complete     # Phase 3a ran -- or "pending" if skipped
  confounders: complete     # Phase 3b ran -- or "pending" if skipped
  data_realities: complete  # Phase 3c ran -- or "pending" if skipped
  inversions: complete      # Phase 4 ran -- or "pending" if skipped
```

Set each phase to `complete` if it produced at least one claim for this goal (or for shared phases like 3a, if it ran at all). Set to `pending` if the phase was skipped or produced zero claims.

**goals.md update:** Read `self/goals.md`. If not already present, add an entry under `## Active Threads`:

```
- /init seeding complete for {goal names}: {N} claims created ({M} orientation, {K} methodology, {L} confounders, {J} inversions)
```

### 5e. Summary Report

Output:

```
=== /init Seeding Summary ===

Goals seeded: {list}

Claims created: {total}
  Orientation:    {count}
  Methodology:    {count}
  Confounders:    {count}
  Data realities: {count}
  Inversions:     {count}

Topic maps created: {count}
Topic maps updated: {count}
Project bridges wired: {count}

Claims list:
{numbered list with titles, one per line}

Graph health:
- Orphan claims: {count from CLAIMS_CREATED that lack topic map links -- should be 0}
- Dangling links: {count -- should be 0}

Suggested next actions:
- /literature -- search for papers supporting or challenging these claims
- /generate -- produce hypotheses building on this foundation
- /reflect -- find connections between new and existing claims
=== End Summary ===
```
