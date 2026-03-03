"""Tests for engram_r.slack_client."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from engram_r.slack_client import SlackAPIError, SlackClient, SlackMessage


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_from_env_success(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_DEFAULT_CHANNEL", "C123")
        monkeypatch.setenv("SLACK_TEAM_ID", "T456")

        client = SlackClient.from_env()
        assert client.bot_token == "xoxb-test-token"
        assert client.default_channel == "C123"
        assert client.team_id == "T456"

    def test_from_env_missing_token(self, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        with pytest.raises(SlackAPIError, match="SLACK_BOT_TOKEN not set"):
            SlackClient.from_env()

    def test_from_env_optional_returns_client(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        client = SlackClient.from_env_optional()
        assert client is not None
        assert client.bot_token == "xoxb-test"

    def test_from_env_optional_returns_none(self, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        assert SlackClient.from_env_optional() is None

    def test_from_env_optional_empty_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "")
        assert SlackClient.from_env_optional() is None


# ---------------------------------------------------------------------------
# _request helper
# ---------------------------------------------------------------------------


def _make_response(data: dict, code: int = 200) -> MagicMock:
    """Create a mock urllib response."""
    body = json.dumps(data).encode("utf-8")
    mock = MagicMock()
    mock.read.return_value = body
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


class TestRequest:
    def test_successful_request(self):
        client = SlackClient(bot_token="xoxb-test")
        resp_data = {"ok": True, "ts": "1234.5678"}

        with patch("urllib.request.urlopen", return_value=_make_response(resp_data)):
            result = client._request("chat.postMessage", params={"channel": "C1"})

        assert result["ok"] is True
        assert result["ts"] == "1234.5678"

    def test_slack_api_error(self):
        client = SlackClient(bot_token="xoxb-test")
        resp_data = {"ok": False, "error": "channel_not_found"}

        with patch("urllib.request.urlopen", return_value=_make_response(resp_data)):
            with pytest.raises(SlackAPIError, match="channel_not_found"):
                client._request("chat.postMessage", params={"channel": "C1"})

    def test_http_error(self):
        client = SlackClient(bot_token="xoxb-test")
        exc = urllib.error.HTTPError(
            "https://slack.com/api/test",
            401,
            "Unauthorized",
            {},
            BytesIO(b"invalid_auth"),
        )

        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(SlackAPIError, match="HTTP 401"):
                client._request("test")

    def test_url_error(self):
        client = SlackClient(bot_token="xoxb-test")
        exc = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(SlackAPIError, match="Connection failed"):
                client._request("test")


# ---------------------------------------------------------------------------
# post_message
# ---------------------------------------------------------------------------


class TestPostMessage:
    def test_post_simple(self):
        client = SlackClient(bot_token="xoxb-test", default_channel="C123")
        resp = {"ok": True, "ts": "1234.5678"}

        with patch("urllib.request.urlopen", return_value=_make_response(resp)):
            result = client.post_message("hello")

        assert result["ts"] == "1234.5678"

    def test_post_with_thread(self):
        client = SlackClient(bot_token="xoxb-test", default_channel="C123")
        resp = {"ok": True, "ts": "1234.9999"}

        with patch("urllib.request.urlopen", return_value=_make_response(resp)) as mock:
            client.post_message("reply", thread_ts="1234.5678")
            call_args = mock.call_args
            req = call_args[0][0]
            body = json.loads(req.data)
            assert body["thread_ts"] == "1234.5678"

    def test_post_with_blocks(self):
        client = SlackClient(bot_token="xoxb-test", default_channel="C123")
        resp = {"ok": True, "ts": "1234.9999"}
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]

        with patch("urllib.request.urlopen", return_value=_make_response(resp)) as mock:
            client.post_message("hi", blocks=blocks)
            req = mock.call_args[0][0]
            body = json.loads(req.data)
            assert body["blocks"] == blocks

    def test_post_explicit_channel(self):
        client = SlackClient(bot_token="xoxb-test", default_channel="C123")
        resp = {"ok": True, "ts": "1234.9999"}

        with patch("urllib.request.urlopen", return_value=_make_response(resp)) as mock:
            client.post_message("hi", channel="C999")
            req = mock.call_args[0][0]
            body = json.loads(req.data)
            assert body["channel"] == "C999"

    def test_post_no_channel_raises(self):
        client = SlackClient(bot_token="xoxb-test")
        with pytest.raises(SlackAPIError, match="No channel specified"):
            client.post_message("hello")


# ---------------------------------------------------------------------------
# get_channel_history
# ---------------------------------------------------------------------------


class TestGetChannelHistory:
    def test_returns_messages(self):
        client = SlackClient(bot_token="xoxb-test", default_channel="C123")
        resp = {
            "ok": True,
            "messages": [
                {"text": "hello", "user": "U1", "ts": "1234.001"},
                {"text": "world", "user": "U2", "ts": "1234.002", "thread_ts": "1234.001"},
            ],
        }

        with patch("urllib.request.urlopen", return_value=_make_response(resp)):
            msgs = client.get_channel_history()

        assert len(msgs) == 2
        assert isinstance(msgs[0], SlackMessage)
        assert msgs[0].text == "hello"
        assert msgs[1].thread_ts == "1234.001"

    def test_no_channel_raises(self):
        client = SlackClient(bot_token="xoxb-test")
        with pytest.raises(SlackAPIError, match="No channel specified"):
            client.get_channel_history()


# ---------------------------------------------------------------------------
# get_thread_replies
# ---------------------------------------------------------------------------


class TestGetThreadReplies:
    def test_returns_replies(self):
        client = SlackClient(bot_token="xoxb-test")
        resp = {
            "ok": True,
            "messages": [
                {"text": "parent", "user": "U1", "ts": "1234.001"},
                {"text": "reply", "user": "U2", "ts": "1234.002"},
            ],
        }

        with patch("urllib.request.urlopen", return_value=_make_response(resp)):
            msgs = client.get_thread_replies("C123", "1234.001")

        assert len(msgs) == 2
        assert msgs[1].text == "reply"


# ---------------------------------------------------------------------------
# get_user_name
# ---------------------------------------------------------------------------


class TestGetUserName:
    def test_returns_display_name(self):
        client = SlackClient(bot_token="xoxb-test")
        resp = {
            "ok": True,
            "user": {
                "name": "jdoe",
                "profile": {"display_name": "Jane Doe", "real_name": "Jane D"},
            },
        }

        with patch("urllib.request.urlopen", return_value=_make_response(resp)):
            name = client.get_user_name("U123")

        assert name == "Jane Doe"

    def test_falls_back_to_real_name(self):
        client = SlackClient(bot_token="xoxb-test")
        resp = {
            "ok": True,
            "user": {
                "name": "jdoe",
                "profile": {"display_name": "", "real_name": "Jane D"},
            },
        }

        with patch("urllib.request.urlopen", return_value=_make_response(resp)):
            name = client.get_user_name("U123")

        assert name == "Jane D"

    def test_returns_user_id_on_error(self):
        client = SlackClient(bot_token="xoxb-test")
        resp = {"ok": False, "error": "user_not_found"}

        with patch("urllib.request.urlopen", return_value=_make_response(resp)):
            name = client.get_user_name("U999")

        assert name == "U999"


# ---------------------------------------------------------------------------
# add_reaction
# ---------------------------------------------------------------------------


class TestAddReaction:
    def test_add_reaction(self):
        client = SlackClient(bot_token="xoxb-test")
        resp = {"ok": True}

        with patch("urllib.request.urlopen", return_value=_make_response(resp)) as mock:
            client.add_reaction("thumbsup", "C123", "1234.5678")
            req = mock.call_args[0][0]
            body = json.loads(req.data)
            assert body["name"] == "thumbsup"
            assert body["channel"] == "C123"
            assert body["timestamp"] == "1234.5678"
