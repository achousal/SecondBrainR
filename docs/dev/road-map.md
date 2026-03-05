---
description: "Consolidated feature road map for EngramR, grounded in methodology research claims and practical system gaps. Three tiers by impact and dependency."
type: development
status: active
created: 2026-03-04
---

# EngramR Feature Road Map

Prioritized feature opportunities grounded in Ars Contexta research claims and operational gaps observed across 200+ notes, 4 research goals, and the co-scientist loop.

---

## Dependency Graph

```
Vault Query Infrastructure (1.1)
  Phase A: Slack bot tool calling (keyword search)
  Phase B: Semantic search (embeddings)
  Phase C: Upgrade tool calling search backend to embeddings
  |-> Contradiction Detection (2.2) [requires Phase B]
  |-> Cross-Goal Synthesis (3.1) [requires Phase B]

Resurfacing + Spaced Maintenance (1.2) -- independent

Community Detection (1.3) -- independent, benefits from 1.1 Phase B

Evidence Graph (2.1) -- independent, enables 3.3

Literature Watch (2.3) -- independent

Hypothesis Changelog (3.2) -- independent
```

Start with Tier 1 items in parallel. Tier 2 builds on Tier 1 foundations. Tier 3 is longer horizon.

---

## Tier 1 -- Foundational (high impact, unblocks downstream features)

### 1.1 Vault Query Infrastructure

**Problem:** The Slack bot relies on static cached context refreshed every 5 min -- it cannot search notes, check live queue state, or look up specific claims. Skill routing uses fragile regex intent extraction. Beyond the bot, keyword search over 200+ notes creates blind spots: semantic neighbors without shared vocabulary are invisible, and `/reflect` misses non-obvious connections.

**Research grounding:**
- [[spreading activation models how agents should traverse]] -- vault traversal is spreading activation; keyword search only traverses explicit lexical matches, missing semantic neighbors that lack shared terms
- [[navigational vertigo emerges in pure association systems without local hierarchy]] -- without semantic search, notes connected by meaning but not by explicit links are unreachable
- [[metadata reduces entropy enabling precision over recall]] -- embeddings add a semantic filtering axis alongside the existing YAML metadata axis
- [[descriptions are retrieval filters not summaries]] -- structured tool results return description-level information that enables progressive disclosure via API
- [[retrieval utility should drive design over capture completeness]] -- tool calling lets the bot answer "how do I find this?" dynamically instead of hoping the cached context contains the answer

#### Phase A -- Slack Bot Tool Calling (keyword search)

Ship immediately. No dependencies. Gives the bot live vault access via Anthropic `tool_use` with keyword-based search as the initial backend.

**What it does:**
- Add tool use loop to `_call_claude()` with 5-iteration cap
- 8 read-only tools (no confirmation needed):

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `search_notes` | Keyword search across notes/ titles + descriptions | `query: str`, `limit: int = 10` | `[{title, description, path}]` |
| `search_literature` | Keyword search across _research/literature/ | `query: str`, `limit: int = 10` | `[{title, description, path}]` |
| `get_note` | Read a specific note by title or path | `title: str` | `{frontmatter, body}` |
| `vault_stats` | Current vault metrics | (none) | `{note_count, hypothesis_count, inbox_count, queue_depth}` |
| `queue_status` | Processing queue state | (none) | `{pending, in_progress, completed_today}` |
| `list_goals` | Active research goals | (none) | `[{name, scope, status}]` |
| `search_hypotheses` | Search hypotheses by keyword | `query: str` | `[{title, elo, status}]` |
| `get_reminders` | Active reminders | (none) | `[{text, due}]` |

- Mutative tools (Phase 2, gated behind confirmation flow): `create_reminder`, `queue_skill`
- Deprecate `extract_skill_intent()` regex for reads; keep `detect_explicit_command()` for `/command` syntax
- 30s TTL cache on `vault_stats` and `queue_status` to reduce redundant filesystem reads
- System prompt guidance: "If a tool returns an error, tell the user what went wrong"

**Design:** `_search_notes` accepts a `search_backend` parameter (`keyword` | `semantic`) so Phase C is a config toggle, not a code rewrite. Default: `keyword`.

**Acceptance criteria:**
- Bot answers "how many notes do I have?" with live stats, not stale cache
- Bot answers "what claims about p-tau217?" with actual search results
- Bot answers "what's in my queue?" with live queue state
- Bot answers "what literature do I have on microglia?" via `search_literature`
- No regression in existing skill routing for mutative commands
- Tool use adds < 3s average latency to responses

**Detailed design:** Archived to `docs/dev/archive/slack-bot-tool-calling.md` (subsumed by this roadmap)

#### Phase B -- Semantic Search (embeddings)

Requires Phase A infrastructure (tool schemas, executor pattern). Adds embedding-based search as a backend.

**What it does:**
- Embed notes on write (post-reduce hook or daemon pass)
- Store vectors locally (sqlite-vss, lancedb, or similar file-based store)
- Query by meaning: `semantic_search(query, limit=10) -> [{title, score, path}]`
- Expose as a Python function callable by Slack bot tools, `/reflect`, and `/reweave`

**Key decisions:**
- Embedding model: local (e.g. sentence-transformers) vs API (Anthropic/OpenAI embeddings)
- Storage: sqlite-vss (zero-dependency) vs lancedb (richer API) vs chromadb
- Index scope: notes/ + _research/hypotheses/ + _research/literature/ (unified)
- Rebuild strategy: full reindex on demand, incremental on note create/update

**Acceptance criteria:**
- `semantic_search("vascular inflammation microglia")` returns relevant claims even if none contain all three words
- Reindex of 200 notes completes in < 30s locally
- No external service dependency (works offline, on HPC)

**Detailed design:** To be written in `docs/dev/semantic-search.md`

#### Phase C -- Search Backend Upgrade

Flip `search_backend` config from `keyword` to `semantic` in the Slack bot tool calling layer. One-line config change plus integration test.

**Acceptance criteria:**
- `search_notes` and `search_literature` tools return semantically relevant results
- Cross-vocabulary queries work ("vascular inflammation" finds "neuroinflammatory priming" notes)
- Tool result truncation handles richer semantic results (titles + scores only; use `get_note` for detail)

---

### 1.2 Random Resurfacing and Spaced Maintenance

**Problem:** Maintenance attention follows recency bias. Older claims from the seeding phase (75+ claims) have never been revisited. Write-only memory accumulates as dead weight.

**Research grounding:**
- [[random note resurfacing prevents write-only memory]] -- without random selection, maintenance exhibits selection bias toward recently active notes; the bottom 80% of notes by link density receive minimal attention
- [[spaced repetition scheduling could optimize vault maintenance]] -- review intervals should adapt to note maturity: new claims need 7-day verification, mature evergreens need 180-day review
- [[incremental formalization happens through repeated touching of old notes]] -- quality improves through many small touches over time, not single comprehensive reviews

**What it does:**
- Daemon maintenance pass selects N notes per cycle using two strategies:
  - **Random selection**: uniform probability across all notes (counteracts attention bias)
  - **Spaced scheduling**: priority queue based on `last_reviewed` date and maturity tier
- For each selected note, run a tending checklist:
  - Are wiki links valid (no dangling)?
  - Is the description still accurate given newer claims?
  - Are there new connections to make (check recent notes)?
  - Does the claim need splitting (too compound)?
- Record `last_reviewed` in frontmatter or a sidecar index
- Surface results as a maintenance report or `/next` suggestions

**Key decisions:**
- Selection ratio: how many random vs scheduled per cycle
- Maturity tiers: derive from note age + review count, or use explicit `maturity` field
- Storage for review history: frontmatter field vs external index file
- Integration: daemon automated pass vs `/resurface` manual skill vs both

**Acceptance criteria:**
- Every note has nonzero probability of being selected in any maintenance cycle
- Notes created > 30 days ago with no review get priority
- Maintenance pass completes in < 60s for 200 notes
- Results are actionable: specific suggestions per note, not generic "review this"

**Detailed design:** To be written in `docs/development/resurfacing.md`.

---

### 1.3 Community Detection for Topic Map Health

**Problem:** Topic maps are human hypotheses about where boundaries fall. As the vault grows past 200 notes, cluster boundaries shift silently. Topic maps that served 15 claims struggle at 40. Cross-goal bridge claims go unnoticed.

**Research grounding:**
- [[community detection algorithms can inform when MOCs should split or merge]] -- Louvain/Leiden on the wiki-link graph reveals natural communities that may not align with current topic map boundaries; three signals matter: split (one MOC covers two communities), merge (two MOCs cover one community), drift (notes migrating between communities)
- [[small-world topology requires hubs and dense local links]] -- the power-law distribution that makes navigation work also makes structural shifts hard to perceive
- [[MOCs are attention management devices not just organizational tools]] -- stale MOC boundaries reshape how agents load context for entire topic areas

**What it does:**
- Parse the wiki-link graph from notes/ into an adjacency structure
- Run community detection (Louvain or Leiden via networkx or leidenalg)
- Compare algorithmic communities against current topic map membership
- Report: split signals, merge signals, drift signals, orphan clusters
- Identify cross-goal bridge claims (notes appearing in communities spanning multiple research goals)

**Key decisions:**
- Graph scope: notes/ only, or include hypotheses and literature notes
- Algorithm: Louvain (simpler, networkx built-in) vs Leiden (better quality, separate dependency)
- Trigger: manual `/graph` skill vs periodic daemon health check vs both
- Action: advisory report only, or propose specific topic map edits

**Acceptance criteria:**
- Detects at least one split or merge signal in the current 200+ note vault
- Identifies cross-goal bridge claims between the 4 active research goals
- Runs in < 10s on the current vault
- Output is human-readable with specific actionable recommendations

**Detailed design:** To be written in `docs/development/community-detection.md`. Partially covered by existing `/graph` skill infrastructure.

---

## Tier 2 -- Building on foundations (high value, benefits from Tier 1)

### 2.1 Evidence Graph (Typed Claim-Hypothesis Edges)

**Problem:** Claims link to topic maps, but the hypothesis-to-evidence chain is implicit. `/tournament` debates hypotheses without citing specific supporting or contradicting evidence. "What breaks if this claim is falsified?" is unanswerable.

**Research grounding:**
- [[source attribution enables tracing claims to foundations]] -- provenance tracking requires explicit typed edges, not implicit co-occurrence in topic maps
- [[claims must be specific enough to be wrong]] -- falsifiability requires knowing which evidence supports a claim so that contradicting evidence can be identified

**What it does:**
- Add an optional `evidence` field to hypothesis frontmatter:
  ```yaml
  evidence:
    supports:
      - "[[claim-title-1]]"
      - "[[claim-title-2]]"
    contradicts:
      - "[[claim-title-3]]"
    assumes:
      - "[[claim-title-4]]"
  ```
- `/generate` and `/evolve` populate evidence links when creating or refining hypotheses
- `/tournament` cites specific evidence during debates
- New query: "what hypotheses depend on this claim?" (reverse evidence lookup)
- Falsification cascade: if a claim is contradicted by new evidence, surface all hypotheses that depend on it

**Key decisions:**
- Storage: hypothesis frontmatter (co-located) vs separate evidence graph file (centralized)
- Edge types: start with `supports`, `contradicts`, `assumes`; extend later
- Automation: `/generate` auto-links vs manual curation vs hybrid

**Acceptance criteria:**
- At least 3 existing hypotheses have evidence links populated
- `/tournament` debates reference specific claims by title
- Reverse query works: given a claim, list all hypotheses that cite it
- No regression in existing hypothesis workflow

---

### 2.2 Contradiction Detection on Ingest

**Problem:** When `/reduce` creates a new claim, it does not check whether the claim contradicts existing claims. Contradictions accumulate silently until manual `/rethink`.

**Research grounding:**
- [[controlled disorder engineers serendipity through semantic rather than topical linking]] -- the most productive surprises are contradictions you did not expect; auto-surfacing them at ingest is serendipity at the boundary
- [[backward maintenance asks what would be different if written today]] -- contradiction detection is automated backward maintenance applied at the moment of creation

**What it does:**
- Post-reduce hook: for each new claim, find semantically similar existing claims (requires 1.1)
- Apply negation heuristics: title polarity reversal, contradictory keywords, opposing confidence levels
- If contradiction detected: auto-create a tension note in `ops/tensions/` linking the two claims
- Surface in `/next` and session orient

**Dependency on 1.1 Phase B:** Semantic search is required to find claims that are topically related but make opposing arguments. Keyword matching alone misses most contradictions.

**Key decisions:**
- Sensitivity threshold: how similar must claims be before checking for contradiction
- Negation detection: simple heuristics (antonyms, "does not", polarity) vs LLM judgment
- Auto-create tension vs flag for human review
- Batch mode: run across all existing claims on first deployment

**Acceptance criteria:**
- Detects at least one known contradiction in the existing vault (e.g., competing claims about chromosome complement effects)
- False positive rate < 30% (most flagged tensions are genuine or plausible)
- Runs in < 5s per new claim
- Does not block `/reduce` pipeline (async post-hook)

---

### 2.3 Literature Watch (Scheduled PubMed/arXiv Monitoring)

**Problem:** Literature discovery is manual -- user must remember to run `/literature` with the right queries. New papers relevant to active goals go unnoticed until the next manual search.

**Research grounding:**
- [[throughput matters more than accumulation]] -- the bottleneck is surfacing the right sources before they go stale, not having sources to process
- [[temporal processing priority creates age-based inbox urgency]] -- sources older than 72h are critical; automated capture keeps the pipeline fed with fresh material

**What it does:**
- Each research goal defines 2-5 standing search queries (PubMed, arXiv, Semantic Scholar)
- Daemon runs queries on a schedule (daily or weekly)
- Deduplicates against existing literature notes (by DOI, title similarity)
- New hits land in `inbox/` with full provenance metadata (source_type: literature-watch, query, timestamp)
- Session orient surfaces: "3 new papers relevant to p-tau217 confounders since last session"

**Key decisions:**
- Query storage: in research goal frontmatter vs separate config file
- Schedule: daemon cron-style vs manual trigger with last-run tracking
- Dedup strategy: exact DOI match + fuzzy title similarity
- Volume control: max N results per query per run to prevent inbox flooding

**Acceptance criteria:**
- Standing queries for at least 2 of the 4 active research goals
- Dedup correctly skips papers already in `_research/literature/`
- New hits include enough metadata for `/seed` to process without manual enrichment
- No duplicate inbox entries across consecutive runs

---

## Tier 3 -- Longer Horizon (valuable, less urgent)

### 3.1 Cross-Goal Synthesis Detection

**Problem:** The 4 research goals share biological mechanisms (neuroinflammation, vascular pathology, sex differences, biomarker validation) but are processed independently. Bridge claims connecting goals are not surfaced automatically.

**Research grounding:**
- [[controlled disorder engineers serendipity through semantic rather than topical linking]] -- cross-goal connections are the highest-value serendipitous discoveries because they bridge entire research programs
- [[cross-links between MOC territories indicate creative leaps and integration depth]] -- notes appearing in multiple distant topic maps are evidence of genuine integration

**What it does:**
- Periodic scan: find claims with high embedding similarity to claims from different research goals
- Or: find claims that appear in topic maps associated with multiple goals
- Surface as "bridge claim" candidates with suggested cross-goal connections
- Feed into `/generate` as cross-goal hypothesis seeds

**Dependency on 1.1 Phase B:** Requires semantic search to find claims that are mechanistically related across goals but use different vocabulary.

---

### 3.2 Hypothesis Changelog

**Problem:** When `/evolve` modifies a hypothesis, the old version is lost. No way to track what changed across tournament cycles or why.

**What it does:**
- Before `/evolve` overwrites a hypothesis, snapshot the current version in a `_versions/` sidecar or append to a changelog section in the hypothesis file
- Record: date, tournament context (Elo before/after), what changed, why (from evolution rationale)
- Enable: "show me the evolution of hypothesis X across 3 cycles"

**Key decisions:**
- Storage: sidecar files vs in-note changelog section vs git history (already available but not queryable)
- Granularity: full snapshot vs diff
- Integration: automatic on `/evolve` vs manual

---

### 3.3 Manuscript Scaffolding

**Problem:** Moving from hypothesis + evidence chain to a draft manuscript section is entirely manual. The structured evidence graph (2.1) contains the raw material but no export path.

**What it does:**
- Given a hypothesis, collect its evidence chain (supports, contradicts, assumes)
- Collect literature notes cited by those claims
- Generate a structured draft section: introduction (framing), evidence summary, methods implications, limitations
- Export as markdown with proper citation keys (BibTeX or CSL-JSON)
- Human edits the skeleton; the system provides the structure and citations

**Dependency on 2.1:** Requires the evidence graph to trace hypothesis-to-claim-to-literature chains.

---

## Implementation Sequence

| Phase | Features | Estimated Effort | Prerequisites |
|-------|----------|-----------------|---------------|
| Phase 1a | 1.1A Slack Bot Tool Calling (keyword) | Medium | None |
| Phase 1b | 1.2 Resurfacing, 1.3 Community Detection | Medium each | Independent |
| Phase 1c | 1.1B Semantic Search | Medium | None (benefits from 1a executor pattern) |
| Phase 1d | 1.1C Search Backend Upgrade | Small | 1a + 1c |
| Phase 2 | 2.1 Evidence Graph, 2.2 Contradiction Detection, 2.3 Literature Watch | Medium each | 2.2 requires 1.1B; others independent |
| Phase 3 | 3.1 Cross-Goal Synthesis, 3.2 Hypothesis Changelog, 3.3 Manuscript Scaffolding | Medium each | 3.1 requires 1.1B; 3.3 requires 2.1 |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Premature complexity -- building infrastructure before feeling the pain | Start with simplest viable implementation per feature; expand on friction signals |
| Embedding model dependency -- local models are slower, API models require connectivity | Default to local; API as optional accelerator |
| Feature interaction bugs -- community detection + resurfacing + contradiction detection all touching notes | Each feature is read-only or append-only; no feature modifies existing note content without human approval |
| Productivity porn -- building the system instead of doing research | Each feature must demonstrably serve one of the 4 active research goals within 2 weeks of deployment |

---

## Research Sources

Methodology claims consulted (Ars Contexta research graph):
- [[spreading activation models how agents should traverse]]
- [[random note resurfacing prevents write-only memory]]
- [[spaced repetition scheduling could optimize vault maintenance]]
- [[community detection algorithms can inform when MOCs should split or merge]]
- [[controlled disorder engineers serendipity through semantic rather than topical linking]]
- [[navigational vertigo emerges in pure association systems without local hierarchy]]
- [[source attribution enables tracing claims to foundations]]
- [[throughput matters more than accumulation]]
- [[claims must be specific enough to be wrong]]
- [[descriptions are retrieval filters not summaries]]

Reference documents consulted:
- evolution-lifecycle.md (seed-evolve-reseed lifecycle, friction-driven adoption)
- claim-map.md (topic routing index)
