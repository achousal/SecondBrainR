---
description: "YAML frontmatter query patterns -- using ripgrep to treat the vault as a database"
type: manual
created: 2026-02-22
---

# Querying Your Vault

Your YAML frontmatter turns ripgrep into a lightweight graph database. Every YAML field you add becomes a queryable dimension. Notes are rows, fields are columns, wiki-links are foreign keys.

---

## Field-Level Queries

Single-field searches across all claims.

```bash
# Find all claims of a specific type
rg '^type: evidence' notes/

# Find claims by confidence level
rg '^confidence: speculative' notes/

# Scan descriptions for a concept
rg '^description:.*feedback' notes/

# Find claims missing required fields
rg -L '^description:' notes/*.md

# List all unique values for a field
rg '^type:' notes/ | awk -F': ' '{print $NF}' | sort -u

# Count claims per type
rg '^type:' notes/ | awk -F': ' '{print $NF}' | sort | uniq -c | sort -rn
```

---

## Cross-Field Queries

Pipe chains combine multiple field constraints. First command selects files, second filters within the set.

```bash
# Established contradictions
rg -l '^type: contradiction' notes/ | xargs rg -l '^confidence: established'

# Speculative claims from a specific source
rg -l '^source:.*bach' notes/ | xargs rg -l '^confidence: speculative'

# Evidence claims created after a date
rg -l '^type: evidence' notes/ | xargs rg -l '^created: 2026-02'

# All claims from a source, showing their descriptions
rg -l '^source:.*kwan' notes/ | xargs rg '^description:'
```

---

## Backlink and Graph Queries

Wiki-links are edges in your knowledge graph. Query them to trace relationships.

```bash
# Who links to a specific claim?
rg '\[\[claim title here\]\]' --glob '*.md'

# Count incoming links for a claim
rg -c '\[\[claim title here\]\]' --glob '*.md'

# Find all outgoing links from a file
rg '\[\[.*?\]\]' notes/specific-claim.md

# Find orphans (claims with zero incoming links)
./ops/scripts/orphan-notes.sh

# Find dangling links (links to non-existent targets)
./ops/scripts/dangling-links.sh

# Get link density across the vault
./ops/scripts/link-density.sh
```

---

## Co-Scientist Queries

Hypothesis-specific queries for the generate-debate-evolve loop.

```bash
# Hypotheses by status
rg '^status:' _research/hypotheses/

# Hypotheses by generation
rg '^generation:' _research/hypotheses/

# Elo ratings above a threshold
rg '^elo:' _research/hypotheses/ | awk -F': ' '$2 > 1200'

# Tournament match winners
rg '^winner:' _research/tournaments/

# All hypotheses linked to a research goal
rg -l '^goal:.*early-detection' _research/hypotheses/

# List all unique sources across literature notes
rg '^source:' _research/literature/ | awk -F': ' '{print $NF}' | sort -u
```

---

## Inventory and Audit Queries

Maintenance queries for vault health.

```bash
# Claims missing descriptions
rg -L '^description:' notes/*.md

# Claims with very short descriptions (likely low quality)
rg '^description: .{1,40}$' notes/

# Files modified in the last 7 days (macOS)
find notes/ -name '*.md' -mtime -7

# Count total claims
ls notes/*.md 2>/dev/null | wc -l

# Count hypotheses by goal
rg '^goal:' _research/hypotheses/ | awk -F': ' '{print $NF}' | sort | uniq -c | sort -rn

# Find duplicate descriptions (possible redundant claims)
rg '^description:' notes/ | awk -F': ' '{print $NF}' | sort | uniq -d
```

---

## Pattern: Adding Queryable Dimensions

If you repeatedly want to filter by something, add it to your YAML schema:

1. **Notice the need** -- you keep wanting to filter by source type, method, or data layer.
2. **Add the field** -- update the relevant template in `_code/templates/`.
3. **Backfill selectively** -- add the field to existing claims where it matters.
4. **Query immediately** -- `rg '^method:.*regression' notes/` just works.

The rule: if a field is never queried, remove it. If you keep wishing you could query it, add it.

---

## Tips

- Use `^` anchors to match YAML keys at line start, avoiding false matches in body text.
- Use `-l` (files-with-matches) as a first pass, then pipe to a second `rg` for cross-field filtering.
- Use `-L` (files-without-match) to find claims missing a field.
- Use `--glob '*.md'` to restrict searches to markdown files when searching from the vault root.
- Combine with `wc -l`, `sort`, `uniq -c` for quick aggregate statistics.
