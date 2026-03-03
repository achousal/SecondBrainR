"""PostToolUse hook (sync): validate note schema on Write/Edit.

Reads tool input from stdin (JSON). If the written file is a vault note
with YAML frontmatter containing a known ``type:``, validates against
the schema. Blocks the write on failure.

Consolidated from validate_write.py + validate-note.sh.

Usage (Claude Code hook):
    uv run python scripts/hooks/validate_write.py

Stdin JSON shape:
    {"tool_name": "Write", "tool_input": {"file_path": "...", "content": "..."}}

Exit behavior:
    - Print JSON with ``"decision": "block"`` on validation failure.
    - Exit 0 silently on success or non-note files.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import yaml  # noqa: F401 -- used by schema_validator transitively

# Add src to path so we can import engram_r
_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_CODE_DIR / "src"))

from engram_r.hook_utils import load_config, resolve_vault  # noqa: E402
from engram_r.integrity import MONITORED_DIRS, PROTECTED_PATHS  # noqa: E402
from engram_r.schema_validator import (  # noqa: E402
    check_notes_provenance,
    detect_unicode_issues,
    detect_yaml_safety_issues,
    validate_filename,
    validate_note,
)

# Directories where notes are flat (no subdirectories allowed).
_FLAT_DIRS = {"notes", "hypotheses", "literature", "experiments", "landscape"}

# Regex for truncated wiki links: [[some title...]]
_TRUNCATED_LINK_RE = re.compile(r"\[\[[^\]]*\.\.\.\]\]")


def _check_flat_dir_violation(rel_path: str) -> str | None:
    """Return an error message if rel_path nests inside a flat directory."""
    parts = rel_path.replace("\\", "/").split("/")

    if len(parts) >= 3 and parts[0] in _FLAT_DIRS:
        return (
            f"Filename contains '/' which creates subdirectories: {rel_path}. "
            f"Replace '/' with '-' in the note title "
            f"(e.g., 'APP/PS1' -> 'APP-PS1')."
        )

    if len(parts) >= 4 and parts[0] == "_research" and parts[1] in _FLAT_DIRS:
        return (
            f"Filename contains '/' which creates subdirectories: {rel_path}. "
            f"Replace '/' with '-' in the note title "
            f"(e.g., 'APP/PS1' -> 'APP-PS1')."
        )

    return None


def _check_truncated_wiki_links(content: str) -> str | None:
    """Detect truncated wiki links like ``[[some title...]]``.

    Absorbed from validate-note.sh. Returns an error message if found.
    """
    match = _TRUNCATED_LINK_RE.search(content)
    if match:
        return (
            f"Truncated wiki link found: {match.group()}. "
            f"Write the full title or use backtick code spans for shorthand references."
        )
    return None


def main() -> None:
    """Validate a written file against note schemas."""
    config = load_config()

    if not config.get("schema_validation", True):
        return

    vault = resolve_vault(config)

    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return

    tool_input = hook_input.get("tool_input", {})
    file_path_str = tool_input.get("file_path", "")

    if not file_path_str:
        return

    file_path = Path(file_path_str)

    # Only validate .md files under vault root
    if file_path.suffix != ".md":
        return

    try:
        vault_resolved = vault.resolve()
        file_resolved = file_path.resolve()
        if not str(file_resolved).startswith(str(vault_resolved)):
            return
    except Exception:
        return

    # Skip files in _code/ (code, templates, and styles -- not notes)
    try:
        rel = file_resolved.relative_to(vault_resolved)
        rel_str = str(rel)
        if rel_str.startswith("_code"):
            return
    except ValueError:
        return

    # Block writes to protected identity/config files
    if (
        config.get("identity_protection", True)
        and rel_str in PROTECTED_PATHS
        and not os.environ.get("ENGRAMR_IDENTITY_UNLOCK")
    ):
        response = {
            "decision": "block",
            "reason": (
                f"Protected file: {rel_str}. "
                f"Set ENGRAMR_IDENTITY_UNLOCK=1 to allow edits to "
                f"identity/config files, then run 'seal' to update "
                f"the manifest."
            ),
        }
        print(json.dumps(response))
        sys.exit(0)

    # Warn on methodology source file writes (monitored, not blocked)
    for monitored_dir in MONITORED_DIRS:
        if rel_str.startswith(monitored_dir + "/") and rel_str not in PROTECTED_PATHS:
            response = {
                "decision": "warn",
                "reason": (
                    f"Methodology source file: {rel_str}. "
                    f"Changes will persist into future compiled outputs."
                ),
            }
            print(json.dumps(response), file=sys.stderr)
            break  # Only warn once

    # Check for / in note titles (creates accidental subdirectories)
    flat_error = _check_flat_dir_violation(rel_str)
    if flat_error:
        response = {
            "decision": "block",
            "reason": flat_error,
        }
        print(json.dumps(response))
        sys.exit(0)

    # Check for other unsafe characters (: * ? " < > |) in the filename
    filename_errors = validate_filename(rel_str)
    if filename_errors:
        response = {
            "decision": "block",
            "reason": "; ".join(filename_errors),
        }
        print(json.dumps(response))
        sys.exit(0)

    # Read the content -- prefer tool_input content if available (Write),
    # otherwise read from disk (Edit)
    content = tool_input.get("content", "")
    if not content and file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return

    if not content:
        return

    # YAML safety: detect unquoted colons/hashes that silently misparse
    yaml_issues = detect_yaml_safety_issues(content)
    if yaml_issues:
        response = {
            "decision": "block",
            "reason": ("YAML safety issue in frontmatter: " + "; ".join(yaml_issues)),
        }
        print(json.dumps(response))
        sys.exit(0)

    # Unicode: detect non-NFC characters in frontmatter
    unicode_issues = detect_unicode_issues(content)
    if unicode_issues:
        response = {
            "decision": "block",
            "reason": ("Unicode normalization issue: " + "; ".join(unicode_issues)),
        }
        print(json.dumps(response))
        sys.exit(0)

    # Truncated wiki links (absorbed from validate-note.sh)
    # Only check files under notes/ and _research/
    if rel_str.startswith("notes") or rel_str.startswith("_research"):
        trunc_error = _check_truncated_wiki_links(content)
        if trunc_error:
            response = {
                "decision": "block",
                "reason": trunc_error,
            }
            print(json.dumps(response))
            sys.exit(0)

    result = validate_note(content)

    if not result.valid:
        response = {
            "decision": "block",
            "reason": "; ".join(result.errors),
        }
        print(json.dumps(response))
        sys.exit(0)

    # Pipeline provenance check for notes/ files
    if config.get("pipeline_compliance", True) and rel_str.startswith("notes"):
        prov = check_notes_provenance(content)

        if not prov.valid:
            response = {
                "decision": "block",
                "reason": "; ".join(prov.errors),
            }
            print(json.dumps(response))
            sys.exit(0)

        # Source warnings only for new files (Write tool), not edits.
        # Design choice: Write warns on missing source field because new notes
        # should have provenance. Edit suppresses because most edits add
        # content to existing notes that already have a source field, and
        # warning on every /reflect or /reweave edit would produce noise.
        # To enforce source on all writes, set schema_validation_strict: true
        # in ops/config.yaml.
        tool_name = hook_input.get("tool_name", "")
        if prov.warnings and tool_name == "Write":
            for w in prov.warnings:
                print(f"WARN: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
