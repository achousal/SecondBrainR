---
name: eda
description: Run exploratory data analysis with PII auto-redaction and themed plots
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
  - Write
---

# /eda -- Exploratory Data Analysis

Run exploratory data analysis on a dataset with PII auto-redaction and themed plots.

## Code location
- `_code/src/engram_r/eda.py` -- EDA computations and plots
- `_code/src/engram_r/pii_filter.py` -- PII detection and redaction
- `_code/src/engram_r/plot_theme.py` -- plot styling
- `_code/src/engram_r/note_builder.py` -- `build_eda_report_note()`

## Workflow
1. Ask the user for the dataset path.
2. Load with `load_dataset(path)` -- auto-redacts ID-like columns (SubjectID, PatientName, SSN, Email, etc., plus profile-specific patterns).
3. Report which columns were redacted and confirm with user.
4. Compute summary statistics with `compute_summary(df)`.
5. Compute correlations with `compute_correlations(df)`.
6. Detect distribution properties with `detect_distributions(df)`.
7. Generate themed plots with `generate_eda_plots(df, output_dir)`:
   - Histograms for numeric columns
   - Correlation heatmap
   - Missing data chart
8. Build an EDA report note using `build_eda_report_note()`.
9. Save the report to `_research/eda-reports/{date}-{dataset_name}.md` in the vault.
10. Present findings to the user: summary stats, notable correlations, distribution flags, redaction list.

## PII detection patterns
Columns matching these patterns are auto-redacted:
- *ID*, *Subject*, *Patient*, *Participant*, *Person*
- *SSN*, *Name*, *DOB*, *Email*, *Phone*, *Address*, *Zip*

Base patterns cover general identifiers (SSN, Email, Address) and research-specific (SubjectID, ParticipantID). Domain profiles can add additional patterns (e.g., MRN for biomedical, student ID for education).

## Run metadata
Record in the note: dataset path, timestamp, Python version, package versions (pandas, numpy), random seed if applicable, number of rows/cols, redacted columns.

## Rules
- Always auto-redact PII columns before any analysis.
- Never show raw ID values in outputs or plots.
- Use the research theme for all plots.
- Save plots as PDF.
- If dataset has >100 columns, limit histogram grid to 20 most variable.

## Skill Graph
Invoked by: user (standalone)
Invokes: (none -- leaf agent)
Reads: user-provided dataset
Writes: _research/eda-reports/, _research/eda-reports/_index.md

## Rationale
Data-driven pattern discovery -- exploratory analysis that reveals structure in datasets before hypothesis formation. Surfaces variables, distributions, and correlations that inform /generate.
