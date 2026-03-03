"""Tests for scripts/init_vault.py scaffold tool."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
import init_vault  # noqa: E402


@pytest.fixture
def source_vault(tmp_path: Path) -> Path:
    """Create a minimal source vault structure for testing."""
    vault = tmp_path / "source"
    vault.mkdir()

    # CLAUDE.md
    (vault / "CLAUDE.md").write_text("# CLAUDE.md\nTest vault.", encoding="utf-8")

    # _code/ (minimal)
    code = vault / "_code"
    code.mkdir()
    (code / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    src = code / "src" / "engram_r"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    tests = code / "tests"
    tests.mkdir()
    (tests / "test_example.py").write_text("def test_pass(): pass\n")

    # _code/templates/
    templates = code / "templates"
    templates.mkdir()
    (templates / "claim-note.md").write_text("---\ntype: claim\n---\n")
    (templates / "hypothesis.md").write_text("---\ntype: hypothesis\n---\n")

    # .claude/hooks/
    hooks = vault / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "session-orient.sh").write_text("#!/bin/bash\necho orient\n")
    (hooks / "auto-commit.sh").write_text("#!/bin/bash\necho commit\n")

    # .claude/skills/
    skills = vault / ".claude" / "skills"
    skills.mkdir(parents=True)
    for s in ["onboard", "reduce", "reflect", "generate", "tournament"]:
        skill_dir = skills / s
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"# {s}\n")
    (skills / "_graph.md").write_text("# Graph\n")

    # ops/
    ops = vault / "ops"
    ops.mkdir()
    (ops / "config.yaml").write_text("dimensions:\n  granularity: atomic\n")
    (ops / "config-reference.yaml").write_text("# reference\n")
    (ops / "daemon-config.yaml").write_text("goals_priority: []\n")
    (ops / "derivation.md").write_text("# Derivation\n")
    (ops / "derivation-manifest.md").write_text("# Manifest\n")

    scripts_dir = ops / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "daemon.sh").write_text("#!/bin/bash\n")

    methodology = ops / "methodology"
    methodology.mkdir()
    (methodology / "index.md").write_text("# Methodology\n")

    # _code/styles/
    code_styles = code / "styles"
    code_styles.mkdir()
    (code_styles / "STYLE_GUIDE.md").write_text("# Style\n")
    (code_styles / "palettes.yaml").write_text("lab_palettes: {}\n")

    # docs/styles/
    doc_styles = vault / "docs" / "styles"
    doc_styles.mkdir(parents=True)
    (doc_styles / "example-lab.md").write_text("# Example Lab\n")

    # self/
    self_dir = vault / "self"
    self_dir.mkdir()
    (self_dir / "identity.md").write_text("# Identity\n")
    (self_dir / "methodology.md").write_text("# Methodology\n")

    # docs/manual/
    manual = vault / "docs" / "manual"
    manual.mkdir(parents=True)
    (manual / "setup-guide.md").write_text("# Setup\n")

    # LICENSE
    (vault / "LICENSE").write_text("MIT\n")

    return vault


@pytest.fixture
def target_path(tmp_path: Path) -> Path:
    """Return a non-existing target path for scaffolding."""
    return tmp_path / "new-vault"


class TestScaffold:
    """Test the scaffold() function."""

    def test_creates_target_directory(
        self, source_vault: Path, target_path: Path
    ) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert target_path.is_dir()

    def test_creates_empty_dirs(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        for d in init_vault._EMPTY_DIRS:
            assert (target_path / d).is_dir(), f"Missing empty dir: {d}"

    def test_copies_templates(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert (target_path / "_code" / "templates" / "claim-note.md").is_file()
        assert (target_path / "_code" / "templates" / "hypothesis.md").is_file()

    def test_copies_hooks(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert (target_path / ".claude" / "hooks" / "session-orient.sh").is_file()

    def test_copies_all_skills_by_default(
        self, source_vault: Path, target_path: Path
    ) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        skills = target_path / ".claude" / "skills"
        assert (skills / "onboard" / "SKILL.md").is_file()
        assert (skills / "generate" / "SKILL.md").is_file()
        assert (skills / "tournament" / "SKILL.md").is_file()

    def test_starter_mode_limits_skills(
        self, source_vault: Path, target_path: Path
    ) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
            starter_only=True,
        )
        skills = target_path / ".claude" / "skills"
        # Starter skills present
        assert (skills / "onboard" / "SKILL.md").is_file()
        assert (skills / "reduce" / "SKILL.md").is_file()
        assert (skills / "reflect" / "SKILL.md").is_file()
        # Full skills absent
        assert not (skills / "generate").is_dir()
        assert not (skills / "tournament").is_dir()

    def test_copies_config_files(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert (target_path / "ops" / "config.yaml").is_file()
        assert (target_path / "ops" / "daemon-config.yaml").is_file()
        assert (target_path / "ops" / "derivation.md").is_file()

    def test_copies_code_directory(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert (target_path / "_code" / "pyproject.toml").is_file()
        assert (
            target_path / "_code" / "src" / "engram_r" / "__init__.py"
        ).is_file()

    def test_excludes_venv_from_code_copy(
        self, source_vault: Path, target_path: Path
    ) -> None:
        # Create a .venv in source
        (source_vault / "_code" / ".venv").mkdir()
        (source_vault / "_code" / ".venv" / "pyvenv.cfg").write_text("x")

        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert not (target_path / "_code" / ".venv").exists()

    def test_creates_gitignore(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        gi = target_path / ".gitignore"
        assert gi.is_file()
        content = gi.read_text()
        assert ".env" in content
        assert "notes/" in content

    def test_creates_env_example(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        env = target_path / ".env.example"
        assert env.is_file()
        assert "OBSIDIAN_API_KEY" in env.read_text()

    def test_creates_arscontexta_marker(
        self, source_vault: Path, target_path: Path
    ) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert (target_path / ".arscontexta").is_dir()

    def test_creates_claude_md(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert (target_path / "CLAUDE.md").is_file()

    def test_creates_readme(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="My Lab",
            init_git=False,
            register=False,
        )
        readme = target_path / "README.md"
        assert readme.is_file()
        assert "My Lab" in readme.read_text()

    def test_creates_goals_template(
        self, source_vault: Path, target_path: Path
    ) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        goals = target_path / "self" / "goals.md"
        assert goals.is_file()
        assert "Active Threads" in goals.read_text()

    def test_creates_reminders(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert (target_path / "ops" / "reminders.md").is_file()

    def test_creates_settings_json(self, source_vault: Path, target_path: Path) -> None:
        import json

        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        settings = target_path / ".claude" / "settings.json"
        assert settings.is_file()
        data = json.loads(settings.read_text(encoding="utf-8"))
        # Should contain skill permissions for the copied skills
        allow = data.get("permissions", {}).get("allow", [])
        skill_entries = [e for e in allow if e.startswith("Skill(")]
        assert len(skill_entries) > 0
        # Each skill on disk should have a corresponding permission
        skills_dir = target_path / ".claude" / "skills"
        disk_skills = {
            d.name
            for d in skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").is_file()
        }
        for name in disk_skills:
            assert f"Skill({name})" in allow


class TestGitInit:
    """Test git initialization."""

    def test_init_git_creates_repo(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=True,
            register=False,
        )
        assert (target_path / ".git").is_dir()

    def test_init_git_makes_initial_commit(
        self, source_vault: Path, target_path: Path
    ) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=True,
            register=False,
        )
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=str(target_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "scaffold EngramR vault" in result.stdout

    def test_no_git_skips_init(self, source_vault: Path, target_path: Path) -> None:
        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
        )
        assert not (target_path / ".git").is_dir()


class TestForce:
    """Test --force behavior."""

    def test_exits_on_existing_nonempty_dir(
        self, source_vault: Path, target_path: Path
    ) -> None:
        target_path.mkdir()
        (target_path / "existing.txt").write_text("hi")

        with pytest.raises(SystemExit):
            init_vault.scaffold(
                target_path,
                source_vault,
                vault_name="Test",
                init_git=False,
                register=False,
                force=False,
            )

    def test_force_overwrites_existing(
        self, source_vault: Path, target_path: Path
    ) -> None:
        target_path.mkdir()
        (target_path / "existing.txt").write_text("hi")

        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test",
            init_git=False,
            register=False,
            force=True,
        )
        assert (target_path / "CLAUDE.md").is_file()
        assert not (target_path / "existing.txt").is_file()


class TestRegister:
    """Test vault registration."""

    def test_creates_registry_if_missing(
        self, source_vault: Path, target_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        # Point registry to a temp location via HOME env var
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        registry = fake_home / ".config" / "engramr" / "vaults.yaml"
        monkeypatch.setenv("HOME", str(fake_home))

        init_vault.scaffold(
            target_path,
            source_vault,
            vault_name="Test Vault",
            init_git=False,
            register=True,
        )
        assert registry.is_file()
        import yaml

        data = yaml.safe_load(registry.read_text())
        assert len(data["vaults"]) == 1
        assert data["vaults"][0]["name"] == "test-vault"
        assert data["vaults"][0]["default"] is True


class TestStarterSkills:
    """Test starter skill list is valid."""

    def test_starter_skills_are_subset_of_all(self) -> None:
        all_skills = set(init_vault._STARTER_SKILLS) | set(init_vault._FULL_SKILLS)
        for s in init_vault._STARTER_SKILLS:
            assert s in all_skills

    def test_no_overlap_between_starter_and_full(self) -> None:
        overlap = set(init_vault._STARTER_SKILLS) & set(init_vault._FULL_SKILLS)
        assert not overlap, f"Overlapping skills: {overlap}"
