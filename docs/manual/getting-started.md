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

## Before Your First Session

### Where EngramR lives

EngramR is a standalone knowledge vault, it should live in a separate directory from your existing projects. Clone it wherever is convenient, working through EngramR is encouraged for project development, especially in planning phases.

```bash
git clone https://github.com/achousal/EngramR.git ~/EngramR
cd ~/EngramR
claude
```

Your existing project structure is untouched. When you run `/onboard ~/projects/MyLab/`, EngramR scans that directory and creates reference notes inside the vault -- nothing in your lab directory is written or moved. It creates a symlink at `_dev/{project-tag}` pointing to your project, then transclude your existing `CLAUDE.md` into the project note. Your files stay where they are; the vault references them.

#### Minimal project `CLAUDE.md`

This is the primary source the scan uses for project description, research question, data details, HPC paths, and conventions. Projects without one still onboard, but the project note will be shallower and the in-vault embed will not resolve until one is created.

If your projects do not have one yet, a few lines is enough for a good onboard:

```markdown
# Project Name

## Overview
What this project studies, what question it is trying to answer, and what the goal is.

## Data / Materials
What you are working with -- samples, datasets, cohorts, specimens, records.
Include approximate size (N), type, and where it lives (path, biobank, repository, etc.).

## Methods
How you study it -- lab techniques, instruments, computational tools, analysis approaches.
Whatever is most relevant to the project's identity.
```

You do not need to fill every section -- even just an Overview paragraph gives the scan enough to populate the project note and research goals correctly.
### What to bring to `/onboard`

- **The path to your lab directory** (e.g., `~/projects/MyLab/`). The scan reads your existing project folders.
- **Research directions.** Even informal descriptions are fine -- the interview will refine them into structured goals.
### What to bring to `/init` (after `/onboard`)

- **3-5 key papers per research area.** PDFs or markdown preferred. These seed your first knowledge claims. Start with papers that represent your current thinking, not an aspirational reading list.

### What to bring to `/literature` (after `/init`)

- **API keys for literature databases.** `/onboard` walks you through this in Turn 3 -- if you skipped it, run `/literature --setup` before your first search. All sources require free registration only:
  - PubMed/NCBI: register at ncbi.nlm.nih.gov and get an API key from your account settings
  - Semantic Scholar: free API key at semanticscholar.org
  - OpenAlex: free, just requires an email

  Keys go in `_code/.env` (gitignored -- never committed). The `/onboard` and `/literature --setup` flows handle this interactively.

### What to bring to `/generate` and `/research` (hypothesis generation)

Nothing special. Both skills work from vault state -- your research goals, your claims, and your literature notes. The richer those are, the better the hypotheses. Running `/literature` before `/research` meaningfully improves output quality.

### What not to do

- **Do not dump your entire reference library into `inbox/`** through it, we processes material thoroughly. To cover ground, process through /literature for abstract centered scans. One well-processed paper is worth ten unprocessed ones. Add more as you work. 

### The right mental model

EngramR is a processing system. Its value comes from the rate at which raw material becomes connected knowledge (there isn't much benefit to storing 10 papers with overlapping claims). Start with a focused set, process it thoroughly, and expand from there.

---

## Your First Session

### Step 1: Onboard your lab

Run `/onboard`. Claude will ask you about your lab, your projects, your data, and your research goals -- a short interview of a few turns. Based on your answers it creates the project structure, data inventory, and research goals that everything else runs on. You review what it generates and correct anything before it is saved.

### Step 2: Seed your knowledge graph

Run `/init`. Claude walks you through creating your first claim together (a short demo), then generates a set of foundational claims for your research area -- orientation, methodology, known confounders, and assumption inversions. You review them in groups before they are added to the graph.

After these two steps you have a working knowledge environment grounded in your actual research context.

### Step 3: Build your literature base

Add your 3-5 foundational papers to `inbox/`, then process them:

```
/seed --all
/ralph
```

Then run `/literature` to automatically search PubMed, Semantic Scholar, and OpenAlex using your research goals as queries. Results are saved as structured literature notes and queued for processing. Run `/ralph` again to extract claims from them.

This step requires API keys -- see "What to bring to `/literature`" above, or follow the prompts if you skipped setup during `/onboard`.

### Step 4: Generate hypotheses

Run `/research` to start the co-scientist loop. It will recommend which step to take first based on your vault state -- typically `/generate` to produce initial hypotheses, then `/review`, then `/tournament` to rank them.

```
/research
```

You do not need to prepare anything for this step. The system reads your goals, claims, and literature notes and generates hypotheses grounded in that evidence.

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

A few entry points depending on what the session is for:

| Use case                           | Entry point                                                                                                                                                 |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Quick orientation                  | `/next` -- evaluates task queue, inbox pressure, pending observations, and active goals; recommends the single highest-value action                         |
| Processing new papers or notes     | Drop files in `inbox/`, run `/seed --all`, then `/ralph` -- each item moves through extract -> reflect -> reweave -> verify with isolated context per phase |
| Expanding literature coverage      | `/literature [topic]` -- searches PubMed, Semantic Scholar, and OpenAlex using your research goals; results are queued for `/ralph`                         |
| Generating or advancing hypotheses | `/research` -- steps through the co-scientist loop (generate, review, tournament, meta-review) and recommends which step fits your current hypothesis pool  |
| Scan for tensions                  | `/health` -- full integrity check for orphan claims, dangling links, schema violations, and stale content; returns a ranked fix list                        |

See [Skills Reference](skills.md) for the full command list.

### Phase 3: Persist

Before session end:
- Write any new insights as atomic claims (route through inbox/ and /reduce).
- Update relevant topic maps with new connections.
- Update self/goals.md with current threads and progress.
- The session-capture hook fires automatically and records a session summary to ops/sessions/.

---

## Your First Claim

Claims are atomic knowledge notes. Each captures exactly one insight, titled as a prose proposition. You do not create claims directly -- you bring material or ideas to Claude, and the pipeline creates them for you.

### Step 1: Bring the insight to Claude

Two common starting points:

**Option A: You have a quick insight to capture.**
Describe the idea to Claude in plain language. Claude will ask clarifying questions if needed, then route the material through `inbox/` and extract a structured claim. You do not write files or run commands -- you describe what you want to preserve.

**Option B: You have a source document to process.**
Drop the file in `inbox/` and tell Claude to process it, or run `/seed inbox/your-file.md` followed by `/ralph`. Claude reads the source, extracts every relevant claim, and creates them in `notes/` with full provenance.

In both cases, content enters through `inbox/`, not `notes/` directly. Direct writes to `notes/` skip quality gates -- this routing is a hard constraint.

### Step 2: Review what was created

After extraction, Claude shows you what it created. Each claim has this shape:

1. **The title is a prose proposition** -- a complete, falsifiable thought a reader could agree or disagree with. Not a topic label.
2. **The description adds context beyond the title** -- scope, mechanism, or implication in one sentence.
3. **The body captures exactly one idea** -- if two distinct claims are bundled, they get split.

### Step 3: Connect it

Tell Claude to find connections, or run `/reflect`. Claude does three things:
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

Topic maps are navigation hubs that organize claims by topic. 

### When to Create

Use `/reflect` after processing a batch of claims -- it detects when 5+ related claims have accumulated without navigation structure and creates or updates the appropriate map.

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

The critical rule: Core Ideas entries must have context phrases.

### Taxonomy

- **Hub** -- entry point for the entire workspace. One per workspace.
- **Domain topic map** -- entry point for a research area. Links to topic-level maps.
- **Topic map** -- active workspace for a specific topic.

---

## Next Steps

- [Skills Reference](skills.md) -- full command reference for all skills.
- [Workflows](workflows.md) -- how the pipeline, maintenance, and co-scientist loops compose.
- [Configuration](configuration.md) -- how to adjust processing depth, chaining, and other dimensions.
