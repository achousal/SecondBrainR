# Biomarker Dashboard

Self-contained HTML tool for clinician biomarker visualization. Opens in any browser, works offline via `file://`, no server required. Patient data never leaves the browser.

## Quick Start

1. Open `dist/index.html` in your browser
2. Select a biomarker panel from the dropdown
3. Upload a CSV or Excel file with patient data
4. Navigate between patients with prev/next buttons
5. Click Print to save as PDF

## Building

```bash
npm install
npm test          # run 125 tests
npm run build     # validate panels + typecheck + build
```

The build produces a single `dist/index.html` file (~436 kB, ~143 kB gzipped) containing all code, styles, and panel configurations inline.

## Panel System

Panels are JSON configurations that define biomarkers, reference ranges, and zone colors. Panels are loaded from two sources at build time:

1. **Profile panels** (primary): `_code/profiles/*/panels/*.json`
2. **Local fallbacks** (dev): `src/config/panels/*.json`

Profile panels take priority when IDs match (deduplication by `id` field).

### Adding a new panel

1. Create a JSON file following the schema in `schemas/panel.schema.json`
2. Place it in your profile's `panels/` directory (e.g., `_code/profiles/bioinformatics/panels/my_panel.json`)
3. Run `npm run validate:panels` to check
4. Rebuild: `npm run build`

See `docs/panel-authoring.md` for the full schema reference.

### Panel JSON structure

```json
{
  "id": "my_panel",
  "name": "My Panel",
  "version": "1.0.0",
  "description": "Description for clinicians",
  "biomarkers": [
    {
      "id": "biomarker_id",
      "name": "Display Name",
      "unit": "pg/mL",
      "aliases": ["alt_name1", "alt_name2"],
      "zones": [
        {
          "label": "Normal",
          "min": 0,
          "max": 10,
          "color": "#4a9e6b",
          "interpretation": "Within normal range."
        },
        {
          "label": "Elevated",
          "min": 10,
          "max": 100,
          "color": "#c75a4a",
          "interpretation": "Above normal range."
        }
      ],
      "source": "Reference citation"
    }
  ]
}
```

**Zone rules**: Zones must be contiguous (no gaps or overlaps). Each zone's `min` must equal the previous zone's `max`. Colors use hex codes from the design token palette.

**Aliases**: Alternative column names for auto-detection. Include common variations (underscored, hyphenated, abbreviated). The mapper normalizes headers by lowercasing and stripping non-alphanumeric characters.

## Branding

Lab-specific branding is configured via `dashboard_config.yaml` in the profile directory:

```yaml
title: "Biomarker Report"
institution: "Lab Name"
disclaimer: "For research use only."
footer: "Lab Name -- Institution"
```

Without a config file, defaults are used (title only, no institution/disclaimer/footer).

## ML Predictions (Optional)

The dashboard supports loading ML prediction results with SHAP feature explanations.

### Upload flow

1. Load patient biomarker data (CSV/Excel) first
2. Click "Load Predictions" in the top bar
3. Select a prediction JSON file
4. SHAP waterfall and probability meter appear per patient

### Prediction JSON format

```json
{
  "modelId": "model_name",
  "runId": "run_id",
  "patients": [
    {
      "patientId": "P001",
      "probability": 0.87,
      "classification": "AD Positive",
      "baseValue": 0.35,
      "shapValues": [
        { "feature": "ptau217", "value": 2.34, "shapValue": 0.28 },
        { "feature": "nfl", "value": 8.2, "shapValue": -0.02 }
      ]
    }
  ]
}
```

Patient IDs in the prediction file must match IDs in the uploaded CSV/Excel data.

See `_code/R/export_predictions.R` for an R template that produces this format.

## Privacy

- All data processing happens in-browser (JavaScript)
- No network requests are made (verify in DevTools Network tab)
- No data is persisted (page refresh clears everything)
- Works offline via `file://` protocol
- Print/PDF uses the browser's built-in print dialog

## Architecture

```
src/
  main.ts                    # App entry point, event binding, render loop
  types.ts                   # All TypeScript interfaces
  config/
    reference_ranges.ts      # Panel loading via import.meta.glob
    branding.ts              # Branding config from profiles
    panels/                  # Local fallback panel JSONs
  data/
    parser.ts                # CSV/Excel parsing (PapaParse + SheetJS)
    mapper.ts                # Column auto-detection via alias matching
    store.ts                 # In-memory state (no persistence)
    prediction_loader.ts     # Prediction JSON parsing + validation
  components/
    GaugeArc.ts              # SVG half-arc gauge (d3-shape)
    GaugeCard.ts             # Biomarker card wrapper
    PredictionPanel.ts       # Probability meter + SHAP waterfall
    SummaryStrip.ts          # Zone-colored summary bar
    PatientHeader.ts         # Demographics display
    PatientNav.ts            # Navigation controls
    FileUpload.ts            # Drag-drop file input
    PanelSelector.ts         # Panel dropdown
    ColumnMapper.ts          # Manual column mapping UI
  styles/
    tokens.css               # Design tokens (colors, fonts)
    layout.css               # Grid, cards, responsive, print
    gauge.css                # Gauge animation
    prediction.css           # Prediction panel styles
  utils/
    zone.ts                  # Zone classification (correctness-critical)
    format.ts                # Number formatting
    print.ts                 # Print helper
```

## Dependencies

| Package | Purpose |
|---------|---------|
| vite | Build tool |
| vite-plugin-singlefile | Inline all assets into single HTML |
| vite-plugin-yaml2 | Import YAML configs at build time |
| d3-shape | SVG arc generation for gauges |
| papaparse | CSV parsing |
| xlsx (SheetJS) | Excel parsing |
| ajv | JSON Schema validation (build time) |
| tsx | TypeScript script runner (build time) |
| vitest | Test runner |
