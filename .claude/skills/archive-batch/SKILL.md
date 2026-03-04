---
name: archive-batch
description: Archive completed processing batches. Moves task files to archive, generates SUMMARY.md, flags queue entries as archived. Triggers on "/archive-batch", "/archive-batch {batch-id}", "/archive-batch --all".
version: "1.0"
generated_from: "arscontexta-v1.6"
user-invocable: true
context: fork
model: haiku
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
argument-hint: "{batch-id} | --all — archive a completed batch or all completed batches"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse arguments:
- `{batch-id}` (required unless --all): the batch ID to archive
- `--all`: archive all batches where every queue entry has `status: done`

**START NOW.** Archive the completed batch.

---

## Step 1: Read Queue

Read the queue file (check `ops/queue/queue.json`, `ops/queue/queue.yaml`, `ops/queue.yaml` in order).

Parse all entries. Group by `batch` field.

## Step 2: Identify Target Batches

**Single batch mode (`{batch-id}`):**
- Find all queue entries where `batch == {batch-id}` OR `id == {batch-id}` (for extract tasks).
- Verify ALL entries for the batch have `status: done`.
- If any entry is NOT done, abort:
  ```
  ERROR: Batch {batch-id} has {N} entries not yet done:
    {id} -- {current_phase} ({status})
  Complete processing before archiving.
  ```

**All mode (`--all`):**
- Group queue entries by `batch`.
- For each batch, check if ALL entries have `status: done`.
- Collect batches where every entry is done.
- If no batches qualify, report: "No completed batches to archive."

## Step 3: Archive Each Batch

For each qualifying batch:

### 3a. Locate Archive Folder

The archive folder was created by /seed: `ops/queue/archive/{date}-{batch-id}/`

```bash
ARCHIVE_DIR=$(ls -d ops/queue/archive/*-${BATCH_ID}* 2>/dev/null | head -1)
```

If no archive folder found, create one:
```bash
DATE=$(date -u +"%Y-%m-%d")
ARCHIVE_DIR="ops/queue/archive/${DATE}-${BATCH_ID}"
mkdir -p "$ARCHIVE_DIR"
```

### 3b. Move Extract Task File

The extract task file is batch-level provenance. Move it to the archive root (not tasks/).

```bash
# Extract task file: ops/queue/{batch-id}.md
mv "ops/queue/${BATCH_ID}.md" "${ARCHIVE_DIR}/${BATCH_ID}-extract.md"
```

### 3c. Move Claim and Enrichment Task Files

Move per-claim task files to the archive tasks/ subfolder.

```bash
mkdir -p "${ARCHIVE_DIR}/tasks"
# Claim/enrichment task files: ops/queue/{batch-id}-*.md
mv ops/queue/${BATCH_ID}-*.md "${ARCHIVE_DIR}/tasks/" 2>/dev/null
```

### 3d. Generate SUMMARY.md

Build a human-readable summary from queue entries and task file frontmatter.

```markdown
# Batch Summary: {batch-id}

## Metadata
- **Source**: {source path from extract task}
- **Seeded**: {created timestamp from extract entry}
- **Archived**: {current UTC timestamp}
- **Total claims**: {count of claim entries}
- **Total enrichments**: {count of enrichment entries}

## Claims

| # | Title | Type | Classification | Note Link |
|---|-------|------|----------------|-----------|
| 1 | {claim title} | {claim/enrichment} | {from task frontmatter if available} | [[{title}]] |
| 2 | ... | ... | ... | ... |

## Processing Timeline
- Seeded: {extract created timestamp}
- Extract completed: {extract completed timestamp}
- Last claim completed: {latest completed timestamp across all entries}
- Archived: {now}

## Key Connections
{If task files contain reflect/reweave sections with connections, summarize the top connections found across all claims. Otherwise: "See individual claim notes for connections."}
```

Write to `${ARCHIVE_DIR}/SUMMARY.md`.

### 3e. Update Queue Entries

For each queue entry in this batch, update:
- `status: "archived"`
- `archive_path: "{ARCHIVE_DIR}"`

Do NOT delete entries from the queue. Archived entries preserve provenance.

## Step 4: Report

```
--=={ archive-batch }==--

Archived: {batch-id}
  Source: {source file}
  Claims: {N} archived
  Files moved: {count}
  Archive: {ARCHIVE_DIR}
  Summary: {ARCHIVE_DIR}/SUMMARY.md

Queue: {N} archived, {M} remaining pending
```

For `--all` mode, report each batch on a separate line:
```
--=={ archive-batch --all }==--

Archived {K} batches:
  {batch-1}: {N} claims -> {archive-dir-1}
  {batch-2}: {N} claims -> {archive-dir-2}

Queue: {total_archived} archived, {remaining} pending
```

---

## Archive Folder Layout

```
ops/queue/archive/{date}-{batch-id}/
  {batch-id}.md              # original source (placed here by /seed)
  {batch-id}-extract.md      # extract task (batch-level provenance)
  SUMMARY.md                 # human-readable index
  tasks/                     # claim + enrichment processing records
    {batch-id}-001.md
    {batch-id}-007.md
```

## Design Rationale

- Queue entries flagged as `archived` (not deleted) to preserve the provenance chain.
- Extract task file at batch root (not in tasks/) because it is batch-level provenance, not a per-claim processing artifact.
- SUMMARY.md provides a human-readable index without needing to parse queue.json.

---

## Critical Constraints

**Never:**
- Archive a batch with pending or in-progress entries
- Delete queue entries (flag as archived instead)
- Overwrite an existing SUMMARY.md without reading it first

**Always:**
- Verify ALL batch entries are done before archiving
- Move the extract task file to archive root (not tasks/)
- Generate SUMMARY.md with claims table
- Update queue entries with archived status and archive_path
- Report clearly what was moved and where
