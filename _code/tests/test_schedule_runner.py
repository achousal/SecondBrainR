"""Tests for engram_r.schedule_runner."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
import yaml

from engram_r.daemon_config import ScheduleEntry
from engram_r.schedule_runner import (
    ExperimentBrief,
    HypothesisBrief,
    LabMember,
    ProjectSummary,
    ReminderBrief,
    ScheduledMessage,
    _classify_project,
    _extract_wikilink_stems,
    _match_reminders_to_project,
    _read_frontmatter,
    _scan_lab_members,
    build_project_updates,
    build_scheduled_messages,
    execute_schedule,
    schedule_is_due,
    schedule_marker_key,
)

# ---------------------------------------------------------------------------
# schedule_is_due
# ---------------------------------------------------------------------------


class TestScheduleIsDue:
    def test_disabled_entry(self):
        entry = ScheduleEntry(name="test", enabled=False, cadence="daily", hour=9)
        now = datetime.datetime(2026, 2, 23, 10, 0)
        assert schedule_is_due(entry, now) is False

    def test_daily_before_hour(self):
        entry = ScheduleEntry(name="test", cadence="daily", hour=9)
        now = datetime.datetime(2026, 2, 23, 8, 30)
        assert schedule_is_due(entry, now) is False

    def test_daily_at_hour(self):
        entry = ScheduleEntry(name="test", cadence="daily", hour=9)
        now = datetime.datetime(2026, 2, 23, 9, 0)
        assert schedule_is_due(entry, now) is True

    def test_daily_after_hour(self):
        entry = ScheduleEntry(name="test", cadence="daily", hour=9)
        now = datetime.datetime(2026, 2, 23, 14, 0)
        assert schedule_is_due(entry, now) is True

    def test_weekly_correct_day(self):
        entry = ScheduleEntry(name="test", cadence="weekly", day="monday", hour=9)
        # 2026-02-23 is a Monday
        now = datetime.datetime(2026, 2, 23, 10, 0)
        assert schedule_is_due(entry, now) is True

    def test_weekly_wrong_day(self):
        entry = ScheduleEntry(name="test", cadence="weekly", day="monday", hour=9)
        # 2026-02-24 is a Tuesday
        now = datetime.datetime(2026, 2, 24, 10, 0)
        assert schedule_is_due(entry, now) is False

    def test_weekly_case_insensitive(self):
        entry = ScheduleEntry(name="test", cadence="weekly", day="Monday", hour=9)
        now = datetime.datetime(2026, 2, 23, 10, 0)
        assert schedule_is_due(entry, now) is True

    def test_monthly_correct_day(self):
        entry = ScheduleEntry(name="test", cadence="monthly", day="15", hour=9)
        now = datetime.datetime(2026, 3, 15, 10, 0)
        assert schedule_is_due(entry, now) is True

    def test_monthly_wrong_day(self):
        entry = ScheduleEntry(name="test", cadence="monthly", day="15", hour=9)
        now = datetime.datetime(2026, 3, 14, 10, 0)
        assert schedule_is_due(entry, now) is False

    def test_unknown_cadence(self):
        entry = ScheduleEntry(name="test", cadence="biweekly", hour=9)
        now = datetime.datetime(2026, 2, 23, 10, 0)
        assert schedule_is_due(entry, now) is False


# ---------------------------------------------------------------------------
# schedule_marker_key
# ---------------------------------------------------------------------------


class TestScheduleMarkerKey:
    def test_daily(self):
        entry = ScheduleEntry(name="exp-deadline", cadence="daily")
        now = datetime.datetime(2026, 2, 23)
        assert schedule_marker_key(entry, now) == "sched-exp-deadline-2026-02-23"

    def test_weekly(self):
        entry = ScheduleEntry(name="weekly-project-update", cadence="weekly")
        now = datetime.datetime(2026, 2, 23)
        key = schedule_marker_key(entry, now)
        assert key.startswith("sched-weekly-project-update-2026-W")
        # 2026-02-23 is in ISO week 9
        assert "W09" in key

    def test_monthly(self):
        entry = ScheduleEntry(name="monthly-digest", cadence="monthly")
        now = datetime.datetime(2026, 3, 15)
        assert schedule_marker_key(entry, now) == "sched-monthly-digest-2026-03"


# ---------------------------------------------------------------------------
# _extract_wikilink_stems
# ---------------------------------------------------------------------------


class TestExtractWikilinkStems:
    def test_list_of_wikilinks(self):
        items = ["[[EXP-001-sample]]", "[[EXP-002-treatment]]"]
        assert _extract_wikilink_stems(items) == ["EXP-001-sample", "EXP-002-treatment"]

    def test_single_string(self):
        assert _extract_wikilink_stems("[[H-TEST-004b]]") == ["H-TEST-004b"]

    def test_no_wikilinks(self):
        assert _extract_wikilink_stems(["plain text"]) == []

    def test_piped_wikilinks(self):
        assert _extract_wikilink_stems(["[[target|display]]"]) == ["target"]


# ---------------------------------------------------------------------------
# _scan_lab_members
# ---------------------------------------------------------------------------


class TestScanLabMembers:
    def test_reads_members_from_index(self, tmp_path: Path):
        index = tmp_path / "_index.md"
        fm = {
            "type": "lab",
            "members": [
                {"name": "Alice", "slack_id": "U111", "role": "lead"},
                {"name": "Bob", "slack_id": "U222", "role": "contributor"},
            ],
        }
        index.write_text(f"---\n{yaml.dump(fm)}---\n# Lab\n")
        members = _scan_lab_members(index)
        assert len(members) == 2
        assert members[0].name == "Alice"
        assert members[0].role == "lead"
        assert members[1].slack_id == "U222"

    def test_missing_members_field(self, tmp_path: Path):
        index = tmp_path / "_index.md"
        index.write_text("---\ntype: lab\n---\n# Lab\n")
        assert _scan_lab_members(index) == []

    def test_skips_incomplete_entries(self, tmp_path: Path):
        index = tmp_path / "_index.md"
        fm = {
            "type": "lab",
            "members": [
                {"name": "Alice"},  # missing slack_id
                {"name": "Bob", "slack_id": "U222"},
            ],
        }
        index.write_text(f"---\n{yaml.dump(fm)}---\n# Lab\n")
        members = _scan_lab_members(index)
        assert len(members) == 1
        assert members[0].name == "Bob"

    def test_default_role(self, tmp_path: Path):
        index = tmp_path / "_index.md"
        fm = {
            "type": "lab",
            "members": [{"name": "Carol", "slack_id": "U333"}],
        }
        index.write_text(f"---\n{yaml.dump(fm)}---\n# Lab\n")
        members = _scan_lab_members(index)
        assert members[0].role == "contributor"


# ---------------------------------------------------------------------------
# _classify_project
# ---------------------------------------------------------------------------


class TestClassifyProject:
    def test_maintenance_status(self):
        proj = ProjectSummary(tag="x", title="X", status="maintenance")
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "maintenance"

    def test_archived_status(self):
        proj = ProjectSummary(tag="x", title="X", status="archived")
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "maintenance"

    def test_null_experiment_outcome(self):
        proj = ProjectSummary(
            tag="x",
            title="X",
            status="active",
            experiments=[
                ExperimentBrief(id="E1", status="completed", outcome="completed-null")
            ],
        )
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "needs_attention"

    def test_designed_experiment(self):
        proj = ProjectSummary(
            tag="x",
            title="X",
            status="active",
            experiments=[ExperimentBrief(id="E1", status="designed")],
        )
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "needs_attention"

    def test_negative_hypothesis(self):
        proj = ProjectSummary(
            tag="x",
            title="X",
            status="active",
            hypotheses=[
                HypothesisBrief(
                    id="H1", status="tested", empirical_outcome="tested-negative"
                )
            ],
        )
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "needs_attention"

    def test_upcoming_reminder(self):
        proj = ProjectSummary(
            tag="x",
            title="X",
            status="active",
            reminders=[ReminderBrief(date="2026-02-28", text="Do something")],
        )
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "needs_attention"

    def test_distant_reminder_is_on_track(self):
        proj = ProjectSummary(
            tag="x",
            title="X",
            status="active",
            reminders=[ReminderBrief(date="2026-06-01", text="Far away")],
        )
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "on_track"

    def test_clean_active_project(self):
        proj = ProjectSummary(tag="x", title="X", status="active")
        assert _classify_project(proj, datetime.date(2026, 2, 23)) == "on_track"


# ---------------------------------------------------------------------------
# _match_reminders_to_project
# ---------------------------------------------------------------------------


class TestMatchReminders:
    def test_matches_by_experiment_id(self):
        reminders = [
            ReminderBrief(date="2026-03-01", text="Submit EXP-001 registration"),
            ReminderBrief(date="2026-03-15", text="Unrelated task"),
        ]
        fm = {
            "project_tag": "ad-classification",
            "linked_experiments": ["[[EXP-001-sample-analysis]]"],
            "linked_hypotheses": [],
        }
        matched = _match_reminders_to_project(reminders, fm)
        assert len(matched) == 1
        assert "EXP-001" in matched[0].text

    def test_matches_by_project_tag(self):
        reminders = [
            ReminderBrief(date="2026-03-01", text="Check proj-treatment counts"),
        ]
        fm = {
            "project_tag": "proj-treatment",
            "linked_experiments": [],
            "linked_hypotheses": [],
        }
        matched = _match_reminders_to_project(reminders, fm)
        assert len(matched) == 1


# ---------------------------------------------------------------------------
# build_project_updates (integration with vault fixture)
# ---------------------------------------------------------------------------


def _create_vault_fixture(tmp_path: Path) -> Path:
    """Create a minimal vault structure for testing."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # ops/reminders.md
    ops = vault / "ops"
    ops.mkdir()
    (ops / "reminders.md").write_text(
        "# Reminders\n\n"
        "## Execution\n\n"
        "- [ ] 2026-03-01: Submit EXP-001 registration\n"
        "- [ ] 2026-06-01: Far future task\n"
    )

    # projects/testlab/_index.md
    projects = vault / "projects" / "testlab"
    projects.mkdir(parents=True)
    lab_fm = {
        "type": "lab",
        "lab_slug": "testlab",
        "pi": "Dr. Test",
        "members": [
            {"name": "Alice Lead", "slack_id": "U111", "role": "lead"},
            {"name": "Bob Observer", "slack_id": "U222", "role": "observer"},
        ],
    }
    (projects / "_index.md").write_text(f"---\n{yaml.dump(lab_fm)}---\n# Test Lab\n")

    # Active project with experiment
    proj1_fm = {
        "type": "project",
        "project_tag": "proj-alpha",
        "title": "Project Alpha",
        "status": "active",
        "linked_experiments": ["[[EXP-001-test]]"],
        "linked_hypotheses": ["[[H-TEST-001]]"],
        "linked_goals": [],
    }
    (projects / "proj-alpha.md").write_text(
        f"---\n{yaml.dump(proj1_fm)}---\nAlpha project.\n"
    )

    # Maintenance project
    proj2_fm = {
        "type": "project",
        "project_tag": "proj-beta",
        "title": "Project Beta",
        "status": "maintenance",
        "linked_experiments": [],
        "linked_hypotheses": [],
        "linked_goals": [],
    }
    (projects / "proj-beta.md").write_text(
        f"---\n{yaml.dump(proj2_fm)}---\nBeta project.\n"
    )

    # Clean active project (on track)
    proj3_fm = {
        "type": "project",
        "project_tag": "proj-gamma",
        "title": "Project Gamma",
        "status": "active",
        "linked_experiments": [],
        "linked_hypotheses": [],
        "linked_goals": [],
    }
    (projects / "proj-gamma.md").write_text(
        f"---\n{yaml.dump(proj3_fm)}---\nGamma project.\n"
    )

    # Experiment note
    exp_dir = vault / "_research" / "experiments"
    exp_dir.mkdir(parents=True)
    exp_fm = {
        "type": "experiment",
        "id": "EXP-001",
        "status": "designed",
        "outcome": "",
        "linked_hypotheses": ["[[H-TEST-001]]"],
    }
    (exp_dir / "EXP-001-test.md").write_text(
        f"---\n{yaml.dump(exp_fm)}---\n# EXP-001\n\n"
        "| Step | Status |\n|---|---|\n| Access request | not started |\n"
    )

    # Hypothesis note
    hyp_dir = vault / "_research" / "hypotheses"
    hyp_dir.mkdir(parents=True)
    hyp_fm = {
        "type": "hypothesis",
        "id": "H-TEST-001",
        "status": "proposed",
        "elo": 1200,
        "empirical_outcome": "",
    }
    (hyp_dir / "H-TEST-001.md").write_text(
        f"---\n{yaml.dump(hyp_fm)}---\n## Statement\n"
    )

    return vault


class TestBuildProjectUpdates:
    def test_produces_lab_updates(self, tmp_path: Path):
        vault = _create_vault_fixture(tmp_path)
        entry = ScheduleEntry(name="test-update", type="project_update", scope="active")
        updates = build_project_updates(vault, entry)
        assert len(updates) == 1

        lab = updates[0]
        assert "Test" in lab.lab_name
        assert len(lab.members) == 2
        # proj-alpha should be needs_attention (designed experiment)
        assert len(lab.needs_attention) == 1
        assert lab.needs_attention[0].tag == "proj-alpha"
        # proj-gamma should be on_track
        assert len(lab.on_track) == 1
        assert lab.on_track[0].tag == "proj-gamma"
        # proj-beta should be maintenance
        assert len(lab.maintenance) == 1
        assert lab.maintenance[0].tag == "proj-beta"

    def test_skips_labs_without_members(self, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "ops").mkdir()
        (vault / "ops" / "reminders.md").write_text("# Reminders\n")
        lab_dir = vault / "projects" / "empty_lab"
        lab_dir.mkdir(parents=True)
        (lab_dir / "_index.md").write_text("---\ntype: lab\n---\n# Empty\n")
        entry = ScheduleEntry(name="test", type="project_update", scope="active")
        assert build_project_updates(vault, entry) == []

    def test_experiment_brief_loaded(self, tmp_path: Path):
        vault = _create_vault_fixture(tmp_path)
        entry = ScheduleEntry(name="test", type="project_update", scope="active")
        updates = build_project_updates(vault, entry)
        proj = updates[0].needs_attention[0]
        assert len(proj.experiments) == 1
        assert proj.experiments[0].id == "EXP-001"
        assert proj.experiments[0].status == "designed"

    def test_hypothesis_brief_loaded(self, tmp_path: Path):
        vault = _create_vault_fixture(tmp_path)
        entry = ScheduleEntry(name="test", type="project_update", scope="active")
        updates = build_project_updates(vault, entry)
        proj = updates[0].needs_attention[0]
        assert len(proj.hypotheses) == 1
        assert proj.hypotheses[0].id == "H-TEST-001"
        assert proj.hypotheses[0].elo == 1200


# ---------------------------------------------------------------------------
# build_scheduled_messages
# ---------------------------------------------------------------------------


class TestBuildScheduledMessages:
    def test_unknown_type_returns_empty(self, tmp_path: Path):
        vault = _create_vault_fixture(tmp_path)
        entry = ScheduleEntry(name="test", type="nonexistent")
        assert build_scheduled_messages(vault, entry) == []

    def test_project_update_produces_messages(self, tmp_path: Path):
        vault = _create_vault_fixture(tmp_path)
        entry = ScheduleEntry(name="test", type="project_update", scope="active")
        messages = build_scheduled_messages(vault, entry)
        # One message per member (2 members)
        assert len(messages) == 2
        assert messages[0].recipient_name == "Alice Lead"
        assert messages[0].recipient_role == "lead"
        assert messages[1].recipient_name == "Bob Observer"
        assert messages[1].recipient_role == "observer"
        # Both should have non-empty blocks
        assert len(messages[0].blocks) > 0
        assert len(messages[1].blocks) > 0


# ---------------------------------------------------------------------------
# deliver_messages
# ---------------------------------------------------------------------------


class TestDeliverMessages:
    def test_returns_zero_when_slack_not_configured(self, monkeypatch):
        monkeypatch.setattr(
            "engram_r.slack_client.SlackClient.from_env_optional",
            classmethod(lambda cls: None),
        )
        msg = ScheduledMessage(
            recipient_slack_id="U111",
            recipient_name="Alice",
            recipient_role="lead",
            lab="Test Lab",
            text="Hello",
        )
        # Import locally so monkeypatch applies
        from engram_r.schedule_runner import deliver_messages as _deliver

        assert _deliver([msg]) == 0

    def test_sends_dms_and_returns_count(self, monkeypatch):
        class FakeClient:
            def open_dm(self, slack_id):
                return f"D-{slack_id}"

            def post_message(self, text, channel, blocks=None):
                pass

        monkeypatch.setattr(
            "engram_r.slack_client.SlackClient.from_env_optional",
            classmethod(lambda cls: FakeClient()),
        )
        messages = [
            ScheduledMessage(
                recipient_slack_id="U111",
                recipient_name="Alice",
                recipient_role="lead",
                lab="Lab",
                text="msg1",
            ),
            ScheduledMessage(
                recipient_slack_id="U222",
                recipient_name="Bob",
                recipient_role="contributor",
                lab="Lab",
                text="msg2",
            ),
        ]
        from engram_r.schedule_runner import deliver_messages as _deliver

        assert _deliver(messages) == 2

    def test_skips_recipient_when_open_dm_fails(self, monkeypatch):
        class FakeClient:
            def open_dm(self, slack_id):
                if slack_id == "U111":
                    return None
                return f"D-{slack_id}"

            def post_message(self, text, channel, blocks=None):
                pass

        monkeypatch.setattr(
            "engram_r.slack_client.SlackClient.from_env_optional",
            classmethod(lambda cls: FakeClient()),
        )
        messages = [
            ScheduledMessage(
                recipient_slack_id="U111",
                recipient_name="Alice",
                recipient_role="lead",
                lab="Lab",
                text="msg1",
            ),
            ScheduledMessage(
                recipient_slack_id="U222",
                recipient_name="Bob",
                recipient_role="contributor",
                lab="Lab",
                text="msg2",
            ),
        ]
        from engram_r.schedule_runner import deliver_messages as _deliver

        assert _deliver(messages) == 1

    def test_continues_on_post_message_exception(self, monkeypatch):
        call_count = 0

        class FakeClient:
            def open_dm(self, slack_id):
                return f"D-{slack_id}"

            def post_message(self, text, channel, blocks=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Slack API error")

        monkeypatch.setattr(
            "engram_r.slack_client.SlackClient.from_env_optional",
            classmethod(lambda cls: FakeClient()),
        )
        messages = [
            ScheduledMessage(
                recipient_slack_id="U111",
                recipient_name="Alice",
                recipient_role="lead",
                lab="Lab",
                text="msg1",
            ),
            ScheduledMessage(
                recipient_slack_id="U222",
                recipient_name="Bob",
                recipient_role="contributor",
                lab="Lab",
                text="msg2",
            ),
        ]
        from engram_r.schedule_runner import deliver_messages as _deliver

        # First fails, second succeeds
        assert _deliver(messages) == 1


# ---------------------------------------------------------------------------
# execute_schedule
# ---------------------------------------------------------------------------


def _create_vault_with_config(tmp_path: Path) -> Path:
    """Create a vault with daemon-config.yaml for execute_schedule tests."""
    vault = tmp_path / "vault"
    vault.mkdir()
    ops = vault / "ops"
    ops.mkdir()
    (ops / "reminders.md").write_text("# Reminders\n")

    config = {
        "schedules": [
            {
                "name": "weekly-project-update",
                "type": "project_update",
                "cadence": "weekly",
                "day": "monday",
                "hour": 9,
                "scope": "active",
                "delivery": "dm",
                "enabled": True,
            }
        ]
    }
    (ops / "daemon-config.yaml").write_text(yaml.dump(config))
    return vault


class TestExecuteSchedule:
    def test_returns_zero_for_unknown_marker(self, tmp_path: Path):
        vault = _create_vault_with_config(tmp_path)
        result = execute_schedule(str(vault), "sched-nonexistent-2026-W09")
        assert result == 0

    def test_returns_zero_when_no_messages(self, tmp_path: Path):
        vault = _create_vault_with_config(tmp_path)
        # No projects dir -> no lab updates -> no messages
        result = execute_schedule(str(vault), "sched-weekly-project-update-2026-W09")
        assert result == 0

    def test_returns_count_from_deliver(self, tmp_path: Path, monkeypatch):
        # Build a vault with a lab that has members and projects
        vault = _create_vault_fixture(tmp_path)
        ops = vault / "ops"
        ops.mkdir(exist_ok=True)
        config = {
            "schedules": [
                {
                    "name": "weekly-project-update",
                    "type": "project_update",
                    "cadence": "weekly",
                    "day": "monday",
                    "hour": 9,
                    "scope": "active",
                    "delivery": "dm",
                    "enabled": True,
                }
            ]
        }
        (ops / "daemon-config.yaml").write_text(yaml.dump(config))

        class FakeClient:
            def open_dm(self, slack_id):
                return f"D-{slack_id}"

            def post_message(self, text, channel, blocks=None):
                pass

        monkeypatch.setattr(
            "engram_r.slack_client.SlackClient.from_env_optional",
            classmethod(lambda cls: FakeClient()),
        )
        result = execute_schedule(str(vault), "sched-weekly-project-update-2026-W09")
        # 2 lab members -> 2 messages sent
        assert result == 2


# ---------------------------------------------------------------------------
# build_scheduled_messages -- new type routing
# ---------------------------------------------------------------------------


class TestBuildScheduledMessagesNewTypes:
    def test_stale_project_type_routes(self, tmp_path: Path):
        vault = _create_vault_fixture(tmp_path)
        entry = ScheduleEntry(name="test", type="stale_project", scope="active")
        # Should not raise; returns list (may be empty if nothing is stale)
        result = build_scheduled_messages(vault, entry)
        assert isinstance(result, list)

    def test_experiment_reminder_type_routes(self, tmp_path: Path):
        vault = _create_vault_fixture(tmp_path)
        entry = ScheduleEntry(
            name="test", type="experiment_reminder", scope="active", lookahead_days=30
        )
        result = build_scheduled_messages(vault, entry)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Stale project builder
# ---------------------------------------------------------------------------


def _create_stale_vault(tmp_path: Path, stale_days: int = 60) -> Path:
    """Create a vault with one stale and one fresh project."""
    import time

    vault = tmp_path / "vault"
    vault.mkdir()

    ops = vault / "ops"
    ops.mkdir()
    (ops / "reminders.md").write_text("# Reminders\n")

    # Daemon config with 30-day stale threshold
    config = {"thresholds": {"stale_notes_days": 30}}
    (ops / "daemon-config.yaml").write_text(yaml.dump(config))

    # Lab with members
    lab_dir = vault / "projects" / "testlab"
    lab_dir.mkdir(parents=True)
    lab_fm = {
        "type": "lab",
        "pi": "Dr. Stale",
        "members": [{"name": "Charlie", "slack_id": "U333", "role": "lead"}],
    }
    (lab_dir / "_index.md").write_text(f"---\n{yaml.dump(lab_fm)}---\n# Lab\n")

    # Research dirs
    exp_dir = vault / "_research" / "experiments"
    exp_dir.mkdir(parents=True)
    hyp_dir = vault / "_research" / "hypotheses"
    hyp_dir.mkdir(parents=True)

    # Stale project -- linked experiment last modified long ago
    proj_stale_fm = {
        "type": "project",
        "project_tag": "proj-stale",
        "title": "Stale Project",
        "status": "active",
        "linked_experiments": ["[[EXP-STALE]]"],
        "linked_hypotheses": [],
        "linked_goals": [],
    }
    (lab_dir / "proj-stale.md").write_text(
        f"---\n{yaml.dump(proj_stale_fm)}---\nStale.\n"
    )
    exp_stale_fm = {"type": "experiment", "id": "EXP-STALE", "status": "designed"}
    stale_exp = exp_dir / "EXP-STALE.md"
    stale_exp.write_text(f"---\n{yaml.dump(exp_stale_fm)}---\n# Stale\n")
    # Backdate mtime
    old_time = time.time() - (stale_days * 86400)
    import os

    os.utime(stale_exp, (old_time, old_time))

    # Fresh project -- recently modified hypothesis
    proj_fresh_fm = {
        "type": "project",
        "project_tag": "proj-fresh",
        "title": "Fresh Project",
        "status": "active",
        "linked_experiments": [],
        "linked_hypotheses": ["[[H-FRESH]]"],
        "linked_goals": [],
    }
    (lab_dir / "proj-fresh.md").write_text(
        f"---\n{yaml.dump(proj_fresh_fm)}---\nFresh.\n"
    )
    hyp_fresh_fm = {"type": "hypothesis", "id": "H-FRESH", "status": "proposed"}
    (hyp_dir / "H-FRESH.md").write_text(f"---\n{yaml.dump(hyp_fresh_fm)}---\n# Fresh\n")

    return vault


class TestBuildStaleProjectMessages:
    def test_identifies_stale_project(self, tmp_path: Path):
        vault = _create_stale_vault(tmp_path, stale_days=60)
        entry = ScheduleEntry(name="stale-test", type="stale_project", scope="active")
        messages = build_scheduled_messages(vault, entry)
        assert len(messages) == 1
        assert messages[0].recipient_name == "Charlie"
        assert "proj-stale" in messages[0].text or "Stale" in messages[0].text

    def test_no_stale_returns_empty(self, tmp_path: Path):
        vault = _create_stale_vault(tmp_path, stale_days=1)
        # With stale_days=1 the "stale" experiment is only 1 day old,
        # but our config threshold is 30 days, so it won't be stale.
        # Actually we need to make the threshold very low -- let's override.
        # The fixture backdates by stale_days=1 day, threshold is 30.
        # So nothing is stale. Good -- this tests no-stale path.
        entry = ScheduleEntry(name="stale-test", type="stale_project", scope="active")
        messages = build_scheduled_messages(vault, entry)
        assert messages == []

    def test_stale_message_contains_project_tag(self, tmp_path: Path):
        vault = _create_stale_vault(tmp_path, stale_days=60)
        entry = ScheduleEntry(name="stale-test", type="stale_project", scope="active")
        messages = build_scheduled_messages(vault, entry)
        # Blocks should contain stale project tag
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for msg in messages
            for b in msg.blocks
            if isinstance(b.get("text"), dict)
        )
        assert "proj-stale" in all_text


# ---------------------------------------------------------------------------
# Experiment reminder builder
# ---------------------------------------------------------------------------


def _create_reminder_vault(tmp_path: Path, reminder_days_ahead: int = 2) -> Path:
    """Create a vault with experiments that have upcoming reminders."""
    vault = tmp_path / "vault"
    vault.mkdir()

    ops = vault / "ops"
    ops.mkdir()

    today = datetime.date.today()
    near_date = today + datetime.timedelta(days=reminder_days_ahead)
    far_date = today + datetime.timedelta(days=90)

    (ops / "reminders.md").write_text(
        "# Reminders\n\n"
        f"- [ ] {near_date.isoformat()}: Submit EXP-REM registration\n"
        f"- [ ] {far_date.isoformat()}: Far future EXP-REM task\n"
    )

    config = {"schedules": []}
    (ops / "daemon-config.yaml").write_text(yaml.dump(config))

    # Lab
    lab_dir = vault / "projects" / "remlab"
    lab_dir.mkdir(parents=True)
    lab_fm = {
        "type": "lab",
        "pi": "Dr. Remind",
        "members": [{"name": "Dana", "slack_id": "U444", "role": "contributor"}],
    }
    (lab_dir / "_index.md").write_text(f"---\n{yaml.dump(lab_fm)}---\n")

    # Project with experiment
    proj_fm = {
        "type": "project",
        "project_tag": "proj-rem",
        "title": "Reminder Project",
        "status": "active",
        "linked_experiments": ["[[EXP-REM-test]]"],
        "linked_hypotheses": [],
        "linked_goals": [],
    }
    (lab_dir / "proj-rem.md").write_text(f"---\n{yaml.dump(proj_fm)}---\n")

    # Experiment with blocking gate
    exp_dir = vault / "_research" / "experiments"
    exp_dir.mkdir(parents=True)
    exp_fm = {"type": "experiment", "id": "EXP-REM", "status": "designed"}
    (exp_dir / "EXP-REM-test.md").write_text(
        f"---\n{yaml.dump(exp_fm)}---\n# EXP-REM\n\n"
        "| Step | Status |\n|---|---|\n| Access request | not started |\n"
    )

    return vault


class TestBuildExperimentReminderMessages:
    def test_upcoming_reminder_within_lookahead(self, tmp_path: Path):
        vault = _create_reminder_vault(tmp_path, reminder_days_ahead=2)
        entry = ScheduleEntry(
            name="exp-test",
            type="experiment_reminder",
            scope="active",
            lookahead_days=3,
        )
        messages = build_scheduled_messages(vault, entry)
        assert len(messages) == 1
        assert messages[0].recipient_name == "Dana"

    def test_no_upcoming_reminders(self, tmp_path: Path):
        vault = _create_reminder_vault(tmp_path, reminder_days_ahead=90)
        entry = ScheduleEntry(
            name="exp-test",
            type="experiment_reminder",
            scope="active",
            lookahead_days=3,
        )
        messages = build_scheduled_messages(vault, entry)
        # Blocking gate still present even though deadline is far away
        assert len(messages) == 1
        # Verify blocks contain blocking gate info
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for msg in messages
            for b in msg.blocks
            if isinstance(b.get("text"), dict)
        )
        assert "BLOCKING" in all_text

    def test_empty_when_no_experiments(self, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        ops = vault / "ops"
        ops.mkdir()
        (ops / "reminders.md").write_text("# Reminders\n")
        (ops / "daemon-config.yaml").write_text("schedules: []\n")

        lab_dir = vault / "projects" / "emptylab"
        lab_dir.mkdir(parents=True)
        lab_fm = {
            "type": "lab",
            "pi": "Dr. Empty",
            "members": [{"name": "Eve", "slack_id": "U555", "role": "lead"}],
        }
        (lab_dir / "_index.md").write_text(f"---\n{yaml.dump(lab_fm)}---\n")
        # No project files -> no experiments
        entry = ScheduleEntry(
            name="exp-test",
            type="experiment_reminder",
            scope="active",
            lookahead_days=7,
        )
        messages = build_scheduled_messages(vault, entry)
        assert messages == []
