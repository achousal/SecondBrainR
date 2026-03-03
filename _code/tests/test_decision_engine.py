"""Tests for the unified decision engine."""

import json
import textwrap

import pytest

from engram_r.daemon_config import DaemonConfig, MetabolicConfig
from engram_r.daemon_scheduler import (
    GoalState,
    TaskStackItem,
    VaultState,
)
from engram_r.decision_engine import (
    Recommendation,
    Signal,
    _build_state_summary,
    _pick_best_signal,
    classify_signals,
    main,
    parse_daemon_inbox,
    parse_next_log,
    recommend,
)
from engram_r.metabolic_indicators import MetabolicState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_config():
    return DaemonConfig(
        goals_priority=[
            "goal-test-analysis",
            "dynamic-metric-networks",
            "test-mechanism-analysis",
        ]
    )


@pytest.fixture
def clean_state():
    """Vault with nothing to do."""
    return VaultState(
        goals=[
            GoalState(
                goal_id="goal-test-analysis",
                hypothesis_count=12,
                undermatched_count=0,
                latest_landscape_mtime=300.0,
                latest_hypothesis_mtime=50.0,
            ),
        ],
    )


@pytest.fixture
def state_with_tasks():
    """Vault with active task stack items."""
    return VaultState(
        task_stack_active=[
            TaskStackItem(
                title="Submit data access request",
                description="gates all downstream analyses",
                section="Active",
            ),
            TaskStackItem(
                title="Pre-register EXP-001",
                description="OSF registration",
                section="Active",
            ),
        ],
    )


@pytest.fixture
def state_with_signals():
    """Vault with session-priority maintenance signals."""
    return VaultState(
        observation_count=15,
        orphan_count=5,
        inbox_count=8,
    )


# ---------------------------------------------------------------------------
# Signal classification
# ---------------------------------------------------------------------------


class TestClassifySignals:
    def test_session_orphans(self, clean_state, default_config):
        clean_state.orphan_count = 3
        signals = classify_signals(clean_state, default_config)
        orphan = [s for s in signals if s.name == "orphan_notes"]
        assert len(orphan) == 1
        assert orphan[0].speed == "session"
        assert orphan[0].count == 3

    def test_session_inbox_pressure(self, clean_state, default_config):
        clean_state.inbox_count = 8
        signals = classify_signals(clean_state, default_config)
        inbox = [s for s in signals if s.name == "inbox_pressure"]
        assert len(inbox) == 1
        assert inbox[0].speed == "session"

    def test_session_observations(self, clean_state, default_config):
        clean_state.observation_count = 12
        signals = classify_signals(clean_state, default_config)
        obs = [s for s in signals if s.name == "observations"]
        assert len(obs) == 1
        assert obs[0].speed == "session"
        assert "/rethink" in obs[0].action

    def test_session_tensions(self, clean_state, default_config):
        clean_state.tension_count = 6
        signals = classify_signals(clean_state, default_config)
        tens = [s for s in signals if s.name == "tensions"]
        assert len(tens) == 1
        assert tens[0].speed == "session"

    def test_session_unmined_sessions(self, clean_state, default_config):
        clean_state.unmined_session_count = 5
        signals = classify_signals(clean_state, default_config)
        sess = [s for s in signals if s.name == "unmined_sessions"]
        assert len(sess) == 1
        assert sess[0].speed == "session"

    def test_multi_session_queue_backlog(self, clean_state, default_config):
        clean_state.queue_backlog = 15
        signals = classify_signals(clean_state, default_config)
        queue = [s for s in signals if s.name == "queue_backlog"]
        assert len(queue) == 1
        assert queue[0].speed == "multi_session"

    def test_multi_session_stale_notes(self, clean_state, default_config):
        clean_state.stale_note_count = 15
        signals = classify_signals(clean_state, default_config)
        stale = [s for s in signals if s.name == "stale_notes"]
        assert len(stale) == 1
        assert stale[0].speed == "multi_session"

    def test_slow_health_stale(self, clean_state, default_config):
        clean_state.health_stale = True
        signals = classify_signals(clean_state, default_config)
        health = [s for s in signals if s.name == "health_stale"]
        assert len(health) == 1
        assert health[0].speed == "slow"

    def test_quarantine_review_signal(self, clean_state, default_config):
        clean_state.quarantine_count = 3
        signals = classify_signals(clean_state, default_config)
        qr = [s for s in signals if s.name == "quarantine_review"]
        assert len(qr) == 1
        assert qr[0].speed == "multi_session"
        assert qr[0].count == 3

    def test_no_quarantine_signal_when_zero(self, clean_state, default_config):
        clean_state.quarantine_count = 0
        signals = classify_signals(clean_state, default_config)
        qr = [s for s in signals if s.name == "quarantine_review"]
        assert qr == []

    def test_no_signals_when_clean(self, clean_state, default_config):
        signals = classify_signals(clean_state, default_config)
        assert len(signals) == 0

    def test_below_threshold_no_signal(self, clean_state, default_config):
        clean_state.inbox_count = 3  # below threshold of > 5
        clean_state.observation_count = 5  # below threshold of >= 10
        signals = classify_signals(clean_state, default_config)
        assert len(signals) == 0

    def test_multiple_signals(self, state_with_signals, default_config):
        signals = classify_signals(state_with_signals, default_config)
        names = {s.name for s in signals}
        assert "observations" in names
        assert "orphan_notes" in names
        assert "inbox_pressure" in names

    def test_metabolic_qpr_signal(self, clean_state, default_config):
        """QPR alarm generates session-priority signal."""
        clean_state.metabolic = MetabolicState(qpr=5.0, alarm_keys=["qpr_critical"])
        signals = classify_signals(clean_state, default_config)
        qpr = [s for s in signals if s.name == "metabolic_qpr"]
        assert len(qpr) == 1
        assert qpr[0].speed == "session"
        assert "/ralph" in qpr[0].action

    def test_metabolic_cmr_signal(self, clean_state, default_config):
        """CMR alarm generates session-priority signal."""
        clean_state.metabolic = MetabolicState(cmr=15.0, alarm_keys=["cmr_hot"])
        signals = classify_signals(clean_state, default_config)
        cmr = [s for s in signals if s.name == "metabolic_cmr"]
        assert len(cmr) == 1
        assert cmr[0].speed == "session"
        assert "/reflect" in cmr[0].action

    def test_metabolic_hcr_signal(self, clean_state, default_config):
        """HCR alarm generates multi-session signal."""
        clean_state.metabolic = MetabolicState(hcr=5.0, alarm_keys=["hcr_low"])
        signals = classify_signals(clean_state, default_config)
        hcr = [s for s in signals if s.name == "metabolic_hcr"]
        assert len(hcr) == 1
        assert hcr[0].speed == "multi_session"
        assert "/experiment" in hcr[0].action

    def test_metabolic_no_alarms_no_signals(self, clean_state, default_config):
        """No metabolic signals when no alarms."""
        clean_state.metabolic = MetabolicState(
            qpr=1.0, cmr=2.0, tpv=1.0, hcr=50.0, gcr=0.8, ipr=0.5, alarm_keys=[]
        )
        signals = classify_signals(clean_state, default_config)
        metabolic = [s for s in signals if s.name.startswith("metabolic_")]
        assert metabolic == []

    def test_metabolic_disabled_no_signals(self, clean_state):
        """No metabolic signals when disabled in config."""
        config = DaemonConfig(
            goals_priority=["goal-test-analysis"],
            metabolic=MetabolicConfig(enabled=False),
        )
        clean_state.metabolic = MetabolicState(qpr=5.0, alarm_keys=["qpr_critical"])
        signals = classify_signals(clean_state, config)
        metabolic = [s for s in signals if s.name.startswith("metabolic_")]
        assert metabolic == []

    def test_metabolic_none_no_signals(self, clean_state, default_config):
        """No metabolic signals when metabolic is None."""
        clean_state.metabolic = None
        signals = classify_signals(clean_state, default_config)
        metabolic = [s for s in signals if s.name.startswith("metabolic_")]
        assert metabolic == []


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------


class TestRecommend:
    def test_task_stack_first(self, state_with_tasks, default_config):
        rec = recommend(state_with_tasks, default_config)
        assert rec.category == "task_stack"
        assert "Submit data access" in rec.action
        assert rec.priority == "session"
        assert "Pre-register" in rec.after_that

    def test_task_stack_overrides_signals(self, default_config):
        """Task stack items override even session-priority signals."""
        state = VaultState(
            observation_count=20,
            orphan_count=50,
            task_stack_active=[
                TaskStackItem(title="My task", section="Active"),
            ],
        )
        rec = recommend(state, default_config)
        assert rec.category == "task_stack"
        assert "My task" in rec.action

    def test_session_signal_when_no_tasks(self, state_with_signals, default_config):
        rec = recommend(state_with_signals, default_config)
        assert rec.priority == "session"
        assert rec.category == "maintenance"

    def test_multi_session_signal(self, clean_state, default_config):
        clean_state.queue_backlog = 15
        rec = recommend(clean_state, default_config)
        assert rec.priority == "multi_session"
        assert "/ralph" in rec.action

    def test_slow_signal(self, clean_state, default_config):
        clean_state.health_stale = True
        rec = recommend(clean_state, default_config)
        assert rec.priority == "slow"
        assert "/health" in rec.action

    def test_tier3_generative(self, default_config):
        """Tier 3 when goals are cycle_complete."""
        state = VaultState(
            goals=[
                GoalState(
                    goal_id="goal-test-analysis",
                    hypothesis_count=12,
                    undermatched_count=0,
                    latest_landscape_mtime=300.0,
                    latest_hypothesis_mtime=400.0,
                ),
            ],
        )
        rec = recommend(state, default_config)
        assert rec.priority == "tier3"
        assert rec.category == "tier3"
        assert "generate" in rec.action.lower() or "evolve" in rec.action.lower()

    def test_clean_state(self, clean_state, default_config):
        rec = recommend(clean_state, default_config)
        assert rec.priority == "clean"
        assert rec.category == "clean"

    def test_highest_impact_session_signal(self, default_config):
        """Engine picks highest-count signal at same priority."""
        state = VaultState(
            observation_count=12,
            orphan_count=2,
        )
        rec = recommend(state, default_config)
        # Observations have higher count
        assert "/rethink" in rec.action

    def test_after_that_from_session_signals(self, default_config):
        state = VaultState(
            observation_count=12,
            orphan_count=5,
        )
        rec = recommend(state, default_config)
        assert rec.after_that != ""


# ---------------------------------------------------------------------------
# Signal picker with dedup
# ---------------------------------------------------------------------------


class TestPickBestSignal:
    def test_highest_count_first(self):
        signals = [
            Signal("a", 5, "session", "/cmd-a", "reason-a"),
            Signal("b", 20, "session", "/cmd-b", "reason-b"),
        ]
        best = _pick_best_signal(signals, [])
        assert best.name == "b"

    def test_dedup_skips_recent(self):
        signals = [
            Signal("a", 20, "session", "/cmd-a", "reason-a"),
            Signal("b", 5, "session", "/cmd-b", "reason-b"),
        ]
        recent = ["/cmd-a was recommended"]
        best = _pick_best_signal(signals, recent)
        assert best.name == "b"

    def test_dedup_falls_back_when_all_recent(self):
        signals = [
            Signal("a", 20, "session", "/cmd-a", "reason-a"),
            Signal("b", 5, "session", "/cmd-b", "reason-b"),
        ]
        recent = ["/cmd-a", "/cmd-b"]
        best = _pick_best_signal(signals, recent)
        # Falls back to highest count
        assert best.name == "a"


# ---------------------------------------------------------------------------
# Daemon inbox parsing
# ---------------------------------------------------------------------------


class TestParseDaemonInbox:
    def test_parse_completed(self, tmp_path):
        inbox = tmp_path / "ops" / "daemon-inbox.md"
        inbox.parent.mkdir(parents=True)
        inbox.write_text(textwrap.dedent("""\
            # Daemon Inbox

            ## 2026-02-23

            ### Completed
            - [x] landscape: p1-landscape-goal-test (sonnet, 314s)
            - [x] meta-review: p1-meta-review-analysis (sonnet, 327s)
            ### Alerts
            - Alert: health gate failed twice
            ### For You
            - [ ] /generate for goal-test-analysis
            - [ ] /evolve for goal-test-analysis
        """))
        result = parse_daemon_inbox(tmp_path)
        assert len(result["completed"]) == 2
        assert "landscape" in result["completed"][0]
        assert len(result["alerts"]) == 1
        assert "health gate" in result["alerts"][0]
        assert len(result["for_you"]) == 2
        assert "/generate" in result["for_you"][0]

    def test_missing_file(self, tmp_path):
        result = parse_daemon_inbox(tmp_path)
        assert result["completed"] == []
        assert result["alerts"] == []
        assert result["for_you"] == []

    def test_empty_file(self, tmp_path):
        inbox = tmp_path / "ops" / "daemon-inbox.md"
        inbox.parent.mkdir(parents=True)
        inbox.write_text("")
        result = parse_daemon_inbox(tmp_path)
        assert result["completed"] == []

    def test_only_parses_first_date_section(self, tmp_path):
        inbox = tmp_path / "ops" / "daemon-inbox.md"
        inbox.parent.mkdir(parents=True)
        inbox.write_text(textwrap.dedent("""\
            # Daemon Inbox

            ## 2026-02-23

            ### Completed
            - [x] task-today

            ## 2026-02-22

            ### Completed
            - [x] task-yesterday
        """))
        result = parse_daemon_inbox(tmp_path)
        assert len(result["completed"]) == 1
        assert "today" in result["completed"][0]


# ---------------------------------------------------------------------------
# Next log parsing
# ---------------------------------------------------------------------------


class TestParseNextLog:
    def test_parse_recommendations(self, tmp_path):
        log = tmp_path / "ops" / "next-log.md"
        log.parent.mkdir(parents=True)
        log.write_text(textwrap.dedent("""\
            # /next Log

            ## 2026-02-23 19:05

            **Mode:** standalone
            **Recommended:** /rethink
            **Priority:** session

            ## 2026-02-23 18:26

            **Recommended:** /tournament for goal-test-analysis
            **Priority:** multi-session

            ## 2026-02-23 17:29

            **Recommended:** Create 4 missing topic maps
            **Priority:** session
        """))
        recs = parse_next_log(tmp_path, n=3)
        assert len(recs) == 3
        assert "/rethink" in recs[0]
        assert "/tournament" in recs[1]

    def test_missing_file(self, tmp_path):
        recs = parse_next_log(tmp_path)
        assert recs == []

    def test_limit_n(self, tmp_path):
        log = tmp_path / "ops" / "next-log.md"
        log.parent.mkdir(parents=True)
        log.write_text(textwrap.dedent("""\
            **Recommended:** first
            **Recommended:** second
            **Recommended:** third
            **Recommended:** fourth
        """))
        recs = parse_next_log(tmp_path, n=2)
        assert len(recs) == 2
        assert recs[0] == "first"


# ---------------------------------------------------------------------------
# State summary
# ---------------------------------------------------------------------------


class TestStateSummary:
    def test_includes_key_fields(self):
        state = VaultState(
            health_fails=1,
            observation_count=6,
            task_stack_active=[
                TaskStackItem(title="t1", section="Active"),
            ],
            goals=[
                GoalState(
                    goal_id="goal-test",
                    hypothesis_count=12,
                    latest_landscape_mtime=300.0,
                    latest_hypothesis_mtime=50.0,
                ),
            ],
        )
        summary = _build_state_summary(state)
        assert summary["health_fails"] == 1
        assert summary["observations"] == 6
        assert summary["task_stack_active"] == 1
        assert len(summary["goals"]) == 1
        assert summary["goals"][0]["cycle_state"] == "cycle_stale"

    def test_metabolic_in_summary(self):
        state = VaultState(
            metabolic=MetabolicState(
                qpr=5.0,
                cmr=19.0,
                tpv=0.5,
                hcr=10.0,
                gcr=0.7,
                ipr=2.0,
                vdr=95.0,
                alarm_keys=["qpr_critical", "cmr_hot"],
            ),
        )
        summary = _build_state_summary(state)
        assert "metabolic" in summary
        assert summary["metabolic"]["qpr"] == 5.0
        assert summary["metabolic"]["tpv"] == 0.5
        assert summary["metabolic"]["gcr"] == 0.7
        assert summary["metabolic"]["ipr"] == 2.0
        assert summary["metabolic"]["vdr"] == 95.0
        assert summary["metabolic"]["alarm_keys"] == ["qpr_critical", "cmr_hot"]
        assert "swr" not in summary["metabolic"]

    def test_metabolic_none_not_in_summary(self):
        state = VaultState(metabolic=None)
        summary = _build_state_summary(state)
        assert "metabolic" not in summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_missing_config(self, tmp_path, capsys):
        """Exit 1 when config not found."""
        exit_code = main([str(tmp_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower() or "Config not found" in captured.err

    def test_clean_state_exit_2(self, tmp_path, capsys):
        """Exit 2 for clean state (need fresh health report to avoid stale signal)."""
        (tmp_path / "ops").mkdir(parents=True)
        config = tmp_path / "ops" / "daemon-config.yaml"
        # Disable metabolic to avoid HCR alarm on empty vault
        config.write_text("goals_priority: []\nmetabolic:\n  enabled: false\n")
        # Create a fresh health report so health_stale=False
        health_dir = tmp_path / "ops" / "health"
        health_dir.mkdir(parents=True)
        (health_dir / "2026-02-23-report.md").write_text(
            "Summary: 0 FAIL, 0 WARN, 3 PASS\n"
        )
        exit_code = main([str(tmp_path)])
        assert exit_code == 2
        output = json.loads(capsys.readouterr().out)
        assert output["recommendation"]["priority"] == "clean"

    def test_recommendation_exit_0(self, tmp_path, capsys):
        """Exit 0 when there is work to do."""
        (tmp_path / "ops").mkdir(parents=True)
        config = tmp_path / "ops" / "daemon-config.yaml"
        config.write_text("goals_priority: []\n")
        # Create task stack with active item
        tasks = tmp_path / "ops" / "tasks.md"
        tasks.write_text(textwrap.dedent("""\
            # Tasks

            ## Active

            - **Do something** -- important task
        """))
        exit_code = main([str(tmp_path)])
        assert exit_code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["recommendation"]["category"] == "task_stack"
        assert "Do something" in output["recommendation"]["action"]

    def test_json_output_structure(self, tmp_path, capsys):
        """Output has required top-level keys."""
        (tmp_path / "ops").mkdir(parents=True)
        config = tmp_path / "ops" / "daemon-config.yaml"
        config.write_text("goals_priority: []\n")
        main([str(tmp_path)])
        output = json.loads(capsys.readouterr().out)
        assert "mode" in output
        assert "recommendation" in output
        assert "state_summary" in output
        assert "daemon_context" in output

    def test_mode_flag(self, tmp_path, capsys):
        """--mode flag is respected."""
        (tmp_path / "ops").mkdir(parents=True)
        config = tmp_path / "ops" / "daemon-config.yaml"
        config.write_text("goals_priority: []\n")
        main([str(tmp_path), "--mode", "standalone"])
        output = json.loads(capsys.readouterr().out)
        assert output["mode"] == "standalone"


# ---------------------------------------------------------------------------
# Multi-alarm metabolic cascade (B1)
# ---------------------------------------------------------------------------


class TestMultiAlarmMetabolicCascade:
    """Verify multi-alarm interactions in the decision engine."""

    def test_qpr_and_cmr_simultaneous(self, clean_state, default_config):
        """QPR + CMR: higher-count signal wins within session speed tier."""
        clean_state.metabolic = MetabolicState(
            qpr=5.0, cmr=15.0, alarm_keys=["qpr_critical", "cmr_hot"]
        )
        signals = classify_signals(clean_state, default_config)
        session_signals = [s for s in signals if s.speed == "session"]
        assert len(session_signals) == 2
        rec = recommend(clean_state, default_config)
        # Both are session-priority; higher count wins
        assert rec.priority == "session"
        assert rec.category == "maintenance"

    def test_qpr_cmr_hcr_triple_alarm(self, clean_state, default_config):
        """QPR + CMR + HCR: session-speed beats multi-session."""
        clean_state.metabolic = MetabolicState(
            qpr=5.0, cmr=15.0, hcr=5.0,
            alarm_keys=["qpr_critical", "cmr_hot", "hcr_low"],
        )
        signals = classify_signals(clean_state, default_config)
        session_sigs = [s for s in signals if s.speed == "session"]
        multi_sigs = [s for s in signals if s.speed == "multi_session"]
        assert len(session_sigs) == 2  # QPR + CMR
        assert len(multi_sigs) == 1  # HCR
        rec = recommend(clean_state, default_config)
        # Session signals should be recommended first
        assert rec.priority == "session"

    def test_metabolic_plus_regular_signals(self, clean_state, default_config):
        """Metabolic + regular session signals interact correctly."""
        clean_state.metabolic = MetabolicState(
            qpr=5.0, alarm_keys=["qpr_critical"]
        )
        clean_state.orphan_count = 20  # Higher count than QPR
        signals = classify_signals(clean_state, default_config)
        session_sigs = [s for s in signals if s.speed == "session"]
        names = {s.name for s in session_sigs}
        assert "metabolic_qpr" in names
        assert "orphan_notes" in names
        rec = recommend(clean_state, default_config)
        # Orphans have higher count (20 vs 5), should win
        assert rec.priority == "session"
        assert "/reflect" in rec.action or "/ralph" in rec.action


# ---------------------------------------------------------------------------
# Queue blocked signal
# ---------------------------------------------------------------------------


class TestQueueBlockedSignal:
    def test_queue_blocked_signal(self, clean_state, default_config):
        """queue_blocked > 0 produces a multi-session signal."""
        clean_state.queue_blocked = 5
        signals = classify_signals(clean_state, default_config)
        blocked = [s for s in signals if s.name == "queue_blocked"]
        assert len(blocked) == 1
        assert blocked[0].speed == "multi_session"
        assert blocked[0].count == 5
        assert "/literature" in blocked[0].action
        assert "unpopulated stubs" in blocked[0].rationale

    def test_no_queue_blocked_signal_when_zero(self, clean_state, default_config):
        """queue_blocked == 0 produces no signal."""
        clean_state.queue_blocked = 0
        signals = classify_signals(clean_state, default_config)
        blocked = [s for s in signals if s.name == "queue_blocked"]
        assert blocked == []

    def test_state_summary_includes_queue_blocked(self):
        """_build_state_summary includes queue_blocked key."""
        state = VaultState(queue_blocked=7)
        summary = _build_state_summary(state)
        assert "queue_blocked" in summary
        assert summary["queue_blocked"] == 7
