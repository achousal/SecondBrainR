"""Parse and manipulate hypothesis notes (YAML frontmatter + Markdown body).

Handles the structured hypothesis format used throughout the co-scientist system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml


@dataclass
class HypothesisData:
    """Parsed representation of a hypothesis note."""

    frontmatter: dict[str, Any]
    body: str
    raw: str

    @property
    def id(self) -> str:
        return self.frontmatter.get("id", "")

    @property
    def title(self) -> str:
        return self.frontmatter.get("title", "")

    @property
    def elo(self) -> float:
        return float(self.frontmatter.get("elo", 1200))

    @property
    def status(self) -> str:
        return self.frontmatter.get("status", "proposed")

    @property
    def generation(self) -> int:
        return int(self.frontmatter.get("generation", 1))

    @property
    def matches(self) -> int:
        return int(self.frontmatter.get("matches", 0))

    @property
    def review_scores(self) -> dict[str, Any]:
        return self.frontmatter.get("review_scores", {})

    @property
    def elo_federated(self) -> float:
        return float(self.frontmatter.get("elo_federated", 0.0))

    @property
    def matches_federated(self) -> int:
        return int(self.frontmatter.get("matches_federated", 0))

    @property
    def is_empirically_resolved(self) -> bool:
        return self.status in EMPIRICALLY_RESOLVED_STATUSES

    @property
    def is_foreign(self) -> bool:
        return self.frontmatter.get("type") == "foreign-hypothesis"

    @property
    def source_vault(self) -> str:
        return str(self.frontmatter.get("source_vault", ""))


EMPIRICALLY_RESOLVED_STATUSES: frozenset[str] = frozenset(
    {
        "tested-positive",
        "tested-negative",
        "tested-partial",
        "analytically-blocked",
    }
)

_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_hypothesis_note(content: str) -> HypothesisData:
    """Parse a hypothesis note into structured data.

    Args:
        content: Raw markdown content with YAML frontmatter.

    Returns:
        HypothesisData with parsed frontmatter and body.

    Raises:
        ValueError: If frontmatter is missing or invalid.
    """
    match = _FM_PATTERN.match(content)
    if not match:
        raise ValueError("No valid YAML frontmatter found")

    fm_text = match.group(1)
    body = content[match.end() :]

    try:
        frontmatter = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise ValueError("Frontmatter must be a YAML mapping")

    return HypothesisData(frontmatter=frontmatter, body=body, raw=content)


def update_frontmatter_field(content: str, field_name: str, value: Any) -> str:
    """Update a single field in the YAML frontmatter.

    Args:
        content: Raw note content.
        field_name: Frontmatter key to update.
        value: New value for the field.

    Returns:
        Updated note content.

    Raises:
        ValueError: If frontmatter is missing.
    """
    match = _FM_PATTERN.match(content)
    if not match:
        raise ValueError("No valid YAML frontmatter found")

    fm_text = match.group(1)
    fm = yaml.safe_load(fm_text) or {}
    fm[field_name] = value

    new_fm = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
    return f"---\n{new_fm}\n---\n{content[match.end():]}"


def append_to_section(content: str, section_name: str, text: str) -> str:
    """Append text to a named markdown section (## heading).

    Inserts before the next ## heading or at end of file.

    Args:
        content: Raw note content.
        section_name: Heading text (without ##).
        text: Text to append.

    Returns:
        Updated note content.

    Raises:
        ValueError: If section is not found.
    """
    pattern = re.compile(
        rf"^(## {re.escape(section_name)}\s*\n)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        raise ValueError(f"Section '## {section_name}' not found")

    insert_pos = match.end()
    # Ensure newline separation
    if content[insert_pos - 1 : insert_pos] != "\n":
        text = "\n" + text
    if not text.endswith("\n"):
        text = text + "\n"

    return content[:insert_pos] + text + content[insert_pos:]


def build_hypothesis_frontmatter(
    *,
    title: str,
    hyp_id: str,
    research_goal: str = "",
    tags: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Build default frontmatter dict for a new hypothesis.

    Args:
        title: Hypothesis title.
        hyp_id: Unique hypothesis ID (e.g., hyp-20260221-001).
        research_goal: Wiki-link to research goal note.
        tags: Additional tags.
        today: Date override for testing.

    Returns:
        Frontmatter dictionary.
    """
    d = today or date.today()
    return {
        "type": "hypothesis",
        "title": title,
        "id": hyp_id,
        "status": "proposed",
        "elo": 1200,
        "matches": 0,
        "wins": 0,
        "losses": 0,
        "generation": 1,
        "parents": [],
        "children": [],
        "research_goal": research_goal,
        "tags": ["hypothesis"] + (tags or []),
        "created": d.isoformat(),
        "updated": d.isoformat(),
        "review_scores": {
            "novelty": None,
            "correctness": None,
            "testability": None,
            "impact": None,
            "overall": None,
        },
        "review_flags": [],
        "linked_experiments": [],
        "linked_literature": [],
    }


def ensure_section(
    content: str, section_name: str, after_section: str | None = None
) -> str:
    """Ensure a ## section exists in the markdown content.

    If the section already exists, returns content unchanged.
    Otherwise, inserts a new empty section after ``after_section``
    (or at the end of the document if ``after_section`` is None or
    not found).

    Args:
        content: Raw note content.
        section_name: Heading text (without ##).
        after_section: Insert after this section heading (without ##).

    Returns:
        Content with the section guaranteed to exist.
    """
    section_pattern = re.compile(
        rf"^## {re.escape(section_name)}\s*$",
        re.MULTILINE,
    )
    if section_pattern.search(content):
        return content

    new_section = f"\n## {section_name}\n\n"

    if after_section:
        after_pattern = re.compile(
            rf"^(## {re.escape(after_section)}\s*\n)(.*?)(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = after_pattern.search(content)
        if match:
            insert_pos = match.end()
            return content[:insert_pos] + new_section + content[insert_pos:]

    # Append at end
    if not content.endswith("\n"):
        content += "\n"
    return content + new_section


def filter_tournament_eligible(
    hypotheses: list[HypothesisData],
) -> list[HypothesisData]:
    """Filter hypotheses to those eligible for tournament matchups.

    Excludes empirically resolved hypotheses (tested-positive,
    tested-negative, tested-partial, analytically-blocked).
    These retain their Elo for leaderboard display but should
    not enter new matchups.

    Args:
        hypotheses: List of parsed hypothesis data.

    Returns:
        Filtered list of tournament-eligible hypotheses.
    """
    return [h for h in hypotheses if not h.is_empirically_resolved]
