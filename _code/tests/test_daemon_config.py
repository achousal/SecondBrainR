"""Tests for engram_r.daemon_config notification configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engram_r.daemon_config import (
    AuthorityConfig,
    BotConfig,
    DaemonConfig,
    InboundConfig,
    NotificationChannels,
    NotificationConfig,
    NotificationEvents,
    ScheduleEntry,
    load_config,
)


# ---------------------------------------------------------------------------
# NotificationChannels
# ---------------------------------------------------------------------------


class TestNotificationChannels:
    def test_default_for_regular_event(self):
        ch = NotificationChannels(default="C1")
        assert ch.for_event("session_start") == "C1"

    def test_alert_channel_for_daemon_alert(self):
        ch = NotificationChannels(default="C1", alerts="C2")
        assert ch.for_event("daemon_alert") == "C2"

    def test_daemon_channel_for_daemon_events(self):
        ch = NotificationChannels(default="C1", daemon="C3")
        assert ch.for_event("daemon_task_complete") == "C3"
        assert ch.for_event("daemon_for_you") == "C3"

    def test_alert_overrides_daemon_for_alerts(self):
        ch = NotificationChannels(default="C1", alerts="C2", daemon="C3")
        assert ch.for_event("daemon_alert") == "C2"

    def test_fallback_to_default_when_specific_empty(self):
        ch = NotificationChannels(default="C1", alerts="", daemon="")
        assert ch.for_event("daemon_alert") == "C1"
        assert ch.for_event("daemon_task_complete") == "C1"


# ---------------------------------------------------------------------------
# NotificationEvents
# ---------------------------------------------------------------------------


class TestNotificationEvents:
    def test_defaults(self):
        ev = NotificationEvents()
        assert ev.session_start is True
        assert ev.new_hypothesis is False

    def test_custom(self):
        ev = NotificationEvents(session_start=False, new_hypothesis=True)
        assert ev.session_start is False
        assert ev.new_hypothesis is True


# ---------------------------------------------------------------------------
# InboundConfig
# ---------------------------------------------------------------------------


class TestInboundConfig:
    def test_defaults(self):
        ic = InboundConfig()
        assert ic.enabled is True
        assert ic.lookback_hours == 24
        assert ic.channel == ""


# ---------------------------------------------------------------------------
# NotificationConfig
# ---------------------------------------------------------------------------


class TestNotificationConfig:
    def test_should_notify_enabled(self):
        cfg = NotificationConfig()
        assert cfg.should_notify("session_start") is True

    def test_should_notify_disabled_globally(self):
        cfg = NotificationConfig(enabled=False)
        assert cfg.should_notify("session_start") is False

    def test_should_notify_level_off(self):
        cfg = NotificationConfig(level="off")
        assert cfg.should_notify("session_start") is False

    def test_should_notify_alerts_only(self):
        cfg = NotificationConfig(level="alerts-only")
        assert cfg.should_notify("daemon_alert") is True
        assert cfg.should_notify("session_start") is False
        assert cfg.should_notify("tournament_result") is False

    def test_should_notify_event_disabled(self):
        events = NotificationEvents(session_start=False)
        cfg = NotificationConfig(events=events)
        assert cfg.should_notify("session_start") is False
        assert cfg.should_notify("session_end") is True

    def test_should_notify_unknown_event(self):
        cfg = NotificationConfig()
        assert cfg.should_notify("nonexistent_event") is False


# ---------------------------------------------------------------------------
# DaemonConfig integration
# ---------------------------------------------------------------------------


class TestDaemonConfigNotifications:
    def test_default_daemon_config_has_notifications(self):
        cfg = DaemonConfig()
        assert isinstance(cfg.notifications, NotificationConfig)
        assert cfg.notifications.enabled is True

    def test_load_config_with_notifications(self, tmp_path: Path):
        config_data = {
            "goals_priority": [],
            "notifications": {
                "enabled": True,
                "level": "alerts-only",
                "channels": {
                    "default": "C0AGLDXCS30",
                    "alerts": "C_ALERTS",
                },
                "events": {
                    "session_start": True,
                    "new_hypothesis": True,
                },
                "inbound": {
                    "enabled": False,
                    "lookback_hours": 12,
                },
            },
        }
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert cfg.notifications.level == "alerts-only"
        assert cfg.notifications.channels.default == "C0AGLDXCS30"
        assert cfg.notifications.channels.alerts == "C_ALERTS"
        assert cfg.notifications.events.new_hypothesis is True
        assert cfg.notifications.inbound.enabled is False
        assert cfg.notifications.inbound.lookback_hours == 12

    def test_load_config_without_notifications(self, tmp_path: Path):
        config_data = {"goals_priority": ["test-analysis"]}
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert cfg.notifications.enabled is True  # default
        assert cfg.notifications.level == "all"  # default

    def test_load_config_notifications_partial(self, tmp_path: Path):
        config_data = {
            "notifications": {
                "enabled": False,
            },
        }
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert cfg.notifications.enabled is False
        # Sub-configs should still get defaults
        assert cfg.notifications.channels.default == ""
        assert cfg.notifications.events.session_start is True
        assert cfg.notifications.inbound.enabled is True

    def test_load_config_ignores_unknown_notification_keys(self, tmp_path: Path):
        config_data = {
            "notifications": {
                "enabled": True,
                "channels": {
                    "default": "C1",
                    "unknown_channel": "C_EXTRA",
                },
                "events": {
                    "session_start": True,
                    "unknown_event": True,
                },
            },
        }
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert cfg.notifications.channels.default == "C1"
        assert cfg.notifications.events.session_start is True


# ---------------------------------------------------------------------------
# ScheduleEntry
# ---------------------------------------------------------------------------


class TestScheduleEntry:
    def test_defaults(self):
        entry = ScheduleEntry()
        assert entry.name == ""
        assert entry.cadence == "weekly"
        assert entry.delivery == "dm"
        assert entry.enabled is True
        assert entry.hour == 9
        assert entry.lookahead_days == 3

    def test_custom_values(self):
        entry = ScheduleEntry(
            name="test-sched",
            type="project_update",
            cadence="daily",
            hour=8,
            delivery="channel",
            enabled=False,
        )
        assert entry.name == "test-sched"
        assert entry.cadence == "daily"
        assert entry.delivery == "channel"
        assert entry.enabled is False


class TestDaemonConfigSchedules:
    def test_default_has_empty_schedules(self):
        cfg = DaemonConfig()
        assert cfg.schedules == []

    def test_load_config_with_schedules(self, tmp_path: Path):
        config_data = {
            "goals_priority": [],
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
                },
                {
                    "name": "stale-alert",
                    "type": "stale_project",
                    "cadence": "weekly",
                    "day": "friday",
                    "hour": 16,
                    "enabled": False,
                },
            ],
        }
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert len(cfg.schedules) == 2
        assert cfg.schedules[0].name == "weekly-project-update"
        assert cfg.schedules[0].type == "project_update"
        assert cfg.schedules[0].day == "monday"
        assert cfg.schedules[0].delivery == "dm"
        assert cfg.schedules[1].name == "stale-alert"
        assert cfg.schedules[1].enabled is False

    def test_load_config_without_schedules(self, tmp_path: Path):
        config_data = {"goals_priority": []}
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert cfg.schedules == []

    def test_load_config_ignores_unknown_schedule_fields(self, tmp_path: Path):
        config_data = {
            "schedules": [
                {
                    "name": "test",
                    "type": "project_update",
                    "unknown_field": "ignored",
                },
            ],
        }
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert len(cfg.schedules) == 1
        assert cfg.schedules[0].name == "test"


# ---------------------------------------------------------------------------
# AuthorityConfig
# ---------------------------------------------------------------------------


class TestAuthorityConfig:
    def test_defaults(self):
        ac = AuthorityConfig()
        assert ac.owner_ids == ()
        assert ac.allowed_ids == ()
        assert ac.public_access is True
        assert ac.max_per_user_per_minute == 5
        assert ac.cooldown_after_deny_s == 30


class TestDaemonConfigBotAuthority:
    def test_bot_authority_parsed(self, tmp_path: Path):
        config_data = {
            "bot": {
                "channel": "C_BOT",
                "authority": {
                    "owner_ids": ["U_OWNER1", "U_OWNER2"],
                    "allowed_ids": ["U_FRIEND"],
                    "public_access": False,
                    "max_per_user_per_minute": 10,
                    "cooldown_after_deny_s": 60,
                },
            },
        }
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert cfg.bot.channel == "C_BOT"
        assert cfg.bot.authority.owner_ids == ("U_OWNER1", "U_OWNER2")
        assert cfg.bot.authority.allowed_ids == ("U_FRIEND",)
        assert cfg.bot.authority.public_access is False
        assert cfg.bot.authority.max_per_user_per_minute == 10
        assert cfg.bot.authority.cooldown_after_deny_s == 60

    def test_bot_authority_defaults(self, tmp_path: Path):
        config_data = {
            "bot": {
                "channel": "C_BOT",
            },
        }
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump(config_data))

        cfg = load_config(cfg_path)
        assert cfg.bot.authority.owner_ids == ()
        assert cfg.bot.authority.public_access is True
        assert cfg.bot.authority.max_per_user_per_minute == 5
