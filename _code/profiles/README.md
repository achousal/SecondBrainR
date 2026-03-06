# Domain Profiles

Domain profiles provide domain-specific configuration, palettes, confounders, heuristics, and templates that customize EngramR for a particular research field.

## Structure

```
profiles/
  {domain-name}/
    profile.yaml              # metadata + config overrides
    identity.yaml             # domain, purpose, focus areas for self/identity.md

    palettes/                  # WHO uses what colors
      _semantic.yaml           # cross-lab semantic mappings (sex, dx, binary)
      {lab-name}.yaml          # per-lab categorical + accent colors

    confounders.yaml           # data layer -> confounder mappings
    heuristics.yaml            # file type/tool -> data layer inference rules
    pii_patterns.yaml          # additional PII column patterns

    styles/
      formats/                 # HOW -- output format conventions
        static-plots.md        # PDF/SVG ggplot2 geometry, sizing, annotations
        interactive-html.md    # HTML dashboard: layout, typography, interactivity
      labs/                    # WHO -- lab visual identity + branding
        {lab-name}.md          # accent palette, semantic overrides, dashboard branding
      projects/                # WHAT -- project-specific plot overrides
        {project-name}.md      # facet layouts, dimensions, annotation specs

    panels/                    # biomarker dashboard panel configs (JSON)
```

## Three Dimensions

Profile styles are organized along three orthogonal dimensions:

| Dimension | Directory | Question | Grows by... |
|-----------|-----------|----------|-------------|
| **Format** | `styles/formats/` | How does this output type look? | Adding a format doc (e.g. `slides.md`, `posters.md`) |
| **Lab** | `styles/labs/` + `palettes/` | What's this lab's visual identity? | Adding a lab YAML + lab doc |
| **Project** | `styles/projects/` | What project-specific overrides apply? | Adding a project doc |

**Resolution order**: project overrides > lab identity > format conventions > domain defaults.

## New User Setup

After cloning, populate your lab-specific files from the provided templates:

```bash
# Lab palette
cp palettes/lab-name.yaml.example palettes/my-lab.yaml

# Lab visual identity
cp styles/labs/lab-name.md.example styles/labs/my-lab.md

# Project overrides (one per project)
cp styles/projects/project-name.md.example styles/projects/my-project.md

# Dashboard panels
cp panels/panel-name.json.example panels/my-panel.json

# Dashboard branding
cp dashboard_config.yaml.example dashboard_config.yaml
```

These user files are gitignored -- they stay local and never conflict with upstream.

## What's Tracked vs Ignored

| Tracked (shared) | Ignored (local) |
|-------------------|-----------------|
| `profile.yaml`, `identity.yaml` | Lab palettes (`palettes/*.yaml` except `_semantic.yaml`) |
| `confounders.yaml`, `heuristics.yaml`, `pii_patterns.yaml` | Lab styles (`styles/labs/*.md`) |
| `palettes/_semantic.yaml` (cross-lab semantic colors) | Project overrides (`styles/projects/*.md`) |
| `styles/formats/*.md` (output format conventions) | Dashboard panels (`panels/*.json`) |
| All `*.example` templates | `dashboard_config.yaml` |

## Creating a New Domain Profile

1. Copy an existing profile directory as a starting point
2. Edit `profile.yaml` with your domain metadata and config overrides
3. Define cross-lab semantic colors in `palettes/_semantic.yaml`
4. Add format conventions in `styles/formats/`
5. Create `*.example` templates for lab palettes, lab styles, project overrides, and panels
6. Define domain-specific confounders, heuristics as needed

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
- **`styles/labs/{lab}.md`**: Contains dashboard branding (title, institution, disclaimer, footer) in the "Dashboard branding" section.

These files are consumed by `_code/dashboard/` during `npm run build`.
