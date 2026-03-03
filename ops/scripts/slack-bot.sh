#!/usr/bin/env bash
# slack-bot.sh -- Two-way vault-aware Slack assistant for Engram Reactor
#
# Runs the Socket Mode bot as a long-lived process. Connects to Slack via
# WebSocket (no public URL needed), listens for DMs/@mentions/channel
# messages, and responds using Claude with full vault context.
#
# Usage:
#   tmux new -s slackbot 'bash ops/scripts/slack-bot.sh'
#   bash ops/scripts/slack-bot.sh --vault main
#
set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VAULT="${VAULT_PATH:-$(cd "$(dirname "$0")/../.." && pwd)}"
LOG_DIR="$VAULT/ops/daemon/logs"
PID_FILE="$VAULT/ops/daemon/.slack-bot.pid"
LOG_FILE="$LOG_DIR/slack-bot-$(date +%Y%m%d-%H%M%S).log"

# Mode flags
VAULT_NAME=""
for arg in "$@"; do
    case "$arg" in
        --vault) VAULT_NAME="__NEXT__" ;;
        *)
            if [ "$VAULT_NAME" = "__NEXT__" ]; then
                VAULT_NAME="$arg"
            fi
            ;;
    esac
done

# Resolve vault path via registry if --vault was provided
if [ -n "$VAULT_NAME" ] && [ "$VAULT_NAME" != "__NEXT__" ]; then
    RESOLVED=$(python3 -c "
from engram_r.vault_registry import get_vault
vc = get_vault('$VAULT_NAME')
print(vc.path)
" 2>/dev/null || python3 -c "
import sys
sys.path.insert(0, '$(cd "$(dirname "$0")/../.." && pwd)/_code/src')
from engram_r.vault_registry import get_vault
vc = get_vault('$VAULT_NAME')
print(vc.path)
" 2>/dev/null)
    if [ -n "$RESOLVED" ]; then
        VAULT="$RESOLVED"
    else
        echo "FATAL: Could not resolve vault '$VAULT_NAME' from registry" >&2
        exit 1
    fi
fi

mkdir -p "$LOG_DIR"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "=============================="
log "SLACK BOT STARTING"
log "  Vault: $VAULT"
log "=============================="

# Check Python -- use uv run from the _code project so venv deps are available
UV_RUN="uv run --project $VAULT/_code"
if ! $UV_RUN python -c "from engram_r.slack_bot import main" 2>/dev/null; then
    log "FATAL: Cannot import slack_bot. Check dependencies."
    log "  Install bot deps: cd $VAULT/_code && uv pip install -e '.[bot]'"
    exit 1
fi

# Check required env vars
for var in SLACK_BOT_TOKEN SLACK_APP_TOKEN ANTHROPIC_API_KEY; do
    if [ -z "${!var:-}" ]; then
        log "FATAL: $var not set"
        exit 1
    fi
done

log "Pre-flight checks passed."

# ---------------------------------------------------------------------------
# PID file
# ---------------------------------------------------------------------------
if [ -f "$PID_FILE" ]; then
    EXISTING_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$EXISTING_PID" ] && ps -p "$EXISTING_PID" -o pid= &>/dev/null; then
        log "FATAL: Slack bot already running (PID $EXISTING_PID). Remove $PID_FILE if stale."
        exit 1
    else
        log "WARNING: Stale PID file found (PID $EXISTING_PID not running). Removing."
        rm -f "$PID_FILE"
    fi
fi

echo $$ > "$PID_FILE"
log "PID file written: $PID_FILE ($$)"

cleanup_pid() {
    rm -f "$PID_FILE"
    log "Slack bot stopped."
}
trap cleanup_pid EXIT INT TERM HUP

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
export VAULT_PATH="$VAULT"
$UV_RUN python -m engram_r.slack_bot 2>&1 | tee -a "$LOG_FILE"
