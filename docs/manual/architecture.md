---
description: "Architecture deep-dive -- knowledge layer, hypothesis layer, Elo system, entity lifecycles"
type: manual
created: 2026-03-01
---

# Architecture

EngramR combines a **knowledge layer** that extracts, connects, and maintains
a graph of atomic claims, and a **hypothesis layer** that generates, debates,
ranks, and evolves testable hypotheses from that evidence.

---

## Knowledge layer

When a lab sets up EngramR, [Ars Contexta](https://github.com/agenticnotetaking/arscontexta)
derives the knowledge system -- folder structure, topic maps, analysis
standards -- from a conversation about the lab's research domains and working
style. Each insight becomes an atomic claim: a single note
with structured metadata and wiki-link edges to related claims. The result is a
knowledge graph built from plain markdown that any team member can browse.

The vault is organized around three primitives:

| Primitive    | What it provides                                                                                                             |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| **Scope**    | Domain boundaries -- research areas, epistemic stance, inclusion and exclusion criteria                                      |
| **Contexts** | Three-space architecture: `self/` (identity, methodology, goals), `notes/` (atomic claims), `ops/` (config, queue, sessions) |
| **Texts**    | Atomic claims -- single-insight notes titled as prose propositions, linked by wiki-link edges into a graph                   |

Topic maps organize claim clusters into navigable neighborhoods -- attention
hubs that make the graph browsable without search. Raw input enters through
a quality pipeline that enforces structure before anything reaches the graph
(see [Workflows](workflows.md) for the full pipeline).

---

## Hypothesis layer

The hypothesis layer reads the accumulated evidence and generates testable
predictions -- each with mechanism, falsification criteria, and a pre-specified
analysis plan. Pairwise debates evaluate novelty, plausibility, testability,
and impact. Elo ratings rank the leaderboard. Meta-reviews extract what made
winners win and inject that feedback into the next generation. Because
hypotheses are themselves notes in the graph, experimental results become
new claims that feed future cycles.

```
/research --> /generate --> /review --> /tournament --> /meta-review
                                                           |
              (feedback feeds back into)                   |
              /generate, /review, /evolve <---------------+
```

### Entity lifecycles

Goals spawn hypotheses. Hypotheses spawn projects. Project results feed back
into the hypothesis pool, reshaping the leaderboard.

|                 | Goal                         | Hypothesis                          | Project                             |
| --------------- | ---------------------------- | ----------------------------------- | ----------------------------------- |
| **Definition**  | Open-ended research question | Testable prediction with mechanism  | Concrete work with defined scope    |
| **Lifecycle**   | Evolves as the lab learns    | Generated, debated, ranked, evolved | Has timeline, budget, deliverables  |
| **Elo applies** | Organizes the leaderboard    | Yes -- compete head-to-head         | No -- projects execute, not compete |

A goal like "Identify early indicators of system degradation" spawns
hypotheses like "Initial variability predicts six-month trend," which
spawns a project to run that analysis on a specific dataset.

---

## Elo rating system

Standard Elo with K=32 for tournament debates. The expected score formula
(`1 / (1 + 10^((elo_b - elo_a) / 400))`) drives zero-sum rating transfers
between debate opponents. Matchup generation prioritizes under-matched
hypotheses and pairs by Elo proximity.

Experimental outcomes also adjust Elo via `apply_empirical_elo()` -- the
hypothesis "plays against reality" at K=16 (half the tournament K, reflecting
lower confidence from a single experiment vs. a multi-round debate). This is
intentionally not zero-sum: empirical evidence injects external information
into the rating system.

Hypotheses that reach empirical resolution (`tested-positive`, `tested-negative`,
`tested-partial`, `analytically-blocked`) retain their Elo for display but are
excluded from future matchups.

### Federated Elo

Each hypothesis carries two independent Elo ratings:

| Field | Updated by | Purpose |
|-------|-----------|---------|
| `elo` | Local `/tournament` | Ranking within this vault |
| `elo_federated` | `/tournament --federated` | Ranking across vaults |

When a local hypothesis first enters a federated match, `elo_federated`
initializes to its current `elo`. Foreign hypotheses start at 1200
(configurable). The two tracks never interfere -- a hypothesis can rank #1
locally and #5 in federated competition.

---

## See Also

- [Skills Reference](skills.md) -- full command reference and example session
- [Configuration](configuration.md) -- dimension settings that shape behavior
- [Inter-Lab Collaboration](inter-lab.md) -- federation and multi-vault setup
