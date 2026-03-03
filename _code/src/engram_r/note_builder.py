"""Pure functions for building Obsidian note content.

Constructs YAML frontmatter + Markdown body for all note types used
in the co-scientist system. No I/O -- returns strings only.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import yaml

from engram_r.schema_validator import normalize_text, sanitize_title, strip_html


def _render_note(frontmatter: dict[str, Any], body: str) -> str:
    """Render frontmatter + body into a complete note string."""
    fm_str = yaml.dump(
        frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True
    ).rstrip()
    return f"---\n{fm_str}\n---\n\n{body}"


# -- Literature note ----------------------------------------------------------


def build_literature_note(
    *,
    title: str,
    doi: str = "",
    authors: list[str] | None = None,
    year: int | str = "",
    journal: str = "",
    abstract: str = "",
    tags: list[str] | None = None,
    source_type: str = "",
    today: date | None = None,
) -> str:
    """Build a literature note.

    Args:
        title: Paper title.
        doi: DOI identifier.
        authors: List of author names.
        year: Publication year.
        journal: Journal name.
        abstract: Paper abstract.
        tags: Additional tags.
        source_type: Backend name (e.g. "pubmed", "semantic_scholar").
            Appended as a tag when non-empty.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    source_tags = [source_type] if source_type else []
    fm = {
        "type": "literature",
        "title": title,
        "doi": doi,
        "authors": authors or [],
        "year": str(year),
        "journal": journal,
        "tags": ["literature"] + source_tags + (tags or []),
        "status": "unread",
        "created": d.isoformat(),
    }
    body = f"""## Abstract
{abstract}

## Key Points
-

## Methods Notes


## Relevance


## Citations

"""
    return _render_note(fm, body)


# -- Hypothesis note -----------------------------------------------------------


def build_hypothesis_note(
    *,
    title: str,
    hyp_id: str,
    statement: str = "",
    mechanism: str = "",
    research_goal: str = "",
    tags: list[str] | None = None,
    today: date | None = None,
) -> str:
    """Build a hypothesis note with the full structured format.

    Args:
        title: Hypothesis title.
        hyp_id: Unique hypothesis ID.
        statement: Core hypothesis statement.
        mechanism: Mechanistic explanation.
        research_goal: Wiki-link to research goal note.
        tags: Additional tags.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    fm = {
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
    body = f"""## Statement
{statement}

## Mechanism
{mechanism}

## Literature Grounding


## Testable Predictions
- [ ]

## Proposed Experiments


## Assumptions
-

## Limitations & Risks


## Review History


## Evolution History

"""
    return _render_note(fm, body)


# -- Experiment note -----------------------------------------------------------


def build_experiment_note(
    *,
    title: str,
    hypothesis_link: str = "",
    parameters: dict[str, Any] | None = None,
    seed: int | None = None,
    objective: str = "",
    tags: list[str] | None = None,
    today: date | None = None,
) -> str:
    """Build an experiment logging note.

    Args:
        title: Experiment title.
        hypothesis_link: Wiki-link to hypothesis being tested.
        parameters: Experiment parameters dict.
        seed: Random seed used.
        objective: Experiment objective.
        tags: Additional tags.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    fm = {
        "type": "experiment",
        "title": title,
        "hypothesis": hypothesis_link,
        "parameters": parameters or {},
        "seed": seed,
        "status": "planned",
        "artifacts": [],
        "tags": ["experiment"] + (tags or []),
        "created": d.isoformat(),
    }
    body = f"""## Objective
{objective}

## Parameters


## Environment


## Results


## Artifacts


## Interpretation


## Next Steps

"""
    return _render_note(fm, body)


# -- EDA report note -----------------------------------------------------------


def build_eda_report_note(
    *,
    title: str,
    dataset_path: str = "",
    n_rows: int = 0,
    n_cols: int = 0,
    redacted_columns: list[str] | None = None,
    summary: str = "",
    tags: list[str] | None = None,
    today: date | None = None,
) -> str:
    """Build an EDA report note.

    Args:
        title: Report title.
        dataset_path: Path to the dataset analyzed.
        n_rows: Number of rows.
        n_cols: Number of columns.
        redacted_columns: Columns auto-redacted for PII.
        summary: Summary of findings.
        tags: Additional tags.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    fm = {
        "type": "eda-report",
        "title": title,
        "dataset": dataset_path,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "redacted_columns": redacted_columns or [],
        "tags": ["eda-report"] + (tags or []),
        "created": d.isoformat(),
    }
    body = f"""## Summary
{summary}

## Column Overview


## Missing Data


## Distributions


## Correlations


## Outliers


## Figures


## Run Metadata

"""
    return _render_note(fm, body)


# -- Research goal note --------------------------------------------------------


def build_research_goal_note(
    *,
    title: str,
    objective: str = "",
    constraints: list[str] | None = None,
    evaluation_criteria: list[str] | None = None,
    domain: str = "",
    tags: list[str] | None = None,
    today: date | None = None,
) -> str:
    """Build a research goal note.

    Args:
        title: Goal title.
        objective: Research objective.
        constraints: Constraints on hypothesis generation.
        evaluation_criteria: How hypotheses should be evaluated.
        domain: Scientific domain.
        tags: Additional tags.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    fm = {
        "type": "research-goal",
        "title": title,
        "status": "active",
        "constraints": constraints or [],
        "evaluation_criteria": evaluation_criteria or [],
        "domain": domain,
        "tags": ["research-goal"] + (tags or []),
        "created": d.isoformat(),
    }
    body = f"""## Objective
{objective}

## Background


## Constraints


## Desired Properties


## Key Literature

"""
    return _render_note(fm, body)


# -- Tournament match note -----------------------------------------------------


def build_tournament_match_note(
    *,
    research_goal: str,
    hypothesis_a: str,
    hypothesis_b: str,
    winner: str = "",
    elo_change_a: float = 0,
    elo_change_b: float = 0,
    debate_summary: str = "",
    verdict: str = "",
    justification: str = "",
    mode: str = "local",
    today: date | None = None,
) -> str:
    """Build a tournament match log note.

    Args:
        research_goal: Wiki-link to the research goal.
        hypothesis_a: Wiki-link to hypothesis A.
        hypothesis_b: Wiki-link to hypothesis B.
        winner: ID or link of the winning hypothesis.
        elo_change_a: Elo delta for hypothesis A.
        elo_change_b: Elo delta for hypothesis B.
        debate_summary: Summary of the debate.
        verdict: Winner declaration.
        justification: Why the winner was chosen.
        mode: Tournament mode ("local" or "federated").
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    fm = {
        "type": "tournament-match",
        "date": d.isoformat(),
        "research_goal": research_goal,
        "hypothesis_a": hypothesis_a,
        "hypothesis_b": hypothesis_b,
        "winner": winner,
        "elo_change_a": elo_change_a,
        "elo_change_b": elo_change_b,
        "mode": mode,
    }
    body = f"""## Debate Summary
{debate_summary}

## Novelty Comparison


## Correctness


## Testability


## Impact


## Verdict
{verdict}

## Justification
{justification}

"""
    return _render_note(fm, body)


# -- Meta-review note ----------------------------------------------------------


def build_meta_review_note(
    *,
    research_goal: str,
    hypotheses_reviewed: int = 0,
    matches_analyzed: int = 0,
    recurring_weaknesses: str = "",
    key_literature: str = "",
    invalid_assumptions: str = "",
    winner_patterns: str = "",
    recommendations_generation: str = "",
    recommendations_evolution: str = "",
    today: date | None = None,
) -> str:
    """Build a meta-review synthesis note.

    Args:
        research_goal: Wiki-link to the research goal.
        hypotheses_reviewed: Number of hypotheses reviewed.
        matches_analyzed: Number of tournament matches analyzed.
        recurring_weaknesses: Common weakness patterns.
        key_literature: Frequently cited key papers.
        invalid_assumptions: Common invalid assumptions.
        winner_patterns: What makes winning hypotheses win.
        recommendations_generation: Advice for /generate.
        recommendations_evolution: Advice for /evolve.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    fm = {
        "type": "meta-review",
        "date": d.isoformat(),
        "research_goal": research_goal,
        "hypotheses_reviewed": hypotheses_reviewed,
        "matches_analyzed": matches_analyzed,
    }
    body = f"""## Recurring Weaknesses
{recurring_weaknesses}

## Key Literature
{key_literature}

## Invalid Assumptions
{invalid_assumptions}

## Winner Patterns
{winner_patterns}

## Recommendations for Generation
{recommendations_generation}

## Recommendations for Evolution
{recommendations_evolution}

"""
    return _render_note(fm, body)


# -- Lab note ------------------------------------------------------------------


def build_lab_note(
    *,
    lab_slug: str,
    pi: str = "",
    institution: str = "",
    hpc_cluster: str = "",
    hpc_scheduler: str = "",
    research_focus: str = "",
    departments: list[str] | None = None,
    center_affiliations: list[str] | None = None,
    external_affiliations: list[str] | None = None,
    tags: list[str] | None = None,
    today: date | None = None,
) -> str:
    """Build a lab entity note.

    Args:
        lab_slug: Lowercase lab identifier (e.g. "example-lab").
        pi: Principal investigator name.
        institution: Institution name.
        hpc_cluster: HPC cluster name (e.g. "TestCluster").
        hpc_scheduler: HPC scheduler (e.g. "LSF", "SLURM").
        research_focus: 1-2 sentence research focus description.
        departments: Department names within the institution.
        center_affiliations: Research center or institute affiliations.
        external_affiliations: Affiliations outside the primary institution.
        tags: Additional tags.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    d = today or date.today()
    fm = {
        "type": "lab",
        "lab_slug": lab_slug,
        "pi": pi,
        "institution": institution,
        "departments": departments or [],
        "center_affiliations": center_affiliations or [],
        "external_affiliations": external_affiliations or [],
        "hpc_cluster": hpc_cluster,
        "hpc_scheduler": hpc_scheduler,
        "research_focus": research_focus,
        "created": d.isoformat(),
        "updated": d.isoformat(),
        "tags": ["lab"] + (tags or []),
    }
    body = """## Projects

## Datasets

## Research Focus

## HPC Environment
"""
    return _render_note(fm, body)


# -- Project note --------------------------------------------------------------


def build_project_note(
    *,
    title: str,
    project_tag: str,
    lab: str,
    pi: str = "",
    status: str = "active",
    project_path: str,
    language: list[str] | None = None,
    hpc_path: str = "",
    scheduler: str = "",
    linked_goals: list[str] | None = None,
    description: str = "",
    has_claude_md: bool = False,
    has_git: bool = False,
    has_tests: bool = False,
    scan_dirs: list[str] | None = None,
    scan_exclude: list[str] | None = None,
    tags: list[str] | None = None,
    today: date | None = None,
) -> str:
    """Build a project registry note.

    Args:
        title: Project title.
        project_tag: Slug for filtering (e.g. "test-project").
        lab: Lab name.
        pi: Principal investigator name.
        status: Project status (active, maintenance, archived).
        project_path: Absolute path to project root.
        language: Programming languages used.
        hpc_path: HPC project path.
        scheduler: HPC scheduler name.
        linked_goals: Wiki-links to research goals.
        description: Project description.
        has_claude_md: Whether project has a CLAUDE.md.
        has_git: Whether project has git initialized.
        has_tests: Whether project has tests.
        scan_dirs: Whitelisted directories for /onboard doc discovery.
        scan_exclude: Additional exclude patterns merged with global onboard config.
        tags: Additional tags.
        today: Date override for testing.

    Returns:
        Complete note content string.
    """
    valid_statuses = {"active", "maintenance", "archived"}
    if status not in valid_statuses:
        msg = f"status must be one of {valid_statuses}, got {status!r}"
        raise ValueError(msg)

    d = today or date.today()
    fm = {
        "type": "project",
        "title": title,
        "project_tag": project_tag,
        "lab": lab,
        "pi": pi,
        "status": status,
        "project_path": project_path,
        "language": language or [],
        "hpc_path": hpc_path,
        "scheduler": scheduler,
        "linked_goals": linked_goals or [],
        "linked_hypotheses": [],
        "linked_experiments": [],
        "has_claude_md": has_claude_md,
        "has_git": has_git,
        "has_tests": has_tests,
        "scan_dirs": scan_dirs or [],
        "scan_exclude": scan_exclude or [],
        "created": d.isoformat(),
        "updated": d.isoformat(),
        "tags": ["project"] + (tags or []),
    }
    body = f"""## Description
{description}

## Research Goals

## Active Analyses

## Key Data

## HPC Notes

## Status Log
- {d.isoformat()}: Created
"""
    return _render_note(fm, body)


# -- Claim note ---------------------------------------------------------------


def build_claim_note(
    *,
    title: str,
    description: str,
    body: str = "",
    claim_type: str = "claim",
    source: str = "",
    confidence: str = "preliminary",
    source_class: str = "synthesis",
    verified_by: str = "agent",
    verified_who: str | None = None,
    verified_date: str | None = None,
    relevant_notes: list[tuple[str, str]] | None = None,
    topics: list[str] | None = None,
    tags: list[str] | None = None,
    today: date | None = None,
    source_vault: str | None = None,
    imported: str | None = None,
    quarantine: bool = False,
) -> tuple[str, str]:
    """Build an atomic claim note with full sanitization.

    Canonical constructor for claim notes created by Python code paths
    (federation import, tooling). Applies NFC normalization and title
    sanitization internally.

    Args:
        title: Claim title as a prose proposition.
        description: One sentence adding context beyond the title (~150 chars).
        body: Markdown body content (reasoning, evidence, links).
        claim_type: Note type (claim, evidence, methodology, etc.).
        source: Source attribution (wiki-link or citation string).
        confidence: established, supported, preliminary, or speculative.
        source_class: empirical, published, preprint, collaborator, synthesis,
            or hypothesis.
        verified_by: human, agent, or unverified.
        verified_who: Full name of human verifier (if verified_by is human).
        verified_date: ISO date of human verification.
        relevant_notes: List of (title, context) tuples for the footer.
        topics: List of topic map titles for the footer.
        tags: Additional tags.
        today: Date override for testing.
        source_vault: Originating vault name (federation import).
        imported: ISO timestamp of when the claim was exported (federation).
        quarantine: Mark imported claim for manual review (federation).

    Returns:
        Tuple of (safe_filename_stem, note_content_string).
        The filename stem is the sanitized title suitable for use as
        ``{stem}.md``.
    """
    d = today or date.today()
    safe_title = sanitize_title(title)
    normalized_desc = normalize_text(description)

    fm: dict[str, Any] = {
        "description": normalized_desc,
        "type": claim_type,
        "confidence": confidence,
        "source_class": source_class,
        "verified_by": verified_by,
        "created": d.isoformat(),
    }
    if source:
        fm["source"] = source
    if verified_who:
        fm["verified_who"] = verified_who
    if verified_date:
        fm["verified_date"] = verified_date
    if tags:
        fm["tags"] = tags
    if source_vault:
        fm["source_vault"] = source_vault
    if imported:
        fm["imported"] = imported
    if quarantine:
        fm["quarantine"] = True

    # Build body with footer
    parts = [body.rstrip() if body else ""]

    # Footer
    footer_lines: list[str] = []
    if source:
        footer_lines.append(f"Source: {source}")
    if relevant_notes:
        footer_lines.append("")
        footer_lines.append("Relevant Notes:")
        for note_title, context in relevant_notes:
            footer_lines.append(f"- [[{note_title}]] -- {context}")
    if topics:
        footer_lines.append("")
        footer_lines.append("Topics:")
        for topic in topics:
            footer_lines.append(f"- [[{topic}]]")

    if footer_lines:
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.extend(footer_lines)

    full_body = "\n".join(parts) + "\n"

    return safe_title, _render_note(fm, full_body)


# -- Foreign hypothesis note -------------------------------------------------


def build_foreign_hypothesis_note(
    *,
    hyp_id: str,
    title: str,
    status: str = "proposed",
    elo: float = 1200.0,
    matches: int = 0,
    generation: int = 1,
    research_goal: str = "",
    tags: list[str] | None = None,
    statement: str = "",
    mechanism: str = "",
    predictions: str = "",
    assumptions: str = "",
    limitations: str = "",
    source_vault: str = "",
    exported: str = "",
    quarantine: bool = True,
) -> tuple[str, str]:
    """Build a foreign-hypothesis note for federation import.

    Applies full sanitization boundary: ``sanitize_title`` on hyp_id
    (filename stem), ``normalize_text`` on title and research_goal,
    ``strip_html`` + ``normalize_text`` on all body sections.

    Args:
        hyp_id: Hypothesis identifier (used as filename stem after sanitization).
        title: Hypothesis title.
        status: Hypothesis status.
        elo: Source vault Elo rating (stored as elo_source).
        matches: Source vault match count (stored as matches_source).
        generation: Hypothesis generation number.
        research_goal: Associated research goal identifier.
        tags: Additional tags (foreign-hypothesis tag added automatically).
        statement: Statement section body.
        mechanism: Mechanism section body.
        predictions: Testable predictions section body.
        assumptions: Assumptions section body.
        limitations: Limitations section body.
        source_vault: Name of the originating vault.
        exported: ISO timestamp of when the hypothesis was exported.
        quarantine: Mark import for manual review (default True).

    Returns:
        Tuple of (safe_id_stem, note_content_string).
    """
    safe_id = sanitize_title(hyp_id)

    def _clean(text: str) -> str:
        return normalize_text(strip_html(text))

    fm: dict[str, Any] = {
        "type": "foreign-hypothesis",
        "title": normalize_text(title),
        "id": hyp_id,
        "status": status,
        "elo_federated": 1200,
        "elo_source": elo,
        "matches_federated": 0,
        "matches_source": matches,
        "generation": generation,
        "research_goal": normalize_text(research_goal),
        "source_vault": source_vault,
        "imported": exported,
        "tags": ["foreign-hypothesis"] + (tags or []),
    }
    if quarantine:
        fm["quarantine"] = True

    body_parts = [f"## Statement\n\n{_clean(statement)}\n"]
    if mechanism:
        body_parts.append(f"## Mechanism\n\n{_clean(mechanism)}\n")
    if predictions:
        body_parts.append(f"## Testable Predictions\n\n{_clean(predictions)}\n")
    if assumptions:
        body_parts.append(f"## Assumptions\n\n{_clean(assumptions)}\n")
    if limitations:
        body_parts.append(f"## Limitations & Risks\n\n{_clean(limitations)}\n")
    body_parts.append("## Federated Tournament History\n")

    body = "\n".join(body_parts) + "\n"

    return safe_id, _render_note(fm, body)
