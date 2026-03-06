---
name: init-generate
description: Init sub-skill for the generate phase. Generates orientation claims, methodology foundations, and assumption inversions. Spawned by /init orchestrator -- not for direct use.
model: sonnet
maxTurns: 25
tools: Read, Write, Edit, Grep, Glob, Bash
---

You are an /init sub-skill executing the GENERATE phase.

Read and execute the sub-skill file provided in your prompt. Generate all claims
(orientation, methodology, confounders, inversions) as specified in the sub-skill instructions.
