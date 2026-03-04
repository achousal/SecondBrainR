"""Tests for EDA module."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from engram_r.eda import (
    compute_correlations,
    compute_summary,
    detect_distributions,
    generate_eda_plots,
    load_dataset,
)
from engram_r.pii_filter import clear_domain_patterns, register_domain_patterns

FIXTURES = Path(__file__).parent / "fixtures"

_CLINICAL_PATTERNS = [
    r"\b(subject|patient|participant|person|individual)[\s_]?id\b",
    r"\b(patient|subject|participant)[\s_]?name\b",
    r"\bMRN\b",
    r"\bsample[\s_]?id\b",
]


class TestLoadDataset:
    @pytest.fixture(autouse=True)
    def _register_clinical(self):
        register_domain_patterns(_CLINICAL_PATTERNS)
        yield
        clear_domain_patterns()

    def test_loads_csv(self):
        df, redacted = load_dataset(FIXTURES / "sample_dataset.csv")
        assert len(df) == 10
        assert "SubjectID" in redacted
        assert "Email" in redacted

    def test_no_redaction(self):
        df, redacted = load_dataset(FIXTURES / "sample_dataset.csv", redact_pii=False)
        assert redacted == []
        assert df["SubjectID"].iloc[0] == "S001"


class TestComputeSummary:
    @pytest.fixture
    def df(self):
        return pd.DataFrame({
            "Age": [70, 68, 75],
            "Metric_A": [0.45, 0.32, 0.51],
            "Sex": ["M", "F", "M"],
        })

    def test_shape(self, df):
        summary = compute_summary(df)
        assert summary["shape"] == {"rows": 3, "cols": 3}

    def test_columns(self, df):
        summary = compute_summary(df)
        assert "Age" in summary["columns"]
        assert "Metric_A" in summary["columns"]

    def test_describe(self, df):
        summary = compute_summary(df)
        assert "Age" in summary["describe"]
        assert "Metric_A" in summary["describe"]

    def test_missing(self, df):
        summary = compute_summary(df)
        assert summary["missing"]["Age"] == 0


class TestComputeCorrelations:
    def test_basic_correlation(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [2, 4, 6]})
        corr = compute_correlations(df)
        assert abs(corr.loc["a", "b"] - 1.0) < 1e-10

    def test_single_numeric_column(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        corr = compute_correlations(df)
        assert corr.empty

    def test_spearman(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [10, 20, 30]})
        corr = compute_correlations(df, method="spearman")
        assert abs(corr.loc["a", "b"] - 1.0) < 1e-10


class TestDetectDistributions:
    def test_basic(self):
        df = pd.DataFrame({"values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
        dists = detect_distributions(df)
        assert "values" in dists
        assert "skew" in dists["values"]
        assert "kurtosis" in dists["values"]

    def test_empty_column(self):
        df = pd.DataFrame({"values": pd.Series(dtype=float)})
        dists = detect_distributions(df)
        assert dists == {}


class TestGenerateEdaPlots:
    def test_generates_plots(self, tmp_path):
        df = pd.DataFrame({
            "Age": [70, 68, 75, 72, 80],
            "Metric_A": [0.45, 0.32, 0.51, 0.40, 0.60],
        })
        saved = generate_eda_plots(df, tmp_path)
        assert len(saved) >= 1
        for p in saved:
            assert p.exists()

    def test_empty_dataframe(self, tmp_path):
        df = pd.DataFrame({"text": ["a", "b", "c"]})
        saved = generate_eda_plots(df, tmp_path)
        assert saved == []
