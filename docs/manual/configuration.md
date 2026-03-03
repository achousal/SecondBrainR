---
description: "Configuration reference -- ops/config.yaml structure, dimensions, processing modes, architect command"
type: manual
created: 2026-02-21
---
l# Configuration

This page documents the system configuration: ops/config.yaml structure, dimension semantics, processing modes, and how to use /architect for structural changes.

---

## Configuration Files

| File | Purpose | Editable |
|------|---------|----------|
| ops/config.yaml | Live configuration -- runtime behavior | Yes, directly |
| ops/derivation.md | Why each dimension was chosen -- human-readable rationale | Reference only |
| ops/derivation-manifest.md | Machine-readable config snapshot -- read by skills at runtime | Via /reseed only |
| ops/daemon-config.yaml | Research loop daemon settings -- tier priorities, scheduling, autonomy level | Yes, directly |
| ops/methodology/ | Vault self-knowledge -- learned behaviors, rationale notes | Via /rethink, /architect |

---

## ops/config.yaml Structure

### Dimensions

```yaml
dimensions:
  granularity: atomic       # atomic | chunked
  organization: flat        # flat | hierarchical
  linking: explicit+implicit # explicit | explicit+implicit
  processing: heavy         # light | moderate | heavy
  navigation: 3-tier        # flat | 2-tier | 3-tier
  maintenance: condition-based # manual | scheduled | condition-based
  schema: moderate          # minimal | moderate | strict
  automation: full          # minimal | partial | full
```

**granularity** -- How large each note is. `atomic` means one claim per file. `chunked` means multiple related claims per file.

**organization** -- How files are arranged. `flat` means all claims in notes/ with wiki-link graph for navigation. `hierarchical` means nested subdirectories by topic.

**linking** -- Connection-finding mode. `explicit` means only manually created links. `explicit+implicit` means the system also suggests implicit connections based on keyword overlap and topic map proximity.

**processing** -- Pipeline depth. `light` skips reweave. `moderate` includes reweave on directly related claims. `heavy` includes broad reweave and maximum quality gates.

**navigation** -- Topic map depth. `flat` means no topic maps. `2-tier` means hub plus topic maps. `3-tier` means hub, domain topic maps, and topic-level maps.

**maintenance** -- When maintenance runs. `manual` means only when explicitly invoked. `scheduled` means on a fixed cadence. `condition-based` means triggers fire when thresholds are met.

**schema** -- How strict YAML validation is. `minimal` checks only description. `moderate` checks description, type enums, and field constraints. `strict` adds cross-field validation and completeness checks.

**automation** -- How much the system does without being asked. `minimal` means no hooks, manual everything. `partial` means orient and capture hooks but no auto-commit. `full` means all hooks active.

### Features

```yaml
features:
  semantic-search: false    # requires qmd installation
  processing-pipeline: true
```

**semantic-search** -- When `true`, skills use embedding-based search in addition to ripgrep. Requires qmd to be installed. Currently deferred; ripgrep and topic maps compensate.

**processing-pipeline** -- When `true`, the full capture-reduce-reflect-reweave-verify pipeline is active. When `false`, direct writes to notes/ are permitted.

### Processing Configuration

```yaml
processing:
  depth: standard           # deep | standard | quick
  chaining: suggested       # manual | suggested | automatic
  extraction:
    selectivity: moderate   # strict | moderate | permissive
    categories: auto        # auto | custom list
  verification:
    description_test: true
    schema_check: true
    link_check: true
  reweave:
    scope: related          # related | broad | full
    frequency: after_create # after_create | periodic | manual
```

**depth** -- Controls attention per claim during processing. `deep` uses fresh context per phase. `standard` balances quality and throughput. `quick` compresses phases for high-volume catch-up.

**chaining** -- Controls how pipeline phases connect. `manual` requires explicit invocation of each phase. `suggested` outputs next steps and adds to queue. `automatic` chains phases without pause.

**extraction.selectivity** -- Controls how many claims are extracted per source. `strict` extracts only high-confidence, clearly novel claims. `moderate` includes supporting evidence and methodological comparisons. `permissive` extracts everything, including speculative connections.

**extraction.categories** -- The list of extraction categories used by /reduce. Defined in ops/config.yaml under `processing.extraction.categories`.

**verification** -- Toggle individual verification checks. All default to `true`.

**reweave.scope** -- How far backward the reweave pass reaches. `related` touches only directly connected claims. `broad` includes two-hop neighbors. `full` touches all claims (expensive).

**reweave.frequency** -- When reweave triggers. `after_create` fires after each reduce. `periodic` accumulates and runs in batches. `manual` runs only when explicitly invoked.

### Provenance

```yaml
provenance: full            # full | minimal | off
```

**full** -- Record source_type, research_prompt, generated timestamp, and link chain in every claim.
**minimal** -- Record source link only.
**off** -- No provenance tracking.

### Research Configuration

```yaml
research:
  primary: web-search
  fallback: web-search
  last_resort: web-search
  default_depth: moderate   # light | moderate | deep
```

Configures the research stack for /learn. Primary, fallback, and last_resort define the tool cascade. Options: web-search, pubmed, arxiv, semantic_scholar, openalex, exa.

### Literature Enrichment

```yaml
literature:
  enrichment:
    enabled: []               # crossref, unpaywall, or both
    timeout_per_doi: 5        # seconds per API call
```

When enabled, search results are post-processed with DOI lookups after deduplication but before sorting. CrossRef fills missing citation counts and PDF URLs. Unpaywall fills missing open-access PDF URLs. Results are never overwritten -- enrichment only fills empty fields. Requires `LITERATURE_ENRICHMENT_EMAIL` env var (no API key needed).

### Co-Scientist Toggles

```yaml
vault_root: /path/to/vault
git_auto_commit: true
schema_validation: true
session_capture: true
```

These toggles control co-scientist hooks. They are also respected by arscontexta hooks.

### Personality (Optional)

```yaml
personality:
  enabled: false
```

When enabled, the system adopts personality dimensions defined in ops/derivation-manifest.md (warmth, opinionatedness, formality, emotional awareness). Default: disabled (neutral, formal, clinical, task-focused).

---

## Derivation Manifest

ops/derivation-manifest.md is the machine-readable configuration snapshot. It contains:

- **engine_version** -- arscontexta version used for derivation.
- **dimensions** -- all dimension positions (mirrors config.yaml).
- **active_blocks** -- which feature blocks are enabled.
- **platform_hints** -- allowed tools, context mode, semantic search availability.
- **personality** -- warmth, opinionatedness, formality, emotional_awareness settings.

Skills read the derivation manifest at invocation for platform hints, dimensions, and personality settings.

---

## Changing Configuration

### Direct Edits

Edit ops/config.yaml for operational changes that do not require re-derivation:
- Processing depth, chaining, selectivity
- Verification toggles
- Reweave scope and frequency
- Provenance level
- Research stack
- Co-scientist toggles

### Structural Changes via /architect

For changes to dimension positions or feature blocks:

```
/architect "I want to switch from atomic to chunked granularity"
/architect "Should I enable semantic search?"
/architect "The 3-tier navigation is too deep for my current vault size"
```

/architect:
1. Reads the current derivation (ops/derivation.md) and configuration.
2. Evaluates the requested change against coherence constraints.
3. Reports hard constraint violations (blocking) and soft constraint warnings.
4. If the change is valid, updates ops/config.yaml and ops/methodology/.
5. Documents the rationale for the change.

See [Meta-Skills](meta-skills.md) for detailed /architect usage.

### Re-Derivation via /reseed

For fundamental changes that require re-deriving the entire configuration:

```
/reseed
```

Re-runs the derivation process with updated dimension positions. Updates CLAUDE.md, ops/config.yaml, and ops/derivation-manifest.md. Preserves existing content.

---

## Coherence Constraints

Dimension positions are not independent. Some combinations create incoherence:

### Hard Constraints (Blocking)

| Combination | Issue |
|-------------|-------|
| atomic + 3-tier nav + high volume | 3-tier must provide sufficient depth for atomic claims |
| full automation + minimal platform | Platform must support hooks and skills |
| heavy processing + no pipeline | Pipeline must be enabled for heavy processing |

### Soft Constraints (Warnings)

| Combination | Warning |
|-------------|---------|
| explicit+implicit linking + no semantic search | Implicit linking falls back to keyword overlap only |
| atomic + light processing | Atomic claims benefit from heavy processing |
| strict schema + minimal automation | Schema validation requires hooks to enforce |

/architect checks both hard and soft constraints before applying changes.

---

## Hooks Configuration

Hooks are configured in .claude/settings.json. The current vault has two hook layers:

### Python Hooks (Co-Scientist)
- `session_orient.py` -- SessionStart: prints research goals, top hypotheses, meta-review summary
- `validate_write.py` -- PostToolUse (Write/Edit): blocks schema violations in co-scientist directories
- `auto_commit.py` -- PostToolUse (Write/Edit): git commits co-scientist content changes
- `session_capture.py` -- Stop: records session summary to ops/sessions/

### Bash Hooks (Arscontexta)
- `session-orient.sh` -- SessionStart: prints vault state, goals, maintenance signals
- `validate-note.sh` -- PostToolUse (Write/Edit): checks notes/ files for required description field
- `auto-commit.sh` -- PostToolUse (Write/Edit): git commits vault content changes
- `session-capture.sh` -- Stop: records session metadata to ops/sessions/

Both layers run additively. Disable arscontexta hooks by removing the `.arscontexta` marker file from the vault root.

---

## Domain Profiles

EngramR is domain-agnostic. Domain-specific behavior is configured via profile
directories in `_code/profiles/`. A profile bundles:

| File | What it configures |
| --- | --- |
| `profile.yaml` | Search backend priority chain, recognized data layers, required env vars |
| `identity.yaml` | Agent identity seed -- purpose statement, domain, focus areas |
| `confounders.yaml` | Auto-drafted confounder claims per data layer |
| `heuristics.yaml` | File extension and tool-name to data-layer inference rules |
| `pii_patterns.yaml` | Domain-specific PII column patterns added to the base filter |
| `palettes.yaml` | Lab and semantic color palettes |
| `styles/PLOT_DESIGN.md` | Domain-specific plot geometry overrides |
| `styles/{lab}.md` | Per-lab accent colors and palette policies |

The `bioinformatics` profile is the bundled example profile. It enables
PubMed + arXiv + Semantic Scholar + OpenAlex search, recognizes 8 data
modalities, and ships with confounder templates for each. Other domains can
define entirely different search backends, data layers, and confounders.

To adapt EngramR to a different research domain, copy the `bioinformatics/`
directory, edit `profile.yaml`, and set `domain.name` in `ops/config.yaml`.

---

## See Also

- [Meta-Skills](meta-skills.md) -- detailed guide to /architect and /ask
- [Workflows](workflows.md) -- how configuration affects processing behavior
- [Troubleshooting](troubleshooting.md) -- diagnosing configuration-related issues
- [Integrations](integrations.md) -- domain profiles in the context of external services
