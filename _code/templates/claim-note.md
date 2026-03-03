---
_schema:
  entity_type: "claim-note"
  applies_to: "notes/*.md"
  required:
    - description
  optional:
    - type
    - role
    - source
    - confidence
    - source_class
    - verified_by
    - verified_who
    - verified_date
    - status
    - created
    - modified
  enums:
    type:
      - claim
      - evidence
      - methodology
      - contradiction
      - pattern
      - question
    role:
      - orientation
      - methodology
      - confounder
      - data-reality
      - inversion
    confidence:
      - established
      - supported
      - preliminary
      - speculative
    source_class:
      - empirical
      - published
      - preprint
      - collaborator
      - synthesis
      - hypothesis
    verified_by:
      - human
      - agent
      - unverified
    status:
      - preliminary
      - active
      - archived
  constraints:
    description:
      max_length: 200
      format: "One sentence adding context beyond the title -- scope, mechanism, or implication"
    topics:
      format: "Array of wiki links to topic maps"

# Template fields
description: ""
type: claim
source: ""
confidence: preliminary
source_class: synthesis
verified_by: agent
verified_who: null
verified_date: null
created: YYYY-MM-DD
---

# {prose-as-title: a complete claim that works in sentences}

{Content: the argument supporting this claim. Show reasoning, cite evidence, link to related claims inline.}

---

Relevant Claims:
- [[related claim]] -- relationship context

Topics:
- [[relevant-topic-map]]
