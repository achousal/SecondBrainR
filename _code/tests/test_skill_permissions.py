"""Tests for engram_r.skill_permissions module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engram_r.skill_permissions import discover_skills, sync_skill_permissions


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal vault with .claude/settings.json and a few skills."""
    v = tmp_path / "vault"
    v.mkdir()
    (v / ".claude").mkdir()
    (v / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"SessionStart": []}}), encoding="utf-8"
    )
    return v


def _add_skill(vault: Path, name: str) -> None:
    """Helper: create a skill directory with SKILL.md."""
    skill_dir = vault / ".claude" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")


class TestDiscoverSkills:
    def test_empty_dir(self, vault: Path) -> None:
        assert discover_skills(vault) == set()

    def test_no_skills_dir(self, tmp_path: Path) -> None:
        assert discover_skills(tmp_path) == set()

    def test_finds_skills(self, vault: Path) -> None:
        _add_skill(vault, "reduce")
        _add_skill(vault, "reflect")
        assert discover_skills(vault) == {"reduce", "reflect"}

    def test_ignores_dirs_without_skill_md(self, vault: Path) -> None:
        _add_skill(vault, "reduce")
        # Directory without SKILL.md
        (vault / ".claude" / "skills" / "broken").mkdir(parents=True)
        assert discover_skills(vault) == {"reduce"}

    def test_ignores_files_at_skill_level(self, vault: Path) -> None:
        _add_skill(vault, "reduce")
        # File, not directory
        (vault / ".claude" / "skills" / "_graph.md").write_text("# Graph\n")
        assert discover_skills(vault) == {"reduce"}


class TestSyncSkillPermissions:
    def test_adds_skill_entries(self, vault: Path) -> None:
        _add_skill(vault, "reduce")
        _add_skill(vault, "reflect")

        changed = sync_skill_permissions(vault)

        assert changed is True
        data = json.loads(
            (vault / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        allow = data["permissions"]["allow"]
        assert "Skill(reduce)" in allow
        assert "Skill(reflect)" in allow

    def test_idempotent(self, vault: Path) -> None:
        _add_skill(vault, "reduce")

        sync_skill_permissions(vault)
        changed = sync_skill_permissions(vault)

        assert changed is False

    def test_preserves_hooks(self, vault: Path) -> None:
        _add_skill(vault, "reduce")

        sync_skill_permissions(vault)

        data = json.loads(
            (vault / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        assert "hooks" in data
        assert data["hooks"]["SessionStart"] == []

    def test_preserves_non_skill_permissions(self, vault: Path) -> None:
        data = {
            "hooks": {},
            "permissions": {"allow": ["WebSearch", "Bash(cd:*)"]},
        }
        (vault / ".claude" / "settings.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        _add_skill(vault, "reduce")

        sync_skill_permissions(vault)

        result = json.loads(
            (vault / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        allow = result["permissions"]["allow"]
        assert "WebSearch" in allow
        assert "Bash(cd:*)" in allow
        assert "Skill(reduce)" in allow

    def test_removes_stale_skills(self, vault: Path) -> None:
        # Start with a skill permission but no skill on disk
        data = {
            "permissions": {"allow": ["Skill(old-skill)", "Skill(reduce)"]},
        }
        (vault / ".claude" / "settings.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        _add_skill(vault, "reduce")

        changed = sync_skill_permissions(vault)

        assert changed is True
        result = json.loads(
            (vault / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        allow = result["permissions"]["allow"]
        assert "Skill(reduce)" in allow
        assert "Skill(old-skill)" not in allow

    def test_no_settings_file(self, tmp_path: Path) -> None:
        assert sync_skill_permissions(tmp_path) is False

    def test_malformed_json_does_not_crash(self, vault: Path) -> None:
        (vault / ".claude" / "settings.json").write_text("not json", encoding="utf-8")

        result = sync_skill_permissions(vault)

        assert result is False

    def test_starter_vs_full_mode(self, vault: Path) -> None:
        """Only skills on disk get permissions -- starter mode has fewer."""
        starter_skills = ["reduce", "reflect", "verify"]
        for s in starter_skills:
            _add_skill(vault, s)

        sync_skill_permissions(vault)

        data = json.loads(
            (vault / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        skill_entries = [e for e in data["permissions"]["allow"] if e.startswith("Skill(")]
        assert len(skill_entries) == 3

        # Simulate adding more skills (full mode)
        _add_skill(vault, "generate")
        _add_skill(vault, "tournament")
        sync_skill_permissions(vault)

        data = json.loads(
            (vault / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        skill_entries = [e for e in data["permissions"]["allow"] if e.startswith("Skill(")]
        assert len(skill_entries) == 5
