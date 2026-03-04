"""Scaffold a new EngramR vault.

Creates the full directory structure, copies templates, hooks, skills,
config files, and optionally initializes git. Designed for non-interactive
batch use with CLI flags; prompts only when --interactive is passed.

Usage:
    uv run python scripts/init_vault.py /path/to/new-vault
    uv run python scripts/init_vault.py /path/to/new-vault --name "My Lab"
    uv run python scripts/init_vault.py /path/to/new-vault --no-git
    uv run python scripts/init_vault.py /path/to/new-vault --starter

Exit codes:
    0 - success
    1 - target already exists (unless --force)
    2 - source vault not found
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# Directories relative to the source vault root that are copied verbatim.
_COPY_DIRS: list[str] = [
    ".claude/hooks",
    ".claude/skills",
    "ops/scripts",
    "ops/methodology",
    "docs/manual",
    "docs/styles",
]

# Individual files copied from the source vault root.
_COPY_FILES: list[str] = [
    "ops/config.yaml",
    "ops/config-reference.yaml",
    "ops/daemon-config.yaml",
    "ops/derivation.md",
    "ops/derivation-manifest.md",
    "self/identity.md",
    "self/methodology.md",
    "LICENSE",
]

# Directories created empty for runtime state (gitignored).
_EMPTY_DIRS: list[str] = [
    "notes",
    "inbox",
    "archive",
    "_dev",
    "_research/goals",
    "_research/hypotheses",
    "_research/literature",
    "_research/experiments",
    "_research/eda-reports",
    "_research/tournaments",
    "_research/meta-reviews",
    "_research/landscape",
    "ops/sessions",
    "ops/daemon/logs",
    "ops/daemon/markers",
    "ops/health",
    "ops/observations",
    "ops/tensions",
    "ops/queue",
    "projects",
]

# Starter skills -- the minimal subset for new users.
_STARTER_SKILLS: list[str] = [
    "onboard",
    "init",
    "reduce",
    "reflect",
    "reweave",
    "verify",
    "validate",
    "seed",
    "next",
    "stats",
    "graph",
    "tasks",
    "pipeline",
]

# Full co-scientist skills added with --full (default).
_FULL_SKILLS: list[str] = [
    "generate",
    "review",
    "tournament",
    "evolve",
    "landscape",
    "meta-review",
    "research",
    "literature",
    "experiment",
    "eda",
    "plot",
    "project",
    "learn",
    "remember",
    "rethink",
    "ralph",
    "refactor",
    "federation-sync",
]


def _find_source_vault() -> Path:
    """Locate the source vault (the repo containing this script)."""
    # scripts/init_vault.py -> _code/scripts/init_vault.py -> vault root
    script_dir = Path(__file__).resolve().parent
    code_dir = script_dir.parent  # _code/
    vault_root = code_dir.parent  # vault root
    if (vault_root / "_code" / "templates").is_dir() and (vault_root / "CLAUDE.md").is_file():
        return vault_root
    log.error("Cannot find source vault from script location: %s", script_dir)
    sys.exit(2)


def _copy_dir(src: Path, dst: Path) -> None:
    """Copy a directory tree, creating parents as needed."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    log.info("  copied %s/", dst.name)


def _copy_file(src: Path, dst: Path) -> None:
    """Copy a single file, creating parent dirs as needed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    log.info("  copied %s", dst.relative_to(dst.parent.parent))


def _create_gitignore(target: Path) -> None:
    """Write a .gitignore suitable for a new vault."""
    content = """\
# Environment and secrets
.env
.env.local

# Python
*.pyc
__pycache__/
*.egg-info/
dist/
build/
_code/.venv/
_code/.mypy_cache/
_code/.pytest_cache/
_code/.ruff_cache/
_code/.coverage
_code/htmlcov/
.coverage

# R
.Rhistory
.RData
.Rproj.user/

# OS
.DS_Store
Thumbs.db

# Obsidian (users configure their own)
.obsidian/

# Claude Code local settings
.claude/settings.local.json
.claude/settings.json.pre-arscontexta

# Session transcripts and daemon operational data
ops/sessions/
ops/daemon/logs/
ops/daemon/markers/
ops/daemon/.daemon.pid

# Development scratch
_dev/

# === Vault content (user-specific, local only) ===
notes/
_research/goals/
_research/hypotheses/
_research/literature/
_research/experiments/
_research/eda-reports/
_research/tournaments/
_research/meta-reviews/
_research/landscape/
_research/data-inventory.md
_research/landscape.md
inbox/
self/goals.md
ops/daemon-inbox.md
ops/tasks.md
ops/next-log.md
ops/reminders.md
ops/health/
ops/observations/
ops/tensions/
ops/queue/
projects/
_code/profiles/*/styles/PLOT_DESIGN.md
.claude/worktrees/
"""
    (target / ".gitignore").write_text(content, encoding="utf-8")
    log.info("  created .gitignore")


def _create_env_example(target: Path) -> None:
    """Write a .env.example with placeholder variables."""
    content = """\
# Obsidian Local REST API
OBSIDIAN_API_KEY=your-api-key-here
OBSIDIAN_API_URL=https://127.0.0.1:27124

# Optional: biomedical domain (uncomment if using bioinformatics profile)
# NCBI_API_KEY=your-ncbi-api-key-here
# NCBI_EMAIL=your-email@example.com
"""
    (target / ".env.example").write_text(content, encoding="utf-8")
    log.info("  created .env.example")


def _create_arscontexta_marker(target: Path) -> None:
    """Create the .arscontexta directory marker for vault root detection."""
    marker = target / ".arscontexta"
    marker.mkdir(exist_ok=True)
    (marker / ".gitkeep").touch()
    log.info("  created .arscontexta/ marker")


def _create_claude_md(target: Path, source: Path, vault_name: str) -> None:
    """Copy CLAUDE.md from source, replacing vault-specific references."""
    src_claude = source / "CLAUDE.md"
    if src_claude.is_file():
        content = src_claude.read_text(encoding="utf-8")
        (target / "CLAUDE.md").write_text(content, encoding="utf-8")
        log.info("  copied CLAUDE.md")
    else:
        log.warning("  CLAUDE.md not found in source vault")


def _create_readme(target: Path, vault_name: str) -> None:
    """Create a minimal README.md for the new vault."""
    content = f"""\
# {vault_name}

A EngramR research knowledge vault.

## Quick Start

1. Copy `.env.example` to `.env` and fill in your API keys
2. Install Python dependencies: `cd _code && uv sync`
3. Open this directory as an Obsidian vault
4. Install the Obsidian Local REST API community plugin
5. Start Claude Code in this directory

## Starter Commands

| Command | What it does |
|---------|-------------|
| `/onboard` | Bootstrap lab integration (projects, data inventory, goals) |
| `/reduce` | Extract claims from inbox sources |
| `/reflect` | Find connections between notes |
| `/next` | Get the most valuable next action |
| `/stats` | Show vault statistics |

## Running the Daemon

```bash
tmux new -s daemon 'bash ops/scripts/daemon.sh'
```

## Running Tests

```bash
cd _code
uv run pytest tests/ -v --cov=engram_r
```

## Documentation

- `CLAUDE.md` -- Full system architecture and instructions
- `docs/manual/` -- Detailed workflow documentation
- `ops/config.yaml` -- Knowledge system configuration
- `ops/config-reference.yaml` -- All valid configuration values
"""
    (target / "README.md").write_text(content, encoding="utf-8")
    log.info("  created README.md")


def _create_goals_template(target: Path) -> None:
    """Create an empty self/goals.md placeholder."""
    goals = target / "self" / "goals.md"
    goals.parent.mkdir(parents=True, exist_ok=True)
    content = """\
# Goals

## Active Threads

(No active threads yet. Use /onboard to bootstrap your first lab integration.)

## Vault State

Claims: 0 | Inbox: 0
"""
    goals.write_text(content, encoding="utf-8")
    log.info("  created self/goals.md")


def _create_reminders(target: Path) -> None:
    """Create an empty ops/reminders.md."""
    reminders = target / "ops" / "reminders.md"
    reminders.parent.mkdir(parents=True, exist_ok=True)
    content = """\
# Reminders

(No reminders yet.)
"""
    reminders.write_text(content, encoding="utf-8")
    log.info("  created ops/reminders.md")


def _copy_code_dir(source: Path, target: Path) -> None:
    """Copy _code/ directory, excluding venv, caches, and coverage."""
    src_code = source / "_code"
    dst_code = target / "_code"

    exclude = {
        ".venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".coverage",
        "htmlcov",
        ".claude",
        ".git",
    }

    def _ignore(directory: str, contents: list[str]) -> list[str]:
        return [c for c in contents if c in exclude]

    shutil.copytree(src_code, dst_code, ignore=_ignore)
    log.info("  copied _code/ (Python + R library)")


def _init_git(target: Path) -> None:
    """Initialize a git repository and make the initial commit."""
    subprocess.run(
        ["git", "init"],
        cwd=str(target),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=str(target),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: scaffold EngramR vault"],
        cwd=str(target),
        capture_output=True,
        check=True,
    )
    log.info("  initialized git repository with initial commit")


def _register_vault(target: Path, vault_name: str) -> None:
    """Add the new vault to the vault registry if it exists."""
    registry_path = Path.home() / ".config" / "engramr" / "vaults.yaml"
    if not registry_path.exists():
        # Create registry with this as the first (default) vault
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        import yaml

        data = {
            "vaults": [
                {
                    "name": vault_name.lower().replace(" ", "-"),
                    "path": str(target.resolve()),
                    "default": True,
                }
            ]
        }
        registry_path.write_text(
            yaml.dump(data, default_flow_style=False), encoding="utf-8"
        )
        log.info("  created vault registry at %s", registry_path)
    else:
        log.info(
            "  vault registry exists at %s -- add this vault manually",
            registry_path,
        )


def _create_settings_json(target: Path, source: Path) -> None:
    """Create .claude/settings.json with hooks from source + skill permissions from disk.

    Reads hooks from the source vault's settings.json and generates Skill()
    permission entries by scanning the target's .claude/skills/ directory.
    """
    settings_dir = target / ".claude"
    settings_dir.mkdir(exist_ok=True)

    # Start with hooks from source settings.json (if present)
    source_settings = source / ".claude" / "settings.json"
    if source_settings.is_file():
        try:
            data = json.loads(source_settings.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    # Scan target's skills directory for Skill() permission entries
    skills_dir = target / ".claude" / "skills"
    skill_names: set[str] = set()
    if skills_dir.is_dir():
        skill_names = {
            d.name
            for d in skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").is_file()
        }

    if skill_names:
        allow = data.get("permissions", {}).get("allow", [])
        non_skill = [e for e in allow if not e.startswith("Skill(")]
        skill_entries = sorted(f"Skill({name})" for name in skill_names)
        data.setdefault("permissions", {})["allow"] = non_skill + skill_entries

    (settings_dir / "settings.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    log.info("  created settings.json (hooks + %d skill permissions)", len(skill_names))


def scaffold(
    target: Path,
    source: Path,
    *,
    vault_name: str = "My Research Vault",
    init_git: bool = True,
    starter_only: bool = False,
    register: bool = True,
    force: bool = False,
) -> None:
    """Create a new vault at *target* from the *source* vault template."""
    target = target.resolve()

    if target.exists() and any(target.iterdir()):
        if not force:
            log.error(
                "Target %s already exists and is not empty. Use --force to overwrite.",
                target,
            )
            sys.exit(1)
        log.warning("--force: removing existing %s", target)
        shutil.rmtree(target)

    target.mkdir(parents=True, exist_ok=True)
    log.info("Scaffolding vault at %s", target)

    # 1. Create empty runtime directories
    log.info("Creating directory structure...")
    for d in _EMPTY_DIRS:
        (target / d).mkdir(parents=True, exist_ok=True)
        (target / d / ".gitkeep").touch()

    # 2. Copy template directories
    log.info("Copying templates and configuration...")
    for d in _COPY_DIRS:
        src = source / d
        if d == ".claude/skills" and starter_only:
            # Copy only starter skills
            dst = target / d
            dst.mkdir(parents=True, exist_ok=True)
            for skill_name in _STARTER_SKILLS:
                skill_src = src / skill_name
                if skill_src.is_dir():
                    _copy_dir(skill_src, dst / skill_name)
            # Also copy _graph.md if present
            graph_md = src / "_graph.md"
            if graph_md.is_file():
                _copy_file(graph_md, dst / "_graph.md")
        elif src.is_dir():
            _copy_dir(src, target / d)
        else:
            log.warning("  skipped %s (not found in source)", d)

    # 3. Copy individual config files
    for f in _COPY_FILES:
        src = source / f
        if src.is_file():
            _copy_file(src, target / f)
        else:
            log.warning("  skipped %s (not found in source)", f)

    # 4. Copy _code/ directory
    log.info("Copying code library...")
    _copy_code_dir(source, target)

    # 5. Generate scaffold files
    log.info("Generating scaffold files...")
    _create_gitignore(target)
    _create_env_example(target)
    _create_arscontexta_marker(target)
    _create_claude_md(target, source, vault_name)
    _create_readme(target, vault_name)
    _create_goals_template(target)
    _create_reminders(target)

    # 6. Create .claude/settings.json with hooks + skill permissions
    _create_settings_json(target, source)

    # 7. Initialize git
    if init_git:
        log.info("Initializing git...")
        _init_git(target)

    # 8. Register vault
    if register:
        log.info("Registering vault...")
        _register_vault(target, vault_name)

    log.info("")
    log.info("Vault scaffolded successfully at %s", target)
    log.info("")
    log.info("Next steps:")
    log.info("  1. cd %s", target)
    log.info("  2. cp .env.example .env && $EDITOR .env")
    log.info("  3. cd _code && uv sync")
    log.info("  4. Open in Obsidian, install Local REST API plugin")
    log.info("  5. Start Claude Code and run /onboard")
    if starter_only:
        log.info("")
        log.info(
            "  Starter mode: %d of %d skills installed.",
            len(_STARTER_SKILLS),
            len(_STARTER_SKILLS) + len(_FULL_SKILLS),
        )
        log.info("  Run init_vault.py again with --full to add co-scientist skills.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a new EngramR vault.",
        epilog=(
            "Examples:\n"
            "  uv run python scripts/init_vault.py ~/NewVault\n"
            '  uv run python scripts/init_vault.py ~/NewVault --name "My Lab"\n'
            "  uv run python scripts/init_vault.py ~/NewVault --starter\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to create the new vault at",
    )
    parser.add_argument(
        "--name",
        default="My Research Vault",
        help="Display name for the vault (default: My Research Vault)",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Skip git init and initial commit",
    )
    parser.add_argument(
        "--no-register",
        action="store_true",
        help="Skip adding to vault registry",
    )
    parser.add_argument(
        "--starter",
        action="store_true",
        help=(
            f"Install only starter skills ({len(_STARTER_SKILLS)} of "
            f"{len(_STARTER_SKILLS) + len(_FULL_SKILLS)}). "
            "Easier onboarding for new users."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite target if it already exists",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Source vault to copy from (default: auto-detect from script location)",
    )
    args = parser.parse_args()

    source = args.source if args.source else _find_source_vault()

    scaffold(
        target=args.target,
        source=source,
        vault_name=args.name,
        init_git=not args.no_git,
        starter_only=args.starter,
        register=not args.no_register,
        force=args.force,
    )


if __name__ == "__main__":
    main()
