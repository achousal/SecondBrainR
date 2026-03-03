"""Structured audit log for the daemon scheduler.

Records each decision cycle as a JSONL entry -- what was evaluated,
which rules triggered, what was selected (or skipped), and why.
Queryable with ``jq``. No external dependencies beyond stdlib.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RuleEvaluation:
    """Result of evaluating one cascade check."""

    check_name: str
    triggered: bool
    skip_reason: str = ""
    candidate_skill: str = ""
    candidate_key: str = ""


@dataclass
class AuditEntry:
    """One daemon decision cycle."""

    timestamp: str
    type: str = "selection"
    selected_task: str = ""
    selected_skill: str = ""
    selected_tier: int = -1
    metabolic_suppressed: bool = False
    vault_summary: dict = field(default_factory=dict)
    rules_evaluated: list[RuleEvaluation] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON."""
        d = asdict(self)
        return d


@dataclass
class AuditOutcome:
    """Post-execution outcome record for a daemon task.

    Written as a separate JSONL entry (``type: "outcome"``) after the task
    process completes.  Captures the vault-state delta so silent failures
    (exit 0, no change) are visible in the audit log.
    """

    timestamp: str
    task_key: str
    skill: str
    outcome: str  # "success" | "no_change" | "error"
    duration_seconds: int
    vault_summary_before: dict = field(default_factory=dict)
    vault_summary_after: dict = field(default_factory=dict)
    changed_keys: list[str] = field(default_factory=list)
    type: str = "outcome"

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON."""
        return asdict(self)


def append_audit_entry(entry: AuditEntry, log_path: Path) -> None:
    """Atomically append an audit entry to a JSONL file.

    Creates parent directories if they do not exist. Uses write-to-temp
    + append to minimize data loss on crash.

    Args:
        entry: The audit entry to write.
        log_path: Path to the JSONL file (e.g. ops/daemon/logs/audit.jsonl).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":"))

    # Write to temp file first, then append -- reduces risk of partial writes
    fd, tmp = tempfile.mkstemp(
        dir=str(log_path.parent), prefix=".audit-", suffix=".tmp"
    )
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
        os.close(fd)
        fd = -1  # mark as closed
        # Append temp content to the log file
        with (
            open(log_path, "a", encoding="utf-8") as f,
            open(tmp, encoding="utf-8") as t,
        ):
            f.write(t.read())
    except OSError:
        logger.warning("Failed to write audit entry to %s", log_path, exc_info=True)
    finally:
        if fd >= 0:
            os.close(fd)
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def append_outcome(outcome: AuditOutcome, log_path: Path) -> None:
    """Append a post-execution outcome entry to the audit JSONL file.

    Uses the same atomic write strategy as :func:`append_audit_entry`.

    Args:
        outcome: The outcome record to write.
        log_path: Path to the JSONL file (e.g. ops/daemon/logs/audit.jsonl).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(outcome.to_dict(), ensure_ascii=False, separators=(",", ":"))

    fd, tmp = tempfile.mkstemp(
        dir=str(log_path.parent), prefix=".audit-", suffix=".tmp"
    )
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
        os.close(fd)
        fd = -1
        with (
            open(log_path, "a", encoding="utf-8") as f,
            open(tmp, encoding="utf-8") as t,
        ):
            f.write(t.read())
    except OSError:
        logger.warning("Failed to write outcome entry to %s", log_path, exc_info=True)
    finally:
        if fd >= 0:
            os.close(fd)
        with contextlib.suppress(OSError):
            os.unlink(tmp)
