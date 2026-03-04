"""Integration tests for the validate_queue.py hook script.

Tests the hook's main() function by mocking stdin (JSON hook input),
config loading, vault root resolution, and on-disk queue state.

Follows the same pattern as test_validate_write.py.
"""

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

from validate_queue import main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hook_input(file_path: str, content: str) -> str:
    """Build JSON string mimicking Claude Code PostToolUse hook stdin."""
    return json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": file_path,
                "content": content,
            },
        }
    )


def _run_hook(
    file_path: str,
    new_queue: list[dict],
    old_queue: list[dict] | None = None,
    config: dict | None = None,
    vault_root: Path | None = None,
    notes_on_disk: list[str] | None = None,
) -> tuple[str, str, bool]:
    """Run the hook main() and capture stdout, stderr, and whether it exited.

    Args:
        file_path: The file_path in the hook input.
        new_queue: The new queue content being written.
        old_queue: The old queue currently on disk. None = no file on disk.
        config: Config dict override.
        vault_root: Mock vault root (will create notes/ under it).
        notes_on_disk: List of note titles to create as .md files in notes/.

    Returns:
        (stdout, stderr, exited_early)
    """
    if config is None:
        config = {"enrichment_target_validation": True}
    if vault_root is None:
        vault_root = Path("/vault")

    content = json.dumps(new_queue)
    stdin_data = _hook_input(file_path, content)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    exited = False

    def fake_exit(code: int = 0) -> None:
        nonlocal exited
        exited = True
        raise SystemExit(code)

    # Build the mock queue file path
    queue_path = vault_root / "ops" / "queue" / "queue.json"

    # Mock Path.exists and Path.read_text for the queue file and notes
    _orig_exists = Path.exists
    _orig_read_text = Path.read_text

    def mock_exists(self: Path) -> bool:
        resolved = str(self)
        if resolved == str(queue_path):
            return old_queue is not None
        if notes_on_disk and resolved.startswith(str(vault_root / "notes")):
            # Check if this note file is in our mock set
            note_name = self.name
            return note_name in {f"{n}.md" for n in (notes_on_disk or [])}
        return _orig_exists(self)

    def mock_read_text(self: Path, encoding: str = "utf-8") -> str:
        if str(self) == str(queue_path) and old_queue is not None:
            return json.dumps(old_queue)
        return _orig_read_text(self, encoding=encoding)

    with (
        patch("validate_queue.load_config", return_value=config),
        patch("validate_queue.resolve_vault", return_value=vault_root),
        patch("sys.stdin", io.StringIO(stdin_data)),
        patch("sys.stdout", stdout_buf),
        patch("sys.stderr", stderr_buf),
        patch("sys.exit", side_effect=fake_exit),
        patch.object(Path, "exists", mock_exists),
        patch.object(Path, "read_text", mock_read_text),
    ):
        try:
            main()
        except SystemExit:
            pass

    return stdout_buf.getvalue(), stderr_buf.getvalue(), exited


def _parse_block_response(stdout: str) -> dict | None:
    """Parse a JSON block response from stdout, or None if empty."""
    stdout = stdout.strip()
    if not stdout:
        return None
    return json.loads(stdout)


# ---------------------------------------------------------------------------
# Tests: phantom target blocking
# ---------------------------------------------------------------------------


class TestPhantomTargetBlocking:
    """New enrichment entries with phantom targets are blocked."""

    def test_blocks_phantom_target(self):
        old = [{"id": "extract-001", "type": "extract"}]
        new = [
            {"id": "extract-001", "type": "extract"},
            {"id": "enrich-001", "type": "enrichment", "target": "nonexistent claim"},
        ]
        stdout, stderr, exited = _run_hook(
            "/vault/ops/queue/queue.json",
            new,
            old_queue=old,
            notes_on_disk=[],
        )
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "enrich-001" in resp["reason"]
        assert "nonexistent claim" in resp["reason"]
        assert exited

    def test_blocks_multiple_phantoms(self):
        old = []
        new = [
            {"id": "enrich-001", "type": "enrichment", "target": "phantom a"},
            {"id": "enrich-002", "type": "enrichment", "target": "phantom b"},
        ]
        stdout, stderr, exited = _run_hook(
            "/vault/ops/queue/queue.json",
            new,
            old_queue=old,
            notes_on_disk=[],
        )
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "enrich-001" in resp["reason"]
        assert "enrich-002" in resp["reason"]


# ---------------------------------------------------------------------------
# Tests: valid targets allowed
# ---------------------------------------------------------------------------


class TestValidTargetsAllowed:
    """Enrichment entries targeting existing notes pass through."""

    def test_allows_valid_target(self):
        old = []
        new = [
            {"id": "enrich-001", "type": "enrichment", "target": "real claim"},
        ]
        stdout, stderr, exited = _run_hook(
            "/vault/ops/queue/queue.json",
            new,
            old_queue=old,
            notes_on_disk=["real claim"],
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert not exited

    def test_allows_edit_to_existing_entry(self):
        """Editing an existing enrichment entry (same ID) always passes."""
        old = [
            {
                "id": "enrich-001",
                "type": "enrichment",
                "status": "pending",
                "target": "phantom that already existed",
            }
        ]
        new = [
            {
                "id": "enrich-001",
                "type": "enrichment",
                "status": "blocked",
                "target": "phantom that already existed",
                "note": "target not found",
            }
        ]
        stdout, stderr, exited = _run_hook(
            "/vault/ops/queue/queue.json",
            new,
            old_queue=old,
            notes_on_disk=[],
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert not exited


# ---------------------------------------------------------------------------
# Tests: early returns
# ---------------------------------------------------------------------------


class TestEarlyReturns:
    """Non-queue files and edge cases trigger early return."""

    def test_non_queue_file_ignored(self):
        stdout, stderr, exited = _run_hook(
            "/vault/notes/some note.md",
            [{"id": "enrich-001", "type": "enrichment", "target": "phantom"}],
            old_queue=[],
            notes_on_disk=[],
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert not exited

    def test_empty_stdin(self):
        """Empty stdin triggers early return."""
        config = {"enrichment_target_validation": True}
        vault_root = Path("/vault")
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with (
            patch("validate_queue.load_config", return_value=config),
            patch("validate_queue.resolve_vault", return_value=vault_root),
            patch("sys.stdin", io.StringIO("")),
            patch("sys.stdout", stdout_buf),
            patch("sys.stderr", stderr_buf),
        ):
            main()

        assert stdout_buf.getvalue().strip() == ""

    def test_non_json_stdin(self):
        """Non-JSON stdin triggers early return."""
        config = {"enrichment_target_validation": True}
        vault_root = Path("/vault")
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with (
            patch("validate_queue.load_config", return_value=config),
            patch("validate_queue.resolve_vault", return_value=vault_root),
            patch("sys.stdin", io.StringIO("not json at all")),
            patch("sys.stdout", stdout_buf),
            patch("sys.stderr", stderr_buf),
        ):
            main()

        assert stdout_buf.getvalue().strip() == ""

    def test_config_disabled(self):
        """When enrichment_target_validation is false, hook is a no-op."""
        old = []
        new = [
            {"id": "enrich-001", "type": "enrichment", "target": "phantom"},
        ]
        config = {"enrichment_target_validation": False}
        stdout, stderr, exited = _run_hook(
            "/vault/ops/queue/queue.json",
            new,
            old_queue=old,
            notes_on_disk=[],
            config=config,
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert not exited


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Malformed queue data, missing files, etc."""

    def test_malformed_old_queue_on_disk(self):
        """If old queue file is not valid JSON, treat as empty old queue."""
        config = {"enrichment_target_validation": True}
        vault_root = Path("/vault")
        queue_path = vault_root / "ops" / "queue" / "queue.json"

        new_queue = [
            {"id": "enrich-001", "type": "enrichment", "target": "phantom"},
        ]
        content = json.dumps(new_queue)
        stdin_data = _hook_input("/vault/ops/queue/queue.json", content)

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        exited = False

        def fake_exit(code: int = 0) -> None:
            nonlocal exited
            exited = True
            raise SystemExit(code)

        def mock_exists(self: Path) -> bool:
            if str(self) == str(queue_path):
                return True
            return False

        def mock_read_text(self: Path, encoding: str = "utf-8") -> str:
            if str(self) == str(queue_path):
                return "not valid json {{{{"
            raise FileNotFoundError

        with (
            patch("validate_queue.load_config", return_value=config),
            patch("validate_queue.resolve_vault", return_value=vault_root),
            patch("sys.stdin", io.StringIO(stdin_data)),
            patch("sys.stdout", stdout_buf),
            patch("sys.stderr", stderr_buf),
            patch("sys.exit", side_effect=fake_exit),
            patch.object(Path, "exists", mock_exists),
            patch.object(Path, "read_text", mock_read_text),
        ):
            try:
                main()
            except SystemExit:
                pass

        resp = _parse_block_response(stdout_buf.getvalue())
        # With malformed old queue -> old_queue=[] -> enrich-001 is "new"
        # -> target "phantom" doesn't exist -> should block
        assert resp is not None
        assert resp["decision"] == "block"

    def test_missing_queue_file_on_disk(self):
        """If no queue file exists on disk, old queue is empty."""
        old = None  # No file on disk
        new = [
            {"id": "enrich-001", "type": "enrichment", "target": "phantom"},
        ]
        stdout, stderr, exited = _run_hook(
            "/vault/ops/queue/queue.json",
            new,
            old_queue=old,
            notes_on_disk=[],
        )
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"

    def test_new_queue_not_a_list(self):
        """If new queue content is not a JSON array, early return."""
        config = {"enrichment_target_validation": True}
        vault_root = Path("/vault")

        content = json.dumps({"not": "a list"})
        stdin_data = _hook_input("/vault/ops/queue/queue.json", content)

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with (
            patch("validate_queue.load_config", return_value=config),
            patch("validate_queue.resolve_vault", return_value=vault_root),
            patch("sys.stdin", io.StringIO(stdin_data)),
            patch("sys.stdout", stdout_buf),
            patch("sys.stderr", stderr_buf),
        ):
            main()

        assert stdout_buf.getvalue().strip() == ""

    def test_only_non_enrichment_new_entries(self):
        """New entries that are not enrichment type are ignored."""
        old = []
        new = [
            {"id": "extract-001", "type": "extract"},
            {"id": "reflect-001", "type": "reflect"},
        ]
        stdout, stderr, exited = _run_hook(
            "/vault/ops/queue/queue.json",
            new,
            old_queue=old,
            notes_on_disk=[],
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert not exited
