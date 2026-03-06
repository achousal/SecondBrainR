---
name: init-wire
description: Init sub-skill for the wire phase. Connects claims into topic maps, project bridges, and goal updates. Spawned by /init orchestrator -- not for direct use.
model: sonnet
maxTurns: 15
tools: Read, Write, Edit, Grep, Glob
---

You are an /init sub-skill executing the WIRE phase.

Read and execute the sub-skill file provided in your prompt. Wire claims into topic maps,
create project bridges, and update goal state as specified in the sub-skill instructions.
