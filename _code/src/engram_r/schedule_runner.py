"""Scheduled task runner for the Research Loop Daemon.

Builds and delivers periodic notifications (weekly project updates,
stale project alerts, experiment reminders) based on vault state.
Direct Python execution -- no LLM required.

The runner is invoked by daemon.sh for 'notify-scheduled' tasks,
bypassing the normal claude -p execution path.
"""

from __future__ import annotations

import datetime
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from engram_r.daemon_config import ScheduleEntry, load_config

logger = logging.getLogger(__name__)

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")

_VALID_DAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ExperimentBrief:
    """Summary of an experiment for notification display."""

    id: str
    status: str
    outcome: str = ""
    blocking_gate: str = ""


@dataclass
class HypothesisBrief:
    """Summary of a hypothesis for notification display."""

    id: str
    elo: float = 0.0
    status: str = ""
    empirical_outcome: str = ""


@dataclass
class ReminderBrief:
    """A single reminder relevant to a project."""

    date: str
    text: str


@dataclass
class ProjectSummary:
    """Aggregated project state for notification rendering."""

    tag: str
    title: str
    status: str
    experiments: list[ExperimentBrief] = field(default_factory=list)
    hypotheses: list[HypothesisBrief] = field(default_factory=list)
    reminders: list[ReminderBrief] = field(default_factory=list)
    next_action: str = ""
    linked_goal_names: list[str] = field(default_factory=list)


@dataclass
class LabMember:
    """A lab member with Slack identity."""

    name: str
    slack_id: str
    role: str = "contributor"


@dataclass
class LabUpdate:
    """Aggregated update for one lab, ready for formatting."""

    lab_name: str
    members: list[LabMember] = field(default_factory=list)
    needs_attention: list[ProjectSummary] = field(default_factory=list)
    on_track: list[ProjectSummary] = field(default_factory=list)
    maintenance: list[ProjectSummary] = field(default_factory=list)
    reminders_this_week: int = 0
    reminders_next_week: int = 0


@dataclass
class ScheduledMessage:
    """A single message to deliver via Slack DM or channel."""

    recipient_slack_id: str
    recipient_name: str
    recipient_role: str
    lab: str
    text: str
    blocks: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Schedule gate logic
# ---------------------------------------------------------------------------


def schedule_is_due(entry: ScheduleEntry, now: datetime.datetime) -> bool:
    """Check whether a schedule entry should fire at the given time.

    Args:
        entry: Schedule configuration.
        now: Current local datetime.

    Returns:
        True if the schedule should fire.
    """
    if not entry.enabled:
        return False
    if now.hour < entry.hour:
        return False
    if entry.cadence == "daily":
        return True
    if entry.cadence == "weekly":
        return now.strftime("%A").lower() == entry.day.lower()
    if entry.cadence == "monthly":
        try:
            return now.day == int(entry.day)
        except (ValueError, TypeError):
            return False
    return False


def schedule_marker_key(entry: ScheduleEntry, now: datetime.datetime) -> str:
    """Generate an idempotency marker key for a schedule entry.

    The key encodes the schedule name and the current period so that
    the same schedule fires at most once per period.

    Args:
        entry: Schedule configuration.
        now: Current local datetime.

    Returns:
        Marker key string (e.g. 'sched-weekly-project-update-2026-W09').
    """
    if entry.cadence == "daily":
        return f"sched-{entry.name}-{now.strftime('%Y-%m-%d')}"
    if entry.cadence == "weekly":
        iso_year, iso_week, _ = now.date().isocalendar()
        return f"sched-{entry.name}-{iso_year}-W{iso_week:02d}"
    if entry.cadence == "monthly":
        return f"sched-{entry.name}-{now.strftime('%Y-%m')}"
    return f"sched-{entry.name}-{now.strftime('%Y-%m-%d')}"


# ---------------------------------------------------------------------------
# Frontmatter reader (local, avoids importing heavy modules)
# ---------------------------------------------------------------------------


def _read_frontmatter(path: Path) -> dict:
    """Read YAML frontmatter from a markdown file."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return {}
    m = _FM_RE.match(text)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def _read_body_first_line(path: Path) -> str:
    """Read the first non-empty body line after frontmatter."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return ""
    m = _FM_RE.match(text)
    body = text[m.end() :] if m else text
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _extract_wikilink_stems(items: list | str) -> list[str]:
    """Extract wikilink stems from a list of strings or a single string."""
    if isinstance(items, str):
        items = [items]
    stems = []
    for item in items:
        m = _WIKILINK_RE.search(str(item))
        if m:
            stems.append(m.group(1).strip())
    return stems


# ---------------------------------------------------------------------------
# Vault scanning -- project, experiment, hypothesis, reminder data
# ---------------------------------------------------------------------------


def _scan_lab_members(lab_index_path: Path) -> list[LabMember]:
    """Parse members from a lab _index.md file."""
    fm = _read_frontmatter(lab_index_path)
    members_raw = fm.get("members", [])
    if not isinstance(members_raw, list):
        return []
    members = []
    for entry in members_raw:
        if isinstance(entry, dict) and entry.get("name") and entry.get("slack_id"):
            members.append(
                LabMember(
                    name=entry["name"],
                    slack_id=entry["slack_id"],
                    role=entry.get("role", "contributor"),
                )
            )
    return members


def _scan_projects(lab_dir: Path, scope: str) -> list[tuple[Path, dict]]:
    """Scan project notes in a lab directory, filtered by scope."""
    projects = []
    if not lab_dir.is_dir():
        return projects
    for f in sorted(lab_dir.iterdir()):
        if f.suffix != ".md" or f.name == "_index.md":
            continue
        fm = _read_frontmatter(f)
        if fm.get("type") != "project":
            continue
        status = fm.get("status", "")
        if scope == "active" and status not in ("active", "maintenance"):
            continue
        projects.append((f, fm))
    return projects


def _load_experiment(vault_path: Path, stem: str) -> ExperimentBrief | None:
    """Load experiment brief from its note."""
    exp_path = vault_path / "_research" / "experiments" / f"{stem}.md"
    if not exp_path.is_file():
        return None
    fm = _read_frontmatter(exp_path)
    exp_id = fm.get("id", stem)
    status = fm.get("status", "unknown")
    outcome = fm.get("outcome", "")
    # Try to extract blocking gate from status or body
    blocking = ""
    if status == "designed":
        blocking = _find_blocking_gate(exp_path)
    return ExperimentBrief(
        id=exp_id, status=status, outcome=outcome, blocking_gate=blocking
    )


def _find_blocking_gate(exp_path: Path) -> str:
    """Scan experiment note for the first blocking gate."""
    try:
        text = exp_path.read_text(errors="replace")
    except OSError:
        return ""
    # Look for "not started" rows in step tables
    for line in text.splitlines():
        if "not started" in line.lower() and "|" in line:
            cells = [c.strip() for c in line.split("|")]
            for cell in cells:
                if cell.lower().startswith("not started"):
                    continue
                if any(
                    kw in cell.lower()
                    for kw in ["access", "download", "approval", "blocked"]
                ):
                    return cell
    return ""


def _load_hypothesis(vault_path: Path, stem: str) -> HypothesisBrief | None:
    """Load hypothesis brief from its note."""
    hyp_path = vault_path / "_research" / "hypotheses" / f"{stem}.md"
    if not hyp_path.is_file():
        return None
    fm = _read_frontmatter(hyp_path)
    return HypothesisBrief(
        id=fm.get("id", stem),
        elo=float(fm.get("elo", 0)),
        status=fm.get("status", ""),
        empirical_outcome=fm.get("empirical_outcome", ""),
    )


def _parse_reminders(vault_path: Path) -> list[ReminderBrief]:
    """Parse all unchecked reminders from ops/reminders.md."""
    rem_path = vault_path / "ops" / "reminders.md"
    if not rem_path.is_file():
        return []
    try:
        text = rem_path.read_text(errors="replace")
    except OSError:
        return []
    reminders = []
    pattern = re.compile(r"^-\s+\[\s\]\s+(\d{4}-\d{2}-\d{2}):\s+(.+)$")
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            reminders.append(ReminderBrief(date=m.group(1), text=m.group(2).strip()))
    return reminders


def _match_reminders_to_project(
    reminders: list[ReminderBrief],
    project_fm: dict,
) -> list[ReminderBrief]:
    """Filter reminders relevant to a project by matching keywords."""
    tag = project_fm.get("project_tag", "")
    title = project_fm.get("title", "")
    exp_stems = _extract_wikilink_stems(project_fm.get("linked_experiments", []))
    hyp_stems = _extract_wikilink_stems(project_fm.get("linked_hypotheses", []))

    # Build search terms from project identifiers
    search_terms = [tag]
    if title:
        search_terms.append(title.split(" - ")[0].strip())
    for stem in exp_stems:
        # Extract EXP-NNN from stem
        m = re.search(r"(EXP-\d+)", stem, re.IGNORECASE)
        if m:
            search_terms.append(m.group(1))
    for stem in hyp_stems:
        # Extract H-XX-NNN from stem
        m = re.search(r"(H-?\w+-?\d+\w*)", stem, re.IGNORECASE)
        if m:
            search_terms.append(m.group(1))

    matched = []
    for rem in reminders:
        rem_lower = rem.text.lower()
        if any(term.lower() in rem_lower for term in search_terms if term):
            matched.append(rem)
    return matched


def _classify_project(
    proj: ProjectSummary,
    today: datetime.date,
    lookahead_days: int = 7,
) -> str:
    """Classify a project as needs_attention, on_track, or maintenance.

    Returns:
        One of: 'needs_attention', 'on_track', 'maintenance'.
    """
    if proj.status in ("maintenance", "archived"):
        return "maintenance"

    # Check for attention triggers
    for exp in proj.experiments:
        if exp.outcome and "null" in exp.outcome:
            return "needs_attention"
        if exp.status in ("designed", "blocked"):
            return "needs_attention"
        if exp.blocking_gate:
            return "needs_attention"
    for hyp in proj.hypotheses:
        if hyp.empirical_outcome and "negative" in hyp.empirical_outcome:
            return "needs_attention"
    # Reminders within lookahead
    cutoff = today + datetime.timedelta(days=lookahead_days)
    for rem in proj.reminders:
        try:
            rem_date = datetime.date.fromisoformat(rem.date)
            if rem_date <= cutoff:
                return "needs_attention"
        except ValueError:
            continue

    return "on_track"


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def build_project_updates(vault_path: Path, entry: ScheduleEntry) -> list[LabUpdate]:
    """Build weekly project update payloads for all labs with members.

    Scans projects/{lab}/_index.md for member lists, collects project
    state, classifies into triage tiers, and returns per-lab updates.

    Args:
        vault_path: Root of the vault.
        entry: Schedule entry configuration.

    Returns:
        List of LabUpdate objects, one per lab with members.
    """
    projects_dir = vault_path / "projects"
    if not projects_dir.is_dir():
        return []

    all_reminders = _parse_reminders(vault_path)
    today = datetime.date.today()
    updates = []

    for lab_dir in sorted(projects_dir.iterdir()):
        if not lab_dir.is_dir():
            continue
        index_path = lab_dir / "_index.md"
        if not index_path.is_file():
            continue

        members = _scan_lab_members(index_path)
        if not members:
            continue

        lab_fm = _read_frontmatter(index_path)
        lab_name = lab_fm.get("pi", lab_dir.name.title()) + " Lab"

        projects = _scan_projects(lab_dir, entry.scope)
        needs_attention = []
        on_track = []
        maintenance = []

        for proj_path, proj_fm in projects:
            tag = proj_fm.get("project_tag", proj_path.stem)
            title = proj_fm.get("title", tag)
            status = proj_fm.get("status", "active")

            # Load linked experiments
            exp_stems = _extract_wikilink_stems(proj_fm.get("linked_experiments", []))
            experiments = []
            for stem in exp_stems:
                brief = _load_experiment(vault_path, stem)
                if brief:
                    experiments.append(brief)

            # Load linked hypotheses
            hyp_stems = _extract_wikilink_stems(proj_fm.get("linked_hypotheses", []))
            hypotheses = []
            for stem in hyp_stems:
                brief = _load_hypothesis(vault_path, stem)
                if brief:
                    hypotheses.append(brief)

            # Match reminders
            matched_reminders = _match_reminders_to_project(all_reminders, proj_fm)

            # Extract goal names
            goal_stems = _extract_wikilink_stems(proj_fm.get("linked_goals", []))

            next_action = proj_fm.get("next_action", "")

            summary = ProjectSummary(
                tag=tag,
                title=title,
                status=status,
                experiments=experiments,
                hypotheses=hypotheses,
                reminders=matched_reminders,
                next_action=next_action,
                linked_goal_names=goal_stems,
            )

            category = _classify_project(summary, today)
            if category == "needs_attention":
                needs_attention.append(summary)
            elif category == "maintenance":
                maintenance.append(summary)
            else:
                on_track.append(summary)

        # Count reminders in time windows
        this_week_cutoff = today + datetime.timedelta(days=7)
        next_week_cutoff = today + datetime.timedelta(days=14)
        reminders_this_week = 0
        reminders_next_week = 0
        for rem in all_reminders:
            try:
                rd = datetime.date.fromisoformat(rem.date)
            except ValueError:
                continue
            # Match reminder to any project in this lab
            lab_tags = [fm.get("project_tag", "") for _, fm in projects]
            lab_exps = []
            for _, fm in projects:
                lab_exps.extend(
                    _extract_wikilink_stems(fm.get("linked_experiments", []))
                )
            is_lab_reminder = any(
                t.lower() in rem.text.lower() for t in lab_tags if t
            ) or any(
                re.search(r"(EXP-\d+)", s, re.IGNORECASE)
                and re.search(r"(EXP-\d+)", s, re.IGNORECASE).group(1).lower()
                in rem.text.lower()
                for s in lab_exps
            )
            if not is_lab_reminder:
                continue
            if rd <= this_week_cutoff:
                reminders_this_week += 1
            elif rd <= next_week_cutoff:
                reminders_next_week += 1

        updates.append(
            LabUpdate(
                lab_name=lab_name,
                members=members,
                needs_attention=needs_attention,
                on_track=on_track,
                maintenance=maintenance,
                reminders_this_week=reminders_this_week,
                reminders_next_week=reminders_next_week,
            )
        )

    return updates


# ---------------------------------------------------------------------------
# Message assembly
# ---------------------------------------------------------------------------


def build_scheduled_messages(
    vault_path: Path, entry: ScheduleEntry
) -> list[ScheduledMessage]:
    """Build all messages for a scheduled task.

    Dispatches to the appropriate payload builder based on entry.type,
    then formats messages per recipient according to their role.

    Args:
        vault_path: Root of the vault.
        entry: Schedule entry configuration.

    Returns:
        List of ScheduledMessage objects ready for delivery.
    """
    builders = {
        "project_update": _build_project_update_messages,
        "stale_project": _build_stale_project_messages,
        "experiment_reminder": _build_experiment_reminder_messages,
    }
    builder = builders.get(entry.type)
    if builder is None:
        logger.warning("Unknown schedule type: %s", entry.type)
        return []
    return builder(vault_path, entry)


def _build_project_update_messages(
    vault_path: Path, entry: ScheduleEntry
) -> list[ScheduledMessage]:
    """Build weekly project update DMs for all lab members."""
    from engram_r.slack_formatter import format_weekly_project_dm

    updates = build_project_updates(vault_path, entry)
    now = datetime.datetime.now()
    iso_year, iso_week, _ = now.date().isocalendar()
    week_start = datetime.date.fromisocalendar(iso_year, iso_week, 1)
    week_end = week_start + datetime.timedelta(days=6)
    week_label = (
        f"Week {iso_week}, {iso_year} "
        f"({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})"
    )

    messages = []
    for lab_update in updates:
        for member in lab_update.members:
            text, blocks = format_weekly_project_dm(
                recipient_name=member.name.split()[0],
                recipient_role=member.role,
                lab_name=lab_update.lab_name,
                week_label=week_label,
                needs_attention=lab_update.needs_attention,
                on_track=lab_update.on_track,
                maintenance=lab_update.maintenance,
                reminders_this_week=lab_update.reminders_this_week,
                reminders_next_week=lab_update.reminders_next_week,
            )
            messages.append(
                ScheduledMessage(
                    recipient_slack_id=member.slack_id,
                    recipient_name=member.name,
                    recipient_role=member.role,
                    lab=lab_update.lab_name,
                    text=text,
                    blocks=blocks,
                )
            )
    return messages


def _build_stale_project_messages(
    vault_path: Path, entry: ScheduleEntry
) -> list[ScheduledMessage]:
    """Build stale project alert DMs for lab members.

    Identifies projects with no linked experiment or hypothesis activity
    within stale_notes_days (from daemon config thresholds, default 30).
    """
    from engram_r.slack_formatter import format_stale_project_dm

    projects_dir = vault_path / "projects"
    if not projects_dir.is_dir():
        return []

    # Load stale threshold from daemon config
    config_path = vault_path / "ops" / "daemon-config.yaml"
    stale_days = 30
    if config_path.is_file():
        try:
            raw = yaml.safe_load(config_path.read_text())
            if isinstance(raw, dict):
                thresholds = raw.get("thresholds", {})
                if isinstance(thresholds, dict):
                    stale_days = thresholds.get("stale_notes_days", 30)
        except (yaml.YAMLError, OSError):
            pass

    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=stale_days)
    cutoff_ts = datetime.datetime.combine(cutoff, datetime.time()).timestamp()

    messages = []

    for lab_dir in sorted(projects_dir.iterdir()):
        if not lab_dir.is_dir():
            continue
        index_path = lab_dir / "_index.md"
        if not index_path.is_file():
            continue

        members = _scan_lab_members(index_path)
        if not members:
            continue

        lab_fm = _read_frontmatter(index_path)
        lab_name = lab_fm.get("pi", lab_dir.name.title()) + " Lab"

        projects = _scan_projects(lab_dir, entry.scope)
        stale_projects: list[tuple[str, str, int]] = []
        active_count = 0

        for proj_path, proj_fm in projects:
            tag = proj_fm.get("project_tag", proj_path.stem)
            title = proj_fm.get("title", tag)

            # Check linked experiment and hypothesis mtimes
            latest_mtime = 0.0
            exp_stems = _extract_wikilink_stems(proj_fm.get("linked_experiments", []))
            for stem in exp_stems:
                exp_path = vault_path / "_research" / "experiments" / f"{stem}.md"
                if exp_path.is_file():
                    latest_mtime = max(latest_mtime, exp_path.stat().st_mtime)

            hyp_stems = _extract_wikilink_stems(proj_fm.get("linked_hypotheses", []))
            for stem in hyp_stems:
                hyp_path = vault_path / "_research" / "hypotheses" / f"{stem}.md"
                if hyp_path.is_file():
                    latest_mtime = max(latest_mtime, hyp_path.stat().st_mtime)

            # If no linked artifacts, use project note mtime
            if latest_mtime == 0.0:
                latest_mtime = proj_path.stat().st_mtime

            if latest_mtime < cutoff_ts:
                days_stale = int(
                    (datetime.datetime.now().timestamp() - latest_mtime) / 86400
                )
                stale_projects.append((tag, title, days_stale))
            else:
                active_count += 1

        if not stale_projects:
            continue

        for member in members:
            text, blocks = format_stale_project_dm(
                recipient_name=member.name.split()[0],
                lab_name=lab_name,
                stale_projects=stale_projects,
                active_count=active_count,
            )
            messages.append(
                ScheduledMessage(
                    recipient_slack_id=member.slack_id,
                    recipient_name=member.name,
                    recipient_role=member.role,
                    lab=lab_name,
                    text=text,
                    blocks=blocks,
                )
            )

    return messages


def _build_experiment_reminder_messages(
    vault_path: Path, entry: ScheduleEntry
) -> list[ScheduledMessage]:
    """Build experiment reminder DMs for lab members.

    Scans experiments with status "designed" or "active", matches
    reminders within lookahead_days, and checks for blocking gates.
    """
    from engram_r.slack_formatter import format_experiment_reminder_dm

    projects_dir = vault_path / "projects"
    if not projects_dir.is_dir():
        return []

    all_reminders = _parse_reminders(vault_path)
    today = datetime.date.today()
    lookahead = entry.lookahead_days
    cutoff = today + datetime.timedelta(days=lookahead)

    messages = []

    for lab_dir in sorted(projects_dir.iterdir()):
        if not lab_dir.is_dir():
            continue
        index_path = lab_dir / "_index.md"
        if not index_path.is_file():
            continue

        members = _scan_lab_members(index_path)
        if not members:
            continue

        lab_fm = _read_frontmatter(index_path)
        lab_name = lab_fm.get("pi", lab_dir.name.title()) + " Lab"

        projects = _scan_projects(lab_dir, entry.scope)

        upcoming_deadlines: list[tuple[str, str, str]] = []  # (exp_id, date, text)
        blocking_gates: list[tuple[str, str]] = []  # (exp_id, gate_desc)

        for _, proj_fm in projects:
            exp_stems = _extract_wikilink_stems(proj_fm.get("linked_experiments", []))
            for stem in exp_stems:
                brief = _load_experiment(vault_path, stem)
                if brief is None:
                    continue
                if brief.status not in ("designed", "active"):
                    continue

                # Check blocking gates
                if brief.blocking_gate:
                    blocking_gates.append((brief.id, brief.blocking_gate))

                # Match reminders to this experiment
                exp_id_pattern = re.search(r"(EXP-\d+)", stem, re.IGNORECASE)
                if exp_id_pattern:
                    exp_search = exp_id_pattern.group(1)
                    for rem in all_reminders:
                        if exp_search.lower() not in rem.text.lower():
                            continue
                        try:
                            rem_date = datetime.date.fromisoformat(rem.date)
                        except ValueError:
                            continue
                        if rem_date <= cutoff:
                            upcoming_deadlines.append((brief.id, rem.date, rem.text))

        if not upcoming_deadlines and not blocking_gates:
            continue

        for member in members:
            text, blocks = format_experiment_reminder_dm(
                recipient_name=member.name.split()[0],
                lab_name=lab_name,
                upcoming_deadlines=upcoming_deadlines,
                blocking_gates=blocking_gates,
            )
            messages.append(
                ScheduledMessage(
                    recipient_slack_id=member.slack_id,
                    recipient_name=member.name,
                    recipient_role=member.role,
                    lab=lab_name,
                    text=text,
                    blocks=blocks,
                )
            )

    return messages


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def deliver_messages(messages: list[ScheduledMessage]) -> int:
    """Send scheduled messages via Slack DM.

    Args:
        messages: List of messages to deliver.

    Returns:
        Count of successfully sent messages.
    """
    from engram_r.slack_client import SlackClient

    client = SlackClient.from_env_optional()
    if client is None:
        logger.warning("Slack not configured, skipping delivery")
        return 0

    sent = 0
    for msg in messages:
        dm_channel = client.open_dm(msg.recipient_slack_id)
        if dm_channel is None:
            logger.warning(
                "Could not open DM with %s (%s)",
                msg.recipient_name,
                msg.recipient_slack_id,
            )
            continue
        try:
            client.post_message(msg.text, dm_channel, blocks=msg.blocks)
            sent += 1
            logger.info("Sent DM to %s (%s)", msg.recipient_name, msg.lab)
        except Exception:
            logger.exception("Failed to send DM to %s", msg.recipient_name)
    return sent


# ---------------------------------------------------------------------------
# Entrypoint for daemon.sh
# ---------------------------------------------------------------------------


def execute_schedule(vault_path_str: str, marker_key: str) -> int:
    """Execute a scheduled task end-to-end.

    Called by daemon.sh for notify-scheduled tasks. Loads config,
    finds the matching schedule entry, builds messages, delivers them.

    Args:
        vault_path_str: Path to the vault root.
        marker_key: The task marker key (e.g. 'sched-weekly-project-update-2026-W09').

    Returns:
        Count of messages sent.
    """
    vault_path = Path(vault_path_str)
    config_path = vault_path / "ops" / "daemon-config.yaml"
    config = load_config(config_path)

    # Find the schedule entry matching this marker key
    entry = None
    for sched in config.schedules:
        if sched.name and marker_key.startswith(f"sched-{sched.name}"):
            entry = sched
            break

    if entry is None:
        logger.error("No schedule entry found for marker key: %s", marker_key)
        return 0

    messages = build_scheduled_messages(vault_path, entry)
    if not messages:
        logger.info("No messages to send for schedule: %s", entry.name)
        return 0

    return deliver_messages(messages)
