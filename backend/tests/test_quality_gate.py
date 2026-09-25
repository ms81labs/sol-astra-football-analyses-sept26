"""The quality ratchet must fail closed, without hiding entire legacy files."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

# Developer tooling is deliberately outside the installed backend package.
# Load this exact source file without relying on pytest's entry-point sys.path.
_quality = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts" / "check_python_quality.py"))
compare_baseline = _quality["compare_baseline"]
normalise_diagnostics = _quality["normalise_diagnostics"]
run_tool = _quality["run_tool"]


def test_new_diagnostic_does_not_hide_behind_existing_debt():
    assert compare_baseline(["old"], ["old", "new"]) == (["new"], [])


def test_removed_debt_requires_baseline_cleanup():
    assert compare_baseline(["old"], []) == ([], ["old"])


def test_duplicate_diagnostics_are_counted():
    assert compare_baseline(["same"], ["same", "same"]) == (["same"], [])


def test_identity_survives_unrelated_line_insertion(tmp_path):
    path = tmp_path / "module.py"
    path.write_text("def f():\n    unused = 1\n")
    diagnostic = {"filename": str(path), "location": {"row": 2}, "code": "F841", "message": "unused"}
    first = normalise_diagnostics("ruff", json.dumps([diagnostic]), tmp_path)
    path.write_text("\n\ndef f():\n    unused = 1\n")
    diagnostic["location"]["row"] = 4
    assert normalise_diagnostics("ruff", json.dumps([diagnostic]), tmp_path) == first


def test_identical_errors_in_different_functions_are_distinct(tmp_path):
    path = tmp_path / "module.py"
    path.write_text("def first():\n    unused = 1\ndef second():\n    unused = 1\n")
    diagnostics = [{"filename": str(path), "location": {"row": row}, "code": "F841", "message": "unused"} for row in (2, 4)]
    keys = normalise_diagnostics("ruff", json.dumps(diagnostics), tmp_path)
    assert keys[0] != keys[1]


@pytest.mark.parametrize("returncode,stdout,stderr", [(2, "[]", "crash"), (0, "not json", ""), (1, "[]", "crash"), (0, "[]", "unexpected warning")])
def test_tool_failure_cannot_pass(tmp_path, monkeypatch, returncode, stdout, stderr):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], returncode, stdout, stderr))
    with pytest.raises((RuntimeError, ValueError)):
        run_tool("ruff", tmp_path)


def test_valid_clean_run_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "[]", ""))
    assert run_tool("ruff", tmp_path) == []


def test_unrecognised_mypy_severity_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        normalise_diagnostics("mypy", json.dumps({"severity": "fatal"}), tmp_path)


def test_quality_tests_load_without_repository_on_import_path(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import runpy, sys; runpy.run_path(sys.argv[1])", str(Path(__file__).resolve())],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_mypy_scope_keeps_clean_numeric_and_route_contracts():
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    required = {
        "backend/app/workbench", "backend/app/schemas.py",
        "backend/app/settings.py", "backend/app/run_benchmarks.py",
        "backend/app/insight_routes.py", "backend/app/job_routes.py",
        "backend/app/match_runtime_routes.py", "backend/app/review_routes.py",
        "backend/app/numeric_types.py",
    }
    assert required <= set(config["tool"]["mypy"]["files"])
    baseline = json.loads((root / "backend/quality/mypy-baseline.json").read_text())
    assert baseline["diagnostics"] == []
