---
type: experiment
title: "{{title}}"
description: ""
id: "{{exp_id}}"
hypothesis: ""
linked_hypotheses: []
linked_projects: []
parameters: {}
seed: null
status: planned
outcome: null
tags: [experiment]
created: {{date}}
---

## 1. Objective

## 2. Hypotheses Under Test

## 3. Design

## 4. Prediction Registry

| ID | Source | Tier | Prediction | Pass criterion |
|----|--------|------|------------|----------------|

## 5. Analysis Pipeline

### Pre-Analysis Gates

### Steps

## 6. Output Directory Convention

All results go to `results/{{exp_id}}/` with this structure:

```
{{exp_id}}/
  README.md              <- file manifest, naming key, reproducibility info
  execution_log.yaml     <- structured step-by-step execution timeline
  data/                  <- processed data artifacts (CSVs)
  figures/               <- plots (PDFs), named {step}_{description}.pdf
  gates/                 <- gate decision records
  rdata/                 <- R serialized objects
  reports/               <- text reports including final synthesis
  tables/                <- summary tables, named {step}_{description}.csv
```

### File naming convention

Step-based: `{step}_{description}.{ext}`

- `step{NN}_` prefix matches the pipeline script number
- `gate{N}_` prefix for pre-analysis gate artifacts
- No paper-style numbering (fig01, table4) -- name by what the file IS

### README.md (required)

The results README must contain:
- Experiment ID and brief outcome
- File manifest: filename -> source script -> SAP prediction -> status
- Which files were skipped and why
- Naming convention reference
- Reproducibility info (seeds, checksums, versions)

### execution_log.yaml (required)

Structured log of each step: id, script, timestamps, status, decision, outputs, notes.
Include a `skipped` section for steps not executed and why.

## 7. Cross-Repo Sync Checklist

When experiment completes, update vault:
- [ ] Hypothesis frontmatter: status, outcome fields
- [ ] Execution tracker: step status column
- [ ] Research goal: empirical findings section
- [ ] gate4_synthesis.txt summary -> experiment note in vault

## 8. Results

## 9. Interpretation

## 10. Next Steps
