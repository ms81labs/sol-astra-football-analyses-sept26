"""Tests for addon CLI entrypoint.

These tests verify the CLI surfaces correct paths for auditing
and that the CLI stays CLI-only (no service startup).
"""
import subprocess
import sys
import tempfile
import json
from pathlib import Path


ADDON_ROOT = Path(__file__).resolve().parents[1]
HELP_OUTPUT = """usage: research_addon [-h] {paths,tracks,corpus,judge} ...

Isolated autoresearch addon for supported-coverage experiments

positional arguments:
  {paths,tracks,corpus,judge}
                        Command to run
    paths               Path resolution and auditing
    tracks              Track management
    corpus              Corpus manifest management
    judge               Judge wrapper commands

options:
  -h, --help            show this help message and exit
"""


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "research_addon.cli", *arguments],
        capture_output=True,
        text=True,
        cwd=ADDON_ROOT,
        env={**subprocess.os.environ, "QT_QPA_PLATFORM": "offscreen"},
        check=False,
    )


class TestCLIPaths:
    """Test addon CLI path resolution and auditing."""

    def test_cli_help_shows_paths_command(self):
        """CLI --help exposes paths command."""
        result = _run_cli("--help")

        assert result.returncode == 0
        assert result.stdout == HELP_OUTPUT
        assert result.stderr == ""

    def test_cli_paths_resolve_reports_safe_paths(self):
        """paths resolve command reports paths staying inside addon/temp roots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_cli("paths", "resolve", "--storage-root", tmpdir)

        assert result.returncode == 0
        assert result.stdout == (
            f"Resolved storage root: {Path(tmpdir).resolve()}\n"
            f"Default run root: {Path(tempfile.gettempdir()).resolve() / 'fotball-analyst-research-addon'}\n"
            "Status: SAFE - using validated root\n"
        )
        assert result.stderr == ""

    def test_cli_paths_resolve_rejects_unsafe_backend(self):
        """paths resolve rejects overrides targeting backend/storage."""
        protected = ADDON_ROOT.parent / "backend" / "storage"
        result = _run_cli(
            "paths",
            "resolve",
            "--storage-root",
            str(protected),
        )

        assert result.returncode == 1
        assert result.stdout == ""
        assert "ERROR: Rejected" in result.stderr
        assert str(protected) in result.stderr

    def test_cli_judge_rejects_protected_root_before_dry_run(self):
        """The public CLI cannot bypass run_judge's path resolver."""
        protected = ADDON_ROOT.parent / "backend"
        result = _run_cli(
            "judge",
            "supported-coverage",
            "--dry-run",
            "--storage-root",
            str(protected),
        )

        assert result.returncode == 1
        assert "Rejected" in result.stderr

    def test_cli_judge_dry_run_accepts_owned_temporary_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_cli(
                "judge",
                "supported-coverage",
                "--dry-run",
                "--storage-root",
                tmpdir,
            )

            assert result.returncode == 0, result.stderr
            assert f'"storage_root": "{Path(tmpdir).resolve()}"' in result.stdout

    def test_tracks_list_is_available_with_config_without_execution_context(self):
        result = _run_cli("tracks", "list")

        assert result.returncode == 0
        assert "supported-coverage  [available-with-config]" in result.stdout
        assert "[executable]" not in result.stdout
        assert "[executable-now]" not in result.stdout

    def test_tracks_list_is_executable_now_with_valid_checkout_context(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "video_id": "readme",
                            "video_path": "README.md",
                            "ground_truth_path": None,
                            "tags": ["test"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = _run_cli("tracks", "list", "--manifest", str(manifest))

        assert result.returncode == 0
        assert "supported-coverage  [executable-now]" in result.stdout

    def test_cli_does_not_start_services(self):
        """CLI commands complete without starting listening services."""
        # Get initial listener state
        result_before = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result_before.returncode == 0
        assert result_before.stderr == ""
        listeners_before = set(result_before.stdout.splitlines())

        # Run a simple CLI command that shouldn't start anything
        cli_result = _run_cli("--help")

        assert cli_result.returncode == 0
        assert cli_result.stdout == HELP_OUTPUT
        assert cli_result.stderr == ""

        # Get final listener state
        result_after = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result_after.returncode == 0
        assert result_after.stderr == ""
        listeners_after = set(result_after.stdout.splitlines())

        new_listeners = listeners_after - listeners_before
        assert all("research_addon" not in listener for listener in new_listeners)
