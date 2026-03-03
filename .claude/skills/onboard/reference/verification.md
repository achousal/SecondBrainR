# Verification Instructions

Reference file for the onboard-verify sub-skill. Extracted from the main onboard SKILL.md Step 6.

---

## Step 6: Verify

Run validation on all created artifacts:

### 6a. Schema check

For each created project note, verify required YAML fields are present:
- type, title, project_tag, lab, pi, status, project_path, language, hpc_path, scheduler, linked_goals, linked_hypotheses, linked_experiments, has_claude_md, has_git, has_tests, created, updated, tags

### 6b. Link health

Check that all `[[wiki-links]]` in created/modified files resolve to real files:
```bash
# Extract wiki-links from new files and check each resolves
```

### 6c. Index sync

Verify every new project note has a corresponding row in `projects/_index.md`.

### 6d. Symlink check

Verify each `_dev/{tag}` symlink exists and points to a valid directory:
```bash
ls -la _dev/{tag}
```

### 6e. Data inventory consistency

Every project with a non-empty data/ directory should have at least a Summary Table entry in `_research/data-inventory.md`.

### 6f. Institution profile consistency

If `institution_profile` is set (non-empty) in the lab entity node, verify `ops/institutions/{slug}.md` exists. If the file is missing, warn:
```
WARN: Lab references institution profile [[{slug}]] but ops/institutions/{slug}.md not found.
```

Report any issues found. If all pass:
```
Verification: all checks passed.
```

---

## Error Handling

| Error | Behavior |
|-------|----------|
| Lab path does not exist | Report error with path checked, ask for correct path |
| No projects detected in path | Report what was scanned and indicators checked, ask if path is correct |
| CLAUDE.md parse failure | Log warning, fall back to filesystem detection only |
| Project already registered | Show as CURRENT in diff, skip unless mode is --update with changes |
| data-inventory.md missing | Create from `_code/templates/data-inventory.md` with today's date |
| self/goals.md missing | Create with `## Active Threads` and `## Active Research Goals` sections |
| projects/_index.md missing | Create with `# Projects` heading and `## Maintenance` section |
| ops/reminders.md missing | Create from `_code/templates/reminders.md` |
| _dev/ directory missing | Create with `mkdir -p _dev` |
| _dev/ symlink already exists pointing to same target | Skip silently (idempotent) |
| _dev/ symlink exists pointing to different target | Warn user, ask before overwriting |
| Research goal already exists | Link project to existing goal instead of creating duplicate |
| projects/{lab}/ directory missing | Create with `mkdir -p` |
| Permission denied on symlink | Report error, suggest manual creation, continue with remaining artifacts |
| Flat structure detected | Offer restructuring options, do not silently flatten or nest |
| No conventions detected from code | Report "no conventions detected" in Lab Profile, accept user corrections |
| /learn fails during institution lookup | Log warning, skip institution profile, continue with filesystem-detected infrastructure only |
| Institution not determinable | Ask user; if skipped, proceed without institution profile |
| ops/institutions/ directory missing | Create with `mkdir -p ops/institutions` |
