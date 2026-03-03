# Elahi Lab Color Style

Color palette and policies for all Elahi lab projects. Inherits all other visual conventions from the parent [`STYLE_GUIDE.md`](./STYLE_GUIDE.md).

## First-choice accent colors

When a plot needs one, two, or three colors and no semantic mapping applies, reach for these in order:

| Rank | Color | R name | Hex |
|------|-------|--------|-----|
| Primary | purple | `purple1` | `#9B30FF` |
| Secondary | orange | `orange1` | `#FFA500` |
| Tertiary | light green | `lightgreen` | `#90EE90` |

## Categorical palette

ColorBrewer Set1 (8 colors). Used for categorical variables with more than three levels or when a dedicated semantic mapping applies.

| Position | Color | Hex | Common use |
|----------|-------|-----|------------|
| 1 | red | `#E41A1C` | |
| 2 | blue | `#377EB8` | |
| 3 | green | `#4DAF4A` | |
| 4 | muted purple | `#984EA3` | |
| 5 | orange | `#FF7F00` | |
| 6 | brown | `#A65628` | |
| 7 | pink | `#F781BF` | |
| 8 | grey | `#999999` | |

Access: `lab_palette("elahi")` (R) or `get_lab_palette("elahi")` (Python).

## Semantic mappings

These map biological categories to fixed colors for consistency across all Elahi projects.

| Mapping | Category | Hex | Scale helpers |
|---------|----------|-----|---------------|
| Sex | Male | `#377EB8` (blue) | `scale_color_sex()`, `scale_fill_sex()` |
| Sex | Female | `#E41A1C` (red) | |
| Diagnosis | P- | `#4DAF4A` (green) | `scale_color_dx()`, `scale_fill_dx()` |
| Diagnosis | P+ | `#E41A1C` (red) | |
| Binary | Control | `#4DAF4A` (green) | |
| Binary | Case | `#E41A1C` (red) | |

All drawn from Set1 positions. Red signals "attention" (female, positive diagnosis, case); blue/green signals "baseline" (male, negative diagnosis, control).


## Heatmap palettes

Inherited from the main style guide:

- **Diverging** (centered at 0): `RdBu` / `RdBu_r`
- **Sequential** (density/counts): `Blues`

No Elahi-specific overrides.
