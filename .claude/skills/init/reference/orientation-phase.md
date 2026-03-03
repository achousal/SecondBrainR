# Orientation Phase Instructions

Reference file for the init-generate sub-skill. Extracted from init SKILL.md Phase 2.

---

## Phase 2: Domain Orientation (per goal)

**Purpose:** Establish the 3-5 core questions each research goal addresses. These become the structural foundation that all later claims connect to.

For each goal in SELECTED_GOALS:

### 2a. Read goal context

Read the goal file from `_research/goals/{goal-slug}.md`. Read existing hypotheses for this goal:

```bash
grep -l "{goal-slug}" _research/hypotheses/*.md 2>/dev/null | head -20
```

Read the latest meta-review if available:

```bash
ls -t _research/meta-reviews/*{goal-slug-fragment}*.md 2>/dev/null | head -1
```

### 2b. Core Questions

The orchestrator collects 3-5 core scientific questions from the user per goal. These are passed as input to this sub-skill.

### 2c. Demo Claim

The orchestrator handles the demo claim walkthrough interactively. If a demo claim was created, it is passed as input and counts as the first orientation claim for this goal. The sub-skill generates orientation claims for the REMAINING core questions only (excluding the one used for the demo claim).

### 2d. Generate Orientation Claims

For each remaining core question (excluding any addressed by the demo claim), generate ONE orientation claim that frames the question as a testable proposition. These are the structural anchors for the graph.

**Claim construction rules:**
- Title: prose-as-title, a complete proposition framing the question (e.g., "early intervention reduces long-term outcome severity in high-risk populations")
- Title must NOT contain: `/ \ : * ? " < > | . + [ ] ( ) { } ^`
- Use `-` instead of `/` in compound terms: `input-output`, `pre-post`, `v2-0`
- Description: one sentence adding scope, mechanism, or implication beyond the title (max 200 chars)
- Body: 2-4 sentences explaining the scientific reasoning, with inline wiki-links to any relevant existing claims or hypotheses

**YAML frontmatter:**
```yaml
---
description: "{context beyond title}"
type: claim
role: orientation
confidence: preliminary
source_class: synthesis
verified_by: agent
created: {today YYYY-MM-DD}
---
```

**Body structure:**
```markdown
{2-4 sentence argument with inline [[wiki-links]] to relevant existing claims or hypotheses.}

---

Topics:
- [[{relevant-topic-map}]]
```

### 2e. Create Orientation Claims

For each orientation claim:

1. Sanitize title for filename: lowercase, replace spaces with `-`, remove forbidden chars
2. Verify wiki-link targets exist:
   ```bash
   ls "notes/{target}.md" 2>/dev/null
   ```
   Remove links to nonexistent targets. Do NOT create dangling links.
3. Construct full file content (YAML frontmatter + body). Add to PENDING_CLAIMS list. Do NOT write to disk.
4. Add to CLAIMS_CREATED tracking list

Store orientation claims as ORIENTATION_CLAIMS (title list) for Phase 3 and 4 reference.

**PHASE TRACKING:** Set PHASE_2_COMPLETE = true. The following phases are MANDATORY:
- Phase 3: Methodology + Confounders + Data Realities (uses ORIENTATION_CLAIMS as input)
- Phase 4: Assumption Inversions (uses ORIENTATION_CLAIMS as input)
- Phase 5: Graph Wiring + Summary (verifies all phases completed)

Skipping to Phase 5 without completing Phase 3 and Phase 4 is a SKILL EXECUTION ERROR. The graph MUST contain methodology, confounder, and inversion claims alongside orientation claims. Orientation-only seeding produces a graph that affirms without questioning -- this violates the vault's falsificationist epistemic stance.
