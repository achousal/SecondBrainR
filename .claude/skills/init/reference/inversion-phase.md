# Inversion Phase Instructions

Reference file for the init-generate sub-skill. Extracted from init SKILL.md Phase 4.

---

## Phase 4: Assumption Inversions (per goal)

**Purpose:** For each orientation claim from Phase 2, generate an explicit inversion -- "what would convince you this is wrong?" This builds falsification thinking into the graph from day one.

For each goal in SELECTED_GOALS, and for each orientation claim created for that goal:

### 4a. Generate Inversion

For each orientation claim, determine what evidence, result, or observation would falsify it. Use the user's input if provided, or generate based on the claim's logic.

### 4b. Create Inversion Claim

Generate a claim that articulates the falsification condition:

```yaml
---
description: "{what the falsification scenario implies}"
type: claim
role: inversion
confidence: speculative
source_class: synthesis
verified_by: agent
created: {today YYYY-MM-DD}
---
```

Title pattern: a proposition that, if true, falsifies the parent claim.
Example: If orientation is "increased measurement variance predicts system failure before observable symptoms", the inversion might be "measurement variance increases reflect instrument degradation rather than meaningful change in the system under study".

Body: 2-3 sentences explaining how this inversion would be tested and what it would mean for the research program. MUST include an inline wiki-link to the parent orientation claim:

```markdown
This inversion challenges [[{parent orientation claim}]] by proposing...

If true, this would require {consequence for the research program}.

---

Topics:
- [[{relevant-topic-map}]]
```

### 4c. Collect Inversions

Follow the same creation procedure:
1. Sanitize title for filename
2. Verify wiki-link targets exist (the parent orientation claim MUST exist since we just created it)
3. Construct full file content. Add to PENDING_CLAIMS list. Do NOT write to disk.
4. Add to CLAIMS_CREATED list
