"""Tests for Slack skill router -- permissions, queue I/O, intent parsing."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engram_r.slack_skill_router import (
    SKILL_AUTH_MATRIX,
    SKILL_SAFETY_TIERS,
    SLACK_ALLOWED_SKILLS,
    SLACK_READONLY_SKILLS,
    QueueEntry,
    check_permission,
    check_slack_queue,
    complete_task,
    detect_explicit_command,
    extract_skill_intent,
    mark_queue_entry_running,
    queue_request,
    read_queue,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """Create a minimal vault with daemon directory."""
    (tmp_path / "ops" / "daemon").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Constants integrity tests
# ---------------------------------------------------------------------------


class TestConstants:
    def test_readonly_skills_subset_of_allowed(self) -> None:
        assert SLACK_READONLY_SKILLS <= SLACK_ALLOWED_SKILLS

    def test_all_allowed_skills_have_safety_tier(self) -> None:
        for skill in SLACK_ALLOWED_SKILLS:
            assert skill in SKILL_SAFETY_TIERS, f"Missing tier for {skill}"

    def test_safety_tiers_valid_values(self) -> None:
        valid = {"read", "maintenance", "mutative"}
        for skill, tier in SKILL_SAFETY_TIERS.items():
            assert tier in valid, f"Invalid tier {tier!r} for {skill}"

    def test_readonly_skills_are_read_tier(self) -> None:
        for skill in SLACK_READONLY_SKILLS:
            assert SKILL_SAFETY_TIERS[skill] == "read"

    def test_owner_has_full_access(self) -> None:
        assert SKILL_AUTH_MATRIX["owner"] == SLACK_ALLOWED_SKILLS

    def test_public_subset_of_allowed(self) -> None:
        assert SKILL_AUTH_MATRIX["public"] <= SKILL_AUTH_MATRIX["allowed"]

    def test_allowed_subset_of_owner(self) -> None:
        assert SKILL_AUTH_MATRIX["allowed"] <= SKILL_AUTH_MATRIX["owner"]


# ---------------------------------------------------------------------------
# Permission check tests
# ---------------------------------------------------------------------------


class TestCheckPermission:
    def test_owner_can_run_mutative(self) -> None:
        ok, reason = check_permission("reduce", "owner")
        assert ok is True
        assert reason == ""

    def test_owner_can_run_readonly(self) -> None:
        ok, reason = check_permission("stats", "owner")
        assert ok is True

    def test_allowed_can_run_readonly(self) -> None:
        ok, reason = check_permission("stats", "allowed")
        assert ok is True

    def test_allowed_cannot_run_mutative(self) -> None:
        ok, reason = check_permission("reduce", "allowed")
        assert ok is False
        assert "does not permit" in reason

    def test_public_can_run_stats(self) -> None:
        ok, reason = check_permission("stats", "public")
        assert ok is True

    def test_public_cannot_run_validate(self) -> None:
        ok, reason = check_permission("validate", "public")
        assert ok is False

    def test_unknown_skill_denied(self) -> None:
        ok, reason = check_permission("hack-the-planet", "owner")
        assert ok is False
        assert "not available" in reason

    def test_unknown_auth_level_denied(self) -> None:
        ok, reason = check_permission("stats", "superadmin")
        assert ok is False


# ---------------------------------------------------------------------------
# Command parsing tests
# ---------------------------------------------------------------------------


class TestDetectExplicitCommand:
    def test_basic_command(self) -> None:
        skill, args = detect_explicit_command("/stats")
        assert skill == "stats"
        assert args == ""

    def test_command_with_args(self) -> None:
        skill, args = detect_explicit_command("/reduce --quarantine")
        assert skill == "reduce"
        assert args == "--quarantine"

    def test_command_case_insensitive(self) -> None:
        skill, args = detect_explicit_command("/Stats")
        assert skill == "stats"

    def test_leading_whitespace(self) -> None:
        skill, args = detect_explicit_command("  /next")
        assert skill == "next"

    def test_not_a_command(self) -> None:
        skill, args = detect_explicit_command("run stats please")
        assert skill is None
        assert args == ""

    def test_unknown_command_no_match(self) -> None:
        skill, args = detect_explicit_command("/deploy")
        assert skill is None

    def test_command_in_middle_of_text(self) -> None:
        skill, args = detect_explicit_command("can you run /stats for me")
        assert skill is None  # Only matches at start

    def test_hyphenated_command(self) -> None:
        skill, args = detect_explicit_command("/meta-review")
        assert skill == "meta-review"


# ---------------------------------------------------------------------------
# Intent extraction tests
# ---------------------------------------------------------------------------


class TestExtractSkillIntent:
    def test_basic_intent(self) -> None:
        response = (
            "I'll check the vault stats for you.\n"
            "<skill-intent>skill: stats</skill-intent>"
        )
        skill, args, cleaned = extract_skill_intent(response)
        assert skill == "stats"
        assert args is None
        assert "skill-intent" not in cleaned
        assert "check the vault" in cleaned

    def test_intent_with_args(self) -> None:
        response = (
            "Running a tournament now.\n"
            "<skill-intent>skill: tournament args: --goal test-analysis</skill-intent>"
        )
        skill, args, cleaned = extract_skill_intent(response)
        assert skill == "tournament"
        assert args == "--goal test-analysis"

    def test_no_intent(self) -> None:
        response = "Just a normal response."
        skill, args, cleaned = extract_skill_intent(response)
        assert skill is None
        assert args is None
        assert cleaned == response

    def test_strips_leading_slash(self) -> None:
        response = "<skill-intent>skill: /stats</skill-intent>"
        skill, _, _ = extract_skill_intent(response)
        assert skill == "stats"

    def test_cleaned_response_trimmed(self) -> None:
        response = "<skill-intent>skill: next</skill-intent>"
        _, _, cleaned = extract_skill_intent(response)
        assert cleaned == ""


# ---------------------------------------------------------------------------
# Queue I/O tests
# ---------------------------------------------------------------------------


class TestQueueIO:
    def test_read_empty_queue(self, vault: Path) -> None:
        entries = read_queue(vault)
        assert entries == []

    def test_queue_request_creates_entry(self, vault: Path) -> None:
        entry_id = queue_request(
            vault, "stats", "", "U_USER", "owner", "C1", "123.456"
        )
        assert len(entry_id) == 12

        entries = read_queue(vault)
        assert len(entries) == 1
        assert entries[0].skill == "stats"
        assert entries[0].requested_by == "U_USER"
        assert entries[0].status == "pending"

    def test_multiple_queue_entries(self, vault: Path) -> None:
        queue_request(vault, "stats", "", "U1", "owner", "C1", "1.0")
        queue_request(vault, "next", "", "U2", "public", "C1", "2.0")
        entries = read_queue(vault)
        assert len(entries) == 2

    def test_mark_running(self, vault: Path) -> None:
        entry_id = queue_request(
            vault, "stats", "", "U1", "owner", "C1", "1.0"
        )
        mark_queue_entry_running(vault, entry_id)
        entries = read_queue(vault)
        assert entries[0].status == "running"

    def test_complete_task_success(self, vault: Path) -> None:
        entry_id = queue_request(
            vault, "stats", "", "U1", "owner", "C1", "1.0"
        )
        mark_queue_entry_running(vault, entry_id)

        with patch("engram_r.slack_skill_router._post_completion_reply"):
            complete_task(vault, f"slack-{entry_id}", "success", 5)

        entries = read_queue(vault)
        assert entries[0].status == "completed"
        assert entries[0].completed_at != ""
        assert "completed" in entries[0].result_summary

    def test_complete_task_failed(self, vault: Path) -> None:
        entry_id = queue_request(
            vault, "reduce", "--quarantine", "U1", "owner", "C1", "1.0"
        )
        with patch("engram_r.slack_skill_router._post_completion_reply"):
            complete_task(vault, f"slack-{entry_id}", "failed", 30)

        entries = read_queue(vault)
        assert entries[0].status == "failed"
        assert "failed" in entries[0].result_summary

    def test_complete_task_reads_result_file(self, vault: Path) -> None:
        entry_id = queue_request(
            vault, "stats", "", "U1", "owner", "C1", "1.0"
        )
        results_dir = vault / "ops" / "daemon" / "slack-results"
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / f"{entry_id}.md").write_text("Vault: 42 notes, 7 hypotheses")

        with patch("engram_r.slack_skill_router._post_completion_reply"):
            complete_task(vault, f"slack-{entry_id}", "success", 3)

        entries = read_queue(vault)
        assert "42 notes" in entries[0].result_summary

    def test_complete_task_missing_entry(self, vault: Path) -> None:
        # Should not raise
        with patch("engram_r.slack_skill_router._post_completion_reply"):
            complete_task(vault, "slack-nonexistent", "success", 1)

    def test_queue_prunes_old_entries(self, vault: Path) -> None:
        queue_request(vault, "stats", "", "U1", "owner", "C1", "1.0")
        # Manually mark as completed with a very old timestamp on disk
        entries = read_queue(vault)
        entries[0].status = "completed"
        entries[0].completed_at = "2020-01-01T00:00:00+00:00"
        qp = vault / "ops" / "daemon" / "slack-queue.json"
        qp.write_text(json.dumps([e.to_dict() for e in entries]))

        # Add a new entry -- triggers pruning on write
        queue_request(vault, "next", "", "U2", "public", "C1", "2.0")

        # Re-read -- old entry should be pruned
        entries = read_queue(vault)
        assert len(entries) == 1
        assert entries[0].skill == "next"

    def test_corrupt_queue_file(self, vault: Path) -> None:
        qp = vault / "ops" / "daemon" / "slack-queue.json"
        qp.write_text("not valid json {{{")
        entries = read_queue(vault)
        assert entries == []


# ---------------------------------------------------------------------------
# check_slack_queue (daemon integration) tests
# ---------------------------------------------------------------------------


class TestCheckSlackQueue:
    def test_returns_none_when_empty(self, vault: Path) -> None:
        result = check_slack_queue(vault)
        assert result is None

    def test_finds_pending_entry(self, vault: Path) -> None:
        queue_request(vault, "stats", "", "U1", "owner", "C1", "1.0")
        result = check_slack_queue(vault)
        assert result is not None
        assert result["entry"].skill == "stats"

    def test_skips_running_entry(self, vault: Path) -> None:
        entry_id = queue_request(
            vault, "stats", "", "U1", "owner", "C1", "1.0"
        )
        mark_queue_entry_running(vault, entry_id)
        result = check_slack_queue(vault)
        assert result is None

    def test_picks_first_pending(self, vault: Path) -> None:
        queue_request(vault, "stats", "", "U1", "owner", "C1", "1.0")
        mark_queue_entry_running(
            vault, read_queue(vault)[0].id
        )
        queue_request(vault, "next", "", "U2", "public", "C1", "2.0")
        result = check_slack_queue(vault)
        assert result["entry"].skill == "next"


# ---------------------------------------------------------------------------
# QueueEntry serialization tests
# ---------------------------------------------------------------------------


class TestQueueEntry:
    def test_roundtrip(self) -> None:
        entry = QueueEntry(
            id="abc123",
            skill="stats",
            args="--verbose",
            requested_by="U_USER",
            auth_level="owner",
            channel="C1",
            thread_ts="123.456",
            requested_at="2026-03-01T00:00:00+00:00",
            status="pending",
        )
        d = entry.to_dict()
        restored = QueueEntry.from_dict(d)
        assert restored.id == entry.id
        assert restored.skill == entry.skill
        assert restored.args == entry.args
        assert restored.status == entry.status

    def test_from_dict_defaults(self) -> None:
        entry = QueueEntry.from_dict({})
        assert entry.status == "pending"
        assert entry.result_summary == ""
