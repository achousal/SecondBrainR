#!/usr/bin/env bash
# Safely rename a claim, updating all wiki links across the vault
# Usage: rename-note.sh "old title" "new title"
set -euo pipefail
VAULT="${PROJECT_DIR:-.}"
OLD="${1:?Usage: rename-note.sh \"old title\" \"new title\"}"
NEW="${2:?Usage: rename-note.sh \"old title\" \"new title\"}"

# Find the file
OLD_FILE=$(find "$VAULT" -name "$OLD.md" -not -path '*/.git/*' 2>/dev/null | head -1)
if [[ -z "$OLD_FILE" ]]; then
  echo "Error: No file found for '$OLD'"
  exit 1
fi

NEW_DIR=$(dirname "$OLD_FILE")
NEW_FILE="$NEW_DIR/$NEW.md"

if [[ -f "$NEW_FILE" ]]; then
  echo "Error: '$NEW.md' already exists"
  exit 1
fi

# Rename with git mv
cd "$VAULT"
git mv "$OLD_FILE" "$NEW_FILE" 2>/dev/null || mv "$OLD_FILE" "$NEW_FILE"

# Update all wiki links
grep -rl "\[\[$OLD\]\]" "$VAULT" --include='*.md' 2>/dev/null | while read -r f; do
  perl -pi -e "s|\Q[[$OLD]]\E|[[$NEW]]|g" "$f"
done

echo "Renamed: $OLD -> $NEW"
echo "Updated all wiki links across the vault"
