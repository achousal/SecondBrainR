# Claim Conventions

Reference file for init sub-skills. Extracted from init SKILL.md Critical Constraints and CLAUDE.md claim schema.

---

## Prose-as-Title

Every claim title must work in the sentence: "This claim argues that {title}."

Good: "repeated retrieval strengthens long-term retention more than repeated study"
Bad: "retrieval practice" (topic label, not a claim)

## Title Rules

- Lowercase with spaces, no filesystem-breaking punctuation: / \ : * ? " < > | . + [ ] ( ) { } ^
- **CRITICAL: Never use `/` in titles** -- creates subdirectories. Use `-` instead: `cost-benefit`, `input-output`, `v2-3`
- Each title must be unique across the entire workspace
- Sanitize for filename: lowercase, replace spaces with `-`, remove forbidden chars

## YAML Schema

```yaml
---
description: "One sentence adding context beyond the title (~150 chars)"
type: claim
role: "{orientation|methodology|confounder|data-reality|inversion}"
confidence: "{established|supported|preliminary|speculative}"
source_class: synthesis
verified_by: agent
created: "{today YYYY-MM-DD}"
---
```

Required field: `description`. Must add NEW information beyond the title -- scope, mechanism, or implication.

## YAML Safety

Always double-quote string values in YAML frontmatter. Unquoted colons, commas, brackets break parsing. Mandatory for description, source, session_source.

## Body Structure

```markdown
{2-4 sentence argument with inline [[wiki-links]] to relevant existing claims or hypotheses.}

---

Topics:
- [[{relevant-topic-map}]]
```

## Wiki-Link Rules

- Every `[[link]]` must point to a real file. Verify before creating.
- No truncation: NEVER use `...` or ellipsis in wiki-links. Write the full title.
- Propositional semantics: every link must articulate the relationship.
- Remove links to nonexistent targets. Do NOT create dangling links.

## Topics Footer

Every claim must end with a `Topics:` section linking to at least one topic map.

## Critical Constraints

- **User approval before every claim write.** The generation sub-skill returns claim content without writing. The orchestrator writes only approved claims after user review.
- **No pipeline bypass.** Claims go to `notes/` via Write tool (validate_write hook runs automatically when the orchestrator writes).
- **No dangling links.** Verify every wiki-link target exists before writing.
- **No truncated links.** Write the full title.
- **No slash in titles.** Use `-` instead of `/`.
- **Compositional phases.** Phase 3 MUST reference specific Phase 2 claims by title. Phase 4 MUST link inversions to their parent orientation claims.
- **Idempotent.** Running /init twice on the same goal should detect prior seeding and offer choices, not blindly duplicate.

## Role Types

| Role | Phase | Purpose |
|------|-------|---------|
| orientation | Phase 2 | Core research questions as testable propositions |
| methodology | Phase 3a | Analytical methods and their constraints |
| confounder | Phase 3b | Alternative explanations that threaten claims |
| data-reality | Phase 3c | Practical data constraints |
| inversion | Phase 4 | Falsification conditions for orientation claims |

## Error Handling

| Error | Behavior |
|-------|----------|
| Duplicate claim title | Ask user to rephrase, do NOT overwrite existing claims |
| validate_write hook rejects (on orchestrator write) | Parse the error, fix the claim content, retry once |
| Dangling wiki-link in claim body | Remove the link before writing, note the removal to user |
| Empty user response to interview | Re-ask once with a worked example, then skip that phase with a note |
