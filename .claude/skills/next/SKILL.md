---
name: next
description: Surface the most valuable next action by combining task stack, queue state, inbox pressure, health, and goals. Recommends one specific action with rationale. Triggers on "/next", "what should I do", "what's next".
version: "2.0"
generated_from: "arscontexta-v1.6"
user-invocable: true
context: fork
model: sonnet
allowed-tools: Read, Grep, Glob, Bash
---

## Runtime Configuration (Step 0 -- before any processing)

Read these files to configure domain-specific behavior:

1. **`ops/config.yaml`** -- thresholds, processing preferences
   - `self_evolution.observation_threshold` (default: 10)
   - `self_evolution.tension_threshold` (default: 5)

## EXECUTE NOW

**INVARIANT: /next recommends, it does not execute.** Present one recommendation with rationale. The user decides what to do. This prevents cognitive outsourcing where the system makes all work decisions and the user becomes a rubber stamp.

**Execute these steps IN ORDER:**

---

### Step 1: Get Recommendation from Decision Engine

Run the unified decision engine CLI:

```bash
VAULT_PATH="$(pwd)"
DECISION=$(cd _code && uv run python -m engram_r.decision_engine "$VAULT_PATH" 2>/dev/null)
EXIT=$?
```

Parse the JSON output. The engine returns:

```json
{
  "mode": "standalone|daemon",
  "recommendation": {
    "action": "specific command or task",
    "rationale": "why this action",
    "priority": "session|multi_session|slow|tier3|clean",
    "category": "task_stack|maintenance|research|tier3|clean",
    "after_that": "second priority if relevant"
  },
  "state_summary": {
    "health_fails": 0,
    "health_stale": false,
    "observations": 6,
    "tensions": 1,
    "queue_backlog": 0,
    "orphan_notes": 0,
    "inbox": 0,
    "unmined_sessions": 0,
    "stale_notes": 0,
    "task_stack_active": 3,
    "task_stack_pending": 15,
    "goals": [{"goal_id": "...", "cycle_state": "...", "hypothesis_count": 12}]
  },
  "daemon_context": {
    "running": false,
    "pid": 0,
    "completed": [],
    "alerts": [],
    "for_you": []
  }
}
```

**If exit code 1 (error):** Fall back to Step 1-fallback.

---

### Step 2: Enrich with Advisor Suggestions

When the engine recommendation action contains `/literature` or `/generate`, call the vault advisor for goal-aware content suggestions:

```bash
ADVISOR=$(cd _code && uv run python -m engram_r.vault_advisor "$VAULT_PATH" \
    --context literature --max 4 2>/dev/null)
ADVISOR_EXIT=$?
```

If `$ADVISOR_EXIT` is 0 and `$ADVISOR` contains valid JSON, parse `suggestions` array and append to the output block:

```
  Suggested queries:
    1. [query] (goal: [goal_ref]) -- [rationale]
    2. ...
```

If the advisor fails or returns no suggestions (`exit 2`), proceed without them. This enrichment is optional -- it provides content-specific guidance but the recommendation is valid without it.

For `/generate` recommendations, use `--context generate` instead of `--context literature`.

**Phase ordering tips enrichment:** When the engine recommendation involves `/ralph` or queue processing, also call the advisor with phase tips:

```bash
ADVISOR=$(cd _code && uv run python -m engram_r.vault_advisor "$VAULT_PATH" \
    --context ralph --include-phase-tips --max 4 2>/dev/null)
```

If phase tips are present (channel `phase_tip`), show them before the recommendation:

```
  Phase advisory:
    - [tip message]
```

This helps the user understand optimal phase ordering before starting queue processing.

---

### Step 1-fallback: Manual Signal Collection

If the decision engine CLI fails (Python not available, import error, missing config), fall back to manual bash-based signal collection:

```bash
# Task stack
TASK_ACTIVE=$(grep -c '^- ' ops/tasks.md 2>/dev/null || echo 0)

# Inbox pressure
INBOX_COUNT=$(find inbox/ -name "*.md" -maxdepth 2 2>/dev/null | wc -l | tr -d ' ')

# Pending observations
OBS_COUNT=$(grep -rl '^status: pending' ops/observations/ 2>/dev/null | wc -l | tr -d ' ')

# Pending tensions
TENSION_COUNT=$(grep -rl '^status: pending\|^status: open' ops/tensions/ 2>/dev/null | wc -l | tr -d ' ')

# Unmined sessions
SESSION_COUNT=$(find ops/sessions/ -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
```

Then apply the priority cascade manually:
1. Task stack active items (read ops/tasks.md, recommend first Active item)
2. Session-priority: orphans > 0, inbox > 5, observations >= 10, tensions >= 5, sessions > 3
3. Multi-session: queue > 10, stale notes > 10
4. Slow: health stale
5. Clean: suggest exploratory work

---

### Step 3: Reconcile Maintenance Queue (optional)

If queue file exists (`ops/queue/queue.json`), reconcile maintenance conditions based on engine state_summary. Auto-close satisfied conditions, create tasks for new threshold breaches. Skip silently if queue is not active.

---

### Step 4: Deduplicate

Read `ops/next-log.md` (if it exists). Check the last 3 entries against the engine recommendation.

**Deduplication rules:**
- If the same recommendation appeared in the last 2 entries, select the `after_that` action instead
- This prevents the system from getting stuck recommending the same thing repeatedly when the user has chosen not to act on it
- If the same recommendation is genuinely the highest priority (e.g., inbox pressure keeps growing), add an explicit note: "This was recommended previously. The signal has grown stronger since then ([before] -> [now])."

---

### Step 5: Output

**Standalone mode (daemon NOT running):**

```
next

  State:
    Inbox: [count] items
    Observations: [count] | Tensions: [count]
    Task stack: [active count] active, [pending count] pending
    [any other decision-relevant signals from state_summary]

  Recommended: [action from engine recommendation]

  Rationale: [rationale from engine, expanded with
  domain vocabulary and goal context]

  After that: [after_that from engine, if present]
```

**Daemon mode (daemon IS running):**

```
next

  Daemon: running (PID [pid])
    Recent: [last 2-3 completed tasks from daemon_context]

  State:
    Tier 3 queue: [count] items pending your review
    Task stack: [active count] active

  Recommended: [action from engine recommendation]

  Rationale: [rationale, including what daemon completed
  that enables this]

  Also queued: [after_that from engine]
```

If daemon alerts exist, surface them before the recommendation:

```
  Daemon: running (PID [pid]) -- ALERT
    [alert text from daemon_context.alerts]

    Recent: [last 2-3 completed tasks]
  ...
```

**Command specificity is mandatory.** Recommendations must be concrete invocations:

| Good | Bad |
|------|-----|
| `/reduce inbox/article-on-spaced-repetition.md` | "process some inbox items" |
| `/ralph` or `/ralph 5` | "work on the queue" |
| `/rethink` | "review your observations" |
| `/reweave [[note title here]]` | "update some old notes" |

**Tool behavior constraints (do not contradict in rationale):**
- `/ralph` without N shows a queue overview and asks the user how many to process. It NEVER processes the full queue automatically. Never say "without a batch limit" or imply unlimited processing.

**State display rules:**
- Show only 2-4 decision-relevant signals -- not all fields from state_summary
- Zero-count signals that are healthy can be omitted
- Non-zero signals at session or multi-session priority should always be shown
- In daemon mode: show daemon health context instead of vault-level signals the daemon owns

---

### Step 6: Log the Recommendation

Append to `ops/next-log.md` (create if missing):

```markdown
## YYYY-MM-DD HH:MM

**Mode:** standalone | daemon
**State:** Inbox: [N] | Notes: [N] | Orphans: [N] | Dangling: [N] | Stale: [N] | Obs: [N] | Tensions: [N] | Queue: [N]
**Recommended:** [action]
**Rationale:** [one sentence]
**Priority:** session | multi-session | slow | tier-3
```

**Why log?** The log serves three purposes:
1. Deduplication -- prevents recommending the same action repeatedly
2. Evolution tracking -- shows what signals have been persistent vs transient
3. /rethink evidence -- persistent recommendations that go unacted-on may reveal misalignment between what the system detects and what the user values

---

## Edge Cases

### Empty Vault (0-5 notes)

If 0 claims and 0 inbox, recommend `/onboard` first -- it creates project notes, data inventory, research goals, and vault wiring that everything else builds on. After onboarding, recommend `/init` to seed orientation claims and methodological foundations. Maintenance is premature with < 5 notes.

After /init, if inbox is empty and no literature notes exist, recommend adding 3-5 foundational papers to inbox/ and running /seed then /ralph before /literature. Known papers (lab publications, grant references) build the graph scaffolding that makes /literature results connectable. Process in small batches -- do not queue more than ~10 unprocessed items. After /literature creates literature notes, recommend /ralph to process them through the queue before /research.

### Everything Clean

The engine returns priority "clean". Say so explicitly. Recommend exploratory work aligned with goals:

```
  No urgent work detected. Consider:
  - Exploring a research direction from goals.md
  - Reweaving older notes to deepen connections
  - Reviewing and updating goals.md itself
```

### No Goals File

Recommend creating `self/goals.md` first. Without priorities, recommendations lack grounding.

### Daemon Running But No "For You" Items

Engine handles this -- returns task stack items or clean state.

### Daemon Running With Alerts

Engine includes alerts in daemon_context. Surface them prominently before the recommendation.

### Queue Not Active

Skip queue reconciliation silently.

### Multiple Session-Priority Signals

Engine picks highest-impact signal with dedup. If the engine's pick was recently recommended, use after_that instead.

---

## Anti-Patterns

| Anti-Pattern | Why It Is Wrong | What to Do Instead |
|-------------|----------------|-------------------|
| Recommending everything | Overwhelms the user | Pick ONE. Mention a second only as "after that" |
| Vague recommendations | No actionable starting point | Name the specific file, note, or command |
| Ignoring task stack | User-set priorities exist for a reason | Engine checks task stack first |
| Repeating the same rec | Nagging if user chose not to act | Dedup via next-log.md |
| Recommending maintenance too early | A 5-note vault does not need health checks | Scale to vault maturity |
| Cognitive outsourcing | Making all decisions for the user | Recommend and explain -- never execute |
