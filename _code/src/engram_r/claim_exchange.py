"""Export and import atomic claims for cross-vault federation.

Claims are vault-internal markdown files. This module provides a portable
YAML-based representation that strips wiki-links (non-portable) and adds
source_vault provenance. Imported claims are quarantined by default.

Export format per claim:
    title: "prose-as-title claim"
    description: "context sentence"
    type: claim
    confidence: supported
    source: "Author et al., 2024"        # citation string, NOT wiki-link
    tags: [tag1, tag2]
    body: "markdown body content"
    source_vault: "vault-name"
    exported: "2026-02-23T12:00:00"

Round-trip guarantee: export -> import preserves all claim content.
Wiki-links are converted to plain text on export and NOT restored on import.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from engram_r.note_builder import build_claim_note
from engram_r.schema_validator import validate_note

logger = logging.getLogger(__name__)

# Pattern to match YAML frontmatter
_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Pattern to match wiki-links: [[target]] or [[target|display]]
_WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


class ClaimExchangeError(Exception):
    """Raised for claim export/import failures."""


@dataclass(frozen=True)
class ExportedClaim:
    """Portable representation of a vault claim."""

    title: str
    description: str = ""
    type: str = "claim"
    confidence: str = "preliminary"
    source: str = ""
    source_class: str = ""
    verified_by: str = ""
    verified_who: str = ""
    verified_date: str = ""
    tags: list[str] = field(default_factory=list)
    body: str = ""
    source_vault: str = ""
    exported: str = ""


def _strip_wiki_links(text: str) -> str:
    """Convert [[target|display]] to display, [[target]] to target."""

    def _replace(m: re.Match) -> str:
        display = m.group(2)
        if display:
            return display
        return m.group(1)

    return _WIKI_LINK.sub(_replace, text)


def _parse_note(content: str) -> tuple[dict[str, Any], str]:
    """Parse a note into frontmatter dict and body string."""
    match = _FM_PATTERN.match(content)
    if not match:
        raise ClaimExchangeError("No valid YAML frontmatter found")
    fm_text = match.group(1)
    body = content[match.end() :]
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise ClaimExchangeError(f"Invalid YAML: {exc}") from exc
    if not isinstance(fm, dict):
        raise ClaimExchangeError("Frontmatter must be a YAML mapping")
    return fm, body


def _source_to_citation(source_value: str) -> str:
    """Convert a source field (possibly a wiki-link) to a plain citation."""
    return _strip_wiki_links(source_value)


def export_claim(
    content: str,
    *,
    title: str,
    source_vault: str,
    now: datetime | None = None,
    sanitize_pii: bool = False,
) -> ExportedClaim:
    """Export a single claim note to portable format.

    Args:
        content: Raw markdown content of the claim note.
        title: The claim title (filename stem).
        source_vault: Name of the vault this claim comes from.
        now: Timestamp override for testing.
        sanitize_pii: If True, redact PII from body/description and
            clear verified_who/verified_date fields.

    Returns:
        ExportedClaim with wiki-links stripped from body and source.
    """
    ts = now or datetime.now(UTC)
    fm, body = _parse_note(content)

    description = fm.get("description", "")
    body_text = _strip_wiki_links(body).strip()
    verified_who = fm.get("verified_who", "") or ""
    verified_date = str(fm.get("verified_date", "")) if fm.get("verified_date") else ""

    if sanitize_pii:
        from engram_r.pii_filter import redact_text

        description = redact_text(description)
        body_text = redact_text(body_text)
        verified_who = ""
        verified_date = ""

    return ExportedClaim(
        title=title,
        description=description,
        type=fm.get("type", "claim"),
        confidence=fm.get("confidence", "preliminary"),
        source=_source_to_citation(fm.get("source", "")),
        source_class=fm.get("source_class", ""),
        verified_by=fm.get("verified_by", ""),
        verified_who=verified_who,
        verified_date=verified_date,
        tags=[t for t in fm.get("tags", []) if isinstance(t, str)],
        body=body_text,
        source_vault=source_vault,
        exported=ts.isoformat(),
    )


def export_claims(
    vault_path: Path,
    *,
    source_vault: str,
    notes_dir: str = "notes",
    filter_type: str | None = None,
    filter_confidence: str | None = None,
    filter_tags: list[str] | None = None,
    filter_quarantined: bool = True,
    now: datetime | None = None,
    sanitize_pii: bool = False,
) -> list[ExportedClaim]:
    """Export claims from a vault's notes directory.

    Args:
        vault_path: Root path of the vault.
        source_vault: Name identifier for this vault.
        notes_dir: Subdirectory containing claim notes.
        filter_type: Only export claims of this type.
        filter_confidence: Only export claims at this confidence level.
        filter_tags: Only export claims containing ALL of these tags.
        filter_quarantined: Skip quarantined notes (default True).
        now: Timestamp override for testing.

    Returns:
        List of ExportedClaim objects.
    """
    notes_path = vault_path / notes_dir
    if not notes_path.is_dir():
        return []

    ts = now or datetime.now(UTC)
    results: list[ExportedClaim] = []

    for note_file in sorted(notes_path.glob("*.md")):
        try:
            content = note_file.read_text(encoding="utf-8")
            fm, _ = _parse_note(content)
        except (ClaimExchangeError, OSError):
            continue

        # Apply filters
        if filter_type and fm.get("type", "claim") != filter_type:
            continue
        if filter_confidence and fm.get("confidence") != filter_confidence:
            continue
        if filter_tags:
            note_tags = set(fm.get("tags", []))
            if not all(t in note_tags for t in filter_tags):
                continue

        if filter_quarantined and fm.get("quarantine"):
            logger.debug("federation.export_skip_quarantined title=%r", note_file.stem)
            continue

        claim = export_claim(
            content,
            title=note_file.stem,
            source_vault=source_vault,
            now=ts,
            sanitize_pii=sanitize_pii,
        )
        logger.debug(
            "federation.export_claim title=%r source_vault=%r",
            claim.title,
            source_vault,
        )
        results.append(claim)

    logger.info(
        "federation.export_claims source_vault=%r count=%d",
        source_vault,
        len(results),
    )
    return results


def export_to_yaml(claims: list[ExportedClaim]) -> str:
    """Serialize exported claims to a YAML string.

    Args:
        claims: List of ExportedClaim objects.

    Returns:
        YAML string with all claims.
    """
    data = [asdict(c) for c in claims]
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def load_exported_claims(yaml_content: str) -> list[ExportedClaim]:
    """Deserialize claims from a YAML string.

    Args:
        yaml_content: YAML string from export_to_yaml.

    Returns:
        List of ExportedClaim objects.

    Raises:
        ClaimExchangeError: If YAML is invalid or claims are malformed.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        raise ClaimExchangeError(f"Invalid YAML: {exc}") from exc

    if not isinstance(data, list):
        raise ClaimExchangeError("Expected a YAML list of claims")

    results: list[ExportedClaim] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "title" not in item:
            continue
        results.append(
            ExportedClaim(
                title=item["title"],
                description=item.get("description", ""),
                type=item.get("type", "claim"),
                confidence=item.get("confidence", "preliminary"),
                source=item.get("source", ""),
                source_class=item.get("source_class", ""),
                verified_by=item.get("verified_by", ""),
                verified_who=item.get("verified_who", ""),
                verified_date=item.get("verified_date", ""),
                tags=item.get("tags", []),
                body=item.get("body", ""),
                source_vault=item.get("source_vault", ""),
                exported=item.get("exported", ""),
            )
        )
    return results


def import_claims(
    vault_path: Path,
    claims: list[ExportedClaim],
    *,
    notes_dir: str = "notes",
    quarantine: bool = True,
    overwrite: bool = False,
) -> list[Path]:
    """Import claims into a vault's notes directory.

    Imported claims get quarantine: true in frontmatter by default.
    Existing notes are NOT overwritten unless overwrite=True.

    Args:
        vault_path: Root path of the target vault.
        claims: List of ExportedClaim objects to import.
        notes_dir: Subdirectory for claim notes.
        quarantine: Add quarantine: true to imported claims.
        overwrite: Overwrite existing notes with same title.

    Returns:
        List of paths to created/updated note files.
    """
    notes_path = vault_path / notes_dir
    notes_path.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    for claim in claims:
        safe_stem, content = build_claim_note(
            title=claim.title,
            description=claim.description,
            body=claim.body or "",
            claim_type=claim.type,
            source=claim.source,
            confidence=claim.confidence,
            source_class=claim.source_class or "synthesis",
            verified_by=claim.verified_by or "agent",
            verified_who=claim.verified_who or None,
            verified_date=claim.verified_date or None,
            tags=claim.tags or None,
            source_vault=claim.source_vault or None,
            imported=claim.exported or None,
            quarantine=quarantine,
        )
        note_path = notes_path / f"{safe_stem}.md"

        if note_path.exists() and not overwrite:
            continue

        result = validate_note(content)
        if not result.valid:
            raise ClaimExchangeError(
                f"Imported claim '{claim.title}' fails schema: "
                + "; ".join(result.errors)
            )

        logger.info(
            "federation.import_claim title=%r source_vault=%r quarantine=%s",
            claim.title,
            claim.source_vault,
            quarantine,
        )
        note_path.write_text(content, encoding="utf-8")
        created.append(note_path)

    return created
