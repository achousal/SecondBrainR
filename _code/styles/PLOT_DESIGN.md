# Plot Design Reference -- Plot-Type Geometry

> **Scope**: Domain-agnostic plot-type geometry and layout specs. Visual identity (typography, frame, output standards, statistical analysis) lives in `STYLE_GUIDE.md`. Domain-specific overrides (color palettes, facet layouts, variable names, results directories) go in profile `styles/PLOT_DESIGN.md` files.

## Y-Axis Strategy

Two modes, selected by plot type:

| Mode | Helper | Used by | Behavior |
|---|---|---|---|
| **Auto-range** | `scale_y_auto()` | All scatter plots | No forced zero; tight padding (2% below, 5% above). Data fills the panel. |
| **Zero-floor** | `scale_y_zero()` | Box, violin, bar plots | Forces y=0; configurable expand padding. |

**Rationale:** Scatter plots show associations -- forcing y=0 wastes space when values live far from zero. Box/violin plots show distributions where the zero baseline is meaningful.

## Distribution plots (violin and box)

Distribution plots use semi-transparent fills with individual data points overlaid. This dual-layer approach shows both the distribution shape and the raw observations.

- **Fill alpha**: 0.35--0.40. Transparent enough to see overlaid points; opaque enough to convey the distribution shape.
- **Individual points**: jittered, alpha 0.5--0.6, size 1.5--5 depending on n. Points give the reader a sense of sample size and outlier structure that summary geometry alone cannot convey.
- **Structural elements**: black whiskers, caps, and medians at linewidth ~1.0. Black structural lines anchor the summary statistics against the colored fills.
- **Outliers**: hidden when jitter points are present (they would duplicate information).
- **Dodge width**: 0.7 for grouped comparisons (e.g., side-by-side subgroups).

### Violin specifics

- Untrimmed (shows full kernel density extent).
- Violin outline linewidth 0.4 (subtle).
- Mean marker: shape 95 (dash), size 6, black.

### Box specifics

- Box width 0.35 (narrow for clean dodged layout).
- Box outline linewidth 0.6.

### Shared distribution patterns

| Detail | Value | Rationale |
|---|---|---|
| Significance brackets | `ggpubr::stat_pvalue_manual`, tip 0.02, step 0.08 | Compact brackets |
| Bracket labels | `{p.signif}` (stars: \*, \*\*, \*\*\*, ns) | Quick visual significance |
| N-labels | italic, size 3, at y=0 or y=-Inf | Sample size per group at base of plot |
| P-value file | Saved as `_plot_pvalues.txt` alongside PDF | Exact numbers always available |

## Scatter plots

- **Point alpha**: 0.6. Balances visibility of individual points against overplotting.
- **White edges**: 0.5pt white stroke around each point. Separates overlapping points and improves readability against colored backgrounds or dense clusters.
- **Regression lines**: linewidth 0.8 with confidence interval fill at alpha 0.18--0.2. The CI ribbon should be visible but not dominate the data layer.

## Statistical annotation box

A consistent annotation box for embedding test results directly in the figure.

- **Background**: wheat fill, alpha 0.8. A warm neutral tone that stands out from white backgrounds without competing with data colors.
- **Shape**: rounded corners, padding 0.3.
- **Position**: top-left (or top-right for scatter panels). Consistent placement creates a visual anchor so the reader always knows where to find statistics.
- **Content**: p-values, effect sizes, sample sizes -- whatever the analysis requires.
- **Font size**: small (2.0--2.5) relative to base. Readable at export resolution but does not dominate.

## Heatmaps

- **Diverging data** (centered at 0): `RdBu` (R) / `RdBu_r` (Python). Perceptually uniform, colorblind-safe, widely recognized as the standard for diverging scales.
- **Sequential data** (density, counts): `Blues`. Clean single-hue ramp that avoids implying a midpoint.
- **Cell borders**: none. Clean tile appearance.

## Reference lines

- **Color**: gray.
- **Style**: dashed or dotted, linewidth 1.0.
- **Purpose**: threshold markers (e.g., significance cutoffs on volcano plots, baseline values). Gray dashed lines indicate reference values without demanding attention.

## Standard figure sizes (inches)

| Plot type | Key | Width x Height |
|-----------|-----|----------------|
| Box/violin (grouped) | `box_grouped` / `violin_grouped` | 8 x 6 |
| Box/violin (single) | `box_single` / `violin_single` | 6 x 6 |
| Scatter (multi-panel) | `scatter_multi` | 18 x 7 |
| Scatter (single pop) | `scatter_single` | 14 x 8 |
| Scatter (bivariate) | `scatter_bivar` | 10 x 6 |
| Correlation heatmap | `heatmap` | 10 x 6 |
| Forest plot | `forest` | 10 x 8 |
| Volcano plot | `volcano` | 10 x 8 |
| ROC curve | `roc` | 7 x 7 |
| Bar + error bars | `bar` | 8 x 6 |

Access via `get_figure_size("roc")` or `FIGURE_SIZES["roc"]`.
