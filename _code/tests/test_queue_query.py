"""Tests for engram_r.queue_query."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from engram_r.queue_query import (
    DEFAULT_MAX_RETRIES,
    PIPELINE_ORDER,
    advance_task,
    fail_task,
    get_actionable,
    get_alerts,
    get_batch_status,
    get_siblings,
    get_stats,
    get_tasks_detail,
    retry_task,
    write_queue_atomic,
)


@pytest.fixture()
def sample_queue():
    return [
        {
            "id": "extract-001",
            "type": "extract",
            "status": "done",
            "current_phase": "reduce",
            "completed_phases": [],
            "completed": "2026-01-01T00:00:00Z",
        },
        {
            "id": "claim-010",
            "type": "claim",
            "status": "pending",
            "target": "alpha claim",
            "batch": "batch-a",
            "file": "batch-a-010.md",
            "current_phase": "reflect",
            "completed_phases": ["create"],
        },
        {
            "id": "claim-011",
            "type": "claim",
            "status": "pending",
            "target": "beta claim",
            "batch": "batch-a",
            "file": "batch-a-011.md",
            "current_phase": "reflect",
            "completed_phases": ["create"],
        },
        {
            "id": "claim-012",
            "type": "claim",
            "status": "pending",
            "target": "gamma claim",
            "batch": "batch-a",
            "file": "batch-a-012.md",
            "current_phase": "reweave",
            "completed_phases": ["create", "reflect"],
        },
        {
            "id": "claim-020",
            "type": "claim",
            "status": "pending",
            "target": "delta claim",
            "batch": "batch-b",
            "file": "batch-b-020.md",
            "current_phase": "create",
            "completed_phases": [],
        },
        {
            "id": "enrich-030",
            "type": "enrichment",
            "status": "pending",
            "target": "epsilon claim",
            "batch": "batch-c",
            "file": "batch-c-030.md",
            "current_phase": "enrich",
            "completed_phases": [],
        },
    ]


class TestGetStats:
    def test_counts_by_status(self, sample_queue):
        stats = get_stats(sample_queue)
        assert stats["total"] == 6
        assert stats["by_status"]["done"] == 1
        assert stats["by_status"]["pending"] == 5

    def test_pending_by_phase(self, sample_queue):
        stats = get_stats(sample_queue)
        assert stats["pending_by_phase"]["reflect"] == 2
        assert stats["pending_by_phase"]["reweave"] == 1
        assert stats["pending_by_phase"]["create"] == 1
        assert stats["pending_by_phase"]["enrich"] == 1

    def test_failed_count(self, sample_queue):
        sample_queue[1]["status"] = "failed"
        stats = get_stats(sample_queue)
        assert stats["failed_count"] == 1
        assert stats["by_status"]["failed"] == 1

    def test_failed_count_zero_when_none(self, sample_queue):
        stats = get_stats(sample_queue)
        assert stats["failed_count"] == 0


class TestGetActionable:
    def test_phase_gate_blocks_reflect_when_create_pending(self, sample_queue):
        result = get_actionable(sample_queue)
        actionable_ids = {t["id"] for t in result["actionable"]}
        # create and enrich are pending, so reflect and reweave should be blocked
        assert "claim-020" in actionable_ids  # create phase -- not blocked
        assert "enrich-030" in actionable_ids  # enrich phase -- not blocked
        assert "claim-010" not in actionable_ids  # reflect -- blocked by create/enrich
        assert "claim-011" not in actionable_ids  # reflect -- blocked
        assert "claim-012" not in actionable_ids  # reweave -- blocked

    def test_phase_gate_blocks_reweave_when_reflect_pending(self):
        tasks = [
            {
                "id": "c1",
                "type": "claim",
                "status": "pending",
                "target": "t1",
                "batch": "b",
                "current_phase": "reflect",
                "completed_phases": ["create"],
            },
            {
                "id": "c2",
                "type": "claim",
                "status": "pending",
                "target": "t2",
                "batch": "b",
                "current_phase": "reweave",
                "completed_phases": ["create", "reflect"],
            },
        ]
        result = get_actionable(tasks)
        actionable_ids = {t["id"] for t in result["actionable"]}
        assert "c1" in actionable_ids
        assert "c2" not in actionable_ids
        assert "reweave" in result["blocked"]

    def test_reduce_and_verify_never_blocked(self):
        tasks = [
            {
                "id": "e1",
                "type": "extract",
                "status": "pending",
                "current_phase": "reduce",
            },
            {
                "id": "v1",
                "type": "claim",
                "status": "pending",
                "target": "t",
                "current_phase": "verify",
                "completed_phases": ["create", "reflect", "reweave"],
            },
            {
                "id": "c1",
                "type": "claim",
                "status": "pending",
                "target": "t2",
                "current_phase": "create",
                "completed_phases": [],
            },
        ]
        result = get_actionable(tasks)
        actionable_ids = {t["id"] for t in result["actionable"]}
        assert "e1" in actionable_ids
        assert "v1" in actionable_ids
        assert "c1" in actionable_ids

    def test_phase_filter(self, sample_queue):
        result = get_actionable(sample_queue, phase_filter="create")
        assert all(t["current_phase"] == "create" for t in result["actionable"])

    def test_batch_filter(self, sample_queue):
        result = get_actionable(sample_queue, batch_filter="batch-b")
        assert all(t["batch"] == "batch-b" for t in result["actionable"])

    def test_limit(self, sample_queue):
        result = get_actionable(sample_queue, limit=1)
        assert len(result["actionable"]) == 1

    def test_pipeline_ordering(self):
        tasks = [
            {
                "id": "r1",
                "type": "claim",
                "status": "pending",
                "target": "t1",
                "current_phase": "verify",
                "completed_phases": ["create", "reflect", "reweave"],
            },
            {
                "id": "r2",
                "type": "extract",
                "status": "pending",
                "current_phase": "reduce",
            },
        ]
        result = get_actionable(tasks)
        phases = [t["current_phase"] for t in result["actionable"]]
        assert phases == ["reduce", "verify"]

    def test_blocked_summary(self, sample_queue):
        result = get_actionable(sample_queue)
        assert "reflect" in result["blocked"]
        assert "reweave" in result["blocked"]
        assert result["blocked"]["reflect"]["count"] == 2
        assert result["blocked"]["reweave"]["count"] == 1


class TestGetSiblings:
    def test_returns_siblings_with_create_completed(self, sample_queue):
        siblings = get_siblings(sample_queue, "claim-010")
        sib_ids = {s["id"] for s in siblings}
        assert "claim-011" in sib_ids
        assert "claim-012" in sib_ids
        assert "claim-010" not in sib_ids  # self excluded

    def test_no_siblings_different_batch(self, sample_queue):
        siblings = get_siblings(sample_queue, "claim-020")
        assert siblings == []

    def test_unknown_task_returns_empty(self, sample_queue):
        assert get_siblings(sample_queue, "nonexistent") == []


class TestGetTasksDetail:
    def test_includes_siblings(self, sample_queue):
        result = get_tasks_detail(
            sample_queue, phase_filter="create", limit=1, include_siblings=True
        )
        assert result["count"] == 1
        task = result["tasks"][0]
        assert task["id"] == "claim-020"
        assert "siblings" in task

    def test_no_siblings_when_not_requested(self, sample_queue):
        result = get_tasks_detail(
            sample_queue, phase_filter="create", limit=1, include_siblings=False
        )
        task = result["tasks"][0]
        assert "siblings" not in task


class TestPhaseGateWithFailed:
    """Failed tasks must not block the phase gate."""

    def test_failed_create_does_not_block_reflect(self):
        tasks = [
            {
                "id": "c1",
                "type": "claim",
                "status": "failed",
                "target": "t1",
                "batch": "b",
                "current_phase": "create",
                "completed_phases": [],
            },
            {
                "id": "c2",
                "type": "claim",
                "status": "pending",
                "target": "t2",
                "batch": "b",
                "current_phase": "reflect",
                "completed_phases": ["create"],
            },
        ]
        result = get_actionable(tasks)
        actionable_ids = {t["id"] for t in result["actionable"]}
        assert "c2" in actionable_ids
        assert "reflect" not in result["blocked"]

    def test_failed_enrich_does_not_block_reflect(self):
        tasks = [
            {
                "id": "e1",
                "type": "enrichment",
                "status": "failed",
                "target": "t1",
                "batch": "b",
                "current_phase": "enrich",
                "completed_phases": [],
            },
            {
                "id": "c1",
                "type": "claim",
                "status": "pending",
                "target": "t2",
                "batch": "b",
                "current_phase": "reflect",
                "completed_phases": ["create"],
            },
        ]
        result = get_actionable(tasks)
        actionable_ids = {t["id"] for t in result["actionable"]}
        assert "c1" in actionable_ids

    def test_failed_tasks_not_in_actionable(self):
        tasks = [
            {
                "id": "c1",
                "type": "claim",
                "status": "failed",
                "target": "t1",
                "current_phase": "create",
                "completed_phases": [],
            },
        ]
        result = get_actionable(tasks)
        assert result["actionable_count"] == 0


class TestFailTask:
    def test_marks_task_failed(self):
        tasks = [
            {"id": "c1", "status": "pending", "current_phase": "create"},
        ]
        result = fail_task(tasks, "c1", reason="zero-claim extraction")
        assert result["action"] == "failed"
        assert tasks[0]["status"] == "failed"
        assert tasks[0]["fail_reason"] == "zero-claim extraction"
        assert tasks[0]["retry_count"] == 0
        assert "failed_at" in tasks[0]

    def test_preserves_existing_retry_count(self):
        tasks = [
            {"id": "c1", "status": "pending", "current_phase": "create",
             "retry_count": 3},
        ]
        result = fail_task(tasks, "c1")
        assert tasks[0]["retry_count"] == 3

    def test_fail_nonexistent_task(self):
        result = fail_task([], "nope")
        assert result["action"] == "error"


class TestRetryTask:
    def test_retries_failed_task(self):
        tasks = [
            {"id": "c1", "status": "failed", "current_phase": "create",
             "retry_count": 0, "fail_reason": "oops", "failed_at": "t"},
        ]
        result = retry_task(tasks, "c1")
        assert result["action"] == "retried"
        assert result["retry_count"] == 1
        assert tasks[0]["status"] == "pending"
        assert "fail_reason" not in tasks[0]
        assert "failed_at" not in tasks[0]

    def test_retry_increments_count(self):
        tasks = [
            {"id": "c1", "status": "failed", "current_phase": "create",
             "retry_count": 4},
        ]
        result = retry_task(tasks, "c1")
        assert tasks[0]["retry_count"] == 5

    def test_retry_refuses_at_limit(self):
        tasks = [
            {"id": "c1", "status": "failed", "current_phase": "create",
             "retry_count": DEFAULT_MAX_RETRIES},
        ]
        result = retry_task(tasks, "c1")
        assert result["action"] == "error"
        assert "retry limit" in result["message"]
        assert tasks[0]["status"] == "failed"

    def test_retry_pending_task_errors(self):
        tasks = [
            {"id": "c1", "status": "pending", "current_phase": "create"},
        ]
        result = retry_task(tasks, "c1")
        assert result["action"] == "error"

    def test_retry_nonexistent_task(self):
        result = retry_task([], "nope")
        assert result["action"] == "error"


class TestAdvanceTask:
    def test_advance_claim_create_to_reflect(self):
        tasks = [
            {"id": "c1", "type": "claim", "status": "pending",
             "current_phase": "create", "completed_phases": []},
        ]
        result = advance_task(tasks, "c1")
        assert result["action"] == "advanced"
        assert result["from_phase"] == "create"
        assert result["to_phase"] == "reflect"
        assert tasks[0]["current_phase"] == "reflect"
        assert "create" in tasks[0]["completed_phases"]

    def test_advance_claim_verify_marks_done(self):
        tasks = [
            {"id": "c1", "type": "claim", "status": "pending",
             "current_phase": "verify",
             "completed_phases": ["create", "reflect", "reweave"]},
        ]
        result = advance_task(tasks, "c1")
        assert result["action"] == "done"
        assert tasks[0]["status"] == "done"
        assert tasks[0]["current_phase"] is None
        assert "completed" in tasks[0]

    def test_advance_enrichment_follows_enrichment_order(self):
        tasks = [
            {"id": "e1", "type": "enrichment", "status": "pending",
             "current_phase": "enrich", "completed_phases": []},
        ]
        result = advance_task(tasks, "e1")
        assert result["to_phase"] == "reflect"

    def test_advance_extract_marks_done(self):
        tasks = [
            {"id": "x1", "type": "extract", "status": "pending",
             "current_phase": "reduce", "completed_phases": []},
        ]
        result = advance_task(tasks, "x1")
        assert result["action"] == "done"

    def test_advance_with_explicit_phase(self):
        tasks = [
            {"id": "c1", "type": "claim", "status": "pending",
             "current_phase": "create", "completed_phases": []},
        ]
        result = advance_task(tasks, "c1", next_phase="verify")
        assert result["to_phase"] == "verify"
        assert tasks[0]["current_phase"] == "verify"

    def test_advance_done_task_errors(self):
        tasks = [
            {"id": "c1", "type": "claim", "status": "done",
             "current_phase": None, "completed_phases": ["create"]},
        ]
        result = advance_task(tasks, "c1")
        assert result["action"] == "error"


class TestGetAlerts:
    def test_surfaces_failed_tasks(self):
        tasks = [
            {"id": "c1", "status": "failed", "target": "t1",
             "current_phase": "create", "fail_reason": "oops",
             "retry_count": 2, "failed_at": "2026-01-01"},
            {"id": "c2", "status": "pending", "current_phase": "reflect"},
        ]
        alerts = get_alerts(tasks)
        assert alerts["failed_count"] == 1
        assert alerts["failed"][0]["id"] == "c1"

    def test_identifies_tasks_at_retry_limit(self):
        tasks = [
            {"id": "c1", "status": "failed", "target": "t1",
             "current_phase": "create", "retry_count": DEFAULT_MAX_RETRIES},
        ]
        alerts = get_alerts(tasks)
        assert alerts["at_retry_limit_count"] == 1


class TestGetBatchStatus:
    def test_counts_by_batch(self, sample_queue):
        result = get_batch_status(sample_queue)
        assert "batch-a" in result["batches"]
        assert result["batches"]["batch-a"]["pending"] == 3

    def test_check_complete_finds_done_batches(self):
        tasks = [
            {"id": "c1", "type": "claim", "status": "done",
             "batch": "b1", "target": "t1"},
            {"id": "c2", "type": "claim", "status": "done",
             "batch": "b1", "target": "t2"},
            {"id": "c3", "type": "claim", "status": "pending",
             "batch": "b2", "target": "t3"},
        ]
        result = get_batch_status(tasks, check_complete=True)
        assert "b1" in result["complete_batches"]
        assert "b2" not in result["complete_batches"]

    def test_failed_tasks_prevent_batch_completion(self):
        tasks = [
            {"id": "c1", "type": "claim", "status": "done",
             "batch": "b1", "target": "t1"},
            {"id": "c2", "type": "claim", "status": "failed",
             "batch": "b1", "target": "t2"},
        ]
        result = get_batch_status(tasks, check_complete=True)
        assert result["complete_count"] == 0


class TestWriteQueueAtomic:
    def test_writes_and_reads_back(self, tmp_path):
        queue_file = tmp_path / "queue.json"
        data = [{"id": "c1", "status": "pending"}]
        write_queue_atomic(data, queue_file)
        loaded = json.loads(queue_file.read_text())
        assert loaded == data

    def test_creates_parent_dirs(self, tmp_path):
        queue_file = tmp_path / "ops" / "queue" / "queue.json"
        write_queue_atomic([{"id": "c1"}], queue_file)
        assert queue_file.exists()

    def test_overwrites_existing(self, tmp_path):
        queue_file = tmp_path / "queue.json"
        write_queue_atomic([{"id": "old"}], queue_file)
        write_queue_atomic([{"id": "new"}], queue_file)
        loaded = json.loads(queue_file.read_text())
        assert loaded[0]["id"] == "new"
