from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_metadata_adapter_smoke as metadata_smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_metadata_inputs(tmp_path: Path, *, fetch_goal: bool = True, include_license_data: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fetch_root = candidate_root / "football_external_safe_source_controlled_sample_fetch_v1"
    metadata_dir = fetch_root / "sample_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "README.md").write_text(
        "SoccerTrack v2\n\nAnnotations are available for tracking and ball localization.\n", encoding="utf-8"
    )
    (metadata_dir / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    if include_license_data:
        (metadata_dir / "LICENSE-DATA").write_text("Creative Commons Attribution 4.0 International\n", encoding="utf-8")
    files = [
        {"name": "README.md", "relativePath": "sample_metadata/README.md", "sha256": "a"},
        {"name": "LICENSE", "relativePath": "sample_metadata/LICENSE", "sha256": "b"},
    ]
    if include_license_data:
        files.append({"name": "LICENSE-DATA", "relativePath": "sample_metadata/LICENSE-DATA", "sha256": "c"})
    _write_json(
        fetch_root / "controlled_sample_fetch_summary.json",
        {
            "batchName": "football_external_safe_source_controlled_sample_fetch",
            "goalAchieved": fetch_goal,
            "primaryBlocker": None if fetch_goal else "football_external_controlled_fetch_failed",
            "selectedSampleResourceId": "soccertrack_v2",
            "fetchScope": "metadata_only",
            "controlledMetadataFetchExecuted": fetch_goal,
            "fetchedFileCount": len(files),
            "fetchFailureCount": 0,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_metadata_adapter_smoke",
        },
    )
    _write_json(
        fetch_root / "fetch_provenance_audit.json",
        {"files": files, "failures": [], "sha256ByFile": {row["name"]: row["sha256"] for row in files}},
    )
    return candidate_root


def test_metadata_adapter_smoke_extracts_license_and_stage_readiness(tmp_path: Path) -> None:
    candidate_root = _write_metadata_inputs(tmp_path)

    payload = metadata_smoke.run_football_external_soccertrack_metadata_adapter_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_metadata_adapter_smoke_v1"
    license_audit = json.loads((output_root / "soccertrack_license_metadata_audit.json").read_text(encoding="utf-8"))
    adapter_audit = json.loads((output_root / "soccertrack_adapter_readiness_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["soccertrackMetadataAdapterSmokePassed"] is True
    assert payload["codeLicenseDetected"] == "MIT"
    assert payload["dataLicenseDetected"] == "CC-BY-4.0"
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_schema_probe"
    assert license_audit["licenseMetadataComplete"] is True
    assert adapter_audit["metadataSupportsAdapterProbe"] is True
    assert (output_root / "decision_matrix.json").exists()


def test_metadata_adapter_smoke_blocks_without_fetch_truth(tmp_path: Path) -> None:
    _write_metadata_inputs(tmp_path, fetch_goal=False)

    payload = metadata_smoke.run_football_external_soccertrack_metadata_adapter_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_metadata_fetch_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_controlled_sample_fetch"


def test_metadata_adapter_smoke_blocks_missing_data_license(tmp_path: Path) -> None:
    _write_metadata_inputs(tmp_path, include_license_data=False)

    payload = metadata_smoke.run_football_external_soccertrack_metadata_adapter_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_data_license_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_sample_download_approval"


def test_metadata_adapter_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_metadata_inputs(tmp_path)

    payload = metadata_smoke.run_football_external_soccertrack_metadata_adapter_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_metadata_adapter_smoke",
        "soccertrack_metadata_contract_repair",
        "soccertrack_metadata_blocker_summary",
    ]
