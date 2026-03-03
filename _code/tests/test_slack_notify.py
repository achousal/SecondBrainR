"""Tests for engram_r.slack_notify."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from engram_r.slack_client import SlackMessage
from engram_r.slack_notify import (
    _get_or_create_daily_thread,
    _prune_old_threads,
    fetch_inbound_messages,
    send_notification,
)


def _write_config(tmp_path: Path, overrides: dict | None = None) -> Path:
    """Write a minimal daemon-config.yaml and return vault_path."""
    vault = tmp_path / "vault"
    ops = vault / "ops"
    ops.mkdir(parents=True)
    daemon_dir = ops / "daemon"
    daemon_dir.mkdir()

    config = {
        "notifications": {
            "enabled": True,
            "level": "all",
            "channels": {"default": "C_TEST"},
            "events": {
                "session_start": True,
                "session_end": True,
                "daemon_task_complete": True,
                "daemon_alert": True,
                "daemon_for_you": True,
                "tournament_result": True,
                "new_hypothesis": False,
                "meta_review": True,
            },
            "inbound": {"enabled": True, "lookback_hours": 24},
        },
    }
    if overrides:
        config.update(overrides)

    (ops / "daemon-config.yaml").write_text(yaml.dump(config))
    return vault


def _mock_client(post_response: dict | None = None) -> MagicMock:
    """Create a mock SlackClient."""
    client = MagicMock()
    client.default_channel = "C_TEST"
    client.post_message.return_value = post_response or {"ok": True, "ts": "1234.0001"}
    client.get_channel_history.return_value = []
    client.get_user_name.return_value = "TestUser"
    return client


# ---------------------------------------------------------------------------
# send_notification
# ---------------------------------------------------------------------------


class TestSendNotification:
    def test_sends_session_start(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()

        result = send_notification(
            "session_start",
            vault,
            client=client,
            goals=["Test metrics"],
        )

        assert result is True
        client.post_message.assert_called()
        # First call creates the daily parent, second posts the notification
        assert client.post_message.call_count == 2

    def test_suppressed_when_disabled(self, tmp_path: Path):
        vault = _write_config(
            tmp_path,
            overrides={"notifications": {"enabled": False, "level": "all"}},
        )
        client = _mock_client()

        result = send_notification("session_start", vault, client=client)
        assert result is False
        client.post_message.assert_not_called()

    def test_suppressed_when_event_off(self, tmp_path: Path):
        vault = _write_config(
            tmp_path,
            overrides={
                "notifications": {
                    "enabled": True,
                    "level": "all",
                    "channels": {"default": "C_TEST"},
                    "events": {"session_start": False},
                }
            },
        )
        client = _mock_client()

        result = send_notification("session_start", vault, client=client)
        assert result is False

    def test_no_client_returns_false(self, tmp_path: Path):
        vault = _write_config(tmp_path)

        with patch(
            "engram_r.slack_client.SlackClient.from_env_optional",
            return_value=None,
        ):
            result = send_notification("session_start", vault)

        assert result is False

    def test_unknown_event_type(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()

        result = send_notification("nonexistent_event", vault, client=client)
        assert result is False

    def test_exception_returns_false(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()
        client.post_message.side_effect = Exception("network error")

        result = send_notification("session_start", vault, client=client)
        assert result is False

    def test_sends_daemon_alert(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()

        result = send_notification(
            "daemon_alert",
            vault,
            client=client,
            message="5 consecutive fast fails",
        )
        assert result is True

    def test_sends_daemon_task_complete(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()

        result = send_notification(
            "daemon_task_complete",
            vault,
            client=client,
            skill="tournament",
            task_key="tourn-test-001",
            model="opus",
            elapsed_s=120,
        )
        assert result is True

    def test_no_config_file_uses_defaults(self, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "ops").mkdir()
        (vault / "ops" / "daemon").mkdir()
        client = _mock_client()

        # Default config has notifications enabled, but no channel
        # Client has default_channel though
        result = send_notification("session_start", vault, client=client)
        assert result is True


# ---------------------------------------------------------------------------
# fetch_inbound_messages
# ---------------------------------------------------------------------------


class TestFetchInboundMessages:
    def test_returns_empty_when_disabled(self, tmp_path: Path):
        vault = _write_config(
            tmp_path,
            overrides={
                "notifications": {
                    "enabled": True,
                    "level": "all",
                    "channels": {"default": "C_TEST"},
                    "inbound": {"enabled": False},
                }
            },
        )
        result = fetch_inbound_messages(vault)
        assert result == ""

    def test_returns_empty_when_no_client(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        with patch(
            "engram_r.slack_client.SlackClient.from_env_optional",
            return_value=None,
        ):
            result = fetch_inbound_messages(vault)
        assert result == ""

    def test_returns_formatted_messages(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()
        client.get_channel_history.return_value = [
            SlackMessage(text="New paper on mechanisms", user="U1", ts="1234.001"),
            SlackMessage(text="Data access approved!", user="U2", ts="1234.002"),
        ]
        client.get_user_name.side_effect = lambda uid: {"U1": "Alice", "U2": "Bob"}.get(
            uid, uid
        )

        result = fetch_inbound_messages(vault, client=client)
        assert "Alice" in result
        assert "mechanisms" in result
        assert "Bob" in result

    def test_updates_last_read_state(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()
        client.get_channel_history.return_value = [
            SlackMessage(text="msg", user="U1", ts="9999.001"),
        ]

        fetch_inbound_messages(vault, client=client)

        state_path = vault / "ops" / "daemon" / "slack-last-read.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["last_read_ts"] == "9999.001"

    def test_uses_last_read_as_oldest(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        state_path = vault / "ops" / "daemon" / "slack-last-read.json"
        state_path.write_text(json.dumps({"last_read_ts": "5000.000"}))

        client = _mock_client()
        client.get_channel_history.return_value = []

        fetch_inbound_messages(vault, client=client)
        client.get_channel_history.assert_called_once()
        call_kwargs = client.get_channel_history.call_args
        assert call_kwargs[1]["oldest"] == "5000.000"

    def test_returns_empty_on_no_messages(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()
        client.get_channel_history.return_value = []

        result = fetch_inbound_messages(vault, client=client)
        assert result == ""

    def test_exception_returns_empty(self, tmp_path: Path):
        vault = _write_config(tmp_path)
        client = _mock_client()
        client.get_channel_history.side_effect = Exception("fail")

        result = fetch_inbound_messages(vault, client=client)
        assert result == ""


# ---------------------------------------------------------------------------
# _get_or_create_daily_thread
# ---------------------------------------------------------------------------


class TestDailyThread:
    def test_creates_new_thread(self, tmp_path: Path):
        vault = tmp_path / "vault"
        (vault / "ops" / "daemon").mkdir(parents=True)
        client = _mock_client({"ok": True, "ts": "1234.0001"})

        def mock_parent(d):
            return f"Activity -- {d}", []

        thread_ts = _get_or_create_daily_thread(
            vault, "C_TEST", client, mock_parent
        )
        assert thread_ts == "1234.0001"

        # Verify state file
        threads_path = vault / "ops" / "daemon" / "slack-threads.json"
        assert threads_path.exists()
        threads = json.loads(threads_path.read_text())
        today = date.today().isoformat()
        assert threads[today]["C_TEST"] == "1234.0001"

    def test_reuses_existing_thread(self, tmp_path: Path):
        vault = tmp_path / "vault"
        daemon_dir = vault / "ops" / "daemon"
        daemon_dir.mkdir(parents=True)

        today = date.today().isoformat()
        threads = {today: {"C_TEST": "existing.1234"}}
        (daemon_dir / "slack-threads.json").write_text(json.dumps(threads))

        client = _mock_client()

        thread_ts = _get_or_create_daily_thread(
            vault, "C_TEST", client, lambda d: ("", [])
        )
        assert thread_ts == "existing.1234"
        # Should NOT have posted a new parent
        client.post_message.assert_not_called()


# ---------------------------------------------------------------------------
# _prune_old_threads
# ---------------------------------------------------------------------------


class TestOutboundScrub:
    """Outbound PII scrub on notifications."""

    def test_notification_text_scrubbed(self, tmp_path: Path):
        """PII in notification text is redacted before posting."""
        vault = _write_config(tmp_path)
        client = _mock_client()

        result = send_notification(
            "daemon_alert",
            vault,
            client=client,
            message="Alert for alice@example.com: 5 fast fails",
        )
        assert result is True
        # Check the post_message call for the notification (second call, first is parent)
        calls = client.post_message.call_args_list
        # At least one call should have redacted text
        all_text = " ".join(
            str(c.args[0]) if c.args else str(c.kwargs.get("text", ""))
            for c in calls
        )
        assert "alice@example.com" not in all_text

    def test_blocks_text_scrubbed(self, tmp_path: Path):
        """PII in Slack blocks is redacted."""
        from engram_r.slack_notify import _scrub_blocks

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Contact alice@example.com for details",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "SSN: 111-22-3333"},
                ],
            },
        ]
        scrubbed = _scrub_blocks(blocks)
        assert "alice@example.com" not in scrubbed[0]["text"]["text"]
        assert "[REDACTED]" in scrubbed[0]["text"]["text"]
        assert "111-22-3333" not in scrubbed[1]["elements"][0]["text"]
        # Original blocks are NOT mutated
        assert "alice@example.com" in blocks[0]["text"]["text"]


class TestPruneOldThreads:
    def test_removes_old_entries(self):
        threads = {
            "2020-01-01": {"C1": "old.ts"},
            "2020-01-02": {"C1": "old2.ts"},
            date.today().isoformat(): {"C1": "today.ts"},
        }
        _prune_old_threads(threads, keep_days=7)
        assert "2020-01-01" not in threads
        assert "2020-01-02" not in threads
        assert date.today().isoformat() in threads

    def test_keeps_recent_entries(self):
        today = date.today().isoformat()
        threads = {today: {"C1": "ts"}}
        _prune_old_threads(threads, keep_days=7)
        assert today in threads
