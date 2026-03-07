---
description: "First session guide -- onboarding, session rhythm, and your first claim"
type: manual
created: 2026-02-21
---

# Getting Started

Clone the repo and open it with Claude Code:

```bash
git clone https://github.com/achousal/EngramR.git
cd EngramR
claude
```

Claude handles setup from here. You answer questions; it builds the infrastructure.

---

## Your First Session

### Step 1: Onboard your lab

Run `/onboard`. Claude will ask you about your lab, your projects, your data, and your research goals -- a short interview of a few turns. Based on your answers it creates the project structure, data inventory, and research goals that everything else runs on. You review what it generates and correct anything before it is saved.

### Step 2: Seed your knowledge graph

Run `/init`. Claude walks you through creating your first claim together (a short demo), then generates a set of foundational claims for your research area -- orientation, methodology, known confounders, and assumption inversions. You review them in groups before they are added to the graph.

After these two steps you have a working knowledge environment grounded in your actual research context.

---

## Session Rhythm: Orient - Work - Persist

Every session follows this three-phase cycle. It is enforced by hooks, not discipline. For the full session rhythm reference, see [Workflows](workflows.md).

### Phase 1: Orient

At session start, the session-orient hook fires automatically and prints:

1. **Active threads** from self/goals.md -- what you are working on.
2. **Reminders** from ops/reminders.md -- overdue time-bound commitments.
3. **Vault state** -- claim count, inbox count, observation count, tension count.
4. **Maintenance signals** -- condition-based triggers (inbox pressure, pending observations, pending tensions).

Read self/identity.md and self/methodology.md to remember who you are and how you work. This is not optional -- without it, the session starts cold.

### Phase 2: Work

Do the actual task. This is where claims are created, connections found, hypotheses generated, literature searched. The processing pipeline and co-scientist skills are your primary tools.

### Phase 3: Persist

Before session end:
- Write any new insights as atomic claims (route through inbox/ and /reduce).
- Update relevant topic maps with new connections.
- Update self/goals.md with current threads and progress.
- The session-capture hook fires automatically and records a session summary to ops/sessions/.

---

## Your First Claim

Claims are atomic knowledge notes. Each captures exactly one insight, titled as a prose proposition.

### Step 1: Route Through the Pipeline

Content enters through inbox/, not notes/ directly. This is a hard constraint -- direct writes to notes/ skip quality gates.

**Option A: Quick insight from conversation.**
Write a short markdown file to inbox/, then extract:

```bash
# Write the insight to inbox/
cat > inbox/early-warning-signals.md << 'EOF'
Increased variance in repeated measurements precedes critical transitions.
Supporting evidence from longitudinal studies and dynamical systems theory.
EOF
```

Then extract the claim:
```
/reduce inbox/early-warning-signals.md
```

**Option B: Process a full document.**
Place the source material in inbox/ and extract:

```
/reduce inbox/review-paper-on-critical-transitions.md
```

In both cases, /reduce reads the source, extracts claims, and creates them in notes/ with full provenance.

### Step 2: Check the Output

After creation, verify the claim meets quality standards:

1. **Title as claim** -- Does the title work as prose when linked? "Since [[increased variance in repeated measurements precedes critical transitions]]" reads naturally.
2. **Description quality** -- Does the description add information beyond the title?
3. **Specificity** -- Could someone disagree with this claim? If not, it is too vague.

### Step 3: Connect

Run /reflect to find connections between the new claim and existing knowledge:

```
/reflect
```

This does three things:
- **Forward connections** -- what existing claims relate to this new one?
- **Backward connections** -- what older claims need updating now that this exists?
- **Topic map updates** -- adds the claim to at least one topic map.

---

## Understanding Claim Structure

Every claim in notes/ follows the template in _code/templates/claim-note.md:

```yaml
---
description: "One sentence adding context beyond the title (~150 chars)"
type: claim
source: "[[source-note]]"
confidence: preliminary
created: 2026-02-21
---
```

### Required Fields

| Field | Constraint |
|-------|-----------|
| description | ~150 chars. Must add information beyond the title -- scope, mechanism, or implication. |

### Optional Fields

| Field | Values | Purpose |
|-------|--------|---------|
| type | claim, evidence, methodology, contradiction, pattern, question | Queryable categorization |
| source | Wiki link to inbox source | Provenance chain |
| confidence | established, supported, preliminary, speculative | Evidence strength |
| created | ISO date | Temporal ordering |

### Body Structure

```markdown
# {prose-as-title}

{Content: the argument supporting this claim. Show reasoning, cite evidence,
link to related claims inline using [[wiki links]].}

---

Relevant Claims:
- [[related claim]] -- relationship context

Topics:
- [[relevant-topic-map]]
```

---

## Understanding Topic Maps

Topic maps are navigation hubs that organize claims by topic. They are not folders -- they are attention managers.

### When to Create

Create a topic map when 5+ related claims accumulate without navigation structure. Do not create one for fewer than 5 claims.

### Structure

```markdown
# topic-name

Brief orientation -- 2-3 sentences.

## Core Ideas
- [[claim]] -- context explaining why this matters here

## Tensions
Unresolved conflicts.

## Open Questions
Gaps, unexplored directions.
```

The critical rule: Core Ideas entries must have context phrases. A bare link list is an address book, not a map.

### Taxonomy

- **Hub** -- entry point for the entire workspace. One per workspace.
- **Domain topic map** -- entry point for a research area. Links to topic-level maps.
- **Topic map** -- active workspace for a specific topic.

---

## Quick Reference: First Session Checklist

1. Read self/identity.md, self/methodology.md, self/goals.md.
2. Check orient output for inbox pressure or maintenance signals.
3. Create one claim via /reduce (write a quick insight to inbox/ first if needed).
4. Run /reflect to connect the claim.
5. Run /verify on the claim to check quality.
6. Update self/goals.md with your current thread.
7. Session-capture hook fires automatically at session end.

---

## Next Steps

- [Skills Reference](skills.md) -- full command reference for all skills.
- [Workflows](workflows.md) -- how the pipeline, maintenance, and co-scientist loops compose.
- [Configuration](configuration.md) -- how to adjust processing depth, chaining, and other dimensions.
