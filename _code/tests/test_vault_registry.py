"""Tests for vault registry -- loading, lookup, fallback behavior."""

from pathlib import Path

import pytest
import yaml

from engram_r.vault_registry import (
    VaultConfig,
    VaultRegistryError,
    get_default_vault,
    get_vault,
    get_vault_path,
    load_registry,
)


@pytest.fixture
def registry_dir(tmp_path):
    """Create a tmp directory for registry files."""
    return tmp_path


def _write_registry(path: Path, data: dict) -> Path:
    """Write a registry YAML file and return its path."""
    registry = path / "vaults.yaml"
    registry.write_text(yaml.dump(data))
    return registry


class TestLoadRegistry:
    def test_missing_file_returns_empty(self, registry_dir):
        missing = registry_dir / "nonexistent.yaml"
        result = load_registry(missing)
        assert result == []

    def test_single_vault(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {
                "vaults": [
                    {
                        "name": "main",
                        "path": "/tmp/test-vault",
                        "api_url": "https://127.0.0.1:27124",
                        "api_key": "test-key",
                        "port": 27124,
                        "default": True,
                    }
                ]
            },
        )
        result = load_registry(reg)
        assert len(result) == 1
        assert result[0].name == "main"
        assert result[0].path == Path("/tmp/test-vault").resolve()
        assert result[0].api_key == "test-key"
        assert result[0].is_default is True

    def test_multiple_vaults(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {
                "vaults": [
                    {"name": "a", "path": "/tmp/a", "default": True},
                    {"name": "b", "path": "/tmp/b"},
                ]
            },
        )
        result = load_registry(reg)
        assert len(result) == 2
        assert result[0].name == "a"
        assert result[1].name == "b"

    def test_malformed_yaml_raises(self, registry_dir):
        reg = registry_dir / "vaults.yaml"
        reg.write_text(": : : invalid yaml [[[")
        with pytest.raises(VaultRegistryError, match="Malformed"):
            load_registry(reg)

    def test_non_dict_root_raises(self, registry_dir):
        reg = _write_registry(registry_dir, ["not", "a", "dict"])
        with pytest.raises(VaultRegistryError, match="must be a YAML mapping"):
            load_registry(reg)

    def test_vaults_not_list_raises(self, registry_dir):
        reg = _write_registry(registry_dir, {"vaults": "not-a-list"})
        with pytest.raises(VaultRegistryError, match="must be a list"):
            load_registry(reg)

    def test_skips_malformed_entries(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {
                "vaults": [
                    {"name": "good", "path": "/tmp/good"},
                    {"name": "no-path"},  # missing path
                    "bare-string",  # not a dict
                    {"path": "/tmp/no-name"},  # missing name
                ]
            },
        )
        result = load_registry(reg)
        assert len(result) == 1
        assert result[0].name == "good"

    def test_defaults_for_optional_fields(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {"vaults": [{"name": "minimal", "path": "/tmp/min"}]},
        )
        result = load_registry(reg)
        assert len(result) == 1
        v = result[0]
        assert v.api_url == "https://127.0.0.1:27124"
        assert v.api_key == ""
        assert v.port == 27124
        assert v.is_default is False

    def test_tilde_expansion(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {"vaults": [{"name": "home", "path": "~/my-vault"}]},
        )
        result = load_registry(reg)
        assert "~" not in str(result[0].path)
        assert result[0].path.is_absolute()


class TestGetVault:
    def test_found(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {
                "vaults": [
                    {"name": "alpha", "path": "/tmp/alpha"},
                    {"name": "beta", "path": "/tmp/beta"},
                ]
            },
        )
        result = get_vault("beta", registry_path=reg)
        assert result.name == "beta"

    def test_not_found_raises(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {"vaults": [{"name": "only", "path": "/tmp/only"}]},
        )
        with pytest.raises(VaultRegistryError, match="not found"):
            get_vault("missing", registry_path=reg)

    def test_empty_registry_raises(self, registry_dir):
        reg = _write_registry(registry_dir, {"vaults": []})
        with pytest.raises(VaultRegistryError, match="not found"):
            get_vault("any", registry_path=reg)


class TestGetDefaultVault:
    def test_explicit_default(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {
                "vaults": [
                    {"name": "a", "path": "/tmp/a"},
                    {"name": "b", "path": "/tmp/b", "default": True},
                ]
            },
        )
        result = get_default_vault(registry_path=reg)
        assert result is not None
        assert result.name == "b"

    def test_single_vault_is_default(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {"vaults": [{"name": "solo", "path": "/tmp/solo"}]},
        )
        result = get_default_vault(registry_path=reg)
        assert result is not None
        assert result.name == "solo"

    def test_multiple_no_default_returns_none(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {
                "vaults": [
                    {"name": "a", "path": "/tmp/a"},
                    {"name": "b", "path": "/tmp/b"},
                ]
            },
        )
        result = get_default_vault(registry_path=reg)
        assert result is None

    def test_empty_registry_returns_none(self, registry_dir):
        reg = _write_registry(registry_dir, {"vaults": []})
        result = get_default_vault(registry_path=reg)
        assert result is None

    def test_missing_file_returns_none(self, registry_dir):
        missing = registry_dir / "missing.yaml"
        result = get_default_vault(registry_path=missing)
        assert result is None


class TestGetVaultPath:
    def test_named_vault(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {"vaults": [{"name": "test", "path": "/tmp/test-vault"}]},
        )
        result = get_vault_path("test", registry_path=reg)
        assert result == Path("/tmp/test-vault").resolve()

    def test_default_vault(self, registry_dir):
        reg = _write_registry(
            registry_dir,
            {"vaults": [{"name": "def", "path": "/tmp/def", "default": True}]},
        )
        result = get_vault_path(None, registry_path=reg)
        assert result == Path("/tmp/def").resolve()

    def test_fallback_to_env(self, registry_dir, monkeypatch):
        monkeypatch.setenv("VAULT_PATH", "/tmp/from-env")
        missing = registry_dir / "missing.yaml"
        result = get_vault_path(None, registry_path=missing)
        assert result == Path("/tmp/from-env").resolve()

    def test_no_registry_no_env_returns_none(self, registry_dir, monkeypatch):
        monkeypatch.delenv("VAULT_PATH", raising=False)
        missing = registry_dir / "missing.yaml"
        result = get_vault_path(None, registry_path=missing)
        assert result is None

    def test_named_not_found_falls_back_to_env(self, registry_dir, monkeypatch):
        monkeypatch.setenv("VAULT_PATH", "/tmp/fallback")
        reg = _write_registry(
            registry_dir,
            {"vaults": [{"name": "other", "path": "/tmp/other"}]},
        )
        result = get_vault_path("missing", registry_path=reg)
        assert result == Path("/tmp/fallback").resolve()


class TestVaultConfig:
    def test_frozen(self):
        vc = VaultConfig(name="test", path=Path("/tmp"))
        with pytest.raises(AttributeError):
            vc.name = "changed"

    def test_defaults(self):
        vc = VaultConfig(name="x", path=Path("/tmp"))
        assert vc.api_url == "https://127.0.0.1:27124"
        assert vc.api_key == ""
        assert vc.port == 27124
        assert vc.is_default is False
