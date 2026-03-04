---
description: "Plan and implementation record for the patient biomarker dashboard -- local-only HTML tool for clinician biomarker visualization"
type: development
status: complete
created: 2026-03-02
updated: 2026-03-02
---

# Patient Biomarker Dashboard -- Development

## Location

`_code/dashboard/` -- self-contained Vite + TypeScript project. Build output: `dist/index.html` (single-file HTML).

```bash
cd _code/dashboard
npm install
npm test          # 125 tests
npm run build     # validate panels -> typecheck -> vite build
```

---

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Deployment | Self-contained `.html` file | Maximum privacy, no server, works offline on `file://` |
| Build | Vite + `vite-plugin-singlefile` | TS safety for zone logic, good DX, single-file output |
| Gauges | Custom SVG via `d3-shape` (~15 kB) | Full control over zone coloring + design tokens |
| CSV/Excel | PapaParse (CSV) + SheetJS (Excel) | Both client-side, data never leaves browser |
| State | In-memory only | No localStorage/IndexedDB -- page refresh clears all data |
| Fonts | System fallback (no bundled web fonts) | Keeps output < 500 kB |
| Print | CSS `@media print` + browser "Save as PDF" | Zero dependency, reliable |
| Design | Match site/ design tokens exactly | Dark theme, amber/teal/green/red zones |
| Panel loading | `import.meta.glob` (build-time) | Panels inlined into bundle, zero runtime fetch, `file://` safe |
| Branding | YAML config per profile | Lab-specific title, institution, disclaimer, footer |
| Predictions | JSON upload + SHAP waterfall SVG | Same d3-shape approach as gauges, no extra deps |

---

## Project Structure

```
_code/dashboard/
  package.json                        # @engram-r/dashboard
  vite.config.ts                      # singlefile + yaml plugins, path aliases
  tsconfig.json
  index.html                          # dev entry
  schemas/
    panel.schema.json                 # JSON Schema for panel validation
    prediction.schema.json            # JSON Schema for prediction payloads
  scripts/
    validate-panels.ts                # build-time panel validation (ajv)
  dist/
    index.html                        # build artifact (the deliverable)
  src/
    main.ts                           # app entry, render loop, event binding
    types.ts                          # all TS interfaces
    vite-env.d.ts                     # Vite client type reference
    config/
      reference_ranges.ts             # panel loading via import.meta.glob
      branding.ts                     # branding config from profiles
      panels/                         # local fallback panel JSONs (dev)
        ad_panel.json
        vascbrain_panel.json
        general_panel.json
    data/
      parser.ts                       # CSV/Excel parsing (PapaParse + SheetJS)
      mapper.ts                       # column auto-detection via alias matching
      store.ts                        # in-memory state (no persistence)
      prediction_loader.ts            # prediction JSON parse + validate
    components/
      FileUpload.ts                   # drag-drop + file picker
      PanelSelector.ts                # dropdown to select biomarker panel
      ColumnMapper.ts                 # column mapping UI (shown only on mismatch)
      PatientNav.ts                   # prev/next, count, search-by-ID
      PatientHeader.ts                # display name, age, sex, visit date
      GaugeCard.ts                    # single biomarker card with gauge
      GaugeArc.ts                     # SVG half-arc renderer (d3-shape)
      SummaryStrip.ts                 # all biomarkers color-coded by zone
      PredictionPanel.ts              # probability meter + SHAP waterfall
    styles/
      tokens.css                      # design tokens from site/src/styles/global.css
      layout.css                      # grid, cards, responsive, @media print
      gauge.css                       # arc animation
      prediction.css                  # prediction panel + print styles
    utils/
      zone.ts                         # zone classification (correctness-critical)
      format.ts                       # number formatting (sig figs, units)
      print.ts                        # window.print() helper
    __tests__/
      zone.test.ts                    # 29 tests -- boundary conditions, edge cases
      mapper.test.ts                  # 32 tests -- alias resolution, partial match
      format.test.ts                  # 19 tests -- number formatting edge cases
      reference_ranges.test.ts        # 11 tests -- panel validation, loading
      panels.test.ts                  # 18 tests -- profile + local panel files
      prediction_loader.test.ts       # 16 tests -- parsing, validation, lookup
      fixtures/
        sample_ad.csv                 # 3 patients, known values
        sample_predictions.json       # 3 patients, SHAP values
  docs/
    panel-authoring.md                # full schema reference for external labs
  README.md                           # usage + architecture docs
  .gitignore
```

---

## Panel System

Panels define biomarker groups with reference ranges, zone colors, and clinical interpretations.

**Sources** (build-time, via `import.meta.glob`):
1. `_code/profiles/*/panels/*.json` -- profile panels (primary)
2. `src/config/panels/*.json` -- local fallbacks (dev)

Profile panels override local when IDs match.

**Validation**: `npm run validate:panels` checks all panel files against `schemas/panel.schema.json` (ajv, draft-07). Runs automatically before every build.

**Current panels**:
| Panel | ID | Biomarkers | Source |
|-------|-----|------------|--------|
| AD Classification | `ad_classification` | ptau217, NfL, GFAP, Ab42/Ab40 | Ashton 2024, Simren 2022 |
| VascBrain | `vascbrain` | ptau217, Ab40, Ab42, GFAP, NfL | SIMOA norms |
| General Clinical | `general_clinical` | CRP, eGFR, Albumin | Standard lab ranges, KDIGO 2012 |

**Adding panels**: create JSON in `_code/profiles/<profile>/panels/`, run `validate:panels`, rebuild. See `docs/panel-authoring.md`.

---

## Branding

Per-profile branding via `dashboard_config.yaml`:

```yaml
title: "Biomarker Report"
institution: "Elahi Lab"
disclaimer: "For research use only. Not for clinical diagnostic purposes."
footer: "Elahi Lab -- Icahn School of Medicine at Mount Sinai"
```

Loaded at build time from `_code/profiles/*/dashboard_config.yaml`. Falls back to defaults (title only) when no config exists.

---

## ML Predictions (SHAP + Risk Scores)

**Upload flow**: CSV/Excel first, then optional JSON prediction file via "Load Predictions" button.

**Visualization**:
- Probability meter: horizontal bar 0-1, color-coded (green < 0.3, amber 0.3-0.7, red > 0.7)
- Classification badge: pill with classification string
- SHAP waterfall: horizontal SVG bars sorted by |shapValue| descending, positive (red) extends right, negative (blue) extends left, base value as dashed reference line

**JSON format** (validated against `schemas/prediction.schema.json`):
```json
{
  "modelId": "ad_classifier_v2",
  "runId": "run_20260215",
  "patients": [{
    "patientId": "P001",
    "probability": 0.87,
    "classification": "AD Positive",
    "baseValue": 0.35,
    "shapValues": [
      { "feature": "ptau217", "value": 2.34, "shapValue": 0.28 }
    ]
  }]
}
```

**R export template**: `_code/R/export_predictions.R` -- shows how R pipelines produce this format.

---

## Key Layout

```
+------------------------------------------------------------------+
|  Biomarker Report  [Elahi Lab]  [AD Panel v]  [Upload] [Pred] [P]|
+------------------------------------------------------------------+
|  Jane Smith  |  Age: 67  |  Sex: F  |  Visit: 2026-02-15        |
|  [< prev]  Patient 3 of 47  [next >]  [Search: ____]            |
+------------------------------------------------------------------+
|  +------------------+  +------------------+  +------------------+ |
|  | p-tau 217  pg/mL |  | NfL        pg/mL |  | GFAP       pg/mL| |
|  |   [gauge arc]    |  |   [gauge arc]    |  |   [gauge arc]   | |
|  |      2.34        |  |      8.2         |  |      142        | |
|  |    Rule-in       |  |     Normal       |  |    Elevated     | |
|  | Amyloid likely   |  | In the normal    |  | Astrocyte       | |
|  | present          |  | range            |  | activation high | |
|  +------------------+  +------------------+  +------------------+ |
|                                                                    |
|  +------------------------------------------------------------+   |
|  | ML Prediction  [AD Positive]                                |   |
|  | Risk Score: [=============87.0%===========]                 |   |
|  | SHAP:  ptau217   [=====+0.28=====>]  2.34                  |   |
|  |        ab42_ab40 [===+0.15===>]      0.062                 |   |
|  |        nfl       [<-0.02]            8.2                   |   |
|  +------------------------------------------------------------+   |
|                                                                    |
|  [For research use only. Not for clinical diagnostic purposes.]    |
+------------------------------------------------------------------+
|  Summary: ptau217 [red] | NfL [green] | GFAP [amber] | Ab42 [red]|
+------------------------------------------------------------------+
|  Elahi Lab -- Icahn School of Medicine at Mount Sinai              |
+------------------------------------------------------------------+
```

---

## Implementation Record

### Phase 1 -- Initial Build (2026-03-02)

Scaffold at `_code/dashboard/`. Vite + TypeScript, single-file output. 3 hardcoded panel JSONs. 91 tests across 4 files.

### Platform Refactoring (2026-03-02)

Five-phase refactoring to domain-agnostic platform. Full plan: `docs/development/biomarker-dashboard-platform.md`.

| Phase | What | Key Files |
|-------|------|-----------|
| 1. Scaffold | Project at `_code/dashboard/`, section in `ops/sections.yaml` | `package.json`, `vite.config.ts` |
| 2. Panel Registry | Dynamic loading via `import.meta.glob` from profiles | `reference_ranges.ts`, `schemas/panel.schema.json`, `scripts/validate-panels.ts` |
| 3. Branding | Per-profile title, institution, disclaimer, footer | `branding.ts`, `dashboard_config.yaml` |
| 4. Predictions | Probability meter + SHAP waterfall, JSON loader | `PredictionPanel.ts`, `prediction_loader.ts`, `prediction.css` |
| 5. Documentation | README, panel authoring guide, profile docs | `README.md`, `docs/panel-authoring.md` |

### Current metrics

| Metric | Value |
|--------|-------|
| Tests | 125 passing (6 files) |
| Build size | 436 kB (143 kB gzipped) |
| TypeScript | Clean compile, zero errors |
| Panel validation | 3 profile + 3 local panels pass schema |

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| vite | ^6.2.0 | Build tool |
| vite-plugin-singlefile | ^2.0.0 | Inline all assets |
| vite-plugin-yaml2 | ^1.1.5 | YAML imports |
| d3-shape | ^3.2.0 | SVG arc generation |
| papaparse | ^5.5.0 | CSV parsing |
| xlsx | 0.20.3 | Excel parsing |
| ajv | ^8.18.0 | JSON Schema validation |
| tsx | ^4.21.0 | TS script runner |
| vitest | ^3.0.0 | Test runner |
| @vitest/coverage-v8 | ^3.0.0 | Coverage |

### Critical reference files

| File | Purpose |
|---|---|
| `site/src/styles/global.css` | Design tokens (colors, fonts, spacing) |
| `_code/profiles/bioinformatics/panels/` | Canonical panel configs |
| `_code/profiles/bioinformatics/dashboard_config.yaml` | Lab branding |
| `_code/R/export_predictions.R` | R template for prediction export |
| `_code/src/engram_r/plot_theme.py` | Zone color conventions |

---

## Verification Checklist

1. [x] `npm run build` produces a single `dist/index.html` file
2. [x] `npm test` -- 125 tests pass
3. [x] `npm run validate:panels` -- all panels pass schema
4. [x] TypeScript clean compile
5. [ ] Open `index.html` via `file://` in Chrome -- page renders, dark theme correct
6. [ ] Upload `sample_ad.csv` fixture -- gauges render with correct zone colors
7. [ ] Navigate between patients with prev/next -- values update
8. [ ] Load `sample_predictions.json` -- SHAP waterfall + probability meter render
9. [ ] Click Print -- clean printable layout, controls hidden, disclaimer/footer visible
10. [ ] Verify no network requests in DevTools Network tab (privacy guarantee)
11. [ ] Open in Firefox and Safari -- cross-browser check
