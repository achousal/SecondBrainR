"""Tests for scripts/hooks/auto_commit.py."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

_CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE_DIR / "src"))
sys.path.insert(0, str(_CODE_DIR / "scripts" / "hooks"))

import auto_commit  # noqa: E402


def _hook_stdin(file_path: str) -> str:
    return json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal vault with git."""
    v = tmp_path / "vault"
    v.mkdir()
    (v / ".arscontexta").write_text("marker", encoding="utf-8")
    (v / "ops").mkdir()
    (v / "ops" / "config.yaml").write_text("git_auto_commit: true\n", encoding="utf-8")
    (v / "notes").mkdir()
    (v / "self").mkdir()
    return v


class TestAutoCommitDisabled:
    def test_skips_when_disabled(self, vault: Path) -> None:
        (vault / "ops" / "config.yaml").write_text(
            "git_auto_commit: false\n", encoding="utf-8"
        )
        with (
            patch("auto_commit.load_config", return_value={"git_auto_commit": False}),
            patch("sys.stdin", io.StringIO(_hook_stdin(str(vault / "self" / "x.md")))),
            patch("auto_commit.subprocess") as mock_sub,
        ):
            auto_commit.main()
            mock_sub.run.assert_not_called()


class TestAutoCommitTrackedFile:
    def test_commits_file_in_tracked_dir(self, vault: Path) -> None:
        file_path = vault / "self" / "goals.md"
        file_path.write_text("goals", encoding="utf-8")

        mock_run = MagicMock(
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
        )

        with (
            patch("auto_commit.load_config", return_value={"git_auto_commit": True}),
            patch("auto_commit.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(str(file_path)))),
            patch("auto_commit._is_git_repo", return_value=True),
            patch("auto_commit.subprocess.run", mock_run),
        ):
            auto_commit.main()

        # Should have git add + git commit for the specific file
        add_calls = [
            c for c in mock_run.call_args_list if "add" in str(c)
        ]
        commit_calls = [
            c for c in mock_run.call_args_list if "commit" in str(c)
        ]
        assert len(add_calls) >= 1
        assert len(commit_calls) >= 1

    def test_skips_file_outside_vault(self, vault: Path) -> None:
        outside = Path("/tmp/outside.md")
        with (
            patch("auto_commit.load_config", return_value={"git_auto_commit": True}),
            patch("auto_commit.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(str(outside)))),
            patch("auto_commit._is_git_repo", return_value=True),
            patch("auto_commit.subprocess.run") as mock_run,
        ):
            auto_commit.main()
        # Should not have called git add/commit
        assert mock_run.call_count == 0


class TestBroadSweep:
    def test_sweep_stages_vault_dirs(self, vault: Path) -> None:
        """Sweep pass stages all vault content directories."""
        file_path = vault / "self" / "goals.md"
        file_path.write_text("goals", encoding="utf-8")

        calls_log = []

        def fake_run(cmd, **kwargs):
            calls_log.append(cmd)
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0 if "add" in cmd else 1,  # diff --cached returns 1 = has changes
                stdout="",
            )

        with (
            patch("auto_commit.load_config", return_value={"git_auto_commit": True}),
            patch("auto_commit.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(str(file_path)))),
            patch("auto_commit._is_git_repo", return_value=True),
            patch("auto_commit.subprocess.run", side_effect=fake_run),
        ):
            auto_commit.main()

        # Should contain sweep commits
        add_commands = [c for c in calls_log if c[0] == "git" and c[1] == "add"]
        # At least the specific file add + sweep adds for existing dirs
        assert len(add_commands) >= 2


class TestNoStdinGraceful:
    def test_empty_stdin_exits_clean(self, vault: Path) -> None:
        with (
            patch("auto_commit.load_config", return_value={"git_auto_commit": True}),
            patch("auto_commit.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO("")),
        ):
            auto_commit.main()  # Should not raise


class TestGitFailureLogging:
    """C1: git command failures logged to stderr."""

    def test_git_add_failure_logged(self, vault: Path) -> None:
        file_path = vault / "self" / "goals.md"
        file_path.write_text("goals", encoding="utf-8")
        stderr_buf = io.StringIO()

        def fake_run(cmd, **kwargs):
            if cmd[1] == "add" and str(file_path) in str(cmd):
                return subprocess.CompletedProcess(
                    args=cmd, returncode=128, stdout="", stderr="fatal: bad"
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with (
            patch("auto_commit.load_config", return_value={"git_auto_commit": True}),
            patch("auto_commit.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(str(file_path)))),
            patch("auto_commit._is_git_repo", return_value=True),
            patch("auto_commit.subprocess.run", side_effect=fake_run),
            patch("sys.stderr", stderr_buf),
        ):
            auto_commit.main()
        assert "git add failed" in stderr_buf.getvalue()

    def test_git_commit_failure_logged(self, vault: Path) -> None:
        file_path = vault / "self" / "goals.md"
        file_path.write_text("goals", encoding="utf-8")
        stderr_buf = io.StringIO()

        def fake_run(cmd, **kwargs):
            if cmd[1] == "commit":
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr="error: commit failed"
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with (
            patch("auto_commit.load_config", return_value={"git_auto_commit": True}),
            patch("auto_commit.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(str(file_path)))),
            patch("auto_commit._is_git_repo", return_value=True),
            patch("auto_commit.subprocess.run", side_effect=fake_run),
            patch("sys.stderr", stderr_buf),
        ):
            auto_commit.main()
        assert "git commit failed" in stderr_buf.getvalue()


class TestErrorHandling:
    def test_exception_logged_not_raised(self, vault: Path) -> None:
        stderr_buf = io.StringIO()
        with (
            patch("auto_commit.load_config", side_effect=RuntimeError("test")),
            patch("sys.stdin", io.StringIO(_hook_stdin("/vault/self/x.md"))),
            patch("sys.stderr", stderr_buf),
        ):
            auto_commit.main()  # Should not raise
        assert "test" in stderr_buf.getvalue()
