from __future__ import annotations

import csv
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from backend.app.main import create_app
from backend.app.training_quality_gate import run_training_quality_gate
from backend.app.workbench.flags import feature_flags


def test_t24_default_flag_is_off_and_leftovers_stay_dev_namespaced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GA_FLAG_LEFTOVER_HTTP", raising=False)
    app = create_app(storage_root=tmp_path / "storage")
    routes = [route for route in app.routes if getattr(route, "path", "").startswith("/api")]

    assert feature_flags({})["leftover_http"] is False
    assert any(route.path.startswith("/api/workbench/dev/") for route in routes)
    assert not any(
        route.path.startswith("/api/")
        and not route.path.startswith("/api/workbench/dev/")
        and "leftover_" in route.endpoint.__module__
        for route in routes
    )


def test_t24_every_frontend_api_path_resolves_with_default_flags(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GA_FLAG_LEFTOVER_HTTP", raising=False)
    app = create_app(storage_root=tmp_path / "storage")
    routes = list(app.routes)
    source = (Path(__file__).resolve().parents[2] / "frontend/src/utils/workbench.ts").read_text(encoding="utf-8")
    requested = set(re.findall(r"(?:`|'|\")(/api[^`'\"]+)", source))

    def resolves(raw: str) -> bool:
        path = re.sub(r"\$\{[^}]+\}", "value", raw.split("?", 1)[0])
        return any(
            getattr(route, "path_regex", re.compile("$^")).fullmatch(path)
            and getattr(getattr(route, "endpoint", None), "__module__", None) == "backend.app.main"
            for route in routes
        )

    assert requested
    assert sorted(path for path in requested if not resolves(path)) == []


def test_t24_h01_h05_regressions_pass_with_default_flag_off() -> None:
    root = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "GA_TEST_DEFAULT_FLAGS": "1"}
    environment.pop("GA_FLAG_LEFTOVER_HTTP", None)
    completed = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q",
            "backend/tests/test_audit_v2_h01_provider.py",
            "backend/tests/test_audit_v2_h02_review.py",
            "backend/tests/test_audit_v2_h03_calibration.py",
            "backend/tests/test_audit_v2_h04_jobs.py",
            "backend/tests/test_audit_v2_h05_recompute.py",
            "backend/tests/test_audit_v2_h05_search_eval.py",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_t25_train_function_and_cli_share_one_default_model() -> None:
    from backend import train_custom

    function_default = inspect.signature(train_custom.fine_tune).parameters["model_path"].default
    cli_default = train_custom.build_parser().get_default("model")
    assert function_default == cli_default == train_custom.DEFAULT_BASE_MODEL


def _write_gate_fixture(tmp_path: Path, *, overlap: bool = False) -> tuple[Path, Path]:
    dataset = tmp_path / "dataset"
    for split in ("train", "val"):
        (dataset / "images" / split).mkdir(parents=True)
        (dataset / "labels" / split).mkdir(parents=True)
        payload = b"same-image" if overlap else split.encode()
        (dataset / "images" / split / "sample.jpg").write_bytes(payload)
        (dataset / "labels" / split / "sample.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    dataset_yaml = dataset / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {dataset}\ntrain: images/train\nval: images/val\nnames:\n  0: ball\n",
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate"
    (candidate / "weights").mkdir(parents=True)
    (candidate / "weights" / "best.pt").write_bytes(b"weights")
    manifest = tmp_path / "dataset-manifest.json"
    manifest.write_text('{"version":1}\n', encoding="utf-8")
    config = candidate / "training-config.json"
    config.write_text('{"epochs":10}\n', encoding="utf-8")
    (candidate / "training_run_summary.json").write_text(
        json.dumps({"datasetManifestPath": str(manifest), "trainingConfigPath": str(config), "bestEpoch": 9}) + "\n",
        encoding="utf-8",
    )
    with (candidate / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "epoch", "metrics/precision(B)", "metrics/recall(B)",
                "metrics/mAP50(B)", "metrics/mAP50-95(B)",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"epoch": 7, "metrics/precision(B)": 0.8, "metrics/recall(B)": 0.8, "metrics/mAP50(B)": 0.9, "metrics/mAP50-95(B)": 0.8},
                {"epoch": 9, "metrics/precision(B)": 0.6, "metrics/recall(B)": 0.5, "metrics/mAP50(B)": 0.55, "metrics/mAP50-95(B)": 0.45},
            ]
        )
    return candidate, dataset_yaml


class _Boxes:
    def __len__(self) -> int:
        return 1


class _Model:
    def predict(self, **_kwargs):
        return [type("Result", (), {"boxes": _Boxes()})()]


def test_t25_gate_binds_checkpoint_epoch_and_hashes_inputs(tmp_path: Path) -> None:
    candidate, dataset_yaml = _write_gate_fixture(tmp_path)
    summary = run_training_quality_gate(
        candidate_root=candidate,
        dataset_yaml_path=dataset_yaml,
        model_factory=lambda _path: _Model(),
    )

    assert summary["checkpointEpoch"] == 9
    assert summary["checkpointValidationMetrics"]["map50"] == 0.55
    assert summary["trainingProgressDiagnostics"]["maxMap50"] == 0.9
    assert summary["datasetConfigSha256"] == hashlib.sha256(dataset_yaml.read_bytes()).hexdigest()
    assert summary["datasetManifestSha256"] == hashlib.sha256(b'{"version":1}\n').hexdigest()
    assert summary["trainingConfigSha256"] == hashlib.sha256(b'{"epochs":10}\n').hexdigest()
    assert summary["bestWeightsSha256"] == hashlib.sha256(b"weights").hexdigest()


def test_t25_gate_rejects_train_val_content_overlap(tmp_path: Path) -> None:
    candidate, dataset_yaml = _write_gate_fixture(tmp_path, overlap=True)
    summary = run_training_quality_gate(
        candidate_root=candidate,
        dataset_yaml_path=dataset_yaml,
        model_factory=lambda _path: _Model(),
    )

    assert summary["trainingQualityGatePassed"] is False
    assert summary["trainingQualityGatePrimaryBlocker"] == "train_val_image_overlap"
    assert summary["trainValOverlapCount"] == 1


def test_t25_gate_rejects_missing_provenance_hashes(tmp_path: Path) -> None:
    candidate, dataset_yaml = _write_gate_fixture(tmp_path)
    (candidate / "training_run_summary.json").write_text('{"bestEpoch":9}\n', encoding="utf-8")

    summary = run_training_quality_gate(
        candidate_root=candidate,
        dataset_yaml_path=dataset_yaml,
        model_factory=lambda _path: _Model(),
    )

    assert summary["trainingQualityGatePassed"] is False
    assert summary["trainingQualityGatePrimaryBlocker"] == "provenance_hash_missing"
