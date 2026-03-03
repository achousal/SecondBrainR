"""Slack skill router -- queue-based execution with RBAC.

Routes Slack user requests to vault skills through the daemon's existing
safety sandbox. Handles permission checks, command parsing, intent
extraction, queue I/O, and task completion notifications.

Queue file: ops/daemon/slack-queue.json
Results dir: ops/daemon/slack-results/
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill ceilings -- hardcoded, not config-driven
# ---------------------------------------------------------------------------

SLACK_READONLY_SKILLS: frozenset[str] = frozenset({"stats", "next", "graph", "tasks"})

SLACK_ALLOWED_SKILLS: frozenset[str] = frozenset(
    {
        # Read-only
        "stats",
        "next",
        "graph",
        "tasks",
        # Maintenance
        "validate",
        "verify",
        # Mutative (via daemon)
        "reduce",
        "reflect",
        "reweave",
        "tournament",
        "meta-review",
        "landscape",
        "rethink",
        "remember",
    }
)

# ---------------------------------------------------------------------------
# Auth matrix -- maps auth level to allowed skills
# ---------------------------------------------------------------------------

SKILL_AUTH_MATRIX: dict[str, frozenset[str]] = {
    "owner": SLACK_ALLOWED_SKILLS,
    "allowed": frozenset({"stats", "next", "tasks", "graph", "validate", "verify"}),
    "public": frozenset({"stats", "next"}),
}

# ---------------------------------------------------------------------------
# Safety tiers -- determines confirmation behavior
# ---------------------------------------------------------------------------

SKILL_SAFETY_TIERS: dict[str, str] = {
    "stats": "read",
    "next": "read",
    "graph": "read",
    "tasks": "read",
    "validate": "maintenance",
    "verify": "maintenance",
    "reduce": "mutative",
    "reflect": "mutative",
    "reweave": "mutative",
    "tournament": "mutative",
    "meta-review": "mutative",
    "landscape": "mutative",
    "rethink": "mutative",
    "remember": "mutative",
}

# ---------------------------------------------------------------------------
# Explicit command regex
# ---------------------------------------------------------------------------

_COMMAND_RE = re.compile(
    r"^\s*/(" + "|".join(re.escape(s) for s in sorted(SLACK_ALLOWED_SKILLS)) + r")"
    r"(?:\s+(.+))?\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# NL intent extraction -- Claude response block
# ---------------------------------------------------------------------------

_INTENT_RE = re.compile(
    r"<skill-intent>\s*skill:\s*(\S+)" r"(?:\s+args:\s*(.*?))?\s*</skill-intent>",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Queue entry
# ---------------------------------------------------------------------------

QUEUE_FILENAME = "slack-queue.json"
RESULTS_DIR = "slack-results"
_PRUNE_AGE_S = 86400  # 24 hours


@dataclass
class QueueEntry:
    """A single entry in the Slack skill queue."""

    id: str
    skill: str
    args: str
    requested_by: str
    auth_level: str
    channel: str
    thread_ts: str
    requested_at: str
    status: str  # pending | running | completed | failed
    result_summary: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "skill": self.skill,
            "args": self.args,
            "requested_by": self.requested_by,
            "auth_level": self.auth_level,
            "channel": self.channel,
            "thread_ts": self.thread_ts,
            "requested_at": self.requested_at,
            "status": self.status,
            "result_summary": self.result_summary,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QueueEntry:
        return cls(
            id=d.get("id", ""),
            skill=d.get("skill", ""),
            args=d.get("args", ""),
            requested_by=d.get("requested_by", ""),
            auth_level=d.get("auth_level", ""),
            channel=d.get("channel", ""),
            thread_ts=d.get("thread_ts", ""),
            requested_at=d.get("requested_at", ""),
            status=d.get("status", "pending"),
            result_summary=d.get("result_summary", ""),
            completed_at=d.get("completed_at", ""),
        )


# ---------------------------------------------------------------------------
# Permission check
# ---------------------------------------------------------------------------


def check_permission(skill: str, auth_level: str) -> tuple[bool, str]:
    """Check whether a user at the given auth level can invoke a skill.

    Returns:
        (allowed, reason) -- reason is empty on success.
    """
    if skill not in SLACK_ALLOWED_SKILLS:
        return False, f"Skill `{skill}` is not available via Slack."

    allowed_skills = SKILL_AUTH_MATRIX.get(auth_level, frozenset())
    if skill not in allowed_skills:
        return False, (
            f"Your access level (`{auth_level}`) does not permit `/{skill}`. "
            f"Available skills: {', '.join(sorted(allowed_skills)) or 'none'}."
        )

    return True, ""


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------


def detect_explicit_command(text: str) -> tuple[str | None, str]:
    """Parse an explicit /command from message text.

    Returns:
        (skill, args) -- skill is None if no command found.
    """
    m = _COMMAND_RE.match(text)
    if not m:
        return None, ""
    skill = m.group(1).lower()
    args = (m.group(2) or "").strip()
    return skill, args


# ---------------------------------------------------------------------------
# NL intent extraction
# ---------------------------------------------------------------------------


def extract_skill_intent(
    response: str,
) -> tuple[str | None, str | None, str]:
    """Extract a skill-intent block from a Claude response.

    Claude is prompted to include <skill-intent>skill: X args: Y</skill-intent>
    when it detects the user wants to run a vault skill.

    Returns:
        (skill, args, cleaned_response) -- cleaned_response has the block removed.
    """
    m = _INTENT_RE.search(response)
    if not m:
        return None, None, response

    skill = m.group(1).lower().lstrip("/")
    args = (m.group(2) or "").strip() or None
    cleaned = response[: m.start()] + response[m.end() :]
    cleaned = cleaned.strip()
    return skill, args, cleaned


# ---------------------------------------------------------------------------
# Queue I/O
# ---------------------------------------------------------------------------


def _queue_path(vault_path: Path) -> Path:
    return vault_path / "ops" / "daemon" / QUEUE_FILENAME


def _results_path(vault_path: Path) -> Path:
    return vault_path / "ops" / "daemon" / RESULTS_DIR


def read_queue(vault_path: Path) -> list[QueueEntry]:
    """Read all entries from the Slack queue file."""
    qp = _queue_path(vault_path)
    if not qp.exists():
        return []
    try:
        data = json.loads(qp.read_text())
        if not isinstance(data, list):
            return []
        return [QueueEntry.from_dict(d) for d in data]
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read slack queue at %s", qp)
        return []


def _write_queue(vault_path: Path, entries: list[QueueEntry]) -> None:
    """Write entries to the Slack queue file, pruning old completed entries."""
    qp = _queue_path(vault_path)
    qp.parent.mkdir(parents=True, exist_ok=True)

    now = time.time()
    pruned = []
    for e in entries:
        if e.status in ("completed", "failed") and e.completed_at:
            try:
                completed_ts = datetime.fromisoformat(e.completed_at).timestamp()
                if now - completed_ts > _PRUNE_AGE_S:
                    continue
            except (ValueError, OSError):
                pass
        pruned.append(e)

    qp.write_text(
        json.dumps([e.to_dict() for e in pruned], indent=2, ensure_ascii=False)
    )


def queue_request(
    vault_path: Path,
    skill: str,
    args: str,
    user_id: str,
    auth_level: str,
    channel: str,
    thread_ts: str,
) -> str:
    """Add a skill request to the Slack queue.

    Returns:
        The entry ID.
    """
    entry_id = uuid.uuid4().hex[:12]
    now = datetime.now(UTC).isoformat()
    entry = QueueEntry(
        id=entry_id,
        skill=skill,
        args=args,
        requested_by=user_id,
        auth_level=auth_level,
        channel=channel,
        thread_ts=thread_ts,
        requested_at=now,
        status="pending",
    )

    entries = read_queue(vault_path)
    entries.append(entry)
    _write_queue(vault_path, entries)

    logger.info(
        "Queued Slack skill request: id=%s skill=%s user=%s",
        entry_id,
        skill,
        user_id,
    )
    return entry_id


# ---------------------------------------------------------------------------
# Task completion (called by daemon post-hook)
# ---------------------------------------------------------------------------


def complete_task(
    vault_path: Path,
    task_key: str,
    outcome: str,
    elapsed_s: int,
) -> None:
    """Mark a Slack queue entry as completed/failed and post a reply.

    Args:
        vault_path: Path to the vault root.
        task_key: Daemon task key (format: "slack-{entry_id}").
        outcome: "success" or "failed".
        elapsed_s: Execution time in seconds.
    """
    entry_id = task_key.removeprefix("slack-")
    entries = read_queue(vault_path)

    target = None
    for e in entries:
        if e.id == entry_id:
            target = e
            break

    if target is None:
        logger.warning("Slack queue entry not found for task_key=%s", task_key)
        return

    target.status = "completed" if outcome == "success" else "failed"
    target.completed_at = datetime.now(UTC).isoformat()

    # Try to read result file for read-only skills
    result_file = _results_path(vault_path) / f"{entry_id}.md"
    if result_file.exists():
        try:
            content = result_file.read_text()
            # Truncate to reasonable Slack message size
            target.result_summary = content[:3000]
        except OSError:
            pass

    if not target.result_summary:
        if outcome == "success":
            target.result_summary = f"/{target.skill} completed in {elapsed_s}s."
        else:
            target.result_summary = f"/{target.skill} failed after {elapsed_s}s."

    _write_queue(vault_path, entries)

    # Post Slack notification
    _post_completion_reply(vault_path, target, elapsed_s)


def _post_completion_reply(
    vault_path: Path,
    entry: QueueEntry,
    elapsed_s: int,
) -> None:
    """Post a completion reply in the original Slack thread."""
    try:
        from engram_r.slack_formatter import format_slack_skill_complete
        from engram_r.slack_notify import _get_client

        client = _get_client()
        if client is None:
            logger.debug("No Slack client available for completion reply")
            return

        text, blocks = format_slack_skill_complete(
            skill=entry.skill,
            entry_id=entry.id,
            outcome=entry.status,
            elapsed_s=elapsed_s,
            result_summary=entry.result_summary,
        )

        # PII scrub
        from engram_r.pii_filter import scrub_outbound

        text = scrub_outbound(text)
        for block in blocks:
            txt = block.get("text", {})
            if isinstance(txt, dict) and txt.get("text"):
                txt["text"] = scrub_outbound(txt["text"])

        client.chat_postMessage(
            channel=entry.channel,
            thread_ts=entry.thread_ts,
            text=text,
            blocks=blocks,
        )
    except Exception:
        logger.exception("Failed to post Slack completion reply for %s", entry.id)


# ---------------------------------------------------------------------------
# Daemon integration -- called by daemon_scheduler
# ---------------------------------------------------------------------------


def check_slack_queue(
    vault_path: Path,
) -> dict[str, Any] | None:
    """Find the first pending entry in the Slack queue.

    Returns:
        Dict with 'entry' (QueueEntry) and queue metadata, or None.
    """
    entries = read_queue(vault_path)
    for entry in entries:
        if entry.status == "pending":
            return {"entry": entry, "vault_path": vault_path}
    return None


def mark_queue_entry_running(vault_path: Path, entry_id: str) -> None:
    """Mark a queue entry as running (called when daemon picks it up)."""
    entries = read_queue(vault_path)
    for e in entries:
        if e.id == entry_id:
            e.status = "running"
            break
    _write_queue(vault_path, entries)
