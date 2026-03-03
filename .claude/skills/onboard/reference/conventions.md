# Convention Inheritance Model

Reference file for onboard sub-skills. Extracted from the main onboard SKILL.md.

---

## Three-Level Inheritance

Statistical and style conventions follow a three-level inheritance chain:

```
Vault defaults (ops/config.yaml)
  -> Lab defaults (projects/{lab}/_index.md frontmatter)
    -> Project overrides (projects/{lab}/{tag}.md frontmatter)
```

**Resolution rule:** Skills that consume conventions (/eda, /plot, /experiment, /generate) resolve in order: project -> lab -> vault. First non-empty value wins.

**What lives where:**

| Level | Stored in | Set by | Example |
|-------|-----------|--------|---------|
| Vault | `ops/config.yaml` under `conventions:` | /setup, manual edit | Default alpha=0.05, vault plot theme |
| Lab | `projects/{lab}/_index.md` `statistical_conventions` / `style_conventions` | /onboard Step 2d | Lab prefers FDR, single-column 3.5in figures |
| Project | `projects/{lab}/{tag}.md` (optional override fields) | /onboard Step 3 corrections or manual | Project targets Nature (specific figure format) |

## Multi-Lab Considerations

- A central vault with multiple labs is ideal when there is domain overlap -- cross-lab synthesis is the primary value.
- If labs have zero domain overlap, separate vaults with /federation-sync may be a better fit.
- Research goals can be lab-specific (`linked_labs: ["smith"]`) or cross-lab (`linked_labs: ["smith", "jones"]`). An empty list means vault-wide.
- /init seeds domain knowledge per goal (`/init {goal-name}` targets a specific goal; goals are already lab-scoped via `linked_labs` frontmatter). Vault-level methodology seeds run once.
- /literature searches are scoped by research goal (already goal-specific). Results benefit all labs in the vault through /reflect and /reweave.
- /tournament can run within a goal (lab-scoped) or vault-wide for cross-domain hypothesis comparison.

## Critical Constraints

- **User approval before writes.** The batch approval is the single gate. Never silently create artifacts.
- **Match existing conventions exactly.** Project notes go in `projects/{lab_slug}/`. Index uses the existing table format. Data inventory uses existing column format.
- **Idempotent.** Running /onboard twice on the same lab produces no duplicate artifacts.
- **No CLAUDE.md content duplication.** Project notes use `![[_dev/{tag}/CLAUDE.md]]` transclusion, not copied content.
- **Wiki-link integrity.** Every link created must resolve. Verify before finishing.
- **YAML safety.** Double-quote all string values in frontmatter.
- **No slash in tags or titles.** Use hyphens: `smith-lab` not `smith/lab`.
