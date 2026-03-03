---
name: plot
description: Generate publication-quality figures using the canonical research theme
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
---

# /plot -- Consistent-Style Figure Generation

Generate publication-quality figures using the canonical research theme.

## Style specification
- Visual identity: `_code/styles/STYLE_GUIDE.md` (typography, frame, output standards, stats, colors)
- Plot-type geometry: `_code/styles/PLOT_DESIGN.md` (distribution, scatter, heatmap, annotation, figure sizes)
- Domain overrides: `_code/profiles/*/styles/PLOT_DESIGN.md` (palettes, facet layouts, variable names)
- Python implementation: `_code/src/engram_r/plot_theme.py`
- R implementation: `_code/R/theme_research.R` + `_code/R/plot_helpers.R`

## Color palettes
- Sex: Male=#377EB8, Female=#E41A1C (ColorBrewer Set1)
- Diagnosis: P-=#4DAF4A, P+=#E41A1C
- Access via `SEX_COLORS` and `DX_COLORS` constants

## Python workflow
1. Import: `from engram_r.plot_theme import apply_research_theme, save_figure, SEX_COLORS, DX_COLORS`
2. Call `apply_research_theme()` before creating figures.
3. Create figures using matplotlib/seaborn.
4. Save with `save_figure(fig, path)` -- defaults to PDF, 300 DPI.
5. Never call `plt.show()`.

## R workflow
1. Source: `source("R/theme_research.R")` and `source("R/plot_helpers.R")`
2. Use `+ theme_research()` on ggplot objects.
3. Use `scale_y_auto()` for scatter plots, `scale_y_zero()` for box/violin.
4. Save with `save_plot(plot, path, width, height)`.
5. Never use `setwd()`.

## Y-axis strategy (from PLOT_DESIGN.md)
- Scatter plots: auto-range (no forced zero), tight padding (2% below, 5% above)
- Box/violin plots: zero-floor, configurable expand

## Output
- Format: PDF (vector) by default
- Dimensions: follow `_code/styles/PLOT_DESIGN.md` table for each plot type
- All outputs saved to user-specified output directory

## Rules
- Always apply the research theme before plotting.
- Use the canonical color palettes for sex and diagnosis variables.
- Font size: 14pt base (matching STYLE_GUIDE.md).
- Bold titles, grey90 strip backgrounds, bottom legend.
- No purple hues in any color scheme.

## Skill Graph
Invoked by: user (standalone), other skills (indirectly via theme)
Invokes: (none -- leaf agent)
Reads: user-provided data, `_code/styles/STYLE_GUIDE.md`, `_code/styles/PLOT_DESIGN.md`, profile `styles/PLOT_DESIGN.md`
Writes: user-specified output directory (PDF figures)

## Rationale
Visual communication -- consistent, publication-quality representation of data and results. Anchored to `_code/styles/STYLE_GUIDE.md` (identity) and `_code/styles/PLOT_DESIGN.md` (geometry) for reproducible aesthetics across all project outputs.
