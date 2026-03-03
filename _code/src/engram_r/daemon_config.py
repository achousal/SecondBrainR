"""Configuration loader for the Research Loop Daemon.

Reads ops/daemon-config.yaml and provides typed access to all settings.
Pure Python -- no I/O beyond initial file read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CooldownConfig:
    """Cooldown durations in minutes after each model tier."""

    after_haiku: int = 2
    after_sonnet: int = 5
    after_opus: int = 10
    idle: int = 30

    def for_model(self, model: str) -> int:
        """Return cooldown minutes for a given model name."""
        mapping = {
            "haiku": self.after_haiku,
            "sonnet": self.after_sonnet,
            "opus": self.after_opus,
        }
        return mapping.get(model, self.after_sonnet)


@dataclass(frozen=True)
class BatchConfig:
    """Batch size settings for daemon tasks."""

    tournament_threshold: int = 8
    matches_per_session: int = 8
    verify_batch: int = 10
    validate_batch: int = 20
    mine_sessions_batch: int = 30


@dataclass(frozen=True)
class ThresholdConfig:
    """Thresholds that trigger maintenance or research actions."""

    undermatched_matches: int = 3
    observations_rethink: int = 10
    tensions_rethink: int = 5
    queue_backlog: int = 10
    orphan_notes: int = 10
    stale_notes_days: int = 30
    unmined_sessions: int = 2


@dataclass(frozen=True)
class RetryConfig:
    """Retry settings for failed tasks."""

    max_per_task: int = 8
    initial_backoff_seconds: int = 60
    max_backoff_seconds: int = 900


@dataclass(frozen=True)
class TimeoutConfig:
    """Global daemon timeout."""

    global_hours: int = 0  # 0 = no timeout


@dataclass(frozen=True)
class ModelConfig:
    """Model assignments for each skill type."""

    tournament_primary: str = "opus"
    tournament_other: str = "sonnet"
    meta_review: str = "sonnet"
    landscape: str = "sonnet"
    reflect: str = "sonnet"
    reweave: str = "sonnet"
    reduce: str = "sonnet"
    verify: str = "haiku"
    validate: str = "haiku"
    remember: str = "haiku"
    rethink: str = "sonnet"

    def for_tournament(self, goal_id: str, primary_goal: str) -> str:
        """Return model for tournament based on goal priority."""
        if goal_id == primary_goal:
            return self.tournament_primary
        return self.tournament_other

    def for_skill(self, skill: str) -> str:
        """Return model for a skill name, falling back to sonnet."""
        mapping = {
            "tournament": self.tournament_other,
            "meta-review": self.meta_review,
            "landscape": self.landscape,
            "reflect": self.reflect,
            "reweave": self.reweave,
            "reduce": self.reduce,
            "verify": self.verify,
            "validate": self.validate,
            "remember": self.remember,
            "rethink": self.rethink,
        }
        return mapping.get(skill, "sonnet")


@dataclass(frozen=True)
class MetabolicConfig:
    """Metabolic feedback thresholds for daemon self-regulation.

    When indicators exceed these thresholds, the daemon suppresses
    creation and prioritizes consolidation/maintenance.

    7 indicators in 3 tiers:
    Tier 1 (Governance): QPR, CMR, TPV -- auto-suppress generative tasks.
    Tier 2 (Awareness): HCR, GCR, IPR -- user-facing signals via /next.
    Tier 3 (Observational): VDR -- logged only.
    """

    enabled: bool = True
    # Tier 1: Governance
    qpr_critical: float = 3.0  # QPR > 3.0 triggers generation halt
    cmr_hot: float = 10.0  # CMR > 10:1 = running hot
    tpv_stalled: float = 0.1  # TPV < 0.1 = stalled throughput
    # Tier 2: Awareness
    hcr_redirect: float = 15.0  # HCR < 15% redirects to SAP support
    gcr_fragmented: float = 0.3  # GCR < 0.3 = fragmented graph
    ipr_overflow: float = 3.0  # IPR > 3.0 = inbox overflowing
    # Tier 3: Observational (VDR informational only)
    vdr_warn: float = 80.0  # VDR > 80% = informational warning
    lookback_days: int = 7  # Window for rate computations
    history_max_snapshots: int = 90  # Max historical snapshots to retain


@dataclass(frozen=True)
class HealthConfig:
    """Health gate settings for /health integration."""

    check_frequency_hours: int = 2
    max_fix_iterations: int = 3
    model: str = "sonnet"


@dataclass(frozen=True)
class NotificationChannels:
    """Channel routing for Slack notifications."""

    default: str = ""
    alerts: str = ""
    daemon: str = ""

    def for_event(self, event_type: str) -> str:
        """Return the channel ID for a given event type.

        Falls back to default if no specific channel is configured.
        """
        if event_type == "daemon_alert" and self.alerts:
            return self.alerts
        if event_type.startswith("daemon_") and self.daemon:
            return self.daemon
        return self.default


@dataclass(frozen=True)
class NotificationEvents:
    """Toggle individual notification event types."""

    session_start: bool = True
    session_end: bool = True
    daemon_task_complete: bool = True
    daemon_alert: bool = True
    daemon_for_you: bool = True
    tournament_result: bool = True
    new_hypothesis: bool = False
    meta_review: bool = True


@dataclass(frozen=True)
class InboundConfig:
    """Configuration for inbound Slack message polling."""

    enabled: bool = True
    lookback_hours: int = 24
    channel: str = ""


@dataclass(frozen=True)
class NotificationConfig:
    """Top-level notification configuration."""

    enabled: bool = True
    level: str = "all"  # all | alerts-only | off
    channels: NotificationChannels = field(default_factory=NotificationChannels)
    events: NotificationEvents = field(default_factory=NotificationEvents)
    inbound: InboundConfig = field(default_factory=InboundConfig)

    def should_notify(self, event_type: str) -> bool:
        """Check whether a notification should be sent for the given event.

        Args:
            event_type: One of the NotificationEvents field names.

        Returns:
            True if the notification should fire.
        """
        if not self.enabled or self.level == "off":
            return False
        if self.level == "alerts-only":
            return event_type == "daemon_alert"
        return getattr(self.events, event_type, False)


@dataclass(frozen=True)
class AuthorityConfig:
    """Access control for the Slack bot."""

    owner_ids: tuple[str, ...] = ()
    allowed_ids: tuple[str, ...] = ()
    public_access: bool = True
    max_per_user_per_minute: int = 5
    cooldown_after_deny_s: int = 30


@dataclass(frozen=True)
class BotConfig:
    """Slack bot configuration for the two-way vault-aware assistant."""

    channel: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_context_messages: int = 20
    max_response_tokens: int = 4096
    vault_refresh_interval_s: int = 300
    authority: AuthorityConfig = field(default_factory=AuthorityConfig)


@dataclass(frozen=True)
class ScheduleEntry:
    """A single scheduled recurring task.

    Attributes:
        name: Unique identifier for this schedule (used in marker keys).
        type: Payload builder type (project_update, stale_project, etc.).
        cadence: Recurrence frequency -- weekly, daily, or monthly.
        day: Day trigger -- weekday name (weekly), 1-28 (monthly).
        hour: Local hour (24h) at or after which the task becomes eligible.
        scope: Project status filter (e.g. 'active' to skip maintenance/archived).
        delivery: Notification delivery method -- 'dm' for private or 'channel'.
        enabled: Whether this schedule is active.
        lookahead_days: For deadline-type schedules, how far ahead to look.
        channel: Override channel ID (delivery=channel only). Empty uses default.
    """

    name: str = ""
    type: str = ""
    cadence: str = "weekly"
    day: str = ""
    hour: int = 9
    scope: str = "active"
    delivery: str = "dm"
    enabled: bool = True
    lookahead_days: int = 3
    channel: str = ""


@dataclass(frozen=True)
class DaemonConfig:
    """Top-level daemon configuration."""

    goals_priority: list[str] = field(default_factory=list)
    models: ModelConfig = field(default_factory=ModelConfig)
    cooldowns: CooldownConfig = field(default_factory=CooldownConfig)
    batching: BatchConfig = field(default_factory=BatchConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    metabolic: MetabolicConfig = field(default_factory=MetabolicConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    bot: BotConfig = field(default_factory=BotConfig)
    schedules: list[ScheduleEntry] = field(default_factory=list)

    @property
    def primary_goal(self) -> str:
        """The highest-priority goal."""
        return self.goals_priority[0] if self.goals_priority else ""


def _build_sub(cls: type, data: dict[str, Any] | None) -> Any:
    """Build a frozen dataclass from a dict, ignoring unknown keys."""
    if data is None:
        return cls()
    valid = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in valid}
    return cls(**filtered)


def load_config(config_path: Path) -> DaemonConfig:
    """Load daemon configuration from a YAML file.

    Args:
        config_path: Path to ops/daemon-config.yaml.

    Returns:
        Populated DaemonConfig.

    Raises:
        FileNotFoundError: If config file does not exist.
        yaml.YAMLError: If YAML is malformed.
    """
    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        return DaemonConfig()

    defaults = DaemonConfig()

    # Build notifications with nested sub-configs
    notif_raw = raw.get("notifications")
    if isinstance(notif_raw, dict):
        notifications = NotificationConfig(
            enabled=notif_raw.get("enabled", True),
            level=notif_raw.get("level", "all"),
            channels=_build_sub(NotificationChannels, notif_raw.get("channels")),
            events=_build_sub(NotificationEvents, notif_raw.get("events")),
            inbound=_build_sub(InboundConfig, notif_raw.get("inbound")),
        )
    else:
        notifications = NotificationConfig()

    # Build schedules list
    schedules_raw = raw.get("schedules")
    schedules: list[ScheduleEntry] = []
    if isinstance(schedules_raw, list):
        for entry in schedules_raw:
            if isinstance(entry, dict):
                schedules.append(_build_sub(ScheduleEntry, entry))

    # Build bot with nested authority sub-config
    bot_raw = raw.get("bot")
    if isinstance(bot_raw, dict):
        auth_raw = bot_raw.get("authority")
        if isinstance(auth_raw, dict):
            # Convert lists to tuples for frozen dataclass
            auth_data = dict(auth_raw)
            for key in ("owner_ids", "allowed_ids"):
                if key in auth_data and isinstance(auth_data[key], list):
                    auth_data[key] = tuple(auth_data[key])
            authority = _build_sub(AuthorityConfig, auth_data)
        else:
            authority = AuthorityConfig()
        bot_valid = {f.name for f in BotConfig.__dataclass_fields__.values()}
        bot_filtered = {
            k: v for k, v in bot_raw.items() if k in bot_valid and k != "authority"
        }
        bot = BotConfig(**bot_filtered, authority=authority)
    else:
        bot = BotConfig()

    return DaemonConfig(
        goals_priority=raw.get("goals_priority", defaults.goals_priority),
        models=_build_sub(ModelConfig, raw.get("models")),
        cooldowns=_build_sub(CooldownConfig, raw.get("cooldowns_minutes")),
        batching=_build_sub(BatchConfig, raw.get("batching")),
        thresholds=_build_sub(ThresholdConfig, raw.get("thresholds")),
        retry=_build_sub(RetryConfig, raw.get("retry")),
        timeout=_build_sub(TimeoutConfig, raw.get("timeout")),
        health=_build_sub(HealthConfig, raw.get("health")),
        metabolic=_build_sub(MetabolicConfig, raw.get("metabolic")),
        notifications=notifications,
        bot=bot,
        schedules=schedules,
    )
