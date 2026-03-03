"""Statistical test selection and formatting helpers.

Provides a decision tree for test selection, runners, and consistent
formatting of p-values, correlation results, and significance annotations.
Mirrors the R stats_helpers.R module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)


# -- Data classes --------------------------------------------------------------


@dataclass
class StatResult:
    """Result of a statistical test."""

    test: str
    statistic: float
    pvalue: float
    method: str
    extra: dict | None = None

    def format(self) -> str:
        """Format as a human-readable string."""
        return f"{self.method}: stat={self.statistic:.4f}, {format_pval(self.pvalue)}"


@dataclass
class CorrelationResult:
    """Result of a correlation test."""

    test: str
    estimate: float
    pvalue: float
    n: int
    method: str

    def format(self) -> str:
        """Format as annotation string: r = X.XX, p = Y.YYY, n = Z."""
        return format_correlation(self.estimate, self.pvalue, self.n)


# -- Test selection decision tree ----------------------------------------------


def select_test(
    design: str,
    n_per_group: int | None = None,
    *,
    normal: bool = False,
    method: str = "spearman",
    min_expected: float = 5,
) -> str:
    """Select the appropriate statistical test based on design and data.

    Decision tree:
    - two_group (unpaired): Welch t (n>=30, normal) or Mann-Whitney U
    - multi_group (3+): Kruskal-Wallis + Dunn post-hoc (BH correction)
    - paired: paired t (normal) or Wilcoxon signed-rank
    - correlation: Spearman (default) or Pearson (if requested + normal)
    - proportion: Fisher exact (expected<5) or Chi-square

    Args:
        design: "two_group", "multi_group", "paired", "correlation", "proportion".
        n_per_group: Sample size per group (required for two_group).
        normal: Whether data passes normality check.
        method: For correlation -- "spearman" (default) or "pearson".
        min_expected: Minimum expected cell count for proportion tests.

    Returns:
        String naming the recommended test.

    Raises:
        ValueError: If design is unknown or required args are missing.
    """
    design = design.lower()

    if design == "two_group":
        if n_per_group is None:
            msg = "n_per_group required for two_group design"
            raise ValueError(msg)
        if n_per_group >= 30 and normal:
            return "welch_t"
        return "mann_whitney"

    if design == "multi_group":
        return "kruskal_wallis"

    if design == "paired":
        return "paired_t" if normal else "wilcoxon_signed_rank"

    if design == "correlation":
        method = method.lower()
        if method == "pearson" and normal:
            return "pearson"
        return "spearman"

    if design == "proportion":
        if min_expected < 5:
            return "fisher_exact"
        return "chi_square"

    valid = "two_group, multi_group, paired, correlation, proportion"
    msg = f"Unknown design: '{design}'. Choose from: {valid}"
    raise ValueError(msg)


# -- Test runners --------------------------------------------------------------


def run_test(
    x: np.ndarray,
    y: np.ndarray | None = None,
    *,
    test: str = "mann_whitney",
    paired: bool = False,
) -> StatResult:
    """Run a statistical test and return a StatResult.

    Args:
        x: First data array (or single array for multi_group with y=None).
        y: Second data array (for two-group or paired tests).
        test: Test name from select_test().
        paired: Whether to treat as paired data.

    Returns:
        StatResult with test name, statistic, p-value, and method.
    """
    x = np.asarray(x, dtype=float)
    if y is not None:
        y = np.asarray(y, dtype=float)

    if test == "welch_t":
        if y is None:
            msg = "Welch t-test requires two groups"
            raise ValueError(msg)
        stat, pval = sp_stats.ttest_ind(x, y, equal_var=False)
        return StatResult(
            test="welch_t",
            statistic=float(stat),
            pvalue=float(pval),
            method="Welch Two Sample t-test",
        )

    if test == "mann_whitney":
        if y is None:
            msg = "Mann-Whitney U test requires two groups"
            raise ValueError(msg)
        stat, pval = sp_stats.mannwhitneyu(x, y, alternative="two-sided")
        return StatResult(
            test="mann_whitney",
            statistic=float(stat),
            pvalue=float(pval),
            method="Wilcoxon rank sum test",
        )

    if test == "paired_t":
        if y is None:
            msg = "Paired t-test requires two groups"
            raise ValueError(msg)
        stat, pval = sp_stats.ttest_rel(x, y)
        return StatResult(
            test="paired_t",
            statistic=float(stat),
            pvalue=float(pval),
            method="Paired t-test",
        )

    if test == "wilcoxon_signed_rank":
        if y is None:
            msg = "Wilcoxon signed-rank test requires two groups"
            raise ValueError(msg)
        stat, pval = sp_stats.wilcoxon(x, y)
        return StatResult(
            test="wilcoxon_signed_rank",
            statistic=float(stat),
            pvalue=float(pval),
            method="Wilcoxon signed rank test",
        )

    if test == "kruskal_wallis":
        # x and y can be two groups, or use *groups via extra args
        if y is None:
            msg = "Kruskal-Wallis requires at least two groups"
            raise ValueError(msg)
        stat, pval = sp_stats.kruskal(x, y)
        return StatResult(
            test="kruskal_wallis",
            statistic=float(stat),
            pvalue=float(pval),
            method="Kruskal-Wallis rank sum test",
        )

    msg = f"Unknown test: '{test}'"
    raise ValueError(msg)


def run_correlation(
    x: np.ndarray,
    y: np.ndarray,
    method: str = "spearman",
) -> CorrelationResult:
    """Run a correlation test.

    Args:
        x: First variable.
        y: Second variable.
        method: "spearman" (default) or "pearson".

    Returns:
        CorrelationResult with estimate, p-value, and n.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if method == "pearson":
        r, pval = sp_stats.pearsonr(x, y)
        method_name = "Pearson's product-moment correlation"
    else:
        r, pval = sp_stats.spearmanr(x, y)
        method_name = "Spearman's rank correlation rho"

    return CorrelationResult(
        test=method,
        estimate=float(r),
        pvalue=float(pval),
        n=len(x),
        method=method_name,
    )


# -- Formatters ----------------------------------------------------------------


def format_pval(p: float, threshold: float = 0.001) -> str:
    """Format a p-value for display.

    Args:
        p: P-value.
        threshold: Below this, report as "p < threshold" (default 0.001).

    Returns:
        Formatted string like "p = 0.042" or "p < 0.001".
    """
    if np.isnan(p):
        return "p = NA"
    if p < threshold:
        return f"p < {threshold}"
    return f"p = {p:.3f}"


def pval_stars(p: float) -> str:
    """Convert p-value to significance stars.

    Args:
        p: P-value.

    Returns:
        "***" (p<0.001), "**" (p<0.01), "*" (p<0.05), or "ns".
    """
    if np.isnan(p):
        return "ns"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def format_correlation(r: float, p: float, n: int) -> str:
    """Format a correlation result for plot annotation.

    Args:
        r: Correlation coefficient.
        p: P-value.
        n: Sample size.

    Returns:
        String like "r = 0.42, p = 0.003, n = 50".
    """
    return f"r = {r:.2f}, {format_pval(p)}, n = {n}"


def save_pvalues(
    path: str | Path,
    pvalues: dict[str, float] | list[tuple[str, float]],
) -> Path:
    """Save p-values as a sidecar text file alongside a figure.

    Args:
        path: Path to the figure file.
        pvalues: Dictionary or list of (label, p-value) pairs.

    Returns:
        Path to the sidecar file.
    """
    path = Path(path)
    sidecar = path.with_name(path.stem + "_pvalues.txt")

    items = pvalues.items() if isinstance(pvalues, dict) else pvalues

    lines = [f"{label}\t{format_pval(p)}" for label, p in items]
    sidecar.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Saved p-values: %s", sidecar)
    return sidecar
