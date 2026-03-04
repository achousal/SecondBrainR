---
status: archived
---

# /init Skill Development

Development log for the `/init` skill -- guided knowledge seeding for new vaults and cycle transitions. Originated 2026-02-27 from meta-review findings and the `/onboard` gap analysis.

---

## Problem Diagnosis

EngramR has `/onboard` for infrastructure wiring (projects, data inventory, symlinks, goals) but no guidance for knowledge seeding. Users arrive at an empty graph with no direction on what first claims should be.

First notes matter disproportionately: they set graph topology and receive the highest context-window processing quality (fewer notes = more attention per note during /reflect and /reweave passes).

### Evidence from Meta-Review

The cross-program meta-review (`_research/meta-reviews/2026-02-23-cross-program-meta-review.md`) identified four structural gaps that `/init` addresses:

| Gap                                                                    | How /init Addresses It                                                                  |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Gatekeeper hypotheses generated one cycle late (positive-first bias)   | Phase 4 assumption inversions force falsification thinking from day one                 |
| Methodological requirements independently rediscovered across programs | Phase 3 shared methodology seeding captures cross-cutting analytical foundations        |
| Cross-program awareness missing                                        | Phase 3 operates across all selected goals, not per-goal                                |
| Confounders treated as limitations not design elements                 | Phase 3b compositional confounder claims elevate confounders to first-class graph nodes |

### Complementarity with /onboard

| Concern | /onboard | /init |
|---------|----------|-------|
| What it builds | Infrastructure (projects, data inventory, goals, symlinks) | Knowledge (orientation claims, methodology, confounders, inversions) |
| When to run | When adding a new lab or project | When starting knowledge work on a goal |
| Prerequisite | Filesystem with project dirs | At least one research goal exists |
| Output location | `projects/`, `_research/goals/`, `_dev/` | `notes/`, `_research/cycles/` |

---

## Design Decisions

Captured during planning phase in `docs/development/Plans.md` and plan-mode conversation.

### 1. Single skill vs. guided sequence of existing skills

**Decision:** Single skill (`/init`).

**Rationale:** The seeding flow has phase dependencies (Phase 3 references Phase 2 output, Phase 4 inverts Phase 2 claims). Orchestrating this across separate skills would require passing state through vault files, adding complexity. A single skill with internal phases keeps the compositional logic self-contained while remaining modular in structure.

### 2. Minimum claim count before declaring seeding complete

**Decision:** Soft gate at 6 claims (warn, do not block).

**Rationale:** Hard gates frustrate users in edge cases (single narrow goal, exploratory early sessions). The soft gate educates without blocking. 6 = at least 3 orientation + 2 methodological + 1 inversion.

### 3. Cycle transition mode

**Decision:** `--cycle` flag on `/init` rather than a separate skill.

**Rationale:** Cycle transitions share infrastructure with seeding (inversion generation, goal management, claim creation). The cycle mode reads more vault state (meta-reviews, experiments, daemon-inbox) but writes to the same targets (notes/, goals.md, reminders). A separate skill would duplicate the claim-creation machinery.

The cycle mode manages transitions by:
- Creating `_research/cycles/cycle-{N}-summary.md` with per-program status
- Asking per-goal disposition (continue / pivot / complete / sub-goal)
- Refreshing inversions with accumulated cycle evidence
- Reconciling daemon vs. meta-review priority drift

### 4. Claim type taxonomy for /init-generated claims

**Decision:** Use existing `type: claim` and `type: methodology`. No new types.

**Rationale:** Note titles alone provide sufficient context to distinguish orientation, confounder, and inversion claims. Adding schema types (type: orientation, type: inversion) would over-engineer the taxonomy. The prose-as-title convention already encodes the claim's role.

### 5. Compositional phase design

**Decision:** Phase 3 explicitly references Phase 2 output by title. Phase 4 generates inversions linked to specific Phase 2 claims.

**Rationale:** This is the key structural innovation. Without composition, Phase 3 confounders are generic ("consider batch effects") rather than specific ("batch effects confound this particular measurement in this context"). The specificity comes from anchoring each confounder question to a concrete orientation claim.

The compositional confounder question template:
```
Looking at the claim: "{Phase 2 orientation claim title}"
What could explain the expected results OTHER than the hypothesis?
(technical, biological, analytical confounders?)
```

### 6. Pipeline compliance for /init claims

**Decision:** Claims write directly to `notes/` via Write tool. validate_write hook enforces schema. No inbox routing.

**Rationale:** /init claims are synthesis, not source extraction. The inbox -> /reduce pipeline exists to transform external sources into atomic claims. /init claims are already atomic propositions generated in conversation with the user. The validate_write hook provides the same schema enforcement that /reduce claims receive.

---

## Implementation

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `.claude/skills/init/SKILL.md` | 780 | Main skill definition |
| `_code/templates/cycle-summary.md` | 57 | Template for cycle transition summaries |

### Files NOT Modified

No existing files were changed. The skill integrates through:
- Existing hooks (validate_write, auto_commit) -- automatic enforcement
- Existing templates (claim-note, topic-map) -- schema reference
- Existing scripts (orphan-notes.sh, dangling-links.sh, validate-schema.sh) -- post-verification

### Skill Architecture

```
/init [goal-name]          -->  SEED MODE
/init --cycle              -->  CYCLE MODE
/init [goal-name] --handoff --> SEED MODE + RALPH HANDOFF

SEED MODE:
  Step 0: Read vocab + vault state
  Step S1: Re-init detection (claim count > 0?)
  Step S2: Infrastructure check (goals, data-inventory exist?)
  Step S3: Goal selection (multi-select from _research/goals/)
  Phase 2: Domain Orientation [per-goal]
    2a. Read goal context
    2b. Interview: 3-5 core scientific questions
    2c. Generate orientation claims
    2d. Write claims -> ORIENTATION_CLAIMS list
  Phase 3: Methodological Seeding [shared, compositional]
    3a. Analytical method claims
    3b. Compositional confounder claims (one per ORIENTATION_CLAIM)
    3c. Data reality claims
    3d. Write all -> CLAIMS_CREATED list
  Phase 4: Assumption Inversions [per-goal, per-orientation-claim]
    4a. "What would convince you this is wrong?"
    4b. Generate inversion claim linked to parent
    4c. Write inversions -> CLAIMS_CREATED list
  Phase 5: Graph Wiring + Summary
    5a. Soft gate (< 6 claims?)
    5b. Topic map updates (create if 5+ claims, otherwise add to existing)
    5c. Update self/goals.md
    5d. Summary report

CYCLE MODE:
  Step C0: Read cycle context (goals, meta-reviews, experiments, daemon, reminders)
  Step C1: Generate cycle summary -> _research/cycles/cycle-{N}-summary.md
  Step C2: Goals transition (continue / pivot / complete / sub-goal)
  Step C3: Refresh assumption inversions with cycle evidence
  Step C4: Daemon reconciliation (optional, if daemon-inbox conflicts)
  Step C5: Update reminders
  Step C6: Cycle transition summary
```

### Claim Creation Pattern

Every claim follows the same procedure across all phases:

1. Construct title (prose-as-title, sanitized)
2. Verify wiki-link targets exist (`ls notes/"{target}.md"`)
3. Remove links to nonexistent targets (no dangling links)
4. Present to user for approval/edit
5. Write to `notes/{sanitized-title}.md` via Write tool
6. validate_write hook enforces schema automatically
7. auto_commit hook commits to git
8. Add to CLAIMS_CREATED tracking list

### Cycle Summary Template Schema

```yaml
type: cycle-summary
cycle: {N}           # integer, auto-incremented
programs: []         # wiki-links to goals
date_range: ""       # "YYYY-MM-DD to YYYY-MM-DD"
status: completed    # active | completed
created: YYYY-MM-DD
```

Sections: Overview, By Program (per-goal standings + findings), Persistent Blind Spots, Cycle Primers for N+1, Infrastructure Changes.

---

## Verification

### Structural Checks (all passed)

| Check | Result |
|-------|--------|
| SKILL.md YAML frontmatter parses | PASS |
| cycle-summary.md YAML frontmatter parses | PASS |
| Skill registered in system (appears in skill list) | PASS |
| dangling-links.sh (no new dangling links) | PASS |
| validate-schema.sh (all existing claims still pass) | PASS |
| Key design elements present (CLAIMS_CREATED, ORIENTATION_CLAIMS, compositional phases, validate_write, auto_commit, Topics footer, RALPH HANDOFF) | PASS |

### What Was NOT Tested

- Live execution of `/init goal-ad-biomarkers` (requires interactive session with claim creation)
- Live execution of `/init --cycle` (requires meta-review state and user input)
- Re-init detection on populated vault (requires running /init, then /init again)

These are interactive skills that require user participation at every claim-write gate. They cannot be smoke-tested without a human in the loop. The structural checks confirm the skill will load and route correctly; functional validation happens on first use.

---

## Integration Points

| System | How /init Integrates |
|--------|---------------------|
| validate_write hook | Automatic schema enforcement on every claim write |
| auto_commit hook | Automatic git commit after each claim |
| /research | Invoked if user needs a new goal during seeding |
| /onboard | Complementary -- /onboard builds infrastructure, /init seeds knowledge |
| /ralph | Can delegate to /init via --handoff flag |
| Topic maps | Phase 5 creates or updates topic maps for created claims |
| Daemon | Cycle mode reconciles daemon-inbox vs. meta-review priorities |
| _research/cycles/ | New directory created at runtime by --cycle mode |

---

## Open Items

- **First-use feedback:** The skill has not yet been run live. First execution may surface friction that requires Phase 3b question refinement or Phase 4 inversion prompt tuning.
- **Cycle numbering:** Currently auto-incremented by counting `_research/cycles/cycle-*.md` files. No explicit cycle registry exists. If cycle summaries are ever deleted or renamed, numbering could drift.
- **Cross-vault seeding:** Federation (`/federation-sync`) does not yet know about /init-generated claims. If claims are exchanged between vaults, orientation and inversion claims may need special handling to preserve their compositional relationships.
