"""Tests for engram_r.plot_builders -- verify each builder returns fig/axes."""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")  # non-interactive backend for CI

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
from engram_r.plot_theme import save_figure


@pytest.fixture
def toy_df():
    """Small DataFrame for testing categorical/numeric plot builders."""
    rng = np.random.default_rng(42)
    n = 40
    return pd.DataFrame({
        "group": np.repeat(["A", "B"], n // 2),
        "sex": np.tile(["Male", "Female"], n // 2),
        "value": rng.normal(5, 1, n),
        "x_val": rng.normal(0, 1, n),
        "y_val": rng.normal(0, 1, n),
    })


@pytest.fixture
def toy_de_df():
    """Small DataFrame mimicking differential expression results."""
    rng = np.random.default_rng(42)
    n = 100
    log2fc = rng.normal(0, 2, n)
    pval = rng.uniform(0.0001, 1, n)
    direction = np.where(
        (np.abs(log2fc) > 1) & (pval < 0.05),
        np.where(log2fc > 0, "Up", "Down"),
        "NS",
    )
    return pd.DataFrame({
        "log2FoldChange": log2fc,
        "pvalue": pval,
        "direction": direction,
    })


@pytest.fixture
def toy_forest_df():
    """Small DataFrame for forest plot."""
    return pd.DataFrame({
        "label": ["Gene A", "Gene B", "Gene C", "Gene D"],
        "estimate": [0.5, -0.3, 1.2, 0.0],
        "ci_lower": [0.1, -0.8, 0.6, -0.5],
        "ci_upper": [0.9, 0.2, 1.8, 0.5],
    })


@pytest.fixture
def toy_roc_df():
    """Small DataFrame for ROC curve."""
    return pd.DataFrame({
        "fpr": [0.0, 0.1, 0.2, 0.4, 0.6, 1.0],
        "tpr": [0.0, 0.4, 0.6, 0.8, 0.9, 1.0],
    })


@pytest.fixture(autouse=True)
def close_all_figs():
    """Close all matplotlib figures after each test."""
    yield
    plt.close("all")


class TestBuildViolin:
    def test_returns_fig_and_axes(self, toy_df):
        fig, ax = build_violin(toy_df, "group", "value")
        assert isinstance(fig, plt.Figure)
        assert isinstance(ax, plt.Axes)

    def test_with_hue(self, toy_df):
        fig, ax = build_violin(toy_df, "group", "value", hue="sex")
        assert isinstance(fig, plt.Figure)

    def test_with_title(self, toy_df):
        fig, ax = build_violin(toy_df, "group", "value", title="Test Violin")
        assert ax.get_title() == "Test Violin"


class TestBuildBox:
    def test_returns_fig_and_axes(self, toy_df):
        fig, ax = build_box(toy_df, "group", "value")
        assert isinstance(fig, plt.Figure)
        assert isinstance(ax, plt.Axes)

    def test_with_hue(self, toy_df):
        fig, ax = build_box(toy_df, "group", "value", hue="sex")
        assert isinstance(fig, plt.Figure)


class TestBuildScatter:
    def test_returns_fig_and_axes(self, toy_df):
        fig, ax = build_scatter(toy_df, "x_val", "y_val")
        assert isinstance(fig, plt.Figure)

    def test_with_regression(self, toy_df):
        fig, ax = build_scatter(toy_df, "x_val", "y_val", add_lm=True)
        assert isinstance(fig, plt.Figure)

    def test_with_hue(self, toy_df):
        fig, ax = build_scatter(toy_df, "x_val", "y_val", hue="group")
        assert isinstance(fig, plt.Figure)


class TestBuildHeatmap:
    def test_returns_fig_and_axes(self):
        rng = np.random.default_rng(42)
        mat = pd.DataFrame(
            rng.normal(0, 1, (5, 5)),
            index=[f"row{i}" for i in range(5)],
            columns=[f"col{i}" for i in range(5)],
        )
        fig, ax = build_heatmap(mat)
        assert isinstance(fig, plt.Figure)

    def test_with_ndarray(self):
        rng = np.random.default_rng(42)
        mat = rng.normal(0, 1, (4, 4))
        fig, ax = build_heatmap(mat)
        assert isinstance(fig, plt.Figure)


class TestBuildVolcano:
    def test_returns_fig_and_axes(self, toy_de_df):
        fig, ax = build_volcano(toy_de_df, "log2FoldChange", "pvalue")
        assert isinstance(fig, plt.Figure)

    def test_with_direction_colors(self, toy_de_df):
        fig, ax = build_volcano(
            toy_de_df, "log2FoldChange", "pvalue", direction="direction"
        )
        assert isinstance(fig, plt.Figure)

    def test_with_title(self, toy_de_df):
        fig, ax = build_volcano(
            toy_de_df, "log2FoldChange", "pvalue", title="DE Results"
        )
        assert ax.get_title() == "DE Results"


class TestBuildForest:
    def test_returns_fig_and_axes(self, toy_forest_df):
        fig, ax = build_forest(toy_forest_df)
        assert isinstance(fig, plt.Figure)

    def test_with_title(self, toy_forest_df):
        fig, ax = build_forest(toy_forest_df, title="Effect Sizes")
        assert ax.get_title() == "Effect Sizes"


class TestBuildRoc:
    def test_from_dataframe(self, toy_roc_df):
        fig, ax = build_roc(toy_roc_df)
        assert isinstance(fig, plt.Figure)

    def test_from_arrays(self):
        rng = np.random.default_rng(42)
        y_true = rng.integers(0, 2, 100)
        y_score = rng.uniform(0, 1, 100)
        fig, ax = build_roc(y_true=y_true, y_score=y_score)
        assert isinstance(fig, plt.Figure)


class TestBuildBar:
    def test_returns_fig_and_axes(self, toy_df):
        summary = toy_df.groupby("group")["value"].mean().reset_index()
        fig, ax = build_bar(summary, "group", "value")
        assert isinstance(fig, plt.Figure)


class TestSaveIntegration:
    """Verify builders + save_figure work end-to-end."""

    def test_violin_save(self, toy_df, tmp_path):
        fig, ax = build_violin(toy_df, "group", "value")
        path = save_figure(fig, tmp_path / "violin_test", fmt="png", close=False)
        assert path.exists()
        assert path.suffix == ".png"

    def test_scatter_save_pdf(self, toy_df, tmp_path):
        fig, ax = build_scatter(toy_df, "x_val", "y_val")
        path = save_figure(fig, tmp_path / "scatter_test", fmt="pdf", close=False)
        assert path.exists()
        assert path.suffix == ".pdf"
