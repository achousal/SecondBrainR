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

## Architecture

EngramR combines a **knowledge layer** (claim extraction, connection-finding,
quality gates) and a **hypothesis layer** (generation, pairwise debate, Elo
ranking, meta-review feedback). See [Architecture](docs/manual/architecture.md)
for the full deep-dive.

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
