"""Historical persistence and trend analysis for metabolic indicators.

Stores snapshots to ops/metabolic/history.yaml and computes trends
across sessions. Atomic writes (tmp + rename) prevent corruption.

Pure Python -- no network I/O. Uses only stdlib + yaml.
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

import yaml

from engram_r.metabolic_indicators import MetabolicState

logger = logging.getLogger(__name__)

HISTORY_FILENAME = "history.yaml"
LATEST_FILENAME = "latest.yaml"
METABOLIC_DIR = "ops/metabolic"

# Indicators tracked in snapshots
INDICATOR_NAMES = ("qpr", "cmr", "tpv", "hcr", "gcr", "ipr", "vdr")


@dataclass
class MetabolicSnapshot:
    """A single point-in-time metabolic measurement."""

    timestamp: str
    session_id: str
    indicators: dict[str, float] = field(default_factory=dict)
    alarm_keys: list[str] = field(default_factory=list)


@dataclass
class MetabolicTrend:
    """Trend analysis for a single indicator."""

    indicator: str
    current: float
    previous: float | None = None
    delta: float | None = None
    direction: str = "stable"  # "improving" | "stable" | "declining"
    avg_7: float | None = None
    avg_30: float | None = None


def _snapshot_from_state(state: MetabolicState, session_id: str) -> MetabolicSnapshot:
    """Create a snapshot from a MetabolicState."""
    return MetabolicSnapshot(
        timestamp=datetime.now(UTC).isoformat(),
        session_id=session_id,
        indicators={
            "qpr": round(state.qpr, 2),
            "cmr": round(state.cmr, 2),
            "tpv": round(state.tpv, 3),
            "hcr": round(state.hcr, 1),
            "gcr": round(state.gcr, 3),
            "ipr": round(state.ipr, 2),
            "vdr": round(state.vdr, 1),
        },
        alarm_keys=list(state.alarm_keys),
    )


def _atomic_write_yaml(path: Path, data: list[dict]) -> None:
    """Write YAML atomically via tmp + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=".metabolic_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def save_snapshot(
    vault_path: Path,
    state: MetabolicState,
    session_id: str,
    max_snapshots: int = 90,
) -> None:
    """Save a metabolic snapshot to history and latest cache.

    Appends to ops/metabolic/history.yaml and writes ops/metabolic/latest.yaml.
    Trims history to max_snapshots entries (oldest removed first).

    Args:
        vault_path: Root of the Obsidian vault.
        state: Current MetabolicState.
        session_id: Current session identifier.
        max_snapshots: Maximum snapshots to retain.
    """
    metabolic_dir = vault_path / METABOLIC_DIR
    history_path = metabolic_dir / HISTORY_FILENAME
    latest_path = metabolic_dir / LATEST_FILENAME

    snapshot = _snapshot_from_state(state, session_id)
    snapshot_dict = asdict(snapshot)

    # Load existing history
    history = load_history(vault_path)
    history_dicts = [asdict(s) for s in history]
    history_dicts.append(snapshot_dict)

    # Trim to max_snapshots
    if len(history_dicts) > max_snapshots:
        history_dicts = history_dicts[-max_snapshots:]

    # Write atomically
    _atomic_write_yaml(history_path, history_dicts)
    _atomic_write_yaml(latest_path, [snapshot_dict])

    logger.debug(
        "Saved metabolic snapshot: %d indicators, %d alarms, %d total snapshots",
        len(snapshot.indicators),
        len(snapshot.alarm_keys),
        len(history_dicts),
    )


def load_history(vault_path: Path) -> list[MetabolicSnapshot]:
    """Load metabolic history from ops/metabolic/history.yaml.

    Args:
        vault_path: Root of the Obsidian vault.

    Returns:
        List of MetabolicSnapshot ordered oldest to newest. Empty list if
        no history exists or file is malformed.
    """
    history_path = vault_path / METABOLIC_DIR / HISTORY_FILENAME
    if not history_path.is_file():
        return []

    try:
        raw = yaml.safe_load(history_path.read_text())
    except (yaml.YAMLError, OSError):
        logger.warning("Failed to read metabolic history: %s", history_path)
        return []

    if not isinstance(raw, list):
        return []

    snapshots = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            snapshots.append(
                MetabolicSnapshot(
                    timestamp=entry.get("timestamp", ""),
                    session_id=entry.get("session_id", ""),
                    indicators=entry.get("indicators", {}),
                    alarm_keys=entry.get("alarm_keys", []),
                )
            )
        except (TypeError, ValueError):
            continue

    return snapshots


def load_latest(vault_path: Path) -> MetabolicSnapshot | None:
    """Load the latest cached snapshot from ops/metabolic/latest.yaml.

    Args:
        vault_path: Root of the Obsidian vault.

    Returns:
        Most recent MetabolicSnapshot, or None if not available.
    """
    latest_path = vault_path / METABOLIC_DIR / LATEST_FILENAME
    if not latest_path.is_file():
        return None

    try:
        raw = yaml.safe_load(latest_path.read_text())
    except (yaml.YAMLError, OSError):
        return None

    if not isinstance(raw, list) or not raw:
        return None

    entry = raw[0]
    if not isinstance(entry, dict):
        return None

    return MetabolicSnapshot(
        timestamp=entry.get("timestamp", ""),
        session_id=entry.get("session_id", ""),
        indicators=entry.get("indicators", {}),
        alarm_keys=entry.get("alarm_keys", []),
    )


def _direction_for(indicator: str, current: float, previous: float) -> str:
    """Determine trend direction based on indicator semantics.

    For "lower is better" indicators (qpr, cmr, ipr, vdr): decrease = improving.
    For "higher is better" indicators (tpv, gcr): increase = improving.
    HCR: higher = improving.
    """
    delta = current - previous
    threshold = 0.01  # Ignore tiny fluctuations

    if abs(delta) < threshold:
        return "stable"

    # Indicators where lower is better
    lower_is_better = {"qpr", "cmr", "ipr", "vdr"}
    if indicator in lower_is_better:
        return "improving" if delta < 0 else "declining"
    # Indicators where higher is better (tpv, gcr, hcr)
    return "improving" if delta > 0 else "declining"


def compute_trends(
    current: MetabolicState,
    history: list[MetabolicSnapshot],
) -> list[MetabolicTrend]:
    """Compute trend analysis for each indicator.

    Compares current values against the most recent historical snapshot
    and computes rolling averages over 7 and 30 entries.

    Args:
        current: Current MetabolicState.
        history: Historical snapshots (oldest first).

    Returns:
        List of MetabolicTrend, one per indicator.
    """
    current_values = {
        "qpr": current.qpr,
        "cmr": current.cmr,
        "tpv": current.tpv,
        "hcr": current.hcr,
        "gcr": current.gcr,
        "ipr": current.ipr,
        "vdr": current.vdr,
    }

    trends = []
    for name in INDICATOR_NAMES:
        cur = current_values[name]
        trend = MetabolicTrend(indicator=name, current=cur)

        if history:
            # Previous value from most recent snapshot
            prev_snap = history[-1]
            prev_val = prev_snap.indicators.get(name)
            if prev_val is not None:
                trend.previous = prev_val
                trend.delta = round(cur - prev_val, 4)
                trend.direction = _direction_for(name, cur, prev_val)

            # Rolling averages
            all_vals = [
                s.indicators.get(name)
                for s in history
                if s.indicators.get(name) is not None
            ]
            if len(all_vals) >= 2:
                trend.avg_7 = round(mean(all_vals[-7:]), 4)
            if len(all_vals) >= 7:
                trend.avg_30 = round(mean(all_vals[-30:]), 4)

        trends.append(trend)

    return trends


def format_trend_line(trends: list[MetabolicTrend]) -> str:
    """Format a condensed trend summary line for session orient.

    Only includes non-stable trends.

    Args:
        trends: List of MetabolicTrend from compute_trends.

    Returns:
        Formatted string like "QPR improving, CMR stable" or empty string.
    """
    parts = []
    for t in trends:
        if t.direction != "stable" and t.previous is not None:
            parts.append(f"{t.indicator.upper()} {t.direction}")

    if not parts:
        return ""
    return "Trend: " + ", ".join(parts)
