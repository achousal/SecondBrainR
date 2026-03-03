---
name: onboard-scan
description: "Scan a lab directory for projects, conventions, and institutional resources. Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
argument-hint: "{lab-path} | {lab-path} --institution {name}"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Scan a lab directory and produce a structured summary of everything found. This is a computational sub-skill invoked by the /onboard orchestrator.

### Step 1: Parse Input

Extract lab path from $ARGUMENTS. If `--institution` is provided, extract institution name.

### Step 2: Read Reference Instructions

Read the detailed scan instructions:
```
Read .claude/skills/onboard/reference/scan-instructions.md
Read .claude/skills/onboard/reference/institution-lookup.md
```

### Step 3: Read Vault State

Read `ops/config.yaml` for `onboard:` section (scan_depth, exclude_dirs, exclude_files). Store as ONBOARD_CONFIG.

Collect registered project tags:
```bash
ls projects/*/*.md 2>/dev/null | xargs basename -a 2>/dev/null | sed 's/\.md$//'
```
Store as REGISTERED_TAGS.

### Step 4: Execute Scan

Follow the reference instructions to:
1. Discover project directories (2a)
2. Extract project metadata (2b)
3. Read CLAUDE.md files for auto-population (2c)
4. Mine conventions from code (2d)
5. Auto-detect per-project fields (2e)
6. Diff against vault (2f)

### Step 5: Institution Signal Detection

Follow `reference/institution-lookup.md` for detection logic, but **do not ask the user any questions**. Interactive steps (confirmation, lab website URL, /learn enrichment) are handled by the orchestrator in Review Turn 1/1b.

The scan agent's role is limited to:
1. Detect institution signals from scan data (CLAUDE.md, email domains, HPC cluster names, scheduler types)
2. Infer PI name from scan signals (CLAUDE.md, directory names, git config)
3. Check for existing institution profile in `ops/institutions/`
4. If profile exists, load it and include in output
5. Output all detected signals with evidence sources

Do NOT invoke /learn or WebFetch for institution data. The orchestrator runs enrichment after user confirmation to avoid wasted lookups on incorrect auto-detection.

### Step 6: Output Structured Summary

Output a structured markdown summary that the orchestrator can parse:

```markdown
## SCAN RESULTS

### Lab Profile
- PI: {name} (source: {evidence})
- Institution: {name} (source: {evidence})
- Departments: {list}
- Centers: {list}
- External affiliations: {list}
- Lab website: {url or "not provided"}

### Research Themes (from lab website)
{list or "none"}

### Group Members (from lab website)
{list or "none"}

### Infrastructure
- Compute: {clusters, schedulers}
- Cloud: {or "not detected"}
- Platforms: {list}
- Core facilities: {list}
- Shared resources: {list}
- Containers: {list}

### Conventions Detected
{comma-separated summary: stats framework, correction method, figure dims, etc.}

### Projects
| # | Project | Status | Domain | Languages | Data Layers | Data Access | Research Q |
|---|---------|--------|--------|-----------|-------------|-------------|------------|
{rows}

### Institution Profile
{path to created/loaded profile, or "skipped"}

### Cross-Lab Connections
{if multi-lab, detected connections}
```

This output is consumed by the /onboard orchestrator for user review.
