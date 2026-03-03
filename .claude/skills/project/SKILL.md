---
name: project
description: Register, update, and query research projects in the vault
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
  - Write
---

# /project -- Project Registry Management

Register, update, and query research projects in the EngramR vault.

## Architecture
Manages project notes in `projects/` and the project index. Uses `build_project_note()` from `note_builder.py`.

## Vault paths
- Project notes: `projects/`
- Index: `projects/_index.md`
- Template: `_code/templates/project.md`
- Vault root: repository root (detected automatically)

## Code
- `_code/src/engram_r/note_builder.py` -- `build_project_note()`
- `_code/src/engram_r/obsidian_client.py` -- vault I/O

## Capabilities

### Register a new project
1. Ask user for: title, project_tag (slug), lab, PI, project_path, language(s), HPC path (if any).
2. If `CLAUDE.md` exists at `project_path`, read it to auto-populate description, language, and infrastructure flags.
3. Detect infrastructure:
   - `has_claude_md`: check `{project_path}/CLAUDE.md`
   - `has_git`: check `{project_path}/.git/`
   - `has_tests`: check for `tests/`, `analysis/tests/`, or language-specific test dirs
4. Build note using `build_project_note()`.
5. Present to user for review.
6. Save to `projects/{project_tag}.md`.
7. Update `projects/_index.md` -- add row to appropriate status table.
8. Create vault bridge symlink:
   - `ln -sfn {project_path} {vault_root}/_dev/{project_tag}`
   - This makes the project browsable/searchable from Obsidian.

### Update an existing project
1. Ask user which project and which fields to update.
2. Read existing project note from `projects/{project_tag}.md`.
3. Update specified frontmatter fields.
4. If `project_path` changed, recreate the `_dev/` symlink:
   - `rm -f {vault_root}/_dev/{project_tag} && ln -sfn {new_path} {vault_root}/_dev/{project_tag}`
5. Append to Status Log: `- {date}: {change summary}`.
6. Present diff to user before saving.
7. Update `projects/_index.md` if status changed.

### List all projects
1. Read `projects/_index.md`.
2. Display the table, optionally filtered by lab, status, or language.

### Link project to research goal
1. Ask user for project_tag and research goal wiki-link.
2. Read project note, add goal to `linked_goals` list.
3. Read research goal note, add `project_tag` to its tags if not present.
4. Save both notes (bidirectional link).
5. Append to Status Log: `- {date}: Linked to {goal}`.

## Frontmatter schema
```yaml
type: project
title: ""
project_tag: ""
lab: ""
pi: ""
status: active          # active | maintenance | archived
project_path: ""
language: []
hpc_path: ""
scheduler: LSF
linked_goals: []
linked_hypotheses: []
linked_experiments: []
has_claude_md: false
has_git: false
has_tests: false
scan_dirs: []              # Whitelisted dirs for /onboard doc discovery (set by onboard)
scan_exclude: []           # Per-project exclude patterns merged with global onboard config
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [project]
```

## Status values
- `active` -- under active development or analysis
- `maintenance` -- stable, occasional updates
- `archived` -- completed or abandoned

## Rules
- Always present notes for user approval before saving.
- Auto-detect infrastructure flags when registering (read from filesystem).
- Keep `projects/_index.md` in sync with individual project notes.
- Use `build_project_note()` for new notes -- do not manually construct frontmatter.
- Bidirectional links: when linking a project to a goal, update both notes.

## Skill Graph
Invoked by: user (standalone)
Invokes: (none -- leaf agent)
Reads: projects/, projects/_index.md, filesystem (project detection)
Writes: projects/, projects/_index.md

## Rationale
Research infrastructure management -- tracks project context, infrastructure state, and cross-references to research goals. Ensures the vault stays connected to the actual codebase and HPC environments.
