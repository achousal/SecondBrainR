"""CLI for querying and mutating the processing queue.

Replaces ad-hoc inline Python in ralph orchestrator Bash calls.
Avoids shell escaping issues (zsh history expansion mangles != in
inline Python).

Usage:
    python -m engram_r.queue_query VAULT_PATH stats
    python -m engram_r.queue_query VAULT_PATH actionable [--limit N] [--type PHASE] [--batch ID]
    python -m engram_r.queue_query VAULT_PATH siblings TASK_ID
    python -m engram_r.queue_query VAULT_PATH tasks [--limit N] [--type PHASE] [--batch ID] [--siblings]
    python -m engram_r.queue_query VAULT_PATH fail TASK_ID [--reason TEXT]
    python -m engram_r.queue_query VAULT_PATH retry TASK_ID
    python -m engram_r.queue_query VAULT_PATH alerts
    python -m engram_r.queue_query VAULT_PATH advance TASK_ID [--phase NEXT_PHASE]
    python -m engram_r.queue_query VAULT_PATH write --patch JSON_PATCH
    python -m engram_r.queue_query VAULT_PATH batches [--check-complete]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_ORDER = ["reduce", "create", "enrich", "reflect", "reweave", "verify"]

# Phase sequences by task type (used for advance logic)
PHASE_ORDER_CLAIM = ["create", "reflect", "reweave", "verify"]
PHASE_ORDER_ENRICHMENT = ["enrich", "reflect", "reweave", "verify"]

# Retry defaults (mirrors daemon RetryConfig)
DEFAULT_MAX_RETRIES = 8


def _pipeline_key(phase: str) -> int:
    try:
        return PIPELINE_ORDER.index(phase)
    except ValueError:
        return len(PIPELINE_ORDER)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _phase_order_for(task: dict) -> list[str]:
    """Return the phase sequence for a task based on its type."""
    task_type = task.get("type", "")
    if task_type == "extract":
        return ["reduce"]
    if task_type == "enrichment":
        return PHASE_ORDER_ENRICHMENT
    return PHASE_ORDER_CLAIM


def _queue_path(vault_path: Path) -> Path | None:
    """Return the first existing queue file path, or None."""
    candidates = [
        vault_path / "ops" / "queue.yaml",
        vault_path / "ops" / "queue" / "queue.yaml",
        vault_path / "ops" / "queue" / "queue.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def write_queue_atomic(queue: list[dict], queue_file: Path) -> None:
    """Write queue to disk atomically (write-to-temp then rename)."""
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=queue_file.parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        json.dump(queue, tmp, indent=2, ensure_ascii=False)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(queue_file)


def load_queue(vault_path: Path) -> list[dict]:
    """Load queue from the first existing location."""
    p = _queue_path(vault_path)
    if p is None:
        print("ERROR: no queue file found", file=sys.stderr)
        sys.exit(1)
    with open(p) as f:
        if p.suffix == ".json":
            return json.load(f)
        else:
            try:
                import yaml
                return yaml.safe_load(f) or []
            except ImportError:
                print("ERROR: pyyaml not installed for .yaml queue", file=sys.stderr)
                sys.exit(1)


def get_stats(tasks: list[dict]) -> dict:
    """Compute queue statistics."""
    by_status: dict[str, int] = {}
    by_phase: dict[str, int] = {}
    pending_by_phase: dict[str, int] = {}

    for t in tasks:
        status = t.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

        phase = t.get("current_phase", "none")
        by_phase[phase] = by_phase.get(phase, 0) + 1

        if status == "pending":
            pending_by_phase[phase] = pending_by_phase.get(phase, 0) + 1

    failed_count = by_status.get("failed", 0)

    return {
        "total": len(tasks),
        "by_status": by_status,
        "pending_by_phase": pending_by_phase,
        "by_phase": by_phase,
        "failed_count": failed_count,
    }


def get_actionable(
    tasks: list[dict],
    phase_filter: str | None = None,
    batch_filter: str | None = None,
    limit: int = 0,
) -> dict:
    """Return actionable (pending, not blocked) tasks in pipeline order.

    Failed tasks are excluded from both the actionable list AND the phase
    gate calculation -- a failed create task does not block reflect/reweave.
    """
    pending = [t for t in tasks if t.get("status") == "pending"]

    # Phase eligibility gate (global) -- only pending tasks count
    pending_phases = set()
    for t in pending:
        cp = t.get("current_phase")
        if cp:
            pending_phases.add(cp)

    blocked_phases: set[str] = set()
    blocked_reasons: dict[str, str] = {}

    if "create" in pending_phases or "enrich" in pending_phases:
        blocked_phases.update({"reflect", "reweave"})
        blockers = []
        if "create" in pending_phases:
            blockers.append("create")
        if "enrich" in pending_phases:
            blockers.append("enrich")
        blocked_reasons["reflect"] = f"{', '.join(blockers)} tasks must finish first"
        blocked_reasons["reweave"] = f"{', '.join(blockers)} tasks must finish first"

    if "reflect" in pending_phases:
        blocked_phases.add("reweave")
        blocked_reasons["reweave"] = "reflect tasks must finish first"

    # Never block reduce or verify
    blocked_phases.discard("reduce")
    blocked_phases.discard("verify")

    actionable = [
        t for t in pending
        if t.get("current_phase") not in blocked_phases
    ]

    # Apply user filters
    if phase_filter:
        actionable = [t for t in actionable if t.get("current_phase") == phase_filter]
    if batch_filter:
        actionable = [t for t in actionable if t.get("batch") == batch_filter]

    # Sort by pipeline order, then queue position
    actionable.sort(key=lambda t: _pipeline_key(t.get("current_phase", "")))

    # Batch grouping within same phase
    seen_batches: list[str] = []
    for t in actionable:
        b = t.get("batch", "")
        if b and b not in seen_batches:
            seen_batches.append(b)

    def batch_group_key(t: dict) -> tuple[int, int]:
        phase_idx = _pipeline_key(t.get("current_phase", ""))
        b = t.get("batch", "")
        batch_idx = seen_batches.index(b) if b in seen_batches else len(seen_batches)
        return (phase_idx, batch_idx)

    actionable.sort(key=batch_group_key)

    if limit > 0:
        actionable = actionable[:limit]

    # Compute blocked summary
    blocked_summary = {}
    for phase in blocked_phases:
        count = sum(1 for t in pending if t.get("current_phase") == phase)
        if count > 0:
            blocked_summary[phase] = {
                "count": count,
                "reason": blocked_reasons.get(phase, "blocked by earlier phase"),
            }

    return {
        "actionable": actionable,
        "actionable_count": len(actionable),
        "blocked": blocked_summary,
    }


def get_siblings(tasks: list[dict], task_id: str) -> list[dict]:
    """Return sibling tasks (same batch, create completed, different id)."""
    target_task = None
    for t in tasks:
        if t.get("id") == task_id:
            target_task = t
            break

    if not target_task:
        return []

    batch = target_task.get("batch")
    if not batch:
        return []

    siblings = []
    for t in tasks:
        if t.get("id") == task_id:
            continue
        if t.get("batch") != batch:
            continue
        completed = t.get("completed_phases", [])
        if "create" in completed or "enrich" in completed:
            siblings.append({
                "id": t.get("id"),
                "target": t.get("target"),
                "current_phase": t.get("current_phase"),
                "status": t.get("status"),
            })

    return siblings


def get_tasks_detail(
    tasks: list[dict],
    phase_filter: str | None = None,
    batch_filter: str | None = None,
    limit: int = 0,
    include_siblings: bool = False,
) -> list[dict]:
    """Return task details with optional sibling info."""
    result = get_actionable(tasks, phase_filter, batch_filter, limit)
    actionable = result["actionable"]

    detailed = []
    for t in actionable:
        entry = {
            "id": t.get("id"),
            "type": t.get("type"),
            "target": t.get("target"),
            "batch": t.get("batch"),
            "file": t.get("file"),
            "current_phase": t.get("current_phase"),
            "completed_phases": t.get("completed_phases", []),
            "source_detail": t.get("source_detail"),
        }
        if include_siblings:
            entry["siblings"] = get_siblings(tasks, t["id"])
        detailed.append(entry)

    return {
        "tasks": detailed,
        "count": len(detailed),
        "blocked": result["blocked"],
    }


def fail_task(
    tasks: list[dict],
    task_id: str,
    reason: str = "",
) -> dict:
    """Mark a task as failed with retry tracking.

    Returns a result dict with the action taken.
    """
    for t in tasks:
        if t.get("id") == task_id:
            retry_count = t.get("retry_count", 0)
            t["status"] = "failed"
            t["fail_reason"] = reason or "unspecified"
            t["failed_at"] = _utcnow_iso()
            t["retry_count"] = retry_count
            return {
                "action": "failed",
                "id": task_id,
                "retry_count": retry_count,
                "reason": t["fail_reason"],
            }
    return {"action": "error", "id": task_id, "message": "task not found"}


def retry_task(
    tasks: list[dict],
    task_id: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict:
    """Reset a failed task to pending for retry.

    Increments retry_count. Refuses if retry_count >= max_retries.
    Returns a result dict with the action taken.
    """
    for t in tasks:
        if t.get("id") == task_id:
            if t.get("status") != "failed":
                return {
                    "action": "error",
                    "id": task_id,
                    "message": f"task is '{t.get('status')}', not 'failed'",
                }
            retry_count = t.get("retry_count", 0) + 1
            if retry_count > max_retries:
                return {
                    "action": "error",
                    "id": task_id,
                    "message": (
                        f"retry limit reached ({max_retries}). "
                        f"Use --force or manually edit queue.json."
                    ),
                    "retry_count": retry_count - 1,
                }
            t["status"] = "pending"
            t["retry_count"] = retry_count
            t.pop("fail_reason", None)
            t.pop("failed_at", None)
            return {
                "action": "retried",
                "id": task_id,
                "retry_count": retry_count,
                "current_phase": t.get("current_phase"),
            }
    return {"action": "error", "id": task_id, "message": "task not found"}


def advance_task(
    tasks: list[dict],
    task_id: str,
    next_phase: str | None = None,
) -> dict:
    """Advance a pending task to its next phase, or mark done if final.

    If next_phase is provided, use it. Otherwise, auto-determine from
    the task's phase_order.

    Returns a result dict with the action taken.
    """
    for t in tasks:
        if t.get("id") == task_id:
            if t.get("status") != "pending":
                return {
                    "action": "error",
                    "id": task_id,
                    "message": f"task is '{t.get('status')}', not 'pending'",
                }

            current = t.get("current_phase")
            completed = t.get("completed_phases", [])

            if next_phase:
                # Explicit phase advancement
                completed.append(current)
                t["completed_phases"] = completed
                t["current_phase"] = next_phase
                return {
                    "action": "advanced",
                    "id": task_id,
                    "from_phase": current,
                    "to_phase": next_phase,
                }

            # Auto-determine next phase
            order = _phase_order_for(t)
            try:
                idx = order.index(current)
            except ValueError:
                return {
                    "action": "error",
                    "id": task_id,
                    "message": f"current phase '{current}' not in order {order}",
                }

            completed.append(current)
            t["completed_phases"] = completed

            if idx + 1 < len(order):
                t["current_phase"] = order[idx + 1]
                return {
                    "action": "advanced",
                    "id": task_id,
                    "from_phase": current,
                    "to_phase": order[idx + 1],
                }
            else:
                t["status"] = "done"
                t["current_phase"] = None
                t["completed"] = _utcnow_iso()
                return {
                    "action": "done",
                    "id": task_id,
                    "from_phase": current,
                }
    return {"action": "error", "id": task_id, "message": "task not found"}


def get_alerts(tasks: list[dict]) -> dict:
    """Surface failed tasks and operational alerts."""
    failed = [
        {
            "id": t.get("id"),
            "target": t.get("target"),
            "current_phase": t.get("current_phase"),
            "fail_reason": t.get("fail_reason", ""),
            "retry_count": t.get("retry_count", 0),
            "failed_at": t.get("failed_at", ""),
        }
        for t in tasks
        if t.get("status") == "failed"
    ]

    # Tasks at retry limit
    at_limit = [f for f in failed if f["retry_count"] >= DEFAULT_MAX_RETRIES]

    return {
        "failed_count": len(failed),
        "failed": failed,
        "at_retry_limit": at_limit,
        "at_retry_limit_count": len(at_limit),
    }


def get_batch_status(tasks: list[dict], check_complete: bool = False) -> dict:
    """Return batch completion status.

    If check_complete is True, identifies batches where ALL tasks are done
    and have 2+ claims -- eligible for cross-connect.
    """
    batches: dict[str, dict] = {}
    for t in tasks:
        batch = t.get("batch", "")
        if not batch:
            continue
        if batch not in batches:
            batches[batch] = {"total": 0, "done": 0, "pending": 0, "failed": 0}
        batches[batch]["total"] += 1
        status = t.get("status", "unknown")
        if status in batches[batch]:
            batches[batch][status] += 1

    result: dict = {"batches": batches}

    if check_complete:
        complete = []
        for batch_id, counts in batches.items():
            if counts["pending"] == 0 and counts["failed"] == 0 and counts["done"] >= 2:
                complete.append(batch_id)
        result["complete_batches"] = complete
        result["complete_count"] = len(complete)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the processing queue")
    parser.add_argument("vault_path", type=Path, help="Path to vault root")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="Queue statistics")

    act = sub.add_parser("actionable", help="List actionable tasks")
    act.add_argument("--limit", type=int, default=0)
    act.add_argument("--type", dest="phase", default=None)
    act.add_argument("--batch", default=None)

    sib = sub.add_parser("siblings", help="Get siblings for a task")
    sib.add_argument("task_id", help="Task ID")

    det = sub.add_parser("tasks", help="Task details with siblings")
    det.add_argument("--limit", type=int, default=0)
    det.add_argument("--type", dest="phase", default=None)
    det.add_argument("--batch", default=None)
    det.add_argument("--siblings", action="store_true")

    fail_cmd = sub.add_parser("fail", help="Mark a task as failed")
    fail_cmd.add_argument("task_id", help="Task ID")
    fail_cmd.add_argument("--reason", default="", help="Failure reason")

    retry_cmd = sub.add_parser("retry", help="Retry a failed task")
    retry_cmd.add_argument("task_id", help="Task ID")
    retry_cmd.add_argument("--force", action="store_true", help="Bypass retry limit")

    sub.add_parser("alerts", help="Show failed tasks and alerts")

    adv = sub.add_parser("advance", help="Advance a task to next phase")
    adv.add_argument("task_id", help="Task ID")
    adv.add_argument("--phase", dest="next_phase", default=None,
                      help="Explicit next phase (auto-determined if omitted)")

    batch_cmd = sub.add_parser("batches", help="Batch completion status")
    batch_cmd.add_argument("--check-complete", action="store_true",
                           help="Identify batches ready for cross-connect")

    args = parser.parse_args()
    vault_path = args.vault_path
    tasks = load_queue(vault_path)

    # Read-only commands
    if args.command == "stats":
        output = get_stats(tasks)
    elif args.command == "actionable":
        output = get_actionable(tasks, args.phase, args.batch, args.limit)
    elif args.command == "siblings":
        output = get_siblings(tasks, args.task_id)
    elif args.command == "tasks":
        output = get_tasks_detail(
            tasks, args.phase, args.batch, args.limit, args.siblings
        )
    elif args.command == "alerts":
        output = get_alerts(tasks)

    # Mutation commands -- write queue back to disk
    elif args.command == "fail":
        output = fail_task(tasks, args.task_id, args.reason)
        if output.get("action") != "error":
            qp = _queue_path(vault_path)
            if qp:
                write_queue_atomic(tasks, qp)
    elif args.command == "retry":
        max_r = DEFAULT_MAX_RETRIES if not args.force else 999
        output = retry_task(tasks, args.task_id, max_retries=max_r)
        if output.get("action") != "error":
            qp = _queue_path(vault_path)
            if qp:
                write_queue_atomic(tasks, qp)
    elif args.command == "advance":
        output = advance_task(tasks, args.task_id, args.next_phase)
        if output.get("action") != "error":
            qp = _queue_path(vault_path)
            if qp:
                write_queue_atomic(tasks, qp)
    elif args.command == "batches":
        output = get_batch_status(tasks, args.check_complete)
    else:
        parser.print_help()
        sys.exit(1)

    json.dump(output, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
