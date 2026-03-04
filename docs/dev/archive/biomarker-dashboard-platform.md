# Biomarker Dashboard -- Domain-Agnostic Platform Refactoring

## Context

The Phase 1 biomarker dashboard (`projects/elahi_lab/biomarker-dashboard/`) is a working single-file HTML tool for clinician biomarker visualization. It's lab-specific: 3 hardcoded panel JSONs, hardcoded title, no branding layer. The goal is to make it a reusable platform where:

- **Any lab** can add biomarker panels via JSON configs (no code changes)
- **Lab-specific branding** (institution, disclaimer, footer) is configurable per profile
- **Phase 2 predictions** (risk scores + SHAP values) are implemented against existing stub interfaces
- **Single HTML file** delivery is preserved (offline, file://, no server)

The existing domain profile system (`_code/profiles/`) already provides the pattern: profile.yaml, palettes.yaml, styles/, confounders.yaml. Adding `panels/` and `dashboard_config.yaml` follows the established architecture.

---

## Phase 1: Migration Scaffold

**Goal**: Move dashboard to `_code/dashboard/`, verify 64 tests + build pass unchanged.

### Files
- **Copy** entire `projects/elahi_lab/biomarker-dashboard/` -> `_code/dashboard/`
- **Modify** `_code/dashboard/package.json`: rename to `@engram-r/dashboard`
- **Modify** `ops/sections.yaml`: add `dashboard` section
- **Create** `projects/elahi_lab/biomarker-dashboard/MOVED.md`: pointer to new location

### Validation
```bash
cd _code/dashboard && npm install && npm test && npm run build
# 64 tests pass, dist/dashboard.html produced
```

---

## Phase 2: Panel Registry (Dynamic Loading from Profiles)

**Goal**: Replace static panel imports with build-time dynamic loading from `_code/profiles/*/panels/*.json`.

### Files

**Move panels**:
- `src/config/panels/ad_panel.json` -> `_code/profiles/bioinformatics/panels/ad_panel.json`
- `src/config/panels/vascbrain_panel.json` -> `_code/profiles/bioinformatics/panels/vascbrain_panel.json`
- `src/config/panels/general_panel.json` -> `_code/profiles/bioinformatics/panels/general_panel.json`
- Keep local copies in `src/config/panels/` as dev fallbacks

**Create**:
- `_code/dashboard/schemas/panel.schema.json` -- JSON Schema 2020-12 for panel validation
- `_code/dashboard/scripts/validate-panels.ts` -- build-time schema validation (uses `ajv`)
- `_code/dashboard/src/__tests__/panels.test.ts` -- dynamic loading tests

**Modify**:
- `src/config/reference_ranges.ts` -- replace 3 static imports with `import.meta.glob`:
  ```typescript
  // Profile panels (build-time resolved, inlined into bundle)
  const profilePanels = import.meta.glob(
    "../../../profiles/*/panels/*.json",
    { eager: true, import: "default" }
  );
  // Local fallbacks for standalone dev
  const localPanels = import.meta.glob(
    "./panels/*.json",
    { eager: true, import: "default" }
  );
  ```
  `validatePanel()` stays identical. `loadPanels()` collects from both sources, profile panels take priority (dedup by `id`).
- `vite.config.ts` -- add `resolve.alias` for `@profiles` path, extend coverage include to `src/config/**`
- `package.json` -- add `ajv`, `tsx` to devDeps; add `"validate:panels"` script; wire into build: `"build": "npm run validate:panels && tsc && vite build"`

### Key insight
`import.meta.glob` resolves at **build time** and inlines JSON into the bundle. Zero runtime fetch. The `file://` offline guarantee is preserved because Vite resolves the glob during compilation, not at page load.

### Validation
```bash
cd _code/dashboard && npm test && npm run build
# All tests pass (64 existing + ~5 new panel tests)
# dist/dashboard.html loads same 3 panels
```

---

## Phase 3: Lab Branding Layer

**Goal**: Configurable title, institution, disclaimer, footer per profile.

### Files

**Create**:
- `_code/profiles/bioinformatics/dashboard_config.yaml`:
  ```yaml
  title: "Biomarker Report"
  institution: "Elahi Lab"
  disclaimer: "For research use only. Not for clinical diagnostic purposes."
  footer: "Elahi Lab -- Icahn School of Medicine at Mount Sinai"
  ```
- `_code/dashboard/src/config/branding.ts` -- loads config via `import.meta.glob("../../../profiles/*/dashboard_config.yaml")`, falls back to defaults

**Modify**:
- `src/types.ts` -- add `DashboardConfig` interface (`title`, `institution`, `logoSvg?`, `disclaimer`, `footer`)
- `src/main.ts` -- replace hardcoded `"Biomarker Report"` with `branding.title`; add institution in top bar; add disclaimer below gauge grid; add footer
- `src/styles/layout.css` -- add `.dashboard-disclaimer`, `.dashboard-footer`, print styles for both
- `vite.config.ts` -- add `vite-plugin-yaml2` to plugins (enables YAML imports)
- `package.json` -- add `vite-plugin-yaml2` devDep

### Validation
- Build shows "Biomarker Report" title, "Elahi Lab" institution, disclaimer, footer
- Without `dashboard_config.yaml`, defaults are used (backward compatible)

---

## Phase 4: Phase 2 Prediction Layer (Risk Scores + SHAP)

**Goal**: Implement risk score visualization + SHAP waterfall against existing stub interfaces.

### Interfaces (already defined in types.ts, no changes needed)
- `PredictionPayload` -- `{ modelId, runId, patients: PredictionResult[] }`
- `PredictionResult` -- `{ patientId, probability, classification, shapValues, baseValue }`
- `ShapEntry` -- `{ feature, value, shapValue }`

### Files

**Create**:
- `_code/dashboard/schemas/prediction.schema.json` -- JSON Schema for prediction payload
- `src/data/prediction_loader.ts`:
  - `parsePredictionJson(text: string): PredictionPayload` -- parse + validate
  - `getPredictionForPatient(payload, patientId): PredictionResult | null`
- `src/styles/prediction.css` -- probability meter, SHAP waterfall, print-safe styles
- `src/__tests__/prediction_loader.test.ts` -- parsing, validation, patient lookup
- `src/__tests__/fixtures/sample_predictions.json` -- test fixture
- `_code/R/export_predictions.R` -- template/example showing how R pipelines produce the JSON format (documentation, not runtime dep)

**Modify**:
- `src/components/PredictionPanel.ts` -- replace stub with full implementation:
  - **Probability meter**: horizontal bar 0-1, color-coded (green < 0.3, amber 0.3-0.7, red > 0.7)
  - **Classification badge**: pill badge with classification string
  - **SHAP waterfall**: horizontal SVG bar chart (same d3-shape approach as GaugeArc):
    - Positive SHAP bars extend right (red/amber)
    - Negative SHAP bars extend left (blue/green)
    - Sorted by |shapValue| descending
    - Base value as vertical reference line
    - Feature name + raw value as labels
- `src/main.ts`:
  - Add "Load Predictions" button in top bar (shown when patient data loaded)
  - Second file input accepting `.json` only
  - On JSON load: parse with `parsePredictionJson()`, store in `state.predictionData`
  - Pass matched `PredictionResult` to `renderPredictionPanel()` per patient
  - Update `render()` to pass prediction data: `renderPredictionPanel(prediction, branding)`
- `index.html` -- add `prediction.css` link

### Validation
```bash
# Unit tests
cd _code/dashboard && npm test
# Manual: upload CSV + predictions JSON, verify SHAP waterfall renders per patient
```

---

## Phase 5: Documentation + Cleanup

### Files

**Create**:
- `_code/dashboard/README.md` -- clinician usage (open file, select panel, upload, print, privacy guarantee), panel authoring guide (JSON schema, zone rules, alias patterns), prediction JSON format
- `_code/dashboard/docs/panel-authoring.md` -- detailed schema reference with examples for external labs

**Modify**:
- `_code/profiles/README.md` -- document `panels/` and `dashboard_config.yaml` extensions
- `docs/development/biomarker-dashboard.md` -- update to reference new location, add Phase 2 record

---

## Dependency Order

```
Phase 1 (scaffold) -> Phase 2 (panel registry) -> Phase 3 (branding)
                                                |
                                                +-> Phase 4 (predictions)
                                                |
Phase 5 (docs) depends on all above -----------+
```

Phases 3 and 4 are independent and can run in parallel after Phase 2.

## New Dependencies

| Package | Purpose | Phase |
|---------|---------|-------|
| `ajv` (devDep) | JSON Schema validation at build time | 2 |
| `vite-plugin-yaml2` (devDep) | Import YAML in Vite | 3 |
| `tsx` (devDep) | Run TS build scripts | 2 |

## Critical Files

| File | Role |
|------|------|
| `src/config/reference_ranges.ts` | Primary coupling point -- static imports -> `import.meta.glob` |
| `src/main.ts` | App entry -- branding injection, prediction upload, render loop |
| `src/types.ts` | Type system -- add `DashboardConfig`, verify Phase 2 stubs |
| `src/components/PredictionPanel.ts` | Stub -> full SHAP + probability implementation |
| `vite.config.ts` | Build config -- path aliases, YAML plugin, coverage paths |
| `_code/profiles/bioinformatics/` | Target for moved panels + new dashboard_config.yaml |
| `ops/sections.yaml` | Register dashboard as a code section |

## Unresolved questions: none.
