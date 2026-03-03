"""Domain profile discovery, loading, and application.

Profiles provide domain-specific configuration (palettes, confounders,
heuristics, PII patterns) that customize EngramR for a particular
research field. Profiles live in _code/profiles/{name}/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _profiles_dir(code_dir: Path | None = None) -> Path:
    """Return the profiles directory, defaulting to _code/profiles/."""
    if code_dir is None:
        code_dir = Path(__file__).resolve().parents[2]
    return code_dir / "profiles"


@dataclass
class DomainProfile:
    """Loaded domain profile with all configuration sections."""

    name: str
    description: str
    version: str
    profile_dir: Path
    identity: dict[str, Any] = field(default_factory=dict)
    config_overrides: dict[str, Any] = field(default_factory=dict)
    env_vars: dict[str, Any] = field(default_factory=dict)
    confounders: dict[str, Any] = field(default_factory=dict)
    heuristics: dict[str, Any] = field(default_factory=dict)
    pii_patterns: list[str] = field(default_factory=list)
    palettes: dict[str, Any] = field(default_factory=dict)


def discover_profiles(code_dir: Path | None = None) -> list[str]:
    """List available profile names by scanning the profiles directory."""
    profiles_path = _profiles_dir(code_dir)
    if not profiles_path.is_dir():
        return []
    return sorted(
        d.name
        for d in profiles_path.iterdir()
        if d.is_dir() and (d / "profile.yaml").exists()
    )


def load_profile(name: str, code_dir: Path | None = None) -> DomainProfile:
    """Load a domain profile by name.

    Args:
        name: Profile directory name (e.g. "bioinformatics").
        code_dir: Path to _code/ directory. Auto-detected if None.

    Returns:
        Populated DomainProfile dataclass.

    Raises:
        FileNotFoundError: If profile directory or profile.yaml missing.
        ValueError: If profile.yaml is missing required fields.
    """
    profiles_path = _profiles_dir(code_dir)
    profile_dir = profiles_path / name

    profile_yaml = profile_dir / "profile.yaml"
    if not profile_yaml.exists():
        raise FileNotFoundError(f"Profile '{name}' not found at {profile_yaml}")

    with open(profile_yaml) as f:
        data = yaml.safe_load(f) or {}

    for required in ("name", "description", "version"):
        if required not in data:
            raise ValueError(f"Profile '{name}' missing required field: {required}")

    profile = DomainProfile(
        name=data["name"],
        description=data["description"],
        version=data["version"],
        profile_dir=profile_dir,
        identity=data.get("identity", {}),
        config_overrides=data.get("config_overrides", {}),
        env_vars=data.get("env_vars", {}),
    )

    # Load optional sidecar files
    confounders_path = profile_dir / "confounders.yaml"
    if confounders_path.exists():
        with open(confounders_path) as f:
            profile.confounders = yaml.safe_load(f) or {}

    heuristics_path = profile_dir / "heuristics.yaml"
    if heuristics_path.exists():
        with open(heuristics_path) as f:
            profile.heuristics = yaml.safe_load(f) or {}

    pii_path = profile_dir / "pii_patterns.yaml"
    if pii_path.exists():
        with open(pii_path) as f:
            pii_data = yaml.safe_load(f) or {}
            profile.pii_patterns = pii_data.get("column_patterns", [])

    palettes_path = profile_dir / "palettes.yaml"
    if palettes_path.exists():
        with open(palettes_path) as f:
            profile.palettes = yaml.safe_load(f) or {}

    return profile


def get_active_profile(
    config_path: Path | str, code_dir: Path | None = None
) -> DomainProfile | None:
    """Read the active domain from config and load its profile.

    Args:
        config_path: Path to ops/config.yaml.
        code_dir: Path to _code/ directory. Auto-detected if None.

    Returns:
        DomainProfile if a domain is configured and profile exists, else None.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        return None

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    domain_cfg = config.get("domain", {})
    domain_name = domain_cfg.get("name", "")
    if not domain_name:
        return None

    try:
        return load_profile(domain_name, code_dir)
    except (FileNotFoundError, ValueError):
        return None


def merge_profile_palettes(
    profile: DomainProfile, palettes_yaml_path: Path | str
) -> None:
    """Merge profile palettes into the main palettes.yaml file.

    Adds labs and semantic palettes from the profile into the base
    palettes file. Existing base palettes (binary, direction, sig,
    diverging, sequential) are preserved.

    Args:
        profile: Loaded domain profile.
        palettes_yaml_path: Path to _code/styles/palettes.yaml.
    """
    palettes_yaml_path = Path(palettes_yaml_path)

    if palettes_yaml_path.exists():
        with open(palettes_yaml_path) as f:
            base = yaml.safe_load(f) or {}
    else:
        base = {}

    profile_palettes = profile.palettes
    if not profile_palettes:
        return

    # Merge labs
    if "labs" in profile_palettes:
        if "labs" not in base:
            base["labs"] = {}
        base["labs"].update(profile_palettes["labs"])

    # Merge semantic palettes
    if "semantic" in profile_palettes:
        if "semantic" not in base:
            base["semantic"] = {}
        base["semantic"].update(profile_palettes["semantic"])

    with open(palettes_yaml_path, "w") as f:
        yaml.dump(base, f, default_flow_style=False, sort_keys=False)


def apply_profile_config(profile: DomainProfile, config_path: Path | str) -> None:
    """Merge profile config_overrides into ops/config.yaml.

    Updates the config file with values from the profile's
    config_overrides section. Existing keys not in the override
    are preserved.

    Args:
        profile: Loaded domain profile.
        config_path: Path to ops/config.yaml.
    """
    config_path = Path(config_path)

    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    overrides = profile.config_overrides
    if not overrides:
        return

    def _deep_merge(base: dict, override: dict) -> dict:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                _deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    _deep_merge(config, overrides)

    # Set domain reference
    if "domain" not in config:
        config["domain"] = {}
    config["domain"]["name"] = profile.name
    config["domain"]["profile"] = str(profile.profile_dir)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
