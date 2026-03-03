"""Tests for Obsidian REST API client.

Uses monkeypatching to avoid actual HTTP calls.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from engram_r.obsidian_client import ObsidianAPIError, ObsidianClient


@pytest.fixture
def client():
    return ObsidianClient(
        api_url="https://127.0.0.1:27124",
        api_key="test-key",
        verify_ssl=False,
    )


class TestObsidianClientInit:
    def test_from_env_missing_key(self, monkeypatch):
        monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
        with pytest.raises(ObsidianAPIError, match="OBSIDIAN_API_KEY"):
            ObsidianClient.from_env()

    def test_from_env_success(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_API_KEY", "my-key")
        monkeypatch.setenv("OBSIDIAN_API_URL", "https://localhost:9999")
        c = ObsidianClient.from_env()
        assert c.api_key == "my-key"
        assert c.api_url == "https://localhost:9999"

    def test_from_env_default_url(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_API_KEY", "k")
        monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)
        c = ObsidianClient.from_env()
        assert c.api_url == "https://127.0.0.1:27124"


class TestObsidianClientMethods:
    """Test client methods with mocked HTTP."""

    def _mock_urlopen(self, body, content_type="application/json", status=200):
        """Create a mock for urllib.request.urlopen."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = body.encode("utf-8")
        mock_resp.headers = {"Content-Type": content_type}
        mock_resp.status = status
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("urllib.request.urlopen")
    def test_get_note(self, mock_urlopen, client):
        mock_urlopen.return_value = self._mock_urlopen(
            "# Hello", content_type="text/markdown"
        )
        result = client.get_note("test/note.md")
        assert result == "# Hello"

    @patch("urllib.request.urlopen")
    def test_create_note(self, mock_urlopen, client):
        mock_urlopen.return_value = self._mock_urlopen("{}")
        client.create_note("test/note.md", "# Content")
        # Verify the request was made
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_list_notes(self, mock_urlopen, client):
        mock_urlopen.return_value = self._mock_urlopen(
            json.dumps({"files": ["a.md", "b.md"]})
        )
        result = client.list_notes("test/")
        assert result == ["a.md", "b.md"]

    @patch("urllib.request.urlopen")
    def test_search(self, mock_urlopen, client):
        mock_urlopen.return_value = self._mock_urlopen(
            json.dumps([{"filename": "test.md", "score": 1.0}])
        )
        result = client.search("query")
        assert len(result) == 1

    @patch("urllib.request.urlopen")
    def test_append_to_note(self, mock_urlopen, client):
        mock_urlopen.return_value = self._mock_urlopen("{}")
        client.append_to_note("test/note.md", "\nAppended text")
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_delete_note(self, mock_urlopen, client):
        mock_urlopen.return_value = self._mock_urlopen("{}")
        client.delete_note("test/note.md")
        mock_urlopen.assert_called_once()


class TestFromVault:
    """Test ObsidianClient.from_vault() classmethod."""

    def _write_registry(self, tmp_path, vaults):
        reg = tmp_path / "vaults.yaml"
        reg.write_text(yaml.dump({"vaults": vaults}))
        return reg

    def test_from_vault_success(self, tmp_path, monkeypatch):
        reg = self._write_registry(
            tmp_path,
            [
                {
                    "name": "test",
                    "path": "/tmp/test",
                    "api_url": "https://localhost:8888",
                    "api_key": "vault-key",
                }
            ],
        )
        with patch(
            "engram_r.vault_registry._DEFAULT_REGISTRY_PATH", reg
        ):
            c = ObsidianClient.from_vault("test")
        assert c.api_key == "vault-key"
        assert c.api_url == "https://localhost:8888"

    def test_from_vault_falls_back_to_env_key(self, tmp_path, monkeypatch):
        reg = self._write_registry(
            tmp_path,
            [{"name": "nokey", "path": "/tmp/nokey"}],
        )
        monkeypatch.setenv("OBSIDIAN_API_KEY", "env-key")
        with patch(
            "engram_r.vault_registry._DEFAULT_REGISTRY_PATH", reg
        ):
            c = ObsidianClient.from_vault("nokey")
        assert c.api_key == "env-key"

    def test_from_vault_no_key_anywhere(self, tmp_path, monkeypatch):
        reg = self._write_registry(
            tmp_path,
            [{"name": "nokey", "path": "/tmp/nokey"}],
        )
        monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
        with patch(
            "engram_r.vault_registry._DEFAULT_REGISTRY_PATH", reg
        ):
            with pytest.raises(ObsidianAPIError, match="No api_key"):
                ObsidianClient.from_vault("nokey")

    def test_from_vault_not_found(self, tmp_path):
        reg = self._write_registry(tmp_path, [])
        with patch(
            "engram_r.vault_registry._DEFAULT_REGISTRY_PATH", reg
        ):
            with pytest.raises(ObsidianAPIError, match="not found"):
                ObsidianClient.from_vault("missing")


class TestObsidianAPIError:
    def test_has_status_code(self):
        err = ObsidianAPIError("test error", status_code=404)
        assert err.status_code == 404
        assert "test error" in str(err)

    def test_no_status_code(self):
        err = ObsidianAPIError("connection failed")
        assert err.status_code is None
