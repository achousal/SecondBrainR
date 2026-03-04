"""Shared utilities for Claude Code hook scripts.

Extracts the three functions duplicated across all hooks:
find_vault_root(), load_config(), resolve_vault().

Fixes the .arscontexta marker detection bug (was .is_dir(), marker is a file).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

_CODE_DIR = Path(__file__).resolve().parent.parent.parent  # _code/


def find_vault_root(start: Path | None = None) -> Path:
    """Walk up from *start* (default CWD) looking for the vault root.

    Detection priority:
        1. Walk up looking for ``.arscontexta`` marker (file or directory)
        2. ``PROJECT_DIR`` environment variable
        3. ``git rev-parse --show-toplevel``
        4. Relative fallback from ``_code/``
    """
    d = (start or Path.cwd()).resolve()
    while d != d.parent:
        if (d / ".arscontexta").exists():
            return d
        d = d.parent

    project_dir = os.environ.get("PROJECT_DIR")
    if project_dir:
        p = Path(project_dir)
        if p.is_dir():
            return p

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return _CODE_DIR.parent


def load_config(vault: Path | None = None) -> dict:
    """Load ops/config.yaml from vault root.

    If *vault* is None, resolves it via find_vault_root().
    """
    if vault is None:
        vault = find_vault_root()
    config_path = vault / "ops" / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def resolve_vault(config: dict | None = None) -> Path:
    """Resolve vault root: config > marker walk-up > git > relative.

    If *config* has a ``vault_root`` key, use that path directly.
    Otherwise delegate to find_vault_root().
    """
    if config is None:
        config = load_config()
    if "vault_root" in config:
        return Path(config["vault_root"])
    return find_vault_root()
