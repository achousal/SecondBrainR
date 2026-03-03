#!/usr/bin/env bash
# Validate all claims against schema (check required fields)
set -euo pipefail
VAULT="${PROJECT_DIR:-.}"
NOTES_DIR="$VAULT/notes"

PASS=0
WARN=0
FAIL=0

find "$NOTES_DIR" -name '*.md' -not -name '.*' 2>/dev/null | while read -r f; do
  title=$(basename "$f" .md)
  issues=""

  # Check for description field
  if ! grep -q '^description:' "$f" 2>/dev/null; then
    issues="$issues missing-description"
  else
    DESC=$(grep '^description:' "$f" | sed 's/^description:[[:space:]]*//' | tr -d '"')
    if [[ -z "$DESC" ]]; then
      issues="$issues empty-description"
    fi
  fi

  if [[ -n "$issues" ]]; then
    echo "FAIL: $title --$issues"
  else
    echo "PASS: $title"
  fi
done
