"""Vault Advisor -- goal-aware content suggestions for skills.

Centralizes "what content is most valuable?" into one testable module.
Phase 1: goal frontier channel only -- parse goal files, detect section gaps,
produce ranked suggestions formatted per calling context.

CLI usage:
    python -m engram_r.vault_advisor VAULT_PATH --context literature --max 4 [--no-cache]

Output JSON: {"context": "...", "suggestions": [...], "cached": bool}
Exit codes: 0 = suggestions, 2 = no gaps, 1 = error
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Frontmatter parser (same pattern as daemon_scheduler)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)

VALID_CONTEXTS = frozenset(
    {"literature", "learn", "generate", "reflect", "reweave", "reduce", "ralph"}
)

# Gap weights for priority formula
_GAP_WEIGHTS: dict[str, int] = {
    "missing_key_literature": 1,
    "missing_background": 2,
    "thin_objective": 3,
}

_THIN_OBJECTIVE_WORDS = 10


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GoalProfile:
    """Parsed representation of a single goal file."""

    goal_id: str
    title: str
    domain: str
    status: str
    objective: str
    has_background: bool
    has_key_literature: bool
    path: Path


@dataclass
class Suggestion:
    """A ranked content suggestion for a specific calling context."""

    channel: str
    query: str
    rationale: str
    priority: int
    goal_ref: str
    scope: str = "full"


@dataclass
class QueuePhaseState:
    """Aggregated phase state from per-claim task files in ops/queue/."""

    total_tasks: int
    sources: set[str] = field(default_factory=set)
    phase_counts: dict[str, int] = field(default_factory=dict)
    sources_with_pending_create: set[str] = field(default_factory=set)
    sources_with_pending_reflect: set[str] = field(default_factory=set)
    sources_with_pending_reweave: set[str] = field(default_factory=set)


@dataclass
class PipelineTip:
    """A pipeline ordering tip detected from queue phase state."""

    tip_id: str
    message: str
    rationale: str
    priority: int  # lower = more urgent


@dataclass
class SessionTip:
    """A session-level tip detected from vault state."""

    tip_id: str
    message: str
    rationale: str
    priority: int  # lower = more urgent


@dataclass
class VaultSnapshot:
    """Lightweight vault state counts for session tip detection."""

    claim_count: int = 0
    inbox_count: int = 0
    observation_count: int = 0
    tension_count: int = 0
    queue_pending: int = 0
    hypothesis_count: int = 0
    has_recent_reduce: bool = False


# ---------------------------------------------------------------------------
# Vault snapshot building
# ---------------------------------------------------------------------------


def _count_md_files(directory: Path) -> int:
    """Count .md files in a directory (non-recursive, excludes dotfiles)."""
    if not directory.is_dir():
        return 0
    return sum(
        1
        for f in directory.iterdir()
        if f.suffix == ".md" and not f.name.startswith(".")
    )


def _has_recent_reduce(vault_path: Path, window_hours: int = 24) -> bool:
    """Check if any queue task file was modified within the window."""
    import time

    queue_dir = vault_path / "ops" / "queue"
    if not queue_dir.is_dir():
        return False
    cutoff = time.time() - (window_hours * 3600)
    for f in queue_dir.iterdir():
        if f.suffix == ".md":
            try:
                if f.stat().st_mtime >= cutoff:
                    return True
            except OSError:
                continue
    return False


def build_vault_snapshot(vault_path: Path) -> VaultSnapshot:
    """Build a lightweight vault state snapshot for session tip detection."""
    return VaultSnapshot(
        claim_count=_count_md_files(vault_path / "notes"),
        inbox_count=_count_md_files(vault_path / "inbox"),
        observation_count=_count_md_files(vault_path / "ops" / "observations"),
        tension_count=_count_md_files(vault_path / "ops" / "tensions"),
        queue_pending=_count_md_files(vault_path / "ops" / "queue"),
        hypothesis_count=_count_md_files(
            vault_path / "_research" / "hypotheses"
        ),
        has_recent_reduce=_has_recent_reduce(vault_path),
    )


# ---------------------------------------------------------------------------
# Session tip detection
# ---------------------------------------------------------------------------


def detect_session_tips(snapshot: VaultSnapshot) -> list[SessionTip]:
    """Detect session tips from vault state. Returns sorted by priority."""
    tips: list[SessionTip] = []

    # Tip 1: reduce_inbox -- inbox has items and no recent reduce activity
    if snapshot.inbox_count > 0 and not snapshot.has_recent_reduce:
        tips.append(
            SessionTip(
                tip_id="reduce_inbox",
                message=(
                    f"{snapshot.inbox_count} inbox items waiting "
                    "-- run /reduce or /pipeline to process them"
                ),
                rationale=(
                    "Inbox items lose context over time. Processing them "
                    "while the source material is fresh improves extraction "
                    "quality."
                ),
                priority=0,
            )
        )

    # Tip 2: unblock_queue -- queue has pending tasks
    if snapshot.queue_pending > 0:
        tips.append(
            SessionTip(
                tip_id="unblock_queue",
                message=(
                    f"{snapshot.queue_pending} queue tasks pending "
                    "-- run /ralph to process them"
                ),
                rationale=(
                    "Pending queue tasks block downstream phases. "
                    "Processing them unblocks reflect and reweave."
                ),
                priority=1,
            )
        )

    # Tip 3: generate_hypotheses -- enough claims but no hypotheses
    if snapshot.claim_count >= 20 and snapshot.hypothesis_count == 0:
        tips.append(
            SessionTip(
                tip_id="generate_hypotheses",
                message=(
                    f"{snapshot.claim_count} claims accumulated with no "
                    "hypotheses -- run /generate to synthesize them"
                ),
                rationale=(
                    "A critical mass of claims enables hypothesis "
                    "generation. Without hypotheses the knowledge graph "
                    "lacks a forward-looking dimension."
                ),
                priority=1,
            )
        )

    # Tip 4: rethink_observations -- observation backlog
    if snapshot.observation_count >= 10:
        tips.append(
            SessionTip(
                tip_id="rethink_observations",
                message=(
                    f"{snapshot.observation_count} observations accumulated "
                    "-- run /rethink to triage them"
                ),
                rationale=(
                    "Observations capture friction signals. Triaging them "
                    "prevents recurring issues and surfaces improvement "
                    "opportunities."
                ),
                priority=2,
            )
        )

    # Tip 5: rethink_tensions -- tension backlog
    if snapshot.tension_count >= 5:
        tips.append(
            SessionTip(
                tip_id="rethink_tensions",
                message=(
                    f"{snapshot.tension_count} tensions accumulated "
                    "-- run /rethink to resolve them"
                ),
                rationale=(
                    "Tensions represent contradictions in the knowledge "
                    "graph. Resolving them improves internal consistency."
                ),
                priority=2,
            )
        )

    tips.sort(key=lambda t: t.priority)
    return tips


def generate_session_suggestions(
    tips: list[SessionTip], max_suggestions: int = 1
) -> list[Suggestion]:
    """Convert SessionTip objects to Suggestion objects."""
    suggestions: list[Suggestion] = []
    for tip in tips[:max_suggestions]:
        suggestions.append(
            Suggestion(
                channel="session_tip",
                query=tip.message,
                rationale=tip.rationale,
                priority=tip.priority,
                goal_ref="",
            )
        )
    return suggestions


# ---------------------------------------------------------------------------
# Goal file parsing
# ---------------------------------------------------------------------------


def _read_frontmatter(path: Path) -> dict:
    """Read YAML frontmatter from a markdown file. Returns {} on failure."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        logger.warning("Cannot read file: %s", path)
        return {}
    m = _FM_RE.match(text)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        logger.warning("Malformed YAML frontmatter in %s", path)
        return {}


def _parse_sections(text: str) -> dict[str, str]:
    """Split markdown body into {section_name: body} by ## headings."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections[name] = body
    return sections


def _section_present(sections: dict[str, str], name: str) -> bool:
    """A section is 'present' if it has at least one non-whitespace line."""
    body = sections.get(name, "")
    return bool(body.strip())


def parse_goal_file(path: Path) -> GoalProfile | None:
    """Parse a single goal .md file into a GoalProfile.

    Returns None if the file is missing, unreadable, or lacks required
    frontmatter fields (title).
    """
    try:
        text = path.read_text(errors="replace")
    except OSError:
        logger.warning("Cannot read goal file: %s", path)
        return None

    fm_match = _FM_RE.match(text)
    if not fm_match:
        return None

    try:
        fm = yaml.safe_load(fm_match.group(1))
        if not isinstance(fm, dict):
            return None
    except yaml.YAMLError:
        logger.warning("Malformed YAML in goal file: %s", path)
        return None

    title = fm.get("title", "")
    if not title:
        return None

    sections = _parse_sections(text)
    objective_text = sections.get("Objective", "")

    return GoalProfile(
        goal_id=path.stem,
        title=title,
        domain=fm.get("domain", ""),
        status=fm.get("status", ""),
        objective=objective_text,
        has_background=_section_present(sections, "Background"),
        has_key_literature=_section_present(sections, "Key Literature"),
        path=path,
    )


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------


def detect_gaps(profile: GoalProfile) -> list[str]:
    """Return gap labels for a parsed goal profile.

    Possible gaps: missing_key_literature, missing_background, thin_objective.
    """
    gaps: list[str] = []

    if not profile.has_key_literature:
        gaps.append("missing_key_literature")

    if not profile.has_background:
        gaps.append("missing_background")

    word_count = len(profile.objective.split())
    if word_count < _THIN_OBJECTIVE_WORDS:
        gaps.append("thin_objective")

    return gaps


# ---------------------------------------------------------------------------
# Goal frontier scanning
# ---------------------------------------------------------------------------


def scan_goal_frontier(
    vault_path: Path, goals_priority: list[str]
) -> list[GoalProfile]:
    """Scan _research/goals/, return active goals in priority order.

    Goals listed in goals_priority come first (in that order), followed
    by any active goals not in the priority list (alphabetical).
    """
    goals_dir = vault_path / "_research" / "goals"
    if not goals_dir.is_dir():
        return []

    # Parse all goal files
    all_profiles: dict[str, GoalProfile] = {}
    for md_file in goals_dir.glob("*.md"):
        profile = parse_goal_file(md_file)
        if profile and profile.status == "active":
            all_profiles[profile.goal_id] = profile

    # Order: priority list first, then remaining alphabetically
    ordered: list[GoalProfile] = []
    seen: set[str] = set()

    for goal_id in goals_priority:
        if goal_id in all_profiles:
            ordered.append(all_profiles[goal_id])
            seen.add(goal_id)

    for goal_id in sorted(all_profiles.keys()):
        if goal_id not in seen:
            ordered.append(all_profiles[goal_id])

    return ordered


# ---------------------------------------------------------------------------
# Context formatting
# ---------------------------------------------------------------------------


def _format_for_context(
    context: str, profile: GoalProfile, gap: str
) -> tuple[str, str]:
    """Produce (query, rationale) formatted for the calling context.

    Returns a domain-specific query string and a one-sentence rationale.
    """
    domain = profile.domain or "general"
    objective = profile.objective or profile.title

    # Build keyword core from objective (first ~8 significant words)
    keywords = " ".join(objective.split()[:8])

    gap_label = gap.replace("_", " ")

    if context in ("literature", "learn"):
        query = f"{keywords} {domain}"
        rationale = f"Goal '{profile.goal_id}' has {gap_label}; search can fill this gap"
    elif context == "generate":
        query = f"Hypothesize mechanisms related to: {objective}"
        rationale = (
            f"Goal '{profile.goal_id}' has {gap_label}; "
            f"generating hypotheses can accelerate exploration"
        )
    elif context == "reflect":
        query = f"What do we know about {keywords}?"
        rationale = (
            f"Goal '{profile.goal_id}' has {gap_label}; "
            f"reflection can surface existing connections"
        )
    elif context == "reweave":
        query = f"Find notes relevant to {keywords}"
        rationale = (
            f"Goal '{profile.goal_id}' has {gap_label}; "
            f"reweaving can bridge existing knowledge"
        )
    elif context == "reduce":
        query = f"Prioritize inbox items related to {domain}"
        rationale = (
            f"Goal '{profile.goal_id}' has {gap_label}; "
            f"reducing relevant sources is high-value"
        )
    else:
        query = keywords
        rationale = f"Goal '{profile.goal_id}' has {gap_label}"

    return query, rationale


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------


def generate_suggestions(
    profiles: list[GoalProfile],
    context: str,
    max_suggestions: int = 4,
) -> list[Suggestion]:
    """Rank gaps across goals, format for context.

    Priority formula: (goal_rank * 10) + gap_weight
    where goal_rank is the 0-based index in the profiles list.
    """
    if context not in VALID_CONTEXTS:
        context = "literature"

    raw: list[tuple[int, str, GoalProfile]] = []

    for rank, profile in enumerate(profiles):
        gaps = detect_gaps(profile)
        for gap in gaps:
            weight = _GAP_WEIGHTS.get(gap, 9)
            priority = (rank * 10) + weight
            raw.append((priority, gap, profile))

    raw.sort(key=lambda x: x[0])

    suggestions: list[Suggestion] = []
    for priority, gap, profile in raw[:max_suggestions]:
        query, rationale = _format_for_context(context, profile, gap)
        suggestions.append(
            Suggestion(
                channel="goal_frontier",
                query=query,
                rationale=rationale,
                priority=priority,
                goal_ref=profile.goal_id,
            )
        )

    return suggestions


# ---------------------------------------------------------------------------
# Pipeline tip scanning (Phase 2 channel)
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\(to be filled by", re.IGNORECASE)


def _detect_task_phase(sections: dict[str, str]) -> str | None:
    """Determine which phase a task file is pending at.

    Returns the phase name (create, enrich, reflect, reweave, verify)
    or None if the task appears fully processed.
    """
    reduce_filled = _section_present(sections, "Reduce Notes")

    # Claim tasks: Create section
    create_body = sections.get("Create", "")
    create_placeholder = bool(_PLACEHOLDER_RE.search(create_body))
    if reduce_filled and create_placeholder:
        return "create"

    # Enrichment tasks: Enrich section
    enrich_body = sections.get("Enrich", "")
    enrich_placeholder = bool(_PLACEHOLDER_RE.search(enrich_body))
    if reduce_filled and enrich_placeholder:
        return "enrich"

    # Check reflect
    reflect_body = sections.get("/reflect", "")
    reflect_placeholder = bool(_PLACEHOLDER_RE.search(reflect_body))
    create_or_enrich_filled = (
        _section_present(sections, "Create")
        or _section_present(sections, "Enrich")
    )
    if create_or_enrich_filled and reflect_placeholder:
        return "reflect"

    # Check reweave
    reweave_body = sections.get("/reweave", "")
    reweave_placeholder = bool(_PLACEHOLDER_RE.search(reweave_body))
    if _section_present(sections, "/reflect") and reweave_placeholder:
        return "reweave"

    # Check verify
    verify_body = sections.get("/verify", "")
    verify_placeholder = bool(_PLACEHOLDER_RE.search(verify_body))
    if _section_present(sections, "/reweave") and verify_placeholder:
        return "verify"

    return None


def scan_queue_phases(vault_path: Path) -> QueuePhaseState:
    """Scan per-claim task files in ops/queue/ and aggregate phase state.

    Parses each .md file's frontmatter for source_task and sections
    to determine what phase each task is pending at.
    """
    queue_dir = vault_path / "ops" / "queue"
    if not queue_dir.is_dir():
        return QueuePhaseState(total_tasks=0)

    state = QueuePhaseState(total_tasks=0)

    for md_file in queue_dir.glob("*.md"):
        if md_file.name == "queue.yaml" or md_file.name == "queue.json":
            continue
        try:
            text = md_file.read_text(errors="replace")
        except OSError:
            continue

        fm = {}
        fm_match = _FM_RE.match(text)
        if fm_match:
            try:
                fm = yaml.safe_load(fm_match.group(1))
                if not isinstance(fm, dict):
                    fm = {}
            except yaml.YAMLError:
                fm = {}

        source = fm.get("source_task", "")
        if not source:
            continue

        state.total_tasks += 1
        state.sources.add(source)

        sections = _parse_sections(text)
        phase = _detect_task_phase(sections)

        if phase:
            state.phase_counts[phase] = state.phase_counts.get(phase, 0) + 1

            if phase in ("create", "enrich"):
                state.sources_with_pending_create.add(source)
            elif phase == "reflect":
                state.sources_with_pending_reflect.add(source)
            elif phase == "reweave":
                state.sources_with_pending_reweave.add(source)

    return state


_VALID_SCOPES = frozenset({"full", "methods_only"})


def scan_extract_scopes(vault_path: Path) -> dict[str, str]:
    """Scan ops/queue/*.md for extract-type tasks and return {task_id: scope}.

    Reads frontmatter from each .md file in the queue directory.  Only files
    with ``type: extract`` are considered.  The ``scope`` field defaults to
    ``"full"`` when absent.  Invalid scope values are silently ignored (the
    task is omitted from the result).
    """
    queue_dir = vault_path / "ops" / "queue"
    if not queue_dir.is_dir():
        return {}

    result: dict[str, str] = {}
    for md_file in queue_dir.glob("*.md"):
        try:
            text = md_file.read_text(errors="replace")
        except OSError:
            continue

        fm_match = _FM_RE.match(text)
        if not fm_match:
            continue
        try:
            fm = yaml.safe_load(fm_match.group(1))
            if not isinstance(fm, dict):
                continue
        except yaml.YAMLError:
            continue

        if fm.get("type") != "extract":
            continue

        task_id = fm.get("id", md_file.stem)
        scope = fm.get("scope", "full")
        if scope not in _VALID_SCOPES:
            continue

        result[task_id] = scope

    return result


def detect_pipeline_tips(phase_state: QueuePhaseState) -> list[PipelineTip]:
    """Detect pipeline ordering opportunities from queue phase state.

    Returns tips sorted by priority (lower = more urgent).
    """
    tips: list[PipelineTip] = []

    # Tip 1: reduce_before_reflect -- multi-source with mixed create/reflect
    if (
        len(phase_state.sources_with_pending_reflect) >= 2
        and len(phase_state.sources_with_pending_create) > 0
    ):
        n_create = len(phase_state.sources_with_pending_create)
        n_reflect = len(phase_state.sources_with_pending_reflect)
        tips.append(
            PipelineTip(
                tip_id="reduce_before_reflect",
                message=(
                    f"Complete all reduce/create phases ({n_create} sources pending) "
                    f"before starting reflect ({n_reflect} sources ready) "
                    "-- cross-source connections need the full claim surface"
                ),
                rationale=(
                    "Reflect finds connections between claims. Running reflect "
                    "before all reductions complete misses cross-source connections "
                    "that only exist after the full claim surface is available."
                ),
                priority=0,
            )
        )

    # Tip 2: batch_reflect_ready -- all sources done reducing, ready for reflect
    if (
        len(phase_state.sources_with_pending_reflect) >= 2
        and len(phase_state.sources_with_pending_create) == 0
    ):
        n_sources = len(phase_state.sources_with_pending_reflect)
        tips.append(
            PipelineTip(
                tip_id="batch_reflect_ready",
                message=(
                    f"All reductions complete across {n_sources} sources. "
                    f"Run reflect as a batch to maximize cross-source connections"
                ),
                rationale=(
                    "The full claim surface is now available. Batching reflect "
                    "across all sources finds connections that per-source "
                    "processing would miss."
                ),
                priority=1,
            )
        )

    # Tip 3: reweave_after_reflect -- mixed reflect/reweave
    if (
        len(phase_state.sources_with_pending_reflect) > 0
        and len(phase_state.sources_with_pending_reweave) > 0
    ):
        tips.append(
            PipelineTip(
                tip_id="reweave_after_reflect",
                message=(
                    "Finish all reflect phases before reweave "
                    "-- reweave updates old notes, which should include "
                    "the new connections from reflect"
                ),
                rationale=(
                    "Reweave is a backward pass that updates older notes. "
                    "Running it before reflect completes means the new "
                    "connections from reflect are not yet available to "
                    "propagate backward."
                ),
                priority=2,
            )
        )

    tips.sort(key=lambda t: t.priority)
    return tips


def generate_pipeline_suggestions(
    tips: list[PipelineTip], max_suggestions: int = 4
) -> list[Suggestion]:
    """Convert PipelineTip objects to Suggestion objects."""
    suggestions: list[Suggestion] = []
    for tip in tips[:max_suggestions]:
        suggestions.append(
            Suggestion(
                channel="pipeline_tip",
                query=tip.message,
                rationale=tip.rationale,
                priority=tip.priority,
                goal_ref="",
            )
        )
    return suggestions


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def _session_key() -> str:
    """Build a session key from PID and date."""
    from datetime import date

    return f"{os.getpid()}-{date.today().isoformat()}"


def load_cache(cache_path: Path) -> dict | None:
    """Read advisor cache. Returns None if missing or stale."""
    if not cache_path.is_file():
        return None
    try:
        data = json.loads(cache_path.read_text())
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(
    cache_path: Path,
    suggestions: list[Suggestion],
    session_key: str,
    context: str,
    max_suggestions: int,
) -> None:
    """Atomic write of advisor cache."""
    data = {
        "session_key": session_key,
        "context": context,
        "max_suggestions": max_suggestions,
        "suggestions": [
            {
                "channel": s.channel,
                "query": s.query,
                "rationale": s.rationale,
                "priority": s.priority,
                "goal_ref": s.goal_ref,
                "scope": s.scope,
            }
            for s in suggestions
        ],
    }
    tmp_path = cache_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.rename(cache_path)


# ---------------------------------------------------------------------------
# Top-level advisor
# ---------------------------------------------------------------------------


def advise(
    vault_path: Path,
    context: str = "literature",
    config: object | None = None,
    max_suggestions: int = 4,
    no_cache: bool = False,
    include_pipeline_tips: bool = False,
    include_session_tips: bool = False,
) -> tuple[list[Suggestion], bool]:
    """Top-level: scan + gaps + suggestions, with caching.

    Args:
        vault_path: Root of the vault.
        context: Calling context (literature, generate, etc.).
        config: DaemonConfig or None (loads from disk if None).
        max_suggestions: Max suggestions to return.
        no_cache: Skip cache read/write.
        include_pipeline_tips: Include pipeline ordering tips from queue state.
        include_session_tips: Include session-level tips from vault state.

    Returns:
        (suggestions, cached) tuple.
    """
    cache_path = vault_path / "ops" / "advisor-cache.json"
    key = _session_key()

    # Check cache
    if not no_cache:
        cached = load_cache(cache_path)
        if cached is not None:
            if (
                cached.get("session_key") == key
                and cached.get("context") == context
                and cached.get("max_suggestions") == max_suggestions
                and cached.get("include_pipeline_tips", False) == include_pipeline_tips
                and cached.get("include_session_tips", False) == include_session_tips
            ):
                return [
                    Suggestion(**s) for s in cached.get("suggestions", [])
                ], True

    # Load config for goals_priority
    goals_priority: list[str] = []
    if config is not None and hasattr(config, "goals_priority"):
        goals_priority = config.goals_priority
    else:
        config_path = vault_path / "ops" / "daemon-config.yaml"
        if config_path.is_file():
            from engram_r.daemon_config import load_config

            loaded = load_config(config_path)
            goals_priority = loaded.goals_priority

    profiles = scan_goal_frontier(vault_path, goals_priority)
    goal_suggestions = generate_suggestions(profiles, context, max_suggestions)

    # Pipeline tips channel
    pipeline_suggestions: list[Suggestion] = []
    if include_pipeline_tips:
        phase_state = scan_queue_phases(vault_path)
        tips = detect_pipeline_tips(phase_state)
        pipeline_suggestions = generate_pipeline_suggestions(tips, max_suggestions)

    # Session tips channel
    session_suggestions: list[Suggestion] = []
    if include_session_tips:
        snapshot = build_vault_snapshot(vault_path)
        session_tips = detect_session_tips(snapshot)
        session_suggestions = generate_session_suggestions(
            session_tips, max_suggestions
        )

    # Merge: session tips + pipeline tips + goal suggestions
    suggestions = session_suggestions + pipeline_suggestions + goal_suggestions
    suggestions = suggestions[:max_suggestions]

    # Write cache
    if not no_cache:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            save_cache(cache_path, suggestions, key, context, max_suggestions)
        except OSError:
            logger.warning("Failed to write advisor cache: %s", cache_path)

    return suggestions, False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the vault advisor.

    Usage:
        python -m engram_r.vault_advisor VAULT_PATH
            --context literature --max 4 [--no-cache]

    Prints JSON with context, suggestions, cached flag.
    Exit codes: 0 = suggestions, 2 = no gaps, 1 = error.
    """
    args = argv if argv is not None else sys.argv[1:]

    vault_path_str = None
    context = "literature"
    max_suggestions = 4
    no_cache = False
    include_pipeline_tips = False
    include_session_tips = False
    all_tips = False

    i = 0
    while i < len(args):
        if args[i] == "--context" and i + 1 < len(args):
            context = args[i + 1]
            i += 2
        elif args[i] == "--max" and i + 1 < len(args):
            try:
                max_suggestions = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif args[i] == "--no-cache":
            no_cache = True
            i += 1
        elif args[i] == "--include-pipeline-tips":
            include_pipeline_tips = True
            i += 1
        elif args[i] == "--include-session-tips":
            include_session_tips = True
            i += 1
        elif args[i] == "--all-tips":
            all_tips = True
            i += 1
        elif not args[i].startswith("--"):
            vault_path_str = args[i]
            i += 1
        else:
            i += 1

    # Auto-enable pipeline tips for ralph context
    if context == "ralph":
        include_pipeline_tips = True

    if not vault_path_str:
        vault_path = _default_vault_path()
    else:
        vault_path = Path(vault_path_str)

    if not vault_path.is_dir():
        msg = {"error": f"Vault path not found: {vault_path}"}
        print(json.dumps(msg), file=sys.stderr)
        return 1

    # --all-tips: show all eligible session tips (for curious users)
    if all_tips:
        try:
            snapshot = build_vault_snapshot(vault_path)
            tips = detect_session_tips(snapshot)
            result = {
                "all_session_tips": [
                    {
                        "tip_id": t.tip_id,
                        "message": t.message,
                        "rationale": t.rationale,
                        "priority": t.priority,
                    }
                    for t in tips
                ],
            }
            print(json.dumps(result, indent=2))
            return 0 if tips else 2
        except Exception as exc:
            msg = {"error": str(exc)}
            print(json.dumps(msg), file=sys.stderr)
            return 1

    try:
        suggestions, cached = advise(
            vault_path,
            context=context,
            max_suggestions=max_suggestions,
            no_cache=no_cache,
            include_pipeline_tips=include_pipeline_tips,
            include_session_tips=include_session_tips,
        )
    except Exception as exc:
        msg = {"error": str(exc)}
        print(json.dumps(msg), file=sys.stderr)
        return 1

    result = {
        "context": context,
        "suggestions": [
            {
                "channel": s.channel,
                "query": s.query,
                "rationale": s.rationale,
                "priority": s.priority,
                "goal_ref": s.goal_ref,
                "scope": s.scope,
            }
            for s in suggestions
        ],
        "cached": cached,
    }

    print(json.dumps(result, indent=2))
    return 0 if suggestions else 2


def _default_vault_path() -> Path:
    """Resolve default vault path."""
    try:
        from engram_r.vault_registry import get_vault_path

        registry_path = get_vault_path()
        if registry_path is not None:
            return registry_path
    except ImportError:
        pass

    env_path = os.environ.get("VAULT_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[3]


if __name__ == "__main__":
    sys.exit(main())
