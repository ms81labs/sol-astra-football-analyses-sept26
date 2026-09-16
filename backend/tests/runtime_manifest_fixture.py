from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import ModuleType


def install_minimal_runtime_manifest(
    tmp_path: Path,
    monkeypatch,  # noqa: ANN001
    runtime_module: ModuleType,
) -> Path:
    """Install a real validated release default for runtime-boundary tests."""

    content = b"test-release-primary-model"
    artifact_root = tmp_path / "release-root"
    artifact_path = artifact_root / "artifacts/primary-model.pt"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(content)
    container_artifact_path = artifact_root / "app/models/primary-model.pt"
    container_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    container_artifact_path.write_bytes(content)
    manifest_path = tmp_path / "release-v7.3.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "releaseVersion": "v7.3",
                "candidateVersion": "v7.3",
                "runtimeVersion": "v7.3",
                "sourceCommit": "a" * 40,
                "createdAt": "2026-08-24T00:00:00Z",
                "runtimeOptions": {
                    "primary_model": {"artifactId": "primary-model"},
                    "auxiliary_ball_model": None,
                    "auxiliary_ball_model_profile": None,
                    "primary_acquisition_mode": "anchored_player_ranked_context_960",
                    "edge_share_repair_profile": None,
                    "baseline_guided_rescue_reference": None,
                    "proposal_selection_truth_seed": None,
                    "reviewed_positive_anchor_seed": None,
                },
                "artifacts": [
                    {
                        "id": "primary-model",
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "sizeBytes": len(content),
                        "localRelativePath": "artifacts/primary-model.pt",
                        "containerPath": "/app/models/primary-model.pt",
                        "origin": "test-fixture",
                        "retentionClass": "release-essential",
                    }
                ],
                "requiredContracts": [
                    "video_to_analysis_product_api_v1",
                    "video_to_analysis_report_v1",
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_module, "RUNTIME_MANIFEST_PATH", manifest_path)
    if hasattr(runtime_module, "RUNTIME_ARTIFACT_ROOT"):
        monkeypatch.setattr(runtime_module, "RUNTIME_ARTIFACT_ROOT", artifact_root.resolve())
    return manifest_path
