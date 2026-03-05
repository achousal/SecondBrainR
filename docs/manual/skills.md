---
description: "Complete command reference for all vault skills"
type: manual
created: 2026-02-21
---

# Skills Reference

All commands available in this vault, organized by layer and category. All skills use bare slash commands (e.g., `/reduce`, `/research`).

---

## Co-Scientist Skills

### Tier 1: Supervisor

#### /research
Orchestrate the co-scientist generate-debate-evolve loop.

| Property | Value |
|----------|-------|
| Invoked by | User (entry point) |
| Invokes | /generate, /review, /tournament, /evolve, /landscape, /meta-review, /literature |
| Reads | _research/goals/, _research/hypotheses/_index.md, _research/meta-reviews/ |
| Writes | _research/goals/ |

Sets research goals and presents a menu of co-scientist operations. Before invoking any sub-skill, checks _research/meta-reviews/ for the latest feedback and injects it as context. The user drives the loop -- the supervisor never auto-advances.

---

### Tier 2: Co-Scientist Agents

#### /generate
Produce novel, literature-grounded hypotheses for a research goal.

| Property | Value |
|----------|-------|
| Invoked by | /research |
| Reads | _research/goals/, _research/meta-reviews/, _research/landscape/, _research/hypotheses/ |
| Writes | _research/hypotheses/, _research/hypotheses/_index.md |

**4 generation modes:**
1. **Literature synthesis** -- search PubMed/arXiv (when configured via domain profile), identify gaps, propose hypotheses with citations.
2. **Self-play debate** -- simulate expert perspectives (molecular biologist, clinician, statistician), extract novel ideas.
3. **Assumption-based reasoning** -- take an existing hypothesis, enumerate assumptions, generate alternatives by relaxing each.
4. **Research expansion** -- use meta-review feedback and landscape gaps to target under-explored regions.

Output: hypothesis notes with Elo=1200, generation=1, status=proposed.

---

#### /review
Critically evaluate hypotheses through multiple review lenses.

| Property | Value |
|----------|-------|
| Invoked by | /research |
| Reads | _research/hypotheses/, _research/meta-reviews/ |
| Writes | _research/hypotheses/ (frontmatter: review_scores, review_flags, Review History) |

**6 review modes:**
1. **Quick screen** -- rapid assessment, scores on 1-10 scale (novelty, correctness, testability, impact, overall).
2. **Literature review** -- search for the claim in PubMed/arXiv (when configured via domain profile), flag if already published or contradicted.
3. **Deep verification** -- decompose into constituent assumptions, search evidence for each.
4. **Observation review** -- assess explanatory power against user-provided experimental data.
5. **Simulation review** -- walk through proposed mechanism step-by-step, identify failure modes.
6. **Tournament-informed review** -- apply learned critique patterns from previous meta-reviews.

Scoring: weighted mean -- correctness 30%, testability 25%, novelty 25%, impact 20%.

---

#### /tournament
Rank hypotheses through pairwise scientific debate with Elo ratings.

| Property | Value |
|----------|-------|
| Invoked by | /research |
| Reads | _research/hypotheses/, _research/goals/ |
| Writes | _research/tournaments/, _research/hypotheses/ (elo, matches, wins, losses), _research/hypotheses/_index.md |

Generates matchups prioritizing under-matched and similar-Elo pairs. Conducts structured debate across four dimensions (novelty, correctness, testability, impact). Tiered comparison: top 25% by Elo receive multi-turn deep debate; bottom 75% receive single-turn comparison.

Elo system: starting rating 1200, K-factor 32, rating sum preserved.

---

#### /evolve
Refine and evolve top-ranked hypotheses into stronger versions.

| Property | Value |
|----------|-------|
| Invoked by | /research |
| Reads | _research/hypotheses/, _research/meta-reviews/ |
| Writes | _research/hypotheses/ (new generation notes), _research/hypotheses/_index.md |

**5 evolution modes:**
1. **Grounding enhancement** -- strengthen evidence base, fix flagged assumptions.
2. **Combination** -- merge 2-3 top hypotheses, resolve contradictions.
3. **Simplification** -- strip non-essential assumptions, focus on testable core.
4. **Research extension** -- extend to adjacent domains, explore broader implications.
5. **Divergent exploration** -- generate contrarian alternatives, target empty landscape regions.

Output: new hypothesis with generation=N+1, parents linked bidirectionally, Elo=1200.

---

#### /landscape
Map the hypothesis space to identify clusters, gaps, and redundancies.

| Property | Value |
|----------|-------|
| Invoked by | /research |
| Reads | _research/hypotheses/ |
| Writes | _research/landscape/, _research/landscape.md |

Clusters hypotheses by shared tags, common assumptions, similar mechanisms, overlapping citations, and Elo tier. Outputs: cluster descriptions, identified gaps, redundancy flags, and suggested directions for /generate and /evolve.

---

#### /meta-review
Synthesize patterns from tournament debates and reviews into actionable feedback.

| Property | Value |
|----------|-------|
| Invoked by | /research |
| Reads | _research/tournaments/, _research/hypotheses/ (review histories) |
| Writes | _research/meta-reviews/ |

Analyzes: recurring weaknesses, key literature, invalid assumptions, winner patterns. Produces concrete recommendations for /generate (what types of hypotheses are missing) and /evolve (which weaknesses to address first). This output feeds back into subsequent cycles -- the self-improving loop mechanism.

---

#### /literature
Search configured search backends, create structured literature notes.

| Property | Value |
|----------|-------|
| Invoked by | /research, user (standalone) |
| Reads | Configured search backends (see `ops/config.yaml` `literature:` section) |
| Writes | _research/literature/, _research/literature/_index.md |

Searches configured backends (PubMed, arXiv, Semantic Scholar, OpenAlex -- controlled by `literature.sources` in config). Presents results as a table. Saves selected papers as structured notes with frontmatter (type, title, doi, authors, year, journal, status) and sections (Abstract, Key Points, Methods Notes, Relevance, Citations).

---

### Tier 3: Supporting Tools

#### /experiment
Log experiments with parameters, results, and artifacts linked to hypotheses.

| Property | Value |
|----------|-------|
| Invoked by | User (standalone) |
| Reads | _research/hypotheses/ (linked hypothesis) |
| Writes | _research/experiments/, _research/experiments/_index.md, _research/hypotheses/ (linked_experiments) |

Records run metadata: parameters, random seed, code version, environment info, timestamp, computational resources. Links experiments bidirectionally to hypotheses.

---

#### /eda
Run exploratory data analysis with PII auto-redaction and themed plots.

| Property | Value |
|----------|-------|
| Invoked by | User (standalone) |
| Reads | User-provided dataset |
| Writes | eda-reports/, eda-reports/_index.md |

Auto-redacts PII columns (SubjectID, PersonName, SSN, Email, etc., plus profile-specific patterns) before analysis. Computes summary statistics, correlations, distribution properties. Generates themed plots (histograms, correlation heatmap, missing data chart). Saves report to vault.

---

#### /plot
Generate publication-quality figures using the canonical research theme.

| Property | Value |
|----------|-------|
| Invoked by | User (standalone) |
| Reads | User-provided data, `_code/styles/STYLE_GUIDE.md`, `_code/styles/PLOT_DESIGN.md`, profile `styles/PLOT_DESIGN.md` |
| Writes | User-specified output directory (PDF figures) |

Applies the research theme (14pt base, bold titles, grey90 strips, bottom legend, left+bottom spines). Uses semantic color palettes (direction, significance, binary, plus profile-specific palettes). Outputs PDF vector by default, 300 DPI raster.

---

#### /project
Register, update, and query research projects in the vault.

| Property | Value |
|----------|-------|
| Invoked by | User (standalone) |
| Reads | projects/, projects/_index.md, filesystem |
| Writes | projects/, projects/_index.md |

Registers projects with infrastructure detection (CLAUDE.md, git, tests). Creates symlinks under _dev/ for Obsidian browsability. Links projects bidirectionally to research goals.

---

## Knowledge Processing Skills

### Processing Pipeline

#### /reduce
Extract claims from source material in inbox/.

| Property | Value |
|----------|-------|
| Input | Path to an inbox/ file |
| Output | One or more claim notes in notes/ |
| Queue | Creates reflect tasks for each extracted claim |

Reads source material through the domain lens. Extracts claims across 6 categories: claims (testable assertions), evidence (data points), methodology comparisons, contradictions, open questions, design patterns. Each extracted claim must pass the quality bar: title works as prose, description adds beyond title, specific enough to disagree with. After extraction, abstract-only sources display a post-extraction advisory with the upgrade path to full-text processing.

---

#### /reflect
Find connections between claims and update topic maps.

| Property | Value |
|----------|-------|
| Input | Claim title or path (or operates on recent claims from queue) |
| Output | Updated claims with new wiki links, updated topic maps |
| Queue | Creates reweave tasks for connected claims |

Three connection-finding operations:
1. Forward connections -- what existing claims relate to this one?
2. Backward connections -- what older claims need updating?
3. Topic map membership -- ensures the claim appears in at least one topic map.

---

#### /reweave
Revisit old claims with new context.

| Property | Value |
|----------|-------|
| Input | Claim title or path |
| Output | Updated claim with revised content, new connections |
| Queue | Creates verify tasks |

Asks: "If I wrote this claim today, what would be different?" Reconsidering a claim based on current knowledge: add connections, rewrite content, sharpen the claim, split bundled ideas, challenge with new evidence. Scope configured in ops/config.yaml (related, broad, or full).

---

#### /verify
Quality-check claims against schema, description standards, and link health.

| Property | Value |
|----------|-------|
| Input | Claim title or path |
| Output | Verification report, fixes applied |

Three checks:
1. **Description quality (cold-read test)** -- read only title and description, predict content, then verify.
2. **Schema compliance** -- all required fields present, enum values valid.
3. **Link health** -- no broken wiki links, no orphaned claims.

---

#### /validate
Batch schema validation across all claims.

| Property | Value |
|----------|-------|
| Input | None (operates on all notes/) |
| Output | Validation report with violations listed |

Checks every claim in notes/ against the _templates/claim-note.md schema. Reports missing required fields, invalid enum values, empty descriptions, and constraint violations.

---

#### /seed
Queue a source file for processing with duplicate detection and silent auto-enrichment. Use `--all` to queue all inbox items at once.

| Property | Value |
|----------|-------|
| Input | Path to source file, or `--all` to queue entire inbox |
| Output | Extract task in ops/queue/, source archived |

Checks for duplicates, creates an archive folder, moves the source from inbox/ to its permanent archive location, creates an extract task file, and updates the queue. DOI stubs are silently enriched via `enrich_single_doi()` during Step 5b -- no manual enrichment step needed. The next step is /ralph to batch-process queued tasks (with fresh context per phase), or /reduce on the specific task file for single-item processing. Does not create claims directly -- all claim creation goes through /reduce.

---

#### /enrich
Integrate new evidence into existing claims with proper citation and provenance upgrades.

| Property | Value |
|----------|-------|
| Input | Task file path, `[[note name]]`, or empty (lists pending) |
| Output | Updated target note + task file enrich section |

Adds published findings to claims originally created from a different source. Reads actual source lines from the literature archive and integrates them as prose -- never fabricates from training knowledge. Evaluates YAML provenance upgrades (confidence, source_class, source) and signals post-enrich actions (title-sharpen, split-recommended, merge-candidate). Supports pipeline mode (`--handoff` from /ralph) and interactive mode with proposal approval. Respects quarantine guard on federation imports.

---

#### /ralph
Orchestrate the full processing chain with fresh context per phase.

| Property | Value |
|----------|-------|
| Input | Path to inbox/ file |
| Output | Fully processed claims |

Named orchestrator for the complete pipeline. Manages context freshness by invoking each phase in a separate context window. Recommended for deep processing of important sources.

---

#### /archive-batch
Archive completed processing batches.

| Property | Value |
|----------|-------|
| Input | `{batch-id}` or `--all` |
| Output | Archived batch folder with SUMMARY.md |

Moves task files to `ops/queue/archive/{date}-{batch-id}/`, generates a human-readable SUMMARY.md with claims table and processing timeline, and flags queue entries as `archived` (entries are never deleted, preserving provenance). Single-batch mode requires all entries to be done; `--all` mode archives every fully completed batch.

---

### Queue and Navigation

#### /tasks
View and manage the task queue.

| Property | Value |
|----------|-------|
| Input | Optional filter (phase, status) |
| Output | Task list from ops/queue/ |

Displays pipeline tasks tracked in ops/queue/queue.json. Each task tracks a claim through phases (create, reflect, reweave, verify). Supports filtering by phase and status.

---

#### /next
Intelligent next-action recommendation.

| Property | Value |
|----------|-------|
| Input | None |
| Output | Prioritized recommendation with rationale |

Evaluates condition-based triggers and queue state. Fires maintenance conditions (orphan claims, dangling links, inbox pressure, pending observations, pending tensions, topic map size). Recommends the highest-priority action with a rationale. Priority derives from consequence speed: session-critical > multi-session > slow-burn.

---

#### /stats
Vault metrics and progress visualization.

| Property | Value |
|----------|-------|
| Input | None |
| Output | Metrics report |

Reports: claim count, inbox count, observation count, tension count, topic map count, orphan count, dangling link count, average links per claim, queue depth by phase. Provides a snapshot of vault health and processing throughput.

---

#### /graph
Graph query generation and analysis.

| Property | Value |
|----------|-------|
| Input | Query type (triangles, clusters, bridges, orphans, influence) |
| Output | Analysis results |

Queries the wiki-link graph:
- **Triangle detection** -- find synthesis opportunities (A links B and C, but B and C are unlinked).
- **Cluster detection** -- find connected components and isolated knowledge islands.
- **Bridge detection** -- find structurally critical claims.
- **Orphan detection** -- claims with zero incoming links.
- **Influence flow** -- rank claims by hub/authority patterns.

---

### Research and Learning

#### /learn
Research a topic and grow the knowledge graph.

| Property | Value |
|----------|-------|
| Input | Topic or question |
| Output | Inbox material, optionally processed into claims |

Conducts research using the configured research stack (web-search by default). Results are deposited in inbox/ with provenance metadata (source_type, research_prompt, generated timestamp). Optionally chains into /reduce for immediate processing.

---

### Self-Evolution

#### /remember
Capture friction and methodology learnings.

| Property | Value |
|----------|-------|
| Input | Observation description |
| Output | Observation note in ops/observations/ |

Captures friction signals, surprises, process gaps, and methodology insights as atomic notes in ops/observations/. Categories: friction, surprise, process-gap, methodology. Accumulation triggers: 10+ observations suggest /rethink.

See [Meta-Skills](meta-skills.md) for detailed usage.

---

#### /rethink
Review accumulated observations and tensions.

| Property | Value |
|----------|-------|
| Input | None (reads ops/observations/ and ops/tensions/) |
| Output | Triaged observations, resolved tensions, methodology updates |

Triages each pending item: PROMOTE (to notes/), IMPLEMENT (update methodology), ARCHIVE (discard), or KEEP PENDING. Resolves tensions between contradicting claims or methodology conflicts.

See [Meta-Skills](meta-skills.md) for detailed usage.

---

#### /refactor
Restructure claims and topic maps.

| Property | Value |
|----------|-------|
| Input | Target claim or topic map |
| Output | Restructured content with updated links |

Split bundled claims, merge near-duplicates, reorganize topic map sections, rename claims (with wiki-link propagation). Uses ops/scripts/rename-note.sh for safe renames.

---

#### /dev
Code section health checks across the codebase.

| Property | Value |
|----------|-------|
| Input | `[section]`, `--changed`, `--affected <section>`, or empty (all sections) |
| Output | Section health report with module metrics |

Runs tests, lint, build, and coverage checks across codebase sections defined in `ops/sections.yaml`. Reports Python/R module counts, test-to-code ratio, skill count, and per-section pass/fail status. Complements /health (vault integrity) with code integrity -- both should be green before releases.

---

### Meta-Commands

### Plugin Skills (arscontexta)

The following skills require the arscontexta plugin. They provide research-backed methodology guidance, system scaffolding, and vault health diagnostics.

#### /health
Run a comprehensive vault health check.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | None |
| Output | Health report with actionable items |

Checks: orphan claims, dangling links, schema violations, topic map coherence, stale content. Each finding includes file path, issue description, and suggested resolution.

---

#### /help
Show available commands and brief descriptions.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | Optional command name for detailed help |
| Output | Command list or detailed usage |

---

#### /architect
Restructure system design by modifying configuration dimensions.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | Question or change request about system structure |
| Output | Updated ops/config.yaml, ops/methodology/ |

See [Meta-Skills](meta-skills.md) and [Configuration](configuration.md) for detailed usage.

---

#### /ask
Query the methodology knowledge base.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | Question about system design or methodology |
| Output | Answer grounded in ops/methodology/ and the bundled research base |

See [Meta-Skills](meta-skills.md) for detailed usage.

---

#### /setup
Initialize a new vault or re-initialize an existing one.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | None (interactive) |
| Output | Vault structure, templates, hooks, skills, config |

Runs the full derivation process: selects a preset, configures dimensions, generates skills and hooks, creates templates and folder structure.

---

#### /reseed
Re-derive the system configuration from updated dimension choices.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | Updated dimension positions or preset |
| Output | Updated CLAUDE.md, config.yaml, derivation records |

When friction patterns accumulate rather than resolve, reseed recalculates the configuration from modified dimension positions. Traces changes to specific evidence in ops/derivation.md.

---

#### /tutorial
Interactive walkthrough of system features.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | Optional track (researcher, manager, personal) |
| Output | Real vault content created via guided steps -- claims, topic maps, and connections that teach by doing |

---

#### /add-domain
Add a new research domain to the vault.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | Domain name and description |
| Output | Domain-specific folders, templates, vocabulary, and topic map integrated with existing architecture |

---

#### /recommend
Get research-backed architecture advice for your knowledge system.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | Use case description, constraints, and goals |
| Output | Specific architecture recommendations grounded in TFT research with rationale for each decision |

---

#### /upgrade
Apply plugin knowledge base updates to the existing system.

| Property | Value |
|----------|-------|
| Requires | arscontexta plugin |
| Input | None (consults arscontexta research graph automatically) |
| Output | Proposed skill upgrades with research justification -- never auto-implements, requires approval |

---

#### /profile
Create, list, show, and activate domain profiles for any research field.

| Property | Value |
|----------|-------|
| Invoked by | User (before /onboard, or standalone) |
| Context | main (orchestrator) + fork (sub-skills) |
| Reads | _code/profiles/, ops/config.yaml |
| Writes | _code/profiles/{name}/, ops/config.yaml, _code/styles/palettes.yaml |

**Modes:**
- `(empty)` -- 6-turn conversational interview to create a new profile
- `--list` -- list available profiles via `discover_profiles()`
- `--show {name}` -- display profile summary via `load_profile()`
- `--activate {name}` -- apply profile to ops/config.yaml and merge palettes

**Architecture:** Main-context orchestrator with four fork sub-skills:
- `profile-suggest` -- web search for domain confounders and tools (haiku)
- `profile-generate` -- write all profile YAML files atomically (sonnet)
- `profile-validate` -- run `load_profile()` validation (haiku)
- `profile-query` -- handle --list and --show modes (haiku)

Interview collects: domain identity, data layers, technical/biological confounders, PII patterns, literature backend routing, and color palettes. Generated profiles are compatible with all existing consumers (/onboard, /init, /eda, /plot, /literature, /learn). No new Python code -- uses existing `domain_profile.py` entry points.

---

#### /onboard
Bootstrap lab integration -- scan filesystem, register projects, build data inventory, create research goals.

| Property | Value |
|----------|-------|
| Invoked by | User (first session entry point) |
| Context | main (orchestrator) + fork (sub-skills) |
| Reads | Lab filesystem, existing projects/, _research/data-inventory.md |
| Writes | projects/, _research/data-inventory.md, _research/goals/, self/goals.md |

**Architecture:** Main-context orchestrator with three fork sub-skills:
- `onboard-scan` -- filesystem discovery, convention mining, institution lookup
- `onboard-generate` -- vault artifact creation
- `onboard-verify` -- schema and link validation

Detailed instructions live in `reference/` files that sub-skills Read on demand. The orchestrator handles all user interaction as natural conversation turns (2-3 review turns). Runs once per lab; use `--update` for incremental re-scans. For multi-lab roots, onboards one lab at a time (depth-first). Natural next step is /init.

---

#### /init
Seed foundational knowledge claims for new vaults or cycle transitions.

| Property | Value |
|----------|-------|
| Invoked by | User (after /onboard) |
| Context | main (orchestrator) + fork (sub-skills) |
| Reads | _research/goals/, self/, notes/, _research/data-inventory.md, projects/ |
| Writes | notes/ (claims), _research/cycles/ (cycle mode), self/goals.md |

**Architecture:** Main-context orchestrator with three fork sub-skills:
- `init-orient` -- vault state reading
- `init-generate` -- claim generation (orientation, methodology, confounders, inversions)
- `init-wire` -- graph wiring (topic maps, project bridges, goal updates)

**Seed mode** (default): natural conversation flow -- goal selection, core questions interview, demo claim walkthrough (user composes one claim interactively), batch generation of remaining claims, grouped review, and graph wiring. Uses /onboard artifacts to pre-populate generation. For multiple goals, seeds one at a time (depth-first).

**Cycle mode** (`--cycle`): research cycle transition -- generates cycle summary, refreshes assumption inversions with new evidence, reconciles daemon recommendations.

---

#### /federation-sync
Sync claims and hypotheses across federated vaults.

| Property | Value |
|----------|-------|
| Input | Remote vault identifier or sync config |
| Output | Synchronized claims and hypotheses, conflict report |

Synchronizes selected claims and hypotheses between federated vault instances. Detects conflicts, preserves provenance, and logs sync operations.

---

## Example Session

The example below uses a clinical research question. The co-scientist system is domain-agnostic -- substitute any research question relevant to your field.

```
/research
> "What early indicators predict treatment response independently of baseline severity?"
# Creates goal note, shows menu

/generate
# Pick "literature synthesis" mode
# Searches configured backends, proposes 3 hypotheses, approve each

/review
# Pick "quick screen" mode
# Scores each hypothesis on mechanistic coherence and domain plausibility

/tournament
# Run 3 pairwise matches, override any verdict
# Elo ratings update automatically

/meta-review
# Synthesizes what made winners win
# Feedback improves the next /generate and /review calls

/evolve
# Pick top hypothesis, evolve via "grounding enhancement"
# New hypothesis enters the pool at Elo 1200
```

---

## See Also

- [Manual Hub](manual.md)
- [Workflows](workflows.md) -- how skills compose into work patterns
- [Meta-Skills](meta-skills.md) -- deep guide to introspective commands
