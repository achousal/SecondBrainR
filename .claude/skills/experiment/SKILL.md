---
name: experiment
description: Log experiments with parameters, results, and artifacts
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
  - Write
---

# /experiment -- Experiment Logging

Log experiments with parameters, results, and artifacts linked to hypotheses.

## Code location
- `_code/src/engram_r/note_builder.py` -- `build_experiment_note()`
- `_code/src/engram_r/obsidian_client.py` -- Obsidian REST API

## Vault paths
- Experiment notes: `_research/experiments/`
- Template: `_code/templates/experiment.md`
- Index: `_research/experiments/_index.md`

## Workflow
1. Ask the user for:
   - Experiment title
   - Linked hypothesis (if any) -- wiki-link like `[[hyp-20260221-001]]`
   - Objective
   - Parameters (as key-value pairs)
   - Random seed (if applicable)
2. Build experiment note using `build_experiment_note()`.
3. Save to `_research/experiments/{date}-{slug}.md`.
4. If a hypothesis is linked, update the hypothesis note's `linked_experiments` frontmatter field.
5. Update `_research/experiments/_index.md` under "Active Experiments".
6. Present the saved note path to the user.

## After running an experiment
When the user reports results:
1. Read the existing experiment note.
2. Update the "Results" section with findings.
3. Update the "Artifacts" section with paths to output files.
4. Update the "Interpretation" section.
5. Set status to "completed" in frontmatter.
6. Ask user about "Next Steps".

## Run metadata to record
- Parameters dict
- Random seed
- Code version (git commit hash if available)
- Environment info (Python version, key package versions)
- Timestamp
- Computational resources (if relevant)

## Project scoping
If the linked hypothesis has a `project_tag` in its tags, inherit it into the experiment note tags. This enables filtering experiments by project across the vault.

## Rules
- Always include a random seed when RNG is used.
- Always link back to the hypothesis being tested.
- Record enough metadata for reproducibility.
- Use the canonical note template structure.

## Skill Graph
Invoked by: user (standalone)
Invokes: (none -- leaf agent)
Reads: _research/hypotheses/ (linked hypothesis)
Writes: _research/experiments/, _research/experiments/_index.md, _research/hypotheses/ (frontmatter: linked_experiments)

## Rationale
Experimental design and provenance logging -- structured recording of tests and results. Links experimental evidence back to hypotheses for empirical validation.
