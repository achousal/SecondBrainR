"""Tests for fix_claim_structure.py maintenance script."""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script as a module
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "maintenance"
    / "fix_claim_structure.py"
)

spec = importlib.util.spec_from_file_location("fix_claim_structure", _SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

strip_title_echo = mod.strip_title_echo
fix_headers = mod.fix_headers
add_topics = mod.add_topics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_claim(notes_dir: Path, name: str, fm: str, body: str) -> Path:
    """Create a claim file with frontmatter and body."""
    path = notes_dir / f"{name}.md"
    content = f"---\n{fm}\n---\n{body}"
    path.write_text(content, encoding="utf-8")
    return path


def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure with notes/ dir."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "notes").mkdir()
    return vault


# ---------------------------------------------------------------------------
# strip_title_echo
# ---------------------------------------------------------------------------


class TestStripTitleEcho:
    def test_removes_heading(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        _make_claim(
            vault / "notes",
            "test-claim",
            'description: "Test claim"',
            "\n# Test Claim\n\nBody text here.\n",
        )

        count = strip_title_echo(vault, dry_run=False)
        assert count == 1

        text = (vault / "notes" / "test-claim.md").read_text()
        assert "# Test Claim" not in text
        assert "Body text here." in text

    def test_dry_run_no_op(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        path = _make_claim(
            vault / "notes",
            "test-claim",
            'description: "Test claim"',
            "\n# Test Claim\n\nBody text here.\n",
        )
        original = path.read_text()

        count = strip_title_echo(vault, dry_run=True)
        assert count == 1
        assert path.read_text() == original  # unchanged

    def test_no_heading_unchanged(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        _make_claim(
            vault / "notes",
            "no-heading",
            'description: "No heading"',
            "\nBody text without heading.\n",
        )

        count = strip_title_echo(vault, dry_run=False)
        assert count == 0


# ---------------------------------------------------------------------------
# fix_headers
# ---------------------------------------------------------------------------


class TestFixHeaders:
    def test_replaces_source_header(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        _make_claim(
            vault / "notes",
            "claim-with-source",
            'description: "Has source header"',
            "\nSome body.\n\n## Source\n[[paper-name]]\n",
        )

        count = fix_headers(vault, dry_run=False)
        assert count >= 1

        text = (vault / "notes" / "claim-with-source.md").read_text()
        assert "## Source" not in text
        assert "Source:" in text

    def test_skips_tension_type(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        _make_claim(
            vault / "notes",
            "tension-claim",
            'description: "A tension"\ntype: "tension"',
            "\nBody.\n\n## Source\n[[paper]]\n",
        )

        count = fix_headers(vault, dry_run=False)
        assert count == 0

        text = (vault / "notes" / "tension-claim.md").read_text()
        assert "## Source" in text  # preserved


# ---------------------------------------------------------------------------
# add_topics
# ---------------------------------------------------------------------------


class TestAddTopics:
    def test_adds_footer(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        _make_claim(
            vault / "notes",
            "no-topics",
            'description: "Missing topics"',
            "\nBody text here.\n",
        )

        count = add_topics(vault, dry_run=False)
        assert count == 1

        text = (vault / "notes" / "no-topics.md").read_text()
        assert "Topics:" in text

    def test_skips_if_present(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        _make_claim(
            vault / "notes",
            "has-topics",
            'description: "Already has topics"',
            "\nBody text here.\n\nTopics:\n- [[topic-a]]\n",
        )

        count = add_topics(vault, dry_run=False)
        assert count == 0

    def test_skips_moc_type(self, tmp_path: Path):
        vault = _make_vault(tmp_path)
        _make_claim(
            vault / "notes",
            "moc-note",
            'description: "A MOC"\ntype: "moc"',
            "\nBody text here.\n",
        )

        count = add_topics(vault, dry_run=False)
        assert count == 0
