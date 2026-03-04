"""Tests for populate_stubs.py maintenance script."""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script as a module (not in a package)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "maintenance"
    / "populate_stubs.py"
)

spec = importlib.util.spec_from_file_location("populate_stubs", _SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_normalize = mod._normalize
_extract_title_words = mod._extract_title_words
_title_similarity = mod._title_similarity
resolve_actual_file = mod.resolve_actual_file
update_abstract_section = mod.update_abstract_section


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Hello World") == "hello world"

    def test_nfc_normalization(self):
        # Combining acute accent -> precomposed form
        decomposed = "e\u0301"  # e + combining acute
        result = _normalize(decomposed)
        assert result == "\u00e9"  # precomposed e-acute


# ---------------------------------------------------------------------------
# _extract_title_words
# ---------------------------------------------------------------------------


class TestExtractTitleWords:
    def test_year_author_skip(self):
        stem = "2024-smith-plasma-biomarkers-in-aging"
        words = _extract_title_words(stem)
        assert words == ["plasma", "biomarkers", "in", "aging"]

    def test_short_stem_fallback(self):
        stem = "short"
        words = _extract_title_words(stem)
        assert words == ["short"]

    def test_two_part_stem(self):
        stem = "2024-smith"
        words = _extract_title_words(stem)
        assert words == ["2024", "smith"]


# ---------------------------------------------------------------------------
# _title_similarity
# ---------------------------------------------------------------------------


class TestTitleSimilarity:
    def test_identical(self):
        assert _title_similarity("hello world", "hello world") == 1.0

    def test_disjoint(self):
        assert _title_similarity("alpha beta", "gamma delta") == 0.0

    def test_partial_overlap(self):
        score = _title_similarity("plasma tau aging", "plasma tau biomarkers")
        # intersection: {plasma, tau} = 2, union: {plasma, tau, aging, biomarkers} = 4
        assert score == pytest.approx(0.5)

    def test_empty_string(self):
        assert _title_similarity("", "hello") == 0.0
        assert _title_similarity("hello", "") == 0.0


# ---------------------------------------------------------------------------
# resolve_actual_file
# ---------------------------------------------------------------------------


class TestResolveActualFile:
    def test_direct_match(self, tmp_path: Path):
        lit_dir = tmp_path / "lit"
        lit_dir.mkdir()
        target = lit_dir / "2024-smith-plasma-biomarkers.md"
        target.write_text("# test")

        result = resolve_actual_file(
            "_research/literature/2024-smith-plasma-biomarkers.md", lit_dir
        )
        assert result == target

    def test_fuzzy_match(self, tmp_path: Path):
        lit_dir = tmp_path / "lit"
        lit_dir.mkdir()
        # Actual file has full author name
        actual = lit_dir / "2024-smith-plasma-biomarkers-in-aging.md"
        actual.write_text("# test")

        # Queue has truncated single-letter author
        result = resolve_actual_file(
            "_research/literature/2024-s-plasma-biomarkers-in-aging.md", lit_dir
        )
        assert result == actual

    def test_no_match(self, tmp_path: Path):
        lit_dir = tmp_path / "lit"
        lit_dir.mkdir()
        (lit_dir / "2024-jones-unrelated-topic.md").write_text("# test")

        result = resolve_actual_file(
            "_research/literature/2025-smith-completely-different.md", lit_dir
        )
        assert result is None

    def test_skips_index_files(self, tmp_path: Path):
        lit_dir = tmp_path / "lit"
        lit_dir.mkdir()
        (lit_dir / "_index.md").write_text("# index")

        result = resolve_actual_file(
            "_research/literature/_index.md", lit_dir
        )
        # Direct match should still work for _index
        assert result is not None


# ---------------------------------------------------------------------------
# update_abstract_section
# ---------------------------------------------------------------------------


class TestUpdateAbstractSection:
    def test_replaces_abstract(self, tmp_path: Path):
        note = tmp_path / "test.md"
        note.write_text(textwrap.dedent("""\
            ---
            title: "Test"
            ---
            ## Abstract
            Old abstract text here.

            ## Key Points
            - Point 1
        """))

        result = update_abstract_section(note, "New abstract content.")
        assert result is True

        text = note.read_text()
        assert "New abstract content." in text
        assert "Old abstract text here." not in text
        assert "## Key Points" in text

    def test_returns_false_if_sections_missing(self, tmp_path: Path):
        note = tmp_path / "test.md"
        note.write_text("# No sections here\nJust text.\n")

        result = update_abstract_section(note, "New abstract.")
        assert result is False
