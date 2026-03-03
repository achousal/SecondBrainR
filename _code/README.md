# Co-Scientist EngramR

A multi-agent generate-debate-evolve system for hypothesis research, implemented as Claude Code skills + Obsidian vault. Inspired by Google DeepMind's "Towards an AI co-scientist" (arXiv:2502.18864).

## Quick start

```bash
cd _code
uv sync --all-extras
cp .env.example .env   # API keys optional -- see env vars table below
uv run pytest tests/ -v
```

For co-scientist architecture, vault structure, and the self-improving loop, see the [project README](../README.md).

## Library modules

All code in `src/engram_r/`:

### Core

| Module | Purpose |
|---|---|
| `obsidian_client.py` | REST API wrapper for Obsidian Local REST API (optional, not a runtime dependency) |
| `note_builder.py` | Pure functions for building all note types (claims, hypotheses, literature, etc.) |
| `schema_validator.py` | Validate note frontmatter against known schemas; sanitization + NFC normalization |
| `hook_utils.py` | Shared utilities for hook scripts (vault resolution, config loading) |
| `integrity.py` | Integrity manifest for self-modifiable files -- tamper detection and write protection |
| `domain_profile.py` | Domain profile discovery, loading, and application |
| `audit.py` | Structured JSONL audit log for daemon scheduler decision cycles |

### Co-Scientist

| Module | Purpose |
|---|---|
| `hypothesis_parser.py` | Parse/update hypothesis YAML frontmatter + body |
| `elo.py` | Elo rating math (pure, no I/O) |
| `experiment_resolver.py` | Resolve experiment outcomes into Elo adjustments and status transitions |

### Daemon + Decision Engine

| Module | Purpose |
|---|---|
| `daemon_config.py` | Config dataclass for Research Loop Daemon (includes MetabolicConfig) |
| `daemon_scheduler.py` | Priority cascade scheduler -- reads vault state, outputs JSON task |
| `schedule_runner.py` | Scheduled task runner for the daemon |
| `metabolic_indicators.py` | Vault health indicators (QPR, VDR, CMR, HCR, SWR) for daemon self-regulation |
| `decision_engine.py` | Unified decision engine for /next and daemon -- signal cascade + metabolic dashboard |
| `_daemon_backoff.py` | Skill-level failure tracking with exponential backoff for the daemon |

### Federation

| Module | Purpose |
|---|---|
| `federation_config.py` | Load and validate federation configuration from `ops/federation.yaml` |
| `vault_registry.py` | Multi-vault registry for federated deployments |
| `claim_exchange.py` | Export/import atomic claims across vaults (routes through `build_claim_note`) |
| `hypothesis_exchange.py` | Export/import hypotheses across vaults with filename sanitization |

### Literature + Data

| Module | Purpose |
|---|---|
| `pubmed.py` | NCBI EUTILS search |
| `arxiv.py` | arXiv Atom API search |
| `semantic_scholar.py` | Semantic Scholar Graph API search |
| `openalex.py` | OpenAlex REST API search |
| `crossref.py` | CrossRef DOI metadata enrichment (citation counts, PDF URLs) |
| `unpaywall.py` | Unpaywall DOI metadata enrichment (open-access PDF URLs) |
| `eda.py` | EDA computations + themed plots |
| `pii_filter.py` | PII/ID column detection and redaction |
| `literature_types.py` | Unified types for literature search (ArticleResult, LiteratureSource protocol) |
| `search_interface.py` | Unified multi-backend search with config-driven backend selection and deduplication |

### Plotting

| Module | Purpose |
|---|---|
| `plot_theme.py` | Matplotlib/seaborn theme, palettes, figure sizes |
| `plot_stats.py` | Statistical test selection, runners, formatters |
| `plot_builders.py` | Standard plot builders (violin, box, scatter, heatmap, volcano, forest, ROC, bar) |

### Slack Integration

| Module | Purpose |
|---|---|
| `slack_client.py` | Slack Web API client for notifications |
| `slack_bot.py` | Two-way vault-aware Slack bot |
| `slack_formatter.py` | Block Kit message formatters for EngramR events |
| `slack_notify.py` | High-level Slack notification dispatch |
| `slack_skill_router.py` | Queue-based skill routing from Slack with RBAC and intent extraction |

R code in `R/`: `theme_research.R`, `palettes.R`, `stats_helpers.R`, `plot_builders.R`, `plot_helpers.R`.

## Testing

```bash
uv run pytest tests/ -v --cov=engram_r    # full suite, >= 90% coverage
uv run ruff check src/                         # lint
uv run black --check src/                      # format
```

## Automation Hooks

5 hooks in `scripts/hooks/`, configured in `.claude/settings.json`:

| Hook | Event | Mode | Purpose |
|---|---|---|---|
| `session_orient.py` | SessionStart | sync | Print active goals, top hypotheses, latest meta-review |
| `validate_write.py` | PostToolUse (Write/Edit) | sync | Block writes that violate note schemas |
| `auto_commit.py` | PostToolUse (Write/Edit) | async | Auto-commit vault note changes |
| `pipeline_bridge.py` | PostToolUse (Write) | async | Suggest /reduce for new literature notes and hypotheses |
| `session_capture.py` | Stop | sync | Record session summary to `ops/sessions/` |

All hooks log errors to stderr (non-blocking). Disable any hook by setting its toggle to `false` in `ops/config.yaml`.

Smoke test commands:
```bash
# Orient
uv run python scripts/hooks/session_orient.py

# Validate (expects JSON on stdin)
echo '{"tool_name":"Write","tool_input":{"file_path":"...","content":"..."}}' | uv run python scripts/hooks/validate_write.py
```

## Hypothesis note format

YAML frontmatter tracks: id, status, elo, matches, wins, losses, generation, parents, children, review_scores, review_flags, linked_experiments, linked_literature.

Sections: Statement, Mechanism, Literature Grounding, Testable Predictions, Proposed Experiments, Assumptions, Limitations & Risks, Review History, Evolution History.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `OBSIDIAN_API_KEY` | No | Obsidian Local REST API bearer token (only for `obsidian_client.py`) |
| `OBSIDIAN_API_URL` | No | Default: `https://127.0.0.1:27124` (only for `obsidian_client.py`) |
| `NCBI_API_KEY` | No (optional, biomedical domains) | NCBI EUTILS for 10 req/s |
| `NCBI_EMAIL` | No (optional, biomedical domains) | Required by NCBI API policy |
| `S2_API_KEY` | No | Semantic Scholar API key. Without: shared anonymous pool. With: 1 req/s dedicated |
| `OPENALEX_API_KEY` | No | OpenAlex API key. Without: anonymous pool (lower rate limits). With: higher rate limits |
| `LITERATURE_ENRICHMENT_EMAIL` | No | Email for CrossRef polite pool + Unpaywall TOS (shared). No API key needed |
| `VAULT_PATH` | No | Vault root for daemon, decision engine, registry |
| `SLACK_BOT_TOKEN` | Slack | Slack bot OAuth token (xoxb-...) |
| `SLACK_APP_TOKEN` | Slack | Slack app-level token for socket mode (xapp-...) |
| `SLACK_BOT_CHANNEL` | Slack | Default channel for bot posts |
| `SLACK_DEFAULT_CHANNEL` | Slack | Fallback channel for slack_client |
| `SLACK_TEAM_ID` | Slack | Workspace team ID |
| `ANTHROPIC_API_KEY` | Slack | Claude API key for Slack bot responses |

## Domain profiles

Domain-specific configuration (search backends, vocabulary, plausibility criteria) lives in `profiles/`. The default bioinformatics profile enables PubMed, arXiv, Semantic Scholar, and OpenAlex; other domains can define their own search backends and terminology.

## Plot theme and reporting standards

Three-tier hierarchy:
- `_code/styles/STYLE_GUIDE.md`: visual identity (typography, frame, output standards, stats, reporting, colors, builders)
- `_code/styles/PLOT_DESIGN.md`: plot-type geometry (distribution, scatter, heatmap, annotation, figure sizes)
- `_code/profiles/{domain}/palettes.yaml`: domain-specific color palettes
- Key theme values: 14pt base, bold titles, grey90 strips, bottom legend, left+bottom spines only
- Semantic palettes: direction, significance, binary (universal, in `_code/styles/palettes.yaml`)
- Profile palettes: loaded from domain profile at runtime
- Output: PDF vector default, 300 DPI raster, sidecar p-values
- Stats: decision tree via `select_test()`, formatters via `format_pval()`
- Builders: `build_violin()`, `build_box()`, `build_scatter()`, etc.
- Python: `apply_research_theme()` + `save_figure()` + `plot_builders`
- R: `theme_research()` + `save_plot()` + `plot_builders.R`

### Analysis deliverables (per _code/styles/STYLE_GUIDE.md)

Every analysis script must produce: figures (PDF), p-value sidecars, stats report (txt), Table 1 (domain-specific, csv+png, if applicable -- typically for cohort-based studies), NA summary (csv, if any missingness). See _code/styles/STYLE_GUIDE.md "Analysis deliverables checklist" for the full table.

Key conventions:
- **n in plots**: always visible -- italic `n=N` at base of distribution plots, inline in scatter annotations
- **Test names**: always named in the stat annotation box (e.g., "Mann-Whitney p = 0.003")
- **Stats report**: timestamped txt with settings, sample counts, per-group results
- **Table 1** (domain-specific): CSV + rendered figure, mean(SD) / n(%), group n in column headers (cohort-based)
- **NA summary**: CSV with variable, group, n_missing, pct_missing, record_ids
