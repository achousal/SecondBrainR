# Panel Authoring Guide

This guide explains how to create biomarker panel configurations for the dashboard.

## Overview

A panel is a JSON file that defines a group of related biomarkers with their reference ranges, zone colors, and clinical interpretations. Panels are validated against `schemas/panel.schema.json` at build time.

## File location

Place panel files in your domain profile's `panels/` directory:

```
_code/profiles/<profile>/panels/<panel_name>.json
```

For example: `_code/profiles/bioinformatics/panels/my_panel.json`

## Schema reference

### Panel (top level)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier. Lowercase, underscores. Pattern: `^[a-z][a-z0-9_]*$` |
| `name` | string | yes | Display name shown in the panel selector |
| `version` | string | yes | Semantic version (e.g., `1.0.0`) |
| `description` | string | yes | Clinical context for the panel |
| `biomarkers` | array | yes | At least one biomarker configuration |

### Biomarker

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique within the panel. Pattern: `^[a-z][a-z0-9_]*$` |
| `name` | string | yes | Display name (e.g., "p-tau 217") |
| `unit` | string | yes | Unit of measurement (e.g., "pg/mL", "ratio", "mg/L") |
| `aliases` | string[] | yes | Alternative column names for auto-detection |
| `zones` | array | yes | At least one zone definition |
| `source` | string | no | Citation for reference ranges |
| `notes` | string | no | Additional clinical notes |

### Zone

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | yes | Zone name (e.g., "Normal", "Elevated", "High") |
| `min` | number | yes | Lower bound (inclusive) |
| `max` | number | yes | Upper bound (exclusive for non-last zones, inclusive for last) |
| `color` | string | yes | Hex color code (e.g., "#4a9e6b"). Pattern: `^#[0-9a-fA-F]{6}$` |
| `interpretation` | string | yes | Patient-friendly explanation |

## Zone rules

1. **Contiguous**: zones must cover a continuous range with no gaps or overlaps
2. **Ordered**: each zone's `min` must equal the previous zone's `max`
3. **At least one**: every biomarker needs at least one zone

### Standard color palette

| Color | Hex | Usage |
|-------|-----|-------|
| Green | `#4a9e6b` | Normal, low risk |
| Blue | `#5ba3c9` | Rule-out, negative, low |
| Amber | `#d4a24e` | Intermediate, borderline, elevated |
| Red | `#c75a4a` | High, rule-in, abnormal |

## Alias patterns

Aliases enable auto-detection of CSV/Excel column names. The mapper normalizes headers by:
1. Converting to lowercase
2. Stripping all non-alphanumeric characters

Include common variations:
- Exact match: `"ptau217"`
- Hyphenated: `"p-tau217"`
- Underscored: `"ptau_217"`
- Full name: `"plasma_ptau217"`

## Example: minimal panel

```json
{
  "id": "lipid_panel",
  "name": "Lipid Panel",
  "version": "1.0.0",
  "description": "Standard lipid panel with clinical ranges",
  "biomarkers": [
    {
      "id": "total_cholesterol",
      "name": "Total Cholesterol",
      "unit": "mg/dL",
      "aliases": ["total_cholesterol", "cholesterol", "tc", "total_chol"],
      "zones": [
        {
          "label": "Desirable",
          "min": 0,
          "max": 200,
          "color": "#4a9e6b",
          "interpretation": "Desirable cholesterol level."
        },
        {
          "label": "Borderline",
          "min": 200,
          "max": 240,
          "color": "#d4a24e",
          "interpretation": "Borderline high. Consider lifestyle changes."
        },
        {
          "label": "High",
          "min": 240,
          "max": 1000,
          "color": "#c75a4a",
          "interpretation": "High cholesterol. Medical review recommended."
        }
      ],
      "source": "ATP III Guidelines"
    }
  ]
}
```

## Validation

Run the build-time validator:

```bash
cd _code/dashboard
npm run validate:panels
```

This checks all panels in profile directories and local fallbacks against the JSON Schema.

## Build

After adding or modifying panels, rebuild the dashboard:

```bash
npm run build
```

Panels are inlined into the HTML bundle at build time via Vite's `import.meta.glob`. No runtime fetching occurs.
