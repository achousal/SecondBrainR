"""Tests for daemon skill-level backoff tracking."""

import json
import time

from engram_r._daemon_backoff import (
    read_backoff,
    record_failure,
    record_success,
    skill_in_backoff,
)


class TestReadBackoff:
    def test_missing_file(self, tmp_path):
        assert read_backoff(tmp_path / "nope.json") == {}

    def test_corrupt_file(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json at all")
        assert read_backoff(p) == {}

    def test_valid_file(self, tmp_path):
        p = tmp_path / "backoff.json"
        p.write_text(json.dumps({"tournament": {"consecutive_failures": 2}}))
        state = read_backoff(p)
        assert state["tournament"]["consecutive_failures"] == 2


class TestRecordFailure:
    def test_increments_count(self, tmp_path):
        p = tmp_path / "backoff.json"
        record_failure("tournament", p, threshold=3)
        state = read_backoff(p)
        assert state["tournament"]["consecutive_failures"] == 1
        assert "backoff_until" not in state["tournament"]

    def test_activates_at_threshold(self, tmp_path):
        p = tmp_path / "backoff.json"
        for _ in range(3):
            record_failure("tournament", p, threshold=3, initial_s=1800)
        state = read_backoff(p)
        assert state["tournament"]["consecutive_failures"] == 3
        assert "backoff_until" in state["tournament"]
        assert state["tournament"]["backoff_duration_s"] == 1800

    def test_escalation(self, tmp_path):
        p = tmp_path / "backoff.json"
        # 6 failures = 2x threshold -> 2x initial duration
        for _ in range(6):
            record_failure("tournament", p, threshold=3, initial_s=1800, max_s=7200)
        state = read_backoff(p)
        assert state["tournament"]["consecutive_failures"] == 6
        assert state["tournament"]["backoff_duration_s"] == 3600

    def test_cap_at_max(self, tmp_path):
        p = tmp_path / "backoff.json"
        # 12 failures = 4x threshold -> 4x initial = 7200, but max is 7200
        for _ in range(12):
            record_failure("tournament", p, threshold=3, initial_s=1800, max_s=7200)
        state = read_backoff(p)
        assert state["tournament"]["backoff_duration_s"] == 7200

    def test_independent_skills(self, tmp_path):
        p = tmp_path / "backoff.json"
        for _ in range(3):
            record_failure("tournament", p, threshold=3)
        record_failure("reflect", p, threshold=3)
        state = read_backoff(p)
        assert state["tournament"]["consecutive_failures"] == 3
        assert state["reflect"]["consecutive_failures"] == 1

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "sub" / "dir" / "backoff.json"
        record_failure("x", p, threshold=1)
        assert p.exists()


class TestRecordSuccess:
    def test_resets_counter(self, tmp_path):
        p = tmp_path / "backoff.json"
        for _ in range(5):
            record_failure("tournament", p, threshold=3)
        record_success("tournament", p)
        state = read_backoff(p)
        assert "tournament" not in state

    def test_noop_for_unknown_skill(self, tmp_path):
        p = tmp_path / "backoff.json"
        p.write_text("{}")
        record_success("nope", p)
        assert read_backoff(p) == {}

    def test_preserves_other_skills(self, tmp_path):
        p = tmp_path / "backoff.json"
        record_failure("a", p, threshold=1)
        record_failure("b", p, threshold=1)
        record_success("a", p)
        state = read_backoff(p)
        assert "a" not in state
        assert "b" in state


class TestSkillInBackoff:
    def test_no_state(self, tmp_path):
        p = tmp_path / "backoff.json"
        in_bo, remaining = skill_in_backoff("x", p)
        assert in_bo is False
        assert remaining == 0

    def test_not_in_backoff_below_threshold(self, tmp_path):
        p = tmp_path / "backoff.json"
        record_failure("x", p, threshold=3)
        in_bo, remaining = skill_in_backoff("x", p)
        assert in_bo is False

    def test_in_backoff_at_threshold(self, tmp_path):
        p = tmp_path / "backoff.json"
        for _ in range(3):
            record_failure("x", p, threshold=3, initial_s=600)
        in_bo, remaining = skill_in_backoff("x", p)
        assert in_bo is True
        assert remaining > 0
        assert remaining <= 600

    def test_backoff_expires(self, tmp_path):
        p = tmp_path / "backoff.json"
        # Manually set backoff_until to the past
        state = {
            "x": {
                "consecutive_failures": 3,
                "backoff_until": time.time() - 10,
                "backoff_duration_s": 600,
            }
        }
        p.write_text(json.dumps(state))
        in_bo, remaining = skill_in_backoff("x", p)
        assert in_bo is False
        assert remaining == 0
