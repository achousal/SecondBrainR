"""Integration tests for the validate_write.py hook script.

Tests the hook's main() function by mocking stdin (JSON hook input),
config loading, and vault root resolution.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE_DIR / "src"))
sys.path.insert(0, str(_CODE_DIR / "scripts" / "hooks"))

from validate_write import (  # noqa: E402
    _check_truncated_wiki_links,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _note(fm_lines: list[str], body: str = "## Body\nContent\n") -> str:
    fm = "\n".join(fm_lines)
    return f"---\n{fm}\n---\n\n{body}"


def _hook_input(
    file_path: str,
    content: str,
    tool_name: str = "Write",
) -> str:
    """Build a JSON string mimicking the Claude Code hook stdin."""
    return json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {
                "file_path": file_path,
                "content": content,
            },
        }
    )


def _run_hook(
    file_path: str,
    content: str,
    tool_name: str = "Write",
    config: dict | None = None,
    vault_root: Path | None = None,
) -> tuple[str, str, bool]:
    """Run the hook main() and capture stdout, stderr, and whether it exited.

    Returns (stdout, stderr, exited_early).
    """
    if config is None:
        config = {"schema_validation": True, "pipeline_compliance": True}
    if vault_root is None:
        vault_root = Path("/vault")

    stdin_data = _hook_input(file_path, content, tool_name)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    exited = False

    def fake_exit(code: int = 0) -> None:
        nonlocal exited
        exited = True
        raise SystemExit(code)

    with (
        patch("validate_write.load_config", return_value=config),
        patch("validate_write.resolve_vault", return_value=vault_root),
        patch("sys.stdin", io.StringIO(stdin_data)),
        patch("sys.stdout", stdout_buf),
        patch("sys.stderr", stderr_buf),
        patch("sys.exit", side_effect=fake_exit),
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
# Tests: provenance enforcement on notes/ files
# ---------------------------------------------------------------------------


class TestProvenanceEnforcement:
    """Pipeline provenance checks on notes/ files."""

    def test_valid_notes_file_passes(self):
        content = _note(
            [
                'description: "Factor-X drives chronic response"',
                'source: "[[2026-bach]]"',
                "type: claim",
            ]
        )
        stdout, stderr, exited = _run_hook(
            "/vault/notes/factor-x drives chronic response.md", content
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert not exited

    def test_notes_file_missing_description_blocks(self):
        content = _note(
            [
                'source: "[[some-source]]"',
                "type: claim",
            ]
        )
        stdout, stderr, exited = _run_hook("/vault/notes/some claim.md", content)
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "description" in resp["reason"].lower()
        assert exited

    def test_notes_file_empty_description_blocks(self):
        content = _note(
            [
                'description: ""',
                'source: "[[some-source]]"',
                "type: claim",
            ]
        )
        stdout, stderr, exited = _run_hook("/vault/notes/some claim.md", content)
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "description" in resp["reason"].lower()

    def test_claim_missing_source_write_warns(self):
        content = _note(
            [
                'description: "Some insight about mechanisms"',
                "type: claim",
            ]
        )
        stdout, stderr, exited = _run_hook(
            "/vault/notes/some insight.md", content, tool_name="Write"
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert "source" in stderr.lower()

    def test_claim_missing_source_edit_no_warning(self):
        content = _note(
            [
                'description: "Some insight about mechanisms"',
                "type: claim",
            ]
        )
        stdout, stderr, exited = _run_hook(
            "/vault/notes/some insight.md", content, tool_name="Edit"
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert stderr == ""

    def test_moc_missing_source_no_warning(self):
        content = _note(
            [
                'description: "Navigation hub for test analysis"',
                "type: moc",
            ]
        )
        stdout, stderr, exited = _run_hook(
            "/vault/notes/test-condition-markers.md",
            content,
            tool_name="Write",
        )
        resp = _parse_block_response(stdout)
        assert resp is None
        assert stderr == ""

    def test_non_notes_file_no_provenance_check(self):
        """Files outside notes/ skip provenance even without description."""
        content = _note(
            [
                "type: hypothesis",
                "title: Test hypothesis",
                "id: hyp-001",
                "status: proposed",
                "elo: 1200",
                "created: 2026-01-01",
                "updated: 2026-01-01",
            ]
        )
        stdout, stderr, exited = _run_hook(
            "/vault/_research/hypotheses/test hypothesis.md", content
        )
        resp = _parse_block_response(stdout)
        assert resp is None

    def test_pipeline_compliance_false_skips_check(self):
        """When pipeline_compliance is false, no provenance check runs."""
        content = _note(
            [
                "type: claim",
                'description: "Test claim for provenance skip"',
            ]
        )
        config = {"schema_validation": True, "pipeline_compliance": False}
        stdout, stderr, exited = _run_hook(
            "/vault/notes/some claim.md", content, config=config
        )
        resp = _parse_block_response(stdout)
        assert resp is None, f"Expected no block, got: {resp}"

    def test_no_frontmatter_in_notes_blocks(self):
        content = "# Just a heading\n\nSome text without frontmatter.\n"
        stdout, stderr, exited = _run_hook("/vault/notes/some note.md", content)
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "frontmatter" in resp["reason"].lower()


# ---------------------------------------------------------------------------
# Tests: truncated wiki link detection (absorbed from validate-note.sh)
# ---------------------------------------------------------------------------


class TestTruncatedWikiLinks:
    """Truncated [[...]] link detection."""

    def test_detects_truncated_link(self):
        err = _check_truncated_wiki_links("See [[some long title...]] for details")
        assert err is not None
        assert "Truncated" in err
        assert "[[some long title...]]" in err

    def test_no_truncated_link(self):
        err = _check_truncated_wiki_links("See [[full title]] for details")
        assert err is None

    def test_ellipsis_outside_link_ok(self):
        err = _check_truncated_wiki_links("Some text... and [[valid link]]")
        assert err is None

    def test_blocks_notes_file_with_truncated_link(self):
        content = _note(
            [
                'description: "Some claim"',
                'source: "[[source]]"',
                "type: claim",
            ],
            body="## Body\nSee [[some hypothesis about mechanisms...]]\n",
        )
        stdout, stderr, exited = _run_hook(
            "/vault/notes/some claim.md", content
        )
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "Truncated" in resp["reason"]
        assert exited

    def test_blocks_research_file_with_truncated_link(self):
        content = _note(
            [
                "type: hypothesis",
                "title: Test",
                "id: H-001",
                "status: proposed",
                "elo: 1200",
                "created: 2026-01-01",
                "updated: 2026-01-01",
            ],
            body="## Body\nSee [[some claim about...]]\n",
        )
        stdout, stderr, exited = _run_hook(
            "/vault/_research/hypotheses/test.md", content
        )
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "Truncated" in resp["reason"]

    def test_no_truncated_link_check_for_self_files(self):
        """Files under self/ should not trigger truncated link check.

        Uses self/goals.md (not protected by identity_protection) to
        verify that truncated-link checking is scoped to notes/ and
        _research/ only.
        """
        content = _note(
            [
                'description: "Active research threads"',
                "type: moc",
            ],
            body="## Body\nSee [[some topic...]] for details\n",
        )
        stdout, stderr, exited = _run_hook(
            "/vault/self/goals.md", content
        )
        resp = _parse_block_response(stdout)
        # Should not block on truncated link (self/ is not notes/ or _research/)
        assert resp is None


# ---------------------------------------------------------------------------
# Tests: protected file write blocking
# ---------------------------------------------------------------------------


class TestProtectedFileWrites:
    """Identity protection blocks writes to protected files."""

    def test_blocks_write_to_protected_file(self):
        """Write to self/identity.md is blocked by default."""
        content = _note(
            [
                'description: "Agent identity"',
                "type: moc",
            ],
        )
        with patch.dict("os.environ", {}, clear=False):
            # Ensure unlock env var is not set
            os.environ.pop("ENGRAMR_IDENTITY_UNLOCK", None)
            stdout, stderr, exited = _run_hook(
                "/vault/self/identity.md", content
            )
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "Protected file" in resp["reason"]
        assert "self/identity.md" in resp["reason"]
        assert exited

    def test_allows_write_with_env_unlock(self):
        """Write allowed when ENGRAMR_IDENTITY_UNLOCK=1."""
        content = _note(
            [
                'description: "Agent identity"',
                "type: moc",
            ],
        )
        with patch.dict("os.environ", {"ENGRAMR_IDENTITY_UNLOCK": "1"}):
            stdout, stderr, exited = _run_hook(
                "/vault/self/identity.md", content
            )
        resp = _parse_block_response(stdout)
        # Should not be blocked for protected file reason
        if resp is not None:
            assert "Protected file" not in resp.get("reason", "")

    def test_allows_write_with_config_disabled(self):
        """Write allowed when identity_protection is false in config."""
        content = _note(
            [
                'description: "Agent identity"',
                "type: moc",
            ],
        )
        config = {
            "schema_validation": True,
            "pipeline_compliance": True,
            "identity_protection": False,
        }
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("ENGRAMR_IDENTITY_UNLOCK", None)
            stdout, stderr, exited = _run_hook(
                "/vault/self/identity.md", content, config=config
            )
        resp = _parse_block_response(stdout)
        # Should not be blocked for protected file reason
        if resp is not None:
            assert "Protected file" not in resp.get("reason", "")

    def test_non_protected_file_unaffected(self):
        """Normal notes/ writes still work."""
        content = _note(
            [
                'description: "A normal claim about mechanisms"',
                'source: "[[some-source]]"',
                "type: claim",
            ],
        )
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("ENGRAMR_IDENTITY_UNLOCK", None)
            stdout, stderr, exited = _run_hook(
                "/vault/notes/some normal claim.md", content
            )
        resp = _parse_block_response(stdout)
        # Should pass through (no protected file block)
        if resp is not None:
            assert "Protected file" not in resp.get("reason", "")


# ---------------------------------------------------------------------------
# Tests: methodology source file warning
# ---------------------------------------------------------------------------


class TestMethodologySourceWarning:
    """Writes to methodology source files emit a warning but do not block."""

    def test_warns_on_methodology_source_write(self):
        content = _note(
            [
                'description: "Methodology directive"',
                "type: methodology",
            ],
        )
        stdout, stderr, exited = _run_hook(
            "/vault/ops/methodology/derivation-rationale.md", content
        )
        resp = _parse_block_response(stdout)
        # Should NOT block
        assert resp is None or resp.get("decision") != "block"
        assert not exited
        # Warning should appear on stderr
        assert "Methodology source file" in stderr
        assert "compiled outputs" in stderr

    def test_compiled_md_is_blocked_not_warned(self):
        """_compiled.md is in PROTECTED_PATHS and should be blocked, not warned."""
        content = _note(
            [
                'description: "Compiled directives"',
                "type: methodology",
            ],
        )
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("ENGRAMR_IDENTITY_UNLOCK", None)
            stdout, stderr, exited = _run_hook(
                "/vault/ops/methodology/_compiled.md", content
            )
        resp = _parse_block_response(stdout)
        assert resp is not None
        assert resp["decision"] == "block"
        assert "Protected file" in resp["reason"]
