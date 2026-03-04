"""PostToolUse hook (sync): block phantom enrichment targets in queue.json.

Reads tool input from stdin (JSON). If the written file is
``ops/queue/queue.json``, compares the new queue against the on-disk
version and blocks any new enrichment entries whose ``target`` does not
resolve to an existing ``.md`` file in ``notes/``.

Usage (Claude Code hook):
    uv run python scripts/hooks/validate_queue.py

Stdin JSON shape:
    {"tool_name": "Write", "tool_input": {"file_path": "...", "content": "..."}}

Exit behavior:
    - Print JSON with ``"decision": "block"`` when phantom targets found.
    - Exit 0 silently on success or non-queue files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to path so we can import engram_r
_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_CODE_DIR / "src"))

from engram_r.hook_utils import load_config, resolve_vault  # noqa: E402
from engram_r.queue_validator import (  # noqa: E402
    find_new_enrichment_entries,
    validate_enrichment_targets,
)

# Relative path within the vault that this hook monitors.
_QUEUE_REL_PATH = Path("ops") / "queue" / "queue.json"


def main() -> None:
    """Validate enrichment targets when queue.json is written."""
    config = load_config()

    if not config.get("enrichment_target_validation", True):
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

    # Only act on queue.json writes
    try:
        vault_resolved = vault.resolve()
        file_resolved = file_path.resolve()
        if not str(file_resolved).startswith(str(vault_resolved)):
            return
        rel = file_resolved.relative_to(vault_resolved)
    except (ValueError, Exception):
        return

    if rel != _QUEUE_REL_PATH:
        return

    # Parse the new queue content from the write
    content = tool_input.get("content", "")
    if not content:
        return

    try:
        new_queue = json.loads(content)
    except (json.JSONDecodeError, Exception):
        return

    if not isinstance(new_queue, list):
        return

    # Read the old queue from disk (still on disk because hook fires before
    # the write completes)
    queue_path = vault_resolved / _QUEUE_REL_PATH
    old_queue: list[dict] = []
    if queue_path.exists():
        try:
            old_queue = json.loads(queue_path.read_text(encoding="utf-8"))
            if not isinstance(old_queue, list):
                old_queue = []
        except (json.JSONDecodeError, Exception):
            old_queue = []

    # Find genuinely new enrichment entries
    new_entries = find_new_enrichment_entries(old_queue, new_queue)
    if not new_entries:
        return

    # Validate targets exist on disk
    notes_dir = vault_resolved / "notes"
    result = validate_enrichment_targets(new_entries, notes_dir)

    if not result.valid:
        phantom_details = "; ".join(
            f"[{p['id']}] target={p.get('target', '<none>')}"
            for p in result.phantom_entries
        )
        response = {
            "decision": "block",
            "reason": (
                f"Phantom enrichment target(s) -- note does not exist in notes/: "
                f"{phantom_details}. "
                f"Verify target exists on disk or extract as a new claim instead."
            ),
        }
        print(json.dumps(response))
        sys.exit(0)


if __name__ == "__main__":
    main()
