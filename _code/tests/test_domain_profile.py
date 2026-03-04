"""Tests for domain profile discovery, loading, and merging."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engram_r.domain_profile import (
    DomainProfile,
    apply_profile_config,
    discover_profiles,
    get_active_profile,
    load_profile,
    merge_profile_palettes,
)


@pytest.fixture
def profiles_dir(tmp_path: Path) -> Path:
    """Create a minimal profiles directory with a test profile."""
    code_dir = tmp_path / "_code"
    profiles = code_dir / "profiles"
    test_profile = profiles / "test-domain"
    test_profile.mkdir(parents=True)

    # profile.yaml
    (test_profile / "profile.yaml").write_text(
        yaml.dump(
            {
                "name": "test-domain",
                "description": "A test research domain",
                "version": "1.0",
                "identity": {
                    "purpose": "Test agent for test domain research",
                    "domain": "Test domain",
                    "focus_areas": ["area-a", "area-b"],
                },
                "config_overrides": {
                    "data_layers": ["Layer-A", "Layer-B", "Layer-C"],
                    "research": {"primary": "web-search"},
                },
                "env_vars": {"optional": {"TEST_KEY": "For testing purposes"}},
            },
            default_flow_style=False,
        )
    )

    # confounders.yaml
    (test_profile / "confounders.yaml").write_text(
        yaml.dump(
            {
                "Layer-A": ["batch effect", "sample quality"],
                "Layer-B": ["instrument drift"],
                "biological_confounders": ["age", "sex"],
            },
            default_flow_style=False,
        )
    )

    # heuristics.yaml
    (test_profile / "heuristics.yaml").write_text(
        yaml.dump(
            {
                "file_extensions": {".dat": "Layer-A", ".csv": "Layer-B"},
                "tool_references": {"ToolX": "Layer-A"},
            },
            default_flow_style=False,
        )
    )

    # pii_patterns.yaml
    (test_profile / "pii_patterns.yaml").write_text(
        yaml.dump(
            {"column_patterns": ["\\bTEST_ID\\b", "\\bsubject\\s*name\\b"]},
            default_flow_style=False,
        )
    )

    # palettes.yaml
    (test_profile / "palettes.yaml").write_text(
        yaml.dump(
            {
                "labs": {"example-lab": ["#E41A1C", "#377EB8", "#4DAF4A"]},
                "semantic": {"category": {"A": "#E41A1C", "B": "#377EB8"}},
            },
            default_flow_style=False,
        )
    )

    return code_dir


@pytest.fixture
def empty_profiles_dir(tmp_path: Path) -> Path:
    """Create an empty profiles directory."""
    code_dir = tmp_path / "_code"
    (code_dir / "profiles").mkdir(parents=True)
    return code_dir


class TestDiscoverProfiles:
    def test_discovers_profiles(self, profiles_dir: Path) -> None:
        result = discover_profiles(profiles_dir)
        assert result == ["test-domain"]

    def test_empty_dir(self, empty_profiles_dir: Path) -> None:
        result = discover_profiles(empty_profiles_dir)
        assert result == []

    def test_missing_dir(self, tmp_path: Path) -> None:
        result = discover_profiles(tmp_path / "nonexistent")
        assert result == []

    def test_ignores_dirs_without_profile_yaml(self, profiles_dir: Path) -> None:
        # Create a directory without profile.yaml
        (profiles_dir / "profiles" / "no-profile").mkdir()
        result = discover_profiles(profiles_dir)
        assert "no-profile" not in result
        assert result == ["test-domain"]


class TestLoadProfile:
    def test_loads_all_sections(self, profiles_dir: Path) -> None:
        profile = load_profile("test-domain", profiles_dir)
        assert profile.name == "test-domain"
        assert profile.description == "A test research domain"
        assert profile.version == "1.0"
        assert profile.identity["domain"] == "Test domain"
        assert len(profile.config_overrides["data_layers"]) == 3
        assert "Layer-A" in profile.confounders
        assert ".dat" in profile.heuristics["file_extensions"]
        assert len(profile.pii_patterns) == 2
        assert "example-lab" in profile.palettes["labs"]

    def test_missing_profile_raises(self, profiles_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_profile("nonexistent", profiles_dir)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        code_dir = tmp_path / "_code"
        bad_profile = code_dir / "profiles" / "bad"
        bad_profile.mkdir(parents=True)
        (bad_profile / "profile.yaml").write_text(yaml.dump({"name": "bad"}))
        with pytest.raises(ValueError, match="missing required field"):
            load_profile("bad", code_dir)

    def test_optional_files_missing(self, tmp_path: Path) -> None:
        code_dir = tmp_path / "_code"
        minimal = code_dir / "profiles" / "minimal"
        minimal.mkdir(parents=True)
        (minimal / "profile.yaml").write_text(
            yaml.dump(
                {
                    "name": "minimal",
                    "description": "Minimal profile",
                    "version": "0.1",
                }
            )
        )
        profile = load_profile("minimal", code_dir)
        assert profile.confounders == {}
        assert profile.heuristics == {}
        assert profile.pii_patterns == []
        assert profile.palettes == {}


class TestGetActiveProfile:
    def test_returns_profile_when_configured(
        self, profiles_dir: Path, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({"domain": {"name": "test-domain"}}))
        profile = get_active_profile(config_path, profiles_dir)
        assert profile is not None
        assert profile.name == "test-domain"

    def test_returns_none_when_no_domain(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({"processing": {"depth": "standard"}}))
        assert get_active_profile(config_path) is None

    def test_returns_none_when_config_missing(self, tmp_path: Path) -> None:
        assert get_active_profile(tmp_path / "missing.yaml") is None

    def test_returns_none_when_profile_missing(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({"domain": {"name": "nonexistent"}}))
        assert get_active_profile(config_path, tmp_path) is None


class TestMergeProfilePalettes:
    def test_merges_labs_and_semantic(self, profiles_dir: Path, tmp_path: Path) -> None:
        profile = load_profile("test-domain", profiles_dir)
        palettes_path = tmp_path / "palettes.yaml"
        palettes_path.write_text(
            yaml.dump(
                {
                    "semantic": {
                        "binary": {
                            "Control": "#4DAF4A",
                            "Case": "#E41A1C",
                        }
                    }
                }
            )
        )
        merge_profile_palettes(profile, palettes_path)

        with open(palettes_path) as f:
            result = yaml.safe_load(f)

        # Base preserved
        assert result["semantic"]["binary"]["Control"] == "#4DAF4A"
        # Profile merged
        assert "example-lab" in result["labs"]
        assert result["semantic"]["category"]["A"] == "#E41A1C"

    def test_creates_sections_when_missing(
        self, profiles_dir: Path, tmp_path: Path
    ) -> None:
        profile = load_profile("test-domain", profiles_dir)
        palettes_path = tmp_path / "palettes.yaml"
        palettes_path.write_text(yaml.dump({}))
        merge_profile_palettes(profile, palettes_path)

        with open(palettes_path) as f:
            result = yaml.safe_load(f)

        assert "labs" in result
        assert "semantic" in result

    def test_noop_when_no_profile_palettes(self, tmp_path: Path) -> None:
        profile = DomainProfile(
            name="empty",
            description="No palettes",
            version="0.1",
            profile_dir=tmp_path,
        )
        palettes_path = tmp_path / "palettes.yaml"
        palettes_path.write_text(yaml.dump({"semantic": {"sig": {"sig": "#E41A1C"}}}))
        merge_profile_palettes(profile, palettes_path)

        with open(palettes_path) as f:
            result = yaml.safe_load(f)
        assert result == {"semantic": {"sig": {"sig": "#E41A1C"}}}


class TestApplyProfileConfig:
    def test_merges_overrides(self, profiles_dir: Path, tmp_path: Path) -> None:
        profile = load_profile("test-domain", profiles_dir)
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "granularity": "atomic",
                    "data_layers": [],
                    "research": {"primary": "web-search", "fallback": "web-search"},
                }
            )
        )
        apply_profile_config(profile, config_path)

        with open(config_path) as f:
            result = yaml.safe_load(f)

        assert result["granularity"] == "atomic"  # preserved
        assert result["data_layers"] == ["Layer-A", "Layer-B", "Layer-C"]
        assert result["research"]["primary"] == "web-search"  # overridden
        assert result["research"]["fallback"] == "web-search"  # preserved
        assert result["domain"]["name"] == "test-domain"

    def test_creates_config_when_missing(
        self, profiles_dir: Path, tmp_path: Path
    ) -> None:
        profile = load_profile("test-domain", profiles_dir)
        config_path = tmp_path / "new_config.yaml"
        apply_profile_config(profile, config_path)

        with open(config_path) as f:
            result = yaml.safe_load(f)

        assert result["data_layers"] == ["Layer-A", "Layer-B", "Layer-C"]
        assert result["domain"]["name"] == "test-domain"
