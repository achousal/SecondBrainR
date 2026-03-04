---
name: profile-generate
description: "Generate all profile YAML files atomically from collected interview data. Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: sonnet
allowed-tools:
  - Read
  - Write
  - Bash
---

## EXECUTE NOW

**Target: $ARGUMENTS**

You generate a complete domain profile directory from collected interview data. The data is passed as a structured block in $ARGUMENTS.

### Step 1: Read Schema Reference

```
Read .claude/skills/profile/reference/file-schemas.md
```

### Step 2: Parse Input Data

Extract from $ARGUMENTS:
- `name`: profile name (machine-safe)
- `description`: domain description
- `purpose`: agent purpose statement
- `focus_areas`: list of 2-4 focus areas
- `data_layers`: list of data layer names
- `file_extensions`: dict mapping extension -> layer
- `tool_references`: dict mapping tool -> layer
- `confounders`: dict mapping layer -> list of confounders
- `biological_confounders`: list
- `data_reality_signals`: dict with species_column and rules
- `pii_patterns`: list of regex patterns
- `literature_primary`: primary backend
- `literature_fallback`: fallback backend
- `literature_sources`: list of backends
- `env_vars_required`: dict
- `env_vars_optional`: dict
- `lab_palette`: list of hex colors (or empty for default)
- `semantic_palettes`: dict (or empty)

### Step 3: Create Profile Directory

```bash
mkdir -p _code/profiles/{name}
```

### Step 4: Write profile.yaml

Use the schema from file-schemas.md. All string values must be double-quoted. Write using the Write tool.

### Step 5: Write confounders.yaml

Top-level keys = data layer names. Include biological_confounders and data_reality_signals sections.

### Step 6: Write heuristics.yaml

Map file_extensions and tool_references to their data layers.

### Step 7: Write pii_patterns.yaml

Write column_patterns list with all regex patterns.

### Step 8: Write palettes.yaml (if palette data provided)

If lab_palette is empty, use the Wong 2011 default:
```yaml
labs:
  default:
    - "#E69F00"
    - "#56B4E9"
    - "#009E73"
    - "#F0E442"
    - "#0072B2"
    - "#D55E00"
    - "#CC79A7"
    - "#000000"
```

If semantic_palettes provided, include the semantic section.

### Step 9: Return Summary

Return:
```
GENERATED: _code/profiles/{name}/
Files: profile.yaml, confounders.yaml, heuristics.yaml, pii_patterns.yaml, palettes.yaml
Status: complete
```

### Critical Rules

- All YAML string values MUST be double-quoted
- Never include comments that could break YAML parsing
- Layer names in sidecar files MUST exactly match profile.yaml data_layers
- Hex values must be 7 characters: # + 6 hex digits
- Profile name must be lowercase with hyphens only
