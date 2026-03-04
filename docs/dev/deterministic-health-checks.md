---
description: "Deterministic verify_health.py replaces LLM-dependent /verify for schema, link, and description checks -- eliminates Skill tool intermittence and context degradation"
type: development
status: complete
created: 2026-03-03
updated: 2026-03-03
---

# Deterministic Health Checks

## Motivation

The `/verify` skill bundled two fundamentally different operations:

1. **Deterministic checks** -- schema compliance, YAML safety, wiki-link resolution, description presence, link density, topic-map connection. Identical results regardless of context state.
2. **Semantic checks** -- recite (cold-read description quality). Requires genuine LLM judgment.

Forcing both through the Skill tool meant deterministic checks inherited LLM-path failure modes:

| Problem | Impact |
|---------|--------|
| "Unknown skill" errors after ~6-7 invocations/session | Pipeline runs (30+ tasks) break mid-batch |
| Subagents improvise ad-hoc fallbacks | Inconsistent quality; diverges from SKILL.md gates |
| Context degradation as session progresses | Checks meant to ensure quality run in degraded attention |
| Tokens consumed on procedural reasoning | Template loading, field comparison waste context budget |

The system's quality enforcement was probabilistic when it should have been guaranteed.

## What Was Built

### A. verify_health.py

Deterministic health checks extracted into a Python module. Reuses `schema_validator.py` imports. Config-driven from `ops/config.yaml` health section.

**Checks implemented:**

- Schema validation (required fields, enum values, YAML safety)
- Unicode normalization issues
- Wiki-link resolution (dangling links)
- Description quality heuristics (length, keyword presence)
- Link density (minimum outgoing links)
- Topic-map connection (orphan detection)

**Invocation:**

```bash
# Single note
python -m engram_r.verify_health notes/some-claim.md --vault-root .

# All notes
python -m engram_r.verify_health --all --vault-root .

# JSON output for programmatic consumption
python -m engram_r.verify_health --all --vault-root . --json
```

**Output:** Structured PASS/WARN/FAIL per check, with detail strings. Compact enough to enter context without consuming reasoning budget.

### B. test_verify_health.py

9 test classes covering every public function plus integration and config tests.

### C. Ralph Fallback Protocol

Documents recovery procedure when the Skill tool fails: read `.claude/skills/{phase}/SKILL.md` directly, continue processing. See `ops/methodology/skill-tool-requires-direct-read-fallback.md`.

## Research Justification

The architecture follows three established principles from the Ars Contexta research graph:

### The Determinism Boundary

Operations producing identical results regardless of input content, context state, or reasoning quality belong in infrastructure (hooks/scripts), not skills. Schema validation, link resolution, and format checks are paradigmatic deterministic operations. Recite stays correctly in the skill layer.

*Claim: "the determinism boundary separates hook methodology from skill methodology"*

### Hook Enforcement vs. Instruction Enforcement

Instruction-encoded methodology (including skill invocation) degrades as context fills. The agent may skip the check, the Skill tool may fail, or the subagent may improvise. A Python script fires on every invocation regardless of context state. The enforcement gap closes from "suggestions that degrade" to "infrastructure that guarantees."

*Claim: "hook enforcement guarantees quality while instruction enforcement merely suggests it"*

### Detection Safety

All checks in verify_health.py are pure detection -- they read state and report findings. The worst outcome is a false alert, never content corruption. Safe to run maximally aggressively (every write, every pipeline phase, every batch) with zero risk to vault integrity.

*Claim: "automated detection is always safe because it only reads state while automated remediation risks content corruption"*

## Performance Comparison

| Dimension | Previous (Skill-dependent) | Current (verify_health.py) |
|-----------|---------------------------|---------------------------|
| Reliability | Degrades after ~6-7 invocations; intermittent failures | 100% deterministic; no session-length limit |
| Context cost | Hundreds of tokens per check (template loading, reasoning) | Near-zero (only PASS/FAIL enters context) |
| Pipeline scaling | Breaks at ~30 tasks; subagents improvise | Scales linearly; no invocation ceiling |
| Failure mode | Silent -- agent skips or improvises without flagging | Loud -- structured FAIL with detail |
| Idempotency | Depends on LLM state | Trivially idempotent (same input = same output) |

## Maturity Trajectory

This change represents the final leg of the documentation-to-skill-to-hook trajectory:

1. **Documentation** (done): CLAUDE.md contained schema rules and link requirements
2. **Skill** (done): `/verify` encoded checks as a skill with quality gates
3. **Script/hook** (current): `verify_health.py` extracts the deterministic subset into infrastructure

The semantic checks (recite) remain at the skill level. The deterministic checks were exercised enough through the skill phase to confirm edge cases and false positive rates. Promotion is justified by accumulated evidence.

## Files

| File | Role |
|------|------|
| `_code/src/engram_r/verify_health.py` | Deterministic health check module |
| `_code/tests/test_verify_health.py` | 9 test classes, integration + config coverage |
| `ops/methodology/skill-tool-requires-direct-read-fallback.md` | Fallback protocol documentation |
