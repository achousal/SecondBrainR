"""Vault registry for multi-vault EngramR deployments.

Reads ~/.config/engramr/vaults.yaml to resolve vault names to
filesystem paths and API credentials. Falls back gracefully when no
registry file exists, preserving backward compatibility with the
single-vault OBSIDIAN_API_KEY / VAULT_PATH environment variable pattern.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY_PATH = Path("~/.config/engramr/vaults.yaml").expanduser()


class VaultRegistryError(Exception):
    """Error loading or querying the vault registry."""


@dataclass(frozen=True)
class VaultConfig:
    """Configuration for a single vault instance.

    Attributes:
        name: Human-readable vault identifier (used in CLI flags, logs).
        path: Absolute filesystem path to the vault root.
        api_url: Optional. Obsidian Local REST API base URL.
            Used by obsidian_client.py for API-based vault access.
        api_key: Optional. Bearer token for the Obsidian API.
            Used by obsidian_client.py for API-based vault access.
        port: Optional. Obsidian API port.
            Used by obsidian_client.py for API-based vault access.
        is_default: Whether this vault is the default when no name is given.
    """

    name: str
    path: Path
    api_url: str = "https://127.0.0.1:27124"
    api_key: str = ""
    port: int = 27124
    is_default: bool = False


def _resolve_path(raw: str) -> Path:
    """Expand ~ and resolve a path string to an absolute Path."""
    return Path(raw).expanduser().resolve()


def _parse_vault_entry(entry: dict) -> VaultConfig | None:
    """Parse a single vault entry from the registry YAML.

    Returns None and logs a warning if the entry is malformed.
    """
    if not isinstance(entry, dict):
        logger.warning("Skipping non-dict vault entry: %s", entry)
        return None
    name = entry.get("name")
    path = entry.get("path")
    if not name or not path:
        logger.warning("Skipping vault entry missing name or path: %s", entry)
        return None
    return VaultConfig(
        name=str(name),
        path=_resolve_path(str(path)),
        api_url=str(entry.get("api_url", "https://127.0.0.1:27124")),
        api_key=str(entry.get("api_key", "")),
        port=int(entry.get("port", 27124)),
        is_default=bool(entry.get("default", False)),
    )


def load_registry(
    registry_path: Path | None = None,
) -> list[VaultConfig]:
    """Load vault configurations from the registry file.

    Args:
        registry_path: Path to vaults.yaml. Defaults to
            ~/.config/engramr/vaults.yaml.

    Returns:
        List of VaultConfig entries. Empty list if file does not exist.

    Raises:
        VaultRegistryError: If file exists but is malformed.
    """
    path = registry_path or _DEFAULT_REGISTRY_PATH
    if not path.is_file():
        return []

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise VaultRegistryError(f"Malformed registry: {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise VaultRegistryError(f"Registry must be a YAML mapping: {path}")

    vaults_raw = raw.get("vaults", [])
    if not isinstance(vaults_raw, list):
        raise VaultRegistryError(f"'vaults' must be a list in {path}")

    vaults: list[VaultConfig] = []
    for entry in vaults_raw:
        vc = _parse_vault_entry(entry)
        if vc is not None:
            vaults.append(vc)

    return vaults


def get_vault(
    name: str,
    registry_path: Path | None = None,
) -> VaultConfig:
    """Look up a vault by name.

    Args:
        name: Vault name as defined in the registry.
        registry_path: Override registry file path.

    Returns:
        VaultConfig for the named vault.

    Raises:
        VaultRegistryError: If vault not found or registry missing/empty.
    """
    vaults = load_registry(registry_path)
    for v in vaults:
        if v.name == name:
            return v
    available = [v.name for v in vaults]
    raise VaultRegistryError(
        f"Vault '{name}' not found in registry. Available: {available}"
    )


def get_default_vault(
    registry_path: Path | None = None,
) -> VaultConfig | None:
    """Return the default vault, or None if no registry/default exists.

    Priority:
        1. Vault marked ``default: true`` in registry.
        2. First vault in registry (if exactly one vault is registered).
        3. None (caller should fall back to env vars / CWD detection).

    Args:
        registry_path: Override registry file path.

    Returns:
        VaultConfig or None.
    """
    vaults = load_registry(registry_path)
    if not vaults:
        return None

    for v in vaults:
        if v.is_default:
            return v

    if len(vaults) == 1:
        return vaults[0]

    return None


def get_vault_path(
    name: str | None = None,
    registry_path: Path | None = None,
) -> Path | None:
    """Convenience: resolve a vault name to its filesystem path.

    Falls back to VAULT_PATH env var if the registry is absent or the
    name is not found.

    Args:
        name: Vault name. If None, returns the default vault path.
        registry_path: Override registry file path.

    Returns:
        Resolved Path, or None if nothing could be determined.
    """
    try:
        if name:
            return get_vault(name, registry_path).path
        vc = get_default_vault(registry_path)
        if vc is not None:
            return vc.path
    except VaultRegistryError:
        pass

    env_path = os.environ.get("VAULT_PATH")
    if env_path:
        return _resolve_path(env_path)

    return None
