"""High-level Slack notification dispatch for EngramR.

Orchestrates SlackClient, slack_formatter, and daemon_config to send
notifications for vault events. Maintains daily threading via a JSON
state file.

All public functions are wrapped in try/except -- they never raise.
Designed to be called from hooks and daemon scripts without risk of
crashing the caller.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def send_notification(
    event_type: str,
    vault_path: Path,
    *,
    client: Any | None = None,
    **kwargs: Any,
) -> bool:
    """Send a Slack notification for a vault event.

    Loads config, checks should_notify(), resolves channel, formats the
    message, and posts it. Uses daily threading: first notification of
    the day posts a parent message, subsequent ones reply in thread.

    Args:
        event_type: One of the NotificationEvents field names
            (e.g. 'session_start', 'daemon_task_complete').
        vault_path: Path to the vault root.
        client: Optional pre-built SlackClient (for testing).
        **kwargs: Event-specific data passed to the formatter.

    Returns:
        True if the notification was sent, False otherwise.
    """
    try:
        from engram_r.daemon_config import load_config
        from engram_r.slack_client import SlackClient
        from engram_r.slack_formatter import (
            format_daemon_alert,
            format_daemon_for_you,
            format_daemon_task_complete,
            format_daily_parent,
            format_meta_review,
            format_session_end,
            format_session_start,
            format_tournament_result,
        )

        # Load config
        config_path = vault_path / "ops" / "daemon-config.yaml"
        if config_path.exists():
            config = load_config(config_path)
        else:
            from engram_r.daemon_config import DaemonConfig

            config = DaemonConfig()

        notif = config.notifications
        if not notif.should_notify(event_type):
            logger.debug("Notification suppressed for event: %s", event_type)
            return False

        # Get or create client
        if client is None:
            client = SlackClient.from_env_optional()
        if client is None:
            logger.debug("Slack not configured, skipping notification")
            return False

        # Resolve channel
        channel = notif.channels.for_event(event_type)
        if not channel and client.default_channel:
            channel = client.default_channel
        if not channel:
            logger.warning("No channel configured for event: %s", event_type)
            return False

        # Format the message
        formatters = {
            "session_start": format_session_start,
            "session_end": format_session_end,
            "daemon_task_complete": format_daemon_task_complete,
            "daemon_alert": format_daemon_alert,
            "daemon_for_you": format_daemon_for_you,
            "tournament_result": format_tournament_result,
            "meta_review": format_meta_review,
        }

        formatter = formatters.get(event_type)
        if formatter is None:
            logger.warning("No formatter for event type: %s", event_type)
            return False

        text, blocks = formatter(**kwargs)

        # Scrub PII from outbound notification (non-negotiable boundary)
        from engram_r.pii_filter import scrub_outbound

        text = scrub_outbound(text)
        if blocks:
            blocks = _scrub_blocks(blocks)

        # Get or create daily thread
        thread_ts = _get_or_create_daily_thread(
            vault_path, channel, client, format_daily_parent
        )

        # Post the message
        client.post_message(text, channel=channel, blocks=blocks, thread_ts=thread_ts)
        return True

    except Exception:
        logger.exception("Failed to send Slack notification for %s", event_type)
        return False


def fetch_inbound_messages(
    vault_path: Path,
    *,
    client: Any | None = None,
) -> str:
    """Fetch recent Slack messages for session orientation.

    Reads the last-read timestamp from state, fetches new messages,
    resolves user names, and returns formatted text for the orientation
    block.

    Args:
        vault_path: Path to the vault root.
        client: Optional pre-built SlackClient (for testing).

    Returns:
        Formatted text string (empty if nothing new or on error).
    """
    try:
        from engram_r.daemon_config import load_config
        from engram_r.slack_client import SlackClient
        from engram_r.slack_formatter import format_inbound_summary

        # Load config
        config_path = vault_path / "ops" / "daemon-config.yaml"
        if config_path.exists():
            config = load_config(config_path)
        else:
            from engram_r.daemon_config import DaemonConfig

            config = DaemonConfig()

        inbound = config.notifications.inbound
        if not inbound.enabled:
            return ""

        # Get or create client
        if client is None:
            client = SlackClient.from_env_optional()
        if client is None:
            return ""

        # Determine channel
        channel = inbound.channel or config.notifications.channels.default
        if not channel and client.default_channel:
            channel = client.default_channel
        if not channel:
            return ""

        # Read last-read state
        state_path = vault_path / "ops" / "daemon" / "slack-last-read.json"
        oldest = ""
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                oldest = state.get("last_read_ts", "")
            except (json.JSONDecodeError, OSError):
                pass

        # Fallback: lookback_hours
        if not oldest:
            cutoff = datetime.now(UTC) - timedelta(hours=inbound.lookback_hours)
            oldest = str(cutoff.timestamp())

        # Fetch messages
        messages = client.get_channel_history(channel=channel, oldest=oldest, limit=50)

        if not messages:
            return ""

        # Resolve user names and format
        formatted_msgs = []
        for msg in messages:
            user_name = client.get_user_name(msg.user) if msg.user else "bot"
            formatted_msgs.append({"user": user_name, "text": msg.text, "ts": msg.ts})

        # Update last-read state
        newest_ts = max(m.ts for m in messages)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"last_read_ts": newest_ts}, ensure_ascii=False)
        state_path.write_text(payload)

        return format_inbound_summary(formatted_msgs, channel_name=channel)

    except Exception:
        logger.exception("Failed to fetch inbound Slack messages")
        return ""


def _scrub_blocks(blocks: list[dict]) -> list[dict]:
    """Deep-copy Slack blocks and redact PII from text fields."""
    import copy

    from engram_r.pii_filter import scrub_outbound

    cleaned = copy.deepcopy(blocks)
    for block in cleaned:
        block_type = block.get("type", "")
        # Section blocks have a text field
        if block_type == "section":
            text_obj = block.get("text")
            if isinstance(text_obj, dict) and "text" in text_obj:
                text_obj["text"] = scrub_outbound(text_obj["text"])
        # Context blocks have elements with text
        elif block_type == "context":
            for elem in block.get("elements", []):
                if isinstance(elem, dict) and "text" in elem:
                    elem["text"] = scrub_outbound(elem["text"])
        # Header blocks have a text field
        elif block_type == "header":
            text_obj = block.get("text")
            if isinstance(text_obj, dict) and "text" in text_obj:
                text_obj["text"] = scrub_outbound(text_obj["text"])
    return cleaned


def _get_or_create_daily_thread(
    vault_path: Path,
    channel: str,
    client: Any,
    format_parent_fn: Any,
) -> str | None:
    """Get or create the daily parent thread for a channel.

    Maintains a JSON file at ops/daemon/slack-threads.json mapping:
        {date: {channel_id: thread_ts}}

    Args:
        vault_path: Path to the vault root.
        channel: Channel ID.
        client: SlackClient instance.
        format_parent_fn: Function that creates the parent message.

    Returns:
        thread_ts of the daily parent, or None if it could not be created.
    """
    threads_path = vault_path / "ops" / "daemon" / "slack-threads.json"
    today = date.today().isoformat()

    # Load existing threads
    threads: dict[str, dict[str, str]] = {}
    if threads_path.exists():
        try:
            threads = json.loads(threads_path.read_text())
        except (json.JSONDecodeError, OSError):
            threads = {}

    # Check if today's thread exists for this channel
    day_threads = threads.get(today, {})
    if channel in day_threads:
        return day_threads[channel]

    # Create new daily parent
    try:
        text, blocks = format_parent_fn(today)
        resp = client.post_message(text, channel=channel, blocks=blocks)
        thread_ts = resp.get("ts", "")

        if thread_ts:
            if today not in threads:
                threads[today] = {}
            threads[today][channel] = thread_ts

            # Prune old dates (keep last 7 days)
            _prune_old_threads(threads, keep_days=7)

            # Save
            threads_path.parent.mkdir(parents=True, exist_ok=True)
            threads_path.write_text(json.dumps(threads, indent=2, ensure_ascii=False))

            return thread_ts
    except Exception:
        logger.exception("Failed to create daily thread for %s", channel)

    return None


def _prune_old_threads(threads: dict[str, dict[str, str]], keep_days: int = 7) -> None:
    """Remove thread entries older than keep_days from the dict in-place."""
    cutoff = (date.today() - timedelta(days=keep_days)).isoformat()
    old_keys = [k for k in threads if k < cutoff]
    for k in old_keys:
        del threads[k]
