"""One-time repair: sync queue.json targets with actual note filenames.

For each done claim task, reads the task file's ## Create section to find
the actual title, then updates queue.json target if it differs.

Also flags phantom entries (marked done but no note exists on disk).

Usage:
    cd _code && uv run python scripts/repair_queue_targets.py [--dry-run]
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
QUEUE_PATH = VAULT / "ops" / "queue" / "queue.json"
NOTES_DIR = VAULT / "notes"


def extract_created_title(task_file: Path) -> str | None:
    """Parse actual created title from task file's ## Create section.

    Handles two formats:
      Created: [[actual title]]
      Created: notes/actual title.md
    """
    if not task_file.exists():
        return None
    content = task_file.read_text()
    match = re.search(r"## Create\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not match:
        return None
    create_section = match.group(1)

    # Format 1: wiki link
    link_match = re.search(r"Created:\s*\[\[(.+?)\]\]", create_section)
    if link_match:
        return link_match.group(1)

    # Format 2: file path
    path_match = re.search(r"Created:\s*notes/(.+?)\.md", create_section)
    if path_match:
        return path_match.group(1)

    return None


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with open(QUEUE_PATH) as f:
        queue = json.load(f)

    # Include both done and failed claims that completed create
    done_claims = [
        (i, t)
        for i, t in enumerate(queue)
        if t.get("type") == "claim"
        and t.get("status") in ("done", "failed")
        and "create" in (t.get("completed_phases") or [])
    ]

    synced = 0
    phantoms = 0
    already_correct = 0

    for idx, task in done_claims:
        task_file = VAULT / "ops" / "queue" / task["file"]
        actual_title = extract_created_title(task_file)
        old_target = task["target"]

        if actual_title is None:
            # Can't determine actual title from task file
            note_exists = (NOTES_DIR / f"{old_target}.md").exists()
            if not note_exists:
                print(f"PHANTOM  {task['id']}: no Create section and no note on disk")
                phantoms += 1
            else:
                already_correct += 1  # note exists under queue target, no rewrite detected
            continue

        note_path = NOTES_DIR / f"{actual_title}.md"
        if not note_path.exists():
            print(f"PHANTOM  {task['id']}: Created: [[{actual_title[:60]}...]] but file missing")
            phantoms += 1
            continue

        if old_target == actual_title:
            already_correct += 1
            continue

        print(f"SYNC     {task['id']}:")
        print(f"  old: {old_target[:80]}")
        print(f"  new: {actual_title[:80]}")
        if not dry_run:
            queue[idx]["target"] = actual_title
        synced += 1

    print(f"\n--- Summary ---")
    print(f"Done claims checked: {len(done_claims)}")
    print(f"Already correct:     {already_correct}")
    print(f"Synced:              {synced}")
    print(f"Phantoms:            {phantoms}")

    if "--reset-phantoms" in sys.argv and not dry_run:
        reset_count = 0
        for idx, task in done_claims:
            task_file_path = VAULT / "ops" / "queue" / task["file"]
            actual = extract_created_title(task_file_path)
            old = task["target"]
            note_on_disk = (
                (NOTES_DIR / f"{actual}.md").exists()
                if actual
                else (NOTES_DIR / f"{old}.md").exists()
            )
            if not note_on_disk:
                queue[idx]["status"] = "pending"
                queue[idx]["current_phase"] = "create"
                queue[idx]["completed_phases"] = [
                    p
                    for p in queue[idx].get("completed_phases", [])
                    if p not in ("create", "reflect", "reweave", "verify")
                ]
                queue[idx].pop("completed", None)
                reset_count += 1
        if reset_count:
            print(f"\nReset {reset_count} phantom tasks to pending/create.")

    if not dry_run and (synced > 0 or "--reset-phantoms" in sys.argv):
        with open(QUEUE_PATH, "w") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"queue.json updated.")
    elif dry_run:
        print(f"\n[dry-run] No changes written.")
        print(f"  Remove --dry-run to apply target sync.")
        print(f"  Add --reset-phantoms to also reset phantom tasks to pending/create.")


if __name__ == "__main__":
    main()
