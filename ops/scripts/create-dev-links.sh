#!/usr/bin/env bash
# Create _dev/ symlinks from project note frontmatter.
#
# Reads project_tag and project_path from all projects/*/*.md YAML frontmatter,
# then creates symlinks at _dev/{project_tag} -> {project_path}.
# Idempotent: existing correct symlinks are skipped; stale ones are warned about.
#
# Usage:
#   bash ops/scripts/create-dev-links.sh            # run from vault root
#   PROJECT_DIR=/path/to/vault bash ops/scripts/create-dev-links.sh

set -euo pipefail

VAULT="${PROJECT_DIR:-.}"
DEV_DIR="$VAULT/_dev"
PROJECTS_DIR="$VAULT/projects"

mkdir -p "$DEV_DIR"

created=0
skipped=0
warned=0

for note in "$PROJECTS_DIR"/*/*.md; do
  [ -f "$note" ] || continue
  basename_note=$(basename "$note")
  [ "$basename_note" = "_index.md" ] && continue

  # Extract project_tag from frontmatter
  tag=$(sed -n '/^---$/,/^---$/p' "$note" | grep '^project_tag:' | head -1 | sed 's/^project_tag: *//' | tr -d '"' | tr -d "'")
  [ -z "$tag" ] && continue

  # Extract project_path from frontmatter
  proj_path=$(sed -n '/^---$/,/^---$/p' "$note" | grep '^project_path:' | head -1 | sed 's/^project_path: *//' | tr -d '"' | tr -d "'")
  [ -z "$proj_path" ] && continue

  # Expand ~ to $HOME
  proj_path="${proj_path/#\~/$HOME}"

  link="$DEV_DIR/$tag"

  if [ -L "$link" ]; then
    current_target=$(readlink "$link")
    if [ "$current_target" = "$proj_path" ]; then
      skipped=$((skipped + 1))
      continue
    else
      echo "WARN: $link -> $current_target (expected $proj_path)" >&2
      warned=$((warned + 1))
      continue
    fi
  fi

  if [ ! -d "$proj_path" ]; then
    echo "WARN: target does not exist: $proj_path (for $tag)" >&2
    warned=$((warned + 1))
    continue
  fi

  ln -sfn "$proj_path" "$link"
  echo "Created: $link -> $proj_path"
  created=$((created + 1))
done

echo ""
echo "=== Summary ==="
echo "Created: $created"
echo "Skipped (already correct): $skipped"
echo "Warnings: $warned"
