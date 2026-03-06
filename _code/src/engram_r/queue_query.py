"""CLI for querying the processing queue.

Replaces ad-hoc inline Python in ralph orchestrator Bash calls.
Avoids shell escaping issues (zsh history expansion mangles != in
inline Python).

Usage:
    python -m engram_r.queue_query VAULT_PATH stats
    python -m engram_r.queue_query VAULT_PATH actionable [--limit N] [--type PHASE] [--batch ID]
    python -m engram_r.queue_query VAULT_PATH siblings TASK_ID
    python -m engram_r.queue_query VAULT_PATH tasks [--limit N] [--type PHASE] [--batch ID] [--siblings]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PIPELINE_ORDER = ["reduce", "create", "enrich", "reflect", "reweave", "verify"]


def _pipeline_key(phase: str) -> int:
    try:
        return PIPELINE_ORDER.index(phase)
    except ValueError:
        return len(PIPELINE_ORDER)


def load_queue(vault_path: Path) -> list[dict]:
    """Load queue from the first existing location."""
    candidates = [
        vault_path / "ops" / "queue.yaml",
        vault_path / "ops" / "queue" / "queue.yaml",
        vault_path / "ops" / "queue" / "queue.json",
    ]
    for p in candidates:
        if p.exists():
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
    print("ERROR: no queue file found", file=sys.stderr)
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

    return {
        "total": len(tasks),
        "by_status": by_status,
        "pending_by_phase": pending_by_phase,
        "by_phase": by_phase,
    }


def get_actionable(
    tasks: list[dict],
    phase_filter: str | None = None,
    batch_filter: str | None = None,
    limit: int = 0,
) -> list[dict]:
    """Return actionable (pending, not blocked) tasks in pipeline order."""
    pending = [t for t in tasks if t.get("status") == "pending"]

    # Phase eligibility gate (global)
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

    args = parser.parse_args()
    tasks = load_queue(args.vault_path)

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
    else:
        parser.print_help()
        sys.exit(1)

    json.dump(output, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
