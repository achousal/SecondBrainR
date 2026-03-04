# Domain Profile Examples

Three worked examples showing how different research domains map to profile configuration. Use these as guidance when interviewing users -- adapt the structure, not the content.

---

## Example 1: Materials Science

```yaml
# profile.yaml
name: "materials-science"
description: "Computational materials science and solid-state characterization"
version: "1.0"
identity:
  purpose: "Co-scientist for structure-property relationship discovery in materials"
  domain: "Materials science and engineering"
  focus_areas:
    - "crystal structure prediction"
    - "mechanical property optimization"
    - "thin film characterization"
config_overrides:
  data_layers:
    - "X-ray diffraction"
    - "Electron microscopy"
    - "Mechanical testing"
    - "Computational simulation"
  research:
    primary: "arxiv"
    fallback: "semantic_scholar"
    last_resort: "web-search"
  literature:
    sources: [arxiv, semantic_scholar, openalex]
    default: "all"
    enrichment:
      enabled: [crossref, unpaywall]
      timeout_per_doi: 5
env_vars:
  required:
    OPENALEX_API_KEY: "OpenAlex API key -- https://openalex.org/"
  optional:
    S2_API_KEY: "Semantic Scholar higher rate limits"
```

```yaml
# confounders.yaml
X-ray diffraction:
  - "Sample preparation artifacts"
  - "Preferred orientation"
  - "Instrument calibration drift"
Electron microscopy:
  - "Beam damage"
  - "Sample thickness variation"
  - "Coating artifacts"
Mechanical testing:
  - "Strain rate sensitivity"
  - "Sample geometry effects"
  - "Environmental conditions"
Computational simulation:
  - "Basis set convergence"
  - "Pseudopotential choice"
  - "k-point sampling density"
biological_confounders: []
data_reality_signals:
  species_column: null
  rules:
    - condition: "simulation-only"
      claim: "computational predictions require experimental validation"
    - condition: "single-crystal-only"
      claim: "single-crystal results may not generalize to polycrystalline materials"
```

```yaml
# heuristics.yaml
file_extensions:
  ".cif": "X-ray diffraction"
  ".xyz": "Computational simulation"
  ".dm3": "Electron microscopy"
  ".tif": "Electron microscopy"
tool_references:
  "VASP": "Computational simulation"
  "Quantum ESPRESSO": "Computational simulation"
  "GSAS": "X-ray diffraction"
  "DigitalMicrograph": "Electron microscopy"
```

```yaml
# pii_patterns.yaml
column_patterns:
  - "\\bsample[\\s_]?id\\b"
  - "\\boperator[\\s_]?name\\b"
  - "\\blab[\\s_]?notebook[\\s_]?ref\\b"
```

---

## Example 2: Social Epidemiology

```yaml
# profile.yaml
name: "social-epidemiology"
description: "Population health and social determinants of disease"
version: "1.0"
identity:
  purpose: "Co-scientist for social determinant-health outcome relationship discovery"
  domain: "Social epidemiology and population health"
  focus_areas:
    - "health disparities"
    - "neighborhood effects"
    - "life course epidemiology"
config_overrides:
  data_layers:
    - "Survey data"
    - "Administrative records"
    - "Geospatial data"
    - "Census data"
  research:
    primary: "pubmed"
    fallback: "openalex"
    last_resort: "web-search"
  literature:
    sources: [pubmed, openalex, semantic_scholar]
    default: "all"
    enrichment:
      enabled: [crossref, unpaywall]
      timeout_per_doi: 5
env_vars:
  required:
    NCBI_EMAIL: "Required by NCBI API policy -- use your institutional email"
    OPENALEX_API_KEY: "OpenAlex API key -- https://openalex.org/"
    LITERATURE_ENRICHMENT_EMAIL: "For CrossRef polite pool + Unpaywall TOS"
  optional:
    NCBI_API_KEY: "NCBI EUTILS for 10 req/s"
```

```yaml
# confounders.yaml
Survey data:
  - "Response bias"
  - "Social desirability"
  - "Recall bias"
  - "Selection into survey"
Administrative records:
  - "Coding variability"
  - "Missingness patterns"
  - "Temporal coverage gaps"
Geospatial data:
  - "Modifiable areal unit problem"
  - "Boundary misalignment"
  - "Temporal mismatch with health data"
Census data:
  - "Undercount bias"
  - "Category changes across waves"
  - "Ecological fallacy risk"
biological_confounders:
  - "age"
  - "sex"
  - "race/ethnicity"
  - "socioeconomic position"
data_reality_signals:
  species_column: null
  rules:
    - condition: "cross-sectional-only"
      claim: "cross-sectional design precludes causal inference about temporal ordering"
    - condition: "single-city"
      claim: "single-city findings may not generalize to other geographic contexts"
```

```yaml
# heuristics.yaml
file_extensions:
  ".sas7bdat": "Survey data"
  ".dta": "Survey data"
  ".shp": "Geospatial data"
  ".geojson": "Geospatial data"
tool_references:
  "SAS": "Survey data"
  "Stata": "Survey data"
  "ArcGIS": "Geospatial data"
  "GeoDa": "Geospatial data"
  "survey": "Survey data"
```

```yaml
# pii_patterns.yaml
column_patterns:
  - "\\b(respondent|participant|subject)[\\s_]?id\\b"
  - "\\bssn\\b"
  - "\\baddress\\b"
  - "\\bzip[\\s_]?code\\b"
  - "\\bdate[\\s_]?of[\\s_]?birth\\b"
```

---

## Example 3: Neuroscience (variant of bioinformatics)

```yaml
# profile.yaml
name: "neuroscience"
description: "Systems and cellular neuroscience with imaging and electrophysiology"
version: "1.0"
identity:
  purpose: "Co-scientist for neural circuit and connectivity discovery"
  domain: "Neuroscience"
  focus_areas:
    - "circuit mapping"
    - "calcium imaging analysis"
    - "behavioral neuroscience"
config_overrides:
  data_layers:
    - "Electrophysiology"
    - "Calcium imaging"
    - "Structural MRI"
    - "Behavioral assays"
    - "Histology"
  research:
    primary: "pubmed"
    fallback: "semantic_scholar"
    last_resort: "web-search"
  literature:
    sources: [pubmed, semantic_scholar, openalex]
    default: "all"
    enrichment:
      enabled: [crossref, unpaywall]
      timeout_per_doi: 5
env_vars:
  required:
    NCBI_EMAIL: "Required by NCBI API policy -- use your institutional email"
    LITERATURE_ENRICHMENT_EMAIL: "For CrossRef polite pool + Unpaywall TOS"
  optional:
    NCBI_API_KEY: "NCBI EUTILS for 10 req/s"
    S2_API_KEY: "Semantic Scholar higher rate limits"
```

```yaml
# confounders.yaml
Electrophysiology:
  - "Electrode drift"
  - "Spike sorting accuracy"
  - "Anesthesia effects"
Calcium imaging:
  - "Indicator kinetics"
  - "Motion artifacts"
  - "Neuropil contamination"
Structural MRI:
  - "Scanner field strength"
  - "Registration accuracy"
  - "Partial volume effects"
Behavioral assays:
  - "Experimenter effects"
  - "Circadian timing"
  - "Housing conditions"
Histology:
  - "Fixation artifacts"
  - "Antibody specificity"
  - "Section thickness variation"
biological_confounders:
  - "age"
  - "sex"
  - "strain"
  - "housing conditions"
data_reality_signals:
  species_column: "Species"
  rules:
    - condition: "mouse-only"
      claim: "mouse model findings require validation in primate or human tissue"
    - condition: "in-vitro-only"
      claim: "in vitro results may not recapitulate in vivo circuit dynamics"
```
