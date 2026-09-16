from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest

from backend.scripts import runpod_session


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs/archive/2026-08-19"
CHRONOLOGY = {
    "SESSION-HANDOFF.md": (401136, "e4e87f334308e520ef6c09b4ca3e8e6a8511a55e1f234797dd0227275ce07199"),
    "activeContext.md": (269528, "b3f014148c8ae9afdc80040bff536408b363c98de0bf69deb7c313b47c280ee5"),
    "currentRoadmap.md": (204765, "4a75c90509ed37187eca6bba062dd4efae104cf7102008acd5ca6e5b01e55e6e"),
}
RETIRED_RECIPE_MODULES = (
    "run_detector_breadth_batch",
    "run_promoted_touchline_detector_candidate_source_robustness_validation",
    "run_promoted_v6_touchline_detector_candidate_v7_training",
    "run_touchline_detector_candidate_evaluation",
    "run_touchline_detector_candidate_model_data_quality_fix",
    "run_touchline_detector_candidate_proposal_signal_generation_fix",
    "run_touchline_detector_candidate_training",
    "run_touchline_detector_candidate_v5_proposal_signal_generation_fix",
    "run_touchline_validation_gate_remediation",
    "run_v7_1_bounded_retrain",
    "run_v7_1_tiny_overfit_sanity_train",
    "run_v7_2_bounded_retrain",
    "run_v7_3_bounded_retrain",
)
RETIRED_RECIPE_PUBLIC_HELPERS = (
    ("run_detector_breadth_batch", "run_local_detector_breadth_screen"),
    ("run_detector_breadth_batch", "run_remote_detector_breadth_screen"),
    ("run_touchline_detector_candidate_evaluation", "run_remote_detector_candidate_screen"),
)
RETIRED_RECIPE_SHARED_HELPERS = (
    ("run_detector_breadth_batch", "_run_remote_proof_on_session"),
    ("run_promoted_v6_touchline_detector_candidate_v7_training", "_pull_remote_artifact"),
    ("run_touchline_detector_candidate_evaluation", "_attempt_remote_proof"),
    ("run_touchline_detector_candidate_model_data_quality_fix", "_pull_remote_artifact"),
    ("run_touchline_detector_candidate_proposal_signal_generation_fix", "_create_remote_training_session"),
    ("run_touchline_detector_candidate_proposal_signal_generation_fix", "_pull_remote_artifact"),
    ("run_touchline_detector_candidate_training", "_pull_remote_artifact"),
    ("run_touchline_detector_candidate_v5_proposal_signal_generation_fix", "_pull_remote_artifact"),
    ("run_v7_1_tiny_overfit_sanity_train", "_run_runpod_training"),
)


def test_retired_recipe_guards_have_no_unreachable_tail() -> None:
    guarded_functions = 0
    for module_name in RETIRED_RECIPE_MODULES:
        path = ROOT / "backend" / "scripts" / f"{module_name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for index, statement in enumerate(node.body):
                has_retirement_guard = any(
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "require_retired_runpod_disabled"
                    for call in ast.walk(statement)
                )
                if has_retirement_guard:
                    guarded_functions += 1
                    assert index == len(node.body) - 1, (
                        f"{module_name}.{node.name} retains unreachable statements "
                        "after its retirement guard"
                    )
    assert guarded_functions == 38


def test_exact_json_helpers_are_shared() -> None:
    common_path = ROOT / "backend" / "scripts" / "football_external_real_eval_chain_common.py"
    common_tree = ast.parse(common_path.read_text(encoding="utf-8"))
    shared_bodies = {
        node.name: ast.dump(ast.Module(body=node.body, type_ignores=[]))
        for node in common_tree.body
        if isinstance(node, ast.FunctionDef) and node.name in {"load_json", "write_json"}
    }
    local_copies: list[str] = []
    for path in sorted((ROOT / "backend" / "scripts").glob("*.py")):
        if path == common_path:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            for shared_name, shared_body in shared_bodies.items():
                if body == shared_body:
                    local_copies.append(f"{path.name}:{node.name}->{shared_name}")
    assert local_copies == []


def test_chronology_is_archived_byte_identically_with_small_pointers() -> None:
    checksums = json.loads((ARCHIVE / "checksums.json").read_text(encoding="utf-8"))
    pointer_paths = {
        "SESSION-HANDOFF.md": ROOT / "SESSION-HANDOFF.md",
        "activeContext.md": ROOT / "memorybank/activeContext.md",
        "currentRoadmap.md": ROOT / "memorybank/currentRoadmap.md",
    }
    for name, (size, digest) in CHRONOLOGY.items():
        archived = ARCHIVE / name
        assert archived.stat().st_size == size
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == digest
        assert checksums[name] == {"sha256": digest, "sizeBytes": size}
        pointer = pointer_paths[name].read_text(encoding="utf-8")
        assert len(pointer.encode()) < 512
        assert f"docs/archive/2026-08-19/{name}" in pointer


def test_current_operational_surface_is_daytona_only() -> None:
    forbidden = (
        "backend.app.runpod",
        "runpod_worker",
        "PROCESSING_BACKEND=runpod",
        "RUNPOD_API_KEY",
        "deploy_to_runpod",
    )
    paths = [
        *sorted((ROOT / "backend/app").glob("*.py")),
        *sorted((ROOT / "backend/release").glob("*.py")),
        ROOT / "scripts/verify.sh",
        ROOT / ".github/workflows/ci.yml",
        ROOT / "README.md",
        ROOT / "docs/status/current.md",
        *sorted((ROOT / "docs/runbooks").glob("*.md")),
    ]
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    rendered = rendered.replace('"runpod_worker_progress"', "")
    for token in forbidden:
        assert token not in rendered
    assert not (ROOT / "backend/app/runpod.py").exists()
    assert not (ROOT / "backend/app/runpod_worker.py").exists()
    assert not (ROOT / "backend/runpod_handler").exists()


def test_current_docs_contain_safe_executable_operations_and_retirement_record() -> None:
    current_paths = [
        ROOT / "README.md",
        ROOT / "docs/status/current.md",
        ROOT / "docs/runbooks/artifact-restore.md",
        ROOT / "docs/runbooks/daytona-gpu-execution.md",
    ]
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in current_paths)
    for command in (
        "VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh",
        "python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run",
        "install -D -m 0600",
    ):
        assert command in rendered
    assert "run_daytona_gpu_smoke --real-smoke" not in rendered
    assert "/root/WorkSpace/" not in rendered
    for origin in re.findall(r"http://[^\s`]+", rendered):
        assert origin in {"http://localhost:5173", "http://127.0.0.1:5173", "http://[::1]:5173", "http://localhost:8080/tasks"}
    assert "https://" not in rendered
    assert "RunPod was retired" in rendered
    assert "No RunPod image was pushed or deployed" in rendered
    assert "No Git history was rewritten" in rendered
    assert "No model or application data was deleted" in rendered
    assert "DAYTONA_API_KEY=<redacted>" in rendered
    status = (ROOT / "docs/status/current.md").read_text(encoding="utf-8")
    for evidence_class in (
        "Software verification",
        "Actual pipeline inference",
        "Independently labeled accuracy",
        "Resource/capacity measurement",
        "Analyst acceptance",
    ):
        assert f"| {evidence_class} |" in status
    assert re.search(r"backend: `\d[\d,]* passed; 1 skipped`", status)


def test_daytona_runbook_has_credential_free_pinned_readiness_command(tmp_path: Path) -> None:
    runbook = (ROOT / "docs/runbooks/daytona-gpu-execution.md").read_text(encoding="utf-8")
    script = 'import daytona, importlib.metadata as metadata, sys; version=metadata.version("daytona"); sys.exit(f"expected daytona==0.207.0, got {version}") if version != "0.207.0" else None'
    command = f'"$DAYTONA_PYTHON" -c {shlex.quote(script)}'

    assert 'export DAYTONA_PYTHON="${DAYTONA_PYTHON:-python3}"' in runbook
    assert command in runbook
    assert '"$DAYTONA_PYTHON" -m backend.scripts.run_daytona_gpu_smoke --dry-run' in runbook
    assert "run_daytona_gpu_smoke --real-smoke" not in runbook
    assert "DAYTONA_API_KEY" not in command
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    (tmp_path / "daytona.py").write_text("", encoding="utf-8")
    dist_info = tmp_path / "daytona-9.9.9.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: daytona\nVersion: 9.9.9\n", encoding="utf-8"
    )
    optimized = subprocess.run(
        [sys.executable, "-O", "-c", script], cwd=tmp_path,
        capture_output=True, text=True, check=False,
    )
    assert optimized.returncode != 0


def test_rejected_runpod_release_records_non_mutation() -> None:
    record = (ROOT / "docs/archive/2026-08-24/rejected-runpod-release.md").read_text(encoding="utf-8")
    assert "No RunPod image was pushed or deployed" in record
    assert "No Git history was rewritten" in record
    assert "No model or application data was deleted" in record


@pytest.mark.parametrize("module_name", RETIRED_RECIPE_MODULES)
def test_historical_provider_recipe_cli_fails_before_parsing_or_io(
    module_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(f"backend.scripts.{module_name}")
    monkeypatch.setattr(sys, "argv", [module_name, "--unknown-option"])
    with pytest.raises(runpod_session.RetiredRemoteProviderError):
        module.main()
    assert "historical" in (module.__doc__ or "").lower()
    assert "retired" in (module.__doc__ or "").lower()


@pytest.mark.parametrize("module_name", RETIRED_RECIPE_MODULES)
def test_historical_provider_recipe_runner_fails_before_filesystem_mutation(
    module_name: str,
    tmp_path: Path,
) -> None:
    module = importlib.import_module(f"backend.scripts.{module_name}")
    runner = getattr(module, module_name)
    path_kwargs = {
        name: tmp_path / name
        for name in inspect.signature(runner).parameters
        if name.endswith(("_path", "_root"))
    }
    with pytest.raises(runpod_session.RetiredRemoteProviderError):
        runner(**path_kwargs)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("module_name,helper_name", RETIRED_RECIPE_PUBLIC_HELPERS)
def test_historical_provider_recipe_public_helper_fails_closed(
    module_name: str,
    helper_name: str,
    tmp_path: Path,
) -> None:
    helper = getattr(importlib.import_module(f"backend.scripts.{module_name}"), helper_name)
    kwargs: dict[str, object] = {
        "video_path": tmp_path / "sentinel.mp4",
        "clip_path": tmp_path / "sentinel.mp4",
        "session": {},
        "detector_models": (),
        "detector_entries": (),
    }
    accepted_kwargs = {
        name: kwargs[name]
        for name in inspect.signature(helper).parameters
        if name in kwargs
    }
    with pytest.raises(runpod_session.RetiredRemoteProviderError):
        helper(**accepted_kwargs)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("module_name,helper_name", RETIRED_RECIPE_SHARED_HELPERS)
def test_historical_shared_remote_helper_fails_before_filesystem_mutation(
    module_name: str,
    helper_name: str,
    tmp_path: Path,
) -> None:
    helper = getattr(importlib.import_module(f"backend.scripts.{module_name}"), helper_name)
    kwargs: dict[str, object] = {
        "session": {},
        "storage_root": tmp_path,
        "proof_name": "sentinel",
        "model_path": "sentinel.pt",
        "detector_label": "sentinel",
        "primary_detector_model_path": "sentinel.pt",
        "proof_kind": "sentinel",
        "requested_gpu_id": None,
        "remote_path": None,
        "local_path": tmp_path / "sentinel.pt",
        "dataset_root": tmp_path / "dataset",
        "data_yaml_path": tmp_path / "data.yaml",
        "output_root": tmp_path / "output",
        "training_recipe": {},
    }
    accepted_kwargs = {
        name: kwargs[name]
        for name in inspect.signature(helper).parameters
        if name in kwargs
    }
    with pytest.raises(runpod_session.RetiredRemoteProviderError):
        helper(**accepted_kwargs)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("module_name", RETIRED_RECIPE_MODULES)
def test_historical_provider_recipe_module_cli_exits_nonzero(module_name: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", f"backend.scripts.{module_name}", "--unknown-option"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "retired" in result.stderr.lower()
    assert "unrecognized arguments" not in result.stderr.lower()
