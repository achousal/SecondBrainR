"""Tests for metabolic history -- persistence and trend analysis."""

from dataclasses import asdict

import yaml

from engram_r.metabolic_history import (
    MetabolicSnapshot,
    MetabolicTrend,
    compute_trends,
    format_trend_line,
    load_history,
    load_latest,
    save_snapshot,
)
from engram_r.metabolic_indicators import MetabolicState


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------


class TestSaveSnapshot:
    def test_creates_history_file(self, tmp_path):
        state = MetabolicState(qpr=2.0, cmr=3.0, tpv=1.5, hcr=20.0, gcr=0.8, ipr=1.0, vdr=90.0)
        save_snapshot(tmp_path, state, "session-001")
        history_path = tmp_path / "ops" / "metabolic" / "history.yaml"
        assert history_path.is_file()
        data = yaml.safe_load(history_path.read_text())
        assert len(data) == 1
        assert data[0]["session_id"] == "session-001"
        assert data[0]["indicators"]["qpr"] == 2.0

    def test_appends_to_existing(self, tmp_path):
        state1 = MetabolicState(qpr=2.0)
        state2 = MetabolicState(qpr=3.0)
        save_snapshot(tmp_path, state1, "s1")
        save_snapshot(tmp_path, state2, "s2")
        data = yaml.safe_load(
            (tmp_path / "ops" / "metabolic" / "history.yaml").read_text()
        )
        assert len(data) == 2
        assert data[0]["session_id"] == "s1"
        assert data[1]["session_id"] == "s2"

    def test_trims_to_max_snapshots(self, tmp_path):
        for i in range(5):
            state = MetabolicState(qpr=float(i))
            save_snapshot(tmp_path, state, f"s{i}", max_snapshots=3)
        data = yaml.safe_load(
            (tmp_path / "ops" / "metabolic" / "history.yaml").read_text()
        )
        assert len(data) == 3
        # Should keep the 3 most recent
        assert data[0]["session_id"] == "s2"
        assert data[2]["session_id"] == "s4"

    def test_writes_latest_cache(self, tmp_path):
        state = MetabolicState(qpr=5.0, tpv=2.0)
        save_snapshot(tmp_path, state, "s1")
        latest_path = tmp_path / "ops" / "metabolic" / "latest.yaml"
        assert latest_path.is_file()
        data = yaml.safe_load(latest_path.read_text())
        assert len(data) == 1
        assert data[0]["indicators"]["qpr"] == 5.0


# ---------------------------------------------------------------------------
# History loading
# ---------------------------------------------------------------------------


class TestLoadHistory:
    def test_empty_when_no_file(self, tmp_path):
        assert load_history(tmp_path) == []

    def test_round_trip(self, tmp_path):
        state = MetabolicState(qpr=1.5, cmr=2.0, tpv=0.5, gcr=0.9)
        save_snapshot(tmp_path, state, "s1")
        history = load_history(tmp_path)
        assert len(history) == 1
        assert history[0].session_id == "s1"
        assert history[0].indicators["qpr"] == 1.5
        assert history[0].indicators["gcr"] == 0.9

    def test_malformed_yaml_returns_empty(self, tmp_path):
        metabolic_dir = tmp_path / "ops" / "metabolic"
        metabolic_dir.mkdir(parents=True)
        (metabolic_dir / "history.yaml").write_text("{{invalid yaml")
        assert load_history(tmp_path) == []

    def test_non_list_returns_empty(self, tmp_path):
        metabolic_dir = tmp_path / "ops" / "metabolic"
        metabolic_dir.mkdir(parents=True)
        (metabolic_dir / "history.yaml").write_text("key: value\n")
        assert load_history(tmp_path) == []


class TestLoadLatest:
    def test_none_when_no_file(self, tmp_path):
        assert load_latest(tmp_path) is None

    def test_reads_latest(self, tmp_path):
        state = MetabolicState(qpr=3.0, tpv=1.0)
        save_snapshot(tmp_path, state, "latest-session")
        latest = load_latest(tmp_path)
        assert latest is not None
        assert latest.session_id == "latest-session"
        assert latest.indicators["qpr"] == 3.0


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------


class TestComputeTrends:
    def test_improving_qpr(self):
        """QPR decreasing = improving (lower is better)."""
        current = MetabolicState(qpr=1.0, cmr=1.0, tpv=1.0, hcr=50.0, gcr=0.9, ipr=0.5, vdr=80.0)
        history = [
            MetabolicSnapshot(
                timestamp="t1", session_id="s1",
                indicators={"qpr": 3.0, "cmr": 1.0, "tpv": 1.0, "hcr": 50.0, "gcr": 0.9, "ipr": 0.5, "vdr": 80.0},
            )
        ]
        trends = compute_trends(current, history)
        qpr_trend = next(t for t in trends if t.indicator == "qpr")
        assert qpr_trend.direction == "improving"
        assert qpr_trend.delta < 0

    def test_declining_tpv(self):
        """TPV decreasing = declining (higher is better)."""
        current = MetabolicState(qpr=1.0, cmr=1.0, tpv=0.1, hcr=50.0, gcr=0.9, ipr=0.5, vdr=80.0)
        history = [
            MetabolicSnapshot(
                timestamp="t1", session_id="s1",
                indicators={"qpr": 1.0, "cmr": 1.0, "tpv": 2.0, "hcr": 50.0, "gcr": 0.9, "ipr": 0.5, "vdr": 80.0},
            )
        ]
        trends = compute_trends(current, history)
        tpv_trend = next(t for t in trends if t.indicator == "tpv")
        assert tpv_trend.direction == "declining"

    def test_stable_when_unchanged(self):
        current = MetabolicState(qpr=1.0, cmr=1.0, tpv=1.0, hcr=50.0, gcr=0.9, ipr=0.5, vdr=80.0)
        history = [
            MetabolicSnapshot(
                timestamp="t1", session_id="s1",
                indicators={"qpr": 1.0, "cmr": 1.0, "tpv": 1.0, "hcr": 50.0, "gcr": 0.9, "ipr": 0.5, "vdr": 80.0},
            )
        ]
        trends = compute_trends(current, history)
        for t in trends:
            assert t.direction == "stable"

    def test_no_history_no_previous(self):
        current = MetabolicState(qpr=1.0)
        trends = compute_trends(current, [])
        for t in trends:
            assert t.previous is None
            assert t.delta is None
            assert t.direction == "stable"

    def test_rolling_averages(self):
        current = MetabolicState(qpr=2.0, cmr=1.0, tpv=1.0, hcr=50.0, gcr=0.9, ipr=0.5, vdr=80.0)
        history = [
            MetabolicSnapshot(
                timestamp=f"t{i}", session_id=f"s{i}",
                indicators={"qpr": float(i), "cmr": 1.0, "tpv": 1.0, "hcr": 50.0, "gcr": 0.9, "ipr": 0.5, "vdr": 80.0},
            )
            for i in range(10)
        ]
        trends = compute_trends(current, history)
        qpr_trend = next(t for t in trends if t.indicator == "qpr")
        assert qpr_trend.avg_7 is not None
        assert qpr_trend.avg_30 is not None


# ---------------------------------------------------------------------------
# Trend formatting
# ---------------------------------------------------------------------------


class TestFormatTrendLine:
    def test_non_stable_trends(self):
        trends = [
            MetabolicTrend(indicator="qpr", current=1.0, previous=3.0, delta=-2.0, direction="improving"),
            MetabolicTrend(indicator="cmr", current=2.0, previous=2.0, delta=0.0, direction="stable"),
            MetabolicTrend(indicator="tpv", current=0.5, previous=1.0, delta=-0.5, direction="declining"),
        ]
        line = format_trend_line(trends)
        assert "QPR improving" in line
        assert "TPV declining" in line
        assert "CMR" not in line

    def test_all_stable_empty(self):
        trends = [
            MetabolicTrend(indicator="qpr", current=1.0, direction="stable"),
        ]
        assert format_trend_line(trends) == ""

    def test_no_previous_excluded(self):
        trends = [
            MetabolicTrend(indicator="qpr", current=1.0, previous=None, direction="improving"),
        ]
        assert format_trend_line(trends) == ""
