"""PostToolUse hook (async): auto-commit vault note changes.

Reads tool input from stdin (JSON). If the written file is under a
git-tracked vault directory, stages and commits it with a descriptive
message. Then performs a broad sweep to catch any remaining unstaged
vault files.

Consolidated from auto_commit.py + auto-commit.sh.

Usage (Claude Code hook):
    uv run python scripts/hooks/auto_commit.py

Stdin JSON shape:
    {"tool_name": "Write", "tool_input": {"file_path": "..."}}

Exit behavior:
    - Always exits 0. Failures are logged to stderr, never block.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent.parent

# Ensure src/ is importable for engram_r package
sys.path.insert(0, str(_CODE_DIR / "src"))

from engram_r.hook_utils import load_config, resolve_vault  # noqa: E402

# Vault directories that contain notes worth auto-committing
_TRACKED_DIRS = {
    "hypotheses",
    "literature",
    "experiments",
    "eda-reports",
    "projects",
    "_research",
    "self",
    "ops",
    "_code",
}

# Directories to stage in the broad sweep (absorbed from auto-commit.sh)
_SWEEP_DIRS = [
    "notes",
    "inbox",
    "archive",
    "self",
    "ops",
    "_research",
    "_code/templates",
    "_code/styles",
    "docs",
    "projects",
]


def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(path),
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _git_has_changes(vault: Path) -> bool:
    """Check if there are staged, unstaged, or untracked changes."""
    # Check staged/unstaged
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(vault),
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def main() -> None:
    try:
        config = load_config()

        if not config.get("git_auto_commit", True):
            return

        vault = resolve_vault(config)

        # Read hook input from stdin
        raw = sys.stdin.read()
        if not raw.strip():
            return
        hook_input = json.loads(raw)

        tool_input = hook_input.get("tool_input", {})
        file_path_str = tool_input.get("file_path", "")

        if not file_path_str:
            return

        file_path = Path(file_path_str).resolve()
        vault_resolved = vault.resolve()

        if not str(file_path).startswith(str(vault_resolved)):
            return

        # Check if file is under a tracked directory
        try:
            rel = file_path.relative_to(vault_resolved)
        except ValueError:
            return

        top_dir = rel.parts[0] if rel.parts else ""
        if top_dir not in _TRACKED_DIRS:
            # Even if the specific file isn't tracked, still do the sweep
            pass
        else:
            # Verify vault root has git
            if not _is_git_repo(vault_resolved):
                return

            # Stage and commit the specific file
            add_result = subprocess.run(
                ["git", "add", str(file_path)],
                cwd=str(vault_resolved),
                capture_output=True,
                text=True,
                check=False,
            )
            if add_result.returncode != 0:
                print(
                    f"auto_commit: git add failed ({add_result.returncode}): "
                    f"{(add_result.stderr or '').strip()}",
                    file=sys.stderr,
                )

            commit_msg = f"auto: update {rel}"
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg, "--no-verify"],
                cwd=str(vault_resolved),
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = commit_result.stdout or ""
            if commit_result.returncode != 0 and "nothing to commit" not in stdout:
                print(
                    f"auto_commit: git commit failed ({commit_result.returncode}): "
                    f"{(commit_result.stderr or '').strip()}",
                    file=sys.stderr,
                )

        # Broad sweep: stage all vault content dirs (absorbed from auto-commit.sh)
        if not _is_git_repo(vault_resolved):
            return

        for d in _SWEEP_DIRS:
            dir_path = vault_resolved / d
            if dir_path.exists():
                subprocess.run(
                    ["git", "add", str(dir_path)],
                    cwd=str(vault_resolved),
                    capture_output=True,
                    check=False,
                )

        # Commit remaining staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(vault_resolved),
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", "auto: vault update", "--no-verify"],
                cwd=str(vault_resolved),
                capture_output=True,
                check=False,
            )

    except Exception as exc:
        print(f"auto_commit: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
