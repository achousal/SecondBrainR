# Interactive HTML Data Representations

Conventions for self-contained HTML dashboards and interactive data visualizations. Reference implementation: `LADC_flow/results/sankey_217_ladc.html`.

## Design Philosophy

- **Self-contained single file**: embed data as JSON, CSS as `<style>`, JS inline. No external dependencies except Google Fonts. Opens in any browser with no build step.
- **Dashboard layout**: summary cards at top, primary visualization in the middle, supporting detail panels below. Information flows from overview to detail.
- **Vanilla SVG**: build charts with raw SVG DOM manipulation. No D3 or charting library required for moderate complexity. Keeps file size small and eliminates version conflicts.

## Typography

| Property | Value |
|----------|-------|
| Font family | `'Inter', -apple-system, BlinkMacSystemFont, sans-serif` |
| Rendering | `-webkit-font-smoothing: antialiased` |
| Line height | 1.5 (body default) |
| Labels | 11px, font-weight 600, uppercase, letter-spacing 0.5-0.8px |
| Values (hero numbers) | 32px, font-weight 700, letter-spacing -0.5px |
| Body text | 13px, font-weight 400-500 |
| Axis labels | 9-11px, font-weight 500-600 |

## Color System

Use CSS custom properties on `:root` for theming. Map semantic meaning to variables, not raw hex.

```css
:root {
  --bg: #fafafa;
  --surface: #ffffff;
  --border: #e5e5e5;
  --text-primary: #1a1a1a;
  --text-secondary: #6b6b6b;
  --text-tertiary: #999999;
  --radius: 6px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
}
```

For data categories, define semantic CSS vars (e.g. `--hi`, `--int`, `--low`) plus `*-light` variants at 0.08 alpha for background fills. Pull actual color values from the active lab's palette file (see `palettes/`).

## Layout

| Element | Style |
|---------|-------|
| Page container | `max-width: 1040px`, centered, padding `48px 32px 64px` |
| Cards row | CSS grid, `repeat(3, 1fr)`, gap 12px |
| Card | White surface, border-radius 6px, subtle shadow, colored 3px top border for category |
| Panels | White surface, border-radius 6px, shadow, padding 24px, margin-bottom 16px |
| Two-column row | CSS grid `1fr 1fr`, gap 16px |
| Responsive | At 720px: collapse grids to single column |

## Interactivity Patterns

- **Tooltips**: dark background (`--text-primary`), white text, 12px, border-radius 6px, follow cursor with offset. Use `pointer-events: none` and opacity transitions.
- **Click-to-filter**: clicking a node dims unrelated flows (opacity 0.04) and highlights the selected node with a stroke. Click background to reset.
- **Mode toggle** (counts/percentages): pill-style segmented control (`border-radius: 6px`, background `#f0f0f0`). Active button gets white background + subtle shadow. Update all labels in-place without re-rendering the SVG structure.
- **Hover states on flows**: `fill-opacity` from 0.5 to 0.75 on hover.

## Data Visualization Conventions

- **Alluvial/sankey flows**: cubic bezier paths with linear gradient fills (source color to target color). Node bars 28px wide, rounded corners (rx 3).
- **Heatmaps**: cell fill uses category color at variable alpha (0.06 base + intensity * 0.55). Diagonal (concordant) cells get heavier stroke. Show both count and percentage per cell.
- **Bar charts**: horizontal diverging bars from a center zero line. Category-colored fills, signed delta labels outside bars.
- **Histograms**: stacked by reclassification status. Background zone shading at 0.04 alpha behind cutpoint regions. Dashed cutpoint lines with value labels.
- **Legends**: centered below chart, flex row, 12px, small colored dots (8px circle).

## Data Embedding

Embed the complete dataset as a `const D = {...}` JSON object in a `<script>` block. Structure:
- `categories`, `stages` (metadata)
- `flows` (aggregated transitions)
- `colors` (RGB per category)
- `summary` (totals, date range)
- `nodes` (source/dest counts)
- `reclassification` (concordance/upgraded/downgraded with n and pct)
- `raw_paired` (individual-level data for distribution plots)
- `cutpoints` (threshold values per assay)
