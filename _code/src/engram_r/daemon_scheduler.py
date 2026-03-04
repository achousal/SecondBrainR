"""Research Loop Daemon scheduler.

Evaluates vault state and selects the highest-priority task to run.
Outputs a JSON task descriptor consumed by daemon.sh.
Pure Python -- uses only stdlib + yaml + existing modules. No network I/O.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from engram_r.audit import AuditEntry, RuleEvaluation, append_audit_entry
from engram_r.daemon_config import DaemonConfig, load_config
from engram_r.frontmatter import FM_RE as _FM_RE, read_frontmatter as _read_frontmatter, default_vault_path as _default_vault_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Decision ceiling -- skills the daemon is allowed to invoke autonomously.
# Hardcoded (not config-driven) so the agent cannot widen its own ceiling.
# ---------------------------------------------------------------------------

DAEMON_ALLOWED_SKILLS: frozenset[str] = frozenset(
    {
        "experiment",
        "tournament",
        "meta-review",
        "landscape",
        "rethink",
        "reflect",
        "reduce",
        "remember",
        "reweave",
        "federation-sync",
        "notify-scheduled",
        "validate",
        "verify",
        "ralph",
    }
)

# Read-only skills that Slack can queue but the daemon normally does not run.
# Separate frozenset so we never widen DAEMON_ALLOWED_SKILLS.
SLACK_READONLY_SKILLS: frozenset[str] = frozenset({"stats", "next", "graph", "tasks"})

# ---------------------------------------------------------------------------
# Frontmatter parser -- imported from engram_r.frontmatter
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


# ---------------------------------------------------------------------------
# Task descriptor -- the JSON contract between scheduler and bash runner
# ---------------------------------------------------------------------------


@dataclass
class DaemonTask:
    """A single task the daemon should execute."""

    skill: str
    args: str = ""
    model: str = "sonnet"
    tier: int = 0  # P0-P4
    prompt: str = ""
    batch_size: int = 1
    task_key: str = ""  # for idempotent marker

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Vault state snapshot
# ---------------------------------------------------------------------------


@dataclass
class GoalState:
    """Research-cycle state for a single goal."""

    goal_id: str
    hypothesis_count: int = 0
    undermatched_count: int = 0
    latest_tournament_mtime: float = 0.0
    latest_meta_review_mtime: float = 0.0
    latest_landscape_mtime: float = 0.0
    latest_hypothesis_mtime: float = 0.0
    latest_experiment_mtime: float = 0.0
    unresolved_experiment_count: int = 0

    @property
    def cycle_state(self) -> str:
        """Determine where this goal is in its research cycle."""
        if self.undermatched_count > 0:
            return "needs_tournament"
        if self.latest_tournament_mtime > self.latest_meta_review_mtime:
            return "needs_meta_review"
        if self.latest_meta_review_mtime > self.latest_landscape_mtime:
            return "needs_landscape"
        # Distinguish "has new work since last landscape" from "nothing new"
        if self.latest_hypothesis_mtime > self.latest_landscape_mtime:
            return "cycle_complete"
        return "cycle_stale"


@dataclass
class RootCause:
    """A single root cause extracted from a health report FAIL block."""

    pattern: str
    description: str
    affected_count: int = 0


@dataclass
class FailedCategory:
    """A single failed health check category with its recommendation."""

    name: str
    detail: str = ""
    recommendation: str = ""
    root_causes: list[RootCause] = field(default_factory=list)


@dataclass
class HealthReport:
    """Parsed output from /health quick."""

    fails: int = 0
    warns: int = 0
    passes: int = 0
    failed_categories: list[FailedCategory] = field(default_factory=list)
    report_path: str = ""
    stale: bool = False


@dataclass
class TaskStackItem:
    """A single item from the human task stack (ops/tasks.md)."""

    title: str
    description: str = ""
    section: str = ""  # "Active", "Pending", "Completed"
    subsection: str = ""  # e.g. "Analysis Pipeline (Wave 1)"


def parse_task_stack(vault_path: Path) -> dict[str, list[TaskStackItem]]:
    """Parse ops/tasks.md into structured task items.

    Returns:
        Dict with keys "active", "pending", "completed" mapping to lists
        of TaskStackItem.
    """
    tasks_path = vault_path / "ops" / "tasks.md"
    result: dict[str, list[TaskStackItem]] = {
        "active": [],
        "pending": [],
        "completed": [],
    }
    if not tasks_path.is_file():
        return result

    try:
        text = tasks_path.read_text(errors="replace")
    except OSError:
        return result

    current_section = ""
    current_subsection = ""
    section_re = re.compile(r"^##\s+(\w+)")
    subsection_re = re.compile(r"^###\s+(.+)")
    item_re = re.compile(r"^-\s+(?:\*\*(.+?)\*\*\s*--\s*(.*)|(.*))$")

    for line in text.splitlines():
        line = line.strip()
        sec_m = section_re.match(line)
        if sec_m:
            current_section = sec_m.group(1).lower()
            current_subsection = ""
            continue
        sub_m = subsection_re.match(line)
        if sub_m:
            current_subsection = sub_m.group(1).strip()
            continue
        if current_section not in result:
            continue
        item_m = item_re.match(line)
        if item_m:
            if item_m.group(1):
                title = item_m.group(1).strip()
                desc = item_m.group(2).strip()
            else:
                raw = item_m.group(3).strip()
                # Split on " -- " for description if present
                if " -- " in raw:
                    title, desc = raw.split(" -- ", 1)
                else:
                    title, desc = raw, ""
            result[current_section].append(
                TaskStackItem(
                    title=title.strip(),
                    description=desc.strip(),
                    section=current_section.capitalize(),
                    subsection=current_subsection,
                )
            )

    return result


@dataclass
class VaultState:
    """Snapshot of vault health and research state."""

    vault_path: Path = field(default_factory=lambda: Path("."))
    health_fails: int = 0
    health_stale: bool = False
    failed_categories: list[FailedCategory] = field(default_factory=list)
    observation_count: int = 0
    tension_count: int = 0
    queue_backlog: int = 0
    orphan_count: int = 0
    inbox_count: int = 0
    unmined_session_count: int = 0
    stale_note_count: int = 0
    goals: list[GoalState] = field(default_factory=list)
    task_stack_active: list[TaskStackItem] = field(default_factory=list)
    task_stack_pending: list[TaskStackItem] = field(default_factory=list)
    completed_markers: set[str] = field(default_factory=set)
    metabolic: object | None = None  # MetabolicState when computed
    federation_enabled: bool = False
    federation_exchange_dir: str = ""
    federation_peers_count: int = 0
    quarantine_count: int = 0
    queue_blocked: int = 0
    claim_count: int = 0


# ---------------------------------------------------------------------------
# Vault state scanner
# ---------------------------------------------------------------------------

_GOAL_LINK_RE = re.compile(r"\[\[([\w-]+)\]\]")


def _newest_mtime(directory: Path, pattern: str) -> float:
    """Return the most recent mtime of files matching glob pattern, or 0."""
    try:
        files = list(directory.glob(pattern))
    except OSError:
        return 0.0
    if not files:
        return 0.0
    return max(f.stat().st_mtime for f in files)


def _count_files(directory: Path, suffix: str = ".md") -> int:
    """Count files with given suffix in a directory (non-recursive)."""
    if not directory.is_dir():
        return 0
    return sum(
        1 for f in directory.iterdir() if f.suffix == suffix and f.name != "_index.md"
    )


def _extract_goal_from_hypothesis(fm: dict) -> str:
    """Extract goal ID from hypothesis frontmatter research_goal field."""
    rg = fm.get("research_goal", "")
    m = _GOAL_LINK_RE.search(str(rg))
    return m.group(1) if m else ""


def _count_unmined_sessions(sessions_dir: Path, marker_dir: Path) -> int:
    """Count session files not yet mined (no corresponding marker)."""
    if not sessions_dir.is_dir():
        return 0
    mined = set()
    if marker_dir.is_dir():
        mined = {f.stem for f in marker_dir.iterdir()}
    count = 0
    for f in sessions_dir.iterdir():
        if f.suffix in (".md", ".jsonl") and f.stem not in mined:
            count += 1
    return count


def _count_queue_pending(queue_file: Path) -> int:
    """Count pending tasks in the queue.json.

    Handles both flat-list format (live queue) and dict-with-tasks format.
    """
    if not queue_file.is_file():
        return 0
    try:
        raw = json.loads(queue_file.read_text())
        tasks = raw if isinstance(raw, list) else raw.get("tasks", [])
        return sum(
            1 for t in tasks if t.get("status") not in ("done", "archived", "blocked")
        )
    except (json.JSONDecodeError, OSError):
        return 0


def _is_literature_stub(text: str) -> bool:
    """Return True if text lacks populated Key Points and Relevance sections."""
    has_key_points = False
    has_relevance = False
    lines = text.splitlines()
    current_section = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Key Points"):
            current_section = "key_points"
            continue
        elif stripped.startswith("## Relevance"):
            current_section = "relevance"
            continue
        elif stripped.startswith("## "):
            current_section = ""
            continue
        is_content = stripped and not stripped.startswith("---")
        if current_section == "key_points" and is_content:
            has_key_points = True
        if current_section == "relevance" and is_content:
            has_relevance = True
    return not (has_key_points and has_relevance)


def _count_queue_blocked(queue_file: Path) -> int:
    """Count queue tasks blocked on unpopulated literature stubs.

    A task is considered blocked when:
    - status == "blocked", OR
    - status == "pending" AND current_phase == "reduce" AND the source file
      is missing or is a stub (Key Points and Relevance both empty).

    Args:
        queue_file: Path to ops/queue/queue.json.

    Returns:
        Number of blocked tasks.
    """
    if not queue_file.is_file():
        return 0
    try:
        raw = json.loads(queue_file.read_text())
        tasks = raw if isinstance(raw, list) else raw.get("tasks", [])
    except (json.JSONDecodeError, OSError):
        return 0

    vault_root = queue_file.parent.parent.parent  # ops/queue/queue.json -> vault
    count = 0
    for t in tasks:
        status = t.get("status", "")
        if status == "blocked":
            count += 1
            continue
        if status == "pending" and t.get("current_phase") == "reduce":
            source = t.get("source", "")
            if not source:
                count += 1
                continue
            source_path = vault_root / source
            if not source_path.is_file():
                count += 1
                continue
            try:
                text = source_path.read_text(errors="replace")
            except OSError:
                count += 1
                continue
            if _is_literature_stub(text):
                count += 1
    return count


def _count_orphan_notes(vault_path: Path) -> int:
    """Count notes in notes/ with zero incoming wiki links from the vault.

    Algorithm (O(n+m), single pass):
      1. Collect all notes/*.md stems (excluding _index.md) as the candidate set.
      2. Scan every *.md file in the vault for wiki link targets.
      3. Orphans = candidate stems NOT in the link target set.
      Skips .git/ directories.

    Args:
        vault_path: Root of the Obsidian vault.

    Returns:
        Number of orphan notes.
    """
    notes_dir = vault_path / "notes"
    if not notes_dir.is_dir():
        return 0

    # 1. Candidate set: all note stems
    note_stems = set()
    for f in notes_dir.iterdir():
        if f.suffix == ".md" and f.name != "_index.md":
            note_stems.add(f.stem)

    if not note_stems:
        return 0

    # 2. Collect all wiki link targets across the vault
    linked_stems: set[str] = set()
    for md_file in vault_path.rglob("*.md"):
        # Skip .git directories
        if ".git" in md_file.parts:
            continue
        try:
            text = md_file.read_text(errors="replace")
        except OSError:
            continue
        for m in _WIKILINK_RE.finditer(text):
            linked_stems.add(m.group(1).strip())

    # 3. Orphans = notes not linked from anywhere
    return len(note_stems - linked_stems)


# ---------------------------------------------------------------------------
# Health report parsing
# ---------------------------------------------------------------------------

_SUMMARY_RE = re.compile(r"Summary:\s*(\d+)\s*FAIL,\s*(\d+)\s*WARN,\s*(\d+)\s*PASS")
_CATEGORY_RE = re.compile(r"\[(\d+)\]\s+(.+?)\s*\.{2,}\s*(FAIL|WARN|PASS)")
_RECOMMENDATION_RE = re.compile(r"^\s+Recommendation:\s*(.+)", re.MULTILINE)
_ROOT_CAUSE_RE = re.compile(r"^\s+-\s+(.+?):\s*(\d+)?\s*(.*)", re.MULTILINE)


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug (lowercase, hyphens, no specials)."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:80]


def _extract_root_causes(block: str) -> list[RootCause]:
    """Extract root causes from a health report FAIL detail block.

    Parses the "Root causes:" section, expecting lines like:
        - Pattern name: N description text
        - Pattern name: description text (no count)
    """
    # Find the Root causes: section
    rc_match = re.search(r"Root causes:\s*\n((?:\s+-\s+.+\n?)+)", block)
    if not rc_match:
        return []
    rc_block = rc_match.group(1)
    causes: list[RootCause] = []
    for line in rc_block.strip().split("\n"):
        line = line.strip()
        if not line.startswith("-"):
            continue
        # Remove leading "- "
        line = line[1:].strip()
        # Split on first colon to get pattern name and rest
        parts = line.split(":", 1)
        if len(parts) < 2:
            continue
        pattern = parts[0].strip()
        rest = parts[1].strip()
        # Try to extract leading count from rest
        count_match = re.match(r"^(\d+)\s+(.*)", rest)
        if count_match:
            count = int(count_match.group(1))
            desc = count_match.group(2).strip()
        else:
            count = 0
            desc = rest
        if pattern:
            causes.append(
                RootCause(
                    pattern=pattern,
                    description=desc,
                    affected_count=count,
                )
            )
    return causes


def get_latest_health_report(vault_path: Path) -> Path | None:
    """Find the newest health report file in ops/health/."""
    health_dir = vault_path / "ops" / "health"
    if not health_dir.is_dir():
        return None
    reports = sorted(health_dir.glob("*.md"), key=lambda f: f.stat().st_mtime)
    return reports[-1] if reports else None


def parse_health_report(report_path: Path, max_age_hours: int = 2) -> HealthReport:
    """Parse a /health report into structured data.

    Args:
        report_path: Path to the health report markdown file.
        max_age_hours: Reports older than this are marked stale.

    Returns:
        Populated HealthReport.
    """
    try:
        text = report_path.read_text(errors="replace")
    except OSError:
        return HealthReport(stale=True, report_path=str(report_path))

    report = HealthReport(report_path=str(report_path))

    # Check staleness by file mtime
    try:
        age_hours = (time.time() - report_path.stat().st_mtime) / 3600
        report.stale = age_hours > max_age_hours
    except OSError:
        report.stale = True

    # Parse summary line
    m = _SUMMARY_RE.search(text)
    if m:
        report.fails = int(m.group(1))
        report.warns = int(m.group(2))
        report.passes = int(m.group(3))

    # Parse detail blocks for FAIL categories
    # Split on detail block markers to extract per-category text
    blocks = re.split(r"(?=\[\d+\]\s+)", text)
    for block in blocks:
        cat_match = _CATEGORY_RE.match(block.strip())
        if not cat_match:
            continue
        status = cat_match.group(3)
        if status != "FAIL":
            continue
        name = cat_match.group(2).strip()
        rec_match = _RECOMMENDATION_RE.search(block)
        recommendation = rec_match.group(1).strip() if rec_match else ""
        root_causes = _extract_root_causes(block)
        report.failed_categories.append(
            FailedCategory(
                name=name,
                detail=block.strip(),
                recommendation=recommendation,
                root_causes=root_causes,
            )
        )

    return report


# ---------------------------------------------------------------------------
# Health observation creation -- root causes become ops/observations/
# ---------------------------------------------------------------------------


def build_health_observation(
    category_name: str,
    root_cause: RootCause,
    report_date: str,
    report_path: str,
) -> tuple[str, str]:
    """Build an observation filename and markdown content from a root cause.

    Args:
        category_name: Health check category (e.g., "Link Health").
        root_cause: The extracted root cause.
        report_date: ISO date string (YYYY-MM-DD).
        report_path: Path to the health report that detected this.

    Returns:
        (filename, content) tuple. Filename has no .md extension.
    """
    cat_slug = _slugify(category_name)
    pattern_slug = _slugify(root_cause.pattern)
    filename = f"health-{cat_slug}-{pattern_slug}-{report_date}"

    count_line = ""
    if root_cause.affected_count > 0:
        count_line = f"\nAffected count: {root_cause.affected_count}"

    content = (
        f"---\n"
        f'description: "Health gate detected recurring {root_cause.pattern} '
        f'pattern in {category_name}"\n'
        f"category: health-pattern\n"
        f"status: pending\n"
        f'observed: "{report_date}"\n'
        f'health_category: "{category_name}"\n'
        f'failure_pattern: "{root_cause.pattern}"\n'
        f"affected_count: {root_cause.affected_count}\n"
        f'report_path: "{report_path}"\n'
        f"---\n"
        f"\n"
        f"# health gate detected {root_cause.pattern} in {category_name}\n"
        f"\n"
        f"**Category:** {category_name}\n"
        f"**Pattern:** {root_cause.pattern}\n"
        f"**Description:** {root_cause.description}{count_line}\n"
        f"**Report:** {report_path}\n"
        f"\n"
        f"This root cause was automatically extracted from the health gate "
        f"report. If it recurs across multiple reports, /rethink will "
        f"propose a systemic fix.\n"
    )
    return filename, content


def create_health_observations(
    vault_path: Path,
    report_path: Path | None = None,
) -> list[str]:
    """Create observation files from health report root causes.

    Reads the latest (or specified) health report, extracts root causes
    from FAIL categories, and writes observation files to ops/observations/.
    Idempotent: skips files that already exist (same filename = same
    category + pattern + date).

    Args:
        vault_path: Root of the Obsidian vault.
        report_path: Specific report to process. If None, uses latest.

    Returns:
        List of created observation filenames.
    """
    if report_path is None:
        report_path = get_latest_health_report(vault_path)
    if report_path is None:
        return []

    report = parse_health_report(report_path, max_age_hours=9999)
    if report.fails == 0:
        return []

    # Extract date from report filename (YYYY-MM-DD-*) or fall back to today
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", report_path.name)
    if date_match:
        report_date = date_match.group(1)
    else:
        from datetime import date

        report_date = date.today().isoformat()

    obs_dir = vault_path / "ops" / "observations"
    obs_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    for cat in report.failed_categories:
        for rc in cat.root_causes:
            filename, content = build_health_observation(
                category_name=cat.name,
                root_cause=rc,
                report_date=report_date,
                report_path=str(report_path),
            )
            target = obs_dir / f"{filename}.md"
            if target.exists():
                continue
            target.write_text(content)
            created.append(filename)

    return created


# Health category -> fix skill mapping
_HEALTH_FIX_MAP: dict[str, tuple[str, str, str]] = {
    # category_name: (skill, args, default_model_key)
    "Schema Compliance": ("validate", "", "validate"),
    "Orphan Detection": ("reflect", "--connect-orphans", "reflect"),
    "Link Health": ("validate", "--fix-dangling", "validate"),
    "Description Quality": ("verify", "", "verify"),
    "Processing Throughput": ("ralph", "", "reduce"),
    "Stale Notes": ("reweave", "--handoff", "reweave"),
    "MOC Coherence": ("reflect", "", "reflect"),
}


def build_health_fix_task(
    category: FailedCategory, config: DaemonConfig
) -> DaemonTask | None:
    """Map a failed health category to a fix task.

    Args:
        category: The failed category from the health report.
        config: Daemon configuration for model selection.

    Returns:
        DaemonTask to fix the category, or None if no automated fix exists
        (e.g., Three-Space Boundaries requires manual intervention).
    """
    entry = _HEALTH_FIX_MAP.get(category.name)
    if entry is None:
        return None

    skill, args, model_key = entry
    model = config.models.for_skill(model_key)
    rec = category.recommendation or f"Fix {category.name} issues"

    return DaemonTask(
        skill=skill,
        args=args,
        model=model,
        tier=0,
        task_key=f"health-fix-{category.name.lower().replace(' ', '-')}",
        prompt=(
            f"{_SKILL_PREAMBLE}\n\n"
            f"Your task: Fix health check failure for '{category.name}'.\n\n"
            f"Health report recommendation: {rec}\n\n"
            f"Run the appropriate skill to resolve these issues. "
            f"Process up to 10 items per invocation."
        ),
    )


def scan_vault(vault_path: Path, config: DaemonConfig) -> VaultState:
    """Scan vault filesystem to build a state snapshot.

    Args:
        vault_path: Root of the Obsidian vault.
        config: Daemon configuration for thresholds.

    Returns:
        VaultState describing current vault health and research cycle state.
    """
    state = VaultState(vault_path=vault_path)
    hyp_dir = vault_path / "_research" / "hypotheses"
    obs_dir = vault_path / "ops" / "observations"
    tens_dir = vault_path / "ops" / "tensions"
    inbox_dir = vault_path / "inbox"
    sessions_dir = vault_path / "ops" / "sessions"
    queue_file = vault_path / "ops" / "queue" / "queue.json"
    tournaments_dir = vault_path / "_research" / "tournaments"
    meta_reviews_dir = vault_path / "_research" / "meta-reviews"
    landscape_dir = vault_path / "_research" / "landscape"
    marker_dir = vault_path / "ops" / "daemon" / "mined-sessions"
    task_marker_dir = vault_path / "ops" / "daemon" / "markers"

    # Completed task markers (daemon.sh writes *.done files here)
    if task_marker_dir.is_dir():
        state.completed_markers = {
            f.stem for f in task_marker_dir.iterdir() if f.suffix == ".done"
        }

    # Task stack from ops/tasks.md
    task_stack = parse_task_stack(vault_path)
    state.task_stack_active = task_stack["active"]
    state.task_stack_pending = task_stack["pending"]

    # Health counts
    state.claim_count = _count_files(vault_path / "notes")
    state.observation_count = _count_files(obs_dir)
    state.tension_count = _count_files(tens_dir)
    state.inbox_count = _count_files(inbox_dir)
    state.queue_backlog = _count_queue_pending(queue_file)
    state.queue_blocked = _count_queue_blocked(queue_file)
    state.orphan_count = _count_orphan_notes(vault_path)
    state.unmined_session_count = _count_unmined_sessions(sessions_dir, marker_dir)

    # Health report (owned by /health -- daemon.sh handles the gate)
    report_path = get_latest_health_report(vault_path)
    if report_path is not None:
        hr = parse_health_report(
            report_path, max_age_hours=config.health.check_frequency_hours
        )
        state.health_fails = hr.fails
        state.health_stale = hr.stale
        state.failed_categories = list(hr.failed_categories)
    else:
        state.health_stale = True

    # Per-goal research cycle state
    # Collect hypothesis -> goal mapping and per-goal hypothesis mtimes
    goal_hyps: dict[str, list[dict]] = {g: [] for g in config.goals_priority}
    goal_hyp_mtimes: dict[str, float] = {g: 0.0 for g in config.goals_priority}

    if hyp_dir.is_dir():
        for f in hyp_dir.iterdir():
            if f.suffix != ".md" or f.name.startswith("_"):
                continue
            fm = _read_frontmatter(f)
            if fm.get("type") != "hypothesis":
                continue
            goal = _extract_goal_from_hypothesis(fm)
            if goal in goal_hyps:
                goal_hyps[goal].append(fm)
                try:
                    mtime = f.stat().st_mtime
                    if mtime > goal_hyp_mtimes[goal]:
                        goal_hyp_mtimes[goal] = mtime
                except OSError:
                    pass

    # Federation state
    fed_config_path = vault_path / "ops" / "federation.yaml"
    if fed_config_path.is_file():
        from engram_r.federation_config import load_federation_config

        try:
            fed = load_federation_config(fed_config_path)
            state.federation_enabled = fed.enabled
            state.federation_exchange_dir = fed.exchange_dir
            state.federation_peers_count = len(fed.peers)
        except Exception:
            pass

    # Quarantine count -- scan notes/ for quarantined federation imports
    notes_dir = vault_path / "notes"
    if notes_dir.is_dir():
        q_count = 0
        for nf in notes_dir.iterdir():
            if nf.suffix != ".md":
                continue
            nf_fm = _read_frontmatter(nf)
            if nf_fm.get("quarantine"):
                q_count += 1
        state.quarantine_count = q_count

    # Experiment state -- scan for completed experiments with unresolved hypotheses
    experiments_dir = vault_path / "_research" / "experiments"
    # goal -> (latest_exp_mtime, unresolved_count)
    goal_exp_state: dict[str, tuple[float, int]] = {
        g: (0.0, 0) for g in config.goals_priority
    }
    if experiments_dir.is_dir():
        for f in experiments_dir.iterdir():
            if f.suffix != ".md" or not f.name.startswith("EXP-"):
                continue
            fm = _read_frontmatter(f)
            outcome = fm.get("outcome", "")
            if not outcome:
                continue
            # Find linked hypotheses and their goal
            linked = fm.get("linked_hypotheses", [])
            if isinstance(linked, str):
                linked = [linked]
            for link_str in linked:
                hyp_stem = _WIKILINK_RE.search(str(link_str))
                if not hyp_stem:
                    continue
                hyp_name = hyp_stem.group(1).strip()
                hyp_path = hyp_dir / f"{hyp_name}.md"
                if not hyp_path.is_file():
                    continue
                hyp_fm = _read_frontmatter(hyp_path)
                goal = _extract_goal_from_hypothesis(hyp_fm)
                if goal not in goal_exp_state:
                    continue
                try:
                    exp_mtime = f.stat().st_mtime
                except OSError:
                    exp_mtime = 0.0
                cur_mtime, cur_unresolved = goal_exp_state[goal]
                if exp_mtime > cur_mtime:
                    goal_exp_state[goal] = (exp_mtime, cur_unresolved)
                # Check if hypothesis has been updated with empirical result
                if not hyp_fm.get("empirical_outcome"):
                    goal_exp_state[goal] = (
                        goal_exp_state[goal][0],
                        goal_exp_state[goal][1] + 1,
                    )

    for goal_id in config.goals_priority:
        hyps = goal_hyps.get(goal_id, [])
        undermatched = sum(
            1
            for h in hyps
            if int(h.get("matches", 0)) < config.thresholds.undermatched_matches
        )
        exp_mtime, exp_unresolved = goal_exp_state.get(goal_id, (0.0, 0))
        gs = GoalState(
            goal_id=goal_id,
            hypothesis_count=len(hyps),
            undermatched_count=undermatched,
            latest_tournament_mtime=_newest_mtime(
                tournaments_dir, f"*{_goal_slug(goal_id)}*"
            ),
            latest_meta_review_mtime=_newest_mtime(
                meta_reviews_dir, f"*{_goal_slug(goal_id)}*"
            ),
            latest_landscape_mtime=_newest_mtime(
                landscape_dir, f"*{_goal_slug(goal_id)}*"
            ),
            latest_hypothesis_mtime=goal_hyp_mtimes.get(goal_id, 0.0),
            latest_experiment_mtime=exp_mtime,
            unresolved_experiment_count=exp_unresolved,
        )
        state.goals.append(gs)

    # Stale note count (notes not updated in stale_notes_days)
    notes_dir = vault_path / "notes"
    if notes_dir.is_dir():
        stale_cutoff = time.time() - (config.thresholds.stale_notes_days * 86400)
        stale = 0
        for nf in notes_dir.iterdir():
            if nf.suffix != ".md" or nf.name == "_index.md":
                continue
            try:
                if nf.stat().st_mtime < stale_cutoff:
                    stale += 1
            except OSError:
                pass
        state.stale_note_count = stale

    # Metabolic indicators
    if config.metabolic.enabled:
        from engram_r.metabolic_indicators import compute_metabolic_state

        # Reuse already-loaded queue data to avoid double-reads
        queue_json = None
        if queue_file.is_file():
            import contextlib

            with contextlib.suppress(json.JSONDecodeError, OSError):
                queue_json = json.loads(queue_file.read_text())
        state.metabolic = compute_metabolic_state(
            vault_path,
            queue_data=queue_json,
            lookback_days=config.metabolic.lookback_days,
            orphan_count=state.orphan_count,
            qpr_critical=config.metabolic.qpr_critical,
            cmr_hot=config.metabolic.cmr_hot,
            tpv_stalled=config.metabolic.tpv_stalled,
            hcr_redirect=config.metabolic.hcr_redirect,
            gcr_fragmented=config.metabolic.gcr_fragmented,
            ipr_overflow=config.metabolic.ipr_overflow,
        )

    return state


def _goal_slug(goal_id: str) -> str:
    """Strip 'goal-' prefix for file glob matching (e.g. goal-my-topic -> my-topic)."""
    if goal_id.startswith("goal-"):
        return goal_id[5:]
    return goal_id


# ---------------------------------------------------------------------------
# Priority cascade -- first match wins
# ---------------------------------------------------------------------------

_TOURNAMENT_PREAMBLE = (
    "You are running autonomously as a daemon with NO human present. "
    "CRITICAL RULES:\n"
    "- NEVER use AskUserQuestion or EnterPlanMode. These tools are disabled.\n"
    "- When the /tournament skill asks 'how many matches to run', answer: "
    "ALL remaining matches.\n"
    "- When the skill presents a verdict for user override, accept the AI "
    "verdict and proceed immediately.\n"
    "- If you encounter any ambiguity, choose the most conservative "
    "reasonable option and continue.\n"
    "- If you encounter an error writing a file, log it and continue with "
    "the next match.\n"
    "- Process matches in batches of {batch_size} per invocation to stay "
    "within context limits."
)

_SKILL_PREAMBLE = (
    "You are running autonomously as a daemon with NO human present. "
    "NEVER use AskUserQuestion or EnterPlanMode. "
    "Make all decisions autonomously. Accept defaults and proceed."
)


def _validate_task_skill(task: DaemonTask) -> None:
    """Raise ValueError if the task's skill is not in the allowed set.

    Slack-originated tasks (task_key starts with ``slack-``) are also
    permitted to use SLACK_READONLY_SKILLS.
    """
    allowed = DAEMON_ALLOWED_SKILLS
    if task.task_key.startswith("slack-"):
        allowed = DAEMON_ALLOWED_SKILLS | SLACK_READONLY_SKILLS
    if task.skill not in allowed:
        raise ValueError(
            f"Skill {task.skill!r} is not in the allowed set for "
            f"task_key={task.task_key!r}. Allowed: {sorted(allowed)}"
        )


@dataclass
class SelectionResult:
    """Result of select_task_audited: the chosen task plus its audit trail."""

    task: DaemonTask | None
    audit: AuditEntry = field(default_factory=lambda: AuditEntry(timestamp=""))


def vault_summary_dict(state: VaultState) -> dict:
    """Build the 9-key vault summary dict from a VaultState snapshot.

    Used by ``select_task_audited`` (audit trail), ``main`` (idle output),
    and ``--scan-only`` mode.  Single source of truth for the summary shape.
    """
    return {
        "health_fails": state.health_fails,
        "health_stale": state.health_stale,
        "observations": state.observation_count,
        "tensions": state.tension_count,
        "queue_backlog": state.queue_backlog,
        "queue_blocked": state.queue_blocked,
        "orphan_notes": state.orphan_count,
        "inbox": state.inbox_count,
        "unmined_sessions": state.unmined_session_count,
    }


def select_task_audited(state: VaultState, config: DaemonConfig) -> SelectionResult:
    """Apply the priority cascade with full audit trail.

    Builds an AuditEntry recording each check evaluated, whether it
    triggered, and why it was skipped if not selected.

    Args:
        state: Current vault state snapshot.
        config: Daemon configuration.

    Returns:
        SelectionResult with the chosen task and audit trail.
    """
    now = datetime.datetime.now(datetime.UTC).isoformat()
    audit = AuditEntry(timestamp=now)

    # Build vault summary for audit
    audit.vault_summary = vault_summary_dict(state)

    # Metabolic governor: suppress generative P1 if tier 1 alarm active
    metabolic_suppress_p1 = False
    if state.metabolic and config.metabolic.enabled:
        alarms = getattr(state.metabolic, "alarm_keys", [])
        tier1_alarms = {"qpr_critical", "cmr_hot", "tpv_stalled"}
        if tier1_alarms & set(alarms):
            metabolic_suppress_p1 = True
    audit.metabolic_suppressed = metabolic_suppress_p1

    if metabolic_suppress_p1:
        # Still allow experiment resolution (not generative)
        task = _check_p1_experiments_only(state, config)
        rule = RuleEvaluation(
            check_name="p1_experiments_only",
            triggered=bool(task and task.task_key not in state.completed_markers),
            candidate_skill=task.skill if task else "",
            candidate_key=task.task_key if task else "",
        )
        if task and task.task_key in state.completed_markers:
            rule.skip_reason = "already_completed"
        audit.rules_evaluated.append(rule)
        if rule.triggered:
            _validate_task_skill(task)
            audit.selected_task = task.task_key
            audit.selected_skill = task.skill
            audit.selected_tier = task.tier
            return SelectionResult(task=task, audit=audit)

        checks = [
            ("p2_maintenance", _check_p2),
            ("p2_5_inbox", _check_p2_5),
            ("p2_7_slack_queue", _check_p2_7_slack_queue),
            ("p3_background", _check_p3),
            ("p3_6_schedules", _check_schedules),
            ("p3_5_federation", _check_p3_5),
        ]
    else:
        checks = [
            ("p1_research_cycle", _check_p1),
            ("p2_maintenance", _check_p2),
            ("p2_5_inbox", _check_p2_5),
            ("p2_7_slack_queue", _check_p2_7_slack_queue),
            ("p3_background", _check_p3),
            ("p3_6_schedules", _check_schedules),
            ("p3_5_federation", _check_p3_5),
        ]

    for check_name, check_fn in checks:
        task = check_fn(state, config)
        triggered = bool(task and task.task_key not in state.completed_markers)
        rule = RuleEvaluation(
            check_name=check_name,
            triggered=triggered,
            candidate_skill=task.skill if task else "",
            candidate_key=task.task_key if task else "",
        )
        if task and task.task_key in state.completed_markers:
            rule.skip_reason = "already_completed"
        elif not task:
            rule.skip_reason = "no_work"
        audit.rules_evaluated.append(rule)

        if triggered:
            _validate_task_skill(task)
            audit.selected_task = task.task_key
            audit.selected_skill = task.skill
            audit.selected_tier = task.tier
            return SelectionResult(task=task, audit=audit)

    # P4: Idle
    return SelectionResult(task=None, audit=audit)


def select_task(state: VaultState, config: DaemonConfig) -> DaemonTask | None:
    """Apply the priority cascade and return the highest-priority task.

    Wrapper around select_task_audited that discards the audit trail.
    Preserves backward compatibility for existing callers.
    """
    return select_task_audited(state, config).task


def _check_p1_experiments_only(
    state: VaultState, config: DaemonConfig
) -> DaemonTask | None:
    """P1 subset: only experiment resolution (not generative work).

    Used when the metabolic governor suppresses generative P1 tasks.
    """
    for gs in state.goals:
        if gs.unresolved_experiment_count > 0:
            return DaemonTask(
                skill="experiment",
                args=f"--resolve {gs.goal_id}",
                model="sonnet",
                tier=1,
                task_key=f"p1-experiment-resolve-{gs.goal_id}",
                prompt=(
                    f"{_SKILL_PREAMBLE}\n\n"
                    f"Your task: Resolve experiment outcomes for {gs.goal_id}.\n\n"
                    f"There are {gs.unresolved_experiment_count} completed experiments "
                    f"with outcomes that have not been propagated to their linked "
                    f"hypotheses. For each: read the experiment note, compute the "
                    f"empirical Elo adjustment using experiment_resolver, update the "
                    f"hypothesis status and Elo, and append to the Empirical Evidence "
                    f"section. Use K=16 and virtual opponent at Elo 1200."
                ),
            )
    return None


def _check_p1(state: VaultState, config: DaemonConfig) -> DaemonTask | None:
    """P1: Research cycle -- experiments, tournament, meta-review, landscape."""
    # Experiment resolution takes priority -- propagate empirical results
    # before next tournament round
    for gs in state.goals:
        if gs.unresolved_experiment_count > 0:
            return DaemonTask(
                skill="experiment",
                args=f"--resolve {gs.goal_id}",
                model="sonnet",
                tier=1,
                task_key=f"p1-experiment-resolve-{gs.goal_id}",
                prompt=(
                    f"{_SKILL_PREAMBLE}\n\n"
                    f"Your task: Resolve experiment outcomes for {gs.goal_id}.\n\n"
                    f"There are {gs.unresolved_experiment_count} completed experiments "
                    f"with outcomes that have not been propagated to their linked "
                    f"hypotheses. For each: read the experiment note, compute the "
                    f"empirical Elo adjustment using experiment_resolver, update the "
                    f"hypothesis status and Elo, and append to the Empirical Evidence "
                    f"section. Use K=16 and virtual opponent at Elo 1200."
                ),
            )

    for gs in state.goals:
        if gs.hypothesis_count < 2:
            continue
        cs = gs.cycle_state
        if cs == "needs_tournament":
            model = config.models.for_tournament(gs.goal_id, config.primary_goal)
            batch = config.batching.matches_per_session
            return DaemonTask(
                skill="tournament",
                args=gs.goal_id,
                model=model,
                tier=1,
                batch_size=batch,
                task_key=f"p1-tournament-{gs.goal_id}",
                prompt=(
                    _TOURNAMENT_PREAMBLE.format(batch_size=batch) + "\n\n"
                    f"Your task: Run /tournament for {gs.goal_id}.\n\n"
                    f"Execute pairwise debates for hypotheses under this "
                    f"research goal. There are {gs.undermatched_count} "
                    f"undermatched hypotheses (fewer than "
                    f"{config.thresholds.undermatched_matches} matches). "
                    f"Skip any matchups that already have logs in "
                    f"_research/tournaments/. Write all match results and "
                    f"Elo updates to the vault. Update the leaderboard "
                    f"when done."
                ),
            )
        if cs == "needs_meta_review":
            return DaemonTask(
                skill="meta-review",
                args=gs.goal_id,
                model=config.models.meta_review,
                tier=1,
                task_key=f"p1-meta-review-{gs.goal_id}",
                prompt=(
                    f"{_SKILL_PREAMBLE}\n\n"
                    f"Your task: Run /meta-review for {gs.goal_id}.\n\n"
                    f"Synthesize patterns from the latest tournament "
                    f"debates. Read all recent match logs in "
                    f"_research/tournaments/ for this goal. Extract "
                    f"cross-cutting feedback about hypothesis quality, "
                    f"common weaknesses, and recommendations for the "
                    f"next generation/evolution cycle. Write the "
                    f"meta-review note to _research/meta-reviews/."
                ),
            )
        if cs == "needs_landscape":
            return DaemonTask(
                skill="landscape",
                args=gs.goal_id,
                model=config.models.landscape,
                tier=1,
                task_key=f"p1-landscape-{gs.goal_id}",
                prompt=(
                    f"{_SKILL_PREAMBLE}\n\n"
                    f"Your task: Run /landscape for {gs.goal_id}.\n\n"
                    f"Generate an updated proximity clustering of all "
                    f"hypotheses under this goal, incorporating the "
                    f"latest Elo ratings and tournament feedback. Write "
                    f"to _research/landscape/."
                ),
            )
        if cs == "cycle_complete":
            # Queue generative work -- this is Tier 3, skip to next goal
            continue
    return None


def _check_p2(state: VaultState, config: DaemonConfig) -> DaemonTask | None:
    """P2: Knowledge maintenance -- rethink, reflect/reweave phases."""
    if state.observation_count >= config.thresholds.observations_rethink:
        return DaemonTask(
            skill="rethink",
            args="--triage-only",
            model=config.models.rethink,
            tier=2,
            task_key="p2-rethink-observations",
            prompt=(
                f"{_SKILL_PREAMBLE}\n\n"
                f"Your task: Run /rethink --triage-only.\n\n"
                f"There are {state.observation_count} pending "
                f"observations. Classify each as PROMOTE, IMPLEMENT, "
                f"ARCHIVE, or KEEP PENDING. Write triage proposals to "
                f"ops/daemon-inbox.md for human review. Do NOT "
                f"auto-implement any changes."
            ),
        )
    if state.tension_count >= config.thresholds.tensions_rethink:
        return DaemonTask(
            skill="rethink",
            args="--triage-only",
            model=config.models.rethink,
            tier=2,
            task_key="p2-rethink-tensions",
            prompt=(
                f"{_SKILL_PREAMBLE}\n\n"
                f"Your task: Run /rethink --triage-only.\n\n"
                f"There are {state.tension_count} pending tensions. "
                f"Classify each and write proposals to "
                f"ops/daemon-inbox.md for human review."
            ),
        )
    if state.queue_backlog > config.thresholds.queue_backlog:
        return DaemonTask(
            skill="reflect",
            args="",
            model=config.models.reflect,
            tier=2,
            task_key="p2-reflect-backlog",
            prompt=(
                f"{_SKILL_PREAMBLE}\n\n"
                f"Your task: Process the claim queue backlog.\n\n"
                f"There are {state.queue_backlog} pending claims in "
                f"the queue. Run /reflect on pending claims to find "
                f"connections and update topic maps. Then run /reweave "
                f"on older related claims. Process up to 10 claims."
            ),
        )
    if state.orphan_count >= config.thresholds.orphan_notes:
        return DaemonTask(
            skill="reflect",
            args="--connect-orphans",
            model=config.models.reflect,
            tier=2,
            task_key="p2-reflect-orphans",
            prompt=(
                f"{_SKILL_PREAMBLE}\n\n"
                f"Your task: Connect orphan notes via /reflect "
                f"--connect-orphans.\n\n"
                f"There are {state.orphan_count} notes in notes/ with "
                f"zero incoming wiki links. Find connections to existing "
                f"claims and add them to topic maps. Process up to 10 "
                f"orphans per invocation."
            ),
        )
    return None


def _check_p2_5(state: VaultState, config: DaemonConfig) -> DaemonTask | None:
    """P2.5: Inbox processing -- seed + ralph.

    Seeds the oldest inbox file (inline, no /seed invocation to avoid
    interactive duplicate-confirmation), then processes through the full
    claim phases (extract -> create -> reflect -> reweave -> verify).
    No quarantine -- the full phase chain IS the quality gate.
    """
    if state.inbox_count > 0:
        return DaemonTask(
            skill="ralph",
            args="",
            model=config.models.reduce,
            tier=2,
            task_key="p2.5-ralph-inbox",
            prompt=(
                f"{_SKILL_PREAMBLE}\n\n"
                f"Your task: Process the oldest inbox item through "
                f"seed + ralph.\n\n"
                f"There are {state.inbox_count} items in inbox/.\n\n"
                f"Step 1 -- Inline seed (do NOT invoke /seed -- it has "
                f"interactive duplicate-confirmation that hangs in daemon "
                f"mode):\n"
                f"  a. Find the oldest .md file in inbox/ (exclude "
                f"_index.md). Use file modification time to determine "
                f"oldest.\n"
                f"  b. Compute SOURCE_BASENAME from the filename "
                f"(lowercase, hyphens for spaces).\n"
                f"  c. Create archive dir: "
                f"ops/queue/archive/{{date}}-{{SOURCE_BASENAME}}/. "
                f"If this archive dir already exists, this file was "
                f"already processed -- skip it and log 'Skipped "
                f"{{file}}: duplicate detected (daemon --no-confirm)' "
                f"to ops/daemon-inbox.md, then exit.\n"
                f"  d. Move the file from inbox/ to the archive dir.\n"
                f"  e. Compute next_claim_start from existing queue + "
                f"archive numbering.\n"
                f"  f. Create extract task file in ops/queue/ and add "
                f"the extract entry to the queue file.\n\n"
                f"Step 2 -- Extract: Run /ralph 1 --batch "
                f"{{SOURCE_BASENAME}} --type extract\n\n"
                f"Step 3 -- Process: Count resulting claim tasks for "
                f"this batch, then run /ralph N --batch "
                f"{{SOURCE_BASENAME}} where N is the total pending "
                f"task count.\n\n"
                f"Step 4 -- Summary: Append a summary to "
                f"ops/daemon-inbox.md noting how many claims were "
                f"created and from which source.\n\n"
                f"NEVER use AskUserQuestion or EnterPlanMode. "
                f"All decisions are autonomous."
            ),
        )
    return None


def _check_p2_7_slack_queue(
    state: VaultState, config: DaemonConfig
) -> DaemonTask | None:
    """P2.7: Slack queue -- user-requested skills via Slack bot."""
    from engram_r.slack_skill_router import (
        SLACK_READONLY_SKILLS as _SR_SKILLS,
    )
    from engram_r.slack_skill_router import (
        check_slack_queue,
        mark_queue_entry_running,
    )

    result = check_slack_queue(state.vault_path)
    if result is None:
        return None

    entry = result["entry"]
    allowed = DAEMON_ALLOWED_SKILLS | _SR_SKILLS
    if entry.skill not in allowed:
        logger.warning(
            "Slack queue entry %s requests disallowed skill %s",
            entry.id,
            entry.skill,
        )
        return None

    mark_queue_entry_running(state.vault_path, entry.id)

    # Read-only skills get a simpler prompt
    if entry.skill in _SR_SKILLS:
        prompt = (
            f"{_SKILL_PREAMBLE}\n\n"
            f"Your task: Run /{entry.skill}"
            f"{' ' + entry.args if entry.args else ''}.\n\n"
            f"Output the results. This was requested by a Slack user."
        )
    else:
        prompt = (
            f"{_SKILL_PREAMBLE}\n\n"
            f"Your task: Run /{entry.skill}"
            f"{' ' + entry.args if entry.args else ''}.\n\n"
            f"This was requested by a Slack user. Execute the skill normally."
        )

    return DaemonTask(
        skill=entry.skill,
        args=entry.args,
        model="sonnet",
        tier=2,
        task_key=f"slack-{entry.id}",
        prompt=prompt,
    )


def _check_p3(state: VaultState, config: DaemonConfig) -> DaemonTask | None:
    """P3: Background -- session mining, stale note reweaving."""
    if state.unmined_session_count > config.thresholds.unmined_sessions:
        return DaemonTask(
            skill="remember",
            args="--mine-sessions",
            model=config.models.remember,
            tier=3,
            batch_size=config.batching.mine_sessions_batch,
            task_key="p3-mine-sessions",
            prompt=(
                f"{_SKILL_PREAMBLE}\n\n"
                f"Your task: Run /remember --mine-sessions.\n\n"
                f"Process unmined session files in ops/sessions/ to "
                f"extract methodology observations, friction signals, "
                f"and process patterns. Write observations to "
                f"ops/observations/. Process up to "
                f"{config.batching.mine_sessions_batch} sessions. "
                f"Flag all processed sessions as mined."
            ),
        )
    if state.stale_note_count > 0:
        return DaemonTask(
            skill="reweave",
            args="--handoff",
            model=config.models.reweave,
            tier=3,
            task_key="p3-reweave-stale",
            prompt=(
                f"{_SKILL_PREAMBLE}\n\n"
                f"Your task: Run /reweave on stale notes.\n\n"
                f"There are {state.stale_note_count} notes not updated "
                f"in over {config.thresholds.stale_notes_days} days. "
                f"Revisit the 5 oldest, add connections to newer "
                f"claims, sharpen descriptions. Skip interactive "
                f"approval -- apply changes directly."
            ),
        )
    return None


def _check_schedules(state: VaultState, config: DaemonConfig) -> DaemonTask | None:
    """P3.6: Scheduled recurring tasks (weekly updates, deadline reminders, etc.).

    Iterates over config.schedules entries, checks whether each is due
    based on cadence/day/hour, and returns the first eligible task whose
    marker has not been completed.
    """
    from engram_r.schedule_runner import schedule_is_due, schedule_marker_key

    if not config.schedules:
        return None

    now = datetime.datetime.now()

    for entry in config.schedules:
        if not entry.enabled or not entry.name:
            continue
        if not schedule_is_due(entry, now):
            continue

        marker_key = schedule_marker_key(entry, now)
        if marker_key in state.completed_markers:
            continue

        return DaemonTask(
            skill="notify-scheduled",
            args=entry.name,
            model="haiku",
            tier=3,
            task_key=marker_key,
            prompt="",  # Not used -- daemon.sh calls Python directly
        )

    return None


def _check_p3_5(state: VaultState, config: DaemonConfig) -> DaemonTask | None:
    """P3.5: Federation sync -- export claims/hypotheses to peers."""
    if not state.federation_enabled:
        return None
    if not state.federation_exchange_dir:
        return None
    return DaemonTask(
        skill="federation-sync",
        args="",
        model="sonnet",
        tier=3,
        task_key="p3.5-federation-sync",
        prompt=(
            f"{_SKILL_PREAMBLE}\n\n"
            f"Your task: Run /federation-sync.\n\n"
            f"Export claims and hypotheses to the shared exchange "
            f"directory according to ops/federation.yaml export policy. "
            f"Import claims and hypotheses from peers according to "
            f"trust levels. Quarantine imported items per policy. "
            f"Write a sync summary to ops/daemon-inbox.md."
        ),
    )


# ---------------------------------------------------------------------------
# Tier 3 inbox append (for cycle_complete goals)
# ---------------------------------------------------------------------------


def build_tier3_entries(state: VaultState, config: DaemonConfig) -> list[str]:
    """Build Tier 3 entries: task stack items first, then generative work.

    Task stack items from ops/tasks.md always appear before generative
    work. Generative work (/generate, /evolve) is only queued for goals
    in "cycle_complete" state (new hypotheses since last landscape), not
    "cycle_stale" (no new work since last cycle completed).

    Returns:
        List of markdown lines for daemon-inbox.md or CLI output.
    """
    entries: list[str] = []

    # Metabolic dashboard when any alarm is active
    if state.metabolic and config.metabolic.enabled:
        m = state.metabolic
        alarm_str = ", ".join(m.alarm_keys) if m.alarm_keys else "none"
        entries.append(
            f"- Metabolic: QPR={m.qpr:.1f}d CMR={m.cmr:.0f}:1 "
            f"TPV={m.tpv:.1f}/d GCR={m.gcr:.2f} IPR={m.ipr:.1f} "
            f"VDR={m.vdr:.0f}% [ALARM: {alarm_str}]"
        )

    # Task stack active items first
    for item in state.task_stack_active:
        entries.append(f"- [ ] {item.title} -- from task stack")

    # Generative work only for cycle_complete (not cycle_stale)
    for gs in state.goals:
        if gs.cycle_state == "cycle_complete" and gs.hypothesis_count >= 2:
            entries.append(
                f"- [ ] /generate for {gs.goal_id} -- research cycle "
                f"complete, ready for next generation"
            )
            entries.append(
                f"- [ ] /evolve for {gs.goal_id} -- top hypotheses "
                f"ready for evolution"
            )

    return entries


def build_inbox_entries(state: VaultState, config: DaemonConfig) -> list[str]:
    """Build daemon-inbox entries (backward-compat wrapper).

    Delegates to build_tier3_entries for the unified task-stack-aware
    logic. Preserved for daemon.sh JSON contract compatibility.

    Returns:
        List of markdown lines to append to daemon-inbox.md.
    """
    return build_tier3_entries(state, config)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the daemon scheduler.

    Usage:
        python -m engram_r.daemon_scheduler [--scan-only] [vault_path]

    Flags:
        --scan-only   Print vault summary JSON and exit (no task selection,
                      no audit entry).  Used by daemon.sh for pre/post
                      vault-state snapshots.

    Prints JSON task descriptor to stdout. Exit code:
        0 = task found (or --scan-only success)
        2 = idle (all caught up)
        1 = error
    """
    args = argv if argv is not None else sys.argv[1:]

    scan_only = False
    positional: list[str] = []
    for a in args:
        if a == "--scan-only":
            scan_only = True
        else:
            positional.append(a)

    vault_path = Path(positional[0]) if positional else _default_vault_path()
    config_path = vault_path / "ops" / "daemon-config.yaml"

    if not config_path.is_file():
        msg = {"error": f"Config not found: {config_path}"}
        print(json.dumps(msg), file=sys.stderr)
        return 1

    config = load_config(config_path)
    state = scan_vault(vault_path, config)

    if scan_only:
        print(json.dumps(vault_summary_dict(state), separators=(",", ":")))
        return 0

    result = select_task_audited(state, config)
    task = result.task

    # Best-effort audit write -- filesystem errors do not block selection
    try:
        audit_path = vault_path / "ops" / "daemon" / "logs" / "audit.jsonl"
        append_audit_entry(result.audit, audit_path)
    except Exception:
        logger.warning("Failed to write audit entry", exc_info=True)

    if task is None:
        # Check for Tier 3 inbox entries
        inbox_entries = build_inbox_entries(state, config)
        result = {
            "status": "idle",
            "inbox_entries": inbox_entries,
            "vault_summary": vault_summary_dict(state),
        }
        print(json.dumps(result, indent=2))
        return 2

    print(task.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
