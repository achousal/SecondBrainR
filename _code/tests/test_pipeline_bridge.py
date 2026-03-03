"""Tests for scripts/hooks/pipeline_bridge.py."""

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

import pipeline_bridge  # noqa: E402


def _hook_stdin(file_path: str) -> str:
    return json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    v.mkdir()
    (v / ".arscontexta").write_text("marker", encoding="utf-8")
    (v / "ops" / "queue").mkdir(parents=True)
    (v / "_research" / "literature").mkdir(parents=True)
    (v / "_research" / "hypotheses").mkdir(parents=True)
    return v


class TestClassifyFile:
    def test_literature_note(self) -> None:
        assert pipeline_bridge._classify_file("_research/literature/2026-smith.md") == "literature note"

    def test_hypothesis(self) -> None:
        assert pipeline_bridge._classify_file("_research/hypotheses/H001.md") == "hypothesis"

    def test_index_file_excluded(self) -> None:
        assert pipeline_bridge._classify_file("_research/literature/_index.md") is None

    def test_template_excluded(self) -> None:
        assert pipeline_bridge._classify_file("_code/templates/literature.md") is None

    def test_unrelated_file(self) -> None:
        assert pipeline_bridge._classify_file("notes/some-claim.md") is None


class TestQueueDedup:
    def test_not_queued(self, vault: Path) -> None:
        queue_path = vault / "ops" / "queue" / "queue.json"
        assert not pipeline_bridge._is_already_queued(queue_path, "_research/literature/x.md")

    def test_already_queued(self, vault: Path) -> None:
        queue_path = vault / "ops" / "queue" / "queue.json"
        queue_path.write_text(
            json.dumps({
                "tasks": [
                    {"source": "_research/literature/x.md", "status": "pending"}
                ]
            }),
            encoding="utf-8",
        )
        assert pipeline_bridge._is_already_queued(queue_path, "_research/literature/x.md")

    def test_done_task_not_queued(self, vault: Path) -> None:
        queue_path = vault / "ops" / "queue" / "queue.json"
        queue_path.write_text(
            json.dumps({
                "tasks": [
                    {"source": "_research/literature/x.md", "status": "done"}
                ]
            }),
            encoding="utf-8",
        )
        assert not pipeline_bridge._is_already_queued(queue_path, "_research/literature/x.md")


class TestErrorLogging:
    """C3: malformed inputs log warnings to stderr."""

    def test_malformed_queue_logs_warning(self, vault: Path) -> None:
        queue_path = vault / "ops" / "queue" / "queue.json"
        queue_path.write_text("{bad json", encoding="utf-8")
        stderr_buf = io.StringIO()

        with patch("sys.stderr", stderr_buf):
            result = pipeline_bridge._is_already_queued(
                queue_path, "_research/literature/x.md"
            )
        assert not result
        assert "malformed queue.json" in stderr_buf.getvalue()

    def test_malformed_stdin_logs_warning(self) -> None:
        stderr_buf = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO("{bad json")),
            patch("sys.stderr", stderr_buf),
        ):
            pipeline_bridge.main()
        assert "stdin parse error" in stderr_buf.getvalue()


class TestAuditTrail:
    """D1: suggestions logged to ops/pipeline-suggestions.log."""

    def test_suggestion_logged_to_file(self, vault: Path) -> None:
        file_path = str(vault / "_research" / "literature" / "2026-test.md")
        stdout_buf = io.StringIO()

        with (
            patch("pipeline_bridge.resolve_vault", return_value=vault),
            patch(
                "pipeline_bridge.load_config",
                return_value={"pipeline_bridge_log": True},
            ),
            patch("sys.stdin", io.StringIO(_hook_stdin(file_path))),
            patch("sys.stdout", stdout_buf),
        ):
            pipeline_bridge.main()

        log_path = vault / "ops" / "pipeline-suggestions.log"
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "literature note" in content
        assert "/reduce" in content

    def test_log_disabled_by_config(self, vault: Path) -> None:
        file_path = str(vault / "_research" / "literature" / "2026-test.md")
        stdout_buf = io.StringIO()

        with (
            patch("pipeline_bridge.resolve_vault", return_value=vault),
            patch(
                "pipeline_bridge.load_config",
                return_value={"pipeline_bridge_log": False},
            ),
            patch("sys.stdin", io.StringIO(_hook_stdin(file_path))),
            patch("sys.stdout", stdout_buf),
        ):
            pipeline_bridge.main()

        log_path = vault / "ops" / "pipeline-suggestions.log"
        assert not log_path.exists()


class TestMainOutput:
    def test_suggests_reduce_for_literature(self, vault: Path) -> None:
        file_path = str(vault / "_research" / "literature" / "2026-smith.md")
        stdout_buf = io.StringIO()

        with (
            patch("pipeline_bridge.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(file_path))),
            patch("sys.stdout", stdout_buf),
        ):
            pipeline_bridge.main()

        output = stdout_buf.getvalue()
        assert "[Pipeline Bridge]" in output
        assert "literature note" in output
        assert "/reduce" in output

    def test_silent_for_unrelated_file(self, vault: Path) -> None:
        file_path = str(vault / "notes" / "claim.md")
        stdout_buf = io.StringIO()

        with (
            patch("pipeline_bridge.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(file_path))),
            patch("sys.stdout", stdout_buf),
        ):
            pipeline_bridge.main()

        assert stdout_buf.getvalue() == ""

    def test_suppressed_when_queued(self, vault: Path) -> None:
        queue_path = vault / "ops" / "queue" / "queue.json"
        queue_path.write_text(
            json.dumps({
                "tasks": [
                    {"source": "_research/literature/2026-smith.md", "status": "pending"}
                ]
            }),
            encoding="utf-8",
        )
        file_path = str(vault / "_research" / "literature" / "2026-smith.md")
        stdout_buf = io.StringIO()

        with (
            patch("pipeline_bridge.resolve_vault", return_value=vault),
            patch("sys.stdin", io.StringIO(_hook_stdin(file_path))),
            patch("sys.stdout", stdout_buf),
        ):
            pipeline_bridge.main()

        assert stdout_buf.getvalue() == ""
