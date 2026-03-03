---
description: "Template for experiment results README files in output directories"
type: template
---
# {{exp_id}} Results: {{title}}

**Experiment:** {{exp_id}} -- {{description}}
**Hypotheses:** {{linked_hypotheses}}
**Executed:** {{date}}
**Outcome:** {{outcome}}
**SAP:** See `{{sap_filename}}` in the EngramR vault.

## Directory Structure

```
{{exp_id}}/
  README.md              <- this file
  execution_log.yaml     <- structured execution timeline with step status
  data/                  <- processed data artifacts (CSVs)
  figures/               <- all generated plots (PDFs)
  gates/                 <- pre-analysis gate decision records
  rdata/                 <- R serialized objects for reproducibility
  reports/               <- text reports including final synthesis
  tables/                <- summary tables (CSVs)
```

## File Manifest

### data/
| File | Source Script | Description |
|------|-------------|-------------|

### figures/
| File | Source Script | SAP Prediction | Description |
|------|-------------|----------------|-------------|

### gates/
| File | Gate | Decision | Description |
|------|------|----------|-------------|

### rdata/
| File | Size | Source Script | Description |
|------|------|-------------|-------------|

### reports/
| File | Source Script | Description |
|------|-------------|-------------|

### tables/
| File | Source Script | SAP Prediction | Description |
|------|-------------|----------------|-------------|

## Naming Convention

Files follow step-based naming: `{step}_{description}.{ext}`

- `step{NN}_` prefix matches the pipeline script number
- `gate{N}_` prefix for pre-analysis gate artifacts

## Reproducibility

- **Primary seed:** {{seed}}
- **Raw data checksum:** SHA256 `{{checksum}}`
- **R version:** {{r_version}}

To reproduce: run scripts in `analysis/{{exp_id}}/` in order.
