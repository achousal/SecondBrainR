"""Standard plot builder functions for Python.

Each builder returns (fig, axes) with the research theme applied.
Uses canonical palettes from plot_theme and sizes from FIGURE_SIZES.
Mirrors the R plot_builders.R module.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from engram_r.plot_theme import (
    DIRECTION_COLORS,
    DIVERGING_PALETTE,
    apply_research_theme,
    get_figure_size,
)

logger = logging.getLogger(__name__)


def _ensure_theme() -> None:
    """Apply research theme if not already set."""
    apply_research_theme()


# -- Violin plot ---------------------------------------------------------------


def build_violin(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    hue: str | None = None,
    title: str | None = None,
    palette: dict[str, str] | list[str] | None = None,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build a violin + strip plot.

    Args:
        data: DataFrame.
        x: Column for x-axis (categorical).
        y: Column for y-axis (numeric).
        hue: Column for color grouping (optional).
        title: Plot title (optional).
        palette: Color mapping (optional).
        figsize: Figure size in inches (optional, defaults to canonical).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        key = "violin_grouped" if hue else "violin_single"
        figsize = get_figure_size(key)

    fig, ax = plt.subplots(figsize=figsize)
    # When palette is provided without hue, assign hue=x to avoid
    # seaborn v0.14 deprecation warning.
    effective_hue = hue if hue else (x if palette else None)
    show_legend = bool(hue)
    sns.violinplot(
        data=data,
        x=x,
        y=y,
        hue=effective_hue,
        palette=palette,
        alpha=0.6,
        inner=None,
        legend=show_legend,
        ax=ax,
    )
    sns.stripplot(
        data=data,
        x=x,
        y=y,
        hue=effective_hue,
        palette=palette,
        size=3,
        alpha=0.5,
        dodge=bool(hue),
        legend=False,
        ax=ax,
    )
    if title:
        ax.set_title(title)
    return fig, ax


# -- Box plot ------------------------------------------------------------------


def build_box(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    hue: str | None = None,
    title: str | None = None,
    palette: dict[str, str] | list[str] | None = None,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build a box + strip plot.

    Args:
        data: DataFrame.
        x: Column for x-axis (categorical).
        y: Column for y-axis (numeric).
        hue: Column for color grouping (optional).
        title: Plot title (optional).
        palette: Color mapping (optional).
        figsize: Figure size in inches (optional).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        key = "box_grouped" if hue else "box_single"
        figsize = get_figure_size(key)

    fig, ax = plt.subplots(figsize=figsize)
    effective_hue = hue if hue else (x if palette else None)
    show_legend = bool(hue)
    sns.boxplot(
        data=data,
        x=x,
        y=y,
        hue=effective_hue,
        palette=palette,
        showfliers=False,
        legend=show_legend,
        ax=ax,
        boxprops={"alpha": 0.6},
    )
    sns.stripplot(
        data=data,
        x=x,
        y=y,
        hue=effective_hue,
        palette=palette,
        size=3,
        alpha=0.5,
        dodge=bool(hue),
        legend=False,
        ax=ax,
    )
    if title:
        ax.set_title(title)
    return fig, ax


# -- Scatter plot --------------------------------------------------------------


def build_scatter(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    hue: str | None = None,
    title: str | None = None,
    palette: dict[str, str] | list[str] | None = None,
    add_lm: bool = False,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build a scatter plot with optional regression line.

    Args:
        data: DataFrame.
        x: Column for x-axis.
        y: Column for y-axis.
        hue: Column for color grouping (optional).
        title: Plot title (optional).
        palette: Color mapping (optional).
        add_lm: Add linear regression line (default False).
        figsize: Figure size in inches (optional).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        figsize = get_figure_size("scatter_bivar")

    fig, ax = plt.subplots(figsize=figsize)
    sns.scatterplot(
        data=data,
        x=x,
        y=y,
        hue=hue,
        palette=palette,
        alpha=0.6,
        s=30,
        ax=ax,
    )
    if add_lm:
        sns.regplot(
            data=data,
            x=x,
            y=y,
            scatter=False,
            ci=95,
            ax=ax,
            line_kws={"color": "black", "linewidth": 0.8},
        )
    if title:
        ax.set_title(title)
    return fig, ax


# -- Heatmap -------------------------------------------------------------------


def build_heatmap(
    mat: pd.DataFrame | np.ndarray,
    *,
    title: str | None = None,
    cmap: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    annot: bool = True,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build a heatmap (correlation or expression).

    Args:
        mat: 2D matrix (DataFrame or ndarray).
        title: Plot title (optional).
        cmap: Colormap name (default DIVERGING_PALETTE).
        vmin: Minimum value for color scale.
        vmax: Maximum value for color scale.
        annot: Annotate cells with values (default True).
        figsize: Figure size in inches (optional).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        figsize = get_figure_size("heatmap")
    if cmap is None:
        cmap = DIVERGING_PALETTE

    if isinstance(mat, np.ndarray):
        mat = pd.DataFrame(mat)

    if vmin is None and vmax is None:
        max_abs = np.nanmax(np.abs(mat.values))
        vmin, vmax = -max_abs, max_abs

    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(
        mat,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        annot=annot,
        fmt=".2f",
        linewidths=0.5,
        square=True,
        ax=ax,
    )
    if title:
        ax.set_title(title)
    return fig, ax


# -- Volcano plot --------------------------------------------------------------


def build_volcano(
    data: pd.DataFrame,
    log2fc: str,
    pvalue: str,
    *,
    direction: str | None = None,
    title: str | None = None,
    fc_thresh: float = 1.0,
    p_thresh: float = 0.05,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build a volcano plot for effect size vs significance.

    Args:
        data: DataFrame.
        log2fc: Column for log2 fold change.
        pvalue: Column for p-value (will be -log10 transformed).
        direction: Column for direction category ("Up"/"Down"/"NS").
        title: Plot title (optional).
        fc_thresh: Fold change threshold for vertical lines (default 1.0).
        p_thresh: P-value threshold for horizontal line (default 0.05).
        figsize: Figure size in inches (optional).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        figsize = get_figure_size("volcano")

    plot_data = data.copy()
    pvals = plot_data[pvalue]
    if (pvals <= 0).any():
        import warnings

        warnings.warn(
            "Non-positive p-values detected; clamping to float min "
            "before -log10 transform",
            stacklevel=2,
        )
        pvals = pvals.clip(lower=np.finfo(float).tiny)
    plot_data["neg_log10_p"] = -np.log10(pvals)

    fig, ax = plt.subplots(figsize=figsize)

    if direction and direction in data.columns:
        for cat, color in DIRECTION_COLORS.items():
            mask = plot_data[direction] == cat
            ax.scatter(
                plot_data.loc[mask, log2fc],
                plot_data.loc[mask, "neg_log10_p"],
                c=color,
                alpha=0.5,
                s=10,
                label=cat,
            )
        ax.legend(loc="upper right", frameon=True, framealpha=0.9)
    else:
        ax.scatter(
            plot_data[log2fc],
            plot_data["neg_log10_p"],
            c="#999999",
            alpha=0.5,
            s=10,
        )

    ax.axhline(-np.log10(p_thresh), ls="--", color="0.5", lw=0.8)
    ax.axvline(-fc_thresh, ls="--", color="0.5", lw=0.8)
    ax.axvline(fc_thresh, ls="--", color="0.5", lw=0.8)
    ax.set_xlabel(log2fc)
    ax.set_ylabel(r"$-\log_{10}(p)$")
    if title:
        ax.set_title(title)
    return fig, ax


# -- Forest plot ---------------------------------------------------------------


def build_forest(
    data: pd.DataFrame,
    *,
    label: str = "label",
    estimate: str = "estimate",
    ci_lower: str = "ci_lower",
    ci_upper: str = "ci_upper",
    title: str | None = None,
    null_value: float = 0.0,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build a forest plot for effect sizes with confidence intervals.

    Args:
        data: DataFrame with label, estimate, ci_lower, ci_upper columns.
        label: Column name for labels.
        estimate: Column name for point estimates.
        ci_lower: Column name for lower CI bound.
        ci_upper: Column name for upper CI bound.
        title: Plot title (optional).
        null_value: Value for null effect line (default 0).
        figsize: Figure size in inches (optional).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        figsize = get_figure_size("forest")

    sorted_data = data.sort_values(estimate)
    y_pos = range(len(sorted_data))

    fig, ax = plt.subplots(figsize=figsize)
    ax.errorbar(
        sorted_data[estimate],
        y_pos,
        xerr=[
            sorted_data[estimate] - sorted_data[ci_lower],
            sorted_data[ci_upper] - sorted_data[estimate],
        ],
        fmt="o",
        color="black",
        capsize=3,
        markersize=5,
    )
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(sorted_data[label].tolist())
    ax.axvline(null_value, ls="--", color="0.5", lw=0.8)
    if title:
        ax.set_title(title)
    return fig, ax


# -- ROC curve -----------------------------------------------------------------


def build_roc(
    data: pd.DataFrame | None = None,
    *,
    fpr: str = "fpr",
    tpr: str = "tpr",
    group: str | None = None,
    y_true: np.ndarray | None = None,
    y_score: np.ndarray | None = None,
    title: str | None = None,
    palette: dict[str, str] | list[str] | None = None,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build an ROC curve plot.

    Can work from pre-computed FPR/TPR columns in a DataFrame, or from
    raw y_true/y_score arrays (requires scikit-learn).

    Args:
        data: DataFrame with fpr and tpr columns (optional if y_true/y_score).
        fpr: Column name for false positive rate.
        tpr: Column name for true positive rate.
        group: Column for grouping multiple curves (optional).
        y_true: True binary labels (alternative to data).
        y_score: Predicted scores (alternative to data).
        title: Plot title (optional).
        palette: Color mapping (optional).
        figsize: Figure size in inches (optional).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        figsize = get_figure_size("roc")

    fig, ax = plt.subplots(figsize=figsize)

    if y_true is not None and y_score is not None:
        try:
            from sklearn.metrics import roc_curve
        except ImportError:
            raise ImportError(
                "scikit-learn is required for ROC curve computation. "
                "Install it with: uv pip install engram-r[ml]"
            ) from None

        fpr_arr, tpr_arr, _ = roc_curve(y_true, y_score)
        ax.plot(fpr_arr, tpr_arr, linewidth=0.8)
    elif data is not None:
        if group and group in data.columns:
            for name, grp in data.groupby(group):
                color = palette.get(name) if isinstance(palette, dict) else None
                ax.plot(grp[fpr], grp[tpr], label=name, linewidth=0.8, color=color)
            ax.legend()
        else:
            ax.plot(data[fpr], data[tpr], linewidth=0.8)

    ax.plot([0, 1], [0, 1], ls="--", color="0.5", lw=0.8)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_aspect("equal")
    if title:
        ax.set_title(title)
    return fig, ax


# -- Bar plot ------------------------------------------------------------------


def build_bar(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    hue: str | None = None,
    yerr: str | None = None,
    title: str | None = None,
    palette: dict[str, str] | list[str] | None = None,
    figsize: tuple[float, float] | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Build a bar plot with optional error bars.

    Args:
        data: DataFrame.
        x: Column for x-axis (categorical).
        y: Column for y-axis (numeric, e.g. mean).
        hue: Column for color grouping (optional).
        yerr: Column for error bar values (optional, symmetric).
        title: Plot title (optional).
        palette: Color mapping (optional).
        figsize: Figure size in inches (optional).

    Returns:
        Tuple of (Figure, Axes).
    """
    _ensure_theme()
    if figsize is None:
        figsize = get_figure_size("bar")

    fig, ax = plt.subplots(figsize=figsize)
    effective_hue = hue if hue else (x if palette else None)
    show_legend = bool(hue)
    sns.barplot(
        data=data,
        x=x,
        y=y,
        hue=effective_hue,
        palette=palette,
        alpha=0.8,
        errorbar=None,
        legend=show_legend,
        ax=ax,
    )
    if yerr and yerr in data.columns:
        # Read bar positions from the rendered containers
        bar_positions = [bar.get_x() + bar.get_width() / 2 for bar in ax.patches]
        bar_heights = [bar.get_height() for bar in ax.patches]
        # Match error values to bar order (categorical x order)
        categories = data[x].unique()
        err_values = [
            data.loc[data[x] == cat, yerr].iloc[0]
            for cat in categories
            if len(data.loc[data[x] == cat, yerr]) > 0
        ]
        ax.errorbar(
            bar_positions[: len(categories)],
            bar_heights[: len(categories)],
            yerr=err_values,
            fmt="none",
            color="black",
            capsize=3,
        )
    if title:
        ax.set_title(title)
    return fig, ax
