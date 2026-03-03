"""Two-way vault-aware Slack bot for EngramR.

Listens for DMs, @mentions, and messages in a configured channel via
Socket Mode. Responds using the Anthropic Messages API with full vault
context (goals, identity, reminders, stats).

Runs as a standalone process alongside the daemon -- does not interfere
with the existing notification system (slack_notify.py).

All public methods are wrapped in try/except -- they never raise.
Designed to be launched via ops/scripts/slack-bot.sh in tmux.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authority constants
# ---------------------------------------------------------------------------

AUTH_OWNER = "owner"
AUTH_ALLOWED = "allowed"
AUTH_PUBLIC = "public"
AUTH_DENIED = "denied"

# Default timeout for pending confirmations (seconds)
_CONFIRMATION_TIMEOUT_S = 300


# ---------------------------------------------------------------------------
# Pending confirmation for mutative skills
# ---------------------------------------------------------------------------


class PendingConfirmation(NamedTuple):
    """A mutative skill awaiting user confirmation."""

    skill: str
    args: str
    user_id: str
    auth_level: str
    channel: str
    thread_ts: str
    expires_at: float  # time.monotonic() deadline


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Sliding-window per-user rate limiter with denial cooldown."""

    def __init__(self, max_per_minute: int = 5, cooldown_s: int = 30) -> None:
        self.max_per_minute = max_per_minute
        self.cooldown_s = cooldown_s
        self._timestamps: dict[str, list[float]] = defaultdict(list)
        self._deny_until: dict[str, float] = {}

    def check(self, user_id: str) -> bool:
        """Return True if the user is within rate limits, False otherwise."""
        now = time.monotonic()

        # Check cooldown from a previous denial
        deny_until = self._deny_until.get(user_id, 0.0)
        if now < deny_until:
            return False

        # Sliding window: keep only timestamps within the last 60 seconds
        window_start = now - 60.0
        self._timestamps[user_id] = [
            ts for ts in self._timestamps[user_id] if ts > window_start
        ]

        if len(self._timestamps[user_id]) >= self.max_per_minute:
            self._deny_until[user_id] = now + self.cooldown_s
            return False

        self._timestamps[user_id].append(now)
        return True

    def reset(self, user_id: str) -> None:
        """Clear all state for a user (for testing)."""
        self._timestamps.pop(user_id, None)
        self._deny_until.pop(user_id, None)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class SlackBotConfig:
    """Configuration for the Slack bot process."""

    vault_path: Path
    slack_bot_token: str
    slack_app_token: str
    anthropic_api_key: str
    bot_channel: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_context_messages: int = 20
    max_response_tokens: int = 4096
    vault_refresh_interval_s: int = 300
    owner_ids: tuple[str, ...] = ()
    allowed_ids: tuple[str, ...] = ()
    public_access: bool = True
    rate_limit_rpm: int = 5
    rate_limit_cooldown_s: int = 30

    @classmethod
    def from_env(cls, vault_path: Path) -> SlackBotConfig:
        """Create config from environment variables and daemon-config.yaml.

        Required env vars: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, ANTHROPIC_API_KEY.
        Optional env var: SLACK_BOT_CHANNEL.

        Bot-specific settings (model, max_context_messages, etc.) are read from
        the ``bot:`` section of ops/daemon-config.yaml, with env vars taking
        precedence for channel.

        Raises:
            ValueError: If required environment variables are missing.
        """
        missing = []
        bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not bot_token:
            missing.append("SLACK_BOT_TOKEN")
        app_token = os.environ.get("SLACK_APP_TOKEN", "")
        if not app_token:
            missing.append("SLACK_APP_TOKEN")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            missing.append("ANTHROPIC_API_KEY")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        # Read daemon-config.yaml bot section for defaults
        bot_cfg = _load_bot_config(vault_path)
        auth_cfg = bot_cfg.get("authority", {})
        if not isinstance(auth_cfg, dict):
            auth_cfg = {}

        return cls(
            vault_path=vault_path,
            slack_bot_token=bot_token,
            slack_app_token=app_token,
            anthropic_api_key=api_key,
            bot_channel=os.environ.get("SLACK_BOT_CHANNEL", "")
            or bot_cfg.get("channel", ""),
            model=bot_cfg.get("model", "claude-sonnet-4-20250514"),
            max_context_messages=bot_cfg.get("max_context_messages", 20),
            max_response_tokens=bot_cfg.get("max_response_tokens", 4096),
            vault_refresh_interval_s=bot_cfg.get("vault_refresh_interval_s", 300),
            owner_ids=tuple(auth_cfg.get("owner_ids", ())),
            allowed_ids=tuple(auth_cfg.get("allowed_ids", ())),
            public_access=auth_cfg.get("public_access", True),
            rate_limit_rpm=auth_cfg.get("max_per_user_per_minute", 5),
            rate_limit_cooldown_s=auth_cfg.get("cooldown_after_deny_s", 30),
        )


def _load_bot_config(vault_path: Path) -> dict[str, Any]:
    """Load the bot section from daemon-config.yaml, returning {} on failure."""
    try:
        import yaml

        config_path = vault_path / "ops" / "daemon-config.yaml"
        if not config_path.exists():
            return {}
        raw = yaml.safe_load(config_path.read_text())
        if isinstance(raw, dict) and isinstance(raw.get("bot"), dict):
            return raw["bot"]
    except Exception:
        logger.debug("Could not read bot config from daemon-config.yaml", exc_info=True)
    return {}


# ---------------------------------------------------------------------------
# Vault context
# ---------------------------------------------------------------------------


@dataclass
class VaultContext:
    """Cached vault state used to build system prompts."""

    identity: str = ""
    methodology: str = ""
    goals: str = ""
    reminders: str = ""
    skills_summary: str = ""
    stats: str = ""


def _read_file_safe(path: Path, max_lines: int = 200) -> str:
    """Read a file, returning empty string on failure. Truncates to max_lines."""
    try:
        if not path.exists():
            return ""
        lines = path.read_text().splitlines()
        return "\n".join(lines[:max_lines])
    except Exception:
        return ""


def load_vault_context(vault_path: Path) -> VaultContext:
    """Load vault context files for the system prompt."""
    self_dir = vault_path / "self"
    ops_dir = vault_path / "ops"

    # Count notes and hypotheses for a quick stats line
    notes_dir = vault_path / "notes"
    hyp_dir = vault_path / "_research" / "hypotheses"
    note_count = len(list(notes_dir.glob("*.md"))) if notes_dir.exists() else 0
    hyp_count = len(list(hyp_dir.glob("*.md"))) if hyp_dir.exists() else 0
    stats = f"Vault: {note_count} notes, {hyp_count} hypotheses"

    return VaultContext(
        identity=_read_file_safe(self_dir / "identity.md"),
        methodology=_read_file_safe(self_dir / "methodology.md", max_lines=80),
        goals=_read_file_safe(self_dir / "goals.md"),
        reminders=_read_file_safe(ops_dir / "reminders.md"),
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------


def _merge_consecutive_roles(
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge consecutive messages with the same role.

    The Anthropic API requires alternating user/assistant roles.
    Consecutive same-role messages are joined with newlines.
    """
    if not messages:
        return []

    merged: list[dict[str, str]] = [messages[0].copy()]
    for msg in messages[1:]:
        if msg["role"] == merged[-1]["role"]:
            merged[-1]["content"] += "\n" + msg["content"]
        else:
            merged.append(msg.copy())
    return merged


# ---------------------------------------------------------------------------
# SlackBot
# ---------------------------------------------------------------------------


@dataclass
class SlackBot:
    """Two-way vault-aware Slack assistant.

    Args:
        config: Bot configuration.
        app: Optional pre-built slack_bolt.App (for testing).
        anthropic_client: Optional pre-built anthropic.Anthropic (for testing).
    """

    config: SlackBotConfig
    app: Any = field(default=None, repr=False)
    anthropic_client: Any = field(default=None, repr=False)
    _bot_user_id: str = field(default="", init=False, repr=False)
    _vault_context: VaultContext = field(
        default_factory=VaultContext, init=False, repr=False
    )
    _refresh_timer: threading.Timer | None = field(default=None, init=False, repr=False)
    _rate_limiter: RateLimiter = field(init=False, repr=False)
    _owner_ids: set[str] = field(init=False, repr=False)
    _allowed_ids: set[str] = field(init=False, repr=False)
    _pending_confirmations: dict[str, PendingConfirmation] = field(
        default_factory=dict, init=False, repr=False
    )
    _skills_enabled: bool = field(default=False, init=False, repr=False)
    _confirm_mutative: bool = field(default=True, init=False, repr=False)
    _confirmation_timeout_s: int = field(
        default=_CONFIRMATION_TIMEOUT_S, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._rate_limiter = RateLimiter(
            max_per_minute=self.config.rate_limit_rpm,
            cooldown_s=self.config.rate_limit_cooldown_s,
        )
        self._owner_ids = set(self.config.owner_ids)
        self._allowed_ids = set(self.config.allowed_ids)

        # Load skill routing config from daemon-config.yaml
        bot_cfg = _load_bot_config(self.config.vault_path)
        skills_cfg = bot_cfg.get("skills", {})
        if isinstance(skills_cfg, dict):
            self._skills_enabled = bool(skills_cfg.get("enabled", False))
            self._confirm_mutative = bool(skills_cfg.get("confirm_mutative", True))
            self._confirmation_timeout_s = int(
                skills_cfg.get("confirmation_timeout_s", _CONFIRMATION_TIMEOUT_S)
            )

        if self.app is None:
            from slack_bolt import App

            self.app = App(token=self.config.slack_bot_token)

        if self.anthropic_client is None:
            import anthropic

            self.anthropic_client = anthropic.Anthropic(
                api_key=self.config.anthropic_api_key
            )

        # Register event handlers -- separate handlers to avoid routing conflicts
        self.app.event("app_mention")(self._handle_mention)
        self.app.event("message")(self._handle_message)

        # Log all unhandled events for debugging
        @self.app.middleware
        def _log_all_events(body, next):
            event = body.get("event", {})
            etype = event.get("type", "unknown")
            esubtype = event.get("subtype", "")
            logger.debug(
                "Incoming event: type=%s subtype=%s user=%s channel=%s",
                etype,
                esubtype,
                event.get("user", ""),
                event.get("channel", ""),
            )
            next()

        # Load initial vault context
        self.refresh_vault_context()

    def start(self) -> None:
        """Start the bot (blocking). Connects via Socket Mode."""
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        # Resolve bot identity
        try:
            auth = self.app.client.auth_test()
            self._bot_user_id = auth.get("user_id", "")
            logger.info("Bot identity resolved: %s", self._bot_user_id)
        except Exception:
            logger.warning("Could not resolve bot identity via auth.test")

        # Start periodic vault refresh
        self._schedule_vault_refresh()

        logger.info("Starting Slack bot via Socket Mode...")
        handler = SocketModeHandler(self.app, self.config.slack_app_token)
        handler.start()

    # -- Event handling -----------------------------------------------------

    def _handle_mention(self, event: dict[str, Any], say: Any, client: Any) -> None:
        """Handle app_mention events. Delegates to the shared handler."""
        logger.info("app_mention event received from user=%s", event.get("user", ""))
        self._process_event(event, say, client)

    def _handle_message(self, event: dict[str, Any], say: Any, client: Any) -> None:
        """Handle message events (DMs, bot channel). Skips @mentions (handled above)."""
        # Skip if this is an @mention -- already handled by _handle_mention
        text = event.get("text", "")
        if self._bot_user_id and f"<@{self._bot_user_id}>" in text:
            channel_type = event.get("channel_type", "")
            if channel_type != "im":
                return
        logger.info(
            "message event received: user=%s channel_type=%s",
            event.get("user", ""),
            event.get("channel_type", ""),
        )
        self._process_event(event, say, client)

    def _authorize(self, user_id: str) -> str:
        """Return the authorization level for a Slack user ID.

        Returns AUTH_OWNER, AUTH_ALLOWED, AUTH_PUBLIC, or AUTH_DENIED.
        When no owner_ids and no allowed_ids are configured and
        public_access is True (the default), all users get AUTH_PUBLIC.
        """
        if user_id in self._owner_ids:
            return AUTH_OWNER
        if user_id in self._allowed_ids:
            return AUTH_ALLOWED
        if self.config.public_access:
            return AUTH_PUBLIC
        return AUTH_DENIED

    def _process_event(self, event: dict[str, Any], say: Any, client: Any) -> None:
        """Shared handler for message and app_mention events."""
        try:
            if not self._should_respond(event):
                return

            # Authority check
            user_id = event.get("user", "")
            auth_level = self._authorize(user_id)
            logger.info("Authority check: user=%s level=%s", user_id, auth_level)
            if auth_level == AUTH_DENIED:
                thread_ts = event.get("thread_ts") or event.get("ts", "")
                say(
                    text="Sorry, you are not authorized to use this bot.",
                    thread_ts=thread_ts,
                )
                return

            # Rate limit check
            if not self._rate_limiter.check(user_id):
                logger.info("Rate limit exceeded for user=%s", user_id)
                thread_ts = event.get("thread_ts") or event.get("ts", "")
                say(
                    text="You are sending messages too quickly. Please wait a moment.",
                    thread_ts=thread_ts,
                )
                return

            channel = event.get("channel", "")
            thread_ts = event.get("thread_ts") or event.get("ts", "")
            user_text = event.get("text", "")

            # Strip bot mention from text
            if self._bot_user_id:
                user_text = user_text.replace(f"<@{self._bot_user_id}>", "").strip()

            # -- Check for pending confirmation in this thread --
            if self._skills_enabled:
                confirm_key = f"{channel}:{thread_ts}"
                pending = self._pending_confirmations.get(confirm_key)
                if pending is not None:
                    handled = self._handle_confirmation(
                        pending, confirm_key, user_text, user_id, say
                    )
                    if handled:
                        return

            # Add thinking reaction
            with contextlib.suppress(Exception):
                client.reactions_add(
                    name="thinking_face",
                    channel=channel,
                    timestamp=event.get("ts", ""),
                )

            # -- Check for explicit /command --
            skill_handled = False
            if self._skills_enabled:
                from engram_r.slack_skill_router import detect_explicit_command

                skill, args = detect_explicit_command(user_text)
                if skill:
                    skill_handled = self._handle_skill_request(
                        skill, args, user_id, auth_level, channel, thread_ts, say
                    )

            if not skill_handled:
                # Build thread context
                thread_messages = self._build_thread_context(
                    client, channel, thread_ts, user_text
                )

                # Build system prompt
                system = self.build_system_prompt()

                # Call Claude
                response_text = self._call_claude(thread_messages, system)

                # -- Check for NL intent in Claude response --
                if self._skills_enabled:
                    from engram_r.slack_skill_router import extract_skill_intent

                    intent_skill, intent_args, cleaned = extract_skill_intent(
                        response_text
                    )
                    if intent_skill:
                        response_text = cleaned
                        self._handle_skill_request(
                            intent_skill,
                            intent_args or "",
                            user_id,
                            auth_level,
                            channel,
                            thread_ts,
                            say,
                        )

                # Scrub PII from outbound response (non-negotiable boundary)
                from engram_r.pii_filter import scrub_outbound

                response_text = scrub_outbound(response_text)

                # Split long responses (Slack limit ~4000 chars per message)
                if response_text:
                    chunks = _split_message(response_text, max_len=3900)
                    for chunk in chunks:
                        say(text=chunk, thread_ts=thread_ts)

            # Remove thinking reaction, add done
            try:
                client.reactions_remove(
                    name="thinking_face",
                    channel=channel,
                    timestamp=event.get("ts", ""),
                )
                client.reactions_add(
                    name="white_check_mark",
                    channel=channel,
                    timestamp=event.get("ts", ""),
                )
            except Exception:
                pass  # Non-critical

        except Exception:
            logger.exception("Error handling message event")
            with contextlib.suppress(Exception):
                say(
                    text="Sorry, I encountered an error processing your message.",
                    thread_ts=event.get("thread_ts") or event.get("ts", ""),
                )

    # -- Skill routing helpers -----------------------------------------------

    def _handle_skill_request(
        self,
        skill: str,
        args: str,
        user_id: str,
        auth_level: str,
        channel: str,
        thread_ts: str,
        say: Any,
    ) -> bool:
        """Route a skill request through permission check and queue.

        Returns True if the skill was handled (queued or denied).
        """
        from engram_r.slack_formatter import format_slack_skill_queued
        from engram_r.slack_skill_router import (
            SKILL_SAFETY_TIERS,
            check_permission,
            queue_request,
        )

        allowed, reason = check_permission(skill, auth_level)
        if not allowed:
            say(text=reason, thread_ts=thread_ts)
            return True

        safety_tier = SKILL_SAFETY_TIERS.get(skill, "mutative")

        # Mutative skills require confirmation if configured
        if safety_tier == "mutative" and self._confirm_mutative:
            confirm_key = f"{channel}:{thread_ts}"
            self._pending_confirmations[confirm_key] = PendingConfirmation(
                skill=skill,
                args=args,
                user_id=user_id,
                auth_level=auth_level,
                channel=channel,
                thread_ts=thread_ts,
                expires_at=time.monotonic() + self._confirmation_timeout_s,
            )
            say(
                text=(
                    f"/{skill} is a mutative operation. "
                    f"Reply *yes* to confirm or *no* to cancel."
                ),
                thread_ts=thread_ts,
            )
            return True

        # Queue immediately for read/maintenance skills
        entry_id = queue_request(
            self.config.vault_path,
            skill,
            args,
            user_id,
            auth_level,
            channel,
            thread_ts,
        )

        text, blocks = format_slack_skill_queued(skill=skill, entry_id=entry_id)
        say(text=text, thread_ts=thread_ts)
        return True

    def _handle_confirmation(
        self,
        pending: PendingConfirmation,
        confirm_key: str,
        user_text: str,
        user_id: str,
        say: Any,
    ) -> bool:
        """Handle a yes/no reply to a pending confirmation.

        Returns True if the message was consumed as a confirmation response.
        """
        # Check expiry
        if time.monotonic() > pending.expires_at:
            self._pending_confirmations.pop(confirm_key, None)
            say(
                text="Confirmation expired. Please re-issue the command.",
                thread_ts=pending.thread_ts,
            )
            return True

        # Only the original requester can confirm
        if user_id != pending.user_id:
            return False

        normalized = user_text.strip().lower()
        if normalized in ("yes", "y", "confirm"):
            self._pending_confirmations.pop(confirm_key, None)

            from engram_r.slack_formatter import format_slack_skill_queued
            from engram_r.slack_skill_router import queue_request

            entry_id = queue_request(
                self.config.vault_path,
                pending.skill,
                pending.args,
                pending.user_id,
                pending.auth_level,
                pending.channel,
                pending.thread_ts,
            )
            text, blocks = format_slack_skill_queued(
                skill=pending.skill, entry_id=entry_id
            )
            say(text=text, thread_ts=pending.thread_ts)
            return True

        if normalized in ("no", "n", "cancel"):
            self._pending_confirmations.pop(confirm_key, None)
            say(text="Cancelled.", thread_ts=pending.thread_ts)
            return True

        # Not a confirmation response -- let it fall through
        return False

    def _should_respond(self, event: dict[str, Any]) -> bool:
        """Determine whether the bot should respond to this event.

        Responds to:
        - Direct messages (channel_type == 'im')
        - @mentions (text contains bot user ID)
        - Messages in the configured bot_channel

        Skips:
        - Messages from the bot itself
        - Messages with subtypes (joins, leaves, etc.) except bot_message
        """
        # Skip own messages
        user = event.get("user", "")
        if self._bot_user_id and user == self._bot_user_id:
            return False

        # Skip bot_id messages (from other integrations or self)
        if event.get("bot_id"):
            return False

        # Skip message subtypes (join/leave/topic etc.)
        subtype = event.get("subtype", "")
        if subtype:
            return False

        # Direct messages
        channel_type = event.get("channel_type", "")
        if channel_type == "im":
            return True

        # @mention
        text = event.get("text", "")
        if self._bot_user_id and f"<@{self._bot_user_id}>" in text:
            return True

        # Bot channel
        channel = event.get("channel", "")
        return bool(self.config.bot_channel and channel == self.config.bot_channel)

    def _build_thread_context(
        self,
        client: Any,
        channel: str,
        thread_ts: str,
        current_text: str,
    ) -> list[dict[str, str]]:
        """Build conversation context from thread history.

        Fetches thread replies, maps bot messages to assistant role and
        all others to user role, merges consecutive same-role messages,
        and caps at max_context_messages.

        Falls back to just the current message on API errors.
        """
        messages: list[dict[str, str]] = []

        try:
            result = client.conversations_replies(channel=channel, ts=thread_ts)
            thread_msgs = result.get("messages", [])

            for msg in thread_msgs:
                msg_user = msg.get("user", "")
                msg_text = msg.get("text", "")

                # Strip bot mention from text
                if self._bot_user_id:
                    msg_text = msg_text.replace(f"<@{self._bot_user_id}>", "").strip()

                if not msg_text:
                    continue

                if self._bot_user_id and msg_user == self._bot_user_id:
                    role = "assistant"
                else:
                    role = "user"

                messages.append({"role": role, "content": msg_text})

        except Exception:
            logger.debug("Could not fetch thread replies, using current message only")
            if current_text:
                messages = [{"role": "user", "content": current_text}]

        if not messages:
            if current_text:
                messages = [{"role": "user", "content": current_text}]
            else:
                return []

        # Cap at max_context_messages
        messages = messages[-self.config.max_context_messages :]

        # Merge consecutive same-role messages
        messages = _merge_consecutive_roles(messages)

        # Ensure conversation starts with user
        if messages and messages[0]["role"] != "user":
            messages = messages[1:]

        # Ensure conversation ends with user
        if messages and messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": "(waiting for response)"})

        return messages

    def build_system_prompt(self) -> str:
        """Assemble the system prompt from cached vault context."""
        ctx = self._vault_context
        sections = []

        sections.append(
            "You are a research assistant for a research knowledge vault "
            "(EngramR). You help the researcher with questions about their "
            "research goals, hypotheses, vault contents, and general science. "
            "Be concise and direct. Use markdown formatting."
        )

        if ctx.identity:
            sections.append(f"## Identity\n{ctx.identity}")

        if ctx.goals:
            sections.append(f"## Current Research Goals\n{ctx.goals}")

        if ctx.reminders:
            sections.append(f"## Active Reminders\n{ctx.reminders}")

        if ctx.stats:
            sections.append(f"## Vault Stats\n{ctx.stats}")

        if ctx.methodology:
            sections.append(f"## Methodology (abbreviated)\n{ctx.methodology}")

        if self._skills_enabled:
            from engram_r.slack_skill_router import SLACK_ALLOWED_SKILLS

            skill_list = ", ".join(sorted(SLACK_ALLOWED_SKILLS))
            sections.append(
                "## Skill Detection\n"
                "If the user's message implies they want to run a vault skill, "
                "include a skill-intent block in your response:\n"
                "<skill-intent>skill: SKILL_NAME args: OPTIONAL_ARGS</skill-intent>\n"
                f"Available skills: {skill_list}\n"
                "Only include this block when the intent is clear. "
                "Always provide a natural language response alongside it."
            )

        return "\n\n".join(sections)

    def refresh_vault_context(self) -> None:
        """Re-read vault files into the cached context."""
        try:
            self._vault_context = load_vault_context(self.config.vault_path)
            logger.debug("Vault context refreshed")
        except Exception:
            logger.exception("Failed to refresh vault context")

    def _schedule_vault_refresh(self) -> None:
        """Schedule periodic vault context refresh."""
        interval = self.config.vault_refresh_interval_s
        if interval <= 0:
            return

        def _refresh_loop() -> None:
            self.refresh_vault_context()
            self._refresh_timer = threading.Timer(interval, _refresh_loop)
            self._refresh_timer.daemon = True
            self._refresh_timer.start()

        self._refresh_timer = threading.Timer(interval, _refresh_loop)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    # -- Claude API ---------------------------------------------------------

    def _call_claude(
        self,
        messages: list[dict[str, str]],
        system: str,
    ) -> str:
        """Call the Anthropic Messages API. Returns text or error message."""
        try:
            response = self.anthropic_client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_response_tokens,
                system=system,
                messages=messages,
            )
            # Extract text from response content blocks
            parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
            return "\n".join(parts) if parts else "(empty response)"

        except Exception as exc:
            logger.exception("Claude API call failed")
            # Return a user-friendly message; full details are in the logs
            err_type = type(exc).__name__
            return (
                f"Sorry, I could not generate a response ({err_type}). "
                "Check the bot logs for details."
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_message(text: str, max_len: int = 3900) -> list[str]:
    """Split a message into chunks that fit Slack's character limit."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        # Try to split at a newline
        split_at = text.rfind("\n", 0, max_len)
        if split_at <= 0:
            # Fall back to space
            split_at = text.rfind(" ", 0, max_len)
        if split_at <= 0:
            split_at = max_len

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for the Slack bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    vault_path = Path(os.environ.get("VAULT_PATH", Path.cwd()))
    config = SlackBotConfig.from_env(vault_path)
    bot = SlackBot(config=config)
    bot.start()


if __name__ == "__main__":
    main()
