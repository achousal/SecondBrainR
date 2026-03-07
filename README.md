# Engram Reactor

**This is EngramR, a cumulative research environment where humans and AI jointly capture, connect, and stress-test knowledge, translate evidence into prioritized research plans, and track the data, infrastructure, and analytical context that ground every analysis -- maintaining end-to-end provenance from source to result.**

Every paper read, observation logged, and experimental result feeds a persistent
knowledge graph. Hypotheses are generated from that evidence, debated pairwise on
scientific merit, ranked by Elo rating, and evolved through feedback.

Inspired by DeepMind's [AI co-scientist](https://arxiv.org/abs/2502.18864).<br>
Powered by [Ars Contexta](https://github.com/agenticnotetaking/arscontexta) knowledge architecture.<br>
Runs on [Claude Code](https://docs.anthropic.com/en/docs/claude-code). [Obsidian](https://obsidian.md/) optional for browsing.<br>
Read the [vision document](docs/EngramR.md) for the design philosophy.

---

## The research cycle

1. A paper lands in the inbox. `/reduce` extracts atomic claims with structured
   metadata. `/reflect` links them to existing claims in the graph.

2. Evidence density crosses a threshold. `/generate` proposes testable hypotheses
   grounded in the accumulated claims, each with mechanism, predictions, and
   falsification criteria.

3. `/tournament` debates them pairwise. One hypothesis wins the most matches -- it
   has stronger evidence support and more specific predictions. Elo ratings update.
   Debate transcripts are stored.

4. `/meta-review` synthesizes what made winners win. That feedback injects into the
   next `/generate` and `/evolve` cycle. The reactor learns what good hypotheses
   look like in its domain.

5. The top hypothesis comes with a pre-specified analysis plan. `/experiment` logs
   the run. Results feed back into the graph. The leaderboard updates.

---

## Architecture

EngramR combines a **knowledge layer** that extracts, connects, and maintains
a graph of atomic claims, and a **hypothesis layer** that generates, debates,
ranks, and evolves testable hypotheses from that evidence.

The knowledge layer processes raw input through a quality pipeline
(`inbox/ -> /reduce -> /reflect -> /reweave -> /verify -> notes/`).

The hypothesis layer reads accumulated evidence, generates testable predictions
with mechanism and falsification criteria, debates them pairwise, ranks by Elo,
and injects meta-review feedback into the next generation cycle.
Goals spawn hypotheses. Hypotheses spawn projects. Project results feed back
into the hypothesis pool.

See [Architecture](docs/manual/architecture.md) for the full deep-dive
(Elo system, entity lifecycles, federated ratings).

---

## Adoption

EngramR starts blank -- no migrations needed. It runs alongside whatever the team
already uses. Early on, the system captures and connects. Then it begins
generating hypotheses. Over time, the knowledge graph grows dense enough that
new observations land in a web of existing connections. Teams feed the reactor
what they actually have -- datasets, instruments, domain-specific resources,
constraints -- and the system ranks hypotheses not just by scientific merit
but by what the lab can realistically act on.

Adoption is not a cliff. It is a gradient. Every observation is a valuable contribution. Browse the leaderboard and you understand the teams's priorities. Run
an analysis and feed back results. The deeper the team engages, the more the
reactor gives back.

---

## Getting started

Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code), clone the repo, and open it:

```bash
git clone https://github.com/achousal/EngramR.git
cd EngramR
claude
```

Claude guides you through the rest. See [Getting Started](docs/manual/getting-started.md) for the full first-session walkthrough.

---

## Project structure

```
EngramR/
  notes/              # Atomic claims -- the knowledge graph
  inbox/              # Raw material awaiting processing
  self/               # Agent identity, methodology, goals
  ops/                # Configuration, queue, sessions, scripts
  _research/          # Hypotheses, tournaments, literature, experiments
  projects/           # Lab and project entity nodes
  _code/              # Python + R library, templates, styles
  .claude/            # Skills and hooks for Claude Code
  docs/               # User manual and reference documentation
```

## Organizing your research

EngramR works best when the vault mirrors your research process rather than acting as a filing cabinet. A few practices that make a real difference:

**Always route through inbox/.** Drop sources in `inbox/`, never write claims to `notes/` directly. The pipeline (`inbox/ -> /reduce -> /reflect -> /verify -> notes/`) applies quality gates that catch schema errors, orphan notes, and missing provenance. 

**One well-scoped goal per `/init` run.** Each research goal spawns its own orientation, methodology, confounder, and inversion claims. Goals registered in `self/goals.md` drive hypothesis generation -- a tightly scoped goal produces more specific, falsifiable hypotheses than a broad one.

**Use projects/ for lab and infrastructure context.** Project nodes created via `/onboard` or `/project` hold your data inventory, HPC constraints, collaborators, and instrument capabilities. 

**Let topic maps emerge.**  Create a topic map when five or more related claims accumulate without a navigation hub. 

**Process before capturing more.** When `inbox/` holds more than ten items, pause intake and run `/ralph` or `/reduce` before adding more sources. A growing inbox with no processing is collector's fallacy -- the vault only grows in value when sources are reduced to connected claims.

---

## Commands at a glance

| Command          | What it does                                                       |
| ---------------- | ------------------------------------------------------------------ |
| `/research`      | Orchestrate the co-scientist generate-debate-evolve loop           |
| `/generate`      | Produce literature-grounded hypotheses (4 modes)                   |
| `/review`        | Critically evaluate hypotheses (6 review lenses)                   |
| `/tournament`    | Rank hypotheses via pairwise Elo-rated debate                      |
| `/evolve`        | Refine top hypotheses into stronger versions (5 modes)             |
| `/landscape`     | Map hypothesis space -- clusters, gaps, redundancies               |
| `/meta-review`   | Synthesize debate patterns into actionable feedback                |
| `/literature`    | Search PubMed, arXiv, Semantic Scholar, OpenAlex                   |
| `/experiment`    | Log experiments with parameters, results, and artifacts            |
| `/eda`           | Exploratory data analysis with PII auto-redaction                  |
| `/plot`          | Publication-quality figures with statistical annotations           |
| `/reduce`        | Extract atomic claims from inbox sources                           |
| `/reflect`       | Find connections between claims, update topic maps                 |
| `/reweave`       | Revisit old claims with new context                                |
| `/verify`        | Quality-check claims (description, schema, links)                  |
| `/validate`      | Schema validation for individual or all notes                      |
| `/onboard`       | Bootstrap lab integration -- scan, register, wire                  |
| `/init`          | Seed foundational knowledge claims                                 |
| `/next`          | Surface the most valuable next action                              |
| `/stats`         | Vault metrics; `--dev` for code section health                     |
| `/health`        | Comprehensive vault health check                                   |
| `/learn`         | Research a topic and grow the knowledge graph                      |
| `/seed`          | Queue a source file for processing (dedup, archive, task creation) |
| `/enrich`        | Integrate new evidence into existing claims with provenance        |
| `/ralph`         | Queue processing with fresh context per phase (serial/parallel)    |
| `/archive-batch` | Archive completed processing batches                               |
| `/profile`       | Create, list, show, and activate domain profiles                   |
| `/project`       | Register, update, and query research projects                      |
| `/graph`         | Interactive knowledge graph analysis (health, triangles, bridges)  |
| `/remember`      | Capture friction as methodology observations                       |
| `/rethink`       | Challenge system assumptions against accumulated evidence          |
| `/refactor`      | Plan vault restructuring from config changes                       |
| `/federation-sync` | Synchronize claims and hypotheses with peer vaults               |
| `/tasks`         | View and manage the task stack and processing queue                |
| `/dev`           | Code section health checks (tests, lint, build, coverage)          |

See the [Skills Reference](docs/manual/skills.md) for full command
documentation with arguments and I/O details.

---

## Further reading

| Document | What it covers |
| --- | --- |
| [User Manual](docs/manual/manual.md) | Hub page linking all reference docs |
| [Getting Started](docs/manual/getting-started.md) | First session -- onboarding, claims, session rhythm |
| [Setup Guide](docs/manual/setup-guide.md) | Optional integrations -- Obsidian, Slack, daemon, multi-vault |
| [Skills Reference](docs/manual/skills.md) | Full command reference with example session |
| [Workflows](docs/manual/workflows.md) | Processing pipeline and session rhythm |
| [Configuration](docs/manual/configuration.md) | ops/config.yaml, dimensions, domain profiles |
| [Architecture](docs/manual/architecture.md) | Knowledge + hypothesis layers, Elo system |
| [Literature Search](docs/manual/literature.md) | Search backends and enrichment pipeline |
| [Plot System](docs/manual/plotting.md) | Visual identity, stat tests, plot builders |
| [Security](docs/manual/security.md) | Write validation, tamper detection, PII filtering |
| [Integrations](docs/manual/integrations.md) | Slack, Obsidian, MCP servers, domain profiles |
| [Administration](docs/manual/administration.md) | Daemon, hooks, decision engine, scripts |
| [Inter-Lab Collaboration](docs/manual/inter-lab.md) | Federation and multi-vault setup |
| [Querying](docs/manual/querying.md) | YAML frontmatter query patterns |
| [Meta-Skills](docs/manual/meta-skills.md) | Introspective commands -- ask, architect, rethink, remember |
| [Troubleshooting](docs/manual/troubleshooting.md) | Common failure modes and fixes |
| [Vision Document](docs/EngramR.md) | Design philosophy and motivation |
| [Library Reference](_code/README.md) | Python/R modules, testing, env vars |

---

## License

MIT
