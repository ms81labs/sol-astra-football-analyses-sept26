from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_sample_schema_probe as schema_probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_metadata_smoke_inputs(
    tmp_path: Path,
    *,
    metadata_goal: bool = True,
    readme_text: str | None = None,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    smoke_root = candidate_root / "football_external_soccertrack_metadata_adapter_smoke_v1"
    fetch_root = candidate_root / "football_external_safe_source_controlled_sample_fetch_v1"
    metadata_dir = fetch_root / "sample_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "README.md").write_text(
        readme_text
        or "\n".join(
            [
                "# SoccerTrack v2",
                "A dataset for Game State Reconstruction (GSR), Ball Action Spotting (BAS), and Multi-Object Tracking (MOT).",
                "GSR annotation format: docs/format-gsr.md",
                "BAS annotation format: docs/format-bas.md",
                "MOT task: docs/task-mot.html",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        smoke_root / "soccertrack_metadata_adapter_smoke_summary.json",
        {
            "batchName": "football_external_soccertrack_metadata_adapter_smoke",
            "goalAchieved": metadata_goal,
            "roadmapAdvanceAllowed": metadata_goal,
            "primaryBlocker": None if metadata_goal else "football_external_soccertrack_metadata_incomplete",
            "soccertrackMetadataAdapterSmokePassed": metadata_goal,
            "codeLicenseDetected": "MIT",
            "dataLicenseDetected": "CC-BY-4.0",
            "metadataSupportsAdapterProbe": metadata_goal,
            "datasetDownloadExecuted": False,
            "fullDatasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_sample_schema_probe",
        },
    )
    _write_json(
        smoke_root / "soccertrack_adapter_readiness_audit.json",
        {
            "metadataSupportsAdapterProbe": metadata_goal,
            "readmeMentionsAnnotations": metadata_goal,
            "readmeMentionsTracking": metadata_goal,
            "readmeMentionsBall": metadata_goal,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    _write_json(
        smoke_root / "soccertrack_license_metadata_audit.json",
        {
            "licenseMetadataComplete": metadata_goal,
            "codeLicenseDetected": "MIT",
            "dataLicenseDetected": "CC-BY-4.0",
            "metadataFileNames": ["LICENSE", "LICENSE-DATA", "README.md"],
        },
    )
    return candidate_root


def test_soccertrack_sample_schema_probe_writes_schema_doc_plan_without_downloads(tmp_path: Path) -> None:
    candidate_root = _write_metadata_smoke_inputs(tmp_path)

    payload = schema_probe.run_football_external_soccertrack_sample_schema_probe(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_sample_schema_probe_v1"
    surface_audit = json.loads((output_root / "soccertrack_schema_surface_audit.json").read_text(encoding="utf-8"))
    doc_plan = json.loads((output_root / "soccertrack_schema_doc_fetch_plan.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "soccertrack_sample_schema_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["sampleSchemaProbeReady"] is True
    assert payload["detectedTaskIds"] == ["gsr", "bas", "mot"]
    assert payload["schemaDocCandidateCount"] >= 2
    assert payload["datasetDownloadExecuted"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_fetch_approval"
    assert surface_audit["readmeMentionsGsr"] is True
    assert surface_audit["readmeMentionsBas"] is True
    assert surface_audit["readmeMentionsMot"] is True
    assert "docs/format-gsr.md" in doc_plan["schemaDocPaths"]
    assert "docs/format-bas.md" in doc_plan["schemaDocPaths"]
    assert contract["schemaDocFetchApproved"] is False
    assert contract["datasetDownloadApproved"] is False


def test_soccertrack_sample_schema_probe_blocks_without_metadata_smoke(tmp_path: Path) -> None:
    _write_metadata_smoke_inputs(tmp_path, metadata_goal=False)

    payload = schema_probe.run_football_external_soccertrack_sample_schema_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_metadata_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_metadata_adapter_smoke"


def test_soccertrack_sample_schema_probe_blocks_when_readme_has_no_schema_surface(tmp_path: Path) -> None:
    _write_metadata_smoke_inputs(tmp_path, readme_text="# SoccerTrack v2\nNo public schema docs here.\n")

    payload = schema_probe.run_football_external_soccertrack_sample_schema_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_schema_doc_surface_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_metadata_adapter_smoke"
    assert payload["datasetDownloadExecuted"] is False


def test_soccertrack_sample_schema_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_metadata_smoke_inputs(tmp_path)

    payload = schema_probe.run_football_external_soccertrack_sample_schema_probe(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_sample_schema_surface_probe",
        "soccertrack_schema_surface_contract_repair",
        "soccertrack_sample_schema_blocker_summary",
    ]
