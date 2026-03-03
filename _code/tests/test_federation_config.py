"""Tests for federation_config module -- federation configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engram_r.federation_config import (
    FederationConfig,
    FederationConfigError,
    PeerConfig,
    load_federation_config,
)


def _write_config(path: Path, data: dict) -> Path:
    """Write a federation config YAML file."""
    config_path = path / "federation.yaml"
    config_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return config_path


class TestLoadFederationConfig:
    """Test loading federation.yaml."""

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        config = load_federation_config(tmp_path / "nonexistent.yaml")
        assert isinstance(config, FederationConfig)
        assert config.enabled is False
        assert config.identity.vault_id == ""
        assert config.peers == {}

    def test_none_path_returns_defaults(self) -> None:
        config = load_federation_config(None)
        assert config.enabled is False

    def test_full_config(self, tmp_path: Path) -> None:
        data = {
            "identity": {
                "vault_id": "vault-001",
                "display_name": "Test Vault",
                "institution": "Test U",
            },
            "enabled": True,
            "sync": {
                "frequency_hours": 12,
                "exchange_dir": "/tmp/exchange",
            },
            "export": {
                "claims": {
                    "enabled": True,
                    "filter_confidence": ["established"],
                    "max_per_sync": 25,
                },
                "hypotheses": {
                    "enabled": True,
                    "min_elo": 1300,
                    "max_per_sync": 10,
                },
            },
            "import": {
                "default_trust": "verified",
                "quarantine": {
                    "enabled": True,
                    "auto_accept_after_days": 7,
                },
                "hypotheses": {
                    "allow_federated_tournament": True,
                    "starting_elo": 1100,
                },
            },
            "peers": {
                "collab": {
                    "vault_id": "peer-001",
                    "display_name": "Collab Lab",
                    "institution": "Partner U",
                    "trust": "full",
                    "notes": "Trusted partner",
                }
            },
        }
        path = _write_config(tmp_path, data)
        config = load_federation_config(path)

        assert config.enabled is True
        assert config.identity.vault_id == "vault-001"
        assert config.identity.display_name == "Test Vault"
        assert config.sync_frequency_hours == 12
        assert config.exchange_dir == "/tmp/exchange"

        assert config.export_policy.claims_enabled is True
        assert config.export_policy.claims_filter_confidence == ["established"]
        assert config.export_policy.claims_max_per_sync == 25
        assert config.export_policy.hypotheses_min_elo == 1300
        assert config.export_policy.hypotheses_max_per_sync == 10

        assert config.import_policy.default_trust == "verified"
        assert config.import_policy.quarantine_enabled is True
        assert config.import_policy.quarantine_auto_accept_days == 7
        assert config.import_policy.starting_elo == 1100

        assert "collab" in config.peers
        assert config.peers["collab"].trust == "full"

    def test_minimal_config(self, tmp_path: Path) -> None:
        data = {"enabled": False}
        path = _write_config(tmp_path, data)
        config = load_federation_config(path)
        assert config.enabled is False
        assert config.identity.vault_id == ""
        assert config.peers == {}

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("{bad: [", encoding="utf-8")
        with pytest.raises(FederationConfigError, match="Invalid YAML"):
            load_federation_config(path)

    def test_non_dict_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- a list\n- not a dict", encoding="utf-8")
        with pytest.raises(FederationConfigError, match="mapping"):
            load_federation_config(path)

    def test_invalid_default_trust_raises(self, tmp_path: Path) -> None:
        data = {"import": {"default_trust": "invalid"}}
        path = _write_config(tmp_path, data)
        with pytest.raises(FederationConfigError, match="Invalid default_trust"):
            load_federation_config(path)

    def test_invalid_peer_trust_raises(self, tmp_path: Path) -> None:
        data = {"peers": {"bad": {"trust": "bogus"}}}
        path = _write_config(tmp_path, data)
        with pytest.raises(FederationConfigError, match="trust level"):
            load_federation_config(path)


class TestExportPolicyPiiField:
    """Test redact_pii_on_export field on ExportPolicy."""

    def test_default_is_true(self) -> None:
        config = load_federation_config(None)
        assert config.export_policy.redact_pii_on_export is True

    def test_parsed_from_config(self, tmp_path: Path) -> None:
        data = {
            "export": {
                "redact_pii": False,
            },
        }
        path = _write_config(tmp_path, data)
        config = load_federation_config(path)
        assert config.export_policy.redact_pii_on_export is False

    def test_true_when_set(self, tmp_path: Path) -> None:
        data = {
            "export": {
                "redact_pii": True,
            },
        }
        path = _write_config(tmp_path, data)
        config = load_federation_config(path)
        assert config.export_policy.redact_pii_on_export is True


class TestPeerTrust:
    """Test trust level resolution."""

    def _config_with_peer(self) -> FederationConfig:
        return FederationConfig(
            peers={
                "trusted": PeerConfig(name="trusted", trust="full"),
                "verified": PeerConfig(name="verified", trust="verified"),
            },
            import_policy=__import__(
                "engram_r.federation_config", fromlist=["ImportPolicy"]
            ).ImportPolicy(default_trust="untrusted"),
        )

    def test_known_peer_trust(self) -> None:
        config = self._config_with_peer()
        assert config.get_peer_trust("trusted") == "full"
        assert config.get_peer_trust("verified") == "verified"

    def test_unknown_peer_gets_default(self) -> None:
        config = self._config_with_peer()
        assert config.get_peer_trust("stranger") == "untrusted"

    def test_can_import_from_full(self) -> None:
        config = self._config_with_peer()
        assert config.can_import_from("trusted") is True

    def test_can_import_from_verified(self) -> None:
        config = self._config_with_peer()
        assert config.can_import_from("verified") is True

    def test_cannot_import_from_untrusted(self) -> None:
        config = self._config_with_peer()
        assert config.can_import_from("stranger") is False

    def test_quarantine_full_peer(self) -> None:
        config = self._config_with_peer()
        assert config.should_quarantine("trusted") is False

    def test_quarantine_verified_peer(self) -> None:
        config = self._config_with_peer()
        assert config.should_quarantine("verified") is True

    def test_quarantine_unknown_peer(self) -> None:
        config = self._config_with_peer()
        assert config.should_quarantine("stranger") is True
