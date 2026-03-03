---
_schema:
  entity_type: "cycle-summary"
  applies_to: "_research/cycles/*.md"
  required:
    - type
    - cycle
    - programs
    - date_range
    - created
  optional:
    - status
  enums:
    type:
      - cycle-summary
    status:
      - active
      - completed
  constraints:
    date_range:
      format: "YYYY-MM-DD to YYYY-MM-DD"

# Template fields
type: cycle-summary
cycle: 0
programs: []
date_range: ""
status: completed
created: YYYY-MM-DD
---

# Cycle {N} Summary

## Overview

{2-3 sentence summary: what this cycle accomplished, what shifted, what remains.}

## By Program

### [[goal-name]]

**Tournament standing:** {top hypothesis, Elo, record}
**Executed:** {experiments run, results}
**Key findings:** {1-3 bullet takeaways}
**Carried forward:** {what persists into next cycle}

## Persistent Blind Spots

{Patterns that recurred across programs -- gatekeeper delay, confounder treatment, cross-program gaps.}

## Cycle Primers for Cycle {N+1}

{Actionable items seeding the next cycle -- inversions to test, confounders to design around, new directions.}

## Infrastructure Changes

{Vault, methodology, or tooling changes made during this cycle.}
