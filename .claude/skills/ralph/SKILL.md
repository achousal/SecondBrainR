---
name: ralph
description: Queue processing with fresh context per phase. Processes N tasks from the queue, spawning isolated subagents to prevent context contamination. Supports serial, parallel, batch filter, and dry run modes. Triggers on "/ralph", "/ralph N", "process queue", "run pipeline tasks".
version: "1.0"
generated_from: "arscontexta-v1.6"
user-invocable: true
context: normal
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Agent
argument-hint: "[N] [--parallel] [--batch id] [--type reduce] [--dry-run] — N = number of tasks to process (optional: omit for overview)"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse arguments:
- N (optional): number of tasks to process. If omitted (bare `/ralph`), run Steps 0-3 to show the queue overview, then ask the user how many to process before continuing to Step 4.
- --parallel: concurrent claim workers (max 5) + cross-connect validation
- --batch [id]: process only tasks from specific batch
- --type [type]: process only tasks at a specific `current_phase` (reduce, create, reflect, reweave, verify, enrich). Note: extraction tasks have `type: extract` but `current_phase: reduce` -- use `--type reduce` to select them.
- --dry-run: show what would execute without running
- --handoff: output structured RALPH HANDOFF block at end (for phase chaining)

**START NOW.** Process queue tasks.

---

## Step 0: Queue Health Advisory

**0a. Phase Ordering Tips**

Before processing, call the vault advisor for phase ordering tips:

```bash
VAULT_PATH="$(pwd)"
ADVISOR=$(cd _code && uv run python -m engram_r.vault_advisor "$VAULT_PATH" \
    --context ralph --include-phase-tips --max 4 2>/dev/null)
ADVISOR_EXIT=$?
```

Store any phase tips internally for use in Step 3 (the overview merges them into the blocked/actionable summary). Do NOT display a separate Phase Advisory block.

If the advisor fails or returns no phase tips, proceed silently.

**0b. Abstract-Only Source Advisory**

Count reduce-phase tasks whose extract task file has `content_depth: abstract` or `scope: abstract_only`. If any exist, display:

```
[Content Depth Advisory] {N} source(s) at abstract scope.
Extraction will be limited to claims/evidence/questions (no methods or design patterns).
```

This is informational only -- never block processing. Continue to Step 1.

---

## MANDATORY CONSTRAINT: SUBAGENT SPAWNING IS NOT OPTIONAL

**You MUST use the Agent tool to spawn a subagent for EVERY task. No exceptions.**

This is not a suggestion. This is not an optimization you can skip for "simple" tasks. The entire architecture depends on fresh context isolation per phase. Executing tasks inline in the lead session:
- Contaminates context (later tasks run on degraded attention)
- Skips the handoff protocol (learnings are not captured)
- Violates the ralph pattern (one phase per context window)

**If you catch yourself about to execute a task directly instead of spawning a subagent, STOP.** Call the Agent tool. Every time. For every task. Including create tasks. Including "simple" tasks.

The lead session's ONLY job is: read queue, spawn subagent, evaluate return, update queue, repeat.

---

## Phase Configuration

Each phase maps to specific Agent tool parameters. Use these EXACTLY when spawning subagents.

| Phase | Skill Invoked | Model | max_turns | Rationale |
|-------|---------------|-------|-----------|-----------|
| extract | /reduce | sonnet | 25 | Large sources need many passes |
| create | (inline note creation) | sonnet | 12 | Bounded: read task, write note (extra headroom for YAML retry) |
| enrich | /enrich | sonnet | 8 | Bounded: read note, augment |
| reflect | /reflect | sonnet | 15 | Dual discovery + MOC update |
| reweave | /reweave | sonnet | 15 | Find + update older notes |
| verify | /verify | haiku | 8 | Schema + recite + review |
| cross-connect | (inline validation) | sonnet | 15 | Validate sibling links |

**Model and turn budgets are read from `ops/daemon-config.yaml`** (sections `models:` and `max_turns:`). Read this file at Step 1 alongside the queue. If daemon-config is missing or unreadable, use the defaults in the table above.

Turn budgets are circuit breakers, not throttles. A bounded phase hitting its cap is probably lost; a semi-bounded phase hitting its cap was doing genuine work. Set high enough that normal execution never hits them, low enough that runaway agents get stopped.

---

## Step 1: Read Queue State and Phase Config

Read **two** files:

**1a. Daemon config** — read `ops/daemon-config.yaml`. Extract the `models:` and `max_turns:` blocks. Store phase-to-model and phase-to-turns mappings for use in Agent calls. If unreadable, use Phase Configuration table defaults.

**1b. Queue file** — check these locations in order:
1. `ops/queue.yaml`
2. `ops/queue/queue.yaml`
3. `ops/queue/queue.json`

Parse the queue. Identify ALL pending tasks.

**Queue structure (v2 schema):**

The queue uses `current_phase` and `completed_phases` per task entry:

```yaml
phase_order:
  claim: [create, reflect, reweave, verify]
  enrichment: [enrich, reflect, reweave, verify]

tasks:
  - id: source-name
    type: extract
    status: pending
    source: ops/queue/archive/2026-01-30-source/source.md
    file: source-name.md
    created: "2026-01-30T10:00:00Z"

  - id: claim-010
    type: claim
    status: pending
    target: "claim title here"
    batch: source-name
    file: source-name-010.md
    current_phase: reflect
    completed_phases: [create]
```

If the queue file does not exist or is empty, report: "Queue is empty. Use /seed to add sources."

## Step 2: Filter Tasks

Build a list of **actionable tasks** — tasks where `status == "pending"`. Order by PIPELINE_ORDER (reduce < create < enrich < reflect < reweave < verify), then by position in the tasks array within the same phase.

Apply filters:
- If `--batch` specified: keep only tasks where `batch` matches
- If `--type` specified: keep only tasks where `current_phase` matches (e.g., `--type reflect` finds tasks whose `current_phase` is "reflect")

**Phase Eligibility Gate (after user filters, before batch grouping):**

Enforce phase ordering across all pending tasks. Later phases cannot run while earlier phases have pending work, because later phases depend on the graph state produced by earlier phases.

1. Count pending tasks by `current_phase` across the **full queue** (not just the user-filtered subset -- the gate considers global queue state).
2. Apply blocking rules:
   - If **any** tasks are pending at `create` or `enrich`: **exclude** tasks at `reflect` and `reweave` from the actionable list.
   - If **any** tasks are pending at `reflect`: **exclude** tasks at `reweave` from the actionable list.
3. `reduce` and `verify` tasks are **never blocked** by this gate. Reduce (which processes extract-type tasks) is upstream of everything; verify is a quality check that does not create new connections.
4. Remove ineligible tasks from the actionable list.

Do NOT display verbose phase gate messages here. Gate results are folded into the compact overview in Step 3.

If the gate removes ALL actionable tasks, Step 3 will show the blockage and suggest processing the earlier phase.

**Batch Grouping (after filtering):**

After filtering, sort actionable tasks so tasks from the same batch appear consecutively:
1. Collect unique batch values in order of first appearance.
2. Group tasks by batch, preserving original order within each group.
3. Tasks with no batch field retain original relative order, placed at end.
4. Flatten into final ordered list.

This changes only order, not which tasks are processed. When `--batch` is set, this is a no-op (all tasks share the same batch already).

The `phase_order` header defines the phase sequence:
- `claim`: create -> reflect -> reweave -> verify
- `enrichment`: enrich -> reflect -> reweave -> verify

## Step 3: Queue Overview

**Canonical pipeline order** (all display components use this):
```
PIPELINE_ORDER = [reduce, create, enrich, reflect, reweave, verify]
```

Show the compact queue overview. Merge phase gate results, pipeline advisory tips, and actionable state into a single block:

```
--=={ ralph }==--

Queue: X pending, Y done
Actionable: {count} ({N} reduce, {N} create, {N} enrich, ...)
Blocked: {N} reflect, {N} reweave -- {reason why, e.g. "35 enrich tasks must finish first so reflect sees the full claim surface"}

Next:
1. {id} -- {current_phase} -- {target (truncated)}
2. {id} -- {current_phase} -- {target (truncated)}
...

Options:
- /ralph {N} --type reduce -- process extractions first
- /ralph {N} --type enrich -- clear enrich backlog (unlocks reflect)
- /ralph {N} -- all eligible tasks
```

**Formatting rules:**
- `Actionable` line: group and label by `current_phase` (not `type`). List phases in PIPELINE_ORDER (reduce, create, enrich, reflect, reweave, verify). Drop phases with 0 actionable tasks. This is critical because `--type` filters on `current_phase`. Extraction tasks have `type: extract` but `current_phase: reduce` -- label them as `reduce` so the suggested `--type` commands match.
- `Blocked` line: only show if tasks were blocked by the phase gate. Include a SHORT rationale (one clause, not a paragraph) explaining why the earlier phase must finish first. If nothing is blocked, omit the line entirely.
- `Next` list: show up to 8 tasks. Sort by PIPELINE_ORDER first (reduce tasks before create before enrich, etc.), then by queue position within the same phase. Truncate claim titles to ~60 chars with `...`.
- `Options`: show 2-4 concrete commands based on the actionable phase distribution. Include a brief label for what each does. **Order by PIPELINE_ORDER** (earliest phase first). Earlier phases unblock downstream work, so pipeline order IS strategic order.

**If all tasks blocked:**
```
--=={ ralph }==--

Queue: X pending, Y done
Blocked: all {N} tasks at {phase} -- {M} {earlier_phase} must finish first

Suggested: /ralph {M} --type {earlier_phase}
```

**If `--dry-run`:** STOP here. Do not process.

**If N was provided as argument:** Continue directly to Step 4 (serial) or Step 6 (parallel).

**If N was NOT provided (bare `/ralph`):** Ask the user how many tasks to process. Show the overview first so they can make an informed choice. Wait for their answer before proceeding. Accept a number, `--batch [id]`, `--type [phase]`, or any combination.

---

## Step 4: Process Loop (SERIAL MODE)

**If `--parallel` is set, skip to Step 6 instead.**

Process up to N tasks (default 1). For each iteration:

### 4a. Select Next Task

Pick the first pending task from the filtered list. Read its metadata: `id`, `type`, `file`, `target`, `batch`, `current_phase`, `completed_phases`.

The `current_phase` determines which skill to invoke.

Report:
```
=== Processing task {i}/{N}: {id} — phase: {current_phase} ===
Target: {target}
File: {file}
```

### 4b. Build Subagent Prompt

Construct a prompt based on `current_phase`. Every prompt MUST include:
- Reference to the task file path (from queue's `file` field)
- The task identity (id, current_phase, target)
- The skill to invoke with `--handoff`
- `ONE PHASE ONLY` constraint
- Instruction to output RALPH HANDOFF block

**Phase-specific prompts:**

For **extract** phase (type=extract tasks only):
```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: extract | Target: {TARGET}

Run /reduce --handoff on the source file referenced in the task file.
After extraction: create per-claim task files, update the queue with new entries
(1 entry per claim with current_phase/completed_phases), output RALPH HANDOFF.
ONE PHASE ONLY. Do NOT run reflect or other phases.
```

For **create** phase:

**Pre-dispatch validation:** Before spawning the subagent, verify the task file exists on disk using `Glob` with `ops/queue/{FILE}`. If the task file does not exist, do NOT dispatch the create. Instead, mark the task as blocked with a note: `"blocked": "task file does not exist — reduce phase may not have completed"`. Report it in the summary as a blocked task. This prevents writes to notes/ without pipeline provenance.

```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: create | Target claim: {TARGET}

Create a claim for this claim in notes/[claim as sentence].md
Follow note design patterns:
- YAML frontmatter with description (adds info beyond title), topics
- CRITICAL: ALL YAML string values MUST be wrapped in double quotes (e.g. description: "text here"). Unquoted values containing colons will be blocked by the validation hook.
- Body: 150-400 words showing reasoning with connective words
- Footer: Source (wiki link), Relevant Notes (with context), Topics
Update the task file's ## Create section.
ONE PHASE ONLY. Do NOT run reflect.
```

For **enrich** phase:

**Pre-dispatch validation:** Before spawning the subagent, verify the target note exists on disk using `Glob` with `notes/**/[TARGET]*`. If the target note does not exist, do NOT dispatch the enrichment. Instead, mark the task as blocked with a note: `"blocked": "target note does not exist"`. Report it in the summary as a blocked task. This prevents wasted subagent work on phantom targets created by reduce-phase hallucination.

```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: enrich | Target: {TARGET}

Run /enrich --handoff using the task file for context.
The task file specifies which existing claim to enrich and what to add.
ONE PHASE ONLY. Do NOT run reflect.
```

For **reflect** phase:

**Build sibling list:** Query the queue for other claims in the same batch where `completed_phases` includes "create" (note already exists). Format as wiki links.

```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: reflect | Target: {TARGET}

OTHER CLAIMS FROM THIS BATCH (check connections to these alongside regular discovery):
{for each sibling in batch where completed_phases includes "create":}
- [[{SIBLING_TARGET}]]
{end for, or "None yet" if this is the first claim}

Run /reflect --handoff on: {TARGET}
Use dual discovery: topic map exploration AND semantic search.
Add inline links where genuine connections exist — including sibling claims listed above.
Update relevant topic map with this claim.
ONE PHASE ONLY. Do NOT run reweave.
```

For **reweave** phase:

**Same sibling list** as reflect (re-query queue for freshest state):

```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: reweave | Target: {TARGET}

OTHER CLAIMS FROM THIS BATCH:
{for each sibling in batch where completed_phases includes "create":}
- [[{SIBLING_TARGET}]]
{end for}

Run /reweave --handoff for: {TARGET}
This is the BACKWARD pass. Find OLDER claims AND sibling claims
that should reference this claim but don't.
Add inline links FROM older claims TO this claim.
ONE PHASE ONLY. Do NOT run verify.
```

For **verify** phase:
```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: verify | Target: {TARGET}

Run /verify --handoff on: {TARGET}
Combined verification: recite (cold-read prediction test), validate (schema check),
review (per-note health).
IMPORTANT: Recite runs FIRST — read only title+description, predict content,
THEN read full claim.
Final phase for this claim. ONE PHASE ONLY.
```

### 4c. Spawn Subagent (MANDATORY — NEVER SKIP)

Call the Agent tool with the constructed prompt. Use the model and max_turns from daemon-config (loaded in Step 1a):

```
Agent(
  subagent_type = "general-purpose",
  prompt = {the constructed prompt from 4b},
  description = "{current_phase}: {short target}" (5 words max),
  model = {daemon-config models[current_phase] — e.g. "haiku" for verify, "sonnet" for reflect},
  max_turns = {daemon-config max_turns[current_phase] — e.g. 8 for verify, 15 for reflect}
)
```

**Phase-to-model lookup:** Map `current_phase` to daemon-config `models:` key: extract->reduce, create->create, enrich->enrich, reflect->reflect, reweave->reweave, verify->verify. Use the model value from that key. If key missing, default to sonnet (haiku for verify).

**REPEAT: You MUST call the Agent tool here.** Do NOT execute the prompt yourself. Do NOT "optimize" by running the task inline. The Agent tool call is the ONLY acceptable action at this step.

Wait for the subagent to complete and capture its return value.

### 4d. Evaluate Return

When the subagent returns:

1. **Look for RALPH HANDOFF block** — search for `=== RALPH HANDOFF` and `=== END HANDOFF ===` markers
2. **If handoff found:** Parse the Work Done, Learnings, and Queue Updates sections
3. **If handoff missing:** Log a warning but continue — the work was still completed
4. **Capture learnings:** If Learnings section has non-NONE entries, note them for the final report

### 4e. Update Queue (Phase Progression)

After evaluating the return, advance the task to the next phase.

**Phase progression logic:**

Look up `phase_order` from the queue header to determine the next phase. Find `current_phase` in the array. If there is a next phase, advance. If it is the last phase, mark done.

**If NOT the last phase** — advance to next:
- Set `current_phase` to the next phase in the sequence
- Append the completed phase to `completed_phases`

**If the last phase** (verify) — mark task done:
- Set `status: done`
- Set `completed` to current UTC timestamp
- Set `current_phase` to null
- Append the completed phase to `completed_phases`

**For extract tasks ONLY:** Re-read the queue after marking done. The reduce skill writes new task entries (1 entry per claim/enrichment with `current_phase`/`completed_phases`) to the queue during execution. The lead must pick these up for subsequent iterations.

### 4f. Report Progress

```
=== Task {id} complete ({i}/{N}) ===
Phase: {current_phase} -> {next_phase or "done"}
```

If learnings were captured, show a brief summary.
If more unblocked tasks exist, show the next one.

### 4g. Re-filter Tasks

Before the next iteration, re-read the queue and re-filter tasks. Phase advancement may have changed eligibility (e.g., after completing a `create` phase, the task is now at `reflect` — if filtering by `--type reflect`, it becomes eligible).

---

## Step 5: Post-Batch Cross-Connect (Serial Mode)

After advancing a task to "done" (Step 4e), check if ALL tasks in that batch now have `status: "done"`. If yes and the batch has 2 or more completed claims:

1. **Collect all note paths** from completed batch tasks. For each claim task with `status: "done"`, read the task file's `## Create` section to find the created note path.

2. **Spawn ONE subagent** for cross-connect validation:
```
Agent(
  subagent_type = "general-purpose",
  prompt = "You are running post-batch cross-connect validation for batch '{BATCH}'.

Notes created in this batch:
{list of ALL note titles + paths from completed batch tasks}

Verify sibling connections exist between batch notes. Add any that were missed
because sibling notes did not exist yet when the earlier claim's reflect ran.
Check backward link gaps. Output RALPH HANDOFF block when done.",
  description = "cross-connect: batch {BATCH}",
  model = {daemon-config models.cross_connect — default "sonnet"},
  max_turns = {daemon-config max_turns.cross_connect — default 15}
)
```

3. **Parse handoff block**, capture learnings. Include cross-connect results in the final report.

**Skip if:** batch has only 1 claim (no siblings) or tasks from the batch are still pending.

---

## Step 6: Parallel Mode (--parallel)

**When `--parallel` flag is present, SKIP Step 4 entirely and use this section instead.**

**Incompatible flags:**

1. `--parallel` cannot be combined with `--type`. Parallel mode processes claims end-to-end (all phases). If `--type` is also set, report an error:
```
ERROR: --parallel and --type are incompatible. Parallel processes full claim pipelines, not individual phases.
Use serial mode for per-phase filtering: /ralph N --type reflect
```

2. `--parallel` requires claim-pipeline tasks (type: claim). Extract tasks MUST run serially because each extraction produces new claim tasks that subsequent iterations need to pick up. If all pending tasks are extract-type, report an error:
```
ERROR: --parallel is not applicable. All {N} pending tasks are extract-phase.
Extract tasks must run serially -- each extraction creates new claim tasks that need sequential registration.
Use: /ralph {N}
```

### Parallel Architecture

**Two-phase design:** Workers receive sibling claim info upfront so they can link proactively. Phase B validates and catches any gaps.

```
Ralph Lead (you) — orchestration only
|
+-- PHASE A: PARALLEL CLAIM PROCESSING (concurrent)
|   +-- worker-001: all 4 phases for claim 001 (with sibling awareness)
|   +-- worker-002: all 4 phases for claim 002 (with sibling awareness)
|   +-- worker-003: all 4 phases for claim 003 (with sibling awareness)
|   +-- ...up to 5 concurrent workers
|
+-- [semantic search index sync]
|
+-- PHASE B: CROSS-CONNECT VALIDATION (one subagent, one pass)
|   +-- validates sibling links, adds any that workers missed
|
+-- CLEANUP + FINAL REPORT
```

**Why two phases?** Workers have sibling awareness (claim titles in spawn prompt) and link proactively during reflect/reweave. But timing means some sibling notes may not exist yet during a worker's reflect phase. Phase B runs a single cross-connect pass after all notes exist.

### 6a. Identify Parallelizable Claims

From the filtered queue, find pending **claim-pipeline tasks** (type: claim or type: enrichment). Extract tasks (type: extract) are NOT parallelizable -- they produce new tasks that require sequential registration.

**Guard check:** If after excluding extract tasks, zero claim-pipeline tasks remain, report the extract-only error from the incompatibility check above and fall back to serial mode (Step 4).

A claim is parallelizable when its `status == "pending"` and `type != "extract"`. Cap at 5 concurrent workers (or N, whichever is smaller).

Report:
```
=== Parallel Mode ===
Parallelizable claims: {count}
Excluded extract tasks: {extract_count} (serial only)
Max concurrent workers: {min(count, N, 5)}
```

### 6b. Spawn Claim Workers

For each parallelizable claim (up to N requested, max 5 concurrent):

Build the worker prompt with sibling awareness:

```
You are a claim worker processing claim "{TARGET}" from batch "{BATCH}".

Claim ID: {CLAIM_ID}
Task file: ops/queue/{FILE}
Current phase: {CURRENT_PHASE}
Completed phases: {COMPLETED_PHASES}

SIBLING CLAIMS IN THIS BATCH (link to these where genuine connections exist):
{for each other claim in the batch:}
- "{SIBLING_TARGET}" (task file: ops/queue/{SIBLING_FILE})
{end for}

During REFLECT and REWEAVE, check if your claim genuinely connects to any sibling.
If a sibling claim exists in notes/, link to it inline where the
connection is real. If it does not exist yet (still being created), skip —
cross-connect will catch it after.

Read the task file for full context. Execute phases from current_phase onwards.
If completed_phases is not empty, skip those phases (resumption mode).

When complete, update the queue entry to status "done" and report the created
claim title, path, and claim ID. The lead needs this for cross-connect.
```

Spawn via Agent tool with parallel worker budget from daemon-config:
```
Agent(
  subagent_type = "general-purpose",
  prompt = {the constructed prompt},
  description = "claim: {short target}" (5 words max),
  model = "sonnet",
  max_turns = {daemon-config max_turns.parallel_worker — default 30}
)
```

**Spawn workers in PARALLEL** — launch all Agent tool calls in a single message, not sequentially.

### 6c. Monitor Workers (Phase A)

Wait for worker completions. As workers complete:

1. **Parse completion message** — extract the created note title and path (needed for Phase B)
2. **Log any learnings** from the worker's report
3. **Check for issues** — failures, skipped phases, resource conflicts

**Collect all created notes** — maintain a list of `{note_title, note_path}` from worker completion messages. You need this for the cross-connect validation phase.

**Completion gate:** Phase B CANNOT start until ALL spawned workers have reported back (either success or error). Track completions:

```
Workers spawned: {total_spawned}
Workers completed: {completion_count}
Workers with errors: {error_count}

Phase B ready: {completion_count + error_count == total_spawned}
```

Do NOT proceed to Phase B while any worker is still running.

### 6d. Cross-Connect Validation (Phase B)

**Light validation pass.** Workers had sibling awareness during Phase A and linked proactively. This phase validates their work and catches gaps.

**Skip if only 1 claim was processed** (no siblings to cross-connect).

Spawn ONE subagent for cross-connect validation:

```
Agent(
  subagent_type = "general-purpose",
  prompt = "You are running post-batch cross-connect validation for batch '{BATCH}'.

Notes created in this batch:
{list of ALL newly created note titles with paths from Phase A}

Verify sibling connections exist between these notes. Add any connections that
workers missed because sibling notes did not exist yet when a worker's reflect ran.
Check backward link gaps. Output RALPH HANDOFF block when done.",
  description = "cross-connect: batch {BATCH}",
  model = {daemon-config models.cross_connect — default "sonnet"},
  max_turns = {daemon-config max_turns.cross_connect — default 15}
)
```

Parse the handoff block, capture learnings.

Report after Phase B:
```
=== Cross-Connect Validation Complete ===
Sibling connections validated: {count}
Missing connections added: {count}
```

### 6e. Cleanup

After Phase B completes (or after Phase A if cross-connect was skipped):

1. Clean any lock files if created
2. Skip to Step 7 for the final report, noting parallel mode in the output

---

## Step 7: Final Report

After all iterations (or when no unblocked tasks remain):

```
--=={ ralph }==--

Processed: {count} tasks
  {breakdown by phase type}

Subagents spawned: {count} (MUST equal tasks processed)

Learnings captured:
  {list any friction, surprises, methodology insights, or "None"}

Queue state:
  Pending: {count}
  Done: {count}
  Phase distribution: {create: N, reflect: N, reweave: N, verify: N}

Next steps:
  {if more pending tasks}: Run /ralph {remaining} to continue
  {if batch complete}: Run /archive-batch {batch-id}
  {if queue empty}: All tasks processed
```

**Verification:** The "Subagents spawned" count MUST equal "Tasks processed." If it does not, the lead executed tasks inline — this is a process violation. Report it as an error.

If `--handoff` flag was set, also output:

```
=== RALPH HANDOFF: orchestration ===
Target: queue processing

Work Done:
- Processed {count} tasks: {list of task IDs}
- Types: {breakdown by type}

Learnings:
- [Friction]: {description} | NONE
- [Surprise]: {description} | NONE
- [Methodology]: {description} | NONE
- [Process gap]: {description} | NONE

Queue Updates:
- Marked done: {list of completed task IDs}
=== END HANDOFF ===
```

---

## Error Recovery

**Subagent crash mid-phase:** The queue still shows `current_phase` at the failed phase. The task file confirms the corresponding section is empty. Re-running `/ralph` picks it up automatically — the task is still pending at that phase.

**Queue corruption:** If the queue file is malformed, report the error and stop. Do NOT attempt to fix it automatically.

**All tasks blocked:** Report which tasks are blocked and why. Suggest remediation.

**Empty queue:** Report "Queue is empty. Use /seed to add sources."

**YAML quoting validation block (create phase):** The validate_write hook blocks notes where YAML frontmatter values contain unquoted colons (`: `). Claims with numeric values in titles (e.g. "AUC 0.94", "29 percent") are high-risk for producing descriptions like `description: AUC 0.94: strong...` where the second colon triggers the block. The subagent sees a tool failure but may retry with similar phrasing and exhaust its turn budget. **Prevention:** The create phase prompt includes a CRITICAL reminder to double-quote all YAML string values. **If still failing:** the prescriptive hook message tells the subagent exactly how to fix it (wrap in double quotes).

---

## Skill Tool Fallback Protocol

The Skill tool can intermittently fail with "Unknown skill" errors after ~6-7 invocations per session. This is a known platform limitation. Direct SKILL.md reads are a first-class recovery mechanism, not an ad-hoc workaround.

### Recovery Procedure

When a `/skill` invocation fails with "Unknown skill" or similar tool errors:

1. **Read the SKILL.md directly** from the filesystem using the Read tool
2. **Follow the instructions** in the SKILL.md as if the Skill tool had loaded them
3. **Continue processing** -- do not abort the batch or retry the Skill tool

### Phase-to-Path Lookup

| Phase Skill | SKILL.md Path |
|-------------|---------------|
| /reduce | `.claude/skills/reduce/SKILL.md` |
| /reflect | `.claude/skills/reflect/SKILL.md` |
| /reweave | `.claude/skills/reweave/SKILL.md` |
| /verify | `.claude/skills/verify/SKILL.md` |
| /enrich | `.claude/skills/enrich/SKILL.md` |
| /ralph | `.claude/skills/ralph/SKILL.md` |

### Lead Session Responsibility

The lead session (ralph orchestrator) applies the same fallback. If the Skill tool fails when building a subagent prompt that references a skill, read the SKILL.md directly and include the relevant instructions in the subagent prompt.

### Subagent Responsibility

Subagents spawned by ralph also apply this fallback. If a subagent's `/reduce --handoff` call fails, it reads `.claude/skills/reduce/SKILL.md` directly and executes accordingly.

---

## Quality Gates

### Gate 1: Subagent Spawned
Every task MUST be processed via Agent tool. If the lead detects it executed a task inline, log this as an error and flag it in the final report.

### Gate 2: Handoff Present
Every subagent SHOULD return a RALPH HANDOFF block. If missing: log warning, mark task done, continue.

### Gate 3: Extract Yield
For extract tasks: if zero claims extracted, log as an observation. Do NOT retry automatically.

### Gate 4: Task File Updated
After each phase, the task file's corresponding section (Create, Reflect, Reweave, Verify) should be filled. If empty after subagent completes, log warning.

---

## Critical Constraints

**Never:**
- Execute tasks inline in the lead session (USE THE AGENT TOOL)
- Process more than one phase per subagent (context contamination)
- Retry failed tasks automatically without human input
- Skip queue phase advancement (breaks pipeline state)
- Process tasks that are not in pending status
- Run if queue file does not exist or is malformed
- In parallel mode: combine with --type (incompatible)

**Always:**
- Spawn a subagent via Agent tool for EVERY task (the lead ONLY orchestrates)
- Include sibling claim titles in reflect and reweave prompts
- Re-read queue after extract tasks (subagent adds new entries)
- Re-filter tasks between iterations (phase advancement creates new eligibility)
- Log learnings from handoff blocks
- Report failures clearly for human review
- Verify subagent count equals task count in final report
