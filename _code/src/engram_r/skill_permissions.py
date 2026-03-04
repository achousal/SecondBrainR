"""Discover skills on disk and sync Skill() permission entries in settings.json.

Called by session_orient.py (self-heal every session) and init_vault.py (initial scaffold).
Non-skill permissions (Bash, WebFetch, MCP, etc.) are never touched.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def discover_skills(vault: Path) -> set[str]:
    """Return skill names found under .claude/skills/*/SKILL.md."""
    skills_dir = vault / ".claude" / "skills"
    if not skills_dir.is_dir():
        return set()
    return {
        d.name
        for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    }


def sync_skill_permissions(vault: Path) -> bool:
    """Sync Skill() entries in .claude/settings.json to match skills on disk.

    - Reads the existing settings.json (hooks, permissions, etc.)
    - Partitions permissions.allow into Skill(...) entries vs everything else
    - Replaces Skill entries with the current disk state
    - Writes back only if changed
    - Returns True if the file was updated

    Never raises -- all errors are caught and logged.
    """
    try:
        settings_path = vault / ".claude" / "settings.json"
        if not settings_path.is_file():
            return False

        data = json.loads(settings_path.read_text(encoding="utf-8"))

        disk_skills = discover_skills(vault)
        wanted = sorted(f"Skill({name})" for name in disk_skills)

        allow = data.get("permissions", {}).get("allow", [])
        non_skill = [e for e in allow if not e.startswith("Skill(")]
        current_skill = sorted(e for e in allow if e.startswith("Skill("))

        if current_skill == wanted:
            return False

        data.setdefault("permissions", {})["allow"] = non_skill + wanted
        settings_path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        added = set(wanted) - set(current_skill)
        removed = set(current_skill) - set(wanted)
        if added:
            log.info("Skill permissions added: %s", ", ".join(sorted(added)))
        if removed:
            log.info("Skill permissions removed: %s", ", ".join(sorted(removed)))
        return True
    except Exception:
        log.debug("skill_permissions sync failed", exc_info=True)
        return False
