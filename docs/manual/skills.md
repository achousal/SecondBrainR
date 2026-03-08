---
description: "Complete command reference for all vault skills"
type: manual
created: 2026-02-21
updated: 2026-03-07
---

# Skills Reference

All commands use bare slash syntax (e.g., `/reduce`, `/research`). **Prerequisites:** [Getting Started](getting-started.md).

---

## Quick Reference

### Co-Scientist Loop

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/research` | Orchestrate the full loop | Entry point -- sets goals, presents menu |
| `/generate` | Create hypotheses | Need new ideas grounded in literature |
| `/review` | Evaluate hypotheses | Score and critique before ranking |
| `/tournament` | Rank via pairwise debate | Compare hypotheses head-to-head (Elo) |
| `/evolve` | Refine top hypotheses | Strengthen, combine, or simplify winners |
| `/landscape` | Map hypothesis space | Find clusters, gaps, redundancies |
| `/meta-review` | Extract patterns from debates | Feed improvements into next cycle |
| `/literature` | Search and save papers | PubMed, arXiv, Semantic Scholar, OpenAlex |

### Knowledge Processing Pipeline

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/seed` | Queue source for processing | New paper or material enters inbox/ |
| `/ralph` | Run pipeline with fresh context | Batch-process queued tasks (extract -> create -> reflect -> reweave -> verify) |
| `/reduce` | Extract claims from source | Single-source processing |
| `/reflect` | Find connections, update MOCs | After new claims are created |
| `/reweave` | Revisit old claims with new context | Backward pass -- update earlier notes |
| `/enrich` | Add evidence to existing claims | New source supports an existing claim |
| `/verify` | Quality-check a claim | Schema, description, link health |
| `/validate` | Batch schema check | Audit all notes/ at once |
| `/archive-batch` | Archive completed batches | Clean up after /ralph finishes |

### Navigation and Status

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/next` | Best next action | "What should I do?" |
| `/tasks` | View processing queue | Check pending work |
| `/stats` | Vault metrics | Snapshot of health and growth |
| `/graph` | Query knowledge graph | Find triangles, bridges, orphans |

### Research Support

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/learn` | Research a topic via web | Grow knowledge graph from external sources |
| `/experiment` | Log experiment metadata | Record parameters, results, artifacts |
| `/eda` | Exploratory data analysis | Auto-redacted summaries and themed plots |
| `/plot` | Publication-quality figures | Generate PDF figures with research theme |
| `/project` | Manage research projects | Register, update, query projects |

### Self-Evolution

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/remember` | Capture friction signals | Something surprising or broken |
| `/rethink` | Review accumulated observations | 10+ observations or 5+ tensions |
| `/refactor` | Restructure claims and MOCs | Split, merge, rename, reorganize |
| `/dev` | Code section health checks | Tests, lint, coverage for _code/ |

### System and Setup (arscontexta plugin)

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/setup` | Scaffold a new vault | First-time initialization |
| `/onboard` | Bootstrap lab integration | Connect a lab's filesystem and projects |
| `/init` | Seed foundational claims | After /onboard, before research |
| `/profile` | Manage domain profiles | Create or switch research domains |
| `/health` | Vault integrity diagnostics | Periodic maintenance |
| `/architect` | System design changes | Modify configuration dimensions |
| `/ask` | Query methodology knowledge base | "How should I..." questions |
| `/recommend` | Architecture advice | Design decisions for your system |
| `/upgrade` | Apply plugin updates | Check for methodology improvements |
| `/add-domain` | Add research domain | Extend vault to new area |
| `/reseed` | Re-derive from dimensions | After accumulated structural drift |
| `/tutorial` | Interactive walkthrough | Learn by doing |
| `/help` | Command discovery | "What can I do?" |
| `/federation-sync` | Sync across vaults | Multi-vault collaboration |

### Typical Workflows

**First session:** `/onboard` -> `/init` -> `/seed` foundational papers -> `/ralph`

**New paper:** `/seed` -> `/ralph` (or `/reduce` -> `/reflect` -> `/reweave` -> `/verify`)

**New research question:** `/research` -> `/generate` -> `/review` -> `/tournament` -> `/meta-review` -> `/evolve`

**Maintenance:** `/next` -> `/health` -> `/rethink` (if observations accumulated)

---

## Research Loop

`/research` is the entry point. It sets a research goal, then presents a menu of the six agents below. Before calling any agent, it injects the latest `/meta-review` feedback as context. The user drives every step -- the supervisor never auto-advances.

```
 /generate ──> /review ──> /tournament
     ^                         |
     |                         v
 /evolve  <── /meta-review <──┘
                   |
              /landscape (anytime -- map the space)
```

### /generate -- Create hypotheses

4 modes: **literature synthesis** (search backends, find gaps, propose hypotheses with citations), **self-play debate** (simulate expert perspectives, extract ideas), **assumption-based reasoning** (relax assumptions of existing hypotheses), **research expansion** (use meta-review feedback to target under-explored regions). Output: hypothesis notes with Elo=1200, generation=1, status=proposed.

### /review -- Evaluate hypotheses

6 modes: **quick screen** (1-10 scores on novelty, correctness, testability, impact), **literature review** (check if published or contradicted), **deep verification** (decompose into assumptions, check each), **observation review** (test against experimental data), **simulation review** (walk through mechanism, find failure modes), **tournament-informed** (apply learned critique patterns). Scoring weights: correctness 30%, testability 25%, novelty 25%, impact 20%.

### /tournament -- Rank via pairwise debate

Generates matchups prioritizing under-matched and similar-Elo pairs. Structured debate across four dimensions. Top 25% get multi-turn deep debate; bottom 75% get single-turn comparison. Elo system: K=32, rating sum preserved.

### /evolve -- Refine top hypotheses

5 modes: **grounding enhancement** (strengthen evidence, fix flagged assumptions), **combination** (merge 2-3 top hypotheses), **simplification** (strip non-essential assumptions), **research extension** (extend to adjacent domains), **divergent exploration** (contrarian alternatives, target empty landscape regions). Output: new generation, parents linked bidirectionally, Elo=1200.

### /landscape -- Map hypothesis space

Clusters hypotheses by shared tags, assumptions, mechanisms, citations, and Elo tier. Outputs cluster descriptions, identified gaps, redundancy flags, and suggested directions for /generate and /evolve.

### /meta-review -- Extract patterns from debates

Analyzes recurring weaknesses, key literature, invalid assumptions, winner patterns. Produces recommendations for /generate (what's missing) and /evolve (what to fix first). This is the self-improving loop mechanism -- output persists in the vault and feeds future cycles.

### /literature -- Search and save papers

Searches configured backends (PubMed, arXiv, Semantic Scholar, OpenAlex -- controlled by `literature.sources` in config). Presents results as a table. Saves selected papers as structured notes with frontmatter and sections (Abstract, Key Points, Methods Notes, Relevance, Citations). Also usable standalone outside /research.

---

## Knowledge Pipeline

Material flows through a fixed sequence. `/ralph` runs the whole chain with fresh context per phase. Individual commands let you run phases manually.

```
inbox/ ──> /seed ──> /reduce ──> /reflect ──> /reweave ──> /verify
                        |            |             |
                   extract claims  connect them  revisit old ones
```

### /seed -- Queue source for processing

Checks for duplicates, archives the source, creates an extract task in `ops/queue/`, and updates the queue. DOI stubs are silently enriched during queueing. Use `--all` to queue the entire inbox at once. Does not create claims -- all extraction goes through /reduce.

### /ralph -- Run the full pipeline

Named orchestrator that batch-processes queued tasks. Spawns each phase (extract, create, reflect, reweave, verify) in a separate context window for freshness. Supports serial, parallel, batch filter, and dry run modes.

### /reduce -- Extract claims from source

Reads source material through the domain lens. Extracts across 6 categories: claims, evidence, methodology comparisons, contradictions, open questions, design patterns. Each claim must pass quality: title as prose, description adds beyond title, specific enough to disagree with. Creates reflect tasks for each extracted claim.

### /reflect -- Find connections, update topic maps

Three operations: forward connections (what relates to this claim?), backward connections (what older claims need updating?), topic map membership (ensure at least one MOC includes this claim). Creates reweave tasks for connected claims.

### /reweave -- Revisit old claims with new context

Asks: "If I wrote this claim today, what would be different?" Adds connections, sharpens the title, splits bundled ideas, challenges with new evidence. Scope configurable: related, broad, or full. Creates verify tasks.

### /enrich -- Add evidence to existing claims

Integrates published findings into claims originally created from a different source. Reads actual source lines -- never fabricates. Evaluates provenance upgrades (confidence, source_class) and signals post-enrich actions (title-sharpen, split, merge). Supports pipeline mode (`--handoff`) and interactive mode.

### /verify -- Quality-check a single claim

Three checks: **description quality** (cold-read test -- predict content from title+description alone), **schema compliance** (required fields, valid enums), **link health** (no broken or orphaned links).

### /validate -- Batch schema check

Checks every claim in notes/ against the schema template. Reports missing fields, invalid enums, empty descriptions, and constraint violations.

### /archive-batch -- Archive completed batches

Moves completed task files to `ops/queue/archive/`, generates SUMMARY.md with claims table and timeline. Queue entries are flagged `archived` (never deleted). Use `--all` to archive every completed batch.

---

## Tools

Standalone utilities -- invoke directly, no orchestrator needed.

**`/learn`** -- Research a topic using the configured research stack (web-search by default). Results go to inbox/ with provenance metadata. Optionally chains into /reduce for immediate processing.

**`/experiment`** -- Log experiment metadata: parameters, seed, code version, environment, timestamp, resources. Links experiments bidirectionally to hypotheses.

**`/eda`** -- Exploratory data analysis with automatic PII redaction (SubjectID, SSN, Email, plus profile-specific patterns). Computes summary stats, correlations, distributions. Generates themed plots. Saves report to vault.

**`/plot`** -- Publication-quality figures using the research theme (14pt base, bold titles, grey90 strips, bottom legend, left+bottom spines). Semantic color palettes. PDF vector output, 300 DPI raster.

**`/project`** -- Register, update, and query research projects. Detects infrastructure (CLAUDE.md, git, tests). Creates symlinks under _dev/ for Obsidian. Links projects to research goals.

---

## Vault Operations

Status, navigation, and graph analysis.

**`/next`** -- Recommends the highest-priority next action by evaluating condition-based triggers and queue state: orphan claims, dangling links, inbox pressure, pending observations/tensions, topic map size. Priority: session-critical > multi-session > slow-burn.

**`/tasks`** -- View pipeline tasks in `ops/queue/queue.json`. Each task tracks a claim through phases (create, reflect, reweave, verify). Filter by phase or status.

**`/stats`** -- Vault metrics: claim count, inbox count, observation/tension counts, topic map count, orphan count, dangling links, average links per claim, queue depth by phase.

**`/graph`** -- Query the wiki-link graph: **triangles** (synthesis opportunities), **clusters** (connected components), **bridges** (structurally critical claims), **orphans** (zero incoming links), **influence** (hub/authority ranking).

**`/health`** -- Vault integrity diagnostics (requires arscontexta plugin). Checks orphan claims, dangling links, schema violations, topic map coherence, stale content. Each finding includes file path and suggested fix.

**`/validate`** -- Batch schema check across all notes/ (see Knowledge Pipeline above).

---

## Self-Evolution

How the system learns from its own friction.

**`/remember`** -- Capture friction signals as atomic notes in `ops/observations/`. Categories: friction, surprise, process-gap, methodology. When 10+ observations accumulate, /rethink is recommended. See [Meta-Skills](meta-skills.md).

**`/rethink`** -- Triage pending observations and tensions. Each item is classified: PROMOTE (to notes/), IMPLEMENT (update methodology), ARCHIVE (discard), or KEEP PENDING. Resolves contradictions between claims or methodology conflicts. See [Meta-Skills](meta-skills.md).

**`/refactor`** -- Restructure claims and topic maps. Split bundled claims, merge near-duplicates, reorganize sections, rename claims with wiki-link propagation.

**`/dev`** -- Code section health checks. Runs tests, lint, build, and coverage across sections defined in `ops/sections.yaml`. Reports module counts, test-to-code ratio, per-section pass/fail. Complements /health (vault integrity) with code integrity.

---

## System Administration

Setup, configuration, and multi-vault operations. All require the arscontexta plugin unless noted.

### First-time setup

**`/setup`** -- Scaffold a new vault from scratch. Runs the full derivation: preset selection, dimension configuration, generates skills, hooks, templates, and folder structure.

**`/profile`** -- Create, list, show, or activate domain profiles. Empty invocation starts a 6-turn interview. Flags: `--list`, `--show {name}`, `--activate {name}`. Interview covers domain identity, data layers, confounders, PII patterns, literature routing, color palettes. Sub-skills: profile-suggest, profile-generate, profile-validate, profile-query.

**`/onboard`** -- Bootstrap lab integration. Scans filesystem, registers projects, builds data inventory, creates research goals. Sub-skills: onboard-scan, onboard-generate, onboard-verify. Runs once per lab; `--update` for incremental re-scans. Next step: /init.

**`/init`** -- Seed foundational knowledge claims after onboarding. **Seed mode** (default): goal selection, core questions interview, demo claim, batch generation, grouped review, graph wiring. **Cycle mode** (`--cycle`): research cycle transition, refreshes inversions, reconciles daemon recommendations. Sub-skills: init-orient, init-generate, init-wire.

### Configuration

**`/architect`** -- Modify system design by changing configuration dimensions. Updates `ops/config.yaml` and `ops/methodology/`. See [Configuration](configuration.md).

**`/reseed`** -- Re-derive the full system configuration from updated dimension positions when friction patterns accumulate rather than resolve. Traces changes to evidence in `ops/derivation.md`.

**`/ask`** -- Query the methodology knowledge base. Returns answers grounded in `ops/methodology/` and the bundled research graph. See [Meta-Skills](meta-skills.md).

**`/recommend`** -- Get architecture advice for your knowledge system. Provide use case, constraints, and goals; receive specific recommendations with TFT research rationale.

**`/upgrade`** -- Check for and apply plugin knowledge base updates. Proposes skill upgrades with research justification. Never auto-implements.

### Extending the vault

**`/add-domain`** -- Add a new research domain. Derives domain-specific folders, templates, vocabulary, and topic maps while connecting to existing architecture.

**`/tutorial`** -- Interactive walkthrough. Three tracks (researcher, manager, personal). Creates real vault content via guided steps.

**`/federation-sync`** -- Synchronize claims and hypotheses across federated vault instances. Detects conflicts, preserves provenance, logs sync operations.

**`/help`** -- Contextual command discovery. Three modes: narrative (first-time), contextual (mid-task), compact (quick reference).

---

## Example Session

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

## I/O Reference

Where each skill reads from and writes to. Most users won't need this -- it's here for debugging and extension.

| Skill | Reads | Writes |
|-------|-------|--------|
| `/research` | `_research/goals/`, `_research/hypotheses/_index.md`, `_research/meta-reviews/` | `_research/goals/` |
| `/generate` | `_research/goals/`, `_research/meta-reviews/`, `_research/landscape/`, `_research/hypotheses/` | `_research/hypotheses/`, `_research/hypotheses/_index.md` |
| `/review` | `_research/hypotheses/`, `_research/meta-reviews/` | `_research/hypotheses/` (frontmatter) |
| `/tournament` | `_research/hypotheses/`, `_research/goals/` | `_research/tournaments/`, `_research/hypotheses/` (elo), `_research/hypotheses/_index.md` |
| `/evolve` | `_research/hypotheses/`, `_research/meta-reviews/` | `_research/hypotheses/`, `_research/hypotheses/_index.md` |
| `/landscape` | `_research/hypotheses/` | `_research/landscape/` |
| `/meta-review` | `_research/tournaments/`, `_research/hypotheses/` | `_research/meta-reviews/` |
| `/literature` | Configured search backends | `_research/literature/`, `_research/literature/_index.md` |
| `/seed` | `inbox/` source file | `ops/queue/` task, archived source |
| `/ralph` | `ops/queue/` tasks | Fully processed claims in `notes/` |
| `/reduce` | `inbox/` file | `notes/` claims, reflect tasks in `ops/queue/` |
| `/reflect` | Claim + existing `notes/` | Updated claims, updated topic maps, reweave tasks |
| `/reweave` | Claim + current knowledge | Updated claim, verify tasks |
| `/enrich` | Task file or note name | Updated target note |
| `/verify` | Claim | Verification report, applied fixes |
| `/validate` | All `notes/` | Validation report |
| `/learn` | Web search results | `inbox/` material |
| `/experiment` | `_research/hypotheses/` | `_research/experiments/` |
| `/eda` | User-provided dataset | `eda-reports/` |
| `/plot` | Data + style guides | PDF figures |
| `/project` | `projects/`, filesystem | `projects/` |
| `/profile` | `_code/profiles/`, `ops/config.yaml` | `_code/profiles/{name}/`, `ops/config.yaml` |
| `/onboard` | Lab filesystem | `projects/`, `_research/goals/`, `self/goals.md` |
| `/init` | `_research/goals/`, `self/`, `notes/` | `notes/` claims, `self/goals.md` |

---

## See Also

- [Manual Hub](manual.md) -- documentation index and reading order
- [Workflows](workflows.md) -- how skills compose into work patterns
- [Meta-Skills](meta-skills.md) -- deep guide to introspective commands
