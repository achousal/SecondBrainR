"""Tests for metabolic indicators -- daemon self-regulation metrics."""

import json
from datetime import UTC, datetime, timedelta

from engram_r.metabolic_indicators import (
    MetabolicState,
    classify_alarms,
    compute_cmr,
    compute_gcr,
    compute_hcr,
    compute_ipr,
    compute_metabolic_state,
    compute_qpr,
    compute_tpv,
    compute_vdr,
)

# ---------------------------------------------------------------------------
# QPR (Queue Pressure Ratio)
# ---------------------------------------------------------------------------


class TestComputeQPR:
    def test_with_recent_completions(self):
        """QPR = backlog / daily_rate."""
        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {"id": "t1", "status": "pending"},
                {"id": "t2", "status": "pending"},
                {"id": "t3", "status": "pending"},
                {
                    "id": "t4",
                    "status": "done",
                    "completed": (now - timedelta(days=1)).isoformat(),
                },
                {
                    "id": "t5",
                    "status": "done",
                    "completed": (now - timedelta(days=2)).isoformat(),
                },
                {
                    "id": "t6",
                    "status": "done",
                    "completed": (now - timedelta(days=3)).isoformat(),
                },
                {
                    "id": "t7",
                    "status": "done",
                    "completed": (now - timedelta(days=6)).isoformat(),
                },
            ]
        }
        # 3 pending, 4 completed in 7 days -> rate = 4/7 -> QPR = 3 / (4/7) = 5.25
        qpr = compute_qpr(queue_data=queue_data, lookback_days=7)
        assert abs(qpr - 5.25) < 0.01

    def test_no_completions_uses_floor_rate(self):
        """When no completions, use floor rate of 0.1."""
        queue_data = {
            "tasks": [
                {"id": "t1", "status": "pending"},
                {"id": "t2", "status": "pending"},
            ]
        }
        qpr = compute_qpr(queue_data=queue_data, lookback_days=7)
        # 2 pending / 0.1 = 20
        assert abs(qpr - 20.0) < 0.01

    def test_all_done_zero_backlog(self):
        """QPR is 0 when no pending tasks."""
        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "completed": (now - timedelta(days=1)).isoformat(),
                },
            ]
        }
        assert compute_qpr(queue_data=queue_data) == 0.0

    def test_empty_queue(self):
        assert compute_qpr(queue_data={"tasks": []}) == 0.0

    def test_none_queue_no_path(self):
        assert compute_qpr(queue_data=None, queue_path=None) == 0.0

    def test_reads_from_disk(self, tmp_path):
        """Reads queue.json from disk when queue_data is None."""
        now = datetime.now(UTC)
        queue_file = tmp_path / "queue.json"
        queue_file.write_text(
            json.dumps(
                {
                    "tasks": [
                        {"id": "t1", "status": "pending"},
                        {
                            "id": "t2",
                            "status": "done",
                            "completed": now.isoformat(),
                        },
                    ]
                }
            )
        )
        qpr = compute_qpr(queue_path=queue_file, lookback_days=7)
        # 1 pending, 1 completed in 7d -> rate = 1/7 -> QPR = 1 / (1/7) = 7
        assert abs(qpr - 7.0) < 0.01

    def test_old_completions_excluded(self):
        """Completions outside lookback window are not counted."""
        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {"id": "t1", "status": "pending"},
                {
                    "id": "t2",
                    "status": "done",
                    "completed": (now - timedelta(days=30)).isoformat(),
                },
            ]
        }
        # 1 pending, 0 recent completions -> floor rate 0.1 -> QPR = 10
        qpr = compute_qpr(queue_data=queue_data, lookback_days=7)
        assert abs(qpr - 10.0) < 0.01


# ---------------------------------------------------------------------------
# VDR (Verification Debt Ratio)
# ---------------------------------------------------------------------------


class TestComputeVDR:
    def test_all_agent_verified(self, tmp_path):
        """100% debt when all are agent-verified."""
        notes = tmp_path / "notes"
        notes.mkdir()
        for i in range(5):
            (notes / f"note-{i}.md").write_text(
                '---\nverified_by: "agent"\n---\nContent\n'
            )
        assert compute_vdr(notes) == 100.0

    def test_mixed_verification(self, tmp_path):
        """Partial human verification."""
        notes = tmp_path / "notes"
        notes.mkdir()
        for i in range(3):
            (notes / f"agent-{i}.md").write_text(
                '---\nverified_by: "agent"\n---\nContent\n'
            )
        for i in range(2):
            (notes / f"human-{i}.md").write_text(
                '---\nverified_by: "human"\n---\nContent\n'
            )
        # 3/5 = 60% debt
        assert abs(compute_vdr(notes) - 60.0) < 0.01

    def test_all_human_verified(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        for i in range(3):
            (notes / f"note-{i}.md").write_text(
                '---\nverified_by: "human"\n---\nContent\n'
            )
        assert compute_vdr(notes) == 0.0

    def test_empty_dir(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        assert compute_vdr(notes) == 0.0

    def test_missing_dir(self, tmp_path):
        assert compute_vdr(tmp_path / "nonexistent") == 0.0

    def test_skips_index(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        (notes / "_index.md").write_text("---\n---\nIndex\n")
        (notes / "note.md").write_text('---\nverified_by: "agent"\n---\n')
        assert compute_vdr(notes) == 100.0  # Only 1 note (index excluded)


# ---------------------------------------------------------------------------
# CMR (Creation:Maintenance Ratio)
# ---------------------------------------------------------------------------


class TestComputeCMR:
    def test_balanced_ratio(self, tmp_path):
        """When creation and maintenance are equal, CMR = 1."""
        notes = tmp_path / "notes"
        notes.mkdir()
        today = datetime.now(UTC).date().isoformat()
        for i in range(3):
            (notes / f"note-{i}.md").write_text(
                f'---\ncreated: "{today}"\n---\nContent\n'
            )

        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {
                    "id": f"claim-{i}",
                    "type": "claim",
                    "status": "done",
                    "completed_phases": ["create", "reflect", "reweave"],
                    "completed": (now - timedelta(days=1)).isoformat(),
                }
                for i in range(3)
            ]
        }
        cmr = compute_cmr(notes, queue_data=queue_data, lookback_days=7)
        assert abs(cmr - 1.0) < 0.01

    def test_creation_dominant(self, tmp_path):
        """High creation, no maintenance -> ratio = creation/1."""
        notes = tmp_path / "notes"
        notes.mkdir()
        today = datetime.now(UTC).date().isoformat()
        for i in range(15):
            (notes / f"note-{i}.md").write_text(
                f'---\ncreated: "{today}"\n---\nContent\n'
            )
        cmr = compute_cmr(notes, queue_data={"tasks": []}, lookback_days=7)
        assert cmr == 15.0  # 15 / max(0,1) = 15

    def test_maintenance_only(self, tmp_path):
        """No recent creation, some maintenance -> CMR = 1/N."""
        notes = tmp_path / "notes"
        notes.mkdir()
        # Old note (created more than 7 days ago, old ctime via fallback)
        old = notes / "old-note.md"
        old.write_text('---\ncreated: "2020-01-01"\n---\nContent\n')

        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {
                    "id": "claim-1",
                    "type": "claim",
                    "status": "done",
                    "completed_phases": ["create", "reflect"],
                    "completed": (now - timedelta(days=1)).isoformat(),
                }
            ]
        }
        cmr = compute_cmr(notes, queue_data=queue_data, lookback_days=7)
        # 0 recent creation -> max(0,1)=1, 1 maintenance -> 1/1 = 1
        assert abs(cmr - 1.0) < 0.01


# ---------------------------------------------------------------------------
# HCR (Hypothesis Conversion Rate)
# ---------------------------------------------------------------------------


class TestComputeHCR:
    def _write_hyp(self, d, name, status):
        (d / f"{name}.md").write_text(
            f'---\ntype: "hypothesis"\nstatus: "{status}"\n---\nContent\n'
        )

    def test_low_conversion(self, tmp_path):
        hyp_dir = tmp_path / "hypotheses"
        hyp_dir.mkdir()
        self._write_hyp(hyp_dir, "h1", "active")
        self._write_hyp(hyp_dir, "h2", "active")
        self._write_hyp(hyp_dir, "h3", "active")
        self._write_hyp(hyp_dir, "h4", "active")
        self._write_hyp(hyp_dir, "h5", "tested-positive")
        # 1/5 = 20%
        hcr, total = compute_hcr(hyp_dir)
        assert abs(hcr - 20.0) < 0.01
        assert total == 5

    def test_counts_all_converted_statuses(self, tmp_path):
        hyp_dir = tmp_path / "hypotheses"
        hyp_dir.mkdir()
        self._write_hyp(hyp_dir, "h1", "tested-positive")
        self._write_hyp(hyp_dir, "h2", "tested-negative")
        self._write_hyp(hyp_dir, "h3", "executing")
        self._write_hyp(hyp_dir, "h4", "sap-written")
        self._write_hyp(hyp_dir, "h5", "active")
        # 4/5 = 80%
        hcr, total = compute_hcr(hyp_dir)
        assert abs(hcr - 80.0) < 0.01
        assert total == 5

    def test_empty_dir(self, tmp_path):
        hyp_dir = tmp_path / "hypotheses"
        hyp_dir.mkdir()
        hcr, total = compute_hcr(hyp_dir)
        assert hcr == 0.0
        assert total == 0

    def test_missing_dir(self, tmp_path):
        hcr, total = compute_hcr(tmp_path / "nonexistent")
        assert hcr == 0.0
        assert total == 0

    def test_skips_non_hypothesis(self, tmp_path):
        hyp_dir = tmp_path / "hypotheses"
        hyp_dir.mkdir()
        self._write_hyp(hyp_dir, "h1", "active")
        (hyp_dir / "readme.md").write_text('---\ntype: "note"\n---\nNot a hypothesis\n')
        (hyp_dir / "_index.md").write_text("---\n---\nIndex\n")
        hcr, total = compute_hcr(hyp_dir)
        assert abs(hcr - 0.0) < 0.01  # 0/1 = 0%
        assert total == 1


# ---------------------------------------------------------------------------
# TPV (Throughput Velocity)
# ---------------------------------------------------------------------------


class TestComputeTPV:
    def test_with_completions(self):
        """TPV = completions / lookback_days."""
        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "completed": (now - timedelta(days=1)).isoformat(),
                },
                {
                    "id": "t2",
                    "status": "done",
                    "completed": (now - timedelta(days=2)).isoformat(),
                },
                {
                    "id": "t3",
                    "status": "done",
                    "completed": (now - timedelta(days=3)).isoformat(),
                },
                {"id": "t4", "status": "pending"},
            ]
        }
        tpv = compute_tpv(queue_data=queue_data, lookback_days=7)
        # 3 completions in 7 days = 3/7 ~= 0.4286
        assert abs(tpv - 3 / 7) < 0.01

    def test_no_completions(self):
        queue_data = {"tasks": [{"id": "t1", "status": "pending"}]}
        assert compute_tpv(queue_data=queue_data, lookback_days=7) == 0.0

    def test_high_throughput(self):
        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {
                    "id": f"t{i}",
                    "status": "done",
                    "completed": (now - timedelta(days=i % 7)).isoformat(),
                }
                for i in range(14)
            ]
        }
        tpv = compute_tpv(queue_data=queue_data, lookback_days=7)
        assert tpv == 2.0  # 14 / 7

    def test_empty_queue(self):
        assert compute_tpv(queue_data={"tasks": []}) == 0.0

    def test_none_queue_no_path(self):
        assert compute_tpv(queue_data=None, queue_path=None) == 0.0

    def test_old_completions_excluded(self):
        now = datetime.now(UTC)
        queue_data = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "completed": (now - timedelta(days=30)).isoformat(),
                },
            ]
        }
        assert compute_tpv(queue_data=queue_data, lookback_days=7) == 0.0


# ---------------------------------------------------------------------------
# GCR (Graph Connectivity Ratio)
# ---------------------------------------------------------------------------


class TestComputeGCR:
    def test_no_orphans(self):
        assert compute_gcr(orphan_count=0, total_notes=10) == 1.0

    def test_all_orphans(self):
        assert compute_gcr(orphan_count=10, total_notes=10) == 0.0

    def test_mixed(self):
        # 3 orphans out of 10 = GCR 0.7
        assert abs(compute_gcr(orphan_count=3, total_notes=10) - 0.7) < 0.01

    def test_empty_vault(self):
        assert compute_gcr(orphan_count=0, total_notes=0) == 1.0


# ---------------------------------------------------------------------------
# IPR (Inbox Pressure Ratio)
# ---------------------------------------------------------------------------


class TestComputeIPR:
    def test_balanced(self, tmp_path):
        """Equal inbox and processing rates -> IPR ~1.0."""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        notes = tmp_path / "notes"
        notes.mkdir()
        today = datetime.now(UTC).date().isoformat()
        for i in range(3):
            (inbox / f"source-{i}.md").write_text("# Source\n")
            (notes / f"note-{i}.md").write_text(
                f'---\ncreated: "{today}"\n---\n'
            )
        ipr = compute_ipr(inbox, notes, lookback_days=7)
        # Both rates are 3/7, but processing rate has floor of 0.1
        # inbox_rate = 3/7, processing_rate = 3/7 -> IPR = 1.0
        assert abs(ipr - 1.0) < 0.5  # Approximate due to ctime variance

    def test_empty_dirs(self, tmp_path):
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        notes = tmp_path / "notes"
        notes.mkdir()
        assert compute_ipr(inbox, notes) == 0.0

    def test_overflow(self, tmp_path):
        """Many inbox items, no processing -> high IPR."""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        notes = tmp_path / "notes"
        notes.mkdir()
        for i in range(10):
            (inbox / f"source-{i}.md").write_text("# Source\n")
        ipr = compute_ipr(inbox, notes, lookback_days=7)
        # 10/7 rate / 0.1 floor = ~14.3
        assert ipr > 3.0

    def test_processing_dominant(self, tmp_path):
        """No inbox items, many processed -> IPR = 0."""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        notes = tmp_path / "notes"
        notes.mkdir()
        today = datetime.now(UTC).date().isoformat()
        for i in range(5):
            (notes / f"note-{i}.md").write_text(
                f'---\ncreated: "{today}"\n---\n'
            )
        assert compute_ipr(inbox, notes, lookback_days=7) == 0.0


# ---------------------------------------------------------------------------
# Alarm classification
# ---------------------------------------------------------------------------


class TestClassifyAlarms:
    def test_multiple_alarms(self):
        state = MetabolicState(
            qpr=5.0, cmr=15.0, tpv=0.0, hcr=10.0, gcr=0.1, ipr=5.0,
            total_notes=10, total_hypotheses=5,
        )
        alarms = classify_alarms(state)
        assert "qpr_critical" in alarms
        assert "cmr_hot" in alarms
        assert "tpv_stalled" in alarms
        assert "hcr_low" in alarms
        assert "gcr_fragmented" in alarms
        assert "ipr_overflow" in alarms

    def test_no_alarms_healthy(self):
        state = MetabolicState(
            qpr=1.0, cmr=2.0, tpv=1.0, hcr=50.0, gcr=0.8, ipr=1.0,
            total_notes=10, total_hypotheses=5,
        )
        alarms = classify_alarms(state)
        assert alarms == []

    def test_qpr_only(self):
        state = MetabolicState(
            qpr=4.0, cmr=2.0, tpv=1.0, hcr=50.0, gcr=0.8, ipr=1.0,
            total_notes=10, total_hypotheses=5,
        )
        alarms = classify_alarms(state)
        assert alarms == ["qpr_critical"]

    def test_custom_thresholds(self):
        state = MetabolicState(
            qpr=2.0, cmr=5.0, tpv=1.0, hcr=50.0, gcr=0.8, ipr=1.0,
            total_notes=10, total_hypotheses=5,
        )
        # Default thresholds: no alarms
        assert classify_alarms(state) == []
        # Lower thresholds: alarms
        alarms = classify_alarms(state, qpr_critical=1.0, cmr_hot=3.0)
        assert "qpr_critical" in alarms
        assert "cmr_hot" in alarms

    def test_vdr_not_alarmed(self):
        """VDR is informational only -- never triggers alarms."""
        state = MetabolicState(
            vdr=99.9, qpr=1.0, cmr=2.0, tpv=1.0, hcr=50.0, gcr=0.8, ipr=1.0,
            total_notes=10, total_hypotheses=5,
        )
        assert classify_alarms(state) == []

    def test_tpv_not_alarmed_on_new_vault(self):
        """TPV at 0 should NOT alarm when vault has < 5 notes (new vault)."""
        state = MetabolicState(tpv=0.0, total_notes=2)
        alarms = classify_alarms(state)
        assert "tpv_stalled" not in alarms

    def test_tpv_alarmed_on_established_vault(self):
        """TPV at 0 SHOULD alarm when vault has >= 5 notes."""
        state = MetabolicState(tpv=0.0, total_notes=10)
        alarms = classify_alarms(state)
        assert "tpv_stalled" in alarms

    def test_hcr_not_alarmed_below_gate(self):
        """HCR should NOT alarm when < 3 hypotheses (gate)."""
        state = MetabolicState(hcr=0.0, total_hypotheses=2)
        alarms = classify_alarms(state)
        assert "hcr_low" not in alarms

    def test_hcr_alarmed_above_gate(self):
        """HCR SHOULD alarm when >= 3 hypotheses and HCR is low."""
        state = MetabolicState(hcr=5.0, total_hypotheses=5)
        alarms = classify_alarms(state)
        assert "hcr_low" in alarms

    def test_gcr_alarmed_when_fragmented(self):
        state = MetabolicState(gcr=0.2, total_notes=10)
        alarms = classify_alarms(state)
        assert "gcr_fragmented" in alarms

    def test_gcr_not_alarmed_when_connected(self):
        state = MetabolicState(gcr=0.8, total_notes=10)
        alarms = classify_alarms(state)
        assert "gcr_fragmented" not in alarms

    def test_ipr_alarmed_when_overflow(self):
        state = MetabolicState(ipr=5.0)
        alarms = classify_alarms(state)
        assert "ipr_overflow" in alarms


# ---------------------------------------------------------------------------
# End-to-end integration
# ---------------------------------------------------------------------------


class TestComputeMetabolicState:
    def test_end_to_end(self, tmp_path):
        """Integration test with a temp vault."""
        # Set up vault structure
        notes = tmp_path / "notes"
        notes.mkdir()
        hyps = tmp_path / "_research" / "hypotheses"
        hyps.mkdir(parents=True)
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)

        # Create some notes
        today = datetime.now(UTC).date().isoformat()
        for i in range(5):
            (notes / f"note-{i}.md").write_text(
                f'---\nverified_by: "agent"\ncreated: "{today}"\n---\n'
            )

        # Create some hypotheses
        for i in range(4):
            (hyps / f"h-{i}.md").write_text(
                '---\ntype: "hypothesis"\nstatus: "active"\n---\n'
            )
        (hyps / "h-4.md").write_text(
            '---\ntype: "hypothesis"\nstatus: "tested-positive"\n---\n'
        )

        # Create queue
        now = datetime.now(UTC)
        queue = {
            "tasks": [
                {"id": "t1", "status": "pending"},
                {"id": "t2", "status": "pending"},
                {
                    "id": "t3",
                    "type": "claim",
                    "status": "done",
                    "completed_phases": ["create", "reflect"],
                    "completed": (now - timedelta(days=1)).isoformat(),
                },
            ]
        }
        (queue_dir / "queue.json").write_text(json.dumps(queue))

        state = compute_metabolic_state(tmp_path)

        # QPR: 2 pending, 1 recent completion -> rate=1/7, QPR=2/(1/7)=14
        assert state.qpr > 0
        # VDR: 5 agent, 0 human -> 100%
        assert state.vdr == 100.0
        # HCR: 1/5 = 20%
        assert abs(state.hcr - 20.0) < 0.01
        # TPV: 1 completion in 7 days = 1/7
        assert state.tpv > 0
        # GCR: defaults to 1.0 when orphan_count not passed
        assert state.gcr == 1.0
        # total_notes and total_hypotheses
        assert state.total_notes == 5
        assert state.total_hypotheses == 5
        # Alarms should include qpr_critical (14 > 3)
        assert "qpr_critical" in state.alarm_keys

    def test_end_to_end_with_orphans(self, tmp_path):
        """Integration test passing orphan_count."""
        notes = tmp_path / "notes"
        notes.mkdir()
        hyps = tmp_path / "_research" / "hypotheses"
        hyps.mkdir(parents=True)
        (tmp_path / "inbox").mkdir()
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "queue.json").write_text('{"tasks": []}')

        for i in range(10):
            (notes / f"note-{i}.md").write_text(
                f'---\nverified_by: "agent"\ncreated: "2020-01-01"\n---\n'
            )

        state = compute_metabolic_state(tmp_path, orphan_count=8)
        # GCR = 1 - (8/10) = 0.2
        assert abs(state.gcr - 0.2) < 0.01
        assert "gcr_fragmented" in state.alarm_keys

    def test_empty_vault_no_alarms(self, tmp_path):
        """Empty vault should produce zero values and no alarms."""
        (tmp_path / "notes").mkdir()
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)
        (tmp_path / "inbox").mkdir()
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "queue.json").write_text('{"tasks": []}')

        state = compute_metabolic_state(tmp_path)
        assert state.qpr == 0.0
        assert state.cmr == 1.0  # max(0,1)/max(0,1)
        assert state.tpv == 0.0
        assert state.hcr == 0.0
        assert state.gcr == 1.0  # No orphan data -> default 1.0
        assert state.ipr == 0.0
        assert state.vdr == 0.0
        assert state.total_notes == 0
        assert state.total_hypotheses == 0
        # No alarms on empty vault
        assert state.alarm_keys == []


# ---------------------------------------------------------------------------
# Bare-list queue format (regression for queue.json as JSON array)
# ---------------------------------------------------------------------------


class TestBareListQueueFormat:
    """queue.json can be a bare JSON array instead of {"tasks": [...]}."""

    def test_qpr_accepts_bare_list(self):
        now = datetime.now(UTC)
        queue_data = [
            {"id": "t1", "status": "pending"},
            {
                "id": "t2",
                "status": "done",
                "completed": (now - timedelta(days=1)).isoformat(),
            },
        ]
        qpr = compute_qpr(queue_data=queue_data, lookback_days=7)
        # 1 pending, 1 completion in 7d -> rate=1/7 -> QPR=7
        assert abs(qpr - 7.0) < 0.01

    def test_tpv_accepts_bare_list(self):
        now = datetime.now(UTC)
        queue_data = [
            {
                "id": "t1",
                "status": "done",
                "completed": (now - timedelta(days=1)).isoformat(),
            },
            {
                "id": "t2",
                "status": "done",
                "completed": (now - timedelta(days=2)).isoformat(),
            },
        ]
        tpv = compute_tpv(queue_data=queue_data, lookback_days=7)
        assert abs(tpv - 2 / 7) < 0.01

    def test_cmr_accepts_bare_list(self, tmp_path):
        notes = tmp_path / "notes"
        notes.mkdir()
        now = datetime.now(UTC)
        queue_data = [
            {
                "id": "claim-1",
                "type": "claim",
                "status": "done",
                "completed_phases": ["create", "reflect"],
                "completed": (now - timedelta(days=1)).isoformat(),
            },
        ]
        cmr = compute_cmr(notes, queue_data=queue_data, lookback_days=7)
        assert cmr >= 0

    def test_reads_bare_list_from_disk(self, tmp_path):
        """compute_qpr reads a bare-list queue.json from disk correctly."""
        now = datetime.now(UTC)
        queue_file = tmp_path / "queue.json"
        queue_file.write_text(
            json.dumps(
                [
                    {"id": "t1", "status": "pending"},
                    {
                        "id": "t2",
                        "status": "done",
                        "completed": now.isoformat(),
                    },
                ]
            )
        )
        qpr = compute_qpr(queue_path=queue_file, lookback_days=7)
        assert abs(qpr - 7.0) < 0.01

    def test_end_to_end_bare_list_queue(self, tmp_path):
        """compute_metabolic_state works with a bare-list queue.json on disk."""
        notes = tmp_path / "notes"
        notes.mkdir()
        (tmp_path / "_research" / "hypotheses").mkdir(parents=True)
        (tmp_path / "inbox").mkdir()
        queue_dir = tmp_path / "ops" / "queue"
        queue_dir.mkdir(parents=True)

        now = datetime.now(UTC)
        (queue_dir / "queue.json").write_text(
            json.dumps(
                [
                    {"id": "t1", "status": "pending"},
                    {
                        "id": "t2",
                        "status": "done",
                        "completed": (now - timedelta(days=1)).isoformat(),
                    },
                ]
            )
        )
        state = compute_metabolic_state(tmp_path)
        assert state.qpr > 0
        assert state.tpv > 0
