"""Integrity manifest for self-modifiable files.

Detects unauthorized modifications to files that influence agent behavior
across sessions. Two layers: detection at session start (warn on drift)
and prevention at write time (block writes to protected paths).

Motivation: arXiv:2602.20021v1 (Agents of Chaos) Case 10 -- externally
editable documents linked from agent memory become persistent prompt
injection vectors. The self/ directory shapes every session via
session_orient.py auto-loading.

Usage:
    python -m engram_r.integrity seal     # snapshot current hashes
    python -m engram_r.integrity verify   # compare against snapshot
    python -m engram_r.integrity status   # show protected files + state
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

PROTECTED_PATHS: frozenset[str] = frozenset(
    {
        "self/identity.md",
        "self/methodology.md",
        "ops/config.yaml",
        "ops/daemon-config.yaml",
        "ops/methodology/_compiled.md",
        "CLAUDE.md",
    }
)

MONITORED_DIRS: frozenset[str] = frozenset(
    {
        "ops/methodology",
    }
)

_MANIFEST_REL = "ops/integrity-manifest.yaml"


def compute_hash(file_path: Path) -> str:
    """SHA-256 of file content. Returns ``sha256:{hex}``."""
    content = file_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return f"sha256:{digest}"


def _scan_monitored_dirs(vault: Path) -> dict[str, str]:
    """Hash ``*.md`` files in MONITORED_DIRS (excluding PROTECTED_PATHS)."""
    monitored: dict[str, str] = {}
    for dir_rel in sorted(MONITORED_DIRS):
        dir_path = vault / dir_rel
        if not dir_path.is_dir():
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            rel = str(md_file.relative_to(vault))
            if rel in PROTECTED_PATHS:
                continue
            monitored[rel] = compute_hash(md_file)
    return monitored


def seal_manifest(vault: Path) -> Path:
    """Compute hashes for all PROTECTED_PATHS that exist. Write manifest.

    Also scans MONITORED_DIRS for ``*.md`` files and stores their hashes
    under a separate ``monitored_files`` key.

    Returns the manifest path.
    """
    files: dict[str, str] = {}
    for rel in sorted(PROTECTED_PATHS):
        full = vault / rel
        if full.exists():
            files[rel] = compute_hash(full)

    monitored = _scan_monitored_dirs(vault)

    manifest = {
        "sealed": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
        "files": files,
        "monitored_files": monitored,
    }

    manifest_path = vault / _MANIFEST_REL
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    return manifest_path


def verify_manifest(vault: Path) -> dict[str, str]:
    """Compare current file hashes against stored manifest.

    Returns ``{relative_path: status}`` where status is one of:
    ``ok``, ``modified``, ``missing``, ``new``.

    Checks both protected files and monitored directory files.

    If no manifest exists, returns an empty dict (no check possible).
    """
    manifest_path = vault / _MANIFEST_REL
    if not manifest_path.exists():
        return {}

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f) or {}

    stored = manifest.get("files", {})
    result: dict[str, str] = {}

    # Check all paths in the stored manifest (protected files)
    for rel, stored_hash in stored.items():
        full = vault / rel
        if not full.exists():
            result[rel] = "missing"
        else:
            current_hash = compute_hash(full)
            result[rel] = "ok" if current_hash == stored_hash else "modified"

    # Check for protected files that exist but weren't in the manifest
    for rel in sorted(PROTECTED_PATHS):
        if rel not in stored:
            full = vault / rel
            if full.exists():
                result[rel] = "new"

    # Check monitored files
    stored_monitored = manifest.get("monitored_files", {})
    for rel, stored_hash in stored_monitored.items():
        full = vault / rel
        if not full.exists():
            result[rel] = "missing"
        else:
            current_hash = compute_hash(full)
            result[rel] = "ok" if current_hash == stored_hash else "modified"

    # Check for new monitored files not in the manifest
    current_monitored = _scan_monitored_dirs(vault)
    for rel in current_monitored:
        if rel not in stored_monitored:
            result[rel] = "new"

    return result


def _cli_seal(args: argparse.Namespace) -> None:
    """CLI handler for 'seal' subcommand."""
    vault = Path(args.vault).resolve()
    path = seal_manifest(vault)
    print(f"Manifest sealed: {path}")


def _cli_verify(args: argparse.Namespace) -> None:
    """CLI handler for 'verify' subcommand."""
    vault = Path(args.vault).resolve()
    result = verify_manifest(vault)
    if not result:
        print("No manifest found. Run 'seal' first.")
        return

    issues = False
    for rel, status in sorted(result.items()):
        if status != "ok":
            issues = True
        print(f"  {status:>10}  {rel}")

    if issues:
        sys.exit(1)


def _cli_status(args: argparse.Namespace) -> None:
    """CLI handler for 'status' subcommand."""
    vault = Path(args.vault).resolve()
    manifest_path = vault / _MANIFEST_REL

    print(f"Protected paths ({len(PROTECTED_PATHS)}):")
    for rel in sorted(PROTECTED_PATHS):
        exists = (vault / rel).exists()
        print(f"  {'exists' if exists else 'absent':>7}  {rel}")

    print(f"\nMonitored directories ({len(MONITORED_DIRS)}):")
    for dir_rel in sorted(MONITORED_DIRS):
        dir_path = vault / dir_rel
        if dir_path.is_dir():
            count = len(list(dir_path.glob("*.md")))
            print(f"  {count:>3} files  {dir_rel}")
        else:
            print(f"  absent  {dir_rel}")

    print()
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}
        sealed = manifest.get("sealed", "unknown")
        file_count = len(manifest.get("files", {}))
        monitored_count = len(manifest.get("monitored_files", {}))
        print(f"Manifest: {manifest_path}")
        print(f"Sealed at: {sealed}")
        print(f"Files tracked: {file_count} protected, {monitored_count} monitored")
    else:
        print("Manifest: not found (run 'seal' to create)")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="engram_r.integrity",
        description="Integrity manifest for self-modifiable files",
    )
    parser.add_argument(
        "--vault",
        default=".",
        help="Vault root directory (default: current directory)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("seal", help="Snapshot current hashes of protected files")
    sub.add_parser("verify", help="Compare current files against manifest")
    sub.add_parser("status", help="Show protected files and manifest state")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "seal": _cli_seal,
        "verify": _cli_verify,
        "status": _cli_status,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
