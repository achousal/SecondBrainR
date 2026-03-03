"""Stop hook: capture session summary to ops/sessions/.

Extracts key information from the session and writes a compact
summary note. Never fails the session -- all exceptions are caught.

Usage (Claude Code hook):
    uv run python scripts/hooks/session_capture.py

Stdin JSON shape (Claude Code Stop hook, all 7 fields):
    {
        "session_id": "abc123",
        "transcript_path": "~/.claude/projects/.../uuid.jsonl",
        "cwd": "/Users/...",
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": true,
        "last_assistant_message": "I've completed..."
    }

Exit behavior:
    - Always exits 0. Never blocks or fails the session.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent.parent

# Ensure src/ is importable for engram_r package
sys.path.insert(0, str(_CODE_DIR / "src"))

from engram_r.hook_utils import load_config, resolve_vault  # noqa: E402


def _git_files_changed(cwd: str) -> list[str]:
    """Return files changed on disk according to git.

    Runs ``git status --porcelain`` from *cwd* and returns a sorted list of
    relative paths.  Returns an empty list on any error (not a git repo,
    git not installed, etc.).
    """
    if not cwd:
        return []
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        files = set()
        for line in result.stdout.splitlines():
            # porcelain format: XY filename  (or XY old -> new for renames)
            if len(line) < 4:
                continue
            entry = line[3:]
            # Handle renames: "old -> new"
            if " -> " in entry:
                entry = entry.split(" -> ", 1)[1]
            files.add(entry.strip())
        return sorted(files)
    except Exception:
        return []


def _extract_session_info(hook_input: dict) -> dict:
    """Extract summary info from hook input and optionally transcript.

    Primary summary source: ``last_assistant_message`` from stdin.
    Secondary enrichment: transcript parsing for files_written and skills_invoked
    (when transcript_path exists and is readable).
    """
    cwd = hook_input.get("cwd", "")
    info: dict = {
        "session_id": hook_input.get("session_id", "unknown"),
        "cwd": cwd,
        "permission_mode": hook_input.get("permission_mode", ""),
        "files_changed": _git_files_changed(cwd),
        "files_written": [],
        "skills_invoked": [],
        "summary": "",
    }

    # Primary: use last_assistant_message directly from hook stdin
    last_msg = hook_input.get("last_assistant_message", "")
    if isinstance(last_msg, str) and last_msg.strip():
        summary = last_msg.strip()
        if len(summary) > 300:
            summary = summary[:300] + "..."
        info["summary"] = summary

    # Secondary: enrich with transcript data if available
    transcript_path = hook_input.get("transcript_path", "")
    if transcript_path and Path(transcript_path).exists():
        try:
            lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()

            files = set()
            skills = set()

            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if isinstance(entry, dict):
                    tool_name = entry.get("tool_name", "")
                    tool_input = entry.get("tool_input", {})
                    if isinstance(tool_input, dict):
                        fp = tool_input.get("file_path", "")
                        if fp and tool_name in ("Write", "Edit"):
                            files.add(fp)

                    if tool_name == "Skill":
                        skill = tool_input.get("skill", "")
                        if skill:
                            skills.add(f"/{skill}")

            info["files_written"] = sorted(files)
            info["skills_invoked"] = sorted(skills)

            # Fallback: if no last_assistant_message, try transcript
            if not info["summary"]:
                last_assistant = ""
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(entry, dict):
                        role = entry.get("role", "")
                        if role == "assistant":
                            content = entry.get("content", "")
                            if isinstance(content, str) and content.strip():
                                last_assistant = content.strip()
                if last_assistant:
                    if len(last_assistant) > 300:
                        last_assistant = last_assistant[:300] + "..."
                    info["summary"] = last_assistant

        except Exception as exc:
            print(
                f"session_capture: transcript parse error: {exc}",
                file=sys.stderr,
            )

    return info


def _slack_session_end(vault: Path, info: dict) -> None:
    """Fire session_end Slack notification. Never raises."""
    try:
        from engram_r.slack_notify import send_notification

        send_notification(
            "session_end",
            vault,
            session_id=info.get("session_id", ""),
            files_written=info.get("files_written", []),
            skills_invoked=info.get("skills_invoked", []),
            summary=info.get("summary", ""),
        )
    except Exception:
        pass


def main() -> None:
    try:
        config = load_config()

        if not config.get("session_capture", True):
            return

        vault = resolve_vault(config)

        raw = sys.stdin.read()
        if not raw.strip():
            return

        hook_input = json.loads(raw)
        info = _extract_session_info(hook_input)

        sessions_dir = vault / "ops" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        session_prefix = info["session_id"][:8] if info["session_id"] else "unknown"
        filename = f"{today}-{session_prefix}.md"
        output_path = sessions_dir / filename

        parts = [
            "---",
            f"date: {today}",
            f'session_id: "{info["session_id"]}"',
        ]
        if info["cwd"]:
            parts.append(f'cwd: "{info["cwd"]}"')
        if info["permission_mode"]:
            parts.append(f'permission_mode: "{info["permission_mode"]}"')
        parts.extend([
            "---",
            "",
            "## Files Changed",
        ])

        if info["files_changed"]:
            for fp in info["files_changed"]:
                parts.append(f"- `{fp}`")
        else:
            parts.append("(none)")

        parts.append("")
        parts.append("## Tool Calls")

        if info["files_written"]:
            for fp in info["files_written"]:
                parts.append(f"- `{fp}`")
        else:
            parts.append("(none)")

        parts.append("")
        parts.append("## Skills Invoked")

        if info["skills_invoked"]:
            for s in info["skills_invoked"]:
                parts.append(f"- {s}")
        else:
            parts.append("(none)")

        parts.append("")
        parts.append("## Session Summary")
        parts.append(info["summary"] or "(no summary available)")
        parts.append("")

        output_path.write_text("\n".join(parts), encoding="utf-8")

        _slack_session_end(vault, info)

    except Exception as exc:
        print(f"session_capture: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
