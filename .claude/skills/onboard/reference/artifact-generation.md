# Artifact Generation Instructions

Reference file for the onboard-generate sub-skill. Extracted from the main onboard SKILL.md Steps 5a-5h.

---

## Artifact creation order

Goals first (so project notes can reference them in linked_goals), then project notes, then everything else.

## 5e. Research Goals (first)

If the strategic interview identified new research directions not covered by existing goals:

1. Check `_research/goals/` for existing goals that might match.
2. If genuinely new, create a research goal note using `_code/templates/research-goal.md` schema:

```yaml
---
type: research-goal
title: "{goal title}"
status: active
linked_labs: ["{lab_slug}"]
constraints: []
evaluation_criteria: []
domain: "{domain}"
tags: [research-goal]
created: {today}
---
```

`linked_labs` scopes the goal to one or more labs. Use `["{lab_slug}"]` for lab-specific goals. For cross-lab goals, list all relevant lab slugs. An empty list means vault-wide.

3. Save to `_research/goals/{goal-slug}.md`.

If a goal already exists that matches what the user described, link the new projects to it instead of creating a duplicate. If the existing goal's `linked_labs` does not include the current lab, append the current lab slug to the list.

**Multi-lab goal handling:** Only ask whether a goal is lab-specific vs cross-lab if multiple labs exist in the vault. Otherwise, default to the current lab.

## 5a. Project Notes

For each NEW project, build a project note. Follow the exact schema from `_code/templates/project.md`:

```yaml
---
type: project
title: "{detected or user-provided title}"
project_tag: "{tag}"
lab: "{lab name}"
pi: "{PI}"
status: active
project_path: "{absolute or ~-relative path}"
language: [{detected languages}]
hpc_path: "{from scan, or empty string if none}"
scheduler: "{LSF, SLURM, or PBS if detected; otherwise empty string}"
linked_goals: [{from Step 4/5e, as wiki-links}]
linked_hypotheses: []
linked_experiments: []
has_claude_md: {true/false}
has_git: {true/false}
has_tests: {true/false}
created: {today YYYY-MM-DD}
updated: {today YYYY-MM-DD}
tags: [project, {lab_slug}]
---

{One-line description from CLAUDE.md or user correction}

![[_dev/{tag}/CLAUDE.md]]
```

### 5a2. Internal Doc Discovery (auto-selected, no per-project checklist)

After generating the base project note, scan the project directory for internal documentation that should be wiki-linked from the project note.

**Discovery (config-driven):**

Build the `find` command dynamically from ONBOARD_CONFIG (loaded in Step 0) and per-project scope:

1. **Determine scan targets.** If the project note has `scan_dirs` set (non-empty list from a previous `--update` run), restrict find to those directories only. If `scan_dirs` is empty (first onboard), scan the full project tree:
   ```bash
   find {project_path} -maxdepth {ONBOARD_CONFIG.scan_depth} -name '*.md' ...
   ```

2. **Build exclude args.** Merge three sources into a single exclude list:
   - Global: `ONBOARD_CONFIG.exclude_dirs` (from `ops/config.yaml`)
   - Per-project: `scan_exclude` from the project note frontmatter (if `--update` mode)
   - Always included: `.claude/plans` (agent plan artifacts)

   For each pattern, emit: `-not -path '*/{pattern}/*'`

3. **Post-filter results.** After find completes, remove:
   - Files < 100 bytes (too small to be meaningful docs)
   - `CLAUDE.md` (already transcluded in the project note)
   - Files whose basename matches any entry in `ONBOARD_CONFIG.exclude_files`

**Auto-selection (no per-project user prompt):**

Classify each discovered file and auto-select research docs:

| Group | Rule | Action |
|---|---|---|
| **Research docs** | Path contains `/analysis/`, `/scripts/`, `/src/`, `/R/`, `/notebooks/`, `/results/`, `/reports/` | Auto-include |
| **Infrastructure** | Path contains `/man/`, `/vignettes/`, `/docs/api/`, `/docs/reference/`; or basename matches `ONBOARD_CONFIG.exclude_files` | Skip |
| **Other** | Everything else | Skip |

**No per-project doc checklist.** Research docs are auto-selected. Mention what was included in the summary. User can adjust later via `--update`.

**Persist scan scope:**
Extract the set of unique top-level directories (relative to project root) from selected files. Save as `scan_dirs` in project note frontmatter. Future `--update` runs use this whitelist automatically.

**Generate Key Docs section:**
For each selected doc, append a `## Key Docs` section to the project note body (after the `![[_dev/{tag}/CLAUDE.md]]` line):

```markdown
## Key Docs
- [[ARCHITECTURE]] -- system architecture and module boundaries
- [[README_FACTORIAL]] -- 2x2x2 factorial experiment design
```

Context phrases are **required** for every entry (same convention as topic map Core Ideas). A bare link list is insufficient.

**Skip conditions:**
- If no `.md` files found besides CLAUDE.md, skip this step silently.
- If no files match the research docs classification, skip without adding the section.

Save to: `projects/{lab_slug}/{tag}.md` (matching existing convention: `projects/lab-a/`, `projects/lab-b/`).

Create lab subdirectory if it does not exist:
```bash
mkdir -p projects/{lab_slug}
```

## 5b. Symlinks

For each NEW project:
```bash
ln -sfn {project_path} {vault_root}/_dev/{tag}
```

Verify _dev/ directory exists first:
```bash
mkdir -p _dev
```

If symlink already exists and points to the same target, skip silently (idempotent).

After creating individual symlinks, run the bulk verification script to catch any missed links:
```bash
bash ops/scripts/create-dev-links.sh
```
This script reads all project notes and ensures every `project_tag` has a corresponding `_dev/` symlink. It is idempotent.

## 5b2. Lab Entity Node

If `projects/{lab_slug}/_index.md` does not exist, create it using the `_code/templates/lab.md` schema:

```yaml
---
type: lab
lab_slug: "{lab_slug}"
pi: "{PI name}"
institution: "{from scan or user correction}"
institution_profile: "[[{institution-slug}]]"
lab_website: "{lab_website_url or empty string if not provided}"
departments: ["{from faculty lookup -- list of department names}"]
center_affiliations: ["{from faculty lookup -- research centers/institutes}"]
external_affiliations: ["{from faculty lookup -- external institutions, or empty}"]
hpc_cluster: "{from scan or empty}"
hpc_scheduler: "{from scan or empty}"
research_focus: "{1-2 sentence focus}"
infrastructure:
  compute: ["{HPC cluster names, cloud accounts, GPU access, local workstations}"]
  containers: ["{Singularity, Docker, or empty}"]
  platforms: ["{detected data management and research platforms, or empty}"]
  core_facilities: ["{detected shared instrumentation and service labs, or empty}"]
  shared_resources: ["{detected repositories, archives, registries, or empty}"]
  licensed_software: ["{detected licensed software, or empty}"]
statistical_conventions:
  multiple_testing: "{FDR, Bonferroni, permutation, or empty}"
  significance_threshold: "{0.05 or lab-specific}"
  effect_size_metrics: ["{log2FC, Cohen's d, odds ratio, etc.}"]
  framework: "{frequentist, bayesian, both, or empty}"
  power_convention: "{lab standard or empty}"
style_conventions:
  accent_palette: "{palette name or empty -- inherits vault theme}"
  figure_dimensions: "{e.g. single-column 3.5in, full-width 7in, or empty}"
  journal_targets: ["{primary target journals}"]
created: {today}
updated: {today}
tags: [lab]
---
```

The body should list the lab's projects and datasets. Filename becomes the `[[lab_slug]]` link target.

Infrastructure fields are populated from scan auto-detection + institution lookup + lab website fetch + user corrections. Identity and infrastructure fields were user-reviewed. Convention fields (statistical_conventions, style_conventions, containers) were silently auto-detected and are NOT user-reviewed during onboarding -- they are included here for downstream skill use (/eda, /plot, /experiment).

The `institution_profile` wiki-link points to the full institutional resource catalog at `ops/institutions/{slug}.md`. The lab's `infrastructure:` fields represent what THIS LAB actually has access to (a subset/override of the institution profile). Empty lists inherit nothing -- they signal "not available" rather than "unknown".

If no institution profile was created (user skipped institution lookup), set `institution_profile: ""` (empty string).

Convention fields that are empty inherit from vault defaults in `ops/config.yaml`. Per-project overrides (if any) are stored in the project note frontmatter and take precedence over lab defaults.

## 5c. Update projects/_index.md

For each NEW project, append a row to the appropriate lab section table in `projects/_index.md`.

Row format (matching existing convention):
```
| [[{tag}]] | {PI} | {languages, comma-separated} | {HPC info or --} | {one-line summary} |
```

If `projects/_index.md` does not exist, it should have been created in Step 0 Bootstrap. If the lab section does not exist within the file, create it:
```markdown
### {Lab Name}

| Project | PI | Language | HPC | Summary |
|---|---|---|---|---|
| [[{tag}]] | {PI} | {languages} | {HPC or --} | {summary} |
```

Insert new lab sections before the `## Maintenance` line.

## 5d. Data Inventory

For each NEW project that has identifiable datasets (data/ directory is non-empty, or data described in CLAUDE.md or scan):

**Summary Table row** -- append to the Summary Table in `_research/data-inventory.md`:
```
| **{Dataset Name}** | {Lab} | {Domain} | {Data layers} | {N or TBD} | {Species} | {Access status} | {Location/project} |
```

**Data Layer Coverage Matrix row** -- append to the Data Layer Coverage Matrix in `_research/data-inventory.md`. Column headers come from `ops/config.yaml` `data_layers` list. Each cell is either the specific subtype detected or `--`:
```
| {Dataset Name} | {layer1 value or --} | {layer2 value or --} | ... |
```

**Display rule:** The per-dataset coverage matrix is written to `_research/data-inventory.md` but NEVER displayed verbosely in onboard output. Instead, display the compressed lab-level summary.

**Detailed Inventory entry** -- append under the appropriate lab heading in the Detailed Inventory section:
```markdown
#### {Dataset Name}

- **Project:** [[{tag}]]
- **Path:** `{project_path}`
- **Source:** {from scan or CLAUDE.md}
- **N:** {sample count or TBD}
- **Data types:** {data layers and specifics}
- **Status:** {current status}
```

Use the exact column format of existing entries. Do not reformat existing content.

## 5g. Update self/goals.md

Append new entries to the `## Active Threads` section:
```
- {Lab Name} onboarded -- {N} projects registered, linked to {goals or "no goals yet"}
```

If new research goals were created, add them under `## Active Research Goals` following the existing format:
```
### [[{goal-slug}]] -- {goal title}
**Scope:** {from user input}
**Status:** Newly created. Next: /literature search + /generate hypotheses.
```

## 5h. Update ops/reminders.md

Add follow-up items only for genuinely incomplete work. Do not add boilerplate reminders for fully onboarded projects.

Examples of actionable reminders:
```
- [ ] {today}: Complete data inventory for {project} -- detailed entry needed
- [ ] {today}: Run /reflect to connect new {lab} projects to existing claims
- [ ] {today}: Apply for {dataset/resource} access -- needed for {goal}
```

Skip reminders for projects that are fully onboarded with no gaps.
