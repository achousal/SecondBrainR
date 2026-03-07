---
description: "Hub page for the vault user manual -- links to all reference pages"
type: manual
created: 2026-02-21
updated: 2026-03-07
---

# User Manual

This manual documents the operation of a research knowledge system built on two complementary layers:

- **Arscontexta layer** -- general knowledge processing: claim extraction, connection-finding, maintenance, quality gates.
- **Co-scientist layer** -- hypothesis generation, tournament ranking, literature search, experimental design.

Both layers share the same three-space architecture (self/, notes/, ops/) and wiki-link graph. Claims in notes/ are the substrate that hypotheses in _research/hypotheses/ build upon.

---

## Reading Order

Start here, then branch based on what you need.

```
Getting Started (first session, claims, session rhythm)
    |
    +-- Skills Reference (command reference for all skills)
    |       |
    |       +-- Workflows (pipeline, co-scientist loop, batch processing)
    |
    +-- Architecture (knowledge layer, hypothesis layer, Elo system)
    |
    +-- Configuration (ops/config.yaml, dimensions, domain profiles)
```

From there, pick what applies:

| Need | Page |
| --- | --- |
| Search PubMed, arXiv, Semantic Scholar | [Literature Search](literature.md) |
| Publication-quality figures | [Plot System](plotting.md) |
| Slack, Obsidian, MCP servers, daemon | [Integrations](integrations.md) |
| Autonomous daemon, hooks, scripts | [Administration](administration.md) |
| Multi-lab federation | [Inter-Lab Collaboration](inter-lab.md) |
| Write validation, tamper detection, PII | [Security and Integrity](security.md) |
| ripgrep query patterns | [Querying](querying.md) |
| /ask, /architect, /rethink, /remember | [Meta-Skills](meta-skills.md) |
| Diagnosing problems | [Troubleshooting](troubleshooting.md) |

---

## All Pages

### Core -- the 5 pages everyone reads

These form a dependency chain. Read them roughly in order.

- **[Getting Started](getting-started.md)** -- First session guide. Onboarding, session rhythm, creating and connecting claims.
- **[Skills Reference](skills.md)** -- Complete command reference, grouped by category. Invocation syntax, arguments, vault I/O.
- **[Workflows](workflows.md)** -- Processing pipeline, co-scientist loop, session rhythm, maintenance cycle, batch processing.
- **[Architecture](architecture.md)** -- Knowledge layer, hypothesis layer, Elo rating system, entity lifecycles, federated Elo.
- **[Configuration](configuration.md)** -- ops/config.yaml structure, dimension semantics, processing modes, domain profiles, /architect.

### Reference -- standalone deep-dives

No reading order between them. Pull one off the shelf when you need it.

- **[Literature Search](literature.md)** -- Search backends (PubMed, arXiv, Semantic Scholar, OpenAlex), enrichment pipeline, unified interface.
- **[Plot System](plotting.md)** -- Visual identity, statistical decision tree, 8 plot builders, semantic palettes, figure sizes.
- **[Querying](querying.md)** -- YAML frontmatter query patterns using ripgrep. Field-level, cross-field, backlink, and audit queries.
- **[Meta-Skills](meta-skills.md)** -- Introspective commands: /ask, /architect, /rethink, /remember. The self-evolution cycle.

### Operations -- running the system in production

These assume you have read the core tier.

- **[Integrations](integrations.md)** -- Slack, Obsidian, MCP servers, research daemon, multi-vault. Setup and configuration.
- **[Administration](administration.md)** -- Research loop daemon, hooks, decision engine, code section health, helper scripts.
- **[Security and Integrity](security.md)** -- Write-time validation (8 gates), tamper detection (SHA-256), PII filtering, escalation ceilings.
- **[Inter-Lab Collaboration](inter-lab.md)** -- Federation, multi-vault operations, trust model, cross-lab claim exchange.
- **[Troubleshooting](troubleshooting.md)** -- Diagnosis and resolution for orphan claims, dangling links, stale content, schema violations.

---

## System Overview

### Three-Space Architecture

| Space | Directory | Purpose |
|-------|-----------|---------|
| Identity | self/ | Agent identity, epistemic stance, goals, methodology |
| Notes | notes/, _research/ | Research content -- claims, hypotheses, literature, experiments |
| Operational | ops/ | Config, sessions, observations, tensions, queue |

### Processing Layers

| Layer | Entry Point | Pipeline | State |
|-------|-------------|----------|-------|
| Arscontexta | inbox/ | capture - reduce - reflect - reweave - verify | notes/, ops/queue/ |
| Co-scientist | /research | generate - review - tournament - evolve - meta-review | _research/ |

### Session Lifecycle

Every session follows orient - work - persist. Hooks fire automatically at session boundaries. See [Workflows](workflows.md) for full details.

### Maintenance Model

Condition-based, not calendar-based. Triggers fire when thresholds are met (orphan claims, 10+ observations, 5+ tensions, inbox items older than 3 days). See [Troubleshooting](troubleshooting.md) for the full condition table.

---

## Conventions

- **Claim** -- an atomic knowledge note in notes/, titled as a prose proposition.
- **Topic map** -- a navigation hub that organizes claims by topic.
- **Wiki link** -- `[[claim title]]` syntax used to connect claims.
- Slash commands use bare names (e.g., /reduce, /research) -- no prefix needed.
- File paths are relative to the vault root unless stated otherwise.
