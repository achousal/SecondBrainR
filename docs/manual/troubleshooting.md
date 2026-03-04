---
description: "Diagnosis and resolution for orphan claims, dangling links, stale content, methodology drift, inbox overflow"
type: manual
created: 2026-02-21
---

# Troubleshooting

This page documents common failure modes, their symptoms, root causes, and resolution procedures.

---

## Orphan Claims

### Symptom
Claims exist in notes/ with zero incoming wiki links. They are invisible to graph traversal and will never be discovered by future sessions.

### Detection

```bash
# Using the vault helper script
./ops/scripts/orphan-notes.sh

# Or via /health
/health

# Or via /graph
/graph orphans
```

### Root Cause

Orphans arise from:
1. **Skipped reflect phase** -- claims created via /reduce but /reflect was not run afterward.
2. **Severed links** -- a claim that linked to this one was deleted or renamed without updating references.
3. **Pipeline bypass** -- a claim was created directly in notes/ without routing through the pipeline.

### Resolution

1. Run `/reflect` targeting the orphan claim to find connections.
2. Ensure the claim appears in at least one topic map's Core Ideas section with context.
3. If the claim has no natural connections, evaluate whether it belongs in notes/ at all. Claims that cannot connect to anything may be too vague or too narrow.

### Prevention

- Never skip the reflect phase after reduce.
- Use ops/scripts/rename-note.sh for all renames (it updates wiki links throughout the vault).
- Run /health periodically to catch orphans early.

---

## Dangling Links

### Symptom
Wiki links in claim bodies or topic maps point to filenames that do not exist. The link renders as unresolved in Obsidian and breaks graph traversal.

### Detection

```bash
# Using the vault helper script
./ops/scripts/dangling-links.sh

# Or via /health
/health
```

### Root Cause

1. **Manual deletion** -- a claim was deleted without searching for files that link to it.
2. **Typo in link** -- the wiki link was typed manually and does not match any filename.
3. **Rename without propagation** -- a claim was renamed outside of the rename script, leaving stale references.

### Resolution

For each dangling link:
1. **If the target should exist** -- create the claim via /seed or /reduce.
2. **If the target was renamed** -- update the link to the new filename. Search for the correct title with `rg 'partial title' notes/`.
3. **If the target was intentionally deleted** -- remove the link from the referencing file and update the surrounding prose.

### Prevention

- Never delete claims without first running `./ops/scripts/backlinks.sh "claim title"` to check incoming references.
- Always use `./ops/scripts/rename-note.sh "old title" "new title"` for renames.
- Never manually type wiki links -- search for the exact filename first.

---

## Stale Content

### Symptom
Claims that have not been updated in a long time (30+ days) may contain outdated information, missing connections to newer claims, or superseded conclusions.

### Detection

```bash
# Find claims by modification date
find notes/ -name '*.md' -mtime +30

# Or via /health (checks for stale content)
/health
```

### Root Cause

1. **No reweave pass** -- the claim was created but never revisited as new knowledge accumulated.
2. **Peripheral topic** -- the claim belongs to a topic that has not been active recently.
3. **Reweave scope too narrow** -- ops/config.yaml `reweave.scope: related` may not reach claims more than one hop away from recent work.

### Resolution

1. Run `/reweave "claim title"` on the stale claim.
2. Consider whether the claim is still accurate given current knowledge. If not, update or archive it.
3. Check if the claim's topic map has recent entries. If the topic itself is stale, it may need a focused reweave pass.

### Prevention

- Consider setting `reweave.scope: broad` in ops/config.yaml if staleness is a recurring problem.
- Use /graph to detect isolated clusters that may be drifting.
- Periodically run `/reweave` on topic maps to trigger cascading reweave of member claims.

---

## Methodology Drift

### Symptom
The system's actual behavior diverges from what is documented in ops/methodology/ or CLAUDE.md. Examples: processing depth in practice differs from config, claims are created without required fields, connect-then-verify order is reversed.

### Detection

This is typically noticed during work when behavior feels inconsistent, or when /ask returns an answer that contradicts observed behavior.

### Root Cause

1. **Config edit without methodology update** -- someone changed ops/config.yaml but did not update ops/methodology/ to reflect the new rationale.
2. **Gradual habit drift** -- shortcuts taken during quick processing sessions become normalized.
3. **Conflicting instructions** -- CLAUDE.md and ops/config.yaml specify different behaviors for the same operation.

### Resolution

1. Run `/remember "methodology drift: [specific observation]"` to capture the signal.
2. Compare ops/config.yaml values against ops/methodology/ documentation and CLAUDE.md instructions.
3. Determine the correct behavior and update the divergent source.
4. If the drift reveals a better approach, run `/architect` to formalize the change.

### Prevention

- Rule Zero: ops/methodology/ is the source of truth. Changes to behavior update methodology FIRST.
- Use /architect for all structural changes rather than direct config edits.
- The session-orient hook surfaces config state, making drift visible at session start.

---

## Inbox Overflow

### Symptom
inbox/ accumulates faster than it is processed. Items older than 3 days trigger the inbox pressure maintenance signal.

### Detection

The session-orient hook reports inbox item count at every session start and flags items older than 3 days. /next will recommend processing when inbox pressure is detected.

### Root Cause

1. **Collector's fallacy** -- saving material feels productive but is not. Capture outpaces processing.
2. **Processing depth too high** -- `deep` processing on every item is thorough but slow. Not all sources warrant deep processing.
3. **No batch processing** -- items are processed one at a time when batch mode would be more efficient.

### Resolution

**Immediate triage:**
1. Sort inbox items by priority (relevance to active research goals).
2. Archive items that are not relevant to current threads.
3. Process high-priority items first.

**Catch-up mode:**
1. Temporarily set `processing.depth: quick` in ops/config.yaml.
2. Run `/seed --all` then `/ralph N` for batch processing.
3. Return to `standard` depth after clearing the backlog.

**Structural fix:**
1. Increase extraction selectivity to `strict` -- extract fewer, higher-quality claims per source.
2. Set a WIP limit: process existing inbox before adding new items.
3. Reduce capture rate -- be more selective about what enters inbox/.

### Prevention

- WIP limit: process what you have before adding more.
- Match capture rate to processing capacity.
- Use `quick` depth for low-priority sources and reserve `deep` for foundational papers.
- /learn deposits directly into inbox/ with provenance -- this is a controlled source of intake.

---

## Schema Violations

### Symptom
Claims in notes/ have missing required fields, invalid enum values, or constraint violations. The validate-note.sh hook warns on writes, and /validate catches existing violations.

### Detection

```bash
# Batch validation
/validate

# Single-file check (via hook output)
# The validate-note.sh hook prints warnings on every Write to notes/
```

### Root Cause

1. **Manual file creation** -- claim created by hand without starting from the template.
2. **Schema evolution** -- a field was added to the template but existing claims were not backfilled.
3. **Corrupted YAML** -- frontmatter syntax error (missing quotes, misaligned indentation).

### Resolution

For each violation:
1. Read the claim and identify the missing or invalid field.
2. Add/fix the field based on _code/templates/claim-note.md.
3. For the `description` field: write a new description that adds information beyond the title (scope, mechanism, or implication; ~150 chars).
4. For `type` field: choose from claim, evidence, methodology, contradiction, pattern, question.
5. For `confidence` field: choose from established, supported, preliminary, speculative.

**Batch fix pattern:**
```bash
# Find all claims missing description
rg -L '^description:' notes/*.md

# Find claims with empty description
rg '^description:\s*$' notes/
rg '^description:\s*""' notes/
```

### Prevention

- Always create claims through the pipeline (/reduce, /seed) rather than manual file creation.
- Keep the validate-note.sh hook active -- it catches violations at write time.
- When evolving the schema, document the change in ops/methodology/ and plan a backfill pass.

---

## Topic Map Sprawl

### Symptom
Topic maps exceed 40 claims and become difficult to navigate. The map loses its function as an attention manager and becomes a flat list.

### Detection

```bash
# Count claims per topic map
for f in notes/*topic-map*.md; do
  echo "$(grep -c '\[\[' "$f") $f"
done | sort -rn

# Or via /health
/health
```

### Root Cause

Research domains can be inherently broad. Topics like "feedback mechanisms" or "measurement methodology" can accumulate claims rapidly, especially during literature review phases.

### Resolution

1. Identify natural sub-communities within the topic map (look for clusters of claims that link to each other more than to the rest).
2. Run `/refactor` to split the topic map into sub-topic maps.
3. The parent topic map becomes a domain topic map that links to the new sub-maps.
4. Each sub-map should have its own orientation, Core Ideas, Tensions, and Open Questions sections.

### Prevention

- Split proactively at 35 claims rather than waiting for 40.
- When adding claims to a topic map, check the current count first.
- Use 3-tier navigation: hub -> domain maps -> topic maps. Domain maps are natural split points.

---

## Duplicate Claims

### Symptom
Two or more claims in notes/ express the same insight with different titles or slightly different framing.

### Detection

```bash
# Search for similar descriptions
rg '^description:' notes/ | sort

# Or during /reflect, when forward-connection search reveals near-identical claims
```

### Root Cause

1. **No deduplication check** during reduce -- the same insight was extracted from different sources.
2. **Different framing** -- two claims express the same idea at different levels of specificity.
3. **Large vault** -- with many claims, it becomes harder to remember what already exists.

### Resolution

1. Determine which claim is stronger (better evidence, clearer framing, more connections).
2. Merge content from the weaker claim into the stronger one.
3. Update all wiki links that point to the weaker claim to point to the stronger one.
4. Archive or delete the weaker claim.
5. Use `/refactor` for assisted merging with link propagation.

### Prevention

- During reduce, always search notes/ for existing claims on the same topic before creating new ones.
- /reduce should check for duplicates as part of its quality gate.
- /landscape (in the co-scientist layer) flags near-duplicates in the hypothesis pool -- apply the same principle to claims.

---

## Session Context Degradation

### Symptom
Quality of connection-finding and claim extraction decreases as the conversation grows longer. The first claims in a processing batch are sharper than the last.

### Root Cause

LLM context windows degrade in quality as they fill. The first ~40% of context is the "smart zone." Processing many claims sequentially in one conversation dilutes attention.

### Resolution

1. Use `/ralph` for deep processing -- it invokes each phase in a separate context window.
2. For batch processing, process 3-5 claims per session, then start a new session.
3. Use `processing.depth: deep` for important sources -- this forces fresh context per phase.

### Prevention

- Configure `processing.chaining: suggested` (default) rather than `automatic` to maintain control over when context resets.
- Process the highest-priority items first, while context is freshest.
- For large inbox backlogs, spread processing across multiple sessions.

---

## Common Error Resolution

### "WARN: missing required 'description' field"

The validate-note.sh hook detected a claim without a description. Add a description to the YAML frontmatter:

```yaml
---
description: "One sentence adding context beyond the title"
---
```

### "WARN: empty description field"

The description exists but is blank. Write a description that adds scope, mechanism, or implication beyond what the title states. ~150 characters.

### Orphan detected but claim is in a topic map

The claim appears in a topic map's Core Ideas list but has no inline wiki links from other claims. Topic map membership is necessary but not sufficient -- claims also need inline connections from other claims to be fully integrated into the graph.

### /next recommends nothing

All conditions are satisfied, the task queue is empty, and the inbox is clear. This is the healthy steady state. Either continue on current research threads or add new material to inbox/.

---

## Diagnostic Commands Quick Reference

| Issue | Command |
|-------|---------|
| Full health check | `/health` |
| Orphan detection | `./ops/scripts/orphan-notes.sh` or `/graph orphans` |
| Dangling links | `./ops/scripts/dangling-links.sh` |
| Schema validation | `/validate` |
| Link density | `./ops/scripts/link-density.sh` |
| Backlinks for a claim | `./ops/scripts/backlinks.sh "claim title"` |
| Vault metrics | `/stats` |
| Next recommended action | `/next` |
| Graph topology | `/graph` |
| Task queue status | `/tasks` |

---

## See Also

- [Workflows](workflows.md) -- understanding the processing pipeline that prevents most issues
- [Configuration](configuration.md) -- adjusting dimensions to prevent structural mismatches
- [Meta-Skills](meta-skills.md) -- using /rethink and /remember for self-improvement
