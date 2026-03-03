"""Skill-level failure tracking with exponential backoff for the daemon.

Reads and writes ``ops/daemon/skill-backoff.json``. Pure Python, no
external dependencies. The daemon shell layer calls these functions to
decide whether a skill should be retried or is still cooling down.

Escalation schedule:
    - 3 consecutive failures  -> 30 min backoff
    - 6 consecutive failures  -> 60 min backoff
    - 9+ consecutive failures -> capped at 2 h
    Success resets the counter for that skill.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def read_backoff(path: Path) -> dict:
    """Read the backoff state file. Returns {} if missing or corrupt."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt backoff file at %s, resetting", path)
        return {}


def _write_backoff(state: dict, path: Path) -> None:
    """Write backoff state atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(path)
    except OSError:
        logger.warning("Failed to write backoff state to %s", path, exc_info=True)


def record_failure(
    skill: str,
    path: Path,
    threshold: int = 3,
    initial_s: int = 1800,
    max_s: int = 7200,
) -> None:
    """Record a skill failure and possibly activate backoff.

    Args:
        skill: Skill name (e.g. "tournament").
        path: Path to skill-backoff.json.
        threshold: Number of consecutive failures before backoff activates.
        initial_s: Initial backoff duration in seconds (default 1800 = 30 min).
        max_s: Maximum backoff duration in seconds (default 7200 = 2 h).
    """
    state = read_backoff(path)
    entry = state.get(skill, {"consecutive_failures": 0})
    entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
    count = entry["consecutive_failures"]

    if count >= threshold:
        # Escalation: double for each threshold-worth of failures, capped
        multiplier = count // threshold
        duration = min(initial_s * multiplier, max_s)
        entry["backoff_until"] = time.time() + duration
        entry["backoff_duration_s"] = duration
    state[skill] = entry
    _write_backoff(state, path)


def record_success(skill: str, path: Path) -> None:
    """Record a skill success -- resets failure counter and backoff."""
    state = read_backoff(path)
    if skill in state:
        del state[skill]
        _write_backoff(state, path)


def skill_in_backoff(skill: str, path: Path) -> tuple[bool, int]:
    """Check whether a skill is currently in backoff.

    Args:
        skill: Skill name.
        path: Path to skill-backoff.json.

    Returns:
        (in_backoff, seconds_remaining). seconds_remaining is 0 when not
        in backoff.
    """
    state = read_backoff(path)
    entry = state.get(skill)
    if entry is None:
        return False, 0
    until = entry.get("backoff_until", 0)
    remaining = int(until - time.time())
    if remaining > 0:
        return True, remaining
    return False, 0
