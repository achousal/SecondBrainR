"""Shared frontmatter parsing and vault-path resolution utilities.

Consolidates _FM_RE, _read_frontmatter, and _default_vault_path that were
previously duplicated across daemon_scheduler, vault_advisor,
metabolic_indicators, schedule_runner, decision_engine, experiment_resolver,
and stub_enricher.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Frontmatter regex
# ---------------------------------------------------------------------------

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def read_frontmatter(path: Path) -> dict:
    """Read YAML frontmatter from a markdown file. Returns {} on failure."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        logger.warning("Cannot read file: %s", path)
        return {}
    m = FM_RE.match(text)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        logger.warning("Malformed YAML frontmatter in %s", path)
        return {}


def default_vault_path() -> Path:
    """Resolve default vault path from registry, environment, or file location.

    Priority:
        1. Vault registry default (~/.config/engramr/vaults.yaml)
        2. VAULT_PATH environment variable
        3. Walk up from this file to find the vault root
    """
    try:
        from engram_r.vault_registry import get_vault_path

        registry_path = get_vault_path()
        if registry_path is not None:
            return registry_path
    except ImportError:
        pass

    env_path = os.environ.get("VAULT_PATH")
    if env_path:
        return Path(env_path)
    # Fallback: walk up from this file to find the vault root
    return Path(__file__).resolve().parents[3]
