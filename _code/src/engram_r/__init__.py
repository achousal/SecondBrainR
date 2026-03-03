"""EngramR: Co-scientist system for Obsidian-based hypothesis research."""

__version__ = "0.7.0"

from engram_r.plot_builders import (
    build_bar,
    build_box,
    build_forest,
    build_heatmap,
    build_roc,
    build_scatter,
    build_violin,
    build_volcano,
)
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
from engram_r.plot_theme import (
    BINARY_COLORS,
    DIRECTION_COLORS,
    DIVERGING_PALETTE,
    FIGURE_SIZES,
    LAB_PALETTES,
    SEMANTIC_PALETTES,
    SEQUENTIAL_PALETTE,
    SIG_COLORS,
    apply_research_theme,
    get_figure_size,
    get_lab_palette,
    save_figure,
)

__all__ = [
    # plot_builders
    "build_bar",
    "build_box",
    "build_forest",
    "build_heatmap",
    "build_roc",
    "build_scatter",
    "build_violin",
    "build_volcano",
    # plot_stats
    "CorrelationResult",
    "StatResult",
    "format_correlation",
    "format_pval",
    "pval_stars",
    "run_correlation",
    "run_test",
    "save_pvalues",
    "select_test",
    # plot_theme
    "BINARY_COLORS",
    "DIRECTION_COLORS",
    "DIVERGING_PALETTE",
    "FIGURE_SIZES",
    "LAB_PALETTES",
    "SEMANTIC_PALETTES",
    "SEQUENTIAL_PALETTE",
    "SIG_COLORS",
    "apply_research_theme",
    "get_figure_size",
    "get_lab_palette",
    "save_figure",
]
