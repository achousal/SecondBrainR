"""Exploratory data analysis computations.

Provides summary statistics, correlations, distribution detection,
and themed plot generation for EDA reports. Uses PII auto-redaction.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from engram_r.pii_filter import auto_redact, load_domain_pii_patterns
from engram_r.plot_theme import apply_research_theme, save_figure

logger = logging.getLogger(__name__)


def load_dataset(
    path: str | Path,
    *,
    redact_pii: bool = True,
    config_path: str | Path | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Load a CSV dataset with optional PII auto-redaction.

    Args:
        path: Path to CSV file.
        redact_pii: Whether to auto-redact ID-like columns.
        config_path: Path to ops/config.yaml for domain-specific PII
            patterns.  When provided, the active domain profile's PII
            patterns are registered before redaction.

    Returns:
        Tuple of (DataFrame, list of redacted column names).
    """
    path = Path(path)
    logger.info("Loading dataset: %s", path)

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in (".tsv", ".txt"):
        df = pd.read_csv(path, sep="\t")
    elif path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    redacted_cols: list[str] = []
    if redact_pii:
        if config_path is not None:
            load_domain_pii_patterns(config_path)
        df, redacted_cols = auto_redact(df)

    logger.info(
        "Loaded %d rows x %d cols (redacted: %s)",
        len(df),
        len(df.columns),
        redacted_cols,
    )
    return df, redacted_cols


def compute_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Compute summary statistics for a DataFrame.

    Args:
        df: Input DataFrame.

    Returns:
        Dict with shape, dtypes, describe (numeric), missing counts.
    """
    numeric_df = df.select_dtypes(include="number")
    return {
        "shape": {"rows": len(df), "cols": len(df.columns)},
        "columns": list(df.columns),
        "dtypes": {str(col): str(dtype) for col, dtype in df.dtypes.items()},
        "describe": numeric_df.describe().to_dict() if not numeric_df.empty else {},
        "missing": df.isnull().sum().to_dict(),
        "n_duplicates": int(df.duplicated().sum()),
    }


def compute_correlations(
    df: pd.DataFrame,
    method: str = "pearson",
) -> pd.DataFrame:
    """Compute correlation matrix for numeric columns.

    Args:
        df: Input DataFrame.
        method: Correlation method ('pearson', 'spearman', 'kendall').

    Returns:
        Correlation matrix DataFrame.
    """
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] < 2:
        return pd.DataFrame()
    return numeric_df.corr(method=method)


def detect_distributions(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Compute basic distribution stats for numeric columns.

    Args:
        df: Input DataFrame.

    Returns:
        Dict mapping column names to {skew, kurtosis, n_unique, pct_zero}.
    """
    result = {}
    numeric_df = df.select_dtypes(include="number")
    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        if len(series) == 0:
            continue
        result[col] = {
            "skew": float(series.skew()),
            "kurtosis": float(series.kurtosis()),
            "n_unique": int(series.nunique()),
            "pct_zero": float((series == 0).mean() * 100),
        }
    return result


def generate_eda_plots(
    df: pd.DataFrame,
    output_dir: str | Path,
    *,
    max_cols: int = 20,
) -> list[Path]:
    """Generate standard EDA plots for a DataFrame.

    Produces:
    - Histograms for numeric columns
    - Correlation heatmap (if >=2 numeric columns)
    - Missing data bar chart

    Args:
        df: Input DataFrame.
        output_dir: Directory to save plots.
        max_cols: Max numeric columns to plot individually.

    Returns:
        List of saved figure paths.
    """
    output_dir = Path(output_dir)
    apply_research_theme()
    saved: list[Path] = []

    numeric_df = df.select_dtypes(include="number")
    cols_to_plot = list(numeric_df.columns[:max_cols])

    # Histograms
    if cols_to_plot:
        n = len(cols_to_plot)
        ncols = min(3, n)
        nrows = (n + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
        if n == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

        for i, col in enumerate(cols_to_plot):
            ax = axes[i]
            numeric_df[col].dropna().hist(ax=ax, bins=30, edgecolor="white")
            ax.set_title(col)
            ax.set_ylabel("Count")

        # Hide empty axes
        for j in range(len(cols_to_plot), len(axes)):
            axes[j].set_visible(False)

        fig.tight_layout()
        saved.append(save_figure(fig, output_dir / "histograms"))

    # Correlation heatmap
    corr = compute_correlations(df)
    if not corr.empty and corr.shape[0] >= 2:
        size = corr.shape[0]
        fig, ax = plt.subplots(figsize=(max(8, size), max(6, size * 0.8)))
        sns.heatmap(
            corr,
            annot=True,
            fmt=".2f",
            cmap="RdBu_r",
            center=0,
            vmin=-1,
            vmax=1,
            ax=ax,
        )
        ax.set_title("Correlation Matrix")
        fig.tight_layout()
        saved.append(save_figure(fig, output_dir / "correlation_heatmap"))

    # Missing data
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if not missing.empty:
        fig, ax = plt.subplots(figsize=(max(8, len(missing) * 0.5), 5))
        missing.plot(kind="bar", ax=ax, color="#377EB8", edgecolor="white")
        ax.set_title("Missing Values by Column")
        ax.set_ylabel("Count")
        fig.tight_layout()
        saved.append(save_figure(fig, output_dir / "missing_data"))

    return saved
