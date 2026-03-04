---
_schema:
  entity_type: "topic-map"
  applies_to: "notes/*.md"
  required:
    - description
    - type
  optional:
    - created
  enums:
    type:
      - moc
  constraints:
    description:
      max_length: 200
      format: "One sentence describing the scope and purpose of this topic map"

# Template fields
description: ""
type: moc
created: YYYY-MM-DD
---

# {topic name}

Brief orientation -- 2-3 sentences explaining what this topic covers and how to use this map.

## Core Ideas
- [[claim]] -- context explaining why this matters here

## Tensions
Unresolved conflicts -- intellectual work, not bugs. What questions remain open?

## Open Questions
What is unexplored. Research directions, gaps, areas needing attention.
