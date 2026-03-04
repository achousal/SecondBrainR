#!/usr/bin/env bash
# Count incoming links to a specific claim
# Usage: backlinks.sh "claim title" [--count]
set -euo pipefail
VAULT="${PROJECT_DIR:-.}"
TITLE="${1:?Usage: backlinks.sh \"claim title\" [--count]}"
COUNT_ONLY="${2:-}"

if [[ "$COUNT_ONLY" == "--count" ]]; then
  grep -rl "\[\[$TITLE\]\]" "$VAULT" --include='*.md' 2>/dev/null | wc -l | tr -d ' '
else
  grep -rl "\[\[$TITLE\]\]" "$VAULT" --include='*.md' 2>/dev/null || echo "(no backlinks found)"
fi
