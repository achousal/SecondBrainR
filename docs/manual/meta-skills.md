---
description: "Deep guide to introspective commands -- ask, architect, rethink, remember"
type: manual
created: 2026-02-21
---

# Meta-Skills

Meta-skills are introspective commands that operate on the system itself rather than on research content. They query methodology, modify configuration, capture friction, and triage accumulated signals. These commands are the mechanism by which the system evolves.

---

## /ask -- Query the Methodology Knowledge Base

### Purpose

Answer questions about why the system is designed the way it is. Grounded in ops/methodology/ and the bundled arscontexta research base (interconnected methodology notes covering Zettelkasten theory, PKM research, atomic note design, and knowledge graph patterns).

### Invocation

```
/ask "why does my system use atomic notes?"
/ask "what are the trade-offs of condition-based maintenance?"
/ask "what research supports the prose-as-title pattern?"
/ask "how does wiki-link density affect knowledge retrieval?"
```

### How It Works

1. Parses the question to identify relevant methodology concepts.
2. Searches ops/methodology/ for vault-specific knowledge (learned behaviors, configuration rationale).
3. Searches the bundled research base for foundational evidence.
4. Synthesizes an answer that cites specific sources.

### When to Use

- When you are unsure why a constraint exists (e.g., "why can't I write directly to notes/?").
- When evaluating whether to change a dimension position.
- When the human asks about the theoretical basis for a vault design choice.
- Before running /architect, to understand the implications of a proposed change.

### Output

A grounded answer citing:
- Vault-specific rationale from ops/methodology/ and ops/derivation.md.
- Research evidence from the bundled knowledge base.
- Relevant dimension positions and their coherence relationships.

---

## /architect -- Restructure System Design

### Purpose

Modify the system's structural configuration by changing dimension positions, enabling/disabling feature blocks, or restructuring the vault's organizational principles. This is the principled alternative to ad-hoc config editing.

### Invocation

```
/architect "I want to switch from atomic to chunked granularity"
/architect "should I enable semantic search?"
/architect "the 3-tier navigation feels excessive for 20 claims"
/architect "I need a new domain for experimental methods alongside theory"
```

### How It Works

1. **Read current state** -- loads ops/config.yaml, ops/derivation.md, ops/derivation-manifest.md.
2. **Understand the request** -- classifies as dimension change, feature toggle, structural reorganization, or domain addition.
3. **Check coherence** -- evaluates hard constraints (blocking) and soft constraints (warnings). Reports all findings before proceeding.
4. **Propose changes** -- presents a concrete plan: which files change, what the new values are, what the expected effects are.
5. **Apply on approval** -- updates ops/config.yaml and writes a methodology note to ops/methodology/ documenting the change and its rationale.
6. **Validate** -- runs coherence checks on the new configuration.

### Coherence Checking

Every dimension change is checked against the constraint table:

**Hard constraints** (block the change):
- Atomic granularity requires at least 2-tier navigation.
- Full automation requires a platform that supports hooks.
- Heavy processing requires the processing pipeline to be enabled.

**Soft constraints** (warn but allow):
- Explicit+implicit linking without semantic search degrades implicit link quality.
- Atomic granularity with light processing produces shallow claims.
- Strict schema with minimal automation has no enforcement mechanism.

### What Gets Updated

| Change Type | Files Updated |
|-------------|---------------|
| Dimension position | ops/config.yaml, ops/methodology/ (rationale note) |
| Feature toggle | ops/config.yaml |
| Processing mode | ops/config.yaml (processing section) |
| Domain addition | Delegates to /add-domain |
| Full re-derivation | Delegates to /reseed |

### When to Use

- When the vault has grown or shrunk enough that a dimension position no longer fits.
- When friction patterns suggest a structural mismatch (e.g., "I keep creating orphan claims" might mean navigation depth is insufficient).
- When adding a new research domain.
- When preparing to enable a deferred feature (e.g., semantic search).

### Relationship to /reseed

/architect makes targeted changes to specific dimensions. /reseed re-derives the entire configuration from scratch, starting from preset selection. Use architect for incremental adjustments; use reseed for fundamental restructuring.

---

## /rethink -- Triage Observations and Tensions

### Purpose

Review accumulated friction signals (ops/observations/) and contradictions (ops/tensions/). Triage each item into an action category. This is the system's self-improvement mechanism.

### Invocation

```
/rethink
```

No arguments. Operates on all pending items in ops/observations/ and ops/tensions/.

### Accumulation Triggers

/rethink is suggested (not required) when:
- 10+ observations have accumulated in ops/observations/ with no triage.
- 5+ tensions have accumulated in ops/tensions/ with no resolution.

These thresholds are surfaced by the session-orient hook and /next.

### How It Works

For each pending observation:
1. Read the observation note (title, category, content).
2. Classify the action:
   - **PROMOTE** -- the observation contains durable knowledge. Create a claim in notes/.
   - **IMPLEMENT** -- the observation reveals a methodology improvement. Update ops/methodology/ or CLAUDE.md.
   - **ARCHIVE** -- the observation is noted but no action is needed. Move to archive/.
   - **KEEP PENDING** -- not enough signal yet. Leave in place.
3. Execute the chosen action.
4. Document the decision in the observation note.

For each pending tension:
1. Read the tension note (the two conflicting items, the nature of the conflict).
2. Determine resolution:
   - **Resolved** -- one side is correct. Update the incorrect claim, archive the tension.
   - **Dissolved** -- the conflict was apparent, not real (different scopes, different contexts). Document why, archive the tension.
   - **Escalated** -- the conflict is genuine and unresolvable with current knowledge. Create an open-question claim in notes/.
   - **KEEP PENDING** -- insufficient evidence to resolve. Leave in place.
3. Execute the chosen resolution.
4. Update the tension status (pending -> resolved | dissolved).

### Observation Categories

| Category | Description | Example |
|----------|-------------|---------|
| friction | Something that impedes work | "Search failed to find a claim I know exists" |
| surprise | Unexpected discovery during work | "Two unrelated pathways converge on the same target" |
| process-gap | Missing step in the workflow | "No way to batch-rename claims across topic maps" |
| methodology | Insight about how to work better | "Claims about experimental protocols need a different schema" |

### Tension Structure

```yaml
---
description: Brief statement of the conflict
status: pending     # pending | resolved | dissolved
claim_a: "[[claim one]]"
claim_b: "[[claim two]]"
---
```

### Output

A triage report listing:
- Each item processed
- Action taken (PROMOTE, IMPLEMENT, ARCHIVE, KEEP PENDING, resolved, dissolved, escalated)
- Rationale for the decision
- Any claims created, methodology notes updated, or tensions resolved

---

## /remember -- Capture Friction Signals

### Purpose

Capture a friction signal, surprise, process gap, or methodology insight immediately, without derailing the current work.

### Invocation

```
/remember "search failed to find the feedback loop claim despite exact title match"
/remember "the reweave step consistently takes longer than reduce -- scope might be too broad"
/remember "user corrected the schema: confidence 'likely' is not a valid enum value"
```

### How It Works

1. Creates an atomic note in ops/observations/ with:
   - Prose-sentence title (the observation itself)
   - Category inferred from content (friction, surprise, process-gap, methodology)
   - Timestamp
   - Status: pending
2. Continues the current work without interruption.

### When to Use

- When something goes wrong during work (search failure, unexpected behavior, user correction).
- When you discover something surprising that does not fit the current task.
- When the human says "remember this" or "always do X."
- When a process feels inefficient but you cannot fix it right now.

### Relationship to /rethink

/remember is the capture step. /rethink is the processing step. Observations accumulate via /remember until the threshold triggers /rethink.

### Automatic Capture

The session-capture hook (session-capture.sh) runs at session end. It can detect friction patterns from the session transcript and auto-create observation notes. This supplements manual /remember invocations.

---

## Self-Evolution Pattern

The four meta-skills compose into a self-evolution cycle:

```
Friction occurs during work
    |
    v
/remember -- capture the signal (ops/observations/)
    |
    v
Signals accumulate (10+ observations or 5+ tensions)
    |
    v
/rethink -- triage and act (PROMOTE, IMPLEMENT, ARCHIVE)
    |
    v
If IMPLEMENT: update methodology or configuration
    |
    v
/architect -- make structural changes if needed
    |
    v
/ask -- ground changes in research evidence
    |
    v
Monitor: did the friction decrease?
    |
    v
If not: /reseed for fundamental restructuring
```

### Rule Zero

ops/methodology/ is the source of truth for system behavior. Changes to system behavior update methodology FIRST. Drift between methodology and actual behavior is a high-priority tension.

### Complexity Arrives at Pain Points

The system does not add features because they seem useful. It adds them because friction proves they are needed. Every structural change should trace to an observation or tension that motivated it.

---

## See Also

- [Configuration](configuration.md) -- ops/config.yaml reference and dimension semantics
- [Workflows](workflows.md) -- how meta-skills fit into the session rhythm
- [Troubleshooting](troubleshooting.md) -- when meta-skills are the right response to a problem
