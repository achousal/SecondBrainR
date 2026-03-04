# Domain Profiles

Domain profiles provide domain-specific configuration, palettes, confounders, heuristics, and templates that customize EngramR for a particular research field.

## Structure

```
profiles/
  {domain-name}/
    profile.yaml         # metadata + config overrides
    identity.yaml        # domain, purpose, focus areas for self/identity.md
    palettes.yaml        # lab + domain semantic palettes
    confounders.yaml     # data layer -> confounder mappings
    heuristics.yaml      # file type/tool -> data layer inference rules
    pii_patterns.yaml    # additional PII column patterns
    styles/              # domain-specific plot supplements
    templates/           # domain-specific template overrides
    panels/              # biomarker dashboard panel configs (JSON)
    dashboard_config.yaml  # dashboard branding (title, institution, disclaimer, footer)
```

## Creating a New Profile

1. Copy an existing profile directory as a starting point
2. Edit `profile.yaml` with your domain metadata and config overrides
3. Define domain-specific palettes, confounders, heuristics as needed
4. Add any domain-specific style guides or templates

## Activation

Set `domain.name` in `ops/config.yaml` to your profile name. The profile is loaded during `/onboard` and applied to vault configuration.

## Profile Loading

Use `engram_r.domain_profile` to discover and load profiles programmatically:

```python
from engram_r.domain_profile import load_profile, discover_profiles

profiles = discover_profiles()  # list available profile names
profile = load_profile("bioinformatics")  # load a specific profile
```

## Dashboard Integration

Profiles can include biomarker panel configurations and dashboard branding:

- **`panels/*.json`**: Biomarker panel configs loaded at build time by the dashboard. See `_code/dashboard/docs/panel-authoring.md` for the schema reference.
- **`dashboard_config.yaml`**: Branding config (title, institution, disclaimer, footer) injected into the dashboard at build time.

These files are consumed by `_code/dashboard/` during `npm run build`.
