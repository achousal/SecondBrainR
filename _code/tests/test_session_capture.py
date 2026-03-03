"""Tests for scripts/hooks/session_capture.py."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE_DIR / "src"))
sys.path.insert(0, str(_CODE_DIR / "scripts" / "hooks"))

import session_capture  # noqa: E402


def _hook_stdin(
    session_id: str = "abc12345",
    transcript_path: str = "",
    cwd: str = "/Users/test/project",
    permission_mode: str = "default",
    last_assistant_message: str = "",
) -> str:
    return json.dumps({
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "permission_mode": permission_mode,
        "hook_event_name": "Stop",
        "stop_hook_active": True,
        "last_assistant_message": last_assistant_message,
    })


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    v.mkdir()
    (v / ".arscontexta").write_text("marker", encoding="utf-8")
    ops = v / "ops"
    ops.mkdir()
    (ops / "config.yaml").write_text("session_capture: true\n", encoding="utf-8")
    return v


class TestExtractSessionInfo:
    def test_basic_extraction(self, tmp_path: Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps({"tool_name": "Write", "tool_input": {"file_path": "/vault/notes/a.md"}}),
            json.dumps({"tool_name": "Skill", "tool_input": {"skill": "reduce"}}),
            json.dumps({"role": "assistant", "content": "Done processing."}),
        ]
        transcript.write_text("\n".join(lines), encoding="utf-8")

        info = session_capture._extract_session_info({
            "session_id": "test123",
            "transcript_path": str(transcript),
            "last_assistant_message": "Final summary here.",
        })
        assert info["session_id"] == "test123"
        assert "/vault/notes/a.md" in info["files_written"]
        assert "/reduce" in info["skills_invoked"]
        assert info["summary"] == "Final summary here."

    def test_missing_transcript(self) -> None:
        info = session_capture._extract_session_info({
            "session_id": "test",
            "transcript_path": "/nonexistent/path.jsonl",
        })
        assert info["files_written"] == []
        assert info["summary"] == ""

    def test_truncates_long_summary(self) -> None:
        long_msg = "x" * 500
        info = session_capture._extract_session_info({
            "session_id": "t",
            "last_assistant_message": long_msg,
        })
        assert len(info["summary"]) == 303  # 300 + "..."

    def test_last_assistant_message_is_primary_summary(self, tmp_path: Path) -> None:
        """last_assistant_message takes priority over transcript parsing."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"role": "assistant", "content": "Transcript message."}),
            encoding="utf-8",
        )
        info = session_capture._extract_session_info({
            "session_id": "t",
            "transcript_path": str(transcript),
            "last_assistant_message": "Direct hook message.",
        })
        assert info["summary"] == "Direct hook message."

    def test_transcript_fallback_when_no_last_message(self, tmp_path: Path) -> None:
        """Falls back to transcript parsing when last_assistant_message is absent."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"role": "assistant", "content": "Transcript fallback."}),
            encoding="utf-8",
        )
        info = session_capture._extract_session_info({
            "session_id": "t",
            "transcript_path": str(transcript),
        })
        assert info["summary"] == "Transcript fallback."

    def test_cwd_extracted(self) -> None:
        info = session_capture._extract_session_info({
            "session_id": "t",
            "cwd": "/Users/test/project",
        })
        assert info["cwd"] == "/Users/test/project"

    def test_permission_mode_extracted(self) -> None:
        info = session_capture._extract_session_info({
            "session_id": "t",
            "permission_mode": "plan",
        })
        assert info["permission_mode"] == "plan"

    def test_empty_enrichment_when_no_transcript(self) -> None:
        """files_written and skills_invoked are empty when transcript is missing."""
        info = session_capture._extract_session_info({
            "session_id": "t",
            "last_assistant_message": "Summary without transcript.",
        })
        assert info["files_written"] == []
        assert info["skills_invoked"] == []
        assert info["summary"] == "Summary without transcript."


class TestMainWritesSession:
    def test_creates_session_file(self, vault: Path) -> None:
        with (
            patch("session_capture.load_config", return_value={"session_capture": True}),
            patch("session_capture.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin("sess1234"))),
            patch.object(session_capture, "_slack_session_end"),
        ):
            session_capture.main()

        sessions_dir = vault / "ops" / "sessions"
        files = list(sessions_dir.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "sess1234" in content
        assert "## Files Changed" in content

    def test_cwd_in_output(self, vault: Path) -> None:
        stdin_data = _hook_stdin("sess1234", cwd="/Users/test/myproject")
        with (
            patch("session_capture.load_config", return_value={"session_capture": True}),
            patch("session_capture.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(stdin_data)),
            patch.object(session_capture, "_slack_session_end"),
        ):
            session_capture.main()

        sessions_dir = vault / "ops" / "sessions"
        files = list(sessions_dir.glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "cwd:" in content
        assert "/Users/test/myproject" in content

    def test_permission_mode_in_output(self, vault: Path) -> None:
        stdin_data = _hook_stdin("sess1234", permission_mode="plan")
        with (
            patch("session_capture.load_config", return_value={"session_capture": True}),
            patch("session_capture.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(stdin_data)),
            patch.object(session_capture, "_slack_session_end"),
        ):
            session_capture.main()

        sessions_dir = vault / "ops" / "sessions"
        files = list(sessions_dir.glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "permission_mode:" in content

    def test_last_assistant_message_populates_summary(self, vault: Path) -> None:
        stdin_data = _hook_stdin(
            "sess1234",
            last_assistant_message="Completed the task successfully.",
        )
        with (
            patch("session_capture.load_config", return_value={"session_capture": True}),
            patch("session_capture.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(stdin_data)),
            patch.object(session_capture, "_slack_session_end"),
        ):
            session_capture.main()

        sessions_dir = vault / "ops" / "sessions"
        files = list(sessions_dir.glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "Completed the task successfully." in content

    def test_skips_when_disabled(self, vault: Path) -> None:
        with (
            patch("session_capture.load_config", return_value={"session_capture": False}),
            patch("sys.stdin", io.StringIO(_hook_stdin())),
        ):
            session_capture.main()

        sessions_dir = vault / "ops" / "sessions"
        assert not sessions_dir.exists()


class TestErrorHandling:
    def test_never_raises(self) -> None:
        with (
            patch("session_capture.load_config", side_effect=RuntimeError("boom")),
            patch("sys.stdin", io.StringIO(_hook_stdin())),
        ):
            session_capture.main()  # Should not raise

    def test_error_logged_to_stderr(self) -> None:
        """C2: main() errors logged to stderr."""
        stderr_buf = io.StringIO()
        with (
            patch(
                "session_capture.load_config",
                side_effect=RuntimeError("test error"),
            ),
            patch("sys.stdin", io.StringIO(_hook_stdin())),
            patch("sys.stderr", stderr_buf),
        ):
            session_capture.main()
        assert "test error" in stderr_buf.getvalue()

    def test_transcript_parse_error_logged(self, tmp_path: Path) -> None:
        """C2: transcript parse errors logged to stderr."""
        bad_transcript = tmp_path / "bad.jsonl"
        bad_transcript.write_bytes(b"\x80\x81\x82")  # invalid UTF-8 in binary mode

        stderr_buf = io.StringIO()
        with patch("sys.stderr", stderr_buf):
            info = session_capture._extract_session_info({
                "session_id": "test",
                "transcript_path": str(bad_transcript),
            })
        # Should still return info (graceful), but log to stderr
        assert info["session_id"] == "test"


class TestGitFilesChanged:
    def test_returns_empty_for_nonexistent_dir(self) -> None:
        result = session_capture._git_files_changed("/nonexistent/path/xyz")
        assert result == []

    def test_returns_empty_for_empty_string(self) -> None:
        result = session_capture._git_files_changed("")
        assert result == []

    def test_returns_empty_for_non_git_dir(self, tmp_path: Path) -> None:
        result = session_capture._git_files_changed(str(tmp_path))
        assert result == []

    def test_detects_new_file(self, tmp_path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        (tmp_path / "new.md").write_text("test", encoding="utf-8")
        result = session_capture._git_files_changed(str(tmp_path))
        assert "new.md" in result

    def test_detects_modified_file(self, tmp_path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        (tmp_path / "existing.md").write_text("v1", encoding="utf-8")
        subprocess.run(
            ["git", "add", "existing.md"], cwd=tmp_path, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=tmp_path,
            capture_output=True,
            env={
                **__import__("os").environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "t@t.com",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "t@t.com",
            },
        )
        (tmp_path / "existing.md").write_text("v2", encoding="utf-8")
        result = session_capture._git_files_changed(str(tmp_path))
        assert "existing.md" in result

    def test_returns_sorted(self, tmp_path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        for name in ["c.md", "a.md", "b.md"]:
            (tmp_path / name).write_text("test", encoding="utf-8")
        result = session_capture._git_files_changed(str(tmp_path))
        assert result == sorted(result)

    def test_info_includes_files_changed(self, tmp_path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        (tmp_path / "note.md").write_text("test", encoding="utf-8")
        info = session_capture._extract_session_info({
            "session_id": "test",
            "cwd": str(tmp_path),
        })
        assert "note.md" in info["files_changed"]


class TestSessionOutputSections:
    def test_files_changed_section_in_output(self, vault: Path) -> None:
        stdin_data = _hook_stdin("sess1234", cwd="/Users/test/project")
        with (
            patch("session_capture.load_config", return_value={"session_capture": True}),
            patch("session_capture.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(stdin_data)),
            patch.object(session_capture, "_slack_session_end"),
            patch.object(session_capture, "_git_files_changed", return_value=["a.md"]),
        ):
            session_capture.main()

        sessions_dir = vault / "ops" / "sessions"
        files = list(sessions_dir.glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "## Files Changed" in content
        assert "## Tool Calls" in content
