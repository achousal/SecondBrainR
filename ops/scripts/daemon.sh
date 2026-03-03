#!/usr/bin/env bash
# daemon.sh -- Research Loop Daemon for Engram Reactor
#
# Continuously evaluates vault state via Python scheduler, executes the
# highest-priority task via `claude -p`, respects cooldowns, and logs
# results to ops/daemon-inbox.md.
#
# Usage:
#   tmux new -s daemon 'bash ops/scripts/daemon.sh'
#   bash ops/scripts/daemon.sh --dry-run         # print what would run
#   bash ops/scripts/daemon.sh --once            # run one task, exit
#   bash ops/scripts/daemon.sh --vault main      # use named vault from registry
#
set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VAULT="${VAULT_PATH:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Load project-scoped env vars (API keys for daemon, Slack bot, etc.)
if [ -f "$VAULT/_code/.env" ]; then
    set -a
    source "$VAULT/_code/.env"
    set +a
fi

LOG_DIR="$VAULT/ops/daemon/logs"
MARKER_DIR="$VAULT/ops/daemon/markers"
PID_FILE="$VAULT/ops/daemon/.daemon.pid"
INBOX_FILE="$VAULT/ops/daemon-inbox.md"
CONFIG_FILE="$VAULT/ops/daemon-config.yaml"
SCHEDULER="$VAULT/_code/src/engram_r/daemon_scheduler.py"

# Read config values via Python for consistency
read_config_value() {
    python3 -c "
import yaml, sys
cfg = yaml.safe_load(open('$CONFIG_FILE'))
keys = '$1'.split('.')
v = cfg
for k in keys:
    v = v.get(k, {}) if isinstance(v, dict) else {}
print(v if v else '$2')
" 2>/dev/null || echo "$2"
}

# Retry config
MAX_RETRIES=$(read_config_value "retry.max_per_task" "8")
INITIAL_BACKOFF=$(read_config_value "retry.initial_backoff_seconds" "60")
MAX_BACKOFF=$(read_config_value "retry.max_backoff_seconds" "900")
GLOBAL_TIMEOUT_H=$(read_config_value "timeout.global_hours" "0")

# Health gate config
HEALTH_CHECK_HOURS=$(read_config_value "health.check_frequency_hours" "2")
HEALTH_MAX_FIX_ITERS=$(read_config_value "health.max_fix_iterations" "3")
HEALTH_MODEL=$(read_config_value "health.model" "sonnet")
HEALTH_DIR="$VAULT/ops/health"

# Autonomous system prompt override
UNATTENDED_OVERRIDE="CRITICAL: You are running unattended as a daemon. There is NO human at the terminal. If you call AskUserQuestion or EnterPlanMode the session will hang forever. NEVER use these tools. Make all decisions autonomously. When a skill asks for user input, provide a reasonable default and continue. When a skill presents a verdict for user override, accept it and proceed."

# Skill-level backoff config
SKILL_BACKOFF_FILE="$VAULT/ops/daemon/skill-backoff.json"
SKILL_BACKOFF_THRESHOLD=3
SKILL_BACKOFF_DURATION=1800
SKILL_BACKOFF_MAX=7200

# Mode flags
DRY_RUN=false
ONCE=false
VAULT_NAME=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --once) ONCE=true ;;
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

# Global state
RUN_START=$(date +%s)
TASKS_PASSED=0
TASKS_FAILED=0
TASKS_SKIPPED=0
FAST_FAIL_COUNT=0
MAX_FAST_FAILS=5   # stop if this many consecutive <10s exits
CONSEC_SKIPS=0
MAX_CONSEC_SKIPS=3 # switch to idle cooldown after this many consecutive skips

LOG_FILE="$LOG_DIR/daemon-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$LOG_DIR" "$MARKER_DIR"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ---------------------------------------------------------------------------
# Slack notifications (fire-and-forget, backgrounded)
# ---------------------------------------------------------------------------
slack_notify() {
    local event_type="$1"; shift
    python3 -c "
import sys
sys.path.insert(0, '$VAULT/_code/src')
from engram_r.slack_notify import send_notification
from pathlib import Path
send_notification('$event_type', vault_path=Path('$VAULT'), $@)
" >> "$LOG_DIR/slack-notify.log" 2>&1 &
}

# ---------------------------------------------------------------------------
# Daemon inbox append
# ---------------------------------------------------------------------------
append_inbox() {
    local section="$1"
    local content="$2"
    local today
    today=$(date +%Y-%m-%d)

    # Create file with today's header if needed
    if [ ! -f "$INBOX_FILE" ]; then
        echo "# Daemon Inbox" > "$INBOX_FILE"
        echo "" >> "$INBOX_FILE"
    fi

    # Add date header if not present
    if ! grep -q "^## $today" "$INBOX_FILE" 2>/dev/null; then
        echo "" >> "$INBOX_FILE"
        echo "## $today" >> "$INBOX_FILE"
        echo "" >> "$INBOX_FILE"
    fi

    # Add section header if not present under today
    if ! grep -q "^### $section" "$INBOX_FILE" 2>/dev/null; then
        echo "### $section" >> "$INBOX_FILE"
    fi

    echo "$content" >> "$INBOX_FILE"
}

# ---------------------------------------------------------------------------
# Health check: Vault directory exists
# ---------------------------------------------------------------------------
check_vault() {
    if [ -d "$VAULT" ] && [ -d "$VAULT/ops" ]; then
        return 0
    else
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Global timeout check
# ---------------------------------------------------------------------------
check_global_timeout() {
    if [ "$GLOBAL_TIMEOUT_H" -eq 0 ]; then
        return 0
    fi
    local timeout_s=$((GLOBAL_TIMEOUT_H * 3600))
    local elapsed=$(( $(date +%s) - RUN_START ))
    if [ "$elapsed" -ge "$timeout_s" ]; then
        log "GLOBAL TIMEOUT reached (${elapsed}s >= ${timeout_s}s). Stopping."
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Idempotent markers
# ---------------------------------------------------------------------------
is_task_done() {
    local key="$1"
    [ -f "$MARKER_DIR/$key.done" ]
}

mark_task_done() {
    local key="$1"
    date '+%Y-%m-%d %H:%M:%S' > "$MARKER_DIR/$key.done"
}

# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------
cooldown() {
    local model="$1"
    local minutes

    case "$model" in
        haiku)  minutes=$(read_config_value "cooldowns_minutes.after_haiku" "2") ;;
        sonnet) minutes=$(read_config_value "cooldowns_minutes.after_sonnet" "5") ;;
        opus)   minutes=$(read_config_value "cooldowns_minutes.after_opus" "10") ;;
        idle)   minutes=$(read_config_value "cooldowns_minutes.idle" "30") ;;
        *)      minutes=5 ;;
    esac

    log "Cooldown: ${minutes}m after $model"
    sleep $((minutes * 60))
}

# ---------------------------------------------------------------------------
# Skill-level backoff (delegates to _daemon_backoff.py)
# ---------------------------------------------------------------------------
skill_in_backoff() {
    local skill="$1"
    python3 -c "
import sys
sys.path.insert(0, '$VAULT/_code/src')
from pathlib import Path
from engram_r._daemon_backoff import skill_in_backoff
in_bo, remaining = skill_in_backoff('$skill', Path('$SKILL_BACKOFF_FILE'))
print('yes' if in_bo else 'no', remaining)
" 2>/dev/null || echo "no 0"
}

record_skill_success() {
    local skill="$1"
    python3 -c "
import sys
sys.path.insert(0, '$VAULT/_code/src')
from pathlib import Path
from engram_r._daemon_backoff import record_success
record_success('$skill', Path('$SKILL_BACKOFF_FILE'))
" 2>/dev/null
}

record_skill_failure() {
    local skill="$1"
    local threshold="${2:-$SKILL_BACKOFF_THRESHOLD}"
    python3 -c "
import sys
sys.path.insert(0, '$VAULT/_code/src')
from pathlib import Path
from engram_r._daemon_backoff import record_failure
record_failure('$skill', Path('$SKILL_BACKOFF_FILE'),
    threshold=$threshold,
    initial_s=$SKILL_BACKOFF_DURATION,
    max_s=$SKILL_BACKOFF_MAX)
" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Vault-state snapshot (for post-condition verification)
# ---------------------------------------------------------------------------
CODE_DIR="$VAULT/_code"

vault_snapshot() {
    cd "$CODE_DIR" && uv run python -m engram_r.daemon_scheduler --scan-only "$VAULT" 2>/dev/null || echo "{}"
}

record_outcome() {
    local task_key="$1"
    local skill="$2"
    local outcome="$3"
    local elapsed="$4"
    local vault_before="$5"
    local vault_after="$6"
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
    cd "$CODE_DIR" && uv run python -c "
from engram_r.audit import AuditOutcome, append_outcome
from pathlib import Path
import json, sys
before = json.loads(sys.argv[1]) if sys.argv[1] else {}
after = json.loads(sys.argv[2]) if sys.argv[2] else {}
changed = [k for k in before if before.get(k) != after.get(k)]
outcome = AuditOutcome(
    timestamp='$ts',
    task_key='$task_key', skill='$skill',
    outcome='success' if changed else 'no_change',
    duration_seconds=$elapsed,
    vault_summary_before=before, vault_summary_after=after,
    changed_keys=changed,
)
append_outcome(outcome, Path('$VAULT/ops/daemon/logs/audit.jsonl'))
" "$vault_before" "$vault_after" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Run scheduler to get next task
# ---------------------------------------------------------------------------
get_next_task() {
    cd "$VAULT" || return 1
    local output
    output=$(python3 -m engram_r.daemon_scheduler "$VAULT" 2>"$LOG_DIR/scheduler-stderr.log")
    local exit_code=$?

    if [ $exit_code -eq 2 ]; then
        # Idle -- check for inbox entries
        local entries
        entries=$(echo "$output" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for e in data.get('inbox_entries', []):
    print(e)
" 2>/dev/null)
        if [ -n "$entries" ]; then
            append_inbox "For You" "$entries"
            slack_notify daemon_for_you "entries=$(echo "$entries" | python3 -c "import sys; print(repr(sys.stdin.read().strip().split('\n')))" 2>/dev/null)"
        fi
        echo "IDLE"
        return 2
    elif [ $exit_code -ne 0 ]; then
        log "ERROR: Scheduler failed (exit=$exit_code)"
        return 1
    fi

    echo "$output"
    return 0
}

# ---------------------------------------------------------------------------
# Execute a task
# ---------------------------------------------------------------------------
run_task() {
    local task_json="$1"

    # Parse task fields
    local skill model prompt task_key
    skill=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['skill'])")
    model=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['model'])")
    prompt=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['prompt'])")
    task_key=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['task_key'])")

    # Skip if already completed
    if [ -n "$task_key" ] && is_task_done "$task_key"; then
        log "SKIP: $task_key (already done)"
        TASKS_SKIPPED=$((TASKS_SKIPPED + 1))
        CONSEC_SKIPS=$((CONSEC_SKIPS + 1))
        return 0
    fi

    # Skill-level backoff check
    local backoff_result
    backoff_result=$(skill_in_backoff "$skill")
    local in_backoff
    in_backoff=$(echo "$backoff_result" | awk '{print $1}')
    local backoff_remaining
    backoff_remaining=$(echo "$backoff_result" | awk '{print $2}')
    if [ "$in_backoff" = "yes" ]; then
        log "SKIP: $skill in backoff (${backoff_remaining}s remaining)"
        TASKS_SKIPPED=$((TASKS_SKIPPED + 1))
        CONSEC_SKIPS=$((CONSEC_SKIPS + 1))
        return 0
    fi

    # Health check: vault directory exists
    if ! check_vault; then
        log "ERROR: Vault directory not found: $VAULT"
        TASKS_FAILED=$((TASKS_FAILED + 1))
        return 1
    fi

    log "=== STARTING: $skill ($task_key, model=$model) ==="

    if [ "$DRY_RUN" = true ]; then
        log "DRY RUN: would execute $skill with model=$model"
        log "  task_key: $task_key"
        log "  prompt: ${prompt:0:200}..."
        return 0
    fi

    local attempt=0
    local backoff=$INITIAL_BACKOFF

    while [ "$attempt" -lt "$MAX_RETRIES" ]; do
        attempt=$((attempt + 1))

        if ! check_global_timeout; then
            exit 0
        fi

        local start_time
        start_time=$(date +%s)

        # Direct Python execution for scheduled notifications (no LLM needed)
        if [ "$skill" = "notify-scheduled" ]; then
            local sched_result
            sched_result=$(python3 -c "
import sys
sys.path.insert(0, '$VAULT/_code/src')
from engram_r.schedule_runner import execute_schedule
sent = execute_schedule('$VAULT', '$task_key')
print(f'Sent {sent} message(s)')
" 2>>"$LOG_FILE")
            local sched_exit=$?
            local elapsed=$(( $(date +%s) - start_time ))
            if [ $sched_exit -eq 0 ]; then
                log "=== COMPLETED: $skill ($task_key, ${elapsed}s) -- $sched_result ==="
                [ -n "$task_key" ] && mark_task_done "$task_key"
                TASKS_PASSED=$((TASKS_PASSED + 1))
                FAST_FAIL_COUNT=0
                CONSEC_SKIPS=0
                record_skill_success "$skill"
                append_inbox "Completed" "- [x] $skill: $task_key ($sched_result, ${elapsed}s)"
                slack_notify daemon_task_complete "skill='$skill', task_key='$task_key', model='direct', elapsed_s=$elapsed"
                return 0
            else
                log "FAIL: $skill ($task_key, exit=$sched_exit, ${elapsed}s)"
                TASKS_FAILED=$((TASKS_FAILED + 1))
                record_skill_failure "$skill"
                return 1
            fi
        fi

        # Vault-state snapshot before execution
        local vault_before
        vault_before=$(vault_snapshot)

        # For Slack read-only tasks, capture output to a results file
        local slack_result_file=""
        if [[ "$task_key" == slack-* ]]; then
            local slack_entry_id="${task_key#slack-}"
            mkdir -p "$VAULT/ops/daemon/slack-results"
            slack_result_file="$VAULT/ops/daemon/slack-results/${slack_entry_id}.md"
        fi

        # Execute via claude -p
        if [ -n "$slack_result_file" ]; then
            claude -p "$prompt" \
                --model "$model" \
                --no-session-persistence \
                --disallowedTools "AskUserQuestion,EnterPlanMode,EnterWorktree" \
                --append-system-prompt "$UNATTENDED_OVERRIDE" \
                > "$slack_result_file" 2>>"$LOG_FILE"
        else
            claude -p "$prompt" \
                --model "$model" \
                --no-session-persistence \
                --disallowedTools "AskUserQuestion,EnterPlanMode,EnterWorktree" \
                --append-system-prompt "$UNATTENDED_OVERRIDE" \
                >> "$LOG_FILE" 2>&1
        fi

        if [ $? -eq 0 ]; then

            local elapsed=$(( $(date +%s) - start_time ))

            # Vault-state snapshot after execution
            local vault_after
            vault_after=$(vault_snapshot)

            # Record outcome (best-effort)
            record_outcome "$task_key" "$skill" "success" "$elapsed" "$vault_before" "$vault_after"

            # Detect silent failure: exit 0 but no vault change
            local vault_changed
            vault_changed=$(python3 -c "
import json, sys
before = json.loads(sys.argv[1]) if sys.argv[1] else {}
after = json.loads(sys.argv[2]) if sys.argv[2] else {}
changed = [k for k in before if before.get(k) != after.get(k)]
print('yes' if changed else 'no')
" "$vault_before" "$vault_after" 2>/dev/null || echo "yes")

            if [ "$vault_changed" = "no" ] && [ "$elapsed" -gt 30 ]; then
                log "NO VAULT CHANGE: $skill ($task_key) ran for ${elapsed}s with no effect"
                record_skill_failure "$skill" 5
            else
                record_skill_success "$skill"
            fi

            log "=== COMPLETED: $skill ($task_key, ${elapsed}s, attempt $attempt) ==="
            [ -n "$task_key" ] && mark_task_done "$task_key"
            TASKS_PASSED=$((TASKS_PASSED + 1))
            FAST_FAIL_COUNT=0
            CONSEC_SKIPS=0
            append_inbox "Completed" "- [x] $skill: $task_key ($model, ${elapsed}s)"
            slack_notify daemon_task_complete "skill='$skill', task_key='$task_key', model='$model', elapsed_s=$elapsed"

            # Slack queue completion hook
            if [[ "$task_key" == slack-* ]]; then
                python3 -c "
import sys; sys.path.insert(0, '$VAULT/_code/src')
from engram_r.slack_skill_router import complete_task
complete_task('$VAULT', '$task_key', 'success', $elapsed)
" >> "$LOG_DIR/slack-queue.log" 2>&1 &
            fi

            return 0
        else
            local exit_code=$?
            local elapsed=$(( $(date +%s) - start_time ))

            if [ "$elapsed" -lt 10 ]; then
                FAST_FAIL_COUNT=$((FAST_FAIL_COUNT + 1))
                log "FAST FAIL: $skill (exit=$exit_code, ${elapsed}s, attempt $attempt/$MAX_RETRIES, consecutive=$FAST_FAIL_COUNT)"
                if [ "$FAST_FAIL_COUNT" -ge "$MAX_FAST_FAILS" ]; then
                    log "ABORT: $MAX_FAST_FAILS consecutive fast fails. Possible config or credit issue."
                    append_inbox "Alerts" "- $(date '+%H:%M') Daemon aborted: $MAX_FAST_FAILS consecutive fast fails"
                    slack_notify daemon_alert "message='Daemon aborted: $MAX_FAST_FAILS consecutive fast fails'"
                    exit 1
                fi
            else
                FAST_FAIL_COUNT=0
                log "FAIL: $skill (exit=$exit_code, ${elapsed}s, attempt $attempt/$MAX_RETRIES)"
            fi

            if [ "$attempt" -lt "$MAX_RETRIES" ]; then
                log "Retrying in ${backoff}s..."
                sleep "$backoff"
                backoff=$(( backoff * 2 ))
                [ "$backoff" -gt "$MAX_BACKOFF" ] && backoff=$MAX_BACKOFF
            fi
        fi
    done

    log "=== GAVE UP: $skill ($task_key) after $MAX_RETRIES attempts ==="
    TASKS_FAILED=$((TASKS_FAILED + 1))
    record_skill_failure "$skill"
    append_inbox "Alerts" "- $(date '+%H:%M') GAVE UP: $skill ($task_key) after $MAX_RETRIES attempts"
    slack_notify daemon_alert "message='GAVE UP: $skill ($task_key) after $MAX_RETRIES attempts'"

    # Slack queue failure hook
    if [[ "$task_key" == slack-* ]]; then
        local gave_up_elapsed=$(( $(date +%s) - start_time ))
        python3 -c "
import sys; sys.path.insert(0, '$VAULT/_code/src')
from engram_r.slack_skill_router import complete_task
complete_task('$VAULT', '$task_key', 'failed', $gave_up_elapsed)
" >> "$LOG_DIR/slack-queue.log" 2>&1 &
    fi

    return 1
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    local total_elapsed=$(( $(date +%s) - RUN_START ))
    local hours=$(( total_elapsed / 3600 ))
    local mins=$(( (total_elapsed % 3600) / 60 ))
    log "=============================="
    log "DAEMON RUN SUMMARY"
    log "  Duration: ${hours}h ${mins}m"
    log "  Passed:   $TASKS_PASSED"
    log "  Failed:   $TASKS_FAILED"
    log "  Skipped:  $TASKS_SKIPPED"
    log "  Log:      $LOG_FILE"
    log "=============================="
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
cd "$VAULT" || { echo "FATAL: cannot cd to vault"; exit 1; }

log "=============================="
log "RESEARCH LOOP DAEMON STARTED"
log "  Vault:   $VAULT"
log "  Mode:    $([ "$DRY_RUN" = true ] && echo "DRY RUN" || ([ "$ONCE" = true ] && echo "ONCE" || echo "CONTINUOUS"))"
log "  Timeout: $([ "$GLOBAL_TIMEOUT_H" -eq 0 ] && echo "none" || echo "${GLOBAL_TIMEOUT_H}h")"
log "=============================="

# Check claude
if ! command -v claude &>/dev/null; then
    log "FATAL: claude command not found in PATH"
    exit 1
fi

# Check Python + scheduler
if ! python3 -c "from engram_r.daemon_scheduler import main" 2>/dev/null; then
    # Try with PYTHONPATH
    export PYTHONPATH="$VAULT/_code/src:${PYTHONPATH:-}"
    if ! python3 -c "from engram_r.daemon_scheduler import main" 2>/dev/null; then
        log "FATAL: Cannot import daemon_scheduler. Check PYTHONPATH."
        exit 1
    fi
fi

# Check config
if [ ! -f "$CONFIG_FILE" ]; then
    log "FATAL: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Check vault directory
if ! check_vault; then
    log "FATAL: Vault directory not found or missing ops/: $VAULT"
    exit 1
fi

log "Pre-flight checks passed."

# ---------------------------------------------------------------------------
# PID file -- prevent double-daemon, enable /next daemon detection
# ---------------------------------------------------------------------------
if [ -f "$PID_FILE" ]; then
    EXISTING_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$EXISTING_PID" ] && ps -p "$EXISTING_PID" -o pid= &>/dev/null; then
        log "FATAL: Daemon already running (PID $EXISTING_PID). Remove $PID_FILE if stale."
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
    print_summary
}
trap cleanup_pid EXIT INT TERM HUP

# ---------------------------------------------------------------------------
# Health observations -- extract root causes into ops/observations/
# ---------------------------------------------------------------------------
create_health_observations() {
    local report_file="$1"
    if [ -z "$report_file" ] || [ ! -f "$report_file" ]; then
        return 0
    fi
    if [ "$DRY_RUN" = true ]; then
        log "DRY RUN: would create health observations from $report_file"
        return 0
    fi
    local created
    created=$(python3 -c "
import sys
sys.path.insert(0, '$VAULT/_code/src')
from pathlib import Path
from engram_r.daemon_scheduler import create_health_observations
result = create_health_observations(Path('$VAULT'), Path('$report_file'))
print(len(result))
for f in result:
    print(f'  {f}')
" 2>"$LOG_DIR/health-obs-stderr.log")
    local count
    count=$(echo "$created" | head -1)
    if [ "$count" != "0" ]; then
        log "Health observations: created $count observation(s) from root causes"
        echo "$created" | tail -n +2 >> "$LOG_FILE"
    fi
}

# ---------------------------------------------------------------------------
# Health gate -- /health must pass before any task runs
# ---------------------------------------------------------------------------
run_health_gate() {
    # Returns: 0 = clean, 1 = fixed (re-run gate), 2 = unfixable (proceed with warning)
    mkdir -p "$HEALTH_DIR"

    # Find newest report
    local latest
    latest=$(ls -t "$HEALTH_DIR"/*.md 2>/dev/null | head -1)

    # Check staleness
    local needs_check=false
    if [ -z "$latest" ]; then
        needs_check=true
    else
        local age_s
        local stat_fmt='-c %Y'
        [[ "$(uname)" == "Darwin" ]] && stat_fmt='-f %m'
        age_s=$(( $(date +%s) - $(stat $stat_fmt "$latest" 2>/dev/null || echo 0) ))
        local max_age_s=$(( HEALTH_CHECK_HOURS * 3600 ))
        if [ "$age_s" -gt "$max_age_s" ]; then
            needs_check=true
        fi
    fi

    if [ "$needs_check" = true ]; then
        log "Health gate: report stale or missing, running /health quick"
        if [ "$DRY_RUN" = true ]; then
            log "DRY RUN: would run /health quick with model=$HEALTH_MODEL"
            return 0
        fi
        if ! check_vault; then
            log "ERROR: Vault directory not found: $VAULT"
            return 2
        fi
        claude -p "$UNATTENDED_OVERRIDE Run /health quick. Write the report to ops/health/." \
            --model "$HEALTH_MODEL" \
            --no-session-persistence \
            --disallowedTools "AskUserQuestion,EnterPlanMode,EnterWorktree" \
            --append-system-prompt "$UNATTENDED_OVERRIDE" \
            >> "$LOG_FILE" 2>&1
        latest=$(ls -t "$HEALTH_DIR"/*.md 2>/dev/null | head -1)
        if [ -z "$latest" ]; then
            log "Health gate: /health produced no report, proceeding with warning"
            append_inbox "Alerts" "- $(date '+%H:%M') Health gate: no report produced"
            return 2
        fi
    fi

    # Parse FAIL count from summary line
    local fail_count
    fail_count=$(grep -o 'Summary: [0-9]* FAIL' "$latest" 2>/dev/null | grep -o '[0-9]*' || echo "0")

    if [ "$fail_count" -eq 0 ]; then
        log "Health gate: PASS (0 failures)"
        return 0
    fi

    log "Health gate: $fail_count FAIL(s) detected"

    # Fix loop
    local iter=0
    while [ "$iter" -lt "$HEALTH_MAX_FIX_ITERS" ] && [ "$fail_count" -gt 0 ]; do
        iter=$((iter + 1))
        log "Health gate: fix iteration $iter/$HEALTH_MAX_FIX_ITERS"

        if [ "$DRY_RUN" = true ]; then
            log "DRY RUN: would run health fix tasks"
            return 0
        fi

        # Get fix task from Python scheduler
        local fix_json
        fix_json=$(python3 -c "
import json, sys
sys.path.insert(0, '$VAULT/_code/src')
from engram_r.daemon_scheduler import parse_health_report, build_health_fix_task, FailedCategory
from engram_r.daemon_config import load_config
from pathlib import Path

config = load_config(Path('$CONFIG_FILE'))
report = parse_health_report(Path('$latest'), max_age_hours=$HEALTH_CHECK_HOURS)
for cat in report.failed_categories:
    task = build_health_fix_task(cat, config)
    if task is not None:
        print(task.to_json())
        break
else:
    print(json.dumps({'status': 'no_fix'}))
" 2>"$LOG_DIR/health-fix-stderr.log")

        local fix_status
        fix_status=$(echo "$fix_json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','has_task'))" 2>/dev/null || echo "has_task")

        if [ "$fix_status" = "no_fix" ]; then
            log "Health gate: no automated fix available for remaining failures"
            break
        fi

        # Execute the fix task
        run_task "$fix_json"

        # Re-run /health
        log "Health gate: re-running /health quick after fix"
        if ! check_vault; then
            log "ERROR: Vault directory not found: $VAULT"
            return 2
        fi
        claude -p "$UNATTENDED_OVERRIDE Run /health quick. Write the report to ops/health/." \
            --model "$HEALTH_MODEL" \
            --no-session-persistence \
            --disallowedTools "AskUserQuestion,EnterPlanMode,EnterWorktree" \
            --append-system-prompt "$UNATTENDED_OVERRIDE" \
            >> "$LOG_FILE" 2>&1

        latest=$(ls -t "$HEALTH_DIR"/*.md 2>/dev/null | head -1)
        fail_count=$(grep -o 'Summary: [0-9]* FAIL' "$latest" 2>/dev/null | grep -o '[0-9]*' || echo "0")
    done

    # Create observations from root causes (after fix loop, before return)
    create_health_observations "$latest"

    if [ "$fail_count" -gt 0 ]; then
        log "Health gate: $fail_count FAIL(s) remain after $iter fix iterations, proceeding with warning"
        append_inbox "Alerts" "- $(date '+%H:%M') Health gate: $fail_count failures unfixed after $iter iterations"
        return 2
    fi

    log "Health gate: PASS after $iter fix iteration(s)"
    return 1
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
while true; do
    if ! check_global_timeout; then
        exit 0
    fi

    # Health gate: /health must pass before downstream work
    run_health_gate
    HEALTH_EXIT=$?
    if [ "$HEALTH_EXIT" -eq 2 ]; then
        log "Health gate returned unfixable, proceeding to task selection anyway"
    fi

    # Get next task from scheduler
    TASK_OUTPUT=$(get_next_task)
    SCHED_EXIT=$?

    if [ $SCHED_EXIT -eq 2 ]; then
        # Idle
        log "All caught up. Cooling down."
        append_inbox "Completed" "- $(date '+%H:%M') All caught up"

        if [ "$ONCE" = true ]; then
            log "ONCE mode: no work to do. Exiting."
            exit 0
        fi

        cooldown "idle"
        # Clear daily markers at midnight to allow re-evaluation
        continue
    fi

    if [ $SCHED_EXIT -ne 0 ]; then
        log "Scheduler error. Retrying in 60s."
        sleep 60
        continue
    fi

    # Extract model for cooldown
    TASK_MODEL=$(echo "$TASK_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('model','sonnet'))" 2>/dev/null || echo "sonnet")

    # Execute
    run_task "$TASK_OUTPUT"

    if [ "$ONCE" = true ]; then
        log "ONCE mode: completed one task. Exiting."
        exit 0
    fi

    # Use idle cooldown if scheduler keeps returning already-done tasks
    if [ "$CONSEC_SKIPS" -ge "$MAX_CONSEC_SKIPS" ]; then
        log "All tasks returned by scheduler already done ($CONSEC_SKIPS consecutive skips). Idle cooldown."
        cooldown "idle"
        # Clear markers at idle boundary to allow re-evaluation next cycle
        CONSEC_SKIPS=0
    else
        cooldown "$TASK_MODEL"
    fi
done
