"""Metabolic indicators for daemon self-regulation.

7 indicators in 3 tiers govern whether the daemon should create
(generate/evolve) or consolidate (reflect/reweave/verify).

Tier 1 (Governance): QPR, CMR, TPV -- auto-suppress daemon generative tasks.
Tier 2 (Awareness): HCR, GCR, IPR -- user-facing signals via /next.
Tier 3 (Observational): VDR -- logged, no automated action.

Pure Python -- no network I/O. Reuses existing vault filesystem conventions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engram_r.frontmatter import FM_RE as _FM_RE, read_frontmatter as _read_frontmatter

logger = logging.getLogger(__name__)


def _normalize_queue_data(raw: dict | list | None) -> dict:
    """Normalize queue data to ``{"tasks": [...]}``.

    Handles two on-disk formats:
    - Legacy dict: ``{"tasks": [...]}`` -- returned as-is.
    - Current list: ``[{...}, ...]`` -- wrapped in ``{"tasks": [...]}``.
    """
    if raw is None:
        return {"tasks": []}
    if isinstance(raw, list):
        return {"tasks": raw}
    if isinstance(raw, dict):
        return raw
    return {"tasks": []}


# Tier classification for alarm keys
ALARM_TIERS: dict[str, int] = {
    "qpr_critical": 1,
    "cmr_hot": 1,
    "tpv_stalled": 1,
    "hcr_low": 2,
    "gcr_fragmented": 2,
    "ipr_overflow": 2,
}


@dataclass
class MetabolicState:
    """Snapshot of 7 metabolic indicators plus alarm classification.

    Tier 1 (Governance -- auto-suppress daemon generative tasks):
        qpr: Queue Pressure Ratio -- days of backlog at current processing rate.
        cmr: Creation:Maintenance Ratio -- new notes vs maintained per week.
        tpv: Throughput Velocity -- claims processed per day.

    Tier 2 (Awareness -- user-facing signals via /next):
        hcr: Hypothesis Conversion Rate -- % with empirical engagement.
        gcr: Graph Connectivity Ratio -- 1 - (orphans / total_notes).
        ipr: Inbox Pressure Ratio -- inbox growth rate / processing rate.

    Tier 3 (Observational -- logged, no automated action):
        vdr: Verification Debt Ratio -- % of claims not human-verified.

    alarm_keys: Which indicators are in alarm state.
    total_notes: Total note count (used for empty-vault gating).
    total_hypotheses: Hypothesis count (used for HCR gating).
    """

    qpr: float = 0.0
    cmr: float = 0.0
    tpv: float = 0.0
    hcr: float = 0.0
    gcr: float = 1.0
    ipr: float = 0.0
    vdr: float = 0.0
    maintenance_count: int = 0
    alarm_keys: list[str] = field(default_factory=list)
    total_notes: int = 0
    total_hypotheses: int = 0


# ---------------------------------------------------------------------------
# Individual indicator computations
# ---------------------------------------------------------------------------


def compute_qpr(
    queue_data: dict | None = None,
    queue_path: Path | None = None,
    lookback_days: int = 7,
) -> float:
    """Compute Queue Pressure Ratio: days of backlog at current rate.

    Args:
        queue_data: Pre-loaded queue.json dict, or None to read from disk.
        queue_path: Path to queue.json (used if queue_data is None).
        lookback_days: Window for computing daily completion rate.

    Returns:
        QPR value (days of backlog). Higher = more pressure.
    """
    if queue_data is None:
        if queue_path is None or not queue_path.is_file():
            return 0.0
        try:
            queue_data = json.loads(queue_path.read_text())
        except (json.JSONDecodeError, OSError):
            return 0.0

    queue_data = _normalize_queue_data(queue_data)
    tasks = queue_data.get("tasks", [])
    if not tasks:
        return 0.0

    backlog = sum(1 for t in tasks if t.get("status") not in ("done", "archived"))
    if backlog == 0:
        return 0.0

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    completed_recent = 0
    for t in tasks:
        completed_str = t.get("completed")
        if not completed_str:
            continue
        try:
            completed_dt = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
            if completed_dt >= cutoff:
                completed_recent += 1
        except (ValueError, TypeError):
            continue

    daily_rate = max(completed_recent / lookback_days, 0.1)
    return backlog / daily_rate


def compute_vdr(notes_dir: Path) -> float:
    """Compute Verification Debt Ratio: % of claims not human-verified.

    Args:
        notes_dir: Path to notes/ directory.

    Returns:
        VDR as percentage (0-100). Higher = more debt.
    """
    if not notes_dir.is_dir():
        return 0.0

    total = 0
    human_verified = 0
    for f in notes_dir.iterdir():
        if f.suffix != ".md" or f.name == "_index.md":
            continue
        total += 1
        fm = _read_frontmatter(f)
        if fm.get("verified_by") == "human":
            human_verified += 1

    if total == 0:
        return 0.0
    return (total - human_verified) / total * 100


def compute_cmr(
    notes_dir: Path,
    queue_data: dict | None = None,
    queue_path: Path | None = None,
    lookback_days: int = 7,
) -> tuple[float, int]:
    """Compute Creation:Maintenance Ratio over the lookback window.

    Creation = notes with `created` date in last N days.
    Maintenance = queue tasks with type "claim" and completed_phases
    containing "reflect" or "reweave", completed in last N days.

    Args:
        notes_dir: Path to notes/ directory.
        queue_data: Pre-loaded queue.json dict.
        queue_path: Path to queue.json (used if queue_data is None).
        lookback_days: Window for rate computations.

    Returns:
        Tuple of (CMR value, raw maintenance count).
        CMR is higher when creation-heavy.
    """
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    cutoff_date = cutoff.date()

    # Count recent creations
    creation = 0
    if notes_dir.is_dir():
        for f in notes_dir.iterdir():
            if f.suffix != ".md" or f.name == "_index.md":
                continue
            fm = _read_frontmatter(f)
            created_str = fm.get("created", "")
            if created_str:
                try:
                    created_date = datetime.fromisoformat(str(created_str)).date()
                    if created_date >= cutoff_date:
                        creation += 1
                        continue
                except (ValueError, TypeError):
                    pass
            # Fallback: file ctime
            try:
                ctime = datetime.fromtimestamp(f.stat().st_ctime, tz=UTC)
                if ctime >= cutoff:
                    creation += 1
            except OSError:
                pass

    # Count recent maintenance completions
    if queue_data is None:
        if queue_path is not None and queue_path.is_file():
            try:
                queue_data = json.loads(queue_path.read_text())
            except (json.JSONDecodeError, OSError):
                queue_data = None
        else:
            queue_data = None

    queue_data = _normalize_queue_data(queue_data)
    maintenance = 0
    for t in queue_data.get("tasks", []):
        if t.get("type") != "claim":
            continue
        phases = t.get("completed_phases", [])
        if not isinstance(phases, list):
            continue
        if not any(p in phases for p in ("reflect", "reweave")):
            continue
        completed_str = t.get("completed")
        if not completed_str:
            continue
        try:
            completed_dt = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
            if completed_dt >= cutoff:
                maintenance += 1
        except (ValueError, TypeError):
            continue

    return max(creation, 1) / max(maintenance, 1), maintenance


def compute_hcr(hypotheses_dir: Path) -> tuple[float, int]:
    """Compute Hypothesis Conversion Rate: % with empirical engagement.

    Converted = status in {tested-positive, tested-negative, executing,
    sap-written}.

    Args:
        hypotheses_dir: Path to _research/hypotheses/ directory.

    Returns:
        Tuple of (HCR percentage 0-100, total hypothesis count).
    """
    if not hypotheses_dir.is_dir():
        return 0.0, 0

    converted_statuses = {
        "tested-positive",
        "tested-negative",
        "executing",
        "sap-written",
    }

    total = 0
    converted = 0
    for f in hypotheses_dir.iterdir():
        if f.suffix != ".md" or f.name.startswith("_"):
            continue
        fm = _read_frontmatter(f)
        if fm.get("type") != "hypothesis":
            continue
        total += 1
        status = str(fm.get("status", "")).strip()
        if status in converted_statuses:
            converted += 1

    if total == 0:
        return 0.0, 0
    return converted / total * 100, total


def compute_tpv(
    queue_data: dict | None = None,
    queue_path: Path | None = None,
    lookback_days: int = 7,
) -> float:
    """Compute Throughput Velocity: claims processed per day.

    Counts queue tasks with status "done" completed within the lookback window.

    Args:
        queue_data: Pre-loaded queue.json dict, or None to read from disk.
        queue_path: Path to queue.json (used if queue_data is None).
        lookback_days: Window for computing daily rate.

    Returns:
        TPV value (completions per day). Higher = more throughput.
    """
    if queue_data is None:
        if queue_path is None or not queue_path.is_file():
            return 0.0
        try:
            queue_data = json.loads(queue_path.read_text())
        except (json.JSONDecodeError, OSError):
            return 0.0

    queue_data = _normalize_queue_data(queue_data)
    tasks = queue_data.get("tasks", [])
    if not tasks:
        return 0.0

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    completed_recent = 0
    for t in tasks:
        if t.get("status") not in ("done", "archived"):
            continue
        completed_str = t.get("completed")
        if not completed_str:
            continue
        try:
            completed_dt = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
            if completed_dt >= cutoff:
                completed_recent += 1
        except (ValueError, TypeError):
            continue

    return completed_recent / lookback_days


def compute_gcr(orphan_count: int, total_notes: int) -> float:
    """Compute Graph Connectivity Ratio: 1 - (orphans / total_notes).

    Takes pre-computed counts to avoid double-scanning the vault.

    Args:
        orphan_count: Number of notes with zero incoming links.
        total_notes: Total number of notes (excluding _index.md).

    Returns:
        GCR value (0.0 to 1.0). Higher = more connected. 1.0 when no orphans.
    """
    if total_notes == 0:
        return 1.0
    return 1.0 - (orphan_count / total_notes)


def compute_ipr(
    inbox_dir: Path,
    notes_dir: Path,
    lookback_days: int = 7,
) -> float:
    """Compute Inbox Pressure Ratio: inbox growth rate / processing rate.

    Uses file ctime for inbox items and note created dates for processing.

    Args:
        inbox_dir: Path to inbox/ directory.
        notes_dir: Path to notes/ directory.
        lookback_days: Window for rate computations.

    Returns:
        IPR value. Higher = more inbox pressure. 0 when balanced or empty.
    """
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    cutoff_date = cutoff.date()

    # Count recent inbox arrivals
    inbox_recent = 0
    if inbox_dir.is_dir():
        for f in inbox_dir.iterdir():
            if f.suffix != ".md" or f.name.startswith("."):
                continue
            try:
                ctime = datetime.fromtimestamp(f.stat().st_ctime, tz=UTC)
                if ctime >= cutoff:
                    inbox_recent += 1
            except OSError:
                pass

    # Count recent note creations (processing output)
    processed_recent = 0
    if notes_dir.is_dir():
        for f in notes_dir.iterdir():
            if f.suffix != ".md" or f.name == "_index.md":
                continue
            fm = _read_frontmatter(f)
            created_str = fm.get("created", "")
            if created_str:
                try:
                    created_date = datetime.fromisoformat(str(created_str)).date()
                    if created_date >= cutoff_date:
                        processed_recent += 1
                        continue
                except (ValueError, TypeError):
                    pass
            try:
                ctime = datetime.fromtimestamp(f.stat().st_ctime, tz=UTC)
                if ctime >= cutoff:
                    processed_recent += 1
            except OSError:
                pass

    inbox_rate = inbox_recent / lookback_days
    processing_rate = max(processed_recent / lookback_days, 0.1)
    return inbox_rate / processing_rate


def _count_notes(notes_dir: Path) -> int:
    """Count .md files in notes/ excluding _index.md."""
    if not notes_dir.is_dir():
        return 0
    return sum(
        1 for f in notes_dir.iterdir() if f.suffix == ".md" and f.name != "_index.md"
    )


# ---------------------------------------------------------------------------
# Alarm classification
# ---------------------------------------------------------------------------


def classify_alarms(
    state: MetabolicState,
    *,
    qpr_critical: float = 3.0,
    cmr_hot: float = 10.0,
    tpv_stalled: float = 0.1,
    hcr_redirect: float = 15.0,
    gcr_fragmented: float = 0.3,
    ipr_overflow: float = 3.0,
    min_notes_for_tpv: int = 5,
    min_hypotheses_for_hcr: int = 3,
) -> list[str]:
    """Classify which metabolic indicators are in alarm state.

    Args:
        state: Computed metabolic state.
        qpr_critical: QPR threshold for generation halt.
        cmr_hot: CMR threshold for running hot.
        tpv_stalled: TPV threshold (below = stalled throughput).
        hcr_redirect: HCR threshold (below = redirect to SAP).
        gcr_fragmented: GCR threshold (below = fragmented graph).
        ipr_overflow: IPR threshold (above = inbox overflowing).
        min_notes_for_tpv: Minimum notes before TPV alarm can fire.
        min_hypotheses_for_hcr: Minimum hypotheses before HCR alarm can fire.

    Returns:
        List of alarm keys (e.g. ["qpr_critical", "cmr_hot"]).
    """
    alarms: list[str] = []

    # Tier 1: Governance
    if state.qpr > qpr_critical:
        alarms.append("qpr_critical")
    if state.cmr > cmr_hot:
        alarms.append("cmr_hot")
    if state.tpv < tpv_stalled and state.total_notes >= min_notes_for_tpv:
        alarms.append("tpv_stalled")

    # Tier 2: Awareness
    if state.total_hypotheses >= min_hypotheses_for_hcr and state.hcr < hcr_redirect:
        alarms.append("hcr_low")
    if state.gcr < gcr_fragmented:
        alarms.append("gcr_fragmented")
    if state.ipr > ipr_overflow:
        alarms.append("ipr_overflow")

    # VDR (Tier 3) is informational only -- never triggers alarms
    return alarms


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_metabolic_state(
    vault_path: Path,
    queue_data: dict | list | None = None,
    lookback_days: int = 7,
    orphan_count: int | None = None,
    qpr_critical: float = 3.0,
    cmr_hot: float = 10.0,
    tpv_stalled: float = 0.1,
    hcr_redirect: float = 15.0,
    gcr_fragmented: float = 0.3,
    ipr_overflow: float = 3.0,
) -> MetabolicState:
    """Compute all 7 metabolic indicators from vault filesystem.

    Args:
        vault_path: Root of the Obsidian vault.
        queue_data: Pre-loaded queue.json dict, or None to read from disk.
        lookback_days: Window for rate computations.
        orphan_count: Pre-computed orphan count (avoids double-scanning).
            If None, GCR defaults to 1.0 (no orphan data available).
        qpr_critical: QPR alarm threshold.
        cmr_hot: CMR alarm threshold.
        tpv_stalled: TPV alarm threshold (below triggers).
        hcr_redirect: HCR alarm threshold (below triggers).
        gcr_fragmented: GCR alarm threshold (below triggers).
        ipr_overflow: IPR alarm threshold (above triggers).

    Returns:
        Populated MetabolicState with alarm classification.
    """
    notes_dir = vault_path / "notes"
    hypotheses_dir = vault_path / "_research" / "hypotheses"
    inbox_dir = vault_path / "inbox"
    queue_path = vault_path / "ops" / "queue" / "queue.json"

    total_notes = _count_notes(notes_dir)
    hcr_value, total_hypotheses = compute_hcr(hypotheses_dir)

    # GCR: use pre-computed orphan_count if available
    if orphan_count is not None:
        gcr_value = compute_gcr(orphan_count, total_notes)
    else:
        gcr_value = 1.0  # Default when orphan data not available

    cmr_value, maintenance_count = compute_cmr(
        notes_dir=notes_dir,
        queue_data=queue_data,
        queue_path=queue_path,
        lookback_days=lookback_days,
    )

    state = MetabolicState(
        qpr=compute_qpr(
            queue_data=queue_data,
            queue_path=queue_path,
            lookback_days=lookback_days,
        ),
        cmr=cmr_value,
        tpv=compute_tpv(
            queue_data=queue_data,
            queue_path=queue_path,
            lookback_days=lookback_days,
        ),
        hcr=hcr_value,
        gcr=gcr_value,
        ipr=compute_ipr(
            inbox_dir=inbox_dir,
            notes_dir=notes_dir,
            lookback_days=lookback_days,
        ),
        vdr=compute_vdr(notes_dir),
        maintenance_count=maintenance_count,
        total_notes=total_notes,
        total_hypotheses=total_hypotheses,
    )
    state.alarm_keys = classify_alarms(
        state,
        qpr_critical=qpr_critical,
        cmr_hot=cmr_hot,
        tpv_stalled=tpv_stalled,
        hcr_redirect=hcr_redirect,
        gcr_fragmented=gcr_fragmented,
        ipr_overflow=ipr_overflow,
    )
    return state


# ---------------------------------------------------------------------------
# CLI entrypoint (for /stats skill)
# ---------------------------------------------------------------------------


def main() -> None:
    """Print metabolic state as JSON for a given vault path."""
    import sys

    if len(sys.argv) < 2:
        msg = "Usage: python -m engram_r.metabolic_indicators <vault>"
        print(json.dumps({"error": msg}))
        sys.exit(1)

    vault_path = Path(sys.argv[1])
    if not vault_path.is_dir():
        print(json.dumps({"error": f"Not a directory: {vault_path}"}))
        sys.exit(1)

    state = compute_metabolic_state(vault_path)
    print(
        json.dumps(
            {
                "qpr": round(state.qpr, 1),
                "cmr": round(state.cmr, 1),
                "tpv": round(state.tpv, 2),
                "hcr": round(state.hcr, 1),
                "gcr": round(state.gcr, 2),
                "ipr": round(state.ipr, 1),
                "vdr": round(state.vdr, 1),
                "alarm_keys": state.alarm_keys,
                "total_notes": state.total_notes,
                "total_hypotheses": state.total_hypotheses,
            }
        )
    )


if __name__ == "__main__":
    main()
