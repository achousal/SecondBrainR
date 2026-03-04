"""Unified decision engine for /next and daemon scheduler.

Single source of truth for "what should the human do next?" Consumed by:
- /next skill (via CLI)
- daemon scheduler (via build_tier3_entries in daemon_scheduler.py)

Import direction: decision_engine -> daemon_scheduler -> daemon_config
Pure Python -- uses only stdlib + yaml + existing modules. No network I/O.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from engram_r.daemon_config import DaemonConfig, load_config
from engram_r.daemon_scheduler import (
    VaultState,
    build_tier3_entries,
    scan_vault,
)
from engram_r.frontmatter import default_vault_path as _default_vault_path

# ---------------------------------------------------------------------------
# Signal and Recommendation dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    """A single vault-state signal classified by consequence speed."""

    name: str
    count: int
    speed: str  # "session" | "multi_session" | "slow"
    action: str  # recommended command
    rationale: str


@dataclass
class Recommendation:
    """A single actionable recommendation for the human."""

    action: str
    rationale: str
    priority: str  # "session" | "multi_session" | "slow" | "tier3" | "clean"
    category: str  # "task_stack" | "maintenance" | "research" | "tier3" | "clean"
    after_that: str = ""


# ---------------------------------------------------------------------------
# Signal classification
# ---------------------------------------------------------------------------


def classify_signals(state: VaultState, config: DaemonConfig) -> list[Signal]:
    """Map VaultState fields to classified signals.

    Uses /next's consequence-speed thresholds to classify each signal.

    Args:
        state: Current vault state snapshot.
        config: Daemon configuration for thresholds.

    Returns:
        List of Signal objects, ordered by priority (session first).
    """
    signals: list[Signal] = []
    thresholds = config.thresholds

    # Metabolic signals (before existing session-priority signals)
    if state.metabolic and config.metabolic.enabled:
        m = state.metabolic
        alarm_keys = getattr(m, "alarm_keys", [])

        # Tier 1: Governance (session-priority)
        if "qpr_critical" in alarm_keys:
            signals.append(
                Signal(
                    name="metabolic_qpr",
                    count=int(m.qpr),
                    speed="session",
                    action="/ralph 5",
                    rationale=(
                        f"Queue pressure {m.qpr:.1f} days "
                        f"(>{config.metabolic.qpr_critical}). "
                        f"Process queue before creating."
                    ),
                )
            )
        if "cmr_hot" in alarm_keys:
            # Bootstrap guard: if no maintenance phases have ever completed
            # and there is queue backlog, redirect to processing first.
            _mc = getattr(m, "maintenance_count", 0)
            if _mc == 0 and state.queue_backlog > 0:
                signals.append(
                    Signal(
                        name="metabolic_cmr",
                        count=int(m.cmr),
                        speed="session",
                        action="/ralph",
                        rationale=(
                            "Bootstrap mode: no reflect phases completed yet. "
                            "Process queue items before first consolidation."
                        ),
                    )
                )
            else:
                signals.append(
                    Signal(
                        name="metabolic_cmr",
                        count=int(m.cmr),
                        speed="session",
                        action="/reflect",
                        rationale=(
                            f"Creation:Maintenance ratio {m.cmr:.0f}:1 "
                            f"(>{config.metabolic.cmr_hot:.0f}:1). Consolidate."
                        ),
                    )
                )
        if "tpv_stalled" in alarm_keys:
            _tpv_action = (
                f"/ralph {state.queue_backlog}"
                if state.queue_backlog > 1
                else "/reduce"
            )
            signals.append(
                Signal(
                    name="metabolic_tpv",
                    count=1,
                    speed="session",
                    action=_tpv_action,
                    rationale=(
                        f"Throughput velocity {m.tpv:.2f}/day "
                        f"(<{config.metabolic.tpv_stalled}). "
                        f"Process queue."
                    ),
                )
            )

        # Tier 2: Awareness (multi-session)
        if "hcr_low" in alarm_keys:
            signals.append(
                Signal(
                    name="metabolic_hcr",
                    count=int(100 - m.hcr),
                    speed="multi_session",
                    action="/experiment",
                    rationale=(
                        f"Hypothesis conversion {m.hcr:.0f}% "
                        f"(<{config.metabolic.hcr_redirect:.0f}%). "
                        f"Write SAPs."
                    ),
                )
            )
        if "gcr_fragmented" in alarm_keys:
            signals.append(
                Signal(
                    name="metabolic_gcr",
                    count=int((1 - m.gcr) * 100),
                    speed="multi_session",
                    action="/reflect --connect-orphans",
                    rationale=(
                        f"Graph connectivity {m.gcr:.2f} "
                        f"(<{config.metabolic.gcr_fragmented}). "
                        f"Connect orphan notes."
                    ),
                )
            )
        if "ipr_overflow" in alarm_keys:
            _ipr_action = (
                f"/ralph {state.queue_backlog}"
                if state.queue_backlog > 1
                else "/reduce"
            )
            signals.append(
                Signal(
                    name="metabolic_ipr",
                    count=int(m.ipr),
                    speed="session",
                    action=_ipr_action,
                    rationale=(
                        f"Inbox pressure {m.ipr:.1f} "
                        f"(>{config.metabolic.ipr_overflow}). "
                        f"Process inbox backlog."
                    ),
                )
            )

    # Session-priority signals
    if state.orphan_count > 0:
        signals.append(
            Signal(
                name="orphan_notes",
                count=state.orphan_count,
                speed="session",
                action="/reflect --connect-orphans",
                rationale=(
                    f"{state.orphan_count} orphan notes invisible to "
                    f"graph traversal"
                ),
            )
        )

    if state.inbox_count > 5:
        signals.append(
            Signal(
                name="inbox_pressure",
                count=state.inbox_count,
                speed="session",
                action="/seed --all then /ralph N",
                rationale=(f"{state.inbox_count} items in inbox, risking idea loss"),
            )
        )

    if state.observation_count >= thresholds.observations_rethink:
        signals.append(
            Signal(
                name="observations",
                count=state.observation_count,
                speed="session",
                action="/rethink",
                rationale=(
                    f"{state.observation_count} pending observations "
                    f"require pattern detection"
                ),
            )
        )

    if state.tension_count >= thresholds.tensions_rethink:
        signals.append(
            Signal(
                name="tensions",
                count=state.tension_count,
                speed="session",
                action="/rethink",
                rationale=(
                    f"{state.tension_count} pending tensions need " f"resolution"
                ),
            )
        )

    if state.unmined_session_count > 3:
        signals.append(
            Signal(
                name="unmined_sessions",
                count=state.unmined_session_count,
                speed="session",
                action="/remember --mine-sessions",
                rationale=(
                    f"{state.unmined_session_count} sessions have "
                    f"uncaptured friction patterns"
                ),
            )
        )

    # Multi-session signals
    if state.queue_backlog > thresholds.queue_backlog:
        signals.append(
            Signal(
                name="queue_backlog",
                count=state.queue_backlog,
                speed="multi_session",
                action="/ralph",
                rationale=(
                    f"{state.queue_backlog} pipeline tasks pending, "
                    f"blocking downstream connections"
                ),
            )
        )

    if state.queue_blocked > 0:
        signals.append(
            Signal(
                name="queue_blocked",
                count=state.queue_blocked,
                speed="multi_session",
                action="/literature",
                rationale=(
                    f"{state.queue_blocked} queue tasks blocked on "
                    f"unpopulated stubs -- populate before /ralph"
                ),
            )
        )

    if state.stale_note_count > 10:
        signals.append(
            Signal(
                name="stale_notes",
                count=state.stale_note_count,
                speed="multi_session",
                action="/reweave",
                rationale=(
                    f"{state.stale_note_count} notes not updated "
                    f"recently, decaying knowledge"
                ),
            )
        )

    if state.quarantine_count > 0:
        signals.append(
            Signal(
                name="quarantine_review",
                count=state.quarantine_count,
                speed="multi_session",
                action="/validate --quarantine",
                rationale=(
                    f"{state.quarantine_count} quarantined notes "
                    f"awaiting human review"
                ),
            )
        )

    # Slow signals
    if state.health_stale:
        signals.append(
            Signal(
                name="health_stale",
                count=1,
                speed="slow",
                action="/health",
                rationale="Health check is stale or missing",
            )
        )

    return signals


# ---------------------------------------------------------------------------
# Daemon inbox and next-log parsing
# ---------------------------------------------------------------------------

_DATE_HEADER_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})")
_SECTION_HEADER_RE = re.compile(r"^###\s+(.+)")


def parse_daemon_inbox(vault_path: Path) -> dict[str, list[str]]:
    """Read ops/daemon-inbox.md, extract today's sections.

    Args:
        vault_path: Root of the Obsidian vault.

    Returns:
        Dict with keys "completed", "alerts", "for_you" mapping to
        lists of entry strings.
    """
    inbox_path = vault_path / "ops" / "daemon-inbox.md"
    result: dict[str, list[str]] = {
        "completed": [],
        "alerts": [],
        "for_you": [],
    }
    if not inbox_path.is_file():
        return result

    try:
        text = inbox_path.read_text(errors="replace")
    except OSError:
        return result

    # Find the most recent date section
    in_recent_date = False
    current_section = ""
    _section_map = {
        "Completed": "completed",
        "Alerts": "alerts",
        "For You": "for_you",
    }

    for line in text.splitlines():
        date_m = _DATE_HEADER_RE.match(line)
        if date_m:
            # Only parse the first (most recent) date section
            if in_recent_date:
                break
            in_recent_date = True
            continue

        if not in_recent_date:
            continue

        sec_m = _SECTION_HEADER_RE.match(line)
        if sec_m:
            section_name = sec_m.group(1).strip()
            current_section = _section_map.get(section_name, "")
            continue

        stripped = line.strip()
        if current_section and stripped.startswith("- "):
            result[current_section].append(stripped)

    return result


def parse_next_log(vault_path: Path, n: int = 3) -> list[str]:
    """Read last N recommendations from ops/next-log.md.

    Args:
        vault_path: Root of the Obsidian vault.
        n: Number of recent recommendations to return.

    Returns:
        List of recommendation strings (most recent first).
    """
    log_path = vault_path / "ops" / "next-log.md"
    if not log_path.is_file():
        return []

    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        return []

    recs: list[str] = []
    rec_re = re.compile(r"^\*\*Recommended:\*\*\s*(.+)", re.MULTILINE)
    for m in rec_re.finditer(text):
        recs.append(m.group(1).strip())

    # File is newest-first, so just take first n
    return recs[:n]


# ---------------------------------------------------------------------------
# Daemon detection
# ---------------------------------------------------------------------------


def _daemon_is_running(vault_path: Path) -> tuple[bool, int]:
    """Check whether the research loop daemon is alive.

    Returns:
        (is_running, pid) tuple.
    """
    pid_path = vault_path / "ops" / "daemon" / ".daemon.pid"
    if not pid_path.is_file():
        return False, 0
    try:
        pid = int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return False, 0
    try:
        os.kill(pid, 0)
        return True, pid
    except OSError:
        return False, 0


# ---------------------------------------------------------------------------
# Empty vault detection (single source of truth)
# ---------------------------------------------------------------------------


def is_empty_vault(claim_count: int, inbox_count: int, queue_backlog: int) -> bool:
    """True when the vault has no content worth routing around.

    Shared by the decision engine and session orient hook so the
    definition lives in exactly one place.
    """
    return claim_count == 0 and inbox_count == 0 and queue_backlog == 0


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------


def recommend(
    state: VaultState,
    config: DaemonConfig,
    mode: str = "auto",
    vault_path: Path | None = None,
) -> Recommendation:
    """Unified priority cascade: one recommendation for the human.

    Priority order:
    1. Task stack active items (always first)
    2. Session-priority signals
    3. Multi-session signals
    4. Slow signals
    5. Tier 3 generative work (daemon idle items)
    6. Clean state

    Args:
        state: Current vault state snapshot.
        config: Daemon configuration.
        mode: "standalone", "daemon", or "auto" (detect daemon).
        vault_path: Vault root (needed for daemon inbox/next-log parsing).

    Returns:
        Recommendation with action, rationale, priority, and category.
    """
    # 0. Empty vault -- always recommend /onboard first
    if (
        not state.task_stack_active
        and is_empty_vault(state.claim_count, state.inbox_count, state.queue_backlog)
    ):
        return Recommendation(
            action="/onboard -- wire your first project into the vault",
            rationale=(
                "Empty vault detected (0 claims, 0 inbox, 0 queue). "
                "/onboard creates project notes, data inventory, research "
                "goals, and vault wiring -- the foundation everything else "
                "builds on."
            ),
            priority="session",
            category="empty_vault",
            after_that="/init to seed orientation claims and methodological foundations",
        )

    # 1. Task stack active items always win
    if state.task_stack_active:
        top = state.task_stack_active[0]
        after = ""
        if len(state.task_stack_active) > 1:
            after = state.task_stack_active[1].title
        return Recommendation(
            action=top.title,
            rationale=(
                f"Top task stack item. {top.description}"
                if top.description
                else "Top task stack item from ops/tasks.md."
            ),
            priority="session",
            category="task_stack",
            after_that=after,
        )

    # 2-4. Classify and pick highest-priority signal
    signals = classify_signals(state, config)

    # Dedup against recent /next recommendations
    recent_recs: list[str] = []
    if vault_path:
        recent_recs = parse_next_log(vault_path, n=3)

    # Session signals first
    session_signals = [s for s in signals if s.speed == "session"]
    if session_signals:
        best = _pick_best_signal(session_signals, recent_recs)
        return Recommendation(
            action=best.action,
            rationale=best.rationale,
            priority="session",
            category="maintenance",
            after_that=_next_signal_action(session_signals, best),
        )

    # Multi-session signals
    multi_signals = [s for s in signals if s.speed == "multi_session"]
    if multi_signals:
        best = _pick_best_signal(multi_signals, recent_recs)
        return Recommendation(
            action=best.action,
            rationale=best.rationale,
            priority="multi_session",
            category="maintenance",
            after_that=_next_signal_action(multi_signals, best),
        )

    # Slow signals
    slow_signals = [s for s in signals if s.speed == "slow"]
    if slow_signals:
        best = _pick_best_signal(slow_signals, recent_recs)
        return Recommendation(
            action=best.action,
            rationale=best.rationale,
            priority="slow",
            category="maintenance",
        )

    # 5. Tier 3 generative work
    tier3 = build_tier3_entries(state, config)
    # Filter out task stack items (already handled above)
    tier3_gen = [e for e in tier3 if "from task stack" not in e]
    if tier3_gen:
        # Extract first actionable entry (strip leading "- [ ] ")
        first = re.sub(r"^-\s*\[[ x]?\]\s*", "", tier3_gen[0])
        after = ""
        if len(tier3_gen) > 1:
            after = re.sub(r"^-\s*\[[ x]?\]\s*", "", tier3_gen[1])
        return Recommendation(
            action=first,
            rationale="Research cycle complete, generative work available.",
            priority="tier3",
            category="tier3",
            after_that=after,
        )

    # 6. Clean state
    return Recommendation(
        action="All signals healthy. Explore a new direction from goals.md "
        "or reweave older notes to deepen the graph.",
        rationale="No urgent work detected.",
        priority="clean",
        category="clean",
    )


def _pick_best_signal(signals: list[Signal], recent_recs: list[str]) -> Signal:
    """Pick the highest-impact signal, deprioritizing recent duplicates.

    Args:
        signals: Signals at the same priority level.
        recent_recs: Last N recommended actions for dedup.

    Returns:
        Best signal to recommend.
    """
    if not signals:
        raise ValueError("Cannot pick from empty signal list")

    # Sort by count descending (highest impact first)
    ranked = sorted(signals, key=lambda s: s.count, reverse=True)

    # Try to find one not recently recommended
    for s in ranked:
        if not any(s.action in rec for rec in recent_recs[:2]):
            return s

    # All were recently recommended; return highest-impact anyway
    return ranked[0]


def _next_signal_action(signals: list[Signal], current: Signal) -> str:
    """Return the action of the next-best signal after current."""
    for s in signals:
        if s is not current:
            return s.action
    return ""


# ---------------------------------------------------------------------------
# State summary for CLI output
# ---------------------------------------------------------------------------


def _build_state_summary(state: VaultState) -> dict:
    """Build a concise state summary dict for JSON output."""
    summary = {
        "claim_count": state.claim_count,
        "health_fails": state.health_fails,
        "health_stale": state.health_stale,
        "observations": state.observation_count,
        "tensions": state.tension_count,
        "queue_backlog": state.queue_backlog,
        "queue_blocked": state.queue_blocked,
        "orphan_notes": state.orphan_count,
        "inbox": state.inbox_count,
        "unmined_sessions": state.unmined_session_count,
        "stale_notes": state.stale_note_count,
        "task_stack_active": len(state.task_stack_active),
        "task_stack_pending": len(state.task_stack_pending),
        "goals": [
            {
                "goal_id": gs.goal_id,
                "cycle_state": gs.cycle_state,
                "hypothesis_count": gs.hypothesis_count,
            }
            for gs in state.goals
        ],
    }
    if state.metabolic:
        m = state.metabolic
        summary["metabolic"] = {
            "qpr": round(m.qpr, 1),
            "cmr": round(m.cmr, 1),
            "tpv": round(m.tpv, 2),
            "hcr": round(m.hcr, 1),
            "gcr": round(m.gcr, 2),
            "ipr": round(m.ipr, 1),
            "vdr": round(m.vdr, 1),
            "alarm_keys": list(m.alarm_keys),
        }
    return summary


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the decision engine.

    Usage:
        python -m engram_r.decision_engine [vault_path]
            [--mode auto|standalone|daemon]

    Prints JSON with recommendation, state_summary, daemon_context.
    Exit code:
        0 = recommendation
        2 = clean (all healthy)
        1 = error
    """
    args = argv if argv is not None else sys.argv[1:]

    # Parse arguments
    vault_path_str = None
    mode = "auto"
    i = 0
    while i < len(args):
        if args[i] == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            vault_path_str = args[i]
            i += 1
        else:
            i += 1

    vault_path = Path(vault_path_str) if vault_path_str else _default_vault_path()
    config_path = vault_path / "ops" / "daemon-config.yaml"

    if not config_path.is_file():
        msg = {"error": f"Config not found: {config_path}"}
        print(json.dumps(msg), file=sys.stderr)
        return 1

    config = load_config(config_path)
    state = scan_vault(vault_path, config)

    # Detect daemon mode
    daemon_running, daemon_pid = _daemon_is_running(vault_path)
    effective_mode = mode
    if mode == "auto":
        effective_mode = "daemon" if daemon_running else "standalone"

    rec = recommend(state, config, mode=effective_mode, vault_path=vault_path)

    # Build daemon context
    daemon_context: dict = {"running": daemon_running, "pid": daemon_pid}
    if daemon_running:
        inbox_data = parse_daemon_inbox(vault_path)
        daemon_context["completed"] = inbox_data["completed"]
        daemon_context["alerts"] = inbox_data["alerts"]
        daemon_context["for_you"] = inbox_data["for_you"]

    result = {
        "mode": effective_mode,
        "recommendation": {
            "action": rec.action,
            "rationale": rec.rationale,
            "priority": rec.priority,
            "category": rec.category,
            "after_that": rec.after_that,
        },
        "state_summary": _build_state_summary(state),
        "daemon_context": daemon_context,
    }

    print(json.dumps(result, indent=2))
    return 0 if rec.priority != "clean" else 2


if __name__ == "__main__":
    sys.exit(main())
