---
description: "Post-implementation review of onboard+init UX changes: progressive disclosure, Phase 3-4 enforcement, role taxonomy, loading order assessment"
type: methodology
created: 2026-02-28
status: archived
---

# Onboard + Init UX Review: Post-Implementation Assessment

Review of the /onboard + /init first-run experience after implementing the stream-garden-stigmergy changes. Evaluated by running a clean vault reset, full /onboard (4 labs, 22 projects), and full /init (3 goals, 35 claims across 5 roles).

---

## 1. The User Introduction Problem

The user intro is the most consequential design surface in the system. It determines whether the user becomes a participant or an audience member. The question is not "what does the user see?" but "what does the user become capable of doing alone after the intro finishes?"

### What the current intro gets right

The /onboard roadmap is the strongest single moment in the sequence. Before any scan runs, the user sees:

```
This process has 5 phases (~3-4 interactions from you).
Setup scales with your existing documentation.
```

This does three things simultaneously: it bounds the time commitment, it signals that the system adapts to existing work, and it frames the user as a reviewer rather than a data entry clerk. The documentation quality message ("well-documented = mostly automatic; undocumented = guided interview") is honest calibration that prevents both disappointment and false confidence.

The /onboard Step 7 "Quick Orientation" section (new) is the second strongest moment. It names the four claim layers before /init runs:

```
Orientation   -- what you study
Methodology   -- how you study it
Confounders   -- what could fool you
Inversions    -- what would prove you wrong
```

This four-line framing is the conceptual payload of the entire system compressed into something a user can hold in working memory. It also sets up the falsificationist epistemic stance without using the word "falsificationist."

### What the current intro gets wrong

The user's first active contribution is choosing goals -- step 12 in the experience. By that point, the system has created 22 project notes, 4 lab profiles, an institution profile, a data inventory, and 22 symlinks. The user approved these, but approval is not contribution. The user's relationship to these artifacts is "I confirmed this is correct" rather than "I helped build this."

The intro never demonstrates the core unit of work. The user sees claims only after /init generates them. They never write one. They never see the `inbox/ -> /reduce -> notes/` pipeline in action. They approve 35 claims but never compose a title, never choose a confidence level, never decide which topic map a claim belongs to. The conventions are taught by exposure, not by practice.

The system teaches its vocabulary through field names in tables and YAML. A new user encounters `type: moc`, `role: orientation`, `source_class: synthesis`, `verified_by: agent` without definitions. These are interpretable by a technical user, but they are not explained at the moment of first encounter. The Quick Orientation section explains the four claim layers in plain language, but the mapping from plain language to YAML values happens silently.

### The unresolved gap

The ideal intro would have the user write one claim before seeing thirty-five generated ones. This was proposed as P3 ("First-Claim-Before-Infrastructure") in the original review but not implemented. The reason is structural: /onboard must scan before /init can seed, and /init must generate before the user has a frame of reference for what claims look like.

The tension is real. The gardening metaphor applies directly: a gardener who plants one seed and watches it grow understands gardening better than one who arrives to find a finished garden. But /init cannot demonstrate claim creation without the goal infrastructure that /onboard produces.

A possible resolution: add a "demo claim" to /init Phase 2b that walks the user through composing one claim interactively before batch-generating the rest. The user would see the prose-as-title convention, the YAML schema, the Topics footer, and the wiki-link verification process on a single concrete example. Then the remaining claims would be generated with the user's understanding of what they are approving.

---

## 2. Stream vs Garden

**Stream** = the temporal conversation that disappears. **Garden** = the durable vault that persists.

### The stream

The onboard+init conversation is approximately 6-8 user interactions across both skills:
1. Provide lab path
2. Confirm institution and infrastructure (3a)
3. Confirm per-lab project tables (3b, one per lab)
4. Optional strategic question
5. Approve artifact generation
6. Select goals for /init
7. Provide core questions per goal (Phase 2b)
8. Confirm/adjust method claims, confounders, data realities (Phase 3)

The progressive disclosure changes (P2) improved the stream significantly. The previous design presented all findings in a single wall of text with 4 simultaneous AskUserQuestion calls. The user approved in one pass -- a compliance event, not a comprehension event. The new design breaks this into separate focused stages. Each stage presents one concern (infrastructure, then per-lab projects, then cross-lab connections) with its own confirmation.

However, the fork execution model limits the progressive disclosure to section separation within a single output, not truly sequential turns. In an interactive (non-fork) context, each sub-step would be a separate conversation turn with its own AskUserQuestion. In the fork context, the agent batches them. This is an architectural constraint of the `context: fork` setting, not a SKILL.md design flaw.

### The garden

What persists after the stream ends:

| Layer | Artifacts | User's Relationship |
|---|---|---|
| Project infrastructure | 22 project notes, 4 lab profiles, 1 institution, 1 data inventory, 22 symlinks | "I confirmed these" |
| Knowledge graph | 35 claims across 5 roles, 3 topic maps | "I answered questions that produced these" |
| Self-knowledge | Updated goals.md, seeding_status in goal files | "I chose which goals to pursue" |
| Operational | Reminders, session log | "I did not interact with these" |

The garden is structurally sound. Every claim has a Topics footer. Every topic map has role-grouped sections. Every goal file tracks which phases completed. The graph has no orphan claims and no dangling links (in claims).

But the garden has a missing bridge. The project layer (`projects/`) and the knowledge layer (`notes/`) are parallel namespaces with no direct connection. `linked_goals: []` in every project file. A user browsing `projects/elahi-lab/ad-classification.md` sees "linked_goals: []" and cannot navigate to the topic map that discusses the same science. A user browsing `notes/ptau217-biomarker-classification.md` sees orientation claims but cannot navigate to the project whose data would test them.

This bridge was not part of the original implementation plan. It should be: the project-to-claim connection is what transforms the vault from "a knowledge base and a project directory" into "a research environment where knowledge and projects reference each other."

---

## 3. Stigmergy: Pheromone Trails in the Vault

Stigmergy means the artifacts themselves teach the user how to work with the system. The user does not need to read documentation -- they learn by encountering artifacts that demonstrate their own conventions.

### What teaches well (strong pheromone trails)

**Topic maps are the best stigmergic artifact.** A user who opens `notes/ptau217-biomarker-classification.md` immediately learns:
- Claims are organized by epistemic role (section headers: Orientation, Methodology, Confounders, Inversions)
- Each entry has a context phrase explaining *why* it belongs here
- Open Questions signal live uncertainty, not false closure
- The sections are ordered pedagogically: what we study, how we measure, what threatens, what would falsify

The role-grouped sections (new) are the single most effective teaching device in the vault. They make the system's epistemic structure visible without explanation. A user who sees "Confounders" as a named section immediately understands that the system tracks threats to its own claims.

**Confounder and inversion claims use inline wiki-links correctly.** The confounder claim "CKD elevates p-tau217..." contains `[[plasma-ptau217-classifies-amyloid-positivity-despite-ckd-confounding]]` inline, explicitly naming the claim it threatens. The inversion claim opens with "This inversion challenges [[parent claim]]." These inline references make the argument structure visible within each file. A user reading a confounder knows immediately which orientation claim it targets.

**The seeding_status block in goal files is machine-readable stigmergy.** A user (or a downstream skill like /health or /generate) reading a goal file can immediately determine whether all phases completed. The five-field block (orientation, methodology, confounders, data_realities, inversions) is both human-readable and queryable.

**Lab _index.md files are complete onboarding documents.** A new collaborator could configure an analysis environment from `projects/elahi-lab/_index.md` alone: HPC cluster, scheduler, statistical conventions, available platforms, project list with summaries.

### What fails to teach (weak or missing pheromone trails)

**Orientation and methodology claims do not link laterally.** They link upward to their topic map via the Topics footer, but they do not link to sibling claims within the body text. A user reading an orientation claim learns "this belongs to a topic map" but not "this relates to that confounder and that inversion." The confounder and inversion claims do this correctly -- the asymmetry means the orientation claims are less self-documenting.

**The `inbox/ -> /reduce -> notes/` pipeline was never exercised.** The user has never seen the normal knowledge-creation workflow. /init bypasses the pipeline (its claims are synthesis, not extraction), which is correct but invisible. A user who has only seen /init does not know that source material is supposed to enter through `inbox/`, be processed by `/reduce`, and emerge as claims in `notes/`. The pipeline bypass rule is stated in CLAUDE.md but never demonstrated.

**YAML field values are not self-documenting.** `type: moc`, `role: orientation`, `source_class: synthesis` are interpretable by inference but never defined at the point of first encounter. A new user sees `confidence: speculative` on an inversion claim and can guess what it means, but they do not know the full enum (established, supported, preliminary, speculative) or the ordering. The claim template at `_code/templates/claim-note.md` defines these, but a user browsing `notes/` would not know to look there.

**The high-risk triage surface is invisible.** The combination `source_class: synthesis` + `confidence: speculative` + `verified_by: agent` is the highest-risk claim category per CLAUDE.md. All 9 inversion claims carry this combination. There is no visual marker, no in-file warning, no stigmergic signal that these claims require human verification before use in a SAP. The risk is queryable but not discoverable by browsing.

**Data-reality claims will go stale.** "CADASIL CSF dataset has unknown final N pending data cleaning" encodes a fact that is currently true but will become false. There is no expiry mechanism, no linked reminder, no affordance that signals "check whether this is still true." A user who does not run `/health` regularly would not know the claim has become outdated.

---

## 4. Loading Order Assessment

### The implemented order

```
/onboard:
  0. Silent vault state read
  1. Path prompt + roadmap display
  2. Silent scan (filesystem, code, conventions)
  3a. Institution + infrastructure review
  3b. Per-lab project table review
  3c. Cross-lab connections review
  4. Optional strategic question
  5. Single approval gate -> batch artifact generation
  6. Silent verification
  7. Summary + Quick Orientation (new)

/init:
  S1. Re-init detection (if claims exist)
  S2. Infrastructure check
  S3. Goal selection
  Phase 2: Core questions interview -> orientation claims
  Phase 3: Methodology + confounders + data realities (vault-informed)
  Phase 4: Inversions per orientation claim
  Phase 5: Phase gate + topic maps + seeding_status + summary
```

### What works about this order

The /onboard -> /init sequence is correct at the macro level. Infrastructure before knowledge. Project metadata before epistemic claims. Data inventory before confounders (so Phase 3 can reference sample sizes). This ordering means Phase 3 can pre-populate confounder drafts from the data inventory, which transforms the confounder interview from "name some confounders" to "confirm or adjust these confounders I found in your data." That shift is significant -- it moves the user from blank-page generation to editorial review.

The Phase 2 -> 3 -> 4 ordering within /init is epistemically sound. Orientation claims establish what is being studied. Methodology claims establish how. Confounders establish what could interfere. Inversions establish what would falsify. Each phase builds on the previous phase's output, and the Phase 5 gate (new) enforces that all phases ran.

### What the order still gets wrong

**Infrastructure dominates the early experience.** The user's first 20 minutes are consumed by project metadata, lab conventions, and data inventory review. These are necessary but do not engage the user as a scientist. The user's first scientifically meaningful act -- answering "what are your 3-5 core questions?" in Phase 2b -- happens after the infrastructure is fully built. By then, the user has internalized a frame: "this system organizes my files." The conceptual reframe -- "this system challenges my assumptions" -- arrives late.

**The Quick Orientation (new) helps but arrives after the infrastructure phase.** It correctly names the four claim layers before /init runs, which is better than the previous design where the layers were never named. But it is a text description, not a demonstrated experience. The user reads about orientation/methodology/confounders/inversions in the abstract. They encounter them concretely only after /init completes.

**The user never practices the claim lifecycle.** /init generates claims and the user approves them. The user never: composes a prose-as-title from scratch, chooses between confidence levels, decides which topic map a claim belongs to, writes a Topics footer, or adds an inline wiki-link. These are the micro-skills that make a user autonomous. After /init, the user depends on the system to generate claims and can only review them.

### The ideal loading order (not yet implemented)

```
Phase 0: ORIENT (5 min)
  Show identity.md and methodology.md (already happens in session orient)
  Show one worked example of each artifact type (not yet implemented)
  User writes one claim manually (not yet implemented)
  -> User learns: what claims look like, how titles work, how links work

Phase 1: SCAFFOLD (10 min)
  /onboard scans ONE lab first (or a small subset)
  User reviews a manageable set of projects
  -> User learns: project metadata, data access vocabulary, lab conventions

Phase 2: SEED (15 min)
  /init for one goal with ALL FOUR PHASES
  User answers core questions, confirms confounders, states inversions
  -> User learns: the four epistemic layers through experience

Phase 3: EXPAND (subsequent sessions)
  Additional labs, projects, goals
  Each follows the same pattern but faster
  -> User learns: the system scales predictably
```

The key difference: comprehension before coverage. The current order is coverage-first (all labs, all projects, all goals in one pass). The ideal order is depth-first (one lab, one goal, fully understood before expanding). The user's understanding compound with each layer, so starting narrow and deep produces better autonomy than starting broad and shallow.

---

## 5. Verdict: What Changed and What Remains

### Changes that landed

| Change | Effect | Evidence |
|---|---|---|
| Phase 5a hard gate | Phases 3-4 cannot be skipped | 35 claims: 9 orientation, 3 methodology, 11 confounders, 3 data realities, 9 inversions |
| Phase 2->3 tracking | Explicit "this is mandatory" language | PHASE_TRACKING block in SKILL.md |
| seeding_status in goal files | Phase completion is machine-queryable | All 3 goals show all phases `complete` |
| role field on all claims | Epistemic layer is visible in frontmatter | 5-value enum, all claims tagged |
| Role-grouped topic maps | Graph structure visible in navigation | All 3 topic maps have Orientation/Methodology/Confounders/Inversions sections |
| Progressive disclosure in /onboard | Review broken into focused stages | 3a/3b/3c structure in SKILL.md |
| Quick Orientation in Step 7 | Four claim layers named before /init | Text block between summary and What's Next |

### What remains unresolved

| Gap | Impact | Proposed Resolution |
|---|---|---|
| User never writes a claim | Low autonomy after onboarding | Add demo-claim step to /init Phase 2b |
| Project-to-claim bridge missing | Two parallel namespaces without cross-references | Populate `linked_goals` in project files during /init Phase 5 |
| Pipeline never demonstrated | User does not know inbox -> /reduce -> notes/ | Add a worked example to Quick Orientation or /tutorial |
| Fork execution limits progressive disclosure | Review stages batch into one output | Consider `context: main` for /onboard, or accept as architectural constraint |
| High-risk claims not flagged in-file | Risk triage requires cross-field query | Add inline marker for speculative + synthesis + agent claims |
| Data-reality claims will go stale | No expiry or review trigger | Link data-reality claims to ops/reminders.md entries |
| Orientation claims lack lateral links | Argument structure incomplete at orientation level | Add inline wiki-links to related confounders/inversions in orientation claim bodies |

### Bottom line

The core failure from the original onboarding -- Phases 3-4 silently skipped, producing an affirmation-only graph -- is fixed. The structural enforcement is strong: hard gate at Phase 5, explicit tracking at Phase 2->3 transition, seeding_status in goal frontmatter, and role taxonomy across all claims and topic maps.

The UX improvements (progressive disclosure, Quick Orientation, role-grouped topic maps) are structurally correct in the SKILL.md and produce better artifacts. The fork execution model limits the progressive disclosure to section separation rather than true sequential turns, but the artifacts themselves teach the system's epistemology effectively.

The remaining gap is user autonomy. The onboarding produces a correct, well-structured, epistemically sound vault -- but the user's role in creating it was editorial (confirm, adjust, approve), not generative (compose, choose, connect). The user exits onboarding knowing what the system built, but not yet knowing how to build with it. That gap is addressed by the skills that follow (/reduce, /reflect, /literature), but the handoff from "I reviewed this" to "I can do this myself" is not yet smooth.

---

Topics:
- [[methodology]]
