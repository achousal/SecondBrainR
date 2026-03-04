"""Tests for engram_r.slack_formatter."""

from __future__ import annotations

from engram_r.slack_formatter import (
    _format_duration,
    _render_attention_project,
    _render_ontrack_project,
    format_daily_parent,
    format_daemon_alert,
    format_daemon_for_you,
    format_daemon_task_complete,
    format_inbound_summary,
    format_meta_review,
    format_session_end,
    format_session_start,
    format_tournament_result,
    format_weekly_project_dm,
)


class TestFormatDuration:
    def test_seconds_only(self):
        assert _format_duration(45) == "45s"

    def test_minutes(self):
        assert _format_duration(120) == "2m"

    def test_minutes_and_seconds(self):
        assert _format_duration(125) == "2m 5s"

    def test_hours(self):
        assert _format_duration(3720) == "1h 2m"


class TestDailyParent:
    def test_returns_tuple(self):
        text, blocks = format_daily_parent("2026-02-23")
        assert "2026-02-23" in text
        assert len(blocks) == 2
        assert blocks[0]["type"] == "header"


class TestSessionStart:
    def test_minimal(self):
        text, blocks = format_session_start()
        assert "Session started" in text
        assert len(blocks) >= 1

    def test_with_goals_and_stats(self):
        text, blocks = format_session_start(
            goals=["Test analysis metrics", "Test mechanism analysis"],
            vault_stats={"claims": 311, "inbox": 9},
            top_hypotheses=["1. H-TEST-004b (Elo 1338)"],
        )
        assert "Session started" in text
        # Collect all text from blocks (sections have text.text, context has elements)
        all_text_parts = []
        for b in blocks:
            if isinstance(b.get("text"), dict):
                all_text_parts.append(b["text"].get("text", ""))
            for elem in b.get("elements", []):
                if isinstance(elem, dict):
                    all_text_parts.append(elem.get("text", ""))
        block_texts = " ".join(all_text_parts)
        assert "Test analysis metrics" in block_texts
        assert "311" in block_texts


class TestSessionEnd:
    def test_minimal(self):
        text, blocks = format_session_end()
        assert "Session ended" in text

    def test_with_details(self):
        text, blocks = format_session_end(
            session_id="abc12345-xyz",
            files_written=["notes/foo.md", "notes/bar.md"],
            skills_invoked=["/generate", "/tournament"],
            summary="Generated 4 hypotheses and ran 8 matches",
            duration_s=300,
        )
        assert "abc12345" in text
        block_texts = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if isinstance(b.get("text"), dict)
        )
        assert "/generate" in block_texts


class TestDaemonTaskComplete:
    def test_basic(self):
        text, blocks = format_daemon_task_complete(
            skill="tournament", task_key="tourn-test-001", model="opus", elapsed_s=120
        )
        assert "tournament" in text
        assert len(blocks) >= 1


class TestDaemonAlert:
    def test_basic(self):
        text, blocks = format_daemon_alert("5 consecutive fast fails")
        assert "alert" in text.lower()
        assert "5 consecutive" in blocks[0]["text"]["text"]


class TestDaemonForYou:
    def test_empty(self):
        text, blocks = format_daemon_for_you()
        assert "0 item(s)" in text

    def test_with_entries(self):
        text, blocks = format_daemon_for_you(
            entries=["Review H-TEST-009 draft", "Approve /rethink proposal"]
        )
        assert "2 item(s)" in text
        assert len(blocks) == 2


class TestTournamentResult:
    def test_basic(self):
        text, blocks = format_tournament_result(
            goal_id="test-analysis",
            matches=8,
            top_hypotheses=["1. H-TEST-004b (1338)", "2. H-TEST-003b (1294)"],
        )
        assert "test-analysis" in text
        block_texts = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if isinstance(b.get("text"), dict)
        )
        assert "H-TEST-004b" in block_texts


class TestMetaReview:
    def test_basic(self):
        text, blocks = format_meta_review(
            goal_id="test-analysis",
            hypotheses_reviewed=12,
            matches_analyzed=74,
            key_patterns=["Gen-2 evolutions dominate"],
        )
        assert "12 hyps" in text
        assert "74 matches" in text


class TestInboundSummary:
    def test_empty_returns_empty(self):
        assert format_inbound_summary([]) == ""

    def test_formats_messages(self):
        msgs = [
            {"user": "Alice", "text": "Check the new paper on methods", "ts": "1"},
            {"user": "Bob", "text": "Data access approved!", "ts": "2"},
        ]
        result = format_inbound_summary(msgs, channel_name="#research")
        assert "#research" in result
        assert "Alice" in result
        assert "methods" in result

    def test_truncates_long_messages(self):
        msgs = [{"user": "U1", "text": "x" * 300, "ts": "1"}]
        result = format_inbound_summary(msgs)
        assert "..." in result

    def test_caps_at_ten(self):
        msgs = [{"user": f"U{i}", "text": f"msg {i}", "ts": str(i)} for i in range(15)]
        result = format_inbound_summary(msgs)
        assert "5 more" in result


# ---------------------------------------------------------------------------
# Weekly Project Update DM
# ---------------------------------------------------------------------------


def _make_project_summary(tag="proj", title="Project", status="active", **kwargs):
    """Helper to create a ProjectSummary-like object for formatter tests."""
    from engram_r.schedule_runner import (
        ExperimentBrief,
        HypothesisBrief,
        ProjectSummary,
        ReminderBrief,
    )

    return ProjectSummary(
        tag=tag,
        title=title,
        status=status,
        experiments=kwargs.get("experiments", []),
        hypotheses=kwargs.get("hypotheses", []),
        reminders=kwargs.get("reminders", []),
        next_action=kwargs.get("next_action", ""),
        linked_goal_names=kwargs.get("linked_goal_names", []),
    )


class TestWeeklyProjectDm:
    def test_minimal(self):
        text, blocks = format_weekly_project_dm(
            recipient_name="Alice",
            recipient_role="lead",
            lab_name="Test Lab",
            week_label="Week 9, 2026",
        )
        assert "Test Lab" in text
        assert "Week 9" in text
        assert any(b["type"] == "header" for b in blocks)
        # Should have greeting with name
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if isinstance(b.get("text"), dict)
        )
        assert "Alice" in all_text

    def test_lead_sees_all_tiers(self):
        from engram_r.schedule_runner import ExperimentBrief, ReminderBrief

        attn = [
            _make_project_summary(
                tag="alpha",
                title="Alpha",
                experiments=[ExperimentBrief(id="EXP-001", status="designed")],
                reminders=[ReminderBrief(date="2026-03-01", text="Submit access")],
            )
        ]
        track = [_make_project_summary(tag="beta", title="Beta")]
        maint = [_make_project_summary(tag="gamma", title="Gamma", status="maintenance")]

        text, blocks = format_weekly_project_dm(
            recipient_name="Alice",
            recipient_role="lead",
            lab_name="Test Lab",
            week_label="Week 9",
            needs_attention=attn,
            on_track=track,
            maintenance=maint,
            reminders_this_week=1,
            reminders_next_week=2,
        )
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if isinstance(b.get("text"), dict)
        )
        assert "NEEDS ATTENTION" in all_text
        assert "ON TRACK" in all_text
        assert "MAINTENANCE" in all_text
        assert "alpha" in all_text
        assert "beta" in all_text
        assert "gamma" in all_text

    def test_observer_gets_counts_for_track_and_maintenance(self):
        track = [
            _make_project_summary(tag=f"p{i}", title=f"Project {i}")
            for i in range(5)
        ]
        maint = [
            _make_project_summary(tag="m1", title="Maint 1", status="maintenance")
        ]
        text, blocks = format_weekly_project_dm(
            recipient_name="Observer",
            recipient_role="observer",
            lab_name="Test Lab",
            week_label="Week 9",
            on_track=track,
            maintenance=maint,
        )
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if isinstance(b.get("text"), dict)
        )
        # Observer should see count, not individual project details
        assert "5 project(s)" in all_text
        assert "1 project(s)" in all_text
        # Should NOT see individual project tags in on_track section
        assert "p0" not in all_text

    def test_footer_shows_reminder_counts(self):
        text, blocks = format_weekly_project_dm(
            recipient_name="Alice",
            recipient_role="lead",
            lab_name="Lab",
            week_label="W9",
            reminders_this_week=3,
            reminders_next_week=5,
        )
        # Footer is a context block
        context_texts = []
        for b in blocks:
            for elem in b.get("elements", []):
                if isinstance(elem, dict):
                    context_texts.append(elem.get("text", ""))
        footer = " ".join(context_texts)
        assert "3" in footer
        assert "5" in footer

    def test_block_limit_guard(self):
        """Message with many projects stays under 50 blocks."""
        many = [
            _make_project_summary(tag=f"p{i}", title=f"Project {i}")
            for i in range(30)
        ]
        text, blocks = format_weekly_project_dm(
            recipient_name="Alice",
            recipient_role="lead",
            lab_name="Lab",
            week_label="W9",
            on_track=many,
        )
        assert len(blocks) <= 50


class TestRenderAttentionProject:
    def test_includes_experiment(self):
        from engram_r.schedule_runner import ExperimentBrief

        proj = _make_project_summary(
            tag="treatment-a",
            title="Treatment-A Study",
            experiments=[
                ExperimentBrief(
                    id="EXP-002",
                    status="completed",
                    outcome="completed-null",
                )
            ],
        )
        result = _render_attention_project(proj)
        assert "EXP-002" in result
        assert "completed-null" in result

    def test_includes_hypothesis_with_elo(self):
        from engram_r.schedule_runner import HypothesisBrief

        proj = _make_project_summary(
            tag="analysis",
            title="Analysis Study",
            hypotheses=[
                HypothesisBrief(
                    id="H-TEST-004b",
                    elo=1338,
                    status="proposed",
                )
            ],
        )
        result = _render_attention_project(proj)
        assert "H-TEST-004b" in result
        assert "1338" in result

    def test_includes_reminder(self):
        from engram_r.schedule_runner import ReminderBrief

        proj = _make_project_summary(
            tag="test",
            title="Test",
            reminders=[ReminderBrief(date="2026-03-01", text="Submit access request")],
        )
        result = _render_attention_project(proj)
        assert "2026-03-01" in result
        assert "Submit access request" in result

    def test_includes_next_action(self):
        proj = _make_project_summary(
            tag="test",
            title="Test",
            next_action="Cycle 3 hypothesis generation",
        )
        result = _render_attention_project(proj)
        assert "Cycle 3" in result


class TestRenderOntrackProject:
    def test_compact_format(self):
        proj = _make_project_summary(tag="bio", title="BioMe")
        result = _render_ontrack_project(proj)
        assert "bio" in result
        assert "BioMe" in result
        assert "No experiments" in result
        assert "No hypotheses" in result

    def test_shows_counts(self):
        from engram_r.schedule_runner import ExperimentBrief, HypothesisBrief

        proj = _make_project_summary(
            tag="test",
            title="Test",
            experiments=[ExperimentBrief(id="E1", status="running")],
            hypotheses=[
                HypothesisBrief(id="H1"),
                HypothesisBrief(id="H2"),
            ],
        )
        result = _render_ontrack_project(proj)
        assert "1 experiment(s)" in result
        assert "2 hypothesis(es)" in result
