"""Tests for engram_r.hook_utils -- shared vault root detection and config loading."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from engram_r.hook_utils import find_vault_root, load_config, resolve_vault


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal vault with .arscontexta marker and config."""
    v = tmp_path / "vault"
    v.mkdir()
    (v / ".arscontexta").write_text("marker", encoding="utf-8")
    ops = v / "ops"
    ops.mkdir()
    (ops / "config.yaml").write_text("schema_validation: true\n", encoding="utf-8")
    return v


class TestFindVaultRoot:
    def test_finds_marker_file(self, vault: Path) -> None:
        """Walk-up finds .arscontexta as a file (not directory)."""
        sub = vault / "a" / "b"
        sub.mkdir(parents=True)
        result = find_vault_root(start=sub)
        assert result == vault

    def test_marker_as_directory(self, tmp_path: Path) -> None:
        """Also works if .arscontexta is a directory (backward compat)."""
        v = tmp_path / "vault"
        v.mkdir()
        (v / ".arscontexta").mkdir()
        result = find_vault_root(start=v)
        assert result == v

    def test_project_dir_env_fallback(self, tmp_path: Path) -> None:
        """Falls back to PROJECT_DIR env var when no marker found."""
        target = tmp_path / "myproject"
        target.mkdir()
        with patch.dict(os.environ, {"PROJECT_DIR": str(target)}):
            # Start from a path with no marker and no git
            with patch("engram_r.hook_utils.subprocess.run", side_effect=FileNotFoundError):
                result = find_vault_root(start=tmp_path / "nowhere")
                assert result == target

    def test_git_fallback(self, tmp_path: Path) -> None:
        """Falls back to git rev-parse when no marker and no PROJECT_DIR."""
        import subprocess as sp

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("engram_r.hook_utils.subprocess.run") as mock_run,
        ):
            # Remove PROJECT_DIR if present
            os.environ.pop("PROJECT_DIR", None)
            mock_run.return_value = sp.CompletedProcess(
                args=[], returncode=0, stdout=str(tmp_path) + "\n"
            )
            result = find_vault_root(start=tmp_path / "nowhere")
            assert result == tmp_path

    def test_relative_fallback(self, tmp_path: Path) -> None:
        """Last resort: return _CODE_DIR.parent."""
        with (
            patch.dict(os.environ, {}, clear=False),
            patch("engram_r.hook_utils.subprocess.run", side_effect=FileNotFoundError),
        ):
            os.environ.pop("PROJECT_DIR", None)
            result = find_vault_root(start=tmp_path / "nowhere")
            # Should be the _code/ parent (repo root)
            assert result.is_dir()


class TestLoadConfig:
    def test_loads_config(self, vault: Path) -> None:
        config = load_config(vault)
        assert config.get("schema_validation") is True

    def test_missing_config_returns_empty(self, tmp_path: Path) -> None:
        config = load_config(tmp_path)
        assert config == {}

    def test_empty_config_returns_empty(self, vault: Path) -> None:
        (vault / "ops" / "config.yaml").write_text("", encoding="utf-8")
        config = load_config(vault)
        assert config == {}


class TestResolveVault:
    def test_config_vault_root_takes_priority(self, tmp_path: Path) -> None:
        target = tmp_path / "custom"
        target.mkdir()
        config = {"vault_root": str(target)}
        result = resolve_vault(config)
        assert result == target

    def test_delegates_to_find_vault_root(self, vault: Path) -> None:
        with patch("engram_r.hook_utils.find_vault_root", return_value=vault):
            result = resolve_vault({})
            assert result == vault
