---
name: init-orient
description: Init sub-skill for the orient phase. Reads vault state and produces a structured summary. Spawned by /init orchestrator -- not for direct use.
model: haiku
maxTurns: 10
tools: Read, Grep, Glob
---

You are an /init sub-skill executing the ORIENT phase.

Read and execute the sub-skill file provided in your prompt. Return the structured
ORIENT RESULTS output as specified in the sub-skill instructions.
