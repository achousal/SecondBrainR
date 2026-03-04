# Methodology Phase Instructions

Reference file for the init-generate sub-skill. Extracted from init SKILL.md Phase 3.

---

## Phase 3: Methodological Seeding

**Purpose:** Seed cross-cutting methodological knowledge -- confounders, data realities, analytical requirements. Captures shared analytical infrastructure anchored to the current goal's orientation claims.

Phase 3 runs once per init-generate invocation. The orchestrator calls init-generate once per goal, so Phase 3 executes for each goal in turn. It uses the current goal's Phase 2 orientation claims as worked examples.

### 3.pre Vault State Scan

**Conditional step -- skip if VAULT_STATE was provided in the input file.**

If the orchestrator passed `VAULT_STATE` and `VAULT_INFORMED = true` in the input, use those values directly for `LAB_CONVENTIONS`, `PROJECT_META`, `DATA_INVENTORY`, and `CODE_TOOLS`. Do NOT re-scan.

**Fallback (VAULT_STATE absent or VAULT_INFORMED is false):** Scan vault artifacts created by /onboard to pre-populate Phase 3 content. Read the following sources (skip silently if missing):

1. **Lab conventions:** Read `projects/*/_index.md`. Extract `statistical_conventions.*` (framework, multiple_testing, effect_size_metrics) and `infrastructure.*` (core_facilities, HPC). Store as `LAB_CONVENTIONS`.

2. **Project metadata:** Read `projects/*/*.md` (excluding `_index.md`). Extract `language`, `linked_goals` fields from frontmatter. Store as `PROJECT_META`.

3. **Data inventory:** Read `_research/data-inventory.md`. Parse the Summary Table rows (columns vary by domain -- e.g., Dataset, Species, Omic Layer, N, Access, Goal Link for bioinformatics; Dataset, Source, Data Type, N, Access, Goal Link for generic domains). Store as `DATA_INVENTORY`.

4. **Code tools:** Read first ~60 lines of `_code/src/engram_r/plot_stats.py` and `_code/R/stats_helpers.R`. Detect available statistical test types, plot types, and helper functions. Store as `CODE_TOOLS`.

**Set flag:** `VAULT_INFORMED = true` if ANY source yielded non-empty data. Otherwise `VAULT_INFORMED = false`.

### 3a. Analytical Method Claims

**If `VAULT_INFORMED`:**

Draft 2-4 analytical method claims from vault state:
- `LAB_CONVENTIONS.statistical_conventions` -> framework, multiple testing correction, effect size metrics
- `CODE_TOOLS` -> available analysis methods, test designs, plot types
- `PROJECT_META.language` -> R/Python tool ecosystem and associated libraries

**Else (vault empty / no onboard data):**

Use the core questions and orientation claims to infer likely analytical methods.

**In either case**, for each method, generate ONE methodology claim:

```yaml
---
description: "{what this method enables or constrains}"
type: methodology
role: methodology
confidence: supported
source_class: synthesis
verified_by: agent
created: {today YYYY-MM-DD}
---
```

Body: 2-3 sentences on why this method matters, its key assumptions, and known limitations. Link to relevant orientation claims from Phase 2.

### 3b. Compositional Confounder Claims

This is the key innovation of /init: using Phase 2 claims as concrete anchors for confounder identification.

For EACH orientation claim in ORIENTATION_CLAIMS:

**If `VAULT_INFORMED`:**

Read domain profile `confounders.yaml` if active (`_code/profiles/{domain.name}/confounders.yaml`). Use its data_layer -> confounders mapping. If no profile is active, use generic confounders.

Match data layer from `DATA_INVENTORY` rows to each orientation claim via its linked goal or domain keywords. Refine confounder selection using these additional signals:
- `DATA_INVENTORY.N` -- small N (< 50) -> inadequate power to detect or adjust for confounders
- `DATA_INVENTORY.Access` -- restricted/pending -> selection bias risk
- `LAB_CONVENTIONS.infrastructure.core_facilities` -- facility-specific batch artifacts

**Else (vault empty / no onboard data):**

Use generic confounders: technical (batch effects, platform artifacts), domain-specific factors (e.g., age, sex, comorbidities for biomedical; socioeconomic factors for social science), and analytical (multiple testing, selection bias).

**In either case**, for each confounder, generate a claim:

```yaml
---
description: "{how this confounder operates and why it matters}"
type: claim
role: confounder
confidence: supported
source_class: synthesis
verified_by: agent
created: {today YYYY-MM-DD}
---
```

Title pattern: "{confounder} confounds {measurement or inference} in {context}"
Example: "batch processing date confounds signal intensity measurements in longitudinal cohort studies"

Body: 2-3 sentences explaining the confounding mechanism, with inline [[wiki-links]] to the orientation claim it threatens.

### 3c. Data Reality Claims

**If `VAULT_INFORMED`:**

Draft 2-3 data reality claims from `DATA_INVENTORY`:
- **Sample sizes:** N values < 50 -> power constraint claim. N = "TBD" -> unknown sample size claim.
- **Access barriers:** Pending access approval (e.g., IRB, DUA, ethics board, data sharing agreement), "Restricted" -> timeline/access constraint claim.
- **Coverage gaps:** `--` entries in the Omic Coverage Matrix -> missing modality claim.
- **Context-specific constraints:** Read domain profile `data_reality_signals` if active. Otherwise use generic constraints from data inventory Context column.

**Else (vault empty / no onboard data):**

Use generic data reality constraints: sample sizes, missing data patterns, platform limitations, cohort access barriers, pre-analytical variables.

**In either case**, for each data reality, generate ONE claim with `type: claim`, `role: data-reality`, and `confidence: supported`. Title pattern: "{data limitation} constrains {what it limits}".

### 3d. Collect Methodological Claims

For each claim in Phase 3 (methods + confounders + data realities):

1. Follow the same creation procedure as Phase 2 (sanitize, verify links). Add to PENDING_CLAIMS list. Do NOT write to disk.
2. Add to CLAIMS_CREATED list
3. Ensure each claim has a `Topics:` footer linking to a relevant topic map
