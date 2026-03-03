# Chipuk Lab Color Style

Color palette and policies for all Chipuk lab projects. Inherits all other visual conventions from the parent [`STYLE_GUIDE.md`](./STYLE_GUIDE.md).

## First-choice accent colors

When a plot needs one, two, or three colors and no semantic mapping applies, reach for these in order:

| Rank | Color | Hex |
|------|-------|-----|
| Primary | blue | `#0072B2` |
| Secondary | orange | `#E69F00` |
| Tertiary | bluish green | `#009E73` |

## Categorical palette

Okabe-Ito (8 colors). Designed for universal colorblind accessibility. Used for categorical variables with more than three levels or when a dedicated semantic mapping applies.

| Position | Color | Hex | Common use |
|----------|-------|-----|------------|
| 1 | orange | `#E69F00` | |
| 2 | sky blue | `#56B4E9` | |
| 3 | bluish green | `#009E73` | |
| 4 | yellow | `#F0E442` | |
| 5 | blue | `#0072B2` | |
| 6 | vermillion | `#D55E00` | |
| 7 | reddish purple | `#CC79A7` | |
| 8 | black | `#000000` | |

Access: `lab_palette("chipuk")` (R) or `get_lab_palette("chipuk")` (Python).

## Semantic mappings

Inherits universal semantic palettes. These map biological categories to fixed colors for consistency across all projects.

| Mapping | Category | Hex | Scale helpers |
|---------|----------|-----|---------------|
| Sex | Male | `#377EB8` (blue) | `scale_color_sex()`, `scale_fill_sex()` |
| Sex | Female | `#E41A1C` (red) | |
| Diagnosis | P- | `#4DAF4A` (green) | `scale_color_dx()`, `scale_fill_dx()` |
| Diagnosis | P+ | `#E41A1C` (red) | |
| Binary | Control | `#4DAF4A` (green) | |
| Binary | Case | `#E41A1C` (red) | |

Semantic colors are drawn from ColorBrewer Set1 (shared across all labs). Red signals "attention" (female, positive diagnosis, case); blue/green signals "baseline" (male, negative diagnosis, control).

## Heatmap palettes

Inherited from the main style guide:

- **Diverging** (centered at 0): `RdBu` / `RdBu_r`
- **Sequential** (density/counts): `Blues`

No Chipuk-specific overrides.
