---
name: onboard-generate
description: "Generate all vault artifacts for onboarded projects. Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
argument-hint: "{data-file-path} -- path to temp file with corrected scan data"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Generate all vault artifacts from user-reviewed scan data. This is a computational sub-skill invoked by the /onboard orchestrator.

### Step 1: Read Input Data

Read the corrected scan data from the path provided in $ARGUMENTS. This file contains the user-reviewed and corrected version of the scan results (projects, infrastructure, institution, goals).

### Step 2: Read Reference Instructions

```
Read .claude/skills/onboard/reference/artifact-generation.md
Read .claude/skills/onboard/reference/conventions.md
```

### Step 3: Read Vault State

Read current state of files that will be modified:
- `projects/_index.md`
- `_research/data-inventory.md` (first 60 lines -- Summary Table)
- `self/goals.md`
- `ops/reminders.md`
- `ops/config.yaml` (for data_layers list)

If any are missing, create them per the Bootstrap procedure in the reference.

### Step 4: Generate Artifacts

Follow `reference/artifact-generation.md` to create all artifacts in order:

1. **Research goals** (5e) -- create `_research/goals/{slug}.md` for new goals
2. **Project notes** (5a) -- create `projects/{lab}/{tag}.md` with full schema
3. **Internal doc discovery** (5a2) -- scan and link research docs
4. **Symlinks** (5b) -- create `_dev/{tag}` symlinks
5. **Lab entity node** (5b2) -- create `projects/{lab}/_index.md`
6. **Projects index** (5c) -- update `projects/_index.md`
7. **Data inventory** (5d) -- update `_research/data-inventory.md`
8. **Goals update** (5g) -- update `self/goals.md`
9. **Reminders** (5h) -- update `ops/reminders.md`

### Step 5: Output File List

Output a structured list of all files created or modified:

```markdown
## ARTIFACTS CREATED

### Files Created
- {path} (type: {project|goal|lab|institution})
...

### Files Modified
- {path} (action: {appended rows|updated section})
...

### Symlinks Created
- _dev/{tag} -> {target}
...

### Summary
- Projects registered: {N}
- Goals created: {N}
- Data inventory entries: {N}
- Internal docs linked: {N}
- Reminders added: {N}
```
