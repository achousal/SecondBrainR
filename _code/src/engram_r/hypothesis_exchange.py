"""Export and import hypotheses for cross-vault federation.

Each vault runs its own Elo tournament independently. This module enables
cross-vault hypothesis sharing with a separate federated Elo track.

Export: top-N hypotheses above an Elo threshold, stripped of wiki-links.
Import: creates type=foreign-hypothesis notes with source_vault metadata
        and a separate elo_federated field.

Federated Elo is a separate rating track from local Elo. Local tournaments
update `elo`; federated tournaments update `elo_federated`. This prevents
cross-vault matches from distorting local rankings.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from engram_r.claim_exchange import _strip_wiki_links
from engram_r.note_builder import build_foreign_hypothesis_note
from engram_r.schema_validator import validate_note

logger = logging.getLogger(__name__)

# Pattern to match YAML frontmatter
_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class HypothesisExchangeError(Exception):
    """Raised for hypothesis export/import failures."""


@dataclass(frozen=True)
class ExportedHypothesis:
    """Portable representation of a vault hypothesis."""

    id: str
    title: str
    status: str = "proposed"
    elo: float = 1200.0
    matches: int = 0
    generation: int = 1
    research_goal: str = ""
    tags: list[str] = field(default_factory=list)
    statement: str = ""
    mechanism: str = ""
    predictions: str = ""
    assumptions: str = ""
    limitations: str = ""
    source_vault: str = ""
    exported: str = ""


def _parse_note(content: str) -> tuple[dict[str, Any], str]:
    """Parse a note into frontmatter dict and body string."""
    match = _FM_PATTERN.match(content)
    if not match:
        raise HypothesisExchangeError("No valid YAML frontmatter found")
    fm_text = match.group(1)
    body = content[match.end() :]
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise HypothesisExchangeError(f"Invalid YAML: {exc}") from exc
    if not isinstance(fm, dict):
        raise HypothesisExchangeError("Frontmatter must be a YAML mapping")
    return fm, body


def _extract_section(body: str, heading: str) -> str:
    """Extract content under a ## heading, stopping at the next ##."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        return ""
    return _strip_wiki_links(match.group(1).strip())


def export_hypothesis(
    content: str,
    *,
    source_vault: str,
    now: datetime | None = None,
    sanitize_pii: bool = False,
) -> ExportedHypothesis:
    """Export a single hypothesis note to portable format.

    Args:
        content: Raw markdown content of the hypothesis note.
        source_vault: Name of the vault this hypothesis comes from.
        now: Timestamp override for testing.
        sanitize_pii: If True, redact PII from body sections.

    Returns:
        ExportedHypothesis with wiki-links stripped.
    """
    ts = now or datetime.now(UTC)
    fm, body = _parse_note(content)

    statement = _extract_section(body, "Statement")
    mechanism = _extract_section(body, "Mechanism")
    predictions = _extract_section(body, "Testable Predictions")
    assumptions = _extract_section(body, "Assumptions")
    limitations = _extract_section(body, "Limitations & Risks")

    if sanitize_pii:
        from engram_r.pii_filter import redact_text

        statement = redact_text(statement)
        mechanism = redact_text(mechanism)
        predictions = redact_text(predictions)
        assumptions = redact_text(assumptions)
        limitations = redact_text(limitations)

    return ExportedHypothesis(
        id=fm.get("id", ""),
        title=fm.get("title", ""),
        status=fm.get("status", "proposed"),
        elo=float(fm.get("elo", 1200)),
        matches=int(fm.get("matches", 0)),
        generation=int(fm.get("generation", 1)),
        research_goal=_strip_wiki_links(fm.get("research_goal", "")),
        tags=[t for t in fm.get("tags", []) if isinstance(t, str)],
        statement=statement,
        mechanism=mechanism,
        predictions=predictions,
        assumptions=assumptions,
        limitations=limitations,
        source_vault=source_vault,
        exported=ts.isoformat(),
    )


def export_hypotheses(
    vault_path: Path,
    *,
    source_vault: str,
    hyp_dir: str = "_research/hypotheses",
    min_elo: float = 0.0,
    max_count: int | None = None,
    now: datetime | None = None,
    sanitize_pii: bool = False,
) -> list[ExportedHypothesis]:
    """Export top hypotheses from a vault, filtered by Elo threshold.

    Args:
        vault_path: Root path of the vault.
        source_vault: Name identifier for this vault.
        hyp_dir: Subdirectory containing hypothesis notes.
        min_elo: Only export hypotheses with Elo >= this value.
        max_count: Maximum number to export (top by Elo). None = all.
        now: Timestamp override for testing.

    Returns:
        List of ExportedHypothesis, sorted by Elo descending.
    """
    hyp_path = vault_path / hyp_dir
    if not hyp_path.is_dir():
        return []

    ts = now or datetime.now(UTC)
    candidates: list[tuple[float, ExportedHypothesis]] = []

    for note_file in sorted(hyp_path.glob("*.md")):
        if note_file.name.startswith("_"):
            continue
        try:
            content = note_file.read_text(encoding="utf-8")
            fm, _ = _parse_note(content)
        except (HypothesisExchangeError, OSError):
            continue

        if fm.get("type") != "hypothesis":
            continue

        elo = float(fm.get("elo", 1200))
        if elo < min_elo:
            continue

        hyp = export_hypothesis(
            content, source_vault=source_vault, now=ts, sanitize_pii=sanitize_pii
        )
        candidates.append((elo, hyp))

    # Sort by Elo descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    results = [h for _, h in candidates]
    if max_count is not None:
        results = results[:max_count]

    logger.info(
        "federation.export_hypotheses source_vault=%r count=%d",
        source_vault,
        len(results),
    )
    return results


def export_to_yaml(hypotheses: list[ExportedHypothesis]) -> str:
    """Serialize exported hypotheses to YAML."""
    data = [asdict(h) for h in hypotheses]
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def load_exported_hypotheses(yaml_content: str) -> list[ExportedHypothesis]:
    """Deserialize hypotheses from a YAML string.

    Args:
        yaml_content: YAML string from export_to_yaml.

    Returns:
        List of ExportedHypothesis objects.

    Raises:
        HypothesisExchangeError: If YAML is invalid.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        raise HypothesisExchangeError(f"Invalid YAML: {exc}") from exc

    if not isinstance(data, list):
        raise HypothesisExchangeError("Expected a YAML list of hypotheses")

    results: list[ExportedHypothesis] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "id" not in item or "title" not in item:
            continue
        results.append(
            ExportedHypothesis(
                id=item["id"],
                title=item["title"],
                status=item.get("status", "proposed"),
                elo=float(item.get("elo", 1200)),
                matches=int(item.get("matches", 0)),
                generation=int(item.get("generation", 1)),
                research_goal=item.get("research_goal", ""),
                tags=item.get("tags", []),
                statement=item.get("statement", ""),
                mechanism=item.get("mechanism", ""),
                predictions=item.get("predictions", ""),
                assumptions=item.get("assumptions", ""),
                limitations=item.get("limitations", ""),
                source_vault=item.get("source_vault", ""),
                exported=item.get("exported", ""),
            )
        )
    return results


def import_hypotheses(
    vault_path: Path,
    hypotheses: list[ExportedHypothesis],
    *,
    hyp_dir: str = "_research/hypotheses",
    overwrite: bool = False,
    quarantine: bool = True,
) -> list[Path]:
    """Import hypotheses into a vault as foreign-hypothesis notes.

    Imported hypotheses get:
    - type: foreign-hypothesis
    - source_vault: originating vault name
    - elo_federated: 1200 (starting federated Elo)
    - elo_source: original Elo from source vault (informational)
    - quarantine: true (when quarantine=True)

    Uses ``build_foreign_hypothesis_note()`` which applies full
    sanitization: HTML stripping, NFC normalization, title sanitization.

    Args:
        vault_path: Root path of the target vault.
        hypotheses: List of ExportedHypothesis objects.
        hyp_dir: Subdirectory for hypothesis notes.
        overwrite: Overwrite existing notes with same ID.
        quarantine: Add quarantine: true to imported hypotheses.

    Returns:
        List of paths to created/updated note files.
    """
    hyp_path = vault_path / hyp_dir
    hyp_path.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    for hyp in hypotheses:
        safe_id, content = build_foreign_hypothesis_note(
            hyp_id=hyp.id,
            title=hyp.title,
            status=hyp.status,
            elo=hyp.elo,
            matches=hyp.matches,
            generation=hyp.generation,
            research_goal=hyp.research_goal,
            tags=hyp.tags or None,
            statement=hyp.statement,
            mechanism=hyp.mechanism,
            predictions=hyp.predictions,
            assumptions=hyp.assumptions,
            limitations=hyp.limitations,
            source_vault=hyp.source_vault,
            exported=hyp.exported,
            quarantine=quarantine,
        )

        filename = f"{safe_id}.md"
        note_path = hyp_path / filename

        if note_path.exists() and not overwrite:
            continue

        result = validate_note(content)
        if not result.valid:
            raise HypothesisExchangeError(
                f"Imported hypothesis '{hyp.id}' fails schema: "
                + "; ".join(result.errors)
            )

        logger.info(
            "federation.import_hypothesis id=%r source_vault=%r quarantine=%s",
            hyp.id,
            hyp.source_vault,
            quarantine,
        )
        note_path.write_text(content, encoding="utf-8")
        created.append(note_path)

    return created
