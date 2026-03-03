---
description: "Hub page for the vault user manual -- links to all reference pages"
type: manual
created: 2026-02-21
---

# User Manual

This manual documents the operation of a research knowledge system built on two complementary layers:

- **Arscontexta layer** -- general knowledge processing: claim extraction, connection-finding, maintenance, quality gates.
- **Co-scientist layer** -- hypothesis generation, tournament ranking, literature search, experimental design.

Both layers share the same three-space architecture (self/, notes/, ops/) and wiki-link graph. Claims in notes/ are the substrate that hypotheses in _research/hypotheses/ build upon.

---

## Manual Pages

### [Getting Started](getting-started.md)
First session guide. Creating your first claim, finding connections, understanding the session rhythm (orient-work-persist), and routing content through the processing pipeline.

### [Skills Reference](skills.md)
Complete command reference for all vault skills, grouped by category. Includes invocation syntax, arguments, and vault I/O for every command.

### [Workflows](workflows.md)
Processing pipeline (capture-reduce-reflect-reweave-verify), maintenance cycle, session rhythm, batch processing, and the co-scientist generate-debate-evolve loop. How the pieces compose into daily and weekly work patterns.

### [Configuration](configuration.md)
Structure and semantics of ops/config.yaml, the derivation manifest, dimension positions, processing depth and chaining modes, and how to use /architect to restructure the system.

### [Meta-Skills](meta-skills.md)
Deep guide to the introspective commands: /ask (query the methodology knowledge base), /architect (restructure system design), /rethink (triage observations and tensions), /remember (capture friction signals).

### [Querying](querying.md)
YAML frontmatter query patterns -- using ripgrep to treat the vault as a database. Field-level, cross-field, backlink, co-scientist, and audit queries with practical examples.

### [Troubleshooting](troubleshooting.md)
Diagnosis and resolution procedures for orphan claims, dangling links, stale content, methodology drift, inbox overflow, schema violations, and other common failure modes.

### [Setup Guide](setup-guide.md)
Installation, environment configuration, dependency setup, and vault initialization for new deployments.

### [Inter-Lab Collaboration](inter-lab.md)
Patterns for federated vaults, cross-lab claim sharing, conflict resolution, and provenance preservation across research groups.

### [Architecture](architecture.md)
Knowledge layer, hypothesis layer, Elo rating system, entity lifecycles (goals, hypotheses, projects), and federated Elo.

### [Literature Search](literature.md)
Search backends (PubMed, arXiv, Semantic Scholar, OpenAlex), enrichment pipeline (CrossRef, Unpaywall), and the unified search interface.

### [Plot System](plotting.md)
Three-tier visual hierarchy, statistical decision tree, 8 plot builders, semantic palettes, and standard figure sizes.

### [Security and Integrity](security.md)
Write-time validation (8 gates), tamper detection (SHA-256 manifest), PII filtering, and escalation ceilings.

### [Integrations](integrations.md)
Slack (notifications, interactive bot, scheduled DMs), Obsidian, MCP servers, and domain profiles.

### [Administration](administration.md)
Research loop daemon (priority cascade, metabolic indicators, model assignment), hooks, decision engine, code section health, and helper scripts.

---

## System Overview

### Three-Space Architecture

| Space | Directory | Purpose |
|-------|-----------|---------|
| Identity | self/ | Agent identity, epistemic stance, goals, methodology |
| Notes | notes/, _research/hypotheses/, _research/literature/, _research/experiments/ | Research content -- the vault's core data |
| Operational | ops/ | Config, sessions, observations, tensions, queue |

### Processing Layers

| Layer | Entry Point | Pipeline | State |
|-------|-------------|----------|-------|
| Arscontexta | inbox/ | capture - reduce - reflect - reweave - verify | notes/, ops/queue/ |
| Co-scientist | /research | generate - review - tournament - evolve - meta-review | _research/hypotheses/, _research/ |

### Session Lifecycle

Every session follows orient - work - persist. Hooks fire automatically at session boundaries: session-orient.sh reads vault state at start; session-capture.sh records the session at end. See [Workflows](workflows.md) for full details.

### Maintenance Model

Condition-based, not calendar-based. Maintenance triggers fire when thresholds are met (orphan claims detected, 10+ pending observations, 5+ pending tensions, inbox items older than 3 days). See [Troubleshooting](troubleshooting.md) for the full condition table.

---

## Conventions Used in This Manual

- **Claim** refers to an atomic knowledge note in notes/, titled as a prose proposition.
- **Topic map** refers to a navigation hub that organizes claims by topic.
- **Wiki link** refers to `[[claim title]]` syntax used to connect claims.
- All slash commands use bare names (e.g., /reduce, /research, /generate) -- no prefix needed.
- All file paths are relative to the vault root unless stated otherwise.
