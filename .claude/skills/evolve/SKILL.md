---
name: evolve
description: "Refine and evolve top-ranked hypotheses into stronger versions"
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
argument-hint: "[hyp-id | top-N] [--mode 1-5] [--goal slug]"
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure runtime behavior:

1. **`ops/config.yaml`** -- co-scientist parameters
   - `co_scientist.elo.starting`: 1200 (evolved hypotheses reset to this)
   - `co_scientist.handoff.mode`: manual | suggested | automatic

2. **`_research/goals/`** -- active research goal
   - Parse `project_tag` from goal frontmatter for tag inheritance
   - If `--goal [slug]` provided, use that goal; otherwise read active goal

3. **Dynamic context injection** (read inside Step 0, keep in working memory):

Latest meta-review feedback (if available):
!`ls -t "$VAULT_ROOT/_research/meta-reviews/"*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "No meta-reviews yet."`

Current landscape map (if available):
!`ls -t "$VAULT_ROOT/_research/landscape/"*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "No landscape analysis yet."`

4. **`_research/hypotheses/`** -- existing hypotheses with Elo rankings and review histories
   - Parse frontmatter: id, title, elo, status, generation, parents, review_scores, review_flags, research_goal, tags

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If `$ARGUMENTS` contains a hypothesis ID (e.g., `hyp-20260301-001`) -> evolve that hypothesis
- If `$ARGUMENTS` contains `top-N` (e.g., `top-3`) -> evolve the N highest-Elo hypotheses
- If `$ARGUMENTS` contains `--mode N` (1-5) -> use that evolution mode
- If `$ARGUMENTS` contains `--goal [slug]` -> scope to that research goal
- If `$ARGUMENTS` contains `--handoff` -> emit CO-SCIENTIST HANDOFF block at end
- If no target specified -> show leaderboard and ask user which hypothesis to evolve

**Execute these steps:**

1. Load co-scientist config from `ops/config.yaml`.
2. Read active research goal. Identify target hypotheses from arguments.
3. Read meta-review feedback (if exists) -- inject into evolution prompt.
4. Read landscape gaps (if exists) -- useful for mode 5 (divergent exploration).
5. Read existing hypothesis IDs and titles for ID uniqueness and novelty checking.
6. If no evolution mode specified: present mode menu, ask user to select.
7. For each target hypothesis:
   a. Read the hypothesis note fully (body + frontmatter).
   b. Read its review history and review flags for weakness identification.
   c. Apply the selected evolution mode (see Evolution Modes below).
   d. Run quality gates on the evolved hypothesis.
   e. Present evolved hypothesis to user for approval.
   f. Save approved hypothesis to `_research/hypotheses/hyp-{YYYYMMDD}-{NNN}.md`.
   g. Update parent hypothesis: add child link to Evolution History, optionally set status to "evolved".
   h. Update `_research/hypotheses/_index.md`.
8. If `--handoff`: emit CO-SCIENTIST HANDOFF block.

**START NOW.** Reference below explains methodology -- use to guide, not as output.

---

# /evolve -- Hypothesis Evolution Agent

Refine and evolve top-ranked hypotheses into stronger versions. Theory refinement through synthesis -- combines strengths of existing hypotheses and addresses weaknesses identified by /review and /tournament. Ensures the hypothesis pool improves across generations.

## Architecture

Implements the Evolution agent from the co-scientist system (arXiv:2502.18864). Supports 5 evolution modes, each targeting a different refinement strategy.

## Vault Paths

- Hypotheses: `_research/hypotheses/`
- Meta-reviews: `_research/meta-reviews/`
- Landscape: `_research/landscape/`
- Research goals: `_research/goals/`

## Code

- `_code/src/engram_r/note_builder.py` -- `build_hypothesis_note()`
- `_code/src/engram_r/hypothesis_parser.py` -- parse and link hypotheses
- `_code/src/engram_r/search_interface.py` -- unified search interface for mode 1 literature grounding
- `_code/src/engram_r/obsidian_client.py` -- vault I/O

## Evolution Modes

### Mode 1: Grounding Enhancement
- Read review flags and weaknesses from /review history.
- Search literature to address specific flagged concerns.
- Strengthen reasoning and evidence base.
- Fix assumptions flagged as invalid or unsupported.
- **Best when**: hypothesis has review flags indicating weak grounding.

### Mode 2: Combination
- Select 2-3 parent hypotheses (user chooses or suggest top-Elo compatible pairs).
- Identify complementary strengths across parents.
- Merge into a unified hypothesis that combines the best aspects.
- Resolve any contradictions between parents explicitly.
- **Requires**: at least 2 existing hypotheses.

### Mode 3: Simplification
- Reduce complexity of the hypothesis mechanism.
- Strip non-essential assumptions.
- Focus on the most testable core claim.
- Improve experimental feasibility.
- **Best when**: hypothesis has low testability scores but high novelty/correctness.

### Mode 4: Research Extension
- Extend hypothesis to adjacent domains or mechanisms.
- Explore broader implications beyond the original scope.
- Connect to related fields or pathways.
- **Best when**: hypothesis has high scores but narrow scope.

### Mode 5: Divergent Exploration
- Deliberately move away from current hypothesis clusters.
- Generate contrarian or orthogonal alternatives.
- Challenge prevailing assumptions in the research goal.
- Use landscape map (if available) to identify empty regions of hypothesis space.
- **Best after**: a /landscape analysis has been run.

## Evolved Hypothesis Format

Same format as /generate output, with these additional fields:

**Frontmatter additions:**
```yaml
generation: {max(parent_generations) + 1}
parents: ["hyp-{parent-id-1}", "hyp-{parent-id-2}"]
evolution_mode: "{mode name}"
elo: 1200
status: "proposed"
```

**Section additions:**
- **Evolution History** must document: which parent(s), what changed, why, and what weakness was addressed.

## Parent-Child Linking

Bidirectional linking is mandatory:
1. **Child note**: `parents` field in frontmatter lists parent IDs.
2. **Parent note**: append entry to "## Evolution History" section:
   ```markdown
   - {YYYY-MM-DD} -> [[hyp-{child-id}]] via {mode name}: {one-sentence rationale}
   ```
3. **Parent status**: optionally set to "evolved" if the child supersedes it (ask user).

## Quality Gates

### Gate 1: Parent Lineage
Every evolved hypothesis must have >= 1 parent ID in its `parents` field. Orphan evolutions are not allowed.

### Gate 2: Evolution Documentation
The "## Evolution History" section must document what changed and why. An empty evolution history fails this gate.

### Gate 3: Testable Predictions
Same as /generate: >= 2 testable predictions required.

### Gate 4: Assumptions Listed
Same as /generate: >= 1 explicitly listed assumption required.

### Gate 5: Generation Increment
`generation` must equal `max(parent_generations) + 1`. Verify by reading parent frontmatter.

### Gate 6: Elo Reset
Evolved hypotheses must start at Elo=1200 (from config). They must earn their ranking through tournament.

### Gate 7: Novelty vs Parent
The evolved hypothesis must differ substantively from its parent(s). If the evolution only rephrases without changing mechanism, predictions, or grounding: flag and ask user to confirm.

### Gate 8: ID Uniqueness
Verify the generated ID does not collide with any existing hypothesis ID. If collision: increment NNN.

## Error Handling

| Error | Action |
|-------|--------|
| No active research goal | Ask user to set one via /research, or provide `--goal`. HANDOFF `status: failed` |
| Target hypothesis not found | List available hypotheses for the goal. HANDOFF `status: failed` |
| `build_hypothesis_note()` failure | Report error, present evolved hypothesis as text. HANDOFF `status: partial` |
| Mode 2 with < 2 hypotheses | Explain combination requires >= 2 hypotheses. Offer mode 1 or 3 instead |
| Mode 5 with no landscape | Continue without landscape data but note reduced effectiveness. Suggest running /landscape first |
| Meta-review load failure | Continue without meta-review context. Note absence in HANDOFF learnings |
| Parent note update failure | Warn user. Child note is primary artifact -- continue |

## Critical Constraints

- **Never auto-save without user approval.** Present each evolved hypothesis for review before writing.
- **Never skip Evolution History documentation.** The rationale for evolution is essential provenance.
- **Always link parent <-> child bidirectionally.** Broken lineage chains compromise traceability.
- **Always reset Elo to 1200.** Evolved hypotheses must earn ranking through tournament.
- **Always inherit relevant literature** from parents. Do not discard grounding without justification.
- **Include meta-review feedback** in evolution prompts when available.
- **Inherit `project_tag`** from parent hypotheses.
- **Source fidelity for synthesis.** Evolved hypotheses must be grounded in vault-documented evidence. Do not inject facts, effect sizes, or mechanisms from model training knowledge that are not traceable to a vault source. If evidence is insufficient, state that explicitly rather than filling gaps from training data.
- **YAML safety.** Always double-quote all string values in YAML frontmatter. Unquoted colons, commas, or brackets cause silent misparsing and will be blocked by the validation hook.
- **Verify wiki-link targets exist** before including them in the evolved hypothesis note. Use Glob to confirm each `[[link]]` resolves to a real file.
- **Escalation ceiling.** Never write to or modify files in `self/`, `ops/config.yaml`, `ops/daemon-config.yaml`, or `CLAUDE.md`. These are protected paths requiring explicit operator confirmation per invocation.

## CO-SCIENTIST HANDOFF

When `--handoff` is present in `$ARGUMENTS`, emit after all work:

```
CO-SCIENTIST HANDOFF
skill: evolve
goal: [[{goal-slug}]]
date: {YYYY-MM-DD}
status: {complete | partial | failed | no-data}
summary: {one sentence, e.g., "evolved hyp-001 via mode 1 (grounding enhancement), gen 2"}

outputs:
  - _research/hypotheses/hyp-{id}.md -- {short title} (evolved from hyp-{parent-id})

quality_gate_results:
  - gate: parent-lineage -- {pass | fail: orphan ids}
  - gate: evolution-documentation -- {pass | fail: ids lacking rationale}
  - gate: testable-predictions -- {pass | fail: ids lacking predictions}
  - gate: assumptions-listed -- {pass | fail: ids lacking assumptions}
  - gate: generation-increment -- {pass | fail: ids with wrong generation}
  - gate: elo-reset -- {pass | fail: ids not at 1200}
  - gate: novelty-vs-parent -- {pass | fail: ids too similar to parent}
  - gate: id-uniqueness -- {pass}

recommendations:
  next_suggested: {tournament | review | generate} -- {why}

learnings:
  - {observation about evolution patterns or gap discovery} | NONE
```

## Skill Graph

Invoked by: /research
Invokes: (none -- leaf agent)
Reads: _research/hypotheses/, _research/meta-reviews/, _research/landscape/, _research/goals/
Writes: _research/hypotheses/ (new generation notes + parent updates), _research/hypotheses/_index.md
