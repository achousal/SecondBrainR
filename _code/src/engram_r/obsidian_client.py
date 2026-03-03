"""REST API wrapper for Obsidian Local REST API plugin.

Handles self-signed certificate, authentication, and common CRUD operations
on vault notes.

Reference: https://github.com/coddingtonbear/obsidian-local-rest-api
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class ObsidianAPIError(Exception):
    """Error communicating with the Obsidian REST API."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ObsidianClient:
    """Client for the Obsidian Local REST API.

    Args:
        api_url: Base URL (e.g. https://127.0.0.1:27124).
        api_key: Bearer token for authentication.
        verify_ssl: Whether to verify SSL certificates (False for self-signed).
    """

    api_url: str
    api_key: str
    verify_ssl: bool = False

    @classmethod
    def from_env(cls) -> ObsidianClient:
        """Create client from environment variables.

        Reads OBSIDIAN_API_URL and OBSIDIAN_API_KEY.
        """
        url = os.environ.get("OBSIDIAN_API_URL", "https://127.0.0.1:27124")
        key = os.environ.get("OBSIDIAN_API_KEY", "")
        if not key:
            raise ObsidianAPIError("OBSIDIAN_API_KEY not set in environment")
        return cls(api_url=url.rstrip("/"), api_key=key)

    @classmethod
    def from_vault(cls, name: str) -> ObsidianClient:
        """Create client from a named vault in the registry.

        Looks up the vault in ~/.config/engramr/vaults.yaml and uses
        its api_url and api_key. Falls back to environment variables if
        the registry entry has no api_key.

        Args:
            name: Vault name as defined in the registry.

        Raises:
            ObsidianAPIError: If vault not found or no API key available.
        """
        from engram_r.vault_registry import VaultRegistryError, get_vault

        try:
            vc = get_vault(name)
        except VaultRegistryError as exc:
            raise ObsidianAPIError(str(exc)) from exc

        url = vc.api_url
        key = vc.api_key or os.environ.get("OBSIDIAN_API_KEY", "")
        if not key:
            raise ObsidianAPIError(
                f"No api_key for vault '{name}' and OBSIDIAN_API_KEY not set"
            )
        return cls(api_url=url.rstrip("/"), api_key=key)

    def _make_ssl_context(self) -> ssl.SSLContext:
        if self.verify_ssl:
            return ssl.create_default_context()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        content_type: str = "application/json",
        accept: str = "application/json",
    ) -> dict[str, Any] | str:
        """Make an HTTP request to the Obsidian API.

        Returns parsed JSON or raw text depending on response content type.
        """
        url = f"{self.api_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": content_type,
            "Accept": accept,
        }

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        ctx = self._make_ssl_context()

        try:
            with urllib.request.urlopen(req, context=ctx) as resp:
                body = resp.read().decode("utf-8")
                resp_ct = resp.headers.get("Content-Type", "")
                if "application/json" in resp_ct:
                    return json.loads(body)
                return body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ObsidianAPIError(
                f"{method} {path} -> {exc.code}: {body}",
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise ObsidianAPIError(f"Connection failed: {exc.reason}") from exc

    def get_note(self, vault_path: str) -> str:
        """Read a note's content by vault-relative path.

        Args:
            vault_path: Path relative to vault root
                (e.g. '_research/hypotheses/hyp-001.md').

        Returns:
            Note content as string.
        """
        encoded = urllib.parse.quote(vault_path, safe="")
        result = self._request(
            "GET",
            f"/vault/{encoded}",
            accept="text/markdown",
        )
        return str(result)

    def create_note(self, vault_path: str, content: str) -> None:
        """Create or overwrite a note.

        Args:
            vault_path: Path relative to vault root.
            content: Markdown content.
        """
        encoded = urllib.parse.quote(vault_path, safe="")
        self._request(
            "PUT",
            f"/vault/{encoded}",
            data=content.encode("utf-8"),
            content_type="text/markdown",
        )

    def append_to_note(self, vault_path: str, content: str) -> None:
        """Append content to an existing note.

        Args:
            vault_path: Path relative to vault root.
            content: Content to append.
        """
        encoded = urllib.parse.quote(vault_path, safe="")
        self._request(
            "POST",
            f"/vault/{encoded}",
            data=content.encode("utf-8"),
            content_type="text/markdown",
        )

    def patch_note(self, vault_path: str, content: str) -> None:
        """Patch (partially update) a note's content.

        Args:
            vault_path: Path relative to vault root.
            content: New content to replace the note body.
        """
        encoded = urllib.parse.quote(vault_path, safe="")
        self._request(
            "PATCH",
            f"/vault/{encoded}",
            data=content.encode("utf-8"),
            content_type="text/markdown",
        )

    def delete_note(self, vault_path: str) -> None:
        """Delete a note from the vault.

        Args:
            vault_path: Path relative to vault root.
        """
        encoded = urllib.parse.quote(vault_path, safe="")
        self._request("DELETE", f"/vault/{encoded}")

    def list_notes(self, folder: str = "/") -> list[str]:
        """List all files under a vault folder.

        Args:
            folder: Vault-relative folder path.

        Returns:
            List of file paths relative to vault root.
        """
        encoded = urllib.parse.quote(folder, safe="")
        result = self._request("GET", f"/vault/{encoded}")
        if isinstance(result, dict) and "files" in result:
            return result["files"]
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search vault notes using Obsidian's search.

        Args:
            query: Search query string.

        Returns:
            List of search result dicts.
        """
        data = json.dumps({"query": query}).encode("utf-8")
        result = self._request("POST", "/search/", data=data)
        if isinstance(result, list):
            return result
        return []

    def update_frontmatter(self, vault_path: str, field: str, value: Any) -> None:
        """Read a note, update one frontmatter field, and write back.

        Convenience method combining get + parse + update + put.

        Args:
            vault_path: Path relative to vault root.
            field: Frontmatter field name.
            value: New value.
        """
        from engram_r.hypothesis_parser import update_frontmatter_field

        content = self.get_note(vault_path)
        updated = update_frontmatter_field(content, field, value)
        self.create_note(vault_path, updated)
