---
status: archived
---

# Review Prompt: Domain-Agnostic Refactoring

## What was done

EngramR was refactored from a bioinformatics-hardcoded system to a domain-agnostic one. Bioinformatics-specific content (lab palettes, omic data layers, PubMed-specific search, confounders, heuristics, PII patterns) was migrated to a structured **domain profile** at `_code/profiles/bioinformatics/`. The core system now uses placeholders, config-driven behavior, and profile loaders.

## Review checklist

For each section, verify the implementation matches the plan at `.claude/plans/lazy-stargazing-castle.md`.

---

### Phase 0: Profile Infrastructure

**New files to review:**
- `_code/profiles/README.md` -- docs for creating a domain profile
- `_code/profiles/bioinformatics/profile.yaml` -- metadata, config_overrides (data_layers, research backends), env_vars
- `_code/profiles/bioinformatics/identity.yaml` -- domain purpose and focus areas
- `_code/profiles/bioinformatics/confounders.yaml` -- data layer -> confounder mappings + biological_confounders + data_reality_signals
- `_code/profiles/bioinformatics/heuristics.yaml` -- file extension -> data layer + tool -> data layer inference rules
- `_code/profiles/bioinformatics/pii_patterns.yaml` -- additional PII column patterns (MRN, patient name, sample_id)
- `_code/profiles/bioinformatics/palettes.yaml` -- lab palettes (elahi, chipuk, kuang) + semantic palettes (sex, dx) moved from core
- `_code/profiles/bioinformatics/styles/PLOT_DESIGN.md` -- moved from `_code/styles/`
- `_code/profiles/bioinformatics/styles/chipuk.md` -- moved from `docs/styles/`
- `_code/profiles/bioinformatics/styles/elahi.md` -- moved from `docs/styles/`
- `_code/src/engram_r/domain_profile.py` -- DomainProfile dataclass + discover_profiles, load_profile, get_active_profile, merge_profile_palettes, apply_profile_config
- `_code/tests/test_domain_profile.py` -- 17 tests

**Verify:**
1. `profile.yaml` has the right config_overrides (8 data_layers, research backends with primary/fallback/last_resort)
2. `confounders.yaml` matches the original hardcoded confounder table from init SKILL.md (Transcriptomics, Proteomics, Genomics, Epigenomics, Metabolomics, Metagenomics, Clinical/EHR, Flow/CyTOF) plus biological_confounders and data_reality_signals
3. `heuristics.yaml` has file extension mappings (.bam, .vcf, .fastq, .bed, .bigwig) and tool references (DESeq2, edgeR, limma, Seurat, Scanpy, MaxQuant, GATK, bismark, QIIME, metaphlan)
4. `domain_profile.py` functions work: discover_profiles finds dirs with profile.yaml; load_profile loads all YAML files; get_active_profile reads config.yaml domain.name; merge_profile_palettes merges into palettes.yaml; apply_profile_config merges config_overrides
5. `ops/config.yaml` has new `domain: { name: "", profile: "" }` section
6. `ops/config-reference.yaml` documents the domain section and profile system

---

### Phase 1: Search Interface

**New files to review:**
- `_code/src/engram_r/search_interface.py` -- SearchResult dataclass with from_pubmed(), from_arxiv(), resolve_search_backends()
- `_code/tests/test_search_interface.py` -- 41 tests

**Modified:**
- `_code/src/engram_r/pubmed.py` -- added search_and_fetch_unified() returning list[SearchResult]
- `_code/src/engram_r/arxiv.py` -- added search_arxiv_unified() returning list[SearchResult]
- `ops/config-reference.yaml` -- added arxiv as valid research backend value

**Verify:**
1. SearchResult dataclass has fields: source_id, title, authors, abstract, year, doi, source_type, url, journal, categories, pdf_url, raw_metadata
2. from_pubmed() correctly converts PubMed article dicts to SearchResult
3. from_arxiv() correctly converts arXiv entry dicts to SearchResult
4. resolve_search_backends() reads ops/config.yaml research section and returns ordered list of backend names
5. Existing pubmed/arxiv APIs remain intact (wrappers added, not replaced)

---

### Phase 2: Bio Content Migration

**Core palette changes:**
- `_code/styles/palettes.yaml` -- removed `labs:` section and `sex:`/`dx:` from semantic; only binary/direction/sig/diverging/sequential remain
- `_code/src/engram_r/plot_theme.py` -- removed _FALLBACK_SEX, _FALLBACK_DX, _FALLBACK_LABS, SEX_COLORS, DX_COLORS exports; LAB_PALETTES defaults to {}; SEMANTIC_PALETTES only has binary/direction/sig; get_lab_palette() error message mentions domain profiles
- `_code/R/palettes.R` -- removed SEX_COLORS, DX_COLORS, .fallback_labs, scale_color_sex(), scale_fill_sex(), scale_color_dx(), scale_fill_dx(); LAB_PALETTES defaults to list()
- `_code/R/plot_helpers.R` -- removed backward-compat SEX_COLORS/DX_COLORS shims
- `_code/src/engram_r/__init__.py` -- removed SEX_COLORS, DX_COLORS from imports and __all__
- `_code/styles/STYLE_GUIDE.md` -- removed lab name table, sex/dx palette refs; updated examples to generic lab_palette("your-lab")
- `_code/src/engram_r/plot_builders.py` -- build_volcano docstring: "differential expression" -> "effect size vs significance"

**Config/template changes:**
- `ops/config.yaml` -- data_layers set to empty list with comment "Populated from domain profile"
- `_code/src/engram_r/note_builder.py` -- scheduler default "" instead of "LSF"; docstring examples genericized
- `_code/src/engram_r/schedule_runner.py` -- hypothesis ID regex: generic `r"(H-?\w+-?\d+\w*)"` instead of `r"(H-?(?:AD|LPS|COMP)-?\d+\w*)"`
- `_code/src/engram_r/slack_bot.py` -- "research knowledge vault" instead of "bioinformatics knowledge vault"
- `_code/src/engram_r/pii_filter.py` -- docstring: "research datasets" instead of "biomedical datasets"
- `_code/templates/indexes/notes-index.md` -- "your research knowledge system" instead of "bioinformatics..."
- `_code/templates/institution.md` -- `domain_resources: []` instead of `biobanks: []` + `cohorts: []`; heading "Domain Resources"
- `_code/templates/data-inventory.md` -- "Context" column instead of "Species"
- `_code/templates/project.md` -- `scheduler: ""` instead of `scheduler: LSF`

**Identity/config changes:**
- `self/identity.md` -- Purpose uses {{DOMAIN}} and {{FOCUS_AREAS}} placeholders
- `CLAUDE.md` line 3 -- "research knowledge system" instead of "bioinformatics research knowledge system"
- `_code/scripts/init_vault.py` -- NCBI keys commented out with "optional biomedical domain" label
- `_code/scripts/verify_claim.py` -- "Your Name" instead of "Andres Chousal"
- `_code/scripts/batch_seed.py` -- deleted (user-specific AD paths)

**Verify:**
1. `palettes.yaml` has NO labs, sex, or dx sections; only binary/direction/sig/diverging/sequential
2. `plot_theme.py` has NO _FALLBACK_* or SEX/DX constants; LAB_PALETTES defaults to empty dict
3. `palettes.R` has NO SEX_COLORS, DX_COLORS, scale_*_sex(), scale_*_dx() or .fallback_labs
4. `__init__.py` has NO SEX_COLORS/DX_COLORS in imports or __all__
5. `schedule_runner.py` regex is generic -- matches any H-{prefix}-{number} pattern
6. Templates use generic field names (domain_resources, Context, scheduler: "")
7. `self/identity.md` has {{DOMAIN}} and {{FOCUS_AREAS}} placeholders (literal text, not resolved)

---

### Phase 3: Skill Generalization

**Modified SKILL.md files:**
- `.claude/skills/literature/SKILL.md` -- Code section added search_interface.py; workflow adds config-reading step
- `.claude/skills/generate/SKILL.md` -- search_interface.py ref; config-driven search; generic source identifiers
- `.claude/skills/review/SKILL.md` -- search_interface.py ref; "cite source identifiers" instead of "cite PMIDs"
- `.claude/skills/evolve/SKILL.md` -- search_interface.py ref
- `.claude/skills/init/SKILL.md` -- Profile-driven confounders replacing hardcoded table; profile-driven data_reality_signals
- `.claude/skills/onboard/SKILL.md` -- Profile-driven heuristics; profile application step; generic examples
- `.claude/skills/eda/SKILL.md` -- PII patterns note about domain profiles adding patterns

**Verify:**
1. Literature skill step 1 reads ops/config.yaml research section for available backends
2. Generate/review/evolve skills reference search_interface.py in their Code section
3. Init skill Phase 3b references `_code/profiles/{domain.name}/confounders.yaml` instead of hardcoded omic table
4. Init skill Phase 3c references profile `data_reality_signals` instead of hardcoded species logic
5. Onboard skill has early step checking `_code/profiles/` for available profiles
6. Onboard skill data layer inference reads `_code/profiles/{domain}/heuristics.yaml`
7. Onboard skill has "Post-Onboarding Profile Application" section for merging profile config/palettes

---

### Phase 4: Documentation

**Modified:**
- `docs/manual/manual.md` -- "research knowledge system" instead of "bioinformatics..."
- `docs/manual/skills.md` -- "domain lens" instead of "bioinformatics lens"; PubMed/arXiv refs get "(when configured via domain profile)"
- `docs/manual/workflows.md` -- "domain lens" instead of "bioinformatics lens"
- `docs/manual/Co-Scientist Guide.md` -- "configured search backends" instead of "PubMed/arXiv"; "domain plausibility" instead of "biological plausibility"
- `docs/EngramR.md` -- added note: "This scenario uses a biomedical lab as an example"
- `README.md` -- NCBI keys moved to "Optional: Domain-specific search" subsection; added "Domain profiles" section; /literature description updated
- `_code/README.md` -- NCBI keys marked optional; added profiles section
- `ops/derivation.md` -- historical note blockquote about bioinformatics being original use case
- `ops/methodology/derivation-rationale.md` -- same historical note
- `ops/methodology/normalize-unicode-in-queue-ids-and-filenames.md` -- "search backends" instead of "PubMed/arXiv"

**Verify:**
1. No "bioinformatics" or "PubMed/arXiv" as required/hardcoded in docs (except derivation historical notes)
2. README has domain profiles section explaining the system
3. Derivation docs have clear historical context notes (not rewritten, just annotated)

---

### Phase 5: Test Data Generalization

**Modified test files (17+):**
- `test_plot_theme.py` -- full rewrite removing sex/dx/lab-specific tests; profile-loading tests
- `test_note_builder.py` -- generic lab names, scheduler="", generic terms
- `test_schema_validator.py` -- generic markers/titles
- `test_hypothesis_parser.py` -- generic tags
- `test_hypothesis_exchange.py` -- generic mechanism terms
- `test_claim_exchange.py` -- "Test Verifier" instead of personal name
- `test_decision_engine.py` -- generic goal/topic slugs
- `test_daemon_scheduler.py` -- generic goal/topic slugs
- `test_slack_formatter.py` -- generic goal names
- `test_slack_bot.py` -- "research" instead of "bioinformatics"
- `test_slack_notify.py` -- generic goal names
- `test_daemon_config.py` -- generic settings
- `test_backfill_provenance.py` -- generic wiki links
- `test_eda.py` -- generic column names
- `test_pubmed.py` -- generic markers
- `test_pii_filter.py` -- generic data
- `test_search_interface.py` -- generic markers
- `test_semantic_scholar.py` -- generic markers
- `test_openalex.py` -- generic titles
- `test_validate_write.py` -- generic descriptions
- `test_init_vault.py` -- generic lab names
- `_code/R/tests/test-palettes.R` -- removed sex/dx/lab-specific tests; generic behavior tests
- `fixtures/sample_dataset.csv` -- generic columns
- `fixtures/sample_pubmed_response.xml` -- generic research article

**Pattern replacements used:**
| Original | Replacement |
|----------|-------------|
| GFAP, NfL, amyloid | Metric_A, Metric_B, Score |
| elahi, chipuk, kuang | example-lab, test-lab-b, test-lab-c |
| Alzheimer, AD, neuroinflammation | test condition, TC, test mechanism |
| Minerva, /sc/arion/, LSF | TestCluster, /tmp/hpc/, "" |
| celiac-risks | test-project |
| P+/P- (as diagnosis) | Active/Control |
| goal-ad-biomarkers | goal-test-analysis |
| IL-6, ceramide, tau, CSF, BBB | generic mechanism terms |
| Andres Chousal | Test Verifier |
| Fanny Elahi | Test PI |
| biomarker(s) | marker(s)/metric(s) |
| dynamic-biomarker-networks | dynamic-metric-networks |

**Verify:**
1. Run `cd _code && uv run pytest tests/ -v --cov=engram_r` -- expect 1233+ passed, 1 pre-existing failure in test_validate_write (schema_validator.py has separate uncommitted changes), 3 seaborn warnings
2. Run `uv run ruff check src/` -- expect clean
3. Run `uv run black --check src/` -- expect clean

---

### Phase 6: Cleanup Validation

Run these sweeps and expect 0 results (or only acceptable contextual references):

```bash
# Domain terms outside profiles/ and derivation docs
grep -rn "bioinformatics\|biomarker\|multi-omics\|Alzheimer\|elahi\|chipuk\|kuang\|Minerva\|/sc/arion\|GFAP\|NfL\|celiac" \
  _code/src/ _code/R/ _code/styles/ _code/templates/ _code/tests/ _code/scripts/ \
  ops/config.yaml self/ .claude/skills/ CLAUDE.md README.md docs/manual/ \
  | grep -v "_code/profiles/"

# Expected: ~6 acceptable contextual references:
# - domain_profile.py docstring example ("bioinformatics")
# - palettes.yaml comment explaining profiles ("bioinformatics")
# - init_vault.py comment ("bioinformatics profile")
# - config.yaml comment ("bioinformatics")
# - onboard SKILL.md HPC cluster detection ("Minerva" as known cluster name)

# Removed exports (should return 0)
grep -rn "SEX_COLORS\|DX_COLORS\|_FALLBACK_LABS\|_FALLBACK_SEX\|_FALLBACK_DX" _code/src/ _code/R/

# Hardcoded hypothesis prefixes (should return 0)
grep -rn "H-AD\|H-LPS\|H-COMP" _code/src/
```

---

### Profile Loading Integration Test

```bash
cd _code
python -c "
from engram_r.domain_profile import discover_profiles, load_profile
profiles = discover_profiles()
print(f'Available profiles: {profiles}')
p = load_profile('bioinformatics')
print(f'Profile: {p.name}, {p.description}')
print(f'Data layers: {len(p.config_overrides.get(\"data_layers\", []))} layers')
print(f'Confounders: {list(p.confounders.keys())[:3]}...')
print(f'Heuristics file_ext: {list(p.heuristics.get(\"file_extensions\", {}).keys())[:3]}...')
print(f'PII patterns: {len(p.pii_patterns)} patterns')
print(f'Lab palettes: {list(p.palettes.get(\"labs\", {}).keys())}')
"
```

---

### Key Invariant

After this refactoring, a bioinformatics user running `/onboard` with `domain: bioinformatics` in config.yaml should get the EXACT same experience as before -- lab palettes, omic confounders, PubMed search, data layers, PII patterns -- but sourced from `_code/profiles/bioinformatics/` instead of hardcoded locations. A non-bio user gets a clean slate with no domain assumptions.

### Pre-existing Issue (not from this refactoring)

`_code/src/engram_r/schema_validator.py` has uncommitted changes (HTML stripping + description requirement enforcement) that cause 1 test failure in `test_validate_write.py::TestProvenanceEnforcement::test_pipeline_compliance_false_skips_check`. This is unrelated to the domain-agnostic refactoring.
