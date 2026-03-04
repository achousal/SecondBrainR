#!/usr/bin/env bash
# Measure average outgoing wiki links per claim in notes/
set -euo pipefail
VAULT="${PROJECT_DIR:-.}"
NOTES_DIR="$VAULT/notes"

TOTAL_LINKS=0
TOTAL_FILES=0

while IFS= read -r f; do
  LINKS=$(grep -co '\[\[[^]]*\]\]' "$f" 2>/dev/null || echo 0)
  TOTAL_LINKS=$((TOTAL_LINKS + LINKS))
  TOTAL_FILES=$((TOTAL_FILES + 1))
done < <(find "$NOTES_DIR" -name '*.md' -not -name '.*' 2>/dev/null)

if [[ "$TOTAL_FILES" -gt 0 ]]; then
  echo "Total claims: $TOTAL_FILES"
  echo "Total outgoing links: $TOTAL_LINKS"
  echo "Average links per claim: $(echo "scale=1; $TOTAL_LINKS / $TOTAL_FILES" | bc 2>/dev/null || echo "N/A")"
else
  echo "No claims found in notes/"
fi
