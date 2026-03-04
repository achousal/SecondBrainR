---
name: onboard-verify
description: "Verify schema, links, and consistency of onboard artifacts. Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: haiku
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
argument-hint: "(no arguments -- verifies all recent onboard artifacts)"
---

## EXECUTE NOW

Verify all recently created onboard artifacts for schema compliance, link health, and consistency.

### Step 1: Read Reference

```
Read .claude/skills/onboard/reference/verification.md
```

### Step 2: Identify Artifacts to Verify

Find recently created/modified project notes:
```bash
find projects/ -name '*.md' -newer projects/_index.md -type f 2>/dev/null
```

If that returns nothing, verify all project notes:
```bash
ls projects/*/*.md 2>/dev/null
```

### Step 3: Run Checks

Follow `reference/verification.md` for each check:

**6a. Schema check** -- For each project note, verify required YAML fields:
- type, title, project_tag, lab, pi, status, project_path, language, hpc_path, scheduler, linked_goals, linked_hypotheses, linked_experiments, has_claude_md, has_git, has_tests, created, updated, tags

**6b. Link health** -- Extract `[[wiki-links]]` from created files, verify each resolves:
```bash
grep -oh '\[\[[^]]*\]\]' {file} | sed 's/\[\[\(.*\)\]\]/\1/' | while read link; do
  ls "notes/${link}.md" "projects/*/${link}.md" "_research/goals/${link}.md" 2>/dev/null || echo "BROKEN: [[${link}]] in {file}"
done
```

**6c. Index sync** -- Every project note in `projects/{lab}/` has a row in `projects/_index.md`.

**6d. Symlink check** -- Each project_tag has a valid `_dev/{tag}` symlink.

**6e. Data inventory consistency** -- Projects with data/ have Summary Table entries.

**6f. Institution profile consistency** -- If lab references an institution_profile, verify the file exists.

### Step 4: Output Report

```markdown
## VERIFICATION REPORT

### Schema Check
- {N} project notes checked
- PASS: {list} | FAIL: {list with missing fields}

### Link Health
- {N} wiki-links checked
- PASS: all resolved | FAIL: {broken links}

### Index Sync
- PASS | FAIL: {missing rows}

### Symlink Check
- PASS | FAIL: {missing symlinks}

### Data Inventory
- PASS | FAIL: {projects missing entries}

### Institution Profile
- PASS | FAIL: {reference without file}

### Overall: {PASS | {N} issues found}
```
