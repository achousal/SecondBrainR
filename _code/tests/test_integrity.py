"""Tests for engram_r.integrity module."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from engram_r.integrity import (
    MONITORED_DIRS,
    PROTECTED_PATHS,
    compute_hash,
    seal_manifest,
    verify_manifest,
)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a mock vault with .arscontexta marker and protected files."""
    v = tmp_path / "vault"
    v.mkdir()
    (v / ".arscontexta").write_text("marker", encoding="utf-8")

    # Create directories
    (v / "self").mkdir()
    (v / "ops").mkdir()
    (v / "ops" / "methodology").mkdir()

    # Create protected files with known content
    (v / "self" / "identity.md").write_text(
        "# Identity\nI am a research agent.\n", encoding="utf-8"
    )
    (v / "self" / "methodology.md").write_text(
        "# Methodology\nScientific method.\n", encoding="utf-8"
    )
    (v / "ops" / "config.yaml").write_text(
        "schema_validation: true\n", encoding="utf-8"
    )
    (v / "CLAUDE.md").write_text("# CLAUDE.md\nInstructions.\n", encoding="utf-8")

    return v


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------


class TestComputeHash:
    def test_deterministic_hash(self, tmp_path: Path) -> None:
        """Same content always produces the same hash."""
        f = tmp_path / "test.txt"
        f.write_text("hello world\n", encoding="utf-8")
        h1 = compute_hash(f)
        h2 = compute_hash(f)
        assert h1 == h2
        assert h1.startswith("sha256:")
        assert len(h1) == len("sha256:") + 64

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        """Different content produces different hashes."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content A", encoding="utf-8")
        f2.write_text("content B", encoding="utf-8")
        assert compute_hash(f1) != compute_hash(f2)


# ---------------------------------------------------------------------------
# seal_manifest
# ---------------------------------------------------------------------------


class TestSealManifest:
    def test_creates_manifest(self, vault: Path) -> None:
        """Seal writes a YAML manifest with all existing protected files."""
        path = seal_manifest(vault)
        assert path.exists()
        assert path.name == "integrity-manifest.yaml"

        with open(path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        assert "sealed" in manifest
        assert "files" in manifest
        # Should have the 4 files we created in the fixture
        assert "self/identity.md" in manifest["files"]
        assert "self/methodology.md" in manifest["files"]
        assert "ops/config.yaml" in manifest["files"]
        assert "CLAUDE.md" in manifest["files"]
        # All hashes start with sha256:
        for h in manifest["files"].values():
            assert h.startswith("sha256:")

    def test_skips_missing_files(self, vault: Path) -> None:
        """No error if a protected file doesn't exist yet."""
        # daemon-config.yaml and ops/methodology/_compiled.md don't exist
        path = seal_manifest(vault)
        with open(path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        assert "ops/daemon-config.yaml" not in manifest["files"]
        assert "ops/methodology/_compiled.md" not in manifest["files"]
        # But the ones that exist are present
        assert len(manifest["files"]) == 4


# ---------------------------------------------------------------------------
# verify_manifest
# ---------------------------------------------------------------------------


class TestVerifyManifest:
    def test_detects_modification(self, vault: Path) -> None:
        """Change a file after seal, verify reports 'modified'."""
        seal_manifest(vault)
        # Modify a protected file
        (vault / "self" / "identity.md").write_text(
            "# Identity\nI am compromised.\n", encoding="utf-8"
        )
        result = verify_manifest(vault)
        assert result["self/identity.md"] == "modified"
        assert result["self/methodology.md"] == "ok"

    def test_detects_missing(self, vault: Path) -> None:
        """Delete a file after seal, verify reports 'missing'."""
        seal_manifest(vault)
        (vault / "self" / "identity.md").unlink()
        result = verify_manifest(vault)
        assert result["self/identity.md"] == "missing"

    def test_detects_new(self, vault: Path) -> None:
        """Add a protected file after seal, verify reports 'new'."""
        seal_manifest(vault)
        # Create a file that was in PROTECTED_PATHS but didn't exist at seal time
        (vault / "ops" / "daemon-config.yaml").write_text(
            "interval: 120\n", encoding="utf-8"
        )
        result = verify_manifest(vault)
        assert result["ops/daemon-config.yaml"] == "new"

    def test_no_manifest_returns_empty(self, vault: Path) -> None:
        """No manifest file -> empty dict, no crash."""
        result = verify_manifest(vault)
        assert result == {}

    def test_all_ok(self, vault: Path) -> None:
        """Unchanged files after seal all report 'ok'."""
        seal_manifest(vault)
        result = verify_manifest(vault)
        expected_ok = [
            "self/identity.md",
            "self/methodology.md",
            "ops/config.yaml",
            "CLAUDE.md",
        ]
        for rel in expected_ok:
            assert result[rel] == "ok"


# ---------------------------------------------------------------------------
# PROTECTED_PATHS constant
# ---------------------------------------------------------------------------


class TestProtectedPaths:
    def test_contains_expected_set(self) -> None:
        """PROTECTED_PATHS contains the documented set of files."""
        expected = {
            "self/identity.md",
            "self/methodology.md",
            "ops/config.yaml",
            "ops/daemon-config.yaml",
            "ops/methodology/_compiled.md",
            "CLAUDE.md",
        }
        assert expected == PROTECTED_PATHS

    def test_is_frozenset(self) -> None:
        """PROTECTED_PATHS is immutable."""
        assert isinstance(PROTECTED_PATHS, frozenset)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_seal(self, vault: Path) -> None:
        """CLI seal subcommand creates manifest."""
        result = subprocess.run(
            [
                sys.executable, "-m", "engram_r.integrity",
                "--vault", str(vault), "seal",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent / "src"),
        )
        assert result.returncode == 0
        assert "Manifest sealed" in result.stdout
        assert (vault / "ops" / "integrity-manifest.yaml").exists()

    def test_cli_verify(self, vault: Path) -> None:
        """CLI verify subcommand reports file statuses."""
        # Seal first
        seal_manifest(vault)
        result = subprocess.run(
            [
                sys.executable, "-m", "engram_r.integrity",
                "--vault", str(vault), "verify",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent / "src"),
        )
        assert result.returncode == 0
        assert "ok" in result.stdout

    def test_cli_verify_detects_modification(self, vault: Path) -> None:
        """CLI verify exits with code 1 when files are modified."""
        seal_manifest(vault)
        (vault / "CLAUDE.md").write_text("# Corrupted\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, "-m", "engram_r.integrity",
                "--vault", str(vault), "verify",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent / "src"),
        )
        assert result.returncode == 1
        assert "modified" in result.stdout


# ---------------------------------------------------------------------------
# Monitored directories
# ---------------------------------------------------------------------------


class TestMonitoredDirs:
    def test_seal_includes_monitored_files(self, vault: Path) -> None:
        """seal_manifest hashes .md files in MONITORED_DIRS."""
        # Create methodology source files
        (vault / "ops" / "methodology" / "derivation-rationale.md").write_text(
            "# Rationale\nOriginal.\n", encoding="utf-8"
        )
        (vault / "ops" / "methodology" / "parallel-workflow.md").write_text(
            "# Parallel\nGuidance.\n", encoding="utf-8"
        )
        path = seal_manifest(vault)
        with open(path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        monitored = manifest.get("monitored_files", {})
        assert "ops/methodology/derivation-rationale.md" in monitored
        assert "ops/methodology/parallel-workflow.md" in monitored
        # _compiled.md is in PROTECTED_PATHS, not monitored
        assert "ops/methodology/_compiled.md" not in monitored

    def test_verify_detects_drift_in_monitored(self, vault: Path) -> None:
        """Modifying a monitored file reports 'modified'."""
        (vault / "ops" / "methodology" / "source.md").write_text(
            "Original content.\n", encoding="utf-8"
        )
        seal_manifest(vault)
        # Modify after seal
        (vault / "ops" / "methodology" / "source.md").write_text(
            "Changed content.\n", encoding="utf-8"
        )
        result = verify_manifest(vault)
        assert result["ops/methodology/source.md"] == "modified"

    def test_monitored_vs_protected_separation(self, vault: Path) -> None:
        """Monitored files are stored separately from protected files."""
        (vault / "ops" / "methodology" / "source.md").write_text(
            "Source.\n", encoding="utf-8"
        )
        path = seal_manifest(vault)
        with open(path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        files = manifest.get("files", {})
        monitored = manifest.get("monitored_files", {})

        # Protected file is in files, not monitored
        assert "self/identity.md" in files
        assert "self/identity.md" not in monitored
        # Methodology source is in monitored, not files
        assert "ops/methodology/source.md" in monitored
        assert "ops/methodology/source.md" not in files
