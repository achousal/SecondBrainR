---
description: "Plot system -- visual identity, statistical decision tree, plot builders, palettes, figure sizes"
type: manual
created: 2026-03-01
---

# Plot System

Publication-quality figures with consistent visual identity across Python and R.
Both languages load the same configuration files and implement identical
statistical decision trees.

---

## Three-tier hierarchy

```
_code/styles/palettes.yaml              -- universal semantic palettes
_code/styles/STYLE_GUIDE.md             -- frame, typography, stats, output standards
_code/styles/PLOT_DESIGN.md             -- plot-type geometry and figure sizes
_code/profiles/{domain}/palettes.yaml   -- lab and domain palettes
_code/profiles/{domain}/styles/         -- domain-specific geometry overrides
```

---

## Visual identity

- **Frame**: `theme_classic` -- white background, left + bottom spines only,
  no gridlines, no panel shading
- **Typography**: 14pt base, bold titles, grey90 facet strips, bottom legend
- **Output**: PDF vector default, 300 DPI raster, `bbox_inches="tight"`
- **n in plots**: always visible -- italic `n=N` at distribution plot bases,
  inline in scatter annotations

---

## Statistical decision tree

Implemented identically in `plot_stats.py` (Python) and `stats_helpers.R`:

| Design | Condition | Test |
| --- | --- | --- |
| Two-group unpaired | n >= 30 AND normal | Welch t-test |
| Two-group unpaired | otherwise | Mann-Whitney U |
| Multi-group (3+) | -- | Kruskal-Wallis + Dunn post-hoc (BH correction) |
| Paired, normal | -- | Paired t-test |
| Paired, non-normal | -- | Wilcoxon signed-rank |
| Correlation, default | -- | Spearman |
| Correlation, normal | -- | Pearson |
| Proportion, expected < 5 | -- | Fisher exact |
| Proportion, all >= 5 | -- | Chi-square |

P-value formatting: `p < 0.001` threshold, else 3 decimal places. Stars:
`***`/`**`/`*`/`ns`. Every figure writes a `_pvalues.txt` sidecar file.

---

## Plot builders

8 plot types with matched implementations in Python (`plot_builders.py`) and
R (`plot_builders.R`):

| Builder | Geometry |
| --- | --- |
| `build_violin` | Violin + jittered points, alpha 0.6, untrimmed |
| `build_box` | Box + jittered points, outliers suppressed |
| `build_scatter` | Points + optional linear regression with CI ribbon |
| `build_heatmap` | Tile plot, RdBu diverging (centered at 0), annotated values |
| `build_volcano` | -log10(p) vs log2FC, colored by direction, reference lines |
| `build_forest` | Point + CI range, sorted by estimate, null reference line |
| `build_roc` | ROC curve (pre-computed or from raw scores), diagonal chance line |
| `build_bar` | Grouped bars + optional error bars |

---

## Palettes

- **Universal semantic**: direction (Up/Down/NS), significance (sig/not sig),
  binary (Control/Case) -- defined in `palettes.yaml`
- **Profile palettes**: Defined per domain profile in
  `_code/profiles/{domain}/palettes.yaml`. Access: `get_lab_palette("name")`
  (Python) or `lab_palette("name")` (R)
- **Domain semantic**: Domain-specific categorical palettes -- defined per
  domain profile
- **Scale helpers**: `scale_color_direction()`, `scale_fill_sig()`,
  `scale_color_lab()`, etc. in both languages

---

## Standard figure sizes

| Plot type | Width x Height (inches) |
| --- | --- |
| Violin/box grouped | 8 x 6 |
| Violin/box single | 6 x 6 |
| Scatter multi-panel | 18 x 7 |
| Scatter single | 14 x 8 |
| Scatter bivariate | 10 x 6 |
| Correlation heatmap | 10 x 6 |
| Forest | 10 x 8 |
| Volcano | 10 x 8 |
| ROC | 7 x 7 |
| Bar + errors | 8 x 6 |

---

## See Also

- [Skills Reference](skills.md) -- `/plot` and `/eda` command details
- `_code/styles/STYLE_GUIDE.md` -- canonical visual identity specification
- `_code/styles/PLOT_DESIGN.md` -- plot-type geometry specification
