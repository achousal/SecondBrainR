"""Load and validate federation configuration from ops/federation.yaml.

Provides typed access to federation settings: vault identity, peer list,
trust levels, import/export policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_VALID_TRUST_LEVELS = {"full", "verified", "untrusted"}


class FederationConfigError(Exception):
    """Raised for federation configuration problems."""


@dataclass(frozen=True)
class PeerConfig:
    """Configuration for a single peer vault."""

    name: str
    vault_id: str = ""
    display_name: str = ""
    institution: str = ""
    trust: str = "untrusted"
    notes: str = ""


@dataclass(frozen=True)
class VaultIdentity:
    """This vault's identity in the federation."""

    vault_id: str = ""
    display_name: str = ""
    institution: str = ""


@dataclass(frozen=True)
class ExportPolicy:
    """Controls what this vault shares with peers."""

    claims_enabled: bool = True
    claims_filter_confidence: list[str] = field(
        default_factory=lambda: ["established", "supported"]
    )
    claims_max_per_sync: int = 50
    hypotheses_enabled: bool = True
    hypotheses_min_elo: float = 1250.0
    hypotheses_max_per_sync: int = 20
    redact_pii_on_export: bool = True


@dataclass(frozen=True)
class ImportPolicy:
    """Controls what this vault accepts from peers."""

    default_trust: str = "untrusted"
    quarantine_enabled: bool = True
    quarantine_auto_accept_days: int = 0
    """Parsed from config but not yet enforced at runtime.

    Intent: automatically lift quarantine after N days for verified peers.
    Deferred until federation is in active multi-vault use. Currently only
    parsed and stored -- no scheduler or cron job consumes this value.
    """
    allow_federated_tournament: bool = True
    starting_elo: float = 1200.0


@dataclass(frozen=True)
class FederationConfig:
    """Complete federation configuration."""

    identity: VaultIdentity = field(default_factory=VaultIdentity)
    enabled: bool = False
    sync_frequency_hours: int = 24
    exchange_dir: str = ""
    export_policy: ExportPolicy = field(default_factory=ExportPolicy)
    import_policy: ImportPolicy = field(default_factory=ImportPolicy)
    peers: dict[str, PeerConfig] = field(default_factory=dict)

    def get_peer_trust(self, peer_name: str) -> str:
        """Get effective trust level for a peer.

        Returns the peer's configured trust, or default_trust for
        unknown peers.
        """
        peer = self.peers.get(peer_name)
        if peer is not None:
            return peer.trust
        return self.import_policy.default_trust

    def can_import_from(self, peer_name: str) -> bool:
        """Check if imports from a peer are allowed (not untrusted)."""
        return self.get_peer_trust(peer_name) != "untrusted"

    def should_quarantine(self, peer_name: str) -> bool:
        """Check if imports from a peer should be quarantined."""
        if not self.import_policy.quarantine_enabled:
            return False
        trust = self.get_peer_trust(peer_name)
        return trust != "full"


def load_federation_config(
    config_path: Path | None = None,
) -> FederationConfig:
    """Load federation configuration from YAML file.

    Args:
        config_path: Path to federation.yaml. If None, returns defaults.

    Returns:
        FederationConfig with all settings parsed.

    Raises:
        FederationConfigError: If file exists but is malformed.
    """
    if config_path is None or not config_path.exists():
        return FederationConfig()

    try:
        raw = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise FederationConfigError(f"Invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise FederationConfigError("Federation config must be a YAML mapping")

    return _parse_config(data)


def _parse_config(data: dict[str, Any]) -> FederationConfig:
    """Parse raw YAML data into a FederationConfig."""
    # Identity
    id_data = data.get("identity", {}) or {}
    identity = VaultIdentity(
        vault_id=str(id_data.get("vault_id", "")),
        display_name=str(id_data.get("display_name", "")),
        institution=str(id_data.get("institution", "")),
    )

    # Sync settings
    sync_data = data.get("sync", {}) or {}

    # Export policy
    exp_data = data.get("export", {}) or {}
    exp_claims = exp_data.get("claims", {}) or {}
    exp_hyps = exp_data.get("hypotheses", {}) or {}
    export_policy = ExportPolicy(
        claims_enabled=bool(exp_claims.get("enabled", True)),
        claims_filter_confidence=exp_claims.get(
            "filter_confidence", ["established", "supported"]
        ),
        claims_max_per_sync=int(exp_claims.get("max_per_sync", 50)),
        hypotheses_enabled=bool(exp_hyps.get("enabled", True)),
        hypotheses_min_elo=float(exp_hyps.get("min_elo", 1250)),
        hypotheses_max_per_sync=int(exp_hyps.get("max_per_sync", 20)),
        redact_pii_on_export=bool(exp_data.get("redact_pii", True)),
    )

    # Import policy
    imp_data = data.get("import", {}) or {}
    imp_quarantine = imp_data.get("quarantine", {}) or {}
    imp_hyps = imp_data.get("hypotheses", {}) or {}
    default_trust = str(imp_data.get("default_trust", "untrusted"))
    if default_trust not in _VALID_TRUST_LEVELS:
        raise FederationConfigError(
            f"Invalid default_trust: {default_trust}. "
            f"Must be one of: {', '.join(sorted(_VALID_TRUST_LEVELS))}"
        )
    import_policy = ImportPolicy(
        default_trust=default_trust,
        quarantine_enabled=bool(imp_quarantine.get("enabled", True)),
        quarantine_auto_accept_days=int(
            imp_quarantine.get("auto_accept_after_days", 0)
        ),
        allow_federated_tournament=bool(
            imp_hyps.get("allow_federated_tournament", True)
        ),
        starting_elo=float(imp_hyps.get("starting_elo", 1200)),
    )

    # Peers
    peers_data = data.get("peers", {}) or {}
    peers: dict[str, PeerConfig] = {}
    for name, pdata in peers_data.items():
        if not isinstance(pdata, dict):
            continue
        trust = str(pdata.get("trust", "untrusted"))
        if trust not in _VALID_TRUST_LEVELS:
            raise FederationConfigError(
                f"Invalid trust level for peer '{name}': {trust}"
            )
        peers[name] = PeerConfig(
            name=name,
            vault_id=str(pdata.get("vault_id", "")),
            display_name=str(pdata.get("display_name", "")),
            institution=str(pdata.get("institution", "")),
            trust=trust,
            notes=str(pdata.get("notes", "")),
        )

    return FederationConfig(
        identity=identity,
        enabled=bool(data.get("enabled", False)),
        sync_frequency_hours=int(sync_data.get("frequency_hours", 24)),
        exchange_dir=str(sync_data.get("exchange_dir", "")),
        export_policy=export_policy,
        import_policy=import_policy,
        peers=peers,
    )
