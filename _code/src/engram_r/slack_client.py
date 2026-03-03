"""Slack Web API client for EngramR notifications.

Handles posting messages, reading channel history, and thread management
via the Slack Web API. Stdlib-only (urllib) -- no third-party dependencies.

Follows the same pattern as obsidian_client.py: @dataclass with from_env()
and from_env_optional() factory methods.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


class SlackAPIError(Exception):
    """Error communicating with the Slack Web API."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


@dataclass
class SlackMessage:
    """A single Slack message."""

    text: str
    user: str
    ts: str
    thread_ts: str | None = None
    blocks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SlackClient:
    """Client for the Slack Web API.

    Args:
        bot_token: Bot User OAuth Token (xoxb-...).
        default_channel: Default channel ID to post to.
        team_id: Slack workspace team ID (optional, for reference).
    """

    bot_token: str
    default_channel: str = ""
    team_id: str = ""

    @classmethod
    def from_env(cls) -> SlackClient:
        """Create client from environment variables.

        Reads SLACK_BOT_TOKEN, SLACK_DEFAULT_CHANNEL, SLACK_TEAM_ID.

        Raises:
            SlackAPIError: If SLACK_BOT_TOKEN is not set.
        """
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            raise SlackAPIError("SLACK_BOT_TOKEN not set in environment")
        return cls(
            bot_token=token,
            default_channel=os.environ.get("SLACK_DEFAULT_CHANNEL", ""),
            team_id=os.environ.get("SLACK_TEAM_ID", ""),
        )

    @classmethod
    def from_env_optional(cls) -> SlackClient | None:
        """Create client from environment variables, returning None if unconfigured.

        Returns None when SLACK_BOT_TOKEN is missing instead of raising.
        Designed for hooks that should silently skip when Slack is not set up.
        """
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            return None
        return cls(
            bot_token=token,
            default_channel=os.environ.get("SLACK_DEFAULT_CHANNEL", ""),
            team_id=os.environ.get("SLACK_TEAM_ID", ""),
        )

    def _request(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP POST request to the Slack Web API.

        Args:
            method: Slack API method (e.g. 'chat.postMessage').
            params: JSON body parameters.

        Returns:
            Parsed JSON response dict.

        Raises:
            SlackAPIError: On HTTP errors or Slack API errors (ok=false).
        """
        url = f"{SLACK_API_BASE}/{method}"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        body = json.dumps(params or {}).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise SlackAPIError(f"{method} -> HTTP {exc.code}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise SlackAPIError(f"{method} -> Connection failed: {exc.reason}") from exc

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            raise SlackAPIError(f"{method} -> Slack error: {error}", error_code=error)

        return data

    def post_message(
        self,
        text: str,
        channel: str = "",
        *,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Post a message to a Slack channel.

        Args:
            text: Fallback text (also used for notifications).
            channel: Channel ID. Falls back to default_channel.
            blocks: Optional Block Kit blocks for rich formatting.
            thread_ts: Parent message timestamp to reply in a thread.

        Returns:
            Slack API response dict (includes 'ts' of the posted message).

        Raises:
            SlackAPIError: If channel is not specified and no default is set.
        """
        ch = channel or self.default_channel
        if not ch:
            raise SlackAPIError(
                "No channel specified and no default_channel configured"
            )

        params: dict[str, Any] = {"channel": ch, "text": text}
        if blocks:
            params["blocks"] = blocks
        if thread_ts:
            params["thread_ts"] = thread_ts

        return self._request("chat.postMessage", params=params)

    def get_channel_history(
        self,
        channel: str = "",
        *,
        oldest: str = "",
        limit: int = 100,
    ) -> list[SlackMessage]:
        """Fetch recent messages from a channel.

        Args:
            channel: Channel ID. Falls back to default_channel.
            oldest: Only messages after this Unix timestamp.
            limit: Maximum number of messages to return (max 1000).

        Returns:
            List of SlackMessage objects, newest first.
        """
        ch = channel or self.default_channel
        if not ch:
            raise SlackAPIError(
                "No channel specified and no default_channel configured"
            )

        params: dict[str, Any] = {"channel": ch, "limit": min(limit, 1000)}
        if oldest:
            params["oldest"] = oldest

        data = self._request("conversations.history", params=params)
        messages = data.get("messages", [])
        return [
            SlackMessage(
                text=m.get("text", ""),
                user=m.get("user", ""),
                ts=m.get("ts", ""),
                thread_ts=m.get("thread_ts"),
                blocks=m.get("blocks", []),
            )
            for m in messages
        ]

    def get_thread_replies(
        self,
        channel: str,
        thread_ts: str,
    ) -> list[SlackMessage]:
        """Fetch replies in a thread.

        Args:
            channel: Channel ID containing the thread.
            thread_ts: Timestamp of the parent message.

        Returns:
            List of SlackMessage objects (includes parent).
        """
        data = self._request(
            "conversations.replies",
            params={"channel": channel, "ts": thread_ts},
        )
        messages = data.get("messages", [])
        return [
            SlackMessage(
                text=m.get("text", ""),
                user=m.get("user", ""),
                ts=m.get("ts", ""),
                thread_ts=m.get("thread_ts"),
                blocks=m.get("blocks", []),
            )
            for m in messages
        ]

    def get_user_name(self, user_id: str) -> str:
        """Resolve a Slack user ID to a display name.

        Args:
            user_id: Slack user ID (e.g. 'U0123456789').

        Returns:
            Display name, or the user_id if resolution fails.
        """
        try:
            data = self._request("users.info", params={"user": user_id})
            user = data.get("user", {})
            profile = user.get("profile", {})
            return (
                profile.get("display_name")
                or profile.get("real_name")
                or user.get("name", user_id)
            )
        except SlackAPIError:
            return user_id

    def open_dm(self, user_id: str) -> str | None:
        """Open a direct message channel with a user.

        Uses conversations.open to get or create a DM channel.

        Args:
            user_id: Slack user ID (e.g. 'U0123456789').

        Returns:
            DM channel ID, or None if the API call fails.
        """
        try:
            data = self._request("conversations.open", params={"users": user_id})
            channel = data.get("channel", {})
            return channel.get("id") if isinstance(channel, dict) else None
        except SlackAPIError:
            logger.warning("Failed to open DM with user %s", user_id)
            return None

    def add_reaction(
        self,
        name: str,
        channel: str,
        timestamp: str,
    ) -> dict[str, Any]:
        """Add a reaction emoji to a message.

        Args:
            name: Emoji name without colons (e.g. 'white_check_mark').
            channel: Channel ID containing the message.
            timestamp: Timestamp of the message to react to.

        Returns:
            Slack API response dict.
        """
        return self._request(
            "reactions.add",
            params={"name": name, "channel": channel, "timestamp": timestamp},
        )
