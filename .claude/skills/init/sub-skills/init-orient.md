---
name: init-orient
description: "Read vault state and produce structured summary for /init orchestrator. Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: haiku
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
argument-hint: "(no arguments -- reads vault state)"
---

## EXECUTE NOW

Read vault state and produce a structured summary for the /init orchestrator.

### Step 1: Read Core State

Read agent identity:
- `self/identity.md`
- `self/methodology.md`
- `self/goals.md`

### Step 2: Count Existing Claims

```bash
ls notes/*.md 2>/dev/null | wc -l
```
Store as CLAIM_COUNT.

### Step 3: Read Research Goals

```bash
ls _research/goals/*.md 2>/dev/null
```

For each goal file found, read its frontmatter to extract: title, status, linked_labs, seeding_status.

**Seeding status mapping:** Derive a single status per goal from the `seeding_status` block:
- No `seeding_status` key at all -> `none`
- All phases (orientation, methodology, confounders, data_realities, inversions) are `complete` -> `complete`
- Any other combination (some complete, some missing) -> `partial`

Store each goal's mapped status for use in Step 6.

### Step 4: Read Vault Artifacts (for vault-informed generation)

**Lab conventions:**
```bash
ls projects/*/_index.md 2>/dev/null
```
For each, extract statistical_conventions and infrastructure fields.

**Project metadata:**
```bash
ls projects/*/*.md 2>/dev/null | grep -v _index
```
For each, extract language, linked_goals from frontmatter.

**Data inventory:**
Read `_research/data-inventory.md` (first 60 lines -- Summary Table only).

**Code tools:**
Read first 60 lines of `_code/src/engram_r/plot_stats.py` and `_code/R/stats_helpers.R` if they exist.

### Step 5: Check for Existing Seeding

For each goal, check if orientation claims already exist:
```bash
grep -rl "role: orientation" notes/*.md 2>/dev/null | head -20
```

### Step 6: Output Structured Summary

```markdown
## VAULT STATE

### Claim Count
{N}

### Goals
| Goal | Status | Labs | Seeding Status |
|------|--------|------|----------------|
{rows from goal files}

### Seeding Status Per Goal
GOAL_SEEDING:
- {goal-slug}: {none|partial|complete}
UNSEEDED_GOALS: {count of goals with status none or partial}

### Lab Conventions
{structured summary of statistical_conventions, infrastructure per lab}

### Data Inventory
{summary table rows if available}

### Code Tools Available
{detected statistical tests, plot types, helper functions}

### Existing Orientation Claims
{list of titles if any, grouped by goal}

### Vault Informed
{true|false -- whether onboard artifacts provide pre-population data}
```
