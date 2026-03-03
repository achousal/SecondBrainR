---
name: init-wire
description: "Wire claims into the knowledge graph -- topic maps, project bridges, goal updates. Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
argument-hint: "{data-file-path} -- path to temp file with approved claims list"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Wire approved claims into the knowledge graph. This is a computational sub-skill invoked by the /init orchestrator after the user has reviewed and approved claims.

### Step 1: Read Input

Read the approved claims data from $ARGUMENTS. It contains:
- CLAIMS_CREATED: full list of approved claims with roles and filenames
- SELECTED_GOALS: goals that were seeded
- Any claims the user rejected or modified during review

### Step 2: Read Reference Instructions

```
Read .claude/skills/init/reference/graph-wiring.md
```

### Step 3: Phase Completion Gate (5a)

Count claims by role and verify:
- ORIENTATION_COUNT > 0
- At least one of METHODOLOGY_COUNT, CONFOUNDER_COUNT, INVERSION_COUNT > 0

If hard gate fails, output error and stop.

### Step 4: Topic Map Updates (5b)

For each topic map referenced in the claims:
1. Check if the topic map file exists
2. If exists: read and append new claims to appropriate role sections
3. If not exists and 5+ claims reference it: create new topic map
4. If not exists and <5 claims: redirect claims to existing topic maps

### Step 5: Project-to-Claim Bridges (5c)

For each goal:
1. Find matching projects via lab index files
2. Check idempotency (existing linked_goals)
3. Update project frontmatter with goal links

### Step 6: Goal File Updates (5d)

For each seeded goal:
1. Add/update `seeding_status` block in goal frontmatter
2. Update `self/goals.md` with seeding thread entry

### Step 7: Output Wiring Summary

```markdown
## WIRING SUMMARY

### Phase Completion
- Orientation: {count}
- Methodology: {count}
- Confounders: {count}
- Data realities: {count}
- Inversions: {count}
- Total: {count}

### Topic Maps
- Created: {count} ({list})
- Updated: {count} ({list})

### Project Bridges
- Wired: {count} ({project -> goal pairs})

### Goal Updates
- Seeding status set: {list of goals}
- goals.md updated: {yes/no}

### Graph Health
- Orphan claims: {count -- should be 0}
- Dangling links: {count -- should be 0}

### Suggested Next Actions
- /literature -- search for papers supporting or challenging these claims
- /generate -- produce hypotheses building on this foundation
- /reflect -- find connections between new and existing claims
```
