#!/usr/bin/env bash
# daemon-all.sh -- Start one daemon per registered vault in tmux windows.
#
# Reads ~/.config/engramr/vaults.yaml and launches a daemon.sh
# instance for each vault in a separate tmux window within a single
# tmux session named "engramr-daemons".
#
# Usage:
#   bash ops/scripts/daemon-all.sh
#   bash ops/scripts/daemon-all.sh --dry-run    # pass flags to each daemon
#
# Prerequisites:
#   - tmux must be installed
#   - ~/.config/engramr/vaults.yaml must exist with at least one vault

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DAEMON_SCRIPT="$SCRIPT_DIR/daemon.sh"
TMUX_SESSION="engramr-daemons"
EXTRA_FLAGS="${*}"

# Check prerequisites
if ! command -v tmux &>/dev/null; then
    echo "FATAL: tmux is required but not found in PATH" >&2
    exit 1
fi

if [ ! -f "$DAEMON_SCRIPT" ]; then
    echo "FATAL: daemon.sh not found at $DAEMON_SCRIPT" >&2
    exit 1
fi

# Get vault names from registry
VAULT_NAMES=$(python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/../../_code/src')
from engram_r.vault_registry import load_registry
vaults = load_registry()
for v in vaults:
    print(v.name)
" 2>/dev/null)

if [ -z "$VAULT_NAMES" ]; then
    echo "No vaults found in registry. Create ~/.config/engramr/vaults.yaml first." >&2
    echo "See ~/.config/engramr/vaults.yaml.example for the format." >&2
    exit 1
fi

VAULT_COUNT=$(echo "$VAULT_NAMES" | wc -l | tr -d ' ')
echo "Found $VAULT_COUNT vault(s) in registry."

# Kill existing session if running
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "Stopping existing $TMUX_SESSION session..."
    tmux kill-session -t "$TMUX_SESSION"
fi

# Create new session with first vault
FIRST_VAULT=$(echo "$VAULT_NAMES" | head -1)
echo "Starting daemon for: $FIRST_VAULT"
tmux new-session -d -s "$TMUX_SESSION" -n "$FIRST_VAULT" \
    "bash $DAEMON_SCRIPT --vault $FIRST_VAULT $EXTRA_FLAGS"

# Add remaining vaults as new windows
echo "$VAULT_NAMES" | tail -n +2 | while read -r vault_name; do
    echo "Starting daemon for: $vault_name"
    tmux new-window -t "$TMUX_SESSION" -n "$vault_name" \
        "bash $DAEMON_SCRIPT --vault $vault_name $EXTRA_FLAGS"
done

echo ""
echo "All daemons started in tmux session: $TMUX_SESSION"
echo "  tmux attach -t $TMUX_SESSION    # attach to watch"
echo "  tmux kill-session -t $TMUX_SESSION  # stop all"
