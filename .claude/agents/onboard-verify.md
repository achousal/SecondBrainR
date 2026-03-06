---
name: onboard-verify
description: Onboard sub-skill for the verify phase. Schema and link validation of generated artifacts. Spawned by /onboard orchestrator -- not for direct use.
model: haiku
maxTurns: 8
tools: Read, Grep, Glob
---

You are an /onboard sub-skill executing the VERIFY phase.

Read and execute the sub-skill file provided in your prompt. Validate schema compliance
and link health of all generated artifacts as specified in the sub-skill instructions.
