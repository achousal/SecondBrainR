---
name: generate
description: "Produce novel, literature-grounded hypotheses for a research goal"
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
argument-hint: "[mode: 1-4] [--count N] [--goal slug]"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- co-scientist parameters
   - `co_scientist.default_generation_count`: how many hypotheses to generate (default: 3)
   - `co_scientist.elo.starting`: initial Elo for new hypotheses (default: 1200)
   - `co_scientist.handoff.mode`: manual | suggested | automatic
   - `research.primary`, `research.fallback`: search backends for mode 1

2. **`_research/goals/`** -- active research goal
   - Parse `project_tag` from goal frontmatter for tag inheritance
   - If `--goal [slug]` provided, use that goal; otherwise read active goal
   - If no active goal: HANDOFF `status: failed`, stop

3. **Dynamic context injection** (read inside Step 0, keep in working memory):

Latest meta-review feedback (if available):
!`ls -t "$VAULT_ROOT/_research/meta-reviews/"*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "No meta-reviews yet."`

Current landscape gaps (if available):
!`ls -t "$VAULT_ROOT/_research/landscape/"*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "No landscape analysis yet."`

4. **`_research/hypotheses/`** -- existing hypothesis IDs and titles
   - Parse all IDs to ensure uniqueness of new IDs
   - Parse titles for novelty checking

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` contains a digit 1-4 -> use that generation mode
- If `$ARGUMENTS` contains `--count N` -> generate N hypotheses (else use `co_scientist.default_generation_count`)
- If `$ARGUMENTS` contains `--goal [slug]` -> scope to that research goal
- If `$ARGUMENTS` contains `--handoff` -> emit CO-SCIENTIST HANDOFF block at end
- If no mode specified -> present mode menu to user

**Execute these steps:**

1. Load co-scientist config from `ops/config.yaml`.
2. Read active research goal. If none: ask user or HANDOFF `status: failed`.
3. Read meta-review feedback (if exists) -- inject into generation prompt.
4. Read landscape gaps (if exists) -- inject into generation prompt for modes 1 and 4.
5. Read existing hypothesis IDs and titles for duplicate/novelty checking.
6. If no mode specified: present mode menu, ask user to select.
7. Generate N hypotheses according to selected mode (see Generation Modes below).
8. For each hypothesis: run quality gates, present to user for approval.
9. Save approved hypotheses to `_research/hypotheses/hyp-{YYYYMMDD}-{NNN}.md`.
10. Update `_research/hypotheses/_index.md`.
11. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /generate -- Hypothesis Generation Agent

Produce novel, literature-grounded hypotheses for a research goal. Abductive inference -- generating the best explanatory hypotheses from available evidence, filling gaps identified by /landscape and incorporating feedback from /meta-review.

## Architecture

Implements the Generation agent from the co-scientist system (arXiv:2502.18864). Supports 4 generation modes, each targeting a different creative strategy.

## Vault Paths

- Output: `_research/hypotheses/` (new hypothesis notes)
- Research goals: `_research/goals/`
- Meta-reviews: `_research/meta-reviews/`
- Landscape: `_research/landscape/`
- Existing hypotheses: `_research/hypotheses/`

## Code

- `_code/src/engram_r/note_builder.py` -- `build_hypothesis_note()`
- `_code/src/engram_r/hypothesis_parser.py` -- `build_hypothesis_frontmatter()`
- `_code/src/engram_r/search_interface.py` -- unified search interface for literature mode
- `_code/src/engram_r/obsidian_client.py` -- vault I/O

## Generation Modes

### Mode 1: Literature Synthesis
- Search configured literature backends for papers relevant to the research goal.
- Identify gaps, contradictions, or unexplored connections in the literature.
- Propose hypotheses that address these gaps.
- Ground each hypothesis with specific citations (PMIDs, arXiv IDs, DOIs).
- **Requires**: at least one search source available (check via `search_interface.py`).

### Mode 2: Self-Play Debate
- Simulate 2-3 expert perspectives (e.g., experimentalist, theorist, statistician).
- Each expert proposes and critiques hypotheses from their viewpoint.
- Extract the most promising novel ideas from the debate.
- **Does not require** external search -- uses existing vault knowledge.

### Mode 3: Assumption-Based Reasoning
- Take an existing hypothesis (user selects which).
- Enumerate its key assumptions.
- For each assumption: generate an alternative hypothesis where that assumption is relaxed, inverted, or replaced.
- **Requires**: at least one existing hypothesis to reason from.

### Mode 4: Research Expansion
- Read meta-review feedback and existing top hypotheses.
- Identify under-explored regions of the hypothesis space.
- Generate hypotheses specifically targeting those gaps.
- Use the landscape map if available.
- **Best after**: at least one /landscape and one /meta-review have been run.

## Project Scoping

If the active research goal has a `project_tag` field set, inherit it into generated hypothesis tags. This enables filtering hypotheses by project across the vault.

## Hypothesis Format

Each hypothesis note must include:

**Frontmatter:**
```yaml
---
type: "hypothesis"
title: "{hypothesis title}"
id: "hyp-{YYYYMMDD}-{NNN}"
status: "proposed"
elo: 1200
generation: 1
research_goal: "[[{goal-slug}]]"
tags: [{domain tags}, {project_tag if set}]
created: "{YYYY-MM-DD}"
---
```

**Sections** (all required):
- **Statement** -- the hypothesis in one clear paragraph
- **Mechanism** -- proposed causal chain or explanatory model
- **Literature Grounding** -- citations with source identifiers
- **Testable Predictions** -- minimum 2, each specific and falsifiable
- **Proposed Experiments** -- how to test the predictions
- **Assumptions** -- explicit list of what the hypothesis takes for granted
- **Limitations & Risks** -- known weaknesses and failure modes
- **Review History** -- (empty, populated by /review)
- **Evolution History** -- (empty, populated by /evolve)

## ID Format

`hyp-{YYYYMMDD}-{NNN}` where NNN is a zero-padded sequence number for that day. Scan existing hypotheses to determine next available NNN.

## Quality Gates

### Gate 1: Testable Predictions
Each hypothesis must have >= 2 testable predictions. Each prediction must be specific enough that an experiment could falsify it. Vague predictions like "may affect outcomes" fail this gate.

### Gate 2: Assumptions Listed
Each hypothesis must have >= 1 explicitly listed assumption. Hypotheses without stated assumptions have hidden assumptions -- surface them.

### Gate 3: Literature Citations (Mode 1)
In literature synthesis mode, each hypothesis must cite at least 1 specific source identifier (PMID, arXiv ID, DOI, URL). Uncited hypotheses in mode 1 are insufficiently grounded.

### Gate 4: Novelty Check
Compare new hypothesis title and mechanism against existing hypotheses. If >80% title similarity to an existing hypothesis: present the existing one and ask user to confirm this is genuinely novel or should be an /evolve instead.

### Gate 5: ID Uniqueness
Verify the generated ID does not collide with any existing hypothesis ID. If collision: increment NNN.

## Error Handling

| Error | Action |
|-------|--------|
| No active research goal | Ask user to set one via /research, or provide `--goal`. HANDOFF `status: failed` |
| `build_hypothesis_note()` failure | Report error, present hypothesis as text, ask user to save manually. HANDOFF `status: partial` |
| `_index.md` write failure | Warn user, hypothesis note is primary artifact. Continue |
| Literature search failure (mode 1) | Warn, offer to switch to mode 2 (self-play) instead. If `--handoff`: try fallback source first |
| Meta-review load failure | Continue without meta-review context. Note absence in HANDOFF learnings |
| Mode 3 with no existing hypotheses | Explain mode 3 requires at least 1 hypothesis. Offer mode 1 or 2 instead |

## Critical Constraints

- **Never auto-save without user approval.** Present each hypothesis for review before writing to vault.
- **Never skip testable predictions or assumptions.** These are the falsifiability backbone.
- **Always inherit `project_tag`** from the active research goal when set.
- **Always start new hypotheses at Elo=1200.** Evolved hypotheses also reset to 1200.
- **Always check for duplicate IDs** before saving.
- **Include meta-review feedback** in the generation prompt when available -- this is the self-improving loop mechanism.

## CO-SCIENTIST HANDOFF

When `--handoff` is present in `$ARGUMENTS`, emit after all work:

```
CO-SCIENTIST HANDOFF
skill: generate
goal: [[{goal-slug}]]
date: {YYYY-MM-DD}
status: {complete | partial | failed | no-data}
summary: {one sentence, e.g., "generated 3 hypotheses via mode 1 (literature synthesis)"}

outputs:
  - _research/hypotheses/hyp-{id}.md -- {short title}

quality_gate_results:
  - gate: testable-predictions -- {pass | fail: hyp-ids lacking predictions}
  - gate: assumptions-listed -- {pass | fail: hyp-ids lacking assumptions}
  - gate: literature-citations -- {pass | fail | n/a (mode != 1)}
  - gate: novelty-check -- {pass | fail: similar to hyp-{existing-id}}
  - gate: id-uniqueness -- {pass}

recommendations:
  next_suggested: {review | tournament | landscape} -- {why}

learnings:
  - {observation about generation process or gap discovery} | NONE
```

## Skill Graph

Invoked by: /research
Invokes: (none -- leaf agent)
Reads: _research/goals/, _research/meta-reviews/, _research/landscape/, _research/hypotheses/
Writes: _research/hypotheses/, _research/hypotheses/_index.md
