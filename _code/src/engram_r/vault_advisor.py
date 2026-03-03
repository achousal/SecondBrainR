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
    {"literature", "learn", "generate", "reflect", "reweave", "reduce"}
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
) -> tuple[list[Suggestion], bool]:
    """Top-level: scan + gaps + suggestions, with caching.

    Args:
        vault_path: Root of the vault.
        context: Calling context (literature, generate, etc.).
        config: DaemonConfig or None (loads from disk if None).
        max_suggestions: Max suggestions to return.
        no_cache: Skip cache read/write.

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
    suggestions = generate_suggestions(profiles, context, max_suggestions)

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
        elif not args[i].startswith("--"):
            vault_path_str = args[i]
            i += 1
        else:
            i += 1

    if not vault_path_str:
        vault_path = _default_vault_path()
    else:
        vault_path = Path(vault_path_str)

    if not vault_path.is_dir():
        msg = {"error": f"Vault path not found: {vault_path}"}
        print(json.dumps(msg), file=sys.stderr)
        return 1

    try:
        suggestions, cached = advise(
            vault_path,
            context=context,
            max_suggestions=max_suggestions,
            no_cache=no_cache,
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
