"""Tests for verify_health module -- deterministic note health checks."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from engram_r.verify_health import (
    CheckItem,
    HealthReport,
    check_description_quality,
    check_link_density,
    check_topic_map_connection,
    extract_topics_section,
    extract_wiki_links,
    load_health_config,
    resolve_links,
    verify_batch,
    verify_note_health,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _note(fm_lines: list[str], body: str = "## Body\nContent\n") -> str:
    fm = "\n".join(fm_lines)
    return f"---\n{fm}\n---\n\n{body}"


@pytest.fixture()
def mini_vault(tmp_path: Path) -> Path:
    """Create a minimal vault with config and a few notes."""
    # Config
    ops = tmp_path / "ops"
    ops.mkdir()
    config = ops / "config.yaml"
    config.write_text(
        textwrap.dedent("""\
        health:
          graph_directories:
          - notes
          - _research
          exclude_directories:
          - ops
          - .claude
        """),
        encoding="utf-8",
    )

    # Notes directory with a couple of claims
    notes = tmp_path / "notes"
    notes.mkdir()

    (notes / "plasma nfl is elevated in dementia.md").write_text(
        _note(
            [
                'description: "Plasma NfL rises across all dementia subtypes"',
                "type: claim",
                'source: "[[2022-paper]]"',
            ],
            body=(
                "## Body\n"
                "Plasma NfL is a non-specific marker of neurodegeneration.\n"
                "See [[p-tau217 outperforms nfl]] for comparison.\n\n"
                "---\n\n"
                "Topics:\n"
                "- [[blood-based ad biomarkers]]\n"
            ),
        ),
        encoding="utf-8",
    )

    (notes / "p-tau217 outperforms nfl.md").write_text(
        _note(
            [
                'description: "p-tau217 has higher specificity than NfL for AD pathology"',
                "type: claim",
                'source: "[[2023-paper]]"',
            ],
            body=(
                "## Body\n"
                "Content about p-tau217.\n"
                "See [[plasma nfl is elevated in dementia]].\n\n"
                "---\n\n"
                "Topics:\n"
                "- [[blood-based ad biomarkers]]\n"
            ),
        ),
        encoding="utf-8",
    )

    (notes / "blood-based ad biomarkers.md").write_text(
        _note(
            [
                'description: "Navigation hub for blood-based AD biomarker claims"',
                "type: moc",
            ],
            body=(
                "# blood-based ad biomarkers\n\n"
                "## Core Ideas\n"
                "- [[plasma nfl is elevated in dementia]] -- non-specific marker\n"
                "- [[p-tau217 outperforms nfl]] -- higher specificity\n"
            ),
        ),
        encoding="utf-8",
    )

    # Research directory
    research = tmp_path / "_research" / "literature"
    research.mkdir(parents=True)
    (research / "2022-paper.md").write_text(
        _note(
            [
                'title: "Paper about NfL"',
                "type: literature",
                "status: read",
                "created: 2026-01-01",
            ],
        ),
        encoding="utf-8",
    )
    (research / "2023-paper.md").write_text(
        _note(
            [
                'title: "Paper about p-tau217"',
                "type: literature",
                "status: read",
                "created: 2026-01-01",
            ],
        ),
        encoding="utf-8",
    )

    return tmp_path


# ---------------------------------------------------------------------------
# TestExtractWikiLinks
# ---------------------------------------------------------------------------


class TestExtractWikiLinks:
    """Wiki link extraction from markdown content."""

    def test_simple_links(self):
        content = "See [[alpha]] and [[beta]] for details."
        links = extract_wiki_links(content)
        assert links == ["alpha", "beta"]

    def test_aliased_links(self):
        content = "Check [[real target|display name]] here."
        links = extract_wiki_links(content)
        assert links == ["real target"]

    def test_fenced_code_block_excluded(self):
        content = (
            "Before.\n"
            "```python\n"
            'link = "[[should-not-match]]"\n'
            "```\n"
            "After [[real-link]].\n"
        )
        links = extract_wiki_links(content)
        assert links == ["real-link"]

    def test_inline_code_excluded(self):
        content = "Use `[[not-a-link]]` but also see [[real-link]]."
        links = extract_wiki_links(content)
        assert links == ["real-link"]

    def test_empty_content(self):
        assert extract_wiki_links("") == []

    def test_no_links(self):
        assert extract_wiki_links("Plain text, no wiki links.") == []

    def test_duplicate_links_preserved(self):
        content = "[[alpha]] then [[alpha]] again."
        links = extract_wiki_links(content)
        assert links == ["alpha", "alpha"]

    def test_multiline_fenced_block(self):
        content = (
            "```\n"
            "[[inside-fence]]\n"
            "more code\n"
            "```\n"
            "[[outside-fence]]\n"
        )
        links = extract_wiki_links(content)
        assert links == ["outside-fence"]


# ---------------------------------------------------------------------------
# TestResolveLinks
# ---------------------------------------------------------------------------


class TestResolveLinks:
    """Link resolution against vault filesystem."""

    def test_existing_files(self, mini_vault: Path):
        targets = ["plasma nfl is elevated in dementia", "p-tau217 outperforms nfl"]
        graph_dirs = ["notes", "_research"]
        missing = resolve_links(targets, mini_vault, graph_dirs)
        assert missing == []

    def test_missing_file(self, mini_vault: Path):
        targets = ["nonexistent claim"]
        graph_dirs = ["notes", "_research"]
        missing = resolve_links(targets, mini_vault, graph_dirs)
        assert missing == ["nonexistent claim"]

    def test_graph_dirs_scoping(self, tmp_path: Path):
        """Files outside graph_dirs are not found."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "hidden.md").write_text("content", encoding="utf-8")
        notes = tmp_path / "notes"
        notes.mkdir()
        missing = resolve_links(["hidden"], tmp_path, ["notes"])
        assert missing == ["hidden"]

    def test_full_vault_fallback(self, mini_vault: Path):
        """Literature notes in _research subdirs resolve via recursive search."""
        targets = ["2022-paper"]
        graph_dirs = ["notes", "_research"]
        missing = resolve_links(targets, mini_vault, graph_dirs)
        assert missing == []

    def test_empty_targets(self, mini_vault: Path):
        missing = resolve_links([], mini_vault, ["notes"])
        assert missing == []


# ---------------------------------------------------------------------------
# TestDescriptionQuality
# ---------------------------------------------------------------------------


class TestDescriptionQuality:
    """Description quality checks against title."""

    def test_good_description(self):
        checks = check_description_quality(
            "plasma nfl is elevated in dementia",
            "Plasma NfL rises across all dementia subtypes",
        )
        statuses = [c.status for c in checks]
        assert "FAIL" not in statuses

    def test_restated_title(self):
        checks = check_description_quality(
            "plasma nfl is elevated in dementia",
            "plasma nfl is elevated in dementia",
        )
        failed = [c for c in checks if c.status == "FAIL"]
        assert any("restat" in c.detail.lower() for c in failed)

    def test_too_short(self):
        checks = check_description_quality(
            "some long title about a scientific topic",
            "Short",
        )
        warned = [c for c in checks if c.status == "WARN"]
        assert any("short" in c.detail.lower() for c in warned)

    def test_too_long(self):
        long_desc = "x" * 300
        checks = check_description_quality("title", long_desc)
        warned = [c for c in checks if c.status == "WARN"]
        assert any("long" in c.detail.lower() for c in warned)

    def test_trailing_period(self):
        checks = check_description_quality("title", "Ends with a period.")
        warned = [c for c in checks if c.status == "WARN"]
        assert any("period" in c.detail.lower() for c in warned)

    def test_multi_sentence(self):
        checks = check_description_quality(
            "title",
            "First sentence. Second sentence",
        )
        warned = [c for c in checks if c.status == "WARN"]
        assert any("sentence" in c.detail.lower() for c in warned)


# ---------------------------------------------------------------------------
# TestLinkDensity
# ---------------------------------------------------------------------------


class TestLinkDensity:
    """Link density threshold checks."""

    def test_zero_links(self):
        checks = check_link_density([])
        assert any(c.status == "WARN" for c in checks)

    def test_one_link(self):
        checks = check_link_density(["alpha"])
        assert any(c.status == "WARN" for c in checks)

    def test_two_links(self):
        checks = check_link_density(["alpha", "beta"])
        assert all(c.status == "PASS" for c in checks)

    def test_five_links(self):
        checks = check_link_density(["a", "b", "c", "d", "e"])
        assert all(c.status == "PASS" for c in checks)

    def test_custom_threshold(self):
        checks = check_link_density(["alpha"], min_links=1)
        assert all(c.status == "PASS" for c in checks)


# ---------------------------------------------------------------------------
# TestExtractTopicsSection
# ---------------------------------------------------------------------------


class TestExtractTopicsSection:
    """Parse the Topics footer section."""

    def test_standard_footer(self):
        content = (
            "Body text.\n\n"
            "---\n\n"
            "Topics:\n"
            "- [[topic-a]]\n"
            "- [[topic-b]]\n"
        )
        topics = extract_topics_section(content)
        assert topics == ["topic-a", "topic-b"]

    def test_multiple_topics(self):
        content = "Topics:\n- [[a]]\n- [[b]]\n- [[c]]\n"
        topics = extract_topics_section(content)
        assert topics == ["a", "b", "c"]

    def test_no_topics_section(self):
        content = "Just body text. No topics footer."
        topics = extract_topics_section(content)
        assert topics == []

    def test_topics_with_context(self):
        content = "Topics:\n- [[topic-a]] -- context about topic\n"
        topics = extract_topics_section(content)
        assert topics == ["topic-a"]


# ---------------------------------------------------------------------------
# TestTopicMapConnection
# ---------------------------------------------------------------------------


class TestTopicMapConnection:
    """Topic map connection validation."""

    def test_valid_connection(self, mini_vault: Path):
        checks = check_topic_map_connection(
            "plasma nfl is elevated in dementia",
            ["blood-based ad biomarkers"],
            mini_vault,
        )
        statuses = [c.status for c in checks]
        assert "FAIL" not in statuses

    def test_missing_topic_file(self, tmp_path: Path):
        notes = tmp_path / "notes"
        notes.mkdir()
        checks = check_topic_map_connection(
            "some claim",
            ["nonexistent-topic"],
            tmp_path,
        )
        warned = [c for c in checks if c.status == "WARN"]
        assert len(warned) >= 1

    def test_no_topics_section(self, tmp_path: Path):
        checks = check_topic_map_connection("some claim", [], tmp_path)
        warned = [c for c in checks if c.status == "WARN"]
        assert any("topic" in c.detail.lower() for c in warned)


# ---------------------------------------------------------------------------
# TestVerifyNoteHealth -- integration
# ---------------------------------------------------------------------------


class TestVerifyNoteHealth:
    """Integration tests for full note health check."""

    def test_healthy_note(self, mini_vault: Path):
        note_path = mini_vault / "notes" / "plasma nfl is elevated in dementia.md"
        report = verify_note_health(
            note_path,
            mini_vault,
            ["notes", "_research"],
        )
        assert report.overall in ("PASS", "WARN")
        assert len(report.failures) == 0

    def test_dangling_link(self, tmp_path: Path):
        notes = tmp_path / "notes"
        notes.mkdir()
        note = notes / "test claim.md"
        note.write_text(
            _note(
                [
                    'description: "Test description that adds context"',
                    "type: claim",
                ],
                body="See [[nonexistent target]] for details.\n",
            ),
            encoding="utf-8",
        )
        report = verify_note_health(note, tmp_path, ["notes"])
        failed = [c for c in report.checks if c.status == "FAIL"]
        assert any("dangling" in c.detail.lower() or "missing" in c.detail.lower() for c in failed)

    def test_no_frontmatter(self, tmp_path: Path):
        notes = tmp_path / "notes"
        notes.mkdir()
        note = notes / "no-fm.md"
        note.write_text("# Just a heading\nNo frontmatter.\n", encoding="utf-8")
        report = verify_note_health(note, tmp_path, ["notes"])
        # Permissive -- no frontmatter passes silently
        assert report.overall in ("PASS", "WARN")

    def test_empty_file(self, tmp_path: Path):
        notes = tmp_path / "notes"
        notes.mkdir()
        note = notes / "empty.md"
        note.write_text("", encoding="utf-8")
        report = verify_note_health(note, tmp_path, ["notes"])
        assert report.overall == "PASS"


# ---------------------------------------------------------------------------
# TestVerifyBatch
# ---------------------------------------------------------------------------


class TestVerifyBatch:
    """Batch verification across vault."""

    def test_one_report_per_note(self, mini_vault: Path):
        reports = verify_batch(
            mini_vault,
            ["notes", "_research"],
            target_dirs=["notes"],
        )
        # mini_vault has 3 notes in notes/
        assert len(reports) == 3

    def test_excluded_dirs(self, mini_vault: Path):
        reports = verify_batch(
            mini_vault,
            ["notes", "_research"],
            target_dirs=["notes"],
        )
        for r in reports:
            assert "_research" not in str(r.note_path)

    def test_empty_vault(self, tmp_path: Path):
        notes = tmp_path / "notes"
        notes.mkdir()
        reports = verify_batch(tmp_path, ["notes"], target_dirs=["notes"])
        assert reports == []


# ---------------------------------------------------------------------------
# TestHealthReport
# ---------------------------------------------------------------------------


class TestHealthReport:
    """HealthReport rollup logic."""

    def test_all_pass(self):
        checks = [
            CheckItem("test1", "PASS", "ok"),
            CheckItem("test2", "PASS", "ok"),
        ]
        report = HealthReport(note_path=Path("test.md"), checks=checks)
        assert report.overall == "PASS"
        assert report.failures == []
        assert report.warnings == []

    def test_warn_rollup(self):
        checks = [
            CheckItem("test1", "PASS", "ok"),
            CheckItem("test2", "WARN", "something"),
        ]
        report = HealthReport(note_path=Path("test.md"), checks=checks)
        assert report.overall == "WARN"
        assert len(report.warnings) == 1

    def test_fail_rollup(self):
        checks = [
            CheckItem("test1", "PASS", "ok"),
            CheckItem("test2", "FAIL", "broken"),
            CheckItem("test3", "WARN", "meh"),
        ]
        report = HealthReport(note_path=Path("test.md"), checks=checks)
        assert report.overall == "FAIL"
        assert len(report.failures) == 1
        assert len(report.warnings) == 1

    def test_empty_checks(self):
        report = HealthReport(note_path=Path("test.md"), checks=[])
        assert report.overall == "PASS"


# ---------------------------------------------------------------------------
# TestLoadHealthConfig
# ---------------------------------------------------------------------------


class TestLoadHealthConfig:
    """Config loading from ops/config.yaml."""

    def test_loads_graph_dirs(self, mini_vault: Path):
        config = load_health_config(mini_vault)
        assert "notes" in config["graph_directories"]
        assert "_research" in config["graph_directories"]

    def test_missing_config_returns_defaults(self, tmp_path: Path):
        config = load_health_config(tmp_path)
        assert "graph_directories" in config
        assert len(config["graph_directories"]) > 0

    def test_config_without_health_section(self, tmp_path: Path):
        ops = tmp_path / "ops"
        ops.mkdir()
        (ops / "config.yaml").write_text("schema_validation: true\n", encoding="utf-8")
        config = load_health_config(tmp_path)
        assert "graph_directories" in config
