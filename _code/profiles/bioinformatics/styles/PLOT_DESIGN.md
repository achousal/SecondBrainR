# Plot Design Reference -- AD Biomarker Pipeline

> **Scope**: AD-pipeline-specific overrides. Parent template: `_code/styles/PLOT_DESIGN.md` (plot-type geometry). Visual identity: `_code/styles/STYLE_GUIDE.md`.

## Color Palette

| Mapping | Color | Hex | Rationale |
|---|---|---|---|
| Sex: Male | blue | `#377EB8` | ColorBrewer Set1 -- colorblind-distinguishable |
| Sex: Female | red | `#E41A1C` | ColorBrewer Set1 |
| Diagnosis: P- | green | `#4DAF4A` | ColorBrewer Set1 |
| Diagnosis: P+ | red | `#E41A1C` | Matches clinical convention (positive = alert) |

Defined in `palettes.R` as `SEX_COLORS` and `DX_COLORS`.

## Scatter Plots -- Biomarker Panels

### Composite (multi-population) scatters

| Detail | Value | Rationale |
|---|---|---|
| Facet layout | `facet_grid2(rows=Population, cols=Biomarker, independent="y")` | Landscape layout: 2 rows (populations) x 6 cols (biomarkers); same column = same biomarker for cross-population comparison |
| Scales | `scales = "free_y", independent = "y"` | Each biomarker column gets its own y-range via ggh4x independent scales; x (FLT_MU) shared |
| PDF dimensions | 18 x 7 in (landscape) | 16:9-friendly; 2 population rows x 6 biomarker columns |
| Geom layers | `geom_smooth(lm)` only | Trend line + CI ribbon; no raw points to avoid overplotting |
| Smooth style | linewidth 0.8, ribbon alpha 0.2 | Visible trend without dominating |
| X-axis expand | `c(0, 0.05)` | No left padding, 5% right for label room |
| Coord | `clip = "off"` | Allows annotation labels to extend beyond panel |

### Single-population scatters

| Detail | Value | Rationale |
|---|---|---|
| Facet layout | `facet_wrap(~ Biomarker, ncol = 3, scales = "free_y")` | Landscape 2x3 grid; grey strip bars label each biomarker |
| PDF dimensions | 14 x 8 in (landscape) | 16:9-friendly; 2 rows x 3 columns |

### Annotation labels (all scatters)

| Detail | Value | Rationale |
|---|---|---|
| Content | 4 lines: Male r/p/n, Female r/p/n, Fisher Z, Interaction p | Complete statistical summary in one box |
| Geom | `geom_label` (boxed) | White background prevents overlap with data |
| Position | `x=Inf, y=Inf`, `hjust=1, vjust=1` | Top-right corner of each panel |
| Font size | 2.0 | Small enough to not dominate; readable at PDF scale |
| Box style | white fill, grey30 text, 0.3pt border | Subtle framing |
| P-value format | `p<0.001` threshold, else 3 decimal places | Convention |
| Correlation | 2 decimal places | Standard reporting |

## FLT vs Age Scatter

| Detail | Value | Rationale |
|---|---|---|
| Y-axis | `scale_y_auto()` | Same auto-range logic as biomarker scatters |
| Color | P-: green, P+: red | Diagnosis palette |
| Faceting | By Diagnosis (and optionally by Sex in the 4-panel version) | Separate trends per group |
| Annotation | `geom_text` (no box) at top-right | Simpler single-line r/p/n label |

## Box/Violin Overrides

### Violin plots

| Detail | Value | Rationale |
|---|---|---|
| Y-axis | `scale_y_zero(c(0.05, 0.25))` | Zero floor; 5% bottom for n-labels, 25% top for brackets |
| Jitter points | size 1.5, alpha 0.6, jitter.width 0.1 | Individual data visible without obscuring violin |

### Box plots

| Detail | Value | Rationale |
|---|---|---|
| Y-axis | `scale_y_zero(c(0, 0.10))` | Zero floor; no bottom padding, 10% top for brackets |

## Ad-Hoc Box Plots

### NfL tertile boxplot

| Detail | Value |
|---|---|
| Y-axis | `limits = c(0, NA)`, expand `c(0.08, 0.05)` |
| Faceting | `facet_wrap(~ SexLabel)` |
| Jitter alpha | 0.2 (lighter than standard 0.6) |

### APOE carrier group boxplot

| Detail | Value |
|---|---|
| Y-axis | `limits = c(0, NA)`, expand `c(0.08, 0.15)` |
| X-axis labels | Rotated 20 degrees (long group names) |
| Jitter | alpha 0.6, size 1.6 |

### E2 genotype boxplot

| Detail | Value |
|---|---|
| Y-axis | `limits = c(0, NA)`, expand `c(0.08, 0.25)` |
| Bracket tiers | Solid = sex comparison; Dashed grey40 = genotype comparison |
| Faceting | `facet_wrap(~ Diagnosis)` |
| Jitter width | 0.15 (tighter than standard 0.2) |

## Correlation Heatmap

| Detail | Value | Rationale |
|---|---|---|
| Fill scale | Diverging blue-white-red, midpoint=0, limits [-1,1] | Standard correlation convention |
| Cell text | r value + n per cell | Complete info without needing legend |
| Grid | `panel.grid = element_blank()` | Clean tile appearance |
| X-axis | 45 degree rotation | Fits biomarker names |

## Output Dimensions

| Plot type | Width x Height (in) | Layout |
|---|---|---|
| Composite scatter (6 biomarkers x 2 populations) | 18 x 7 | 2 rows x 6 cols (landscape) |
| Single-population scatter | 14 x 8 | 2 rows x 3 cols (landscape) |
| Correlation scatter (NFL/cog/angio scripts) | 10-14 x 6-8 | cowplot grid, ncol=4 |
| Box/violin (Dx x Sex) | 8 x 6 | -- |
| Box/violin (P+ only) | 6 x 6 | -- |
| FLT vs Age | 10 x 6 | -- |
| Carrier group / E2 genotype box | 10-12 x 6 | -- |
| Correlation heatmap | 10 x 6 | -- |

All outputs saved as PDF (vector format). Primary output directories:
- `results/AD_FLT_amyloid/` (AD_analysis.R)
- `results/cog_amyloid/` (NFL_cog.R)
- `results/NFL_angio_amyloid/` (NFL_angio.R)
- `results/GFAP_NfL_amyloid/` (NFL_GFAP_Angio.R)

## Table 1 (cohort summary)

Every project with a defined cohort produces a Table 1. This is the standard demographic/clinical summary that grounds the analysis.

### Structure

| Section | Variables | Format |
|---------|-----------|--------|
| Demographics | Age, Sex, Race/Ethnicity, BMI | continuous: `mean (SD)`; categorical: `n (%)` |
| Clinical | markers, eGFR, creatinine, etc. | continuous: `mean (SD)` |
| Comorbidities | diabetes, hypertension, etc. | binary: `n (%)` |

### Column layout

- One column per group: `"Group A (n = X)"`, `"Group B (n = Y)"`.
- n embedded directly in the column header.
- Optional SMD column (standardized mean difference) for balance assessment.
- Section headers as row separators (bold or shaded).

### Output formats

- **CSV** (machine-readable, version-controlled): `results/tables/table1.csv`
- **Rendered figure** (manuscript-ready): `results/tables/table1.png` + `.svg`

### Implementation reference

The reference implementation is `make_table1(df, output_path)` (Python, `analysis/table1.py`). For R projects, use `gtsummary::tbl_summary()` or `tableone::CreateTableOne()` to produce equivalent output.
