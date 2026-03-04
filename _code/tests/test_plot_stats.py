"""Tests for engram_r.plot_stats -- stat helpers and formatters."""

from __future__ import annotations

import numpy as np
import pytest

from engram_r.plot_stats import (
    CorrelationResult,
    StatResult,
    format_correlation,
    format_pval,
    pval_stars,
    run_correlation,
    run_test,
    save_pvalues,
    select_test,
)

# -- select_test decision tree ------------------------------------------------


class TestSelectTest:
    """Tests for the statistical test selection decision tree."""

    def test_two_group_welch_large_normal(self):
        assert select_test("two_group", 50, normal=True) == "welch_t"

    def test_two_group_welch_at_boundary(self):
        assert select_test("two_group", 30, normal=True) == "welch_t"

    def test_two_group_mann_whitney_not_normal(self):
        assert select_test("two_group", 50, normal=False) == "mann_whitney"

    def test_two_group_mann_whitney_small_n(self):
        assert select_test("two_group", 10, normal=True) == "mann_whitney"

    def test_two_group_requires_n(self):
        with pytest.raises(ValueError, match="n_per_group required"):
            select_test("two_group")

    def test_multi_group_always_kruskal(self):
        assert select_test("multi_group") == "kruskal_wallis"

    def test_paired_normal(self):
        assert select_test("paired", normal=True) == "paired_t"

    def test_paired_not_normal(self):
        assert select_test("paired", normal=False) == "wilcoxon_signed_rank"

    def test_correlation_default_spearman(self):
        assert select_test("correlation") == "spearman"

    def test_correlation_pearson_when_normal(self):
        assert select_test("correlation", method="pearson", normal=True) == "pearson"

    def test_correlation_spearman_when_pearson_not_normal(self):
        assert (
            select_test("correlation", method="pearson", normal=False) == "spearman"
        )

    def test_proportion_chi_square(self):
        assert select_test("proportion", min_expected=10) == "chi_square"

    def test_proportion_fisher_exact(self):
        assert select_test("proportion", min_expected=3) == "fisher_exact"

    def test_unknown_design_raises(self):
        with pytest.raises(ValueError, match="Unknown design"):
            select_test("unknown")

    def test_case_insensitive(self):
        assert select_test("TWO_GROUP", 50, normal=False) == "mann_whitney"
        assert select_test("Multi_Group") == "kruskal_wallis"


# -- Formatters ----------------------------------------------------------------


class TestFormatPval:
    """Tests for format_pval."""

    def test_above_threshold(self):
        assert format_pval(0.042) == "p = 0.042"

    def test_below_threshold(self):
        assert format_pval(0.0001) == "p < 0.001"

    def test_at_threshold(self):
        assert format_pval(0.001) == "p = 0.001"

    def test_near_one(self):
        assert format_pval(0.999) == "p = 0.999"

    def test_nan(self):
        assert format_pval(float("nan")) == "p = NA"

    def test_custom_threshold(self):
        assert format_pval(0.04, threshold=0.05) == "p < 0.05"


class TestPvalStars:
    """Tests for pval_stars."""

    @pytest.mark.parametrize(
        "p, expected",
        [
            (0.0001, "***"),
            (0.005, "**"),
            (0.03, "*"),
            (0.1, "ns"),
            (1.0, "ns"),
        ],
    )
    def test_star_thresholds(self, p: float, expected: str):
        assert pval_stars(p) == expected

    def test_nan_returns_ns(self):
        assert pval_stars(float("nan")) == "ns"


class TestFormatCorrelation:
    """Tests for format_correlation."""

    def test_basic(self):
        result = format_correlation(0.42, 0.003, 50)
        assert "r = 0.42" in result
        assert "p = 0.003" in result
        assert "n = 50" in result

    def test_small_p(self):
        result = format_correlation(-0.85, 0.00001, 100)
        assert "r = -0.85" in result
        assert "p < 0.001" in result
        assert "n = 100" in result


# -- Test runners --------------------------------------------------------------


class TestRunTest:
    """Tests for run_test."""

    def test_mann_whitney(self):
        rng = np.random.default_rng(42)
        x = rng.normal(5, 1, 30)
        y = rng.normal(7, 1, 30)
        result = run_test(x, y, test="mann_whitney")
        assert isinstance(result, StatResult)
        assert result.test == "mann_whitney"
        assert 0 <= result.pvalue <= 1

    def test_welch_t(self):
        rng = np.random.default_rng(42)
        x = rng.normal(5, 1, 30)
        y = rng.normal(7, 1, 30)
        result = run_test(x, y, test="welch_t")
        assert result.test == "welch_t"
        assert 0 <= result.pvalue <= 1

    def test_paired_t(self):
        rng = np.random.default_rng(42)
        x = rng.normal(5, 1, 20)
        y = x + rng.normal(1, 0.5, 20)
        result = run_test(x, y, test="paired_t")
        assert result.test == "paired_t"
        assert result.pvalue < 0.05  # clear effect

    def test_wilcoxon_signed_rank(self):
        rng = np.random.default_rng(42)
        x = rng.normal(5, 1, 20)
        y = x + rng.normal(1, 0.5, 20)
        result = run_test(x, y, test="wilcoxon_signed_rank")
        assert result.test == "wilcoxon_signed_rank"
        assert 0 <= result.pvalue <= 1

    def test_kruskal_wallis(self):
        rng = np.random.default_rng(42)
        x = rng.normal(5, 1, 30)
        y = rng.normal(8, 1, 30)
        result = run_test(x, y, test="kruskal_wallis")
        assert result.test == "kruskal_wallis"
        assert 0 <= result.pvalue <= 1

    def test_unknown_test_raises(self):
        with pytest.raises(ValueError, match="Unknown test"):
            run_test(np.array([1, 2, 3]), np.array([4, 5, 6]), test="bogus")

    def test_welch_t_requires_two_groups(self):
        with pytest.raises(ValueError, match="requires two groups"):
            run_test(np.array([1, 2, 3]), test="welch_t")

    def test_result_format_method(self):
        rng = np.random.default_rng(42)
        x = rng.normal(5, 1, 30)
        y = rng.normal(7, 1, 30)
        result = run_test(x, y, test="mann_whitney")
        formatted = result.format()
        assert "stat=" in formatted
        assert "p" in formatted


class TestRunCorrelation:
    """Tests for run_correlation."""

    def test_spearman(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, 50)
        y = x + rng.normal(0, 0.5, 50)
        result = run_correlation(x, y, method="spearman")
        assert isinstance(result, CorrelationResult)
        assert result.test == "spearman"
        assert result.n == 50
        assert result.estimate > 0.5  # strong correlation

    def test_pearson(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, 50)
        y = x + rng.normal(0, 0.5, 50)
        result = run_correlation(x, y, method="pearson")
        assert result.test == "pearson"
        assert result.estimate > 0.5

    def test_format_method(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, 50)
        y = x + rng.normal(0, 0.5, 50)
        result = run_correlation(x, y)
        formatted = result.format()
        assert "r = " in formatted
        assert "n = 50" in formatted


# -- save_pvalues --------------------------------------------------------------


class TestSavePvalues:
    """Tests for save_pvalues."""

    def test_dict_input(self, tmp_path):
        fig_path = tmp_path / "plot.pdf"
        fig_path.touch()
        pvals = {"Group A vs B": 0.03, "Group A vs C": 0.0001}
        sidecar = save_pvalues(fig_path, pvals)
        assert sidecar.exists()
        content = sidecar.read_text()
        assert "Group A vs B" in content
        assert "p = 0.030" in content
        assert "p < 0.001" in content

    def test_list_input(self, tmp_path):
        fig_path = tmp_path / "plot.pdf"
        fig_path.touch()
        pvals = [("Test1", 0.05), ("Test2", 0.0005)]
        sidecar = save_pvalues(fig_path, pvals)
        content = sidecar.read_text()
        assert "Test1" in content
        assert "Test2" in content

    def test_sidecar_naming(self, tmp_path):
        fig_path = tmp_path / "my_figure.pdf"
        fig_path.touch()
        sidecar = save_pvalues(fig_path, {"x": 0.5})
        assert sidecar.name == "my_figure_pvalues.txt"
