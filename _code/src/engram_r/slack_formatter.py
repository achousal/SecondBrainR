"""Slack Block Kit message formatters for EngramR events.

Pure functions that return (text, blocks) tuples for each notification type.
text is the fallback/notification preview; blocks provide rich formatting.
"""

from __future__ import annotations

from typing import Any


def _header_block(text: str) -> dict[str, Any]:
    """Create a header block."""
    return {"type": "header", "text": {"type": "plain_text", "text": text}}


def _section_block(mrkdwn: str) -> dict[str, Any]:
    """Create a section block with mrkdwn text."""
    return {"type": "section", "text": {"type": "mrkdwn", "text": mrkdwn}}


def _context_block(elements: list[str]) -> dict[str, Any]:
    """Create a context block with mrkdwn elements."""
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": t} for t in elements],
    }


def _divider_block() -> dict[str, Any]:
    """Create a divider block."""
    return {"type": "divider"}


def format_daily_parent(date_str: str) -> tuple[str, list[dict[str, Any]]]:
    """Format the daily parent message that threads all notifications.

    Args:
        date_str: Date string (e.g. '2026-02-23').

    Returns:
        (text, blocks) tuple.
    """
    text = f"EngramR Activity -- {date_str}"
    blocks = [
        _header_block(f"EngramR Activity -- {date_str}"),
        _section_block("All vault notifications for today thread below."),
    ]
    return text, blocks


def format_session_start(
    goals: list[str] | None = None,
    vault_stats: dict[str, Any] | None = None,
    top_hypotheses: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Format a session start notification.

    Args:
        goals: Active research goal names.
        vault_stats: Dict with keys like 'claims', 'inbox', 'hypotheses'.
        top_hypotheses: Top-ranked hypothesis titles.

    Returns:
        (text, blocks) tuple.
    """
    text = "Session started"
    blocks: list[dict[str, Any]] = [_section_block("*Session started*")]

    stats = vault_stats or {}
    stat_parts = []
    if stats.get("claims"):
        stat_parts.append(f"Claims: {stats['claims']}")
    if stats.get("inbox"):
        stat_parts.append(f"Inbox: {stats['inbox']}")
    if stats.get("hypotheses"):
        stat_parts.append(f"Hypotheses: {stats['hypotheses']}")
    if stat_parts:
        blocks.append(_context_block([" | ".join(stat_parts)]))

    if goals:
        goal_lines = "\n".join(f"- {g}" for g in goals[:5])
        blocks.append(_section_block(f"*Active goals:*\n{goal_lines}"))

    if top_hypotheses:
        hyp_lines = "\n".join(top_hypotheses[:5])
        blocks.append(_section_block(f"*Top hypotheses:*\n{hyp_lines}"))

    return text, blocks


def format_session_end(
    session_id: str = "",
    files_written: list[str] | None = None,
    skills_invoked: list[str] | None = None,
    summary: str = "",
    duration_s: int = 0,
) -> tuple[str, list[dict[str, Any]]]:
    """Format a session end notification.

    Args:
        session_id: Short session ID.
        files_written: List of file paths written during the session.
        skills_invoked: List of skills used (e.g. ['/generate', '/tournament']).
        summary: Brief session summary.
        duration_s: Session duration in seconds.

    Returns:
        (text, blocks) tuple.
    """
    duration_str = _format_duration(duration_s) if duration_s > 0 else ""
    text = f"Session ended ({session_id[:8]})"

    blocks: list[dict[str, Any]] = [_section_block("*Session ended*")]

    ctx_parts = []
    if session_id:
        ctx_parts.append(f"ID: `{session_id[:8]}`")
    if duration_str:
        ctx_parts.append(f"Duration: {duration_str}")
    files = files_written or []
    if files:
        ctx_parts.append(f"Files: {len(files)}")
    if ctx_parts:
        blocks.append(_context_block([" | ".join(ctx_parts)]))

    skills = skills_invoked or []
    if skills:
        blocks.append(_section_block(f"*Skills:* {', '.join(skills)}"))

    if summary:
        truncated = summary[:500] + "..." if len(summary) > 500 else summary
        blocks.append(_section_block(f"*Summary:* {truncated}"))

    return text, blocks


def format_daemon_task_complete(
    skill: str = "",
    task_key: str = "",
    model: str = "",
    elapsed_s: int = 0,
) -> tuple[str, list[dict[str, Any]]]:
    """Format a daemon task completion notification.

    Args:
        skill: Skill that was executed (e.g. 'tournament').
        task_key: Unique task identifier.
        model: Model used (e.g. 'sonnet').
        elapsed_s: Execution time in seconds.

    Returns:
        (text, blocks) tuple.
    """
    duration_str = _format_duration(elapsed_s) if elapsed_s > 0 else ""
    text = f"Daemon: {skill} completed ({task_key})"

    blocks: list[dict[str, Any]] = [
        _section_block(f"*Daemon task completed:* `{skill}`"),
    ]

    ctx_parts = []
    if task_key:
        ctx_parts.append(f"Key: `{task_key}`")
    if model:
        ctx_parts.append(f"Model: {model}")
    if duration_str:
        ctx_parts.append(duration_str)
    if ctx_parts:
        blocks.append(_context_block([" | ".join(ctx_parts)]))

    return text, blocks


def format_daemon_alert(
    message: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    """Format a daemon alert notification.

    Args:
        message: Alert message text.

    Returns:
        (text, blocks) tuple.
    """
    text = f"Daemon alert: {message}"
    blocks: list[dict[str, Any]] = [
        _section_block(f"*Daemon alert*\n{message}"),
    ]
    return text, blocks


def format_daemon_for_you(
    entries: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Format daemon 'For You' items (queued for human review).

    Args:
        entries: List of entry descriptions.

    Returns:
        (text, blocks) tuple.
    """
    items = entries or []
    text = f"Daemon: {len(items)} item(s) for your review"
    blocks: list[dict[str, Any]] = [
        _section_block(f"*For You* -- {len(items)} item(s) queued for review"),
    ]
    if items:
        item_text = "\n".join(f"- {e}" for e in items[:10])
        blocks.append(_section_block(item_text))
    return text, blocks


def format_tournament_result(
    goal_id: str = "",
    matches: int = 0,
    top_hypotheses: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Format a tournament result notification.

    Args:
        goal_id: Research goal identifier.
        matches: Number of matches completed.
        top_hypotheses: Top-ranked hypothesis titles after the tournament.

    Returns:
        (text, blocks) tuple.
    """
    text = f"Tournament: {matches} matches for {goal_id}"
    blocks: list[dict[str, Any]] = [
        _section_block(f"*Tournament results* -- `{goal_id}`"),
    ]

    ctx_parts = [f"Matches: {matches}"]
    blocks.append(_context_block(ctx_parts))

    hyps = top_hypotheses or []
    if hyps:
        hyp_text = "\n".join(hyps[:5])
        blocks.append(_section_block(f"*Leaderboard:*\n{hyp_text}"))

    return text, blocks


def format_meta_review(
    goal_id: str = "",
    hypotheses_reviewed: int = 0,
    matches_analyzed: int = 0,
    key_patterns: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Format a meta-review completion notification.

    Args:
        goal_id: Research goal identifier.
        hypotheses_reviewed: Number of hypotheses reviewed.
        matches_analyzed: Number of tournament matches analyzed.
        key_patterns: Key patterns extracted.

    Returns:
        (text, blocks) tuple.
    """
    text = (
        f"Meta-review: {goal_id}"
        f" ({hypotheses_reviewed} hyps, {matches_analyzed} matches)"
    )
    blocks: list[dict[str, Any]] = [
        _section_block(f"*Meta-review completed* -- `{goal_id}`"),
    ]

    ctx_parts = [
        f"Hypotheses: {hypotheses_reviewed}",
        f"Matches: {matches_analyzed}",
    ]
    blocks.append(_context_block(ctx_parts))

    patterns = key_patterns or []
    if patterns:
        pattern_text = "\n".join(f"- {p}" for p in patterns[:5])
        blocks.append(_section_block(f"*Key patterns:*\n{pattern_text}"))

    return text, blocks


def format_inbound_summary(
    messages: list[dict[str, str]],
    channel_name: str = "",
) -> str:
    """Format inbound Slack messages for session orientation.

    Args:
        messages: List of dicts with 'user', 'text', 'ts' keys.
        channel_name: Name of the channel for display.

    Returns:
        Plain text summary for inclusion in the orientation block.
    """
    if not messages:
        return ""

    header = f"Slack messages ({channel_name})" if channel_name else "Slack messages"
    lines = [header]
    for msg in messages[:10]:
        user = msg.get("user", "unknown")
        text = msg.get("text", "")
        # Truncate long messages
        if len(text) > 200:
            text = text[:200] + "..."
        lines.append(f"  [{user}] {text}")

    if len(messages) > 10:
        lines.append(f"  ... and {len(messages) - 10} more")

    return "\n".join(lines)


def format_weekly_project_dm(
    recipient_name: str,
    recipient_role: str,
    lab_name: str,
    week_label: str,
    needs_attention: list | None = None,
    on_track: list | None = None,
    maintenance: list | None = None,
    reminders_this_week: int = 0,
    reminders_next_week: int = 0,
) -> tuple[str, list[dict[str, Any]]]:
    """Format a weekly project update DM for a lab member.

    Content adapts to recipient role:
    - lead/contributor: Full detail for all project tiers.
    - observer: Full detail for needs_attention, counts only for rest.

    Args:
        recipient_name: First name of recipient (for greeting).
        recipient_role: One of 'lead', 'contributor', 'observer'.
        lab_name: Display name of the lab.
        week_label: Human-readable week range (e.g. 'Week 9, 2026 (Feb 23 - Mar 1)').
        needs_attention: Projects requiring action.
        on_track: Active projects without blockers.
        maintenance: Projects in maintenance/archived status.
        reminders_this_week: Count of reminders due within 7 days.
        reminders_next_week: Count of reminders due within 8-14 days.

    Returns:
        (text, blocks) tuple for Slack Block Kit.
    """
    attn = needs_attention or []
    track = on_track or []
    maint = maintenance or []
    total = len(attn) + len(track) + len(maint)
    is_observer = recipient_role == "observer"

    text = f"Weekly Project Update -- {lab_name} ({week_label})"

    blocks: list[dict[str, Any]] = [
        _header_block(f"Weekly Project Update -- {lab_name}"),
        _context_block([week_label]),
        _section_block(
            f"Hi {recipient_name},\n\n"
            f"Here is your weekly update for "
            f"{total} project(s) in {lab_name}."
        ),
    ]

    # -- Needs Attention (full detail for all roles) --
    if attn:
        blocks.append(_divider_block())
        blocks.append(_section_block(f"*NEEDS ATTENTION ({len(attn)})*"))
        for proj in attn:
            blocks.append(_section_block(_render_attention_project(proj)))

    # -- On Track --
    if track:
        blocks.append(_divider_block())
        if is_observer:
            blocks.append(_section_block(f"*ON TRACK* -- {len(track)} project(s)"))
        else:
            blocks.append(_section_block(f"*ON TRACK ({len(track)})*"))
            # Render compact one-liners, splitting into chunks to stay
            # under the 3000-char Block Kit section limit
            lines = [_render_ontrack_project(p) for p in track]
            _append_chunked_sections(blocks, lines, max_chars=2800)

    # -- Maintenance --
    if maint:
        blocks.append(_divider_block())
        if is_observer:
            blocks.append(_section_block(f"*MAINTENANCE* -- {len(maint)} project(s)"))
        else:
            blocks.append(_section_block(f"*MAINTENANCE ({len(maint)})*"))
            lines = [f"`{p.tag}` -- {p.title} | {p.status}" for p in maint]
            _append_chunked_sections(blocks, lines, max_chars=2800)

    # -- Footer --
    blocks.append(_divider_block())
    footer_parts = [
        f"Reminders due this week: {reminders_this_week}",
        f"Next week: {reminders_next_week}",
    ]
    blocks.append(_context_block([" | ".join(footer_parts)]))

    # Guard against Block Kit 50-block limit
    if len(blocks) > 48:
        blocks = blocks[:47]
        blocks.append(
            _context_block(["(truncated -- too many projects for one message)"])
        )

    return text, blocks


def format_stale_project_dm(
    recipient_name: str,
    lab_name: str,
    stale_projects: list[tuple[str, str, int]],
    active_count: int = 0,
) -> tuple[str, list[dict[str, Any]]]:
    """Format a stale project alert DM for a lab member.

    Args:
        recipient_name: First name of recipient.
        lab_name: Display name of the lab.
        stale_projects: List of (tag, title, days_stale) tuples.
        active_count: Number of non-stale active projects.

    Returns:
        (text, blocks) tuple for Slack Block Kit.
    """
    total = len(stale_projects) + active_count
    text = f"Stale Project Alert -- {lab_name}"

    blocks: list[dict[str, Any]] = [
        _header_block(f"Stale Project Alert -- {lab_name}"),
        _section_block(
            f"Hi {recipient_name},\n\n"
            f"{len(stale_projects)} of {total} project(s) have had no "
            f"experiment or hypothesis activity recently."
        ),
        _divider_block(),
    ]

    lines = []
    for tag, title, days in stale_projects:
        lines.append(f"`{tag}` -- {title} ({days} days since last activity)")
    _append_chunked_sections(blocks, lines, max_chars=2800)

    blocks.append(_divider_block())
    blocks.append(
        _context_block([f"Stale: {len(stale_projects)} | Active: {active_count}"])
    )

    return text, blocks


def format_experiment_reminder_dm(
    recipient_name: str,
    lab_name: str,
    upcoming_deadlines: list[tuple[str, str, str]] | None = None,
    blocking_gates: list[tuple[str, str]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Format an experiment reminder DM for a lab member.

    Args:
        recipient_name: First name of recipient.
        lab_name: Display name of the lab.
        upcoming_deadlines: List of (exp_id, date, text) tuples.
        blocking_gates: List of (exp_id, gate_description) tuples.

    Returns:
        (text, blocks) tuple for Slack Block Kit.
    """
    deadlines = upcoming_deadlines or []
    gates = blocking_gates or []
    text = f"Experiment Reminders -- {lab_name}"

    blocks: list[dict[str, Any]] = [
        _header_block(f"Experiment Reminders -- {lab_name}"),
        _section_block(f"Hi {recipient_name},"),
    ]

    if deadlines:
        blocks.append(_divider_block())
        blocks.append(_section_block(f"*UPCOMING DEADLINES ({len(deadlines)})*"))
        lines = []
        for exp_id, date, reminder_text in deadlines:
            lines.append(f"`{exp_id}` -- {date}: {reminder_text}")
        _append_chunked_sections(blocks, lines, max_chars=2800)

    if gates:
        blocks.append(_divider_block())
        blocks.append(_section_block(f"*BLOCKING GATES ({len(gates)})*"))
        lines = []
        for exp_id, gate_desc in gates:
            lines.append(f"`{exp_id}` -- {gate_desc}")
        _append_chunked_sections(blocks, lines, max_chars=2800)

    return text, blocks


def _render_attention_project(proj: Any) -> str:
    """Render a needs-attention project as mrkdwn text."""
    lines = [f"*`{proj.tag}`* -- {proj.title}"]
    lines.append(f"  Status: {proj.status}")

    for exp in proj.experiments:
        parts = [f"{exp.id} -- {exp.status}"]
        if exp.outcome:
            parts.append(f"({exp.outcome})")
        elif exp.blocking_gate:
            parts.append(f"(blocked: {exp.blocking_gate})")
        lines.append(f"  Experiment: {' '.join(parts)}")

    for hyp in proj.hypotheses:
        parts = [f"{hyp.id} -- {hyp.status}"]
        elo_str = f"Elo {hyp.elo:.0f}" if hyp.elo else ""
        outcome_str = hyp.empirical_outcome if hyp.empirical_outcome else ""
        detail = ", ".join(p for p in [elo_str, outcome_str] if p)
        if detail:
            parts.append(f"({detail})")
        lines.append(f"  Hypothesis: {' '.join(parts)}")

    for rem in proj.reminders:
        lines.append(f"  Reminder: {rem.date} -- {rem.text}")

    if proj.next_action:
        lines.append(f"  Next: {proj.next_action}")

    return "\n".join(lines)


def _render_ontrack_project(proj: Any) -> str:
    """Render an on-track project as a compact one-liner."""
    detail_parts = [f"Status: {proj.status}"]
    if proj.experiments:
        detail_parts.append(f"{len(proj.experiments)} experiment(s)")
    else:
        detail_parts.append("No experiments")
    if proj.hypotheses:
        detail_parts.append(f"{len(proj.hypotheses)} hypothesis(es)")
    else:
        detail_parts.append("No hypotheses")
    return f"`{proj.tag}` -- {proj.title}\n  {' | '.join(detail_parts)}"


def _append_chunked_sections(
    blocks: list[dict[str, Any]],
    lines: list[str],
    max_chars: int = 2800,
) -> None:
    """Append lines as section blocks, splitting to respect char limits."""
    chunk: list[str] = []
    chunk_len = 0
    for line in lines:
        if chunk_len + len(line) + 1 > max_chars and chunk:
            blocks.append(_section_block("\n".join(chunk)))
            chunk = []
            chunk_len = 0
        chunk.append(line)
        chunk_len += len(line) + 1
    if chunk:
        blocks.append(_section_block("\n".join(chunk)))


def format_slack_skill_queued(
    skill: str = "",
    entry_id: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    """Format a Slack skill queue acknowledgment.

    Args:
        skill: Skill that was queued (e.g. 'stats').
        entry_id: Queue entry identifier.

    Returns:
        (text, blocks) tuple.
    """
    text = f"Queued /{skill} ({entry_id})"
    blocks: list[dict[str, Any]] = [
        _section_block(f"Queued `/{skill}` for execution."),
    ]
    ctx_parts = [f"ID: `{entry_id}`"]
    blocks.append(_context_block(ctx_parts))
    return text, blocks


def format_slack_skill_complete(
    skill: str = "",
    entry_id: str = "",
    outcome: str = "",
    elapsed_s: int = 0,
    result_summary: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    """Format a Slack skill completion notification.

    Args:
        skill: Skill that was executed (e.g. 'stats').
        entry_id: Queue entry identifier.
        outcome: 'completed' or 'failed'.
        elapsed_s: Execution time in seconds.
        result_summary: Truncated result content.

    Returns:
        (text, blocks) tuple.
    """
    status_word = "completed" if outcome == "completed" else "failed"
    duration_str = _format_duration(elapsed_s) if elapsed_s > 0 else ""
    text = f"/{skill} {status_word} ({entry_id})"

    blocks: list[dict[str, Any]] = [
        _section_block(f"`/{skill}` {status_word}"),
    ]

    ctx_parts = [f"ID: `{entry_id}`"]
    if duration_str:
        ctx_parts.append(duration_str)
    blocks.append(_context_block(ctx_parts))

    if result_summary:
        truncated = result_summary[:2800]
        if len(result_summary) > 2800:
            truncated += "\n..."
        blocks.append(_section_block(truncated))

    return text, blocks


def _format_duration(seconds: int) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining = seconds % 60
    if minutes < 60:
        return f"{minutes}m {remaining}s" if remaining else f"{minutes}m"
    hours = minutes // 60
    remaining_min = minutes % 60
    return f"{hours}h {remaining_min}m"
