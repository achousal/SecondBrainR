"""Resolve experiment outcomes into hypothesis Elo adjustments and status transitions.

Pure-function module -- no I/O, no side effects.  Computes empirical
updates that the /experiment skill (or daemon) applies to vault files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from engram_r.elo import apply_empirical_elo
from engram_r.hypothesis_parser import (
    append_to_section,
    ensure_section,
    parse_hypothesis_note,
    update_frontmatter_field,
)

# ---------------------------------------------------------------------------
# Outcome -> (hypothesis_status, elo_direction)
# elo_direction: True = win, False = loss, None = no change
# ---------------------------------------------------------------------------

OUTCOME_MAP: dict[str, tuple[str, bool | None]] = {
    "positive": ("tested-positive", True),
    "negative": ("tested-negative", False),
    "null": ("tested-negative", False),
    "partial": ("tested-partial", None),
    "blocked": ("analytically-blocked", None),
    "completed-null": ("tested-negative", False),
    "completed-positive": ("tested-positive", True),
}

DEFAULT_EMPIRICAL_K = 16.0
VIRTUAL_OPPONENT_ELO = 1200.0

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class EmpiricalUpdate:
    """Result of computing an empirical Elo adjustment."""

    hypothesis_id: str
    old_elo: float
    new_elo: float
    delta: float
    new_status: str
    reason: str


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _parse_experiment_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from an experiment note."""
    m = _FM_RE.match(content)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def compute_empirical_update(
    hypothesis_content: str,
    experiment_content: str,
    k: float = DEFAULT_EMPIRICAL_K,
) -> EmpiricalUpdate | None:
    """Compute an empirical Elo adjustment from experiment outcome.

    The hypothesis "plays against reality" -- a virtual opponent at
    Elo 1200.  K defaults to 16 (half of tournament K=32) so empirical
    evidence has meaningful but not overwhelming influence on rankings.

    Args:
        hypothesis_content: Raw markdown of the hypothesis note.
        experiment_content: Raw markdown of the experiment note.
        k: K-factor for the empirical update.

    Returns:
        EmpiricalUpdate if an adjustment should be made, None if the
        hypothesis is already resolved or the experiment has no outcome.
    """
    hyp = parse_hypothesis_note(hypothesis_content)

    if hyp.is_empirically_resolved:
        return None

    exp_fm = _parse_experiment_frontmatter(experiment_content)
    outcome_raw = exp_fm.get("outcome") or exp_fm.get("status", "")
    outcome = str(outcome_raw).strip().lower()

    if outcome not in OUTCOME_MAP:
        return None

    new_status, elo_direction = OUTCOME_MAP[outcome]
    exp_id = exp_fm.get("id", exp_fm.get("title", "unknown"))

    if elo_direction is None:
        # No Elo change (partial, blocked)
        return EmpiricalUpdate(
            hypothesis_id=hyp.id,
            old_elo=hyp.elo,
            new_elo=hyp.elo,
            delta=0.0,
            new_status=new_status,
            reason=f"Experiment {exp_id}: outcome={outcome}, no Elo change",
        )

    new_elo, delta = apply_empirical_elo(
        hypothesis_elo=hyp.elo,
        won=elo_direction,
        k=k,
        opponent_elo=VIRTUAL_OPPONENT_ELO,
    )

    direction_word = "supported" if elo_direction else "refuted"
    return EmpiricalUpdate(
        hypothesis_id=hyp.id,
        old_elo=hyp.elo,
        new_elo=round(new_elo, 1),
        delta=round(delta, 1),
        new_status=new_status,
        reason=f"Experiment {exp_id}: hypothesis {direction_word} (outcome={outcome})",
    )


def apply_empirical_update(
    hypothesis_content: str,
    update: EmpiricalUpdate,
    experiment_wiki_link: str = "",
) -> str:
    """Apply an empirical update to hypothesis note content.

    Updates frontmatter fields (status, elo, empirical_outcome,
    empirical_experiment) and appends a summary to the
    ``## Empirical Evidence`` section (creating it if missing).

    Args:
        hypothesis_content: Raw markdown of the hypothesis note.
        update: The computed empirical update.
        experiment_wiki_link: Wiki-link to the experiment note
            (e.g. ``[[EXP-002-treatment-response-analysis]]``).

    Returns:
        Updated hypothesis note content.
    """
    content = hypothesis_content

    content = update_frontmatter_field(content, "status", update.new_status)
    content = update_frontmatter_field(content, "elo", update.new_elo)
    content = update_frontmatter_field(content, "empirical_outcome", update.new_status)
    if experiment_wiki_link:
        content = update_frontmatter_field(
            content, "empirical_experiment", experiment_wiki_link
        )

    content = ensure_section(content, "Empirical Evidence")

    evidence_text = (
        f"\n**{update.reason}**\n"
        f"- Elo: {update.old_elo} -> {update.new_elo} (delta: {update.delta:+.1f})\n"
        f"- Status: {update.new_status}\n"
    )
    if experiment_wiki_link:
        evidence_text += f"- Experiment: {experiment_wiki_link}\n"

    content = append_to_section(content, "Empirical Evidence", evidence_text)
    return content
