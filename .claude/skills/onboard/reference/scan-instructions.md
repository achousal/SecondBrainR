# Onboard Scan Instructions

Reference file for the onboard-scan sub-skill. Extracted from the main onboard SKILL.md.

---

## Step 2: Scan Everything

Given a lab path, perform a single comprehensive pass: discover projects, extract metadata, mine conventions, and auto-detect per-project fields. No separate user prompts during this step.

### 2a. Discover project directories

List immediate subdirectories. For each, check for project indicators:

```bash
# List candidate directories (depth 1)
ls -d {lab_path}/*/ 2>/dev/null
```

A directory is a **project candidate** if it contains ANY of:
- `CLAUDE.md` (strong signal)
- `.git/` (strong signal)
- `data/` directory
- `analysis/` or `results/` directory
- `*.R`, `*.py`, `*.sh` files (check with ls, not deep find)
- `Snakefile`, `Nextflow`, `Makefile`
- `*.lsf`, `*.slurm`, `*.pbs` files (HPC job scripts)

Skip directories that are clearly not projects: `.git`, `__pycache__`, `node_modules`, `.Rproj.user`, `renv`, `.snakemake`.

### 2b. Extract project metadata

For each candidate project, collect:

| Field | Detection Method |
|-------|-----------------|
| name | Directory basename |
| project_tag | Lowercase, hyphens for spaces/underscores |
| languages | File extensions: .R -> R, .py -> Python, .sh -> Bash, .nf -> Nextflow |
| has_claude_md | Test `{path}/CLAUDE.md` exists |
| has_git | Test `{path}/.git/` exists |
| has_tests | Test `{path}/tests/` or `{path}/analysis/tests/` exists |
| data_files | `ls {path}/data/ 2>/dev/null | head -10` (sample, not exhaustive) |
| hpc_indicators | Presence of .lsf/.slurm/.pbs files, or HPC paths in CLAUDE.md |

### 2c. Read CLAUDE.md for auto-population

If `CLAUDE.md` exists in a project, read it (first 100 lines) and extract:
- **Description**: first paragraph or "## Overview" section
- **Language**: from documented tech stack or dependencies
- **HPC path**: any HPC/cluster paths mentioned
- **Scheduler**: LSF, SLURM, PBS if mentioned
- **Key data files**: from "## Data" or similar section

Do NOT read CLAUDE.md files that are excessively large (>500 lines). Read first 100 lines only.

### 2d. Mine conventions from code

**Identity signals:**
- PI name: grep CLAUDE.md files for "PI:", "Principal Investigator", author fields
- Institution: grep for university/hospital/institute names, email domains
- Research focus: extract from CLAUDE.md overview sections, README.md first paragraphs

**HPC signals:**
- Cluster name: grep for Minerva, O2, Biowulf, Sherlock, etc. in CLAUDE.md, .lsf, .slurm, .pbs files
- Scheduler: infer from file extensions (.lsf -> LSF, .slurm -> SLURM, .pbs -> PBS) or keywords
- HPC paths: grep CLAUDE.md and job scripts for `/hpc/`, `/sc/`, `/n/`, `/data/` patterns

**Convention signals (silent collection)** -- detected but NOT presented at review. These are auto-populated in the lab entity node and editable later. Sample up to 5 R/Python analysis files per project (prefer files in `analysis/`, `scripts/`, `src/`):

| Convention | Detection method |
|-----------|-----------------|
| Multiple testing | grep for `p.adjust`, `method=`, `"BH"`, `"fdr"`, `"bonferroni"`, `multipletests`, `fdrcorrection` |
| Significance threshold | grep for `alpha`, `p.value <`, `padj <`, `pvalue_threshold`, common thresholds (0.05, 0.01, 0.1) |
| Effect size metrics | grep for `log2FoldChange`, `logFC`, `cohen`, `odds.ratio`, `hazard.ratio`, `effect_size` |
| Statistical framework | grep for `brms`, `stan`, `rstanarm`, `pymc`, `bambi` (Bayesian); `lm(`, `glm(`, `t.test`, `wilcox` (frequentist); domain-specific packages from project code |
| Power analysis | grep for `pwr::`, `power.t.test`, `samplesize`, `power_analysis` |
| Accent palette | grep for `scale_color_`, `scale_fill_`, palette definitions, hex color arrays in R/Python plot code |
| Figure dimensions | grep for `ggsave`, `width=`, `height=`, `fig.width`, `fig.height`, `figsize` |
| Journal targets | grep CLAUDE.md for journal names (Nature, Cell, PNAS, JCI, etc.) |
| Containers | presence of `Dockerfile`, `Singularity`, `singularity.def`, `*.sif` files |

**Infrastructure signals** -- detect compute, platform, and facility references beyond HPC:

| Resource type | Detection method |
|--------------|-----------------|
| Cloud compute | grep CLAUDE.md, configs for `aws`, `s3://`, `gcp`, `gs://`, `azure`, `blob.core` |
| Platforms | grep CLAUDE.md, scripts for data management and research platform references |
| Core facilities | grep CLAUDE.md for shared facility and instrumentation references |
| Public data | grep for public data repository accessions and dataset identifiers |
| Shared resources | grep CLAUDE.md for shared resource references (biobanks, registries, archives, etc.) |

```bash
# Example: detect infrastructure signals across lab
grep -rli 's3://\|Singularity\|Dockerfile' {lab_path}/*/CLAUDE.md {lab_path}/*/README.md 2>/dev/null | head -10
```

```bash
# Example: sample R/Python files for statistical patterns
find {project_path} -name '*.R' -path '*/analysis/*' -o -name '*.R' -path '*/scripts/*' | head -5 | while read f; do
  grep -n 'p.adjust\|method=\|brms\|stan\|pwr::' "$f" 2>/dev/null | head -10
done
```

### 2e. Auto-detect per-project fields

For each project, attempt to infer:

| Field | Detection Method |
|-------|-----------------|
| Research domain | From CLAUDE.md overview, directory names, data file types |
| Data source | From data/ contents, CLAUDE.md references to datasets, accession patterns |
| Data layers | Match against `data_layers` list in `ops/config.yaml`. Infer from file types, tool references, and project descriptions. Domain-specific heuristics apply (e.g., in bioinformatics: DESeq2 -> Transcriptomics, `.bam` -> Genomics). |
| Key research question | From CLAUDE.md overview section, first paragraph of README.md |

Store inferred values with their evidence source (e.g., "{Layer} (from {tool/file} in {path})").

### 2f. Diff against vault

Compare discovered projects against REGISTERED_TAGS from Step 0.

Classify each discovered project:

| Status | Condition | Action |
|--------|-----------|--------|
| **NEW** | project_tag not in REGISTERED_TAGS | Full onboard |
| **CHANGED** | project_tag exists but path or key metadata differs | Update |
| **CURRENT** | project_tag exists and matches | Skip |
