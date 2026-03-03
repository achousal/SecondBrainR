# Example Lab Color Style

Color palette and policies for lab projects. Inherits all other visual conventions from the parent [`STYLE_GUIDE.md`](../../_code/styles/STYLE_GUIDE.md).

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

Access: `lab_palette("example")` (R) or `get_lab_palette("example")` (Python).

## Semantic mappings

Inherits universal semantic palettes. These map domain categories to fixed colors for consistency across all projects. Domain-specific semantic mappings (e.g., biomedical Sex/Diagnosis palettes) are defined in `_code/profiles/bioinformatics/` and similar profile directories.

| Mapping | Category | Hex | Notes |
|---------|----------|-----|-------|
| Direction | Up | `#E41A1C` (red) | Universal -- increase/alert |
| Direction | Down | `#377EB8` (blue) | Universal -- decrease/baseline |
| Binary | Control | `#4DAF4A` (green) | Universal -- reference group |
| Binary | Case | `#E41A1C` (red) | Universal -- experimental group |

Profile-specific palettes (e.g., Sex, Diagnosis) are loaded from `palettes.yaml` in the active domain profile. See `_code/profiles/` for examples.

## Heatmap palettes

Inherited from the main style guide:

- **Diverging** (centered at 0): `RdBu` / `RdBu_r`
- **Sequential** (density/counts): `Blues`
