---
description: "Security and integrity -- write-time validation, tamper detection, PII filtering, escalation ceilings"
type: manual
created: 2026-03-01
---

# Security and Integrity

Three defense-in-depth layers protect vault integrity, agent behavior, and
research data.

---

## Layer 1: Write-time prevention (validate_write.py)

A synchronous Claude Code hook that runs on every Write and Edit operation.
Blocks the write before it happens. Gate checks in order:

1. **Identity protection** -- blocks writes to protected files (`self/identity.md`,
   `self/methodology.md`, `ops/config.yaml`, `ops/daemon-config.yaml`,
   `ops/methodology/_compiled.md`, `CLAUDE.md`) unless the env var
   `ENGRAMR_IDENTITY_UNLOCK=1` is set. Warns (does not block) on writes to
   `ops/methodology/` source files.
2. **Flat directory enforcement** -- blocks filenames containing `/` in flat
   directories (`notes/`, `hypotheses/`, `literature/`, `experiments/`,
   `landscape/`) to prevent accidental subdirectory creation.
3. **Unsafe filename characters** -- blocks `: * ? " < > |` and non-NFC
   Unicode in filenames.
4. **YAML safety** -- detects unquoted colon-space sequences and hash-start
   values in frontmatter (both cause silent YAML misparsing).
5. **Unicode normalization** -- blocks non-NFC characters in frontmatter.
6. **Truncated wiki links** -- blocks `[[some title...]]` patterns that
   indicate an abbreviated link (violates graph invariants).
7. **Schema validation** -- checks required frontmatter fields per note type
   (12 known types with defined schemas).
8. **Pipeline provenance** -- blocks notes in `notes/` without a `description`
   field; warns on missing `source` for claim-type notes.

### Enforced schemas

12 note types with required fields:

| Type | Required fields |
| --- | --- |
| `hypothesis` | title, id, status, elo, created, updated |
| `foreign-hypothesis` | title, id, status, elo_federated, elo_source, matches_federated, matches_source, source_vault, imported |
| `literature` | title, status, created |
| `experiment` | title, status, created |
| `eda-report` | title, dataset, created |
| `research-goal` | title, status, created |
| `tournament-match` | date, research_goal, hypothesis_a, hypothesis_b |
| `meta-review` | date, research_goal |
| `project` | title, project_tag, lab, status, project_path, created, updated |
| `lab` | lab_slug, pi, created, updated |
| `institution` | name, slug, created, updated |
| `claim` / `evidence` / `methodology` / `contradiction` / `pattern` / `question` | description |

All claims also track epistemic provenance: `confidence` (established / supported / preliminary / speculative), `source_class` (empirical / published / preprint / collaborator / synthesis / hypothesis), `verified_by` (human / agent / unverified).

---

## Layer 2: Tamper detection (integrity.py)

SHA-256 manifest of files that shape agent behavior. Designed specifically
against the prompt injection attack vector where an adversary edits an agent's
memory files between sessions (per [arXiv:2602.20021v1](https://arxiv.org/abs/2602.20021v1),
Case 10).

```bash
cd _code
uv run python -m engram_r.integrity --vault .. seal     # snapshot hashes
uv run python -m engram_r.integrity --vault .. verify   # detect drift
uv run python -m engram_r.integrity --vault .. status   # show state
```

Protected files: `self/identity.md`, `self/methodology.md`, `ops/config.yaml`,
`ops/daemon-config.yaml`, `ops/methodology/_compiled.md`, `CLAUDE.md`.
Monitored directories: `ops/methodology/*.md`.

The `session_orient.py` hook runs `verify_manifest()` at every session start
and surfaces any drift immediately.

---

## Layer 3: PII filtering (pii_filter.py)

Prevents accidental export of research subject identifiers at system
boundaries.

**DataFrame columns** -- regex patterns detect: subject/patient/participant IDs,
SSN, names, DOB, email, phone, address, zip code, sample IDs, record IDs,
bare `id` columns. `auto_redact(df)` replaces flagged column values with
`[REDACTED]` (copy, never mutates in place).

**Free text** -- `redact_text()` / `scrub_outbound()` catches SSN format,
email addresses, and US phone numbers in plain text.

Domain profiles can extend these patterns (e.g., the bioinformatics profile adds
MRN and patient name patterns for biomedical data; a social science profile
might add participant codes). See `pii_patterns.yaml` in each profile.

PII scrubbing is applied automatically:
- Before every Slack notification (`slack_notify.py`)
- On federation exports when `redact_pii_on_export: true` (default)
- During EDA when `redact_pii=True` (default in `load_dataset()`)

---

## Escalation ceilings

Behavioral guardrails that hold regardless of conversational pressure or
social framing:

- Never delete or overwrite files in `self/` (identity, methodology, goals)
- Never disable hooks, schema validation, or pipeline compliance
- Never modify `ops/config.yaml`, `ops/daemon-config.yaml`, or `CLAUDE.md`
  without explicit operator instruction in the current session
- Never widen the daemon's allowed-skill ceiling or lower metabolic thresholds
- Never remove integrity protections
- Never execute destructive shell commands against vault directories without
  per-invocation operator confirmation

Each escalation requires its own confirmation. A single approval does not
generalize.

---

## See Also

- [Administration](administration.md) -- hooks that enforce these layers
- [Configuration](configuration.md) -- schema validation and provenance settings
- [Inter-Lab Collaboration](inter-lab.md) -- federation safety guardrails
