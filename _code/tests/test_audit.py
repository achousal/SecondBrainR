"""Tests for the daemon audit log writer."""

import json

from engram_r.audit import (
    AuditEntry,
    AuditOutcome,
    RuleEvaluation,
    append_audit_entry,
    append_outcome,
)


class TestRuleEvaluation:
    def test_basic_fields(self):
        rule = RuleEvaluation(
            check_name="p1_research_cycle",
            triggered=True,
            candidate_skill="tournament",
            candidate_key="p1-tournament-goal-x",
        )
        assert rule.check_name == "p1_research_cycle"
        assert rule.triggered is True
        assert rule.candidate_skill == "tournament"

    def test_skip_reason_default(self):
        rule = RuleEvaluation(check_name="p2", triggered=False)
        assert rule.skip_reason == ""


class TestAuditEntry:
    def test_to_dict_basic(self):
        entry = AuditEntry(
            timestamp="2026-02-28T12:00:00+00:00",
            selected_task="p1-tournament-goal-x",
            selected_skill="tournament",
            selected_tier=1,
        )
        d = entry.to_dict()
        assert d["timestamp"] == "2026-02-28T12:00:00+00:00"
        assert d["selected_task"] == "p1-tournament-goal-x"
        assert d["selected_skill"] == "tournament"
        assert d["selected_tier"] == 1
        assert d["error"] == ""

    def test_to_dict_with_rules(self):
        rule = RuleEvaluation(check_name="p1", triggered=False, skip_reason="no_work")
        entry = AuditEntry(
            timestamp="2026-02-28T12:00:00+00:00",
            rules_evaluated=[rule],
        )
        d = entry.to_dict()
        assert len(d["rules_evaluated"]) == 1
        assert d["rules_evaluated"][0]["check_name"] == "p1"
        assert d["rules_evaluated"][0]["skip_reason"] == "no_work"

    def test_to_dict_serializable(self):
        entry = AuditEntry(
            timestamp="2026-02-28T12:00:00+00:00",
            vault_summary={"health_fails": 0, "inbox": 3},
            rules_evaluated=[
                RuleEvaluation(check_name="p1", triggered=False, skip_reason="no_work"),
                RuleEvaluation(
                    check_name="p2",
                    triggered=True,
                    candidate_skill="rethink",
                    candidate_key="p2-rethink",
                ),
            ],
        )
        # Must be JSON-serializable
        text = json.dumps(entry.to_dict())
        parsed = json.loads(text)
        assert parsed["vault_summary"]["inbox"] == 3


class TestAppendAuditEntry:
    def test_creates_file(self, tmp_path):
        log_path = tmp_path / "logs" / "audit.jsonl"
        entry = AuditEntry(timestamp="2026-02-28T12:00:00+00:00")
        append_audit_entry(entry, log_path)
        assert log_path.exists()
        line = log_path.read_text().strip()
        parsed = json.loads(line)
        assert parsed["timestamp"] == "2026-02-28T12:00:00+00:00"

    def test_appends_multiple(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        for i in range(3):
            entry = AuditEntry(
                timestamp=f"2026-02-28T12:0{i}:00+00:00",
                selected_task=f"task-{i}",
            )
            append_audit_entry(entry, log_path)
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
        for i, line in enumerate(lines):
            parsed = json.loads(line)
            assert parsed["selected_task"] == f"task-{i}"

    def test_valid_jsonl_format(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        entry = AuditEntry(
            timestamp="2026-02-28T12:00:00+00:00",
            rules_evaluated=[
                RuleEvaluation(check_name="p1", triggered=True, candidate_skill="x"),
            ],
        )
        append_audit_entry(entry, log_path)
        # Each line must be valid JSON
        for line in log_path.read_text().strip().split("\n"):
            json.loads(line)  # should not raise

    def test_no_temp_files_left(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        entry = AuditEntry(timestamp="2026-02-28T12:00:00+00:00")
        append_audit_entry(entry, log_path)
        remaining = list(tmp_path.glob(".audit-*"))
        assert remaining == []


class TestAuditEntryType:
    def test_default_type_is_selection(self):
        entry = AuditEntry(timestamp="2026-02-28T12:00:00+00:00")
        assert entry.type == "selection"

    def test_type_in_serialized_dict(self):
        entry = AuditEntry(timestamp="2026-02-28T12:00:00+00:00")
        d = entry.to_dict()
        assert d["type"] == "selection"

    def test_type_in_jsonl_output(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        entry = AuditEntry(timestamp="2026-02-28T12:00:00+00:00")
        append_audit_entry(entry, log_path)
        parsed = json.loads(log_path.read_text().strip())
        assert parsed["type"] == "selection"


class TestAuditOutcome:
    def test_basic_fields(self):
        outcome = AuditOutcome(
            timestamp="2026-02-28T12:05:00+00:00",
            task_key="p1-tournament-goal-x",
            skill="tournament",
            outcome="success",
            duration_seconds=120,
            vault_summary_before={"inbox": 3},
            vault_summary_after={"inbox": 2},
            changed_keys=["inbox"],
        )
        assert outcome.type == "outcome"
        assert outcome.outcome == "success"
        assert outcome.changed_keys == ["inbox"]

    def test_to_dict(self):
        outcome = AuditOutcome(
            timestamp="2026-02-28T12:05:00+00:00",
            task_key="task-1",
            skill="reduce",
            outcome="no_change",
            duration_seconds=45,
        )
        d = outcome.to_dict()
        assert d["type"] == "outcome"
        assert d["task_key"] == "task-1"
        assert d["duration_seconds"] == 45

    def test_serializable(self):
        outcome = AuditOutcome(
            timestamp="2026-02-28T12:05:00+00:00",
            task_key="task-1",
            skill="reduce",
            outcome="success",
            duration_seconds=60,
            vault_summary_before={"inbox": 3, "queue_backlog": 5},
            vault_summary_after={"inbox": 3, "queue_backlog": 4},
            changed_keys=["queue_backlog"],
        )
        text = json.dumps(outcome.to_dict())
        parsed = json.loads(text)
        assert parsed["changed_keys"] == ["queue_backlog"]


class TestAppendOutcome:
    def test_creates_file(self, tmp_path):
        log_path = tmp_path / "logs" / "audit.jsonl"
        outcome = AuditOutcome(
            timestamp="2026-02-28T12:05:00+00:00",
            task_key="task-1",
            skill="reduce",
            outcome="success",
            duration_seconds=60,
        )
        append_outcome(outcome, log_path)
        assert log_path.exists()
        parsed = json.loads(log_path.read_text().strip())
        assert parsed["type"] == "outcome"
        assert parsed["task_key"] == "task-1"

    def test_appends_to_existing(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        # Write a selection entry first
        entry = AuditEntry(timestamp="2026-02-28T12:00:00+00:00")
        append_audit_entry(entry, log_path)
        # Then an outcome
        outcome = AuditOutcome(
            timestamp="2026-02-28T12:05:00+00:00",
            task_key="task-1",
            skill="reduce",
            outcome="success",
            duration_seconds=60,
        )
        append_outcome(outcome, log_path)
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["type"] == "selection"
        assert json.loads(lines[1])["type"] == "outcome"

    def test_no_temp_files_left(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        outcome = AuditOutcome(
            timestamp="2026-02-28T12:05:00+00:00",
            task_key="task-1",
            skill="reduce",
            outcome="no_change",
            duration_seconds=0,
        )
        append_outcome(outcome, log_path)
        remaining = list(tmp_path.glob(".audit-*"))
        assert remaining == []
