"""Parse and manipulate hypothesis notes (YAML frontmatter + Markdown body).

Handles the structured hypothesis format used throughout the co-scientist system.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Convergence detection
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def _extract_section(body: str, name: str) -> str:
    """Extract text under a ## heading, up to the next ## or EOF."""
    pattern = re.compile(
        rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(body)
    return m.group(1).strip() if m else ""


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens from text."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets. Returns 1.0 if both empty."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _extract_list_items(section_text: str) -> set[str]:
    """Extract normalized list items (- [ ] or - lines) as a set."""
    items = re.findall(r"^[-*]\s*(?:\[.\]\s*)?(.+)$", section_text, re.MULTILINE)
    return {item.strip().lower() for item in items}


def _extract_wiki_links(text: str) -> set[str]:
    """Extract wiki-link targets from text."""
    return set(re.findall(r"\[\[([^\]]+)\]\]", text))


def compute_hypothesis_similarity(
    parent: HypothesisData, child: HypothesisData
) -> float:
    """Compute weighted similarity between parent and child hypotheses.

    Weights:
        Title tokens:          0.15
        Mechanism section:     0.30
        Predictions overlap:   0.25
        Assumptions overlap:   0.15
        Literature refs:       0.15

    Args:
        parent: Parsed parent hypothesis.
        child: Parsed child hypothesis.

    Returns:
        Similarity score in [0.0, 1.0].
    """
    title_sim = _jaccard(_tokenize(parent.title), _tokenize(child.title))

    mech_sim = _jaccard(
        _tokenize(_extract_section(parent.body, "Mechanism")),
        _tokenize(_extract_section(child.body, "Mechanism")),
    )

    pred_parent = _extract_list_items(_extract_section(parent.body, "Testable Predictions"))
    pred_child = _extract_list_items(_extract_section(child.body, "Testable Predictions"))
    pred_sim = _jaccard(pred_parent, pred_child)

    assum_parent = _extract_list_items(_extract_section(parent.body, "Assumptions"))
    assum_child = _extract_list_items(_extract_section(child.body, "Assumptions"))
    assum_sim = _jaccard(assum_parent, assum_child)

    lit_parent = _extract_wiki_links(_extract_section(parent.body, "Literature Grounding"))
    lit_child = _extract_wiki_links(_extract_section(child.body, "Literature Grounding"))
    lit_sim = _jaccard(lit_parent, lit_child)

    return (
        0.15 * title_sim
        + 0.30 * mech_sim
        + 0.25 * pred_sim
        + 0.15 * assum_sim
        + 0.15 * lit_sim
    )


@dataclass
class ConvergenceEntry:
    """A single entry in the convergence log."""

    date: str
    parent_id: str
    child_id: str
    lineage_root: str
    similarity: float
    streak: int
    evolution_mode: str


def _find_lineage_root(hyp: HypothesisData) -> str:
    """Return the root ancestor ID. If no parents, the hypothesis itself is root."""
    parents = hyp.frontmatter.get("parents", [])
    if not parents:
        return hyp.id
    return parents[0]


def read_convergence_log(log_path: Path) -> list[ConvergenceEntry]:
    """Read the convergence log file.

    The log stores entries as a JSON array in a fenced code block.

    Args:
        log_path: Path to the convergence log markdown file.

    Returns:
        List of convergence entries, ordered chronologically.
    """
    if not log_path.exists():
        return []

    text = log_path.read_text()
    m = re.search(r"```json\n(.*?)```", text, re.DOTALL)
    if not m:
        return []

    try:
        raw = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    return [
        ConvergenceEntry(
            date=e.get("date", ""),
            parent_id=e.get("parent_id", ""),
            child_id=e.get("child_id", ""),
            lineage_root=e.get("lineage_root", ""),
            similarity=float(e.get("similarity", 0.0)),
            streak=int(e.get("streak", 0)),
            evolution_mode=e.get("evolution_mode", ""),
        )
        for e in raw
    ]


def get_lineage_streak(entries: list[ConvergenceEntry], lineage_root: str) -> int:
    """Get the current convergence streak for a lineage.

    Args:
        entries: All convergence entries.
        lineage_root: Root hypothesis ID for the lineage.

    Returns:
        Current consecutive streak of similarity >= 0.90.
    """
    lineage = [e for e in entries if e.lineage_root == lineage_root]
    if not lineage:
        return 0
    streak = 0
    for entry in reversed(lineage):
        if entry.similarity >= 0.90:
            streak += 1
        else:
            break
    return streak


def append_convergence_entry(
    log_path: Path, entry: ConvergenceEntry
) -> None:
    """Append a convergence entry to the log file.

    Creates the file if it does not exist.

    Args:
        log_path: Path to the convergence log markdown file.
        entry: Entry to append.
    """
    entries = read_convergence_log(log_path)
    entries.append(entry)

    records = [
        {
            "date": e.date,
            "parent_id": e.parent_id,
            "child_id": e.child_id,
            "lineage_root": e.lineage_root,
            "similarity": round(e.similarity, 4),
            "streak": e.streak,
            "evolution_mode": e.evolution_mode,
        }
        for e in entries
    ]

    content = (
        "# Convergence Log\n\n"
        "Tracks hypothesis evolution convergence across lineages.\n"
        "Auto-generated by /evolve. Do not edit manually.\n\n"
        "```json\n"
        + json.dumps(records, indent=2)
        + "\n```\n"
    )
    log_path.write_text(content)
