#!/usr/bin/env bash
# Find claims with no incoming wiki links (orphans)
# Scans notes/ for files not referenced by any [[wiki link]] elsewhere in the vault.
set -euo pipefail
VAULT="${PROJECT_DIR:-.}"
NOTES_DIR="$VAULT/notes"

find "$NOTES_DIR" -name '*.md' -not -name '.*' 2>/dev/null | while read -r f; do
  title=$(basename "$f" .md)
  # Search the entire vault for [[title]] -- exclude .git
  if ! grep -rq "\[\[$title\]\]" "$VAULT" --include='*.md' 2>/dev/null; then
    echo "Orphan: $title"
  fi
done
