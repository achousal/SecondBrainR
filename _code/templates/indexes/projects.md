---
type: index
title: Project Registry
tags: [index, project]
---

# Project Registry

Each project note is a **thin metadata shell** with an `![[_dev/.../CLAUDE.md]]` transclusion. The CLAUDE.md in the project repo is the single source of truth -- vault notes never duplicate content that would desync.

## Active Projects

<!-- Register projects here using /project or /onboard. Example:

| Project | PI | Language | HPC | Summary |
|---|---|---|---|---|
| [[my-project]] | Smith | Python | Slurm | Differential expression analysis |
-->

## Maintenance

_None_

## Archived

_None_

## Architecture Note

- `_dev/{project_tag}/` symlinks point to actual project directories on disk
- Vault notes transclude `![[_dev/{tag}/CLAUDE.md]]` for live rendering
- Only CLAUDE.md files are indexed from `_dev/`; all other files excluded via `.obsidian/app.json`
- Single source of truth: edit CLAUDE.md in the project repo, vault reflects it immediately
- Lab entity nodes live at `projects/{lab}/_index.md` -- link as `[[{lab}/_index|Lab Name]]`
