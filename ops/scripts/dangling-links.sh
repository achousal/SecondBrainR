#!/usr/bin/env bash
# Canonical dangling link checker for the vault.
# Find wiki links pointing to non-existent files.
# Handles [[target|display text]] syntax. Excludes skill files, templates, and test fixtures.
# Scoped to knowledge graph directories only (notes/, _research/, self/, projects/).
# Intentionally excludes ops/health/ and ops/queue/ -- those are diagnostic artifacts,
# not graph nodes, and their shorthand references are not meant to resolve.
set -euo pipefail
VAULT="${PROJECT_DIR:-.}"

# Directories to scan (vault content, not infrastructure)
SCAN_DIRS=(
  "$VAULT/notes"
  "$VAULT/hypotheses"
  "$VAULT/literature"
  "$VAULT/self"
  "$VAULT/experiments"
  "$VAULT/projects"
  "$VAULT/_research"
)

# Collect all wiki links from content files, strip display text
for dir in "${SCAN_DIRS[@]}"; do
  [[ -d "$dir" ]] || continue
  grep -roh '\[\[[^]]*\]\]' "$dir" --include='*.md' 2>/dev/null
done \
  | sed 's/\[\[//;s/\]\]//' \
  | sed 's/|.*//' \
  | grep -v '^\$' \
  | grep -v '^\.' \
  | grep -v '^!' \
  | grep -v '^-' \
  | grep -v '/' \
  | sort -u \
  | while read -r title; do
    [[ -z "$title" ]] && continue
    if ! find "$VAULT" -name "$title.md" -not -path '*/.git/*' 2>/dev/null | grep -q .; then
      echo "Dangling: [[$title]]"
    fi
  done
