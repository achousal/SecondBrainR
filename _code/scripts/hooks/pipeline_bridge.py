"""PostToolUse hook: suggest /reduce for new literature/hypothesis files.

Detects writes to _research/literature/ and _research/hypotheses/ and
suggests running /reduce if the file is not already queued. Non-blocking,
informational only. Never modifies files.

Ported from pipeline-bridge.sh.

Usage (Claude Code hook):
    uv run python scripts/hooks/pipeline_bridge.py

Stdin JSON shape:
    {"tool_name": "Write", "tool_input": {"file_path": "..."}}

Exit behavior:
    - Always exits 0. Prints suggestion to stdout if applicable.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent.parent

sys.path.insert(0, str(_CODE_DIR / "src"))

from engram_r.hook_utils import load_config, resolve_vault  # noqa: E402


def _classify_file(rel_path: str) -> str | None:
    """Return note type string if file is a literature or hypothesis note.

    Returns None for non-matching files, index files, and templates.
    """
    # Skip index files and templates
    skip_prefixes = ("_research/literature/_index.md", "_research/hypotheses/_index.md")
    if rel_path in skip_prefixes or rel_path.startswith("_code/templates/"):
        return None

    if rel_path.startswith("_research/literature/") and rel_path.endswith(".md"):
        return "literature note"
    if rel_path.startswith("_research/hypotheses/") and rel_path.endswith(".md"):
        return "hypothesis"

    return None


def _is_already_queued(queue_path: Path, rel_path: str) -> bool:
    """Check if a reduce task already exists in queue.json for this file."""
    if not queue_path.exists():
        return False
    try:
        data = json.loads(queue_path.read_text(encoding="utf-8"))
        tasks = data.get("tasks", [])
        for task in tasks:
            src = task.get("source", "")
            if rel_path in src and task.get("status") != "done":
                return True
    except (json.JSONDecodeError, Exception) as exc:
        print(
            f"pipeline_bridge: malformed queue.json: {exc}",
            file=sys.stderr,
        )
    return False


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, Exception) as exc:
        print(f"pipeline_bridge: stdin parse error: {exc}", file=sys.stderr)
        return

    tool_input = hook_input.get("tool_input", {})
    file_path_str = tool_input.get("file_path", "")
    if not file_path_str:
        return

    vault = resolve_vault()
    vault_str = str(vault.resolve())
    file_path = Path(file_path_str).resolve()

    # Compute vault-relative path
    try:
        rel_path = str(file_path.relative_to(vault.resolve()))
    except ValueError:
        return

    note_type = _classify_file(rel_path)
    if note_type is None:
        return

    # Check queue dedup
    queue_path = vault / "ops" / "queue" / "queue.json"
    if _is_already_queued(queue_path, rel_path):
        return

    basename = Path(rel_path).name
    suggestion = f"New {note_type}: {basename}. Consider: /reduce {rel_path}"
    print(f"[Pipeline Bridge] {suggestion}")

    # D1: audit trail
    config = load_config()
    if config.get("pipeline_bridge_log", True):
        log_path = vault / "ops" / "pipeline-suggestions.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts} | {suggestion}\n")
        except OSError as exc:
            print(f"pipeline_bridge: log write failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
