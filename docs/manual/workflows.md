---
description: "Processing pipeline, maintenance cycle, session rhythm, batch processing, and co-scientist loop"
type: manual
created: 2026-02-21
---

# Workflows

This page documents how the system's skills compose into repeatable work patterns: the processing pipeline, the co-scientist loop, the session rhythm, maintenance cycles, and batch processing strategies.

---

## Processing Pipeline

Every piece of content follows: capture - reduce - reflect - reweave - verify. Each phase has a distinct purpose and operates best with focused attention.

### Phase 1: Capture

**Purpose:** Zero-friction intake.
**Destination:** inbox/
**Method:** Place raw material in inbox/ by any means -- file copy, /learn output, manual paste. Speed of capture beats precision of filing.

Content types that enter through inbox/:
- Research papers (PDFs, markdown summaries)
- Web research output from /learn
- Notes from conferences, conversations, seminars
- Raw data observations
- Literature summaries from /literature

### Phase 2: Reduce

**Purpose:** Transform raw material into structured claims.
**Command:** `/reduce inbox/source-file.md`
**Output:** One or more claim notes in notes/

Reads the source through the domain lens. Extracts claims across six categories:

| Category | What to Find | Output |
|----------|-------------|--------|
| Claims | Testable assertions about mechanisms, effects, relationships | claim note |
| Evidence | Data points, measurements, statistical results | claim note |
| Methodology comparisons | How different studies approached similar questions | claim note |
| Contradictions | Results conflicting with existing claims | claim note (+ tension in ops/tensions/) |
| Open questions | Gaps, unresolved mechanisms, future directions | claim note |
| Design patterns | Reusable experimental designs, analytical approaches | claim note |

**Quality bar for extracted claims:**
- Title works as prose when linked
- Description adds information beyond the title
- Claim is specific enough to disagree with
- Reasoning is visible in the body

**Selectivity** is configured in ops/config.yaml (strict, moderate, permissive). Default: moderate.

### Phase 3: Reflect

**Purpose:** Integrate new claims into the existing knowledge graph.
**Command:** `/reflect`
**Output:** Updated claims with wiki links, updated topic maps

Three operations:
1. **Forward connections** -- search for existing claims that relate to the new one. Add inline wiki links where the relationship is propositional.
2. **Backward connections** -- identify older claims that should reference the new one. Update those claims.
3. **Topic map membership** -- ensure every claim appears in at least one topic map with context.

### Phase 4: Reweave

**Purpose:** Revisit older claims in light of new knowledge.
**Command:** `/reweave "claim title"`
**Output:** Updated claim with revised content and connections

Asks: "If I wrote this claim today, what would be different?" This is not a light touch-up. Reweaving is completely reconsidering a claim: add connections, rewrite content, sharpen the proposition, split bundled ideas, challenge with new evidence.

**Scope** is configured in ops/config.yaml:
- **related** (default) -- only claims directly connected to the new claim
- **broad** -- claims within two hops
- **full** -- all claims (expensive, use sparingly)

**Frequency** is configured in ops/config.yaml:
- **after_create** (default) -- reweave triggers after each reduce
- **periodic** -- batch reweaving on a schedule
- **manual** -- only when explicitly invoked

### Phase 5: Verify

**Purpose:** Quality-check the claim against standards.
**Command:** `/verify "claim title"`
**Output:** Verification report and applied fixes

Three checks:
1. **Cold-read test** -- read only the title and description. Predict the claim's content. Read the body. If the prediction missed major content, the description needs improvement.
2. **Schema compliance** -- required fields present, enum values valid, description within length limit.
3. **Link health** -- all wiki links resolve to real files, claim is not orphaned.

---

## Pipeline Orchestration

### Processing Depth

Configured via `processing.depth` in ops/config.yaml:

| Depth | Behavior | Use Case |
|-------|----------|----------|
| deep | Full pipeline, fresh context per phase, maximum quality gates | Important sources, foundational papers |
| standard | Full pipeline, balanced attention | Default for most work |
| quick | Compressed pipeline, combine phases | High-volume catch-up, inbox backlog |

### Pipeline Chaining

Configured via `processing.chaining` in ops/config.yaml:

| Mode | Behavior |
|------|----------|
| manual | Each skill outputs "Next: /[skill] [target]" -- you decide when to proceed |
| suggested | Skills output next step AND add to task queue (default) |
| automatic | Skills complete, then next phase runs immediately |

### Full Processing Invocation

**Single file:**
```
/seed inbox/source-file.md
```
Then: /ralph 1 --batch source-file

**All inbox:**
```
/seed --all
```
Then: /ralph N

**Batch queue processing with fresh context:**
```
/seed inbox/important-paper.md   # creates extract task in queue
/ralph 1                          # processes queued task with isolated context per phase
```

/ralph processes tasks already in the queue, not inbox files directly. /seed must run first.

---

## Task Queue

Pipeline tasks are tracked in ops/queue/queue.json. Each claim progresses through phases:

```
create -> reflect -> reweave -> verify
```

Task files accumulate notes across phases -- they are the shared state between phases.

### Viewing the Queue

```
/tasks
/tasks --phase reflect
/tasks --status pending
```

### Queue + Maintenance Integration

/next evaluates both pipeline queue and maintenance conditions on each invocation. It recommends the single highest-priority action.

---

## Co-Scientist Loop

The hypothesis research loop is distinct from the processing pipeline but operates on the same vault.

### The Self-Improving Cycle

The co-scientist loop (see [Architecture](architecture.md) for diagram):

1. **/research** -- set a research goal, choose the next step.
2. **/generate** -- create hypotheses (4 modes: literature synthesis, self-play debate, assumption-based, research expansion).
3. **/review** -- evaluate hypotheses (6 modes: quick screen, literature review, deep verification, observation review, simulation review, tournament-informed).
4. **/tournament** -- rank hypotheses through pairwise Elo-rated debate.
5. **/meta-review** -- synthesize patterns from debates and reviews into recommendations.
6. Recommendations feed back into /generate and /evolve for the next cycle.

### When to Run Each Step

| Signal | Action |
|--------|--------|
| New research goal defined | /generate (literature synthesis mode) |
| 3+ unreviewed hypotheses | /review (quick screen first, then deeper modes) |
| 5+ reviewed hypotheses | /tournament (3-5 matches per round) |
| 2+ tournament rounds complete | /meta-review |
| Meta-review identifies gaps | /generate (research expansion mode) |
| Top hypotheses have known weaknesses | /evolve (grounding enhancement or simplification) |
| Hypothesis pool feels redundant | /landscape, then /evolve (combination or divergent) |

### Cross-Layer Integration

Claims in notes/ provide the knowledge substrate that hypotheses build upon. When /reduce extracts a claim that is relevant to an active research goal, the reflect phase should link it to relevant hypotheses. When /literature creates a literature note, it feeds into /generate's evidence base.

---

## Session Rhythm

### Orient (Automatic)

The session-orient hook fires at SessionStart and prints:
1. Active threads from self/goals.md
2. Overdue reminders from ops/reminders.md
3. Vault state counts (claims, inbox, observations, tensions)
4. Maintenance signals (inbox pressure, observation/tension thresholds)

Additionally, the co-scientist orient hook prints:
1. Active research goals from _research/goals/
2. Top hypotheses from _research/hypotheses/_index.md
3. Latest meta-review summary

### Work

Execute tasks based on orient output and user priorities. Common work patterns:

**Knowledge processing session:**
1. Check inbox for unprocessed items.
2. Run /reduce on highest-priority item.
3. Run /reflect on extracted claims.
4. Run /next for the recommended next action.

**Hypothesis research session:**
1. Check research goal state.
2. Run the next step in the co-scientist loop (based on /research menu).
3. If meta-review recommends gaps, run /generate.

**Maintenance session:**
1. Run /health for a full check.
2. Address orphan claims via /reflect.
3. Fix dangling links.
4. Run /rethink if observations or tensions have accumulated.

### Persist (Automatic + Manual)

Before session end:
- Write new insights as claims (via /seed or /reduce).
- Update relevant topic maps.
- Update self/goals.md with current threads.
- The session-capture hook fires automatically, recording a session summary to ops/sessions/.
- The auto-commit hook stages and commits vault changes.

---

## Maintenance Cycle

Maintenance is condition-based, not calendar-based. Conditions are evaluated by /next at each invocation and by the session-orient hook at session start.

### Condition Table

| Signal | Threshold | Action | Priority |
|--------|-----------|--------|----------|
| Orphan claims | Any detected | /reflect on orphans | High |
| Dangling links | Any detected | Fix or create target claims | High |
| Inbox pressure | Items older than 3 days | /seed then /ralph | Medium |
| Pending observations | 10+ accumulated | /rethink | Medium |
| Pending tensions | 5+ accumulated | /rethink | Medium |
| Topic map size | >40 claims | /refactor (split) | Low |
| Schema violations | Any detected | /validate then fix | Low |
| Stale content | Claims not updated in 30+ days | /reweave | Low |

### Self-Healing Properties

Conditions auto-resolve: fix the underlying problem and the maintenance task disappears. No manual task management required -- the system evaluates conditions fresh on each /next invocation.

---

## Batch Processing

### Inbox Backlog

When inbox/ accumulates multiple items:

```
/seed --all then /ralph N
```

Or process individually with quick depth:
```
# Temporarily switch to quick processing
# (edit ops/config.yaml: processing.depth: quick)
/reduce inbox/item-1.md
/reduce inbox/item-2.md
# Then batch reflect
/reflect
```

### Batch Validation

```
/validate
```

Checks all claims in notes/ against the schema. Produces a report of violations.

### Batch Health Check

```
/health
```

Runs orphan detection, dangling link detection, schema validation, topic map coherence, and stale content checks across the entire vault.

---

## Provenance Chain

Every claim maintains a traceable chain from source to processed output:

```
source query -> inbox/ file (provenance metadata) -> /reduce -> notes/ claim
```

Standard provenance fields in inbox YAML:
```yaml
source_type: research | web-search | manual | import
research_prompt: "the query that generated this content"
generated: "2026-02-21T15:30:00Z"
```

The `source` field in each claim links back to the inbox file via wiki link, preserving the full chain.

---

## See Also

- [Skills Reference](skills.md) -- detailed command reference
- [Configuration](configuration.md) -- how to adjust depth, chaining, and dimensions
- [Troubleshooting](troubleshooting.md) -- handling pipeline failures and quality issues
