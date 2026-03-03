"""Tests for the two-way vault-aware Slack bot."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engram_r.slack_bot import (
    AUTH_ALLOWED,
    AUTH_DENIED,
    AUTH_OWNER,
    AUTH_PUBLIC,
    PendingConfirmation,
    RateLimiter,
    SlackBot,
    SlackBotConfig,
    VaultContext,
    _merge_consecutive_roles,
    _split_message,
    load_vault_context,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure for testing."""
    (tmp_path / "self").mkdir()
    (tmp_path / "ops").mkdir()
    (tmp_path / "notes").mkdir()
    (tmp_path / "_research" / "hypotheses").mkdir(parents=True)

    (tmp_path / "self" / "identity.md").write_text("# Identity\nI am the agent.")
    (tmp_path / "self" / "methodology.md").write_text("# Methodology\nIterative.")
    (tmp_path / "self" / "goals.md").write_text("# Goals\n## Test analysis\nActive.")
    (tmp_path / "ops" / "reminders.md").write_text("- [ ] Submit data access request")

    # Create some notes and hypotheses
    for i in range(5):
        (tmp_path / "notes" / f"note-{i}.md").write_text(f"Note {i}")
    for i in range(3):
        (tmp_path / "_research" / "hypotheses" / f"H-{i}.md").write_text(f"H {i}")

    return tmp_path


@pytest.fixture()
def config(vault: Path) -> SlackBotConfig:
    """Create a test config."""
    return SlackBotConfig(
        vault_path=vault,
        slack_bot_token="xoxb-test-token",
        slack_app_token="xapp-test-token",
        anthropic_api_key="sk-ant-test-key",
        bot_channel="C_BOT_CHAN",
        model="claude-sonnet-4-20250514",
        max_context_messages=10,
        max_response_tokens=1024,
        vault_refresh_interval_s=0,  # Disable timer in tests
    )


def _mock_anthropic_response(text: str = "Hello from Claude") -> MagicMock:
    """Create a mock Anthropic API response."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


@pytest.fixture()
def mock_app() -> MagicMock:
    """Create a mock slack_bolt App."""
    app = MagicMock()
    # event() should return a decorator that accepts a handler
    app.event = MagicMock(side_effect=lambda event_name: lambda fn: fn)
    app.client.auth_test.return_value = {"user_id": "U_BOT"}
    return app


@pytest.fixture()
def mock_anthropic() -> MagicMock:
    """Create a mock Anthropic client."""
    client = MagicMock()
    client.messages.create.return_value = _mock_anthropic_response()
    return client


@pytest.fixture()
def bot(
    config: SlackBotConfig, mock_app: MagicMock, mock_anthropic: MagicMock
) -> SlackBot:
    """Create a SlackBot with mocked dependencies."""
    b = SlackBot(config=config, app=mock_app, anthropic_client=mock_anthropic)
    b._bot_user_id = "U_BOT"
    return b


# ---------------------------------------------------------------------------
# Config factory tests
# ---------------------------------------------------------------------------


class TestSlackBotConfig:
    def test_from_env_success(self, vault: Path) -> None:
        env = {
            "SLACK_BOT_TOKEN": "xoxb-test",
            "SLACK_APP_TOKEN": "xapp-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "SLACK_BOT_CHANNEL": "C_CHAN",
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = SlackBotConfig.from_env(vault)
        assert cfg.slack_bot_token == "xoxb-test"
        assert cfg.slack_app_token == "xapp-test"
        assert cfg.anthropic_api_key == "sk-ant-test"
        assert cfg.bot_channel == "C_CHAN"

    def test_from_env_missing_vars_raises(self, vault: Path) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(ValueError, match="SLACK_BOT_TOKEN"),
        ):
            SlackBotConfig.from_env(vault)

    def test_from_env_reads_daemon_config(self, vault: Path) -> None:
        # Write a daemon-config with bot section
        config_yaml = (
            "bot:\n" "  model: claude-opus-4-20250514\n" "  max_context_messages: 50\n"
        )
        (vault / "ops" / "daemon-config.yaml").write_text(config_yaml)

        env = {
            "SLACK_BOT_TOKEN": "xoxb-test",
            "SLACK_APP_TOKEN": "xapp-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = SlackBotConfig.from_env(vault)
        assert cfg.model == "claude-opus-4-20250514"
        assert cfg.max_context_messages == 50

    def test_from_env_env_channel_overrides_config(self, vault: Path) -> None:
        config_yaml = "bot:\n  channel: C_FROM_YAML\n"
        (vault / "ops" / "daemon-config.yaml").write_text(config_yaml)

        env = {
            "SLACK_BOT_TOKEN": "xoxb-test",
            "SLACK_APP_TOKEN": "xapp-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "SLACK_BOT_CHANNEL": "C_FROM_ENV",
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = SlackBotConfig.from_env(vault)
        assert cfg.bot_channel == "C_FROM_ENV"

    def test_from_env_missing_one_var(self, vault: Path) -> None:
        env = {
            "SLACK_BOT_TOKEN": "xoxb-test",
            # Missing SLACK_APP_TOKEN and ANTHROPIC_API_KEY
        }
        with (
            patch.dict("os.environ", env, clear=True),
            pytest.raises(ValueError, match="SLACK_APP_TOKEN"),
        ):
            SlackBotConfig.from_env(vault)


# ---------------------------------------------------------------------------
# _should_respond tests
# ---------------------------------------------------------------------------


class TestShouldRespond:
    def test_dm_returns_true(self, bot: SlackBot) -> None:
        event = {"channel_type": "im", "user": "U_HUMAN", "text": "hello"}
        assert bot._should_respond(event) is True

    def test_mention_returns_true(self, bot: SlackBot) -> None:
        event = {
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "hey <@U_BOT> what's up",
            "channel": "C_OTHER",
        }
        assert bot._should_respond(event) is True

    def test_bot_channel_returns_true(self, bot: SlackBot) -> None:
        event = {
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "random message",
            "channel": "C_BOT_CHAN",
        }
        assert bot._should_respond(event) is True

    def test_own_message_returns_false(self, bot: SlackBot) -> None:
        event = {"user": "U_BOT", "text": "I said this", "channel_type": "im"}
        assert bot._should_respond(event) is False

    def test_bot_id_message_returns_false(self, bot: SlackBot) -> None:
        event = {
            "bot_id": "B_SOME_BOT",
            "user": "U_OTHER",
            "text": "bot message",
            "channel_type": "im",
        }
        assert bot._should_respond(event) is False

    def test_subtype_returns_false(self, bot: SlackBot) -> None:
        event = {
            "user": "U_HUMAN",
            "text": "hello",
            "subtype": "channel_join",
            "channel_type": "im",
        }
        assert bot._should_respond(event) is False

    def test_random_channel_no_mention_returns_false(self, bot: SlackBot) -> None:
        event = {
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "just chatting",
            "channel": "C_RANDOM",
        }
        assert bot._should_respond(event) is False

    def test_no_bot_user_id_still_checks_channel(self, bot: SlackBot) -> None:
        bot._bot_user_id = ""
        event = {
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "test",
            "channel": "C_BOT_CHAN",
        }
        assert bot._should_respond(event) is True

    def test_empty_event(self, bot: SlackBot) -> None:
        assert bot._should_respond({}) is False


# ---------------------------------------------------------------------------
# _build_thread_context tests
# ---------------------------------------------------------------------------


class TestBuildThreadContext:
    def test_maps_roles_correctly(self, bot: SlackBot) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN", "text": "question?"},
                {"user": "U_BOT", "text": "answer."},
                {"user": "U_HUMAN", "text": "follow-up?"},
            ]
        }
        result = bot._build_thread_context(client, "C1", "ts1", "follow-up?")
        assert result == [
            {"role": "user", "content": "question?"},
            {"role": "assistant", "content": "answer."},
            {"role": "user", "content": "follow-up?"},
        ]

    def test_merges_consecutive_user(self, bot: SlackBot) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN", "text": "line 1"},
                {"user": "U_OTHER", "text": "line 2"},
            ]
        }
        result = bot._build_thread_context(client, "C1", "ts1", "line 2")
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert "line 1" in result[0]["content"]
        assert "line 2" in result[0]["content"]

    def test_caps_at_max(self, bot: SlackBot) -> None:
        client = MagicMock()
        msgs = [{"user": f"U_{i}", "text": f"msg {i}"} for i in range(20)]
        # Alternate with bot
        for i in range(0, 20, 2):
            msgs[i]["user"] = "U_HUMAN"
        for i in range(1, 20, 2):
            msgs[i]["user"] = "U_BOT"
        client.conversations_replies.return_value = {"messages": msgs}
        bot.config.max_context_messages = 4
        result = bot._build_thread_context(client, "C1", "ts1", "current")
        # After capping to 4, merging, and ensuring start/end user
        assert len(result) <= 5  # Could be fewer after merge

    def test_api_error_fallback(self, bot: SlackBot) -> None:
        client = MagicMock()
        client.conversations_replies.side_effect = Exception("API error")
        result = bot._build_thread_context(client, "C1", "ts1", "hello?")
        assert result == [{"role": "user", "content": "hello?"}]

    def test_empty_thread(self, bot: SlackBot) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {"messages": []}
        result = bot._build_thread_context(client, "C1", "ts1", "hey")
        assert result == [{"role": "user", "content": "hey"}]

    def test_strips_bot_mention(self, bot: SlackBot) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN", "text": "<@U_BOT> what are my goals?"},
            ]
        }
        result = bot._build_thread_context(client, "C1", "ts1", "what are my goals?")
        assert "<@U_BOT>" not in result[0]["content"]

    def test_ensures_starts_with_user(self, bot: SlackBot) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [
                {"user": "U_BOT", "text": "I started this thread"},
                {"user": "U_HUMAN", "text": "ok"},
            ]
        }
        result = bot._build_thread_context(client, "C1", "ts1", "ok")
        assert result[0]["role"] == "user"

    def test_ensures_ends_with_user(self, bot: SlackBot) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN", "text": "question"},
                {"user": "U_BOT", "text": "answer"},
            ]
        }
        result = bot._build_thread_context(client, "C1", "ts1", "")
        assert result[-1]["role"] == "user"


# ---------------------------------------------------------------------------
# _merge_consecutive_roles tests
# ---------------------------------------------------------------------------


class TestMergeConsecutiveRoles:
    def test_empty(self) -> None:
        assert _merge_consecutive_roles([]) == []

    def test_no_merge_needed(self) -> None:
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        assert _merge_consecutive_roles(msgs) == msgs

    def test_merges_consecutive_user(self) -> None:
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
            {"role": "assistant", "content": "c"},
        ]
        result = _merge_consecutive_roles(msgs)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "a\nb"}
        assert result[1] == {"role": "assistant", "content": "c"}

    def test_merges_consecutive_assistant(self) -> None:
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "assistant", "content": "c"},
        ]
        result = _merge_consecutive_roles(msgs)
        assert len(result) == 2
        assert result[1] == {"role": "assistant", "content": "b\nc"}

    def test_single_message(self) -> None:
        msgs = [{"role": "user", "content": "alone"}]
        assert _merge_consecutive_roles(msgs) == msgs

    def test_does_not_mutate_input(self) -> None:
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
        ]
        original = [m.copy() for m in msgs]
        _merge_consecutive_roles(msgs)
        assert msgs == original


# ---------------------------------------------------------------------------
# build_system_prompt tests
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_includes_identity(self, bot: SlackBot) -> None:
        prompt = bot.build_system_prompt()
        assert "I am the agent" in prompt

    def test_includes_goals(self, bot: SlackBot) -> None:
        prompt = bot.build_system_prompt()
        assert "Test analysis" in prompt

    def test_includes_reminders(self, bot: SlackBot) -> None:
        prompt = bot.build_system_prompt()
        assert "data access" in prompt

    def test_includes_stats(self, bot: SlackBot) -> None:
        prompt = bot.build_system_prompt()
        assert "5 notes" in prompt
        assert "3 hypotheses" in prompt

    def test_includes_intro(self, bot: SlackBot) -> None:
        prompt = bot.build_system_prompt()
        assert "research assistant" in prompt

    def test_omits_empty_sections(self, bot: SlackBot) -> None:
        bot._vault_context = VaultContext()
        prompt = bot.build_system_prompt()
        assert "## Identity" not in prompt
        assert "## Current Research Goals" not in prompt
        assert "research assistant" in prompt  # Intro always present


# ---------------------------------------------------------------------------
# load_vault_context tests
# ---------------------------------------------------------------------------


class TestLoadVaultContext:
    def test_reads_files(self, vault: Path) -> None:
        ctx = load_vault_context(vault)
        assert "I am the agent" in ctx.identity
        assert "Iterative" in ctx.methodology
        assert "Test analysis" in ctx.goals
        assert "data access" in ctx.reminders
        assert "5 notes" in ctx.stats
        assert "3 hypotheses" in ctx.stats

    def test_handles_missing_files(self, tmp_path: Path) -> None:
        ctx = load_vault_context(tmp_path)
        assert ctx.identity == ""
        assert ctx.goals == ""
        assert "0 notes" in ctx.stats

    def test_truncates_long_files(self, vault: Path) -> None:
        long_content = "\n".join(f"Line {i}" for i in range(300))
        (vault / "self" / "identity.md").write_text(long_content)
        ctx = load_vault_context(vault)
        lines = ctx.identity.splitlines()
        assert len(lines) == 200


# ---------------------------------------------------------------------------
# refresh_vault_context tests
# ---------------------------------------------------------------------------


class TestRefreshVaultContext:
    def test_updates_context(self, bot: SlackBot, vault: Path) -> None:
        # Modify a vault file
        (vault / "self" / "goals.md").write_text("# Goals\n## New Goal\nUpdated.")
        bot.refresh_vault_context()
        assert "New Goal" in bot._vault_context.goals

    def test_handles_error(self, bot: SlackBot) -> None:
        bot.config = SlackBotConfig(
            vault_path=Path("/nonexistent/vault"),
            slack_bot_token="t",
            slack_app_token="t",
            anthropic_api_key="t",
        )
        # Should not raise
        bot.refresh_vault_context()


# ---------------------------------------------------------------------------
# _call_claude tests
# ---------------------------------------------------------------------------


class TestCallClaude:
    def test_success(self, bot: SlackBot, mock_anthropic: MagicMock) -> None:
        result = bot._call_claude([{"role": "user", "content": "hi"}], "system prompt")
        assert result == "Hello from Claude"
        mock_anthropic.messages.create.assert_called_once()

    def test_passes_config(self, bot: SlackBot, mock_anthropic: MagicMock) -> None:
        bot._call_claude([{"role": "user", "content": "hi"}], "sys")
        call_kwargs = mock_anthropic.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["system"] == "sys"

    def test_api_error_returns_message(
        self, bot: SlackBot, mock_anthropic: MagicMock
    ) -> None:
        mock_anthropic.messages.create.side_effect = RuntimeError("rate limit")
        result = bot._call_claude([{"role": "user", "content": "hi"}], "system")
        assert "could not generate" in result.lower()

    def test_empty_response(self, bot: SlackBot, mock_anthropic: MagicMock) -> None:
        resp = MagicMock()
        resp.content = []
        mock_anthropic.messages.create.return_value = resp
        result = bot._call_claude([{"role": "user", "content": "hi"}], "system")
        assert result == "(empty response)"

    def test_multi_block_response(
        self, bot: SlackBot, mock_anthropic: MagicMock
    ) -> None:
        block1 = MagicMock()
        block1.text = "Part 1"
        block2 = MagicMock()
        block2.text = "Part 2"
        resp = MagicMock()
        resp.content = [block1, block2]
        mock_anthropic.messages.create.return_value = resp
        result = bot._call_claude([{"role": "user", "content": "hi"}], "system")
        assert result == "Part 1\nPart 2"


# ---------------------------------------------------------------------------
# _split_message tests
# ---------------------------------------------------------------------------


class TestSplitMessage:
    def test_short_message(self) -> None:
        assert _split_message("hello", max_len=100) == ["hello"]

    def test_splits_at_newline(self) -> None:
        text = "a" * 50 + "\n" + "b" * 50
        chunks = _split_message(text, max_len=60)
        assert len(chunks) == 2
        assert chunks[0] == "a" * 50
        assert chunks[1] == "b" * 50

    def test_splits_at_space(self) -> None:
        text = "word " * 20  # 100 chars
        chunks = _split_message(text, max_len=50)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_hard_split(self) -> None:
        text = "x" * 200
        chunks = _split_message(text, max_len=50)
        assert len(chunks) == 4
        assert "".join(chunks) == text

    def test_empty_message(self) -> None:
        assert _split_message("") == [""]


# ---------------------------------------------------------------------------
# Event handler integration tests
# ---------------------------------------------------------------------------


class TestHandleMessageIntegration:
    def test_full_flow_mention(
        self, bot: SlackBot, mock_anthropic: MagicMock
    ) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN", "text": "<@U_BOT> what are my goals?"},
            ]
        }
        say = MagicMock()

        event = {
            "channel": "C_BOT_CHAN",
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "<@U_BOT> what are my goals?",
            "ts": "123.456",
        }

        bot._handle_mention(event=event, say=say, client=client)

        # Claude was called
        mock_anthropic.messages.create.assert_called_once()
        call_kwargs = mock_anthropic.messages.create.call_args.kwargs
        assert call_kwargs["messages"][0]["role"] == "user"
        assert "goals" in call_kwargs["messages"][0]["content"].lower()

        # System prompt has vault context
        assert "Test analysis" in call_kwargs["system"]

        # Response was sent
        say.assert_called_once()
        assert say.call_args.kwargs["thread_ts"] == "123.456"

    def test_dm_flow(self, bot: SlackBot, mock_anthropic: MagicMock) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"user": "U_HUMAN", "text": "hello"}]
        }
        say = MagicMock()

        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_HUMAN",
            "text": "hello",
            "ts": "789.012",
        }

        bot._handle_message(event=event, say=say, client=client)
        say.assert_called_once()

    def test_skips_non_target(self, bot: SlackBot) -> None:
        say = MagicMock()
        client = MagicMock()

        event = {
            "channel": "C_RANDOM",
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "not for bot",
            "ts": "111.222",
        }

        bot._handle_message(event=event, say=say, client=client)
        say.assert_not_called()

    def test_error_sends_apology(
        self, bot: SlackBot, mock_anthropic: MagicMock
    ) -> None:
        client = MagicMock()
        client.conversations_replies.side_effect = Exception("fail")
        mock_anthropic.messages.create.side_effect = Exception("double fail")
        say = MagicMock()

        event = {
            "channel": "C_BOT_CHAN",
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "test",
            "ts": "333.444",
        }

        # Use _process_event directly (bot_channel, no mention)
        bot._process_event(event=event, say=say, client=client)
        # Should still try to say something (apology or error response)
        assert say.call_count >= 1

    def test_thread_reply(self, bot: SlackBot, mock_anthropic: MagicMock) -> None:
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN", "text": "first question"},
                {"user": "U_BOT", "text": "first answer"},
                {"user": "U_HUMAN", "text": "<@U_BOT> follow-up"},
            ]
        }
        say = MagicMock()

        event = {
            "channel": "C_BOT_CHAN",
            "channel_type": "channel",
            "user": "U_HUMAN",
            "text": "<@U_BOT> follow-up",
            "ts": "456.789",
            "thread_ts": "123.000",
        }

        bot._handle_mention(event=event, say=say, client=client)

        call_kwargs = mock_anthropic.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        # Should have the full thread context
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

        # Reply should be in the thread
        assert say.call_args.kwargs["thread_ts"] == "123.000"


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_under_limit(self) -> None:
        rl = RateLimiter(max_per_minute=3, cooldown_s=10)
        assert rl.check("U1") is True
        assert rl.check("U1") is True
        assert rl.check("U1") is True

    def test_denies_over_limit(self) -> None:
        rl = RateLimiter(max_per_minute=2, cooldown_s=10)
        assert rl.check("U1") is True
        assert rl.check("U1") is True
        assert rl.check("U1") is False

    def test_users_independent(self) -> None:
        rl = RateLimiter(max_per_minute=1, cooldown_s=10)
        assert rl.check("U1") is True
        assert rl.check("U2") is True
        assert rl.check("U1") is False
        assert rl.check("U2") is False

    def test_cooldown_blocks(self) -> None:
        rl = RateLimiter(max_per_minute=1, cooldown_s=9999)
        assert rl.check("U1") is True
        assert rl.check("U1") is False  # triggers cooldown
        # Still blocked by cooldown
        assert rl.check("U1") is False

    def test_window_expires(self) -> None:
        rl = RateLimiter(max_per_minute=1, cooldown_s=0)
        assert rl.check("U1") is True
        # Manually expire the timestamp
        rl._timestamps["U1"] = [time.monotonic() - 61.0]
        rl._deny_until.pop("U1", None)
        assert rl.check("U1") is True

    def test_reset_clears(self) -> None:
        rl = RateLimiter(max_per_minute=1, cooldown_s=9999)
        assert rl.check("U1") is True
        assert rl.check("U1") is False
        rl.reset("U1")
        assert rl.check("U1") is True


# ---------------------------------------------------------------------------
# Authorize tests
# ---------------------------------------------------------------------------


class TestAuthorize:
    def _make_bot(
        self,
        vault: Path,
        mock_app: MagicMock,
        mock_anthropic: MagicMock,
        *,
        owner_ids: tuple[str, ...] = (),
        allowed_ids: tuple[str, ...] = (),
        public_access: bool = True,
    ) -> SlackBot:
        cfg = SlackBotConfig(
            vault_path=vault,
            slack_bot_token="xoxb-test-token",
            slack_app_token="xapp-test-token",
            anthropic_api_key="sk-ant-test-key",
            vault_refresh_interval_s=0,
            owner_ids=owner_ids,
            allowed_ids=allowed_ids,
            public_access=public_access,
        )
        b = SlackBot(config=cfg, app=mock_app, anthropic_client=mock_anthropic)
        b._bot_user_id = "U_BOT"
        return b

    def test_owner_recognized(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        b = self._make_bot(vault, mock_app, mock_anthropic, owner_ids=("U_OWNER",))
        assert b._authorize("U_OWNER") == AUTH_OWNER

    def test_allowed_recognized(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        b = self._make_bot(vault, mock_app, mock_anthropic, allowed_ids=("U_FRIEND",))
        assert b._authorize("U_FRIEND") == AUTH_ALLOWED

    def test_public_allows_unknown(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        b = self._make_bot(vault, mock_app, mock_anthropic, public_access=True)
        assert b._authorize("U_STRANGER") == AUTH_PUBLIC

    def test_public_disabled_denies(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        b = self._make_bot(
            vault,
            mock_app,
            mock_anthropic,
            owner_ids=("U_OWNER",),
            public_access=False,
        )
        assert b._authorize("U_STRANGER") == AUTH_DENIED

    def test_denied_gets_message(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        b = self._make_bot(
            vault, mock_app, mock_anthropic, public_access=False
        )
        say = MagicMock()
        client = MagicMock()
        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_STRANGER",
            "text": "hello",
            "ts": "100.200",
        }
        b._process_event(event=event, say=say, client=client)
        say.assert_called_once()
        assert "not authorized" in say.call_args.kwargs["text"].lower()

    def test_rate_limit_denial(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        b = self._make_bot(
            vault, mock_app, mock_anthropic, public_access=True
        )
        b.config = SlackBotConfig(
            vault_path=vault,
            slack_bot_token="xoxb-test-token",
            slack_app_token="xapp-test-token",
            anthropic_api_key="sk-ant-test-key",
            vault_refresh_interval_s=0,
            rate_limit_rpm=1,
            rate_limit_cooldown_s=9999,
        )
        b._rate_limiter = RateLimiter(max_per_minute=1, cooldown_s=9999)

        say = MagicMock()
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"user": "U_HUMAN", "text": "msg"}]
        }
        mock_anthropic.messages.create.return_value = _mock_anthropic_response()

        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_HUMAN",
            "text": "first",
            "ts": "100.200",
        }
        b._process_event(event=event, say=say, client=client)
        # First call succeeds
        assert say.call_count >= 1

        say.reset_mock()
        event["text"] = "second"
        event["ts"] = "100.300"
        b._process_event(event=event, say=say, client=client)
        # Second call gets rate-limited
        say.assert_called_once()
        assert "too quickly" in say.call_args.kwargs["text"].lower()

    def test_no_authority_preserves_open(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        """Default config (no owner_ids, public_access=True) allows everyone."""
        b = self._make_bot(vault, mock_app, mock_anthropic)
        assert b._authorize("U_ANYONE") == AUTH_PUBLIC


# ---------------------------------------------------------------------------
# Outbound PII scrub tests
# ---------------------------------------------------------------------------


class TestOutboundScrub:
    def test_response_with_email_is_scrubbed(
        self, bot: SlackBot, mock_anthropic: MagicMock
    ) -> None:
        """Claude response containing an email gets PII scrubbed."""
        mock_anthropic.messages.create.return_value = _mock_anthropic_response(
            "Contact alice@example.com for details"
        )
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"user": "U_HUMAN", "text": "who to contact?"}]
        }
        say = MagicMock()

        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_HUMAN",
            "text": "who to contact?",
            "ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        # The say call should have the scrubbed text
        sent_text = say.call_args.kwargs["text"]
        assert "alice@example.com" not in sent_text
        assert "[REDACTED]" in sent_text

    def test_clean_response_unchanged(
        self, bot: SlackBot, mock_anthropic: MagicMock
    ) -> None:
        """Claude response without PII passes through unchanged."""
        clean_text = "The hypothesis has an Elo of 1350.0"
        mock_anthropic.messages.create.return_value = _mock_anthropic_response(
            clean_text
        )
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"user": "U_HUMAN", "text": "status?"}]
        }
        say = MagicMock()

        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_HUMAN",
            "text": "status?",
            "ts": "200.200",
        }
        bot._process_event(event=event, say=say, client=client)

        sent_text = say.call_args.kwargs["text"]
        assert sent_text == clean_text


# ---------------------------------------------------------------------------
# Skill routing tests
# ---------------------------------------------------------------------------


def _make_skills_bot(
    vault: Path,
    mock_app: MagicMock,
    mock_anthropic: MagicMock,
    *,
    owner_ids: tuple[str, ...] = ("U_OWNER",),
    confirm_mutative: bool = True,
) -> SlackBot:
    """Create a bot with skills enabled."""
    # Write daemon-config with skills enabled
    import yaml

    config_yaml = {
        "bot": {
            "skills": {
                "enabled": True,
                "confirm_mutative": confirm_mutative,
                "confirmation_timeout_s": 300,
            }
        }
    }
    (vault / "ops").mkdir(exist_ok=True)
    (vault / "ops" / "daemon-config.yaml").write_text(yaml.dump(config_yaml))

    cfg = SlackBotConfig(
        vault_path=vault,
        slack_bot_token="xoxb-test-token",
        slack_app_token="xapp-test-token",
        anthropic_api_key="sk-ant-test-key",
        vault_refresh_interval_s=0,
        owner_ids=owner_ids,
        public_access=True,
    )
    b = SlackBot(config=cfg, app=mock_app, anthropic_client=mock_anthropic)
    b._bot_user_id = "U_BOT"
    return b


class TestSkillExplicitCommand:
    def test_explicit_command_queued(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic)
        (vault / "ops" / "daemon").mkdir(parents=True, exist_ok=True)

        say = MagicMock()
        client = MagicMock()
        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_OWNER",
            "text": "/stats",
            "ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        # Should have queued and sent acknowledgment
        assert say.call_count >= 1
        sent_text = say.call_args_list[0].kwargs["text"]
        assert "Queued" in sent_text or "queued" in sent_text.lower()

    def test_explicit_mutative_asks_confirmation(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic)

        say = MagicMock()
        client = MagicMock()
        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_OWNER",
            "text": "/reduce",
            "ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        # Should ask for confirmation
        sent_text = say.call_args_list[0].kwargs["text"]
        assert "mutative" in sent_text.lower() or "confirm" in sent_text.lower()

    def test_denied_skill_sends_reason(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic, owner_ids=())

        say = MagicMock()
        client = MagicMock()
        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_STRANGER",
            "text": "/reduce",
            "ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        sent_text = say.call_args_list[0].kwargs["text"]
        assert "does not permit" in sent_text


class TestSkillConfirmation:
    def test_confirmation_yes_queues(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic)
        (vault / "ops" / "daemon").mkdir(parents=True, exist_ok=True)

        # Set up a pending confirmation
        confirm_key = "D_DM:100.100"
        bot._pending_confirmations[confirm_key] = PendingConfirmation(
            skill="reduce",
            args="",
            user_id="U_OWNER",
            auth_level="owner",
            channel="D_DM",
            thread_ts="100.100",
            expires_at=time.monotonic() + 300,
        )

        say = MagicMock()
        client = MagicMock()
        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_OWNER",
            "text": "yes",
            "ts": "100.200",
            "thread_ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        sent_text = say.call_args_list[0].kwargs["text"]
        assert "Queued" in sent_text or "queued" in sent_text.lower()
        assert confirm_key not in bot._pending_confirmations

    def test_confirmation_no_cancels(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic)

        confirm_key = "D_DM:100.100"
        bot._pending_confirmations[confirm_key] = PendingConfirmation(
            skill="reduce",
            args="",
            user_id="U_OWNER",
            auth_level="owner",
            channel="D_DM",
            thread_ts="100.100",
            expires_at=time.monotonic() + 300,
        )

        say = MagicMock()
        client = MagicMock()
        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_OWNER",
            "text": "no",
            "ts": "100.200",
            "thread_ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        assert "Cancelled" in say.call_args_list[0].kwargs["text"]
        assert confirm_key not in bot._pending_confirmations

    def test_confirmation_expired(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic)

        confirm_key = "D_DM:100.100"
        bot._pending_confirmations[confirm_key] = PendingConfirmation(
            skill="reduce",
            args="",
            user_id="U_OWNER",
            auth_level="owner",
            channel="D_DM",
            thread_ts="100.100",
            expires_at=time.monotonic() - 1,  # Already expired
        )

        say = MagicMock()
        client = MagicMock()
        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_OWNER",
            "text": "yes",
            "ts": "100.200",
            "thread_ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        sent_text = say.call_args_list[0].kwargs["text"]
        assert "expired" in sent_text.lower()

    def test_wrong_user_cannot_confirm(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(
            vault, mock_app, mock_anthropic, owner_ids=("U_OWNER", "U_OTHER")
        )

        confirm_key = "D_DM:100.100"
        bot._pending_confirmations[confirm_key] = PendingConfirmation(
            skill="reduce",
            args="",
            user_id="U_OWNER",
            auth_level="owner",
            channel="D_DM",
            thread_ts="100.100",
            expires_at=time.monotonic() + 300,
        )

        say = MagicMock()
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"user": "U_OTHER", "text": "yes"}]
        }
        mock_anthropic.messages.create.return_value = _mock_anthropic_response()

        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_OTHER",
            "text": "yes",
            "ts": "100.200",
            "thread_ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        # Confirmation should still be pending (wrong user)
        assert confirm_key in bot._pending_confirmations


class TestSkillNLDetection:
    def test_nl_intent_queues_skill(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic)
        (vault / "ops" / "daemon").mkdir(parents=True, exist_ok=True)

        # Claude returns a response with a skill-intent block
        mock_anthropic.messages.create.return_value = _mock_anthropic_response(
            "Sure, let me get your vault stats.\n"
            "<skill-intent>skill: stats</skill-intent>"
        )

        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"user": "U_OWNER", "text": "show me vault stats"}]
        }
        say = MagicMock()

        event = {
            "channel": "D_DM",
            "channel_type": "im",
            "user": "U_OWNER",
            "text": "show me vault stats",
            "ts": "100.100",
        }
        bot._process_event(event=event, say=say, client=client)

        # Should have the cleaned response AND queue message
        calls = [c.kwargs["text"] for c in say.call_args_list]
        assert any("vault stats" in c.lower() for c in calls)
        assert any("queued" in c.lower() for c in calls)


class TestBuildSystemPromptWithSkills:
    def test_includes_skill_detection_when_enabled(
        self, vault: Path, mock_app: MagicMock, mock_anthropic: MagicMock
    ) -> None:
        bot = _make_skills_bot(vault, mock_app, mock_anthropic)
        prompt = bot.build_system_prompt()
        assert "skill-intent" in prompt
        assert "stats" in prompt

    def test_excludes_skill_detection_when_disabled(self, bot: SlackBot) -> None:
        bot._skills_enabled = False
        prompt = bot.build_system_prompt()
        assert "skill-intent" not in prompt
