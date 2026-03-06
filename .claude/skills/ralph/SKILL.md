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
- --unblock: show failed tasks and offer retry or skip options
- --retry TASK_ID: reset a specific failed task to pending for re-processing

**START NOW.** Process queue tasks.

---

## Step -1: Unblock / Retry Handling

**If `--unblock` is set:**
```bash
VAULT_PATH="$(pwd)"
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" alerts
```
Display failed tasks with their reasons and retry counts. For each failed task, offer:
- Retry: `cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" retry TASK_ID`
- Skip (leave failed): no action needed, failed tasks do not block the phase gate.

STOP after displaying. Do not process queue tasks.

**If `--retry TASK_ID` is set:**
```bash
VAULT_PATH="$(pwd)"
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" retry TASK_ID
```
Report result. If retry limit reached, inform user they can use `--force` by manually editing queue.json or running:
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" retry TASK_ID --force
```
STOP after retrying. Do not process queue tasks.

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

Each phase maps to a **named subagent** in `.claude/agents/`. Model, maxTurns, and tool access are enforced by the agent definition -- NOT by the Agent tool call site.

| Phase | Named Agent | Model | maxTurns | Rationale |
|-------|-------------|-------|----------|-----------|
| extract | `ralph-extract` | sonnet | 25 | Large sources need many passes |
| create | `ralph-create` | sonnet | 12 | Bounded: read task, write note (extra headroom for YAML retry) |
| enrich | `ralph-enrich` | sonnet | 8 | Bounded: read note, augment |
| reflect | `ralph-reflect` | sonnet | 15 | Dual discovery + MOC update |
| reweave | `ralph-reweave` | sonnet | 15 | Find + update older notes |
| verify | `ralph-verify` | haiku | 8 | Schema + recite + review |
| cross-connect | `ralph-cross-connect` | sonnet | 15 | Validate sibling links |

**Interactive sessions**: model and turn budgets are enforced by the named agent frontmatter in `.claude/agents/ralph-*.md`. No runtime config lookup needed.

**Daemon sessions**: model is enforced by the `claude -p --model` flag in `daemon.sh`, reading from `ops/daemon-config.yaml`. The daemon does not use named subagents.

To change a model for interactive use, edit the agent's frontmatter. To change for daemon use, edit `ops/daemon-config.yaml`. To keep both in sync, run `_code/scripts/sync_ralph_agents.py` (generates agent files from daemon-config).

Turn budgets are circuit breakers, not throttles. A bounded phase hitting its cap is probably lost; a semi-bounded phase hitting its cap was doing genuine work.

---

## Step 1: Read Queue State

Use the queue query CLI to read queue state. This avoids shell escaping issues with inline Python.

**Stats:**
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" stats
```
Returns JSON: `total`, `by_status`, `pending_by_phase`, `by_phase`.

**Actionable tasks** (with phase gate, batch grouping, pipeline ordering built in):
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" actionable [--limit N] [--type PHASE] [--batch ID]
```
Returns JSON: `actionable` (task list), `actionable_count`, `blocked` (phase gate results).

**Task details with siblings** (for building subagent prompts):
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" tasks --limit N --siblings [--type PHASE] [--batch ID]
```
Returns JSON: `tasks` (with full metadata + sibling list per task), `count`, `blocked`.

**Siblings for a single task:**
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" siblings TASK_ID
```

If the queue file does not exist, the CLI exits with an error. Report: "Queue is empty. Use /seed to add sources."

Set `VAULT_PATH` once at the start: `VAULT_PATH="$(pwd)"` (from vault root).

## Step 2: Filter Tasks

The queue query CLI handles filtering, phase eligibility gating, and batch grouping automatically. The `--type` and `--batch` flags map directly to user arguments. The phase gate enforces:

- If **any** tasks pending at `create` or `enrich`: `reflect` and `reweave` are blocked.
- If **any** tasks pending at `reflect`: `reweave` is blocked.
- `reduce` and `verify` are never blocked.

The CLI returns blocked tasks separately with reasons. Use the `actionable` or `tasks` subcommand output directly -- do NOT re-implement filtering in ad-hoc Python or shell.

The `phase_order` defines the phase sequence:
- `claim`: create -> reflect -> reweave -> verify
- `enrichment`: enrich -> reflect -> reweave -> verify

## Step 3: Queue Overview

Build the overview from CLI output. Run all three commands:
```bash
VAULT_PATH="$(pwd)"
cd _code
STATS=$(uv run python -m engram_r.queue_query "$VAULT_PATH" stats)
ACTIONABLE=$(uv run python -m engram_r.queue_query "$VAULT_PATH" actionable --limit 8)
ALERTS=$(uv run python -m engram_r.queue_query "$VAULT_PATH" alerts)
```

Parse the JSON to construct the display. **Canonical pipeline order** for display:
```
PIPELINE_ORDER = [reduce, create, enrich, reflect, reweave, verify]
```

Show the compact queue overview. Merge phase gate results, pipeline advisory tips, and actionable state into a single block:

```
--=={ ralph }==--

Queue: X pending, Y done, Z failed
Actionable: {count} ({N} reduce, {N} create, {N} enrich, ...)
Blocked: {N} reflect, {N} reweave -- {reason why, e.g. "35 enrich tasks must finish first so reflect sees the full claim surface"}
Failed: {N} tasks ({N} at retry limit) -- /ralph --unblock to review

Next:
1. {id} -- {current_phase} -- {target (truncated)}
2. {id} -- {current_phase} -- {target (truncated)}
...

Options:
- /ralph {N} --type reduce -- process extractions first
- /ralph {N} --type enrich -- clear enrich backlog (unlocks reflect)
- /ralph {N} -- all eligible tasks
- /ralph --unblock -- review and retry failed tasks
```

**Formatting rules:**
- `Actionable` line: group and label by `current_phase` (not `type`). List phases in PIPELINE_ORDER (reduce, create, enrich, reflect, reweave, verify). Drop phases with 0 actionable tasks. This is critical because `--type` filters on `current_phase`. Extraction tasks have `type: extract` but `current_phase: reduce` -- label them as `reduce` so the suggested `--type` commands match.
- `Blocked` line: only show if tasks were blocked by the phase gate. Include a SHORT rationale (one clause, not a paragraph) explaining why the earlier phase must finish first. If nothing is blocked, omit the line entirely.
- `Failed` line: only show if `failed_count > 0` from the alerts query. Show count and how many are at retry limit. Omit if no failed tasks.
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

**Idempotency guard:** Before dispatching, read the task file and check if the current phase's section (e.g. `## Create`, `## Reflect`) is already filled with content. If it IS already filled (from a previous crashed run), skip the subagent dispatch and advance the phase directly using:
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" advance TASK_ID
```
Log: `"Skipped {current_phase} for {id} -- section already filled (idempotency guard)"`. Continue to the next task.

Report:
```
=== Processing task {i}/{N}: {id} — phase: {current_phase} ===
Target: {target}
File: {file}
```

### 4b. Build Subagent Prompt

Use the CLI to get task details with siblings for the current batch of tasks:
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" tasks --limit N --siblings [--type PHASE] [--batch ID]
```

Parse the JSON output. Each task entry includes `id`, `type`, `target`, `batch`, `file`, `current_phase`, `completed_phases`, `source_detail`, and `siblings` (list of sibling tasks with their targets).

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

**Build verified sibling list:** Query the queue for other claims in the same batch where `completed_phases` includes "create". For each sibling, verify the note exists on disk using `Glob` for `notes/{SIBLING_TARGET}.md`. Only include siblings whose notes actually exist. This prevents dangling wiki links caused by title rewrites or failed creates.

```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: reflect | Target: {TARGET}

OTHER CLAIMS FROM THIS BATCH (check connections to these alongside regular discovery):
{for each sibling in batch where completed_phases includes "create"
 AND note verified to exist on disk:}
- [[{SIBLING_TARGET}]]
{end for, or "None yet" if no verified siblings}

Run /reflect --handoff on: {TARGET}
Use dual discovery: topic map exploration AND semantic search.
Add inline links where genuine connections exist — including sibling claims listed above.
Update relevant topic map with this claim.
ONE PHASE ONLY. Do NOT run reweave.
```

For **reweave** phase:

**Same verified sibling list** as reflect (re-query queue for freshest state, re-verify existence on disk):

```
Read the task file at ops/queue/{FILE} for context.

You are processing task {ID} from the work queue.
Phase: reweave | Target: {TARGET}

OTHER CLAIMS FROM THIS BATCH:
{for each sibling in batch where completed_phases includes "create"
 AND note verified to exist on disk:}
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

### 4c. Spawn Named Subagent (MANDATORY -- NEVER SKIP)

Call the Agent tool with the **named subagent** for the current phase. Model, maxTurns, and tool access are enforced by the agent definition -- you do NOT pass these at the call site.

```
Agent(
  subagent_type = "ralph-{current_phase}",
  prompt = {the constructed prompt from 4b},
  description = "{current_phase}: {short target}" (5 words max)
)
```

**Phase-to-agent mapping:**

| current_phase | subagent_type |
|---------------|---------------|
| extract (reduce) | `ralph-extract` |
| create | `ralph-create` |
| enrich | `ralph-enrich` |
| reflect | `ralph-reflect` |
| reweave | `ralph-reweave` |
| verify | `ralph-verify` |

**NEVER use `general-purpose` for ralph tasks.** Named agents enforce model selection (e.g. haiku for verify, sonnet for reflect). Anonymous agents inherit the session model, which silently upgrades cost when the session runs on Opus.

**REPEAT: You MUST call the Agent tool here.** Do NOT execute the prompt yourself. Do NOT "optimize" by running the task inline. The Agent tool call is the ONLY acceptable action at this step.

Wait for the subagent to complete and capture its return value.

### 4d. Evaluate Return

When the subagent returns:

1. **Look for RALPH HANDOFF block** — search for `=== RALPH HANDOFF` and `=== END HANDOFF ===` markers
2. **If handoff found:** Parse the Work Done, Learnings, and Queue Updates sections
3. **If handoff missing AND task file section is empty:** The subagent failed to complete the phase. Mark the task as **failed** using the CLI:
   ```bash
   cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" fail TASK_ID --reason "subagent returned without handoff or task file update"
   ```
   Report the failure and continue to the next task. Do NOT advance the phase.
4. **If handoff missing BUT task file section is filled:** Log a warning but continue — the work was completed, just the handoff was missed.
5. **Capture learnings:** If Learnings section has non-NONE entries, note them for the final report

### 4e. Update Queue (Phase Progression)

After evaluating the return, advance the task to the next phase using the CLI:

```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" advance TASK_ID
```

The CLI auto-determines the next phase from the task's type and phase order. It handles both advancement and done-marking (including timestamps).

**Post-create target sync (MANDATORY after create phase):**

The create subagent may sharpen or rewrite the proposed title to satisfy prose-as-title rules. The queue `target` field must match the actual filename on disk, or all downstream sibling links will dangle.

After a **create** phase completes:
1. Read the task file's `## Create` section. Parse the `Created: [[actual title]]` wiki link.
2. If the actual title differs from the queue entry's `target`, update `target` in queue.json to match.
3. Also verify the note exists on disk: `Glob` for `notes/{actual title}.md`. If missing, mark the task as **failed**:
   ```bash
   cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" fail TASK_ID --reason "create phase completed but note not found on disk"
   ```

This sync ensures reflect, reweave, cross-connect, and verify all reference the real filename.

**Post-reweave target sync (MANDATORY after reweave phase):**

The reweave subagent may execute a title-sharpen rename signaled by enrich. The queue `target` field must match the actual filename on disk, or verify will reference a stale path.

After a **reweave** phase completes:
1. Read the task file's `## Reweave` section. Look for a `| rename |` row in the Changes Applied table.
2. If a rename row exists, parse the new title from the `[[old title]] -> [[new title]]` format.
3. If the new title differs from the queue entry's `target`, update `target` in queue.json to match.
4. Verify the note exists on disk: `Glob` for `notes/{new title}.md`. If missing, log a warning -- the rename may have failed silently.

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

After advancing a task to "done" (Step 4e), check for completed batches using the CLI:
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" batches --check-complete
```
This retroactively checks ALL batches, not just the one whose task was just advanced. It catches batches completed across multiple `/ralph` runs. If `complete_batches` is non-empty and has 2 or more claims:

1. **Collect all note paths** from completed batch tasks. For each claim task with `status: "done"`, read the task file's `## Create` section to find the created note path.

2. **Spawn ONE subagent** for cross-connect validation:
```
Agent(
  subagent_type = "ralph-cross-connect",
  prompt = "You are running post-batch cross-connect validation for batch '{BATCH}'.

Notes created in this batch:
{list of ALL note titles + paths from completed batch tasks}

Verify sibling connections exist between batch notes. Add any that were missed
because sibling notes did not exist yet when the earlier claim's reflect ran.
Check backward link gaps. Output RALPH HANDOFF block when done.",
  description = "cross-connect: batch {BATCH}"
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

During REFLECT and REWEAVE, verify each sibling note exists on disk (Glob for
notes/{SIBLING_TARGET}.md) BEFORE linking to it. Queue targets may differ from
actual filenames due to title sharpening during create. If a sibling note does
not exist under its queue target name, check the sibling's task file ## Create
section for the actual title. If it does not exist yet (still being created),
skip — cross-connect will catch it after.

Read the task file for full context. Execute phases from current_phase onwards.
If completed_phases is not empty, skip those phases (resumption mode).

When complete, update the queue entry to status "done" and report the created
claim title, path, and claim ID. The lead needs this for cross-connect.
```

Spawn via Agent tool using the named agent for the claim's current phase. For claims starting at `create`, use `ralph-create`. The parallel worker processes one phase, returns, and the orchestrator advances to the next phase and spawns the next named agent.

**Important:** Parallel mode still processes phases sequentially per claim -- it parallelizes ACROSS claims, not across phases within a claim. Each spawn uses the phase-appropriate named agent:

```
Agent(
  subagent_type = "ralph-{current_phase}",
  prompt = {the constructed prompt},
  description = "claim: {short target}" (5 words max)
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
  subagent_type = "ralph-cross-connect",
  prompt = "You are running post-batch cross-connect validation for batch '{BATCH}'.

Notes created in this batch:
{list of ALL newly created note titles with paths from Phase A}

Verify sibling connections exist between these notes. Add any connections that
workers missed because sibling notes did not exist yet when a worker's reflect ran.
Check backward link gaps. Output RALPH HANDOFF block when done.",
  description = "cross-connect: batch {BATCH}"
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
  Failed this run: {count} (reasons: ...)

Subagents spawned: {count} (MUST equal tasks dispatched, excludes idempotency skips)

Learnings captured:
  {list any friction, surprises, methodology insights, or "None"}

Queue state:
  Pending: {count}
  Done: {count}
  Failed: {count} ({N} at retry limit)
  Phase distribution: {create: N, reflect: N, reweave: N, verify: N}

Next steps:
  {if more pending tasks}: Run /ralph {remaining} to continue
  {if batch complete}: Run /archive-batch {batch-id}
  {if failed tasks}: Run /ralph --unblock to review failed tasks
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

**Subagent crash mid-phase:** The queue still shows `current_phase` at the failed phase. The task file confirms the corresponding section is empty. Re-running `/ralph` picks it up automatically — the task is still pending at that phase. If the subagent crashes repeatedly (handoff missing AND task file section empty), the task is marked `failed` automatically (Gate 2). Use `/ralph --unblock` to review and retry.

**Stuck pipeline (phase gate deadlock):** If all actionable tasks are blocked because of tasks stuck at earlier phases, check for `failed` tasks first:
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" alerts
```
Failed tasks do NOT block the phase gate. If pending tasks are genuinely stuck (subagent keeps failing), mark them failed manually:
```bash
cd _code && uv run python -m engram_r.queue_query "$VAULT_PATH" fail TASK_ID --reason "description"
```
This unblocks downstream phases immediately.

**Retry exhaustion:** Tasks that hit the retry limit (8 attempts) remain `failed` and require manual intervention: either fix the underlying issue and force-retry, or accept the loss and archive.

**Queue corruption:** If the queue file is malformed, report the error and stop. Do NOT attempt to fix it automatically.

**All tasks blocked:** Report which tasks are blocked and why. Suggest remediation. Check alerts for failed tasks that may be resolvable.

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
Every subagent SHOULD return a RALPH HANDOFF block. If missing AND task file section is empty: mark task **failed** via CLI. If missing BUT task file section is filled: log warning, advance phase.

### Gate 3: Extract Yield
For extract tasks: if zero claims extracted, mark task **failed** via CLI with reason `"zero-claim extraction"`. Do NOT advance to done. Do NOT retry automatically.

### Gate 4: Task File Updated
After each phase, the task file's corresponding section (Create, Reflect, Reweave, Verify) should be filled. If empty after subagent completes AND no handoff: mark task **failed** (see Gate 2). If empty but handoff present with work done: log warning, advance cautiously.

### Gate 5: Idempotency
Before dispatching a subagent, check if the task file's current phase section is already filled. If yes: skip dispatch, advance phase directly via CLI. Log as idempotency skip.

---

## Critical Constraints

**Never:**
- Execute tasks inline in the lead session (USE THE AGENT TOOL)
- Process more than one phase per subagent (context contamination)
- Retry failed tasks automatically without human input
- Skip queue phase advancement (breaks pipeline state)
- Process tasks that are not in pending status (failed tasks require explicit retry first)
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
