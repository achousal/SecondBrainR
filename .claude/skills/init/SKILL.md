---
name: init
description: "Guided knowledge seeding for new vaults or cycle transitions. Seeds orientation claims, methodological foundations, and assumption inversions. Cycle mode generates transition summaries and refreshes inversions."
version: "2.0"
generated_from: "arscontexta-v1.6"
user-invocable: true
context: main
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
  - Skill
  - Agent
argument-hint: "[goal-name] | --cycle | --handoff"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

You are the /init orchestrator. You run in main context -- natural conversation turns, no AskUserQuestion needed. Sub-skills handle computation in fork context; you handle all user interaction.

**Architecture:** This skill coordinates three fork sub-skills via the Agent tool (subagent_type: general-purpose). Each agent Reads its sub-skill file from `sub-skills/` and executes its instructions in isolation:
- `init-orient` -- reads vault state, produces structured summary
- `init-generate` -- generates all claims (orientation, methodology, confounders, inversions)
- `init-wire` -- wires claims into topic maps, project bridges, goal updates

Detailed instructions for each phase live in `reference/` files that sub-skill agents Read on demand.

---

## Mode Selection

Parse `$ARGUMENTS`:

| Input | Mode |
|-------|------|
| (empty) | Seed mode -- interactive goal selection, full pipeline |
| `{goal-name}` | Seed mode -- direct seeding for named goal |
| `--cycle` | Cycle mode -- read `reference/cycle-mode.md` and follow those instructions |
| `--handoff` (appended) | Any mode + RALPH HANDOFF at end |

If `--cycle`, read `.claude/skills/init/reference/cycle-mode.md` and follow its instructions directly. The remainder of this file covers seed mode only.

---

## Phase 0: ORIENT

Launch an orient agent using the Agent tool:

```
Agent(subagent_type: "general-purpose", model: "haiku", description: "init orient")
Prompt: "Read and execute .claude/skills/init/sub-skills/init-orient.md. Return the structured ORIENT RESULTS output as specified in the sub-skill."
```

Parse the structured output: CLAIM_COUNT, goals list, vault state, VAULT_INFORMED flag, GOAL_SEEDING dict, and UNSEEDED_GOALS count.

### Re-init detection

If CLAIM_COUNT > 0, tell the user:

```
Your vault already has {CLAIM_COUNT} claims. /init is designed for early-stage seeding.

Options:
1. Seed a new goal -- add foundation claims for a goal that lacks seeding
2. Full re-seed -- generate all claim types from scratch (existing claims preserved)
3. Cancel -- exit without changes
{If UNSEEDED_GOALS > 0:}
4. Seed unseeded goals -- continue where you left off ({UNSEEDED_GOALS} goals remaining)
```

If option 4 selected: pre-populate SELECTED_GOALS with all goals whose GOAL_SEEDING status is `none` or `partial`, then skip Phase 1 goal selection and proceed directly to the budget recommendation in Phase 1.

Wait for user response. If cancel, stop.

### Infrastructure check

If `_research/goals/`, `self/goals.md`, or `projects/_index.md` are missing, warn:

```
Missing infrastructure: {list}
Recommendation: Run /onboard first, then return to /init.
Continue anyway?
```

Wait for response.

### Literature readiness check

After infrastructure check, run a lightweight readiness nudge:

```
uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import check_literature_readiness
print(json.dumps(check_literature_readiness('../ops/config.yaml')))
"
```

If `result.ready` is False:
  Print: "Note: {N} literature API keys still missing ({comma-separated var names}). Run /literature --setup before your first search."

No interactive loop here -- just a one-line nudge. `/onboard` is where full inline setup happens.

If `result.ready` is True: say nothing (no noise).

---

## Phase 1: GOAL SELECTION

### Turn 1: Goal review and selection

If a goal name was provided as argument, look it up and set SELECTED_GOALS = [that goal].

Otherwise, present available goals from the orient output as **editable suggestions**, annotated with seeding status:

```
=== Research Goals ===

These were created during onboarding. They are suggestions -- you own them.
Everything downstream (core questions, claims, wiring) builds from these goals,
so get them right here. We will seed goals one at a time.

{numbered list, each with title, one-line scope, and seeding tag:}
1. {goal title}    [{seeded tag}]
   {one-line scope}

Seeding tags from GOAL_SEEDING:
  complete -> [seeded]
  partial  -> [partial]
  none     -> [not seeded]

You can:
- Select goals to seed (by number or name)
- Edit a goal -- change title, scope, or framing before seeding
- Add a new goal
- Remove a goal

Tip: To workshop responses without consuming agent context, copy them into a
separate Claude session, refine there, and paste the final versions back here.
```

Wait for user response. Build SELECTED_GOALS list (ordered).

### Budget recommendation

After SELECTED_GOALS is built (whether from user selection or pre-populated by option 4):

```
{If len(SELECTED_GOALS) <= 2:}
  Proceeding with {N} goals this session.

{If len(SELECTED_GOALS) > 2:}
  You selected {N} goals. To maintain quality, I recommend seeding
  up to 2 goals per session. I'll remember which goals are done --
  next session, run /init and pick up the rest.

  Options:
  1. Seed first 2 now, rest next session (recommended)
  2. Seed all {N} now (quality may degrade for later goals)
```

Wait for response. If option 1, trim SELECTED_GOALS to the first 2. Store the original count as TOTAL_SELECTED for use in Phase 6.

**If user edits a goal:** Apply changes to the goal file in `_research/goals/` and update `self/goals.md` before proceeding. Re-present the edited goal for confirmation.

**If user adds a new goal:** Create a new goal file following `_code/templates/research-goal.md`, update `self/goals.md`, then add it to SELECTED_GOALS.

**If user removes a goal:** Confirm removal. Delete the goal file and remove its entry from `self/goals.md`.

---

## Phases 2-5: PER-GOAL LOOP

For each goal in SELECTED_GOALS, run the full generate-review-wire cycle. Initialize aggregate counters: TOTAL_CLAIMS = {}, TOTAL_TOPIC_MAPS = {created: 0, updated: 0}, TOTAL_BRIDGES = 0.

```
For goal_index, goal in enumerate(SELECTED_GOALS):
```

### Step 1: Banner

```
=== Seeding goal {goal_index + 1} of {len(SELECTED_GOALS)}: {goal title} ===
```

### Step 2: Core Questions

For this goal, generate 3-5 suggested core questions based on the goal's scope, linked projects, and any available vault context (data inventory, literature, project CLAUDE.md files). Then present them as editable suggestions:

```
For the goal "{goal title}":

Here are suggested core questions based on your projects and scope:

1. "{suggested question 1}"
2. "{suggested question 2}"
3. "{suggested question 3}"
{4-5 if warranted}

You can:
- Approve these as-is
- Edit any question (by number)
- Add your own questions
- Remove questions that miss the mark
- Replace all with your own
```

Wait for user response. Parse into individual questions.

**Quality bar for suggestions:** Each question should be specific enough to generate falsifiable hypotheses. Prefer "Does X predict Y in population Z?" over "What is the role of X?" Ground suggestions in the actual data and methods available in the linked projects.

### Step 3: Demo Claim (FIRST goal only)

**Skip this step for goal_index > 0.** The demo claim teaches the claim format once.

The user's first generative act. Building one thing teaches more than reviewing thirty.

Take the user's FIRST core question. Generate a suggested claim from it -- transform the question into a propositional statement grounded in the goal's scope and available data. Then present:

```
Let's turn your first question into a claim.

Question: "{first core question}"

A claim is a prose proposition -- a complete thought someone could agree or disagree with.
Test: "This claim argues that [title]" must work as a sentence.

Here is a suggested claim:

  Title:       "{suggested propositional title}"
  Description: "{suggested description, ~150 chars}"
  Confidence:  {suggested level}

You can:
- Approve as-is
- Edit any field
- Replace with your own claim entirely
```

Wait for user response. Parse title, description, confidence.

If approved, construct the full claim with YAML frontmatter and body. Present for final review:

```
Here is your first claim:

File: notes/{sanitized-title}.md
Title: {title}
  (Test: "This claim argues that {title}" -- reads as a sentence)
Description: {description}
Confidence: {confidence}

{full YAML + body preview}

Approve, edit, or skip?
```

**If approved:** Write to `notes/{sanitized-title}.md`. This is the demo claim.
**If edit:** Apply edits, re-present.
**If skip:** Proceed without demo claim. No penalty.

### Step 4: Generate Claims (fork)

Write input data to a temp file:
- SELECTED_GOALS = [this_goal] (single-element list)
- CORE_QUESTIONS (for this goal)
- DEMO_CLAIM (if approved and this is the first goal -- counts as first orientation claim)
- VAULT_STATE (from orient output)
- VAULT_INFORMED flag

Launch a generation agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "init generate")
Prompt: "Read and execute .claude/skills/init/sub-skills/init-generate.md with target: {temp-file-path}. Return the structured GENERATED CLAIMS output as specified in the sub-skill."
```

Parse the structured output: claims grouped by role with titles, filenames, and `<<<CLAIM>>>` content blocks.

### Step 5: Review and Write

Present this goal's claims grouped by role for review:

```
=== Claims for "{goal title}" ===

Orientation ({N}):
{numbered list of titles with one-line descriptions}

Methodology ({N}):
{numbered list}

Confounders ({N}):
{numbered list, each noting which orientation claim it threatens}

Inversions ({N}):
{numbered list, each noting which orientation claim it challenges}

Total: {N} claims

Review each group. You can:
- Approve all
- Remove specific claims by number
- Edit a claim's title or description
- Request additional claims for a category
```

Wait for user response. Apply any edits/removals.

**Write Approved Claims:**

1. Parse `<<<CLAIM>>>` blocks from the generation output
2. Skip claims the user removed (match by number or title)
3. Apply any user edits to the claim content strings
4. Write each approved claim via the Write tool to the path specified in the `FILE:` line
   - validate_write hook enforces schema automatically
   - auto_commit hook commits to git
5. Present: "Writing {N} approved claims..."
6. If validate_write rejects a claim, parse the error, fix the content, retry once

### Step 6: Wire (fork)

Write this goal's approved claims list to a temp file (claims are now on disk). Launch a wiring agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "init wire")
Prompt: "Read and execute .claude/skills/init/sub-skills/init-wire.md with target: {temp-file-path}. Return the structured WIRING SUMMARY output as specified in the sub-skill."
```

Parse the wiring summary. Present per-goal mini-summary:

```
Goal "{goal title}": {N} claims written, {N} topic maps updated, {N} project bridges wired.
```

Update aggregate counters.

### Step 7: Continue or Stop

If more goals remain in SELECTED_GOALS:

**Budget-cap reached (this is goal N of N in SELECTED_GOALS, and unseeded goals remain beyond this batch):**
```
Goal {N} of {N} complete. {remaining unseeded count} goals remain unseeded.
Recommended: start a fresh session for the next batch.
Run /init and select "Seed unseeded goals" to continue.
```
Break the loop and proceed to Phase 6.

**Under budget cap (more goals in SELECTED_GOALS):**
```
Ready for the next goal: "{next goal title}"? Or stop here and seed the rest later.
```

Wait for user response. If user stops, break the loop and proceed to Phase 6.

---

## Phase 6: SUMMARY

Present final summary aggregating across all goals seeded, with explicit unseeded tracking:

```
=== /init Seeding Summary ===

Goals seeded this session: {count}
{for each goal seeded:}
  - {goal title}: {N} claims

Claims created: {total across all goals}
  Orientation:    {count}
  Methodology:    {count}
  Confounders:    {count}
  Data realities: {count}
  Inversions:     {count}

Topic maps: {created count} created, {updated count} updated
Project bridges: {count} wired

Graph health:
- Orphan claims: {count} (should be 0)
- Dangling links: {count} (should be 0)

Your knowledge graph now has a four-layer foundation.
Each orientation claim has methodology context, confounders
that challenge it, and inversions that would falsify it.
```

**Unseeded goals call-to-action:** Compute remaining unseeded goals from the GOAL_SEEDING dict (re-check after this session's seeding completes -- goals seeded this session are now `complete`).

```
{If unseeded goals remain:}
Goals not yet seeded ({N}):
  - {goal-slug}
  - {goal-slug}

To continue: run /init and select "Seed unseeded goals"

{If all goals seeded:}
All research goals are now seeded.
```

Then present next steps:

```
=== What's Next ===
```

Run readiness check:
```
uv run --directory {vault_root}/_code python -c "
import json, sys; sys.path.insert(0, 'src')
from engram_r.search_interface import check_literature_readiness
print(json.dumps(check_literature_readiness('../ops/config.yaml')))
"
```

Then present the appropriate next steps:

```
If result.ready:
  /literature -- search for papers supporting or challenging these claims
If not result.ready:
  /literature --setup -- configure API keys before searching (missing: {comma-separated var list})
  /literature         -- or search now with available sources only

/generate  -- produce hypotheses building on this foundation
/reflect   -- find connections between new and existing claims
=== End Summary ===
```

---

## Handoff Mode

If `--handoff` was included, append RALPH HANDOFF block after the summary:

```
=== RALPH HANDOFF: init ===
Target: {arguments}
Mode: seed

Work Done:
- {summary of actions taken}

Files Modified:
- {list}

Claims Created:
- {list of claim titles}

Learnings:
- [Friction]: {any} | NONE
- [Surprise]: {any} | NONE
- [Methodology]: {any} | NONE

Queue Updates:
- Suggest: {follow-up actions}
=== END HANDOFF ===
```

---

## Error Handling

| Error | Behavior |
|-------|----------|
| No goals exist | Suggest /research to create a goal, or offer to create inline |
| Re-init on populated vault | Soft detection + user choice (Phase 0) |
| Missing infrastructure | Warn + recommend /onboard (Phase 0) |
| Sub-skill fails | Report error, offer to retry or proceed manually |
| Duplicate claim title | Report to user, ask for rephrasing |
| validate_write hook rejects | Parse error, fix claim, retry once |

---

## Skill Graph

Invoked by: user (standalone), /ralph (delegation), /onboard (suggested next step)
Prerequisite: /onboard (creates research goals and project infrastructure)
Invokes: init-orient, init-generate, init-wire (via Agent tool); /research (if user needs a new goal)
Suggests next: /literature, /generate, /reflect
Reads: self/, _research/goals/, _research/meta-reviews/, notes/, projects/
Writes: notes/ (claims), _research/cycles/ (cycle summaries), self/goals.md, projects/ (linked_goals wiring)
