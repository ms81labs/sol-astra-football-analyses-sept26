from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_schema_doc_fetch_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_schema_probe_inputs(
    tmp_path: Path,
    *,
    probe_goal: bool = True,
    schema_paths: list[str] | None = None,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    probe_root = candidate_root / "football_external_soccertrack_sample_schema_probe_v1"
    paths = schema_paths or [
        "docs/format-gsr.md",
        "docs/format-bas.md",
        "docs/task-gsr.html",
        "docs/task-bas.html",
        "docs/task-mot.html",
    ]
    _write_json(
        probe_root / "soccertrack_sample_schema_probe_summary.json",
        {
            "batchName": "football_external_soccertrack_sample_schema_probe",
            "goalAchieved": probe_goal,
            "roadmapAdvanceAllowed": probe_goal,
            "primaryBlocker": None if probe_goal else "football_external_soccertrack_schema_doc_surface_missing",
            "sampleSchemaProbeReady": probe_goal,
            "detectedTaskIds": ["gsr", "bas", "mot"] if probe_goal else [],
            "schemaDocCandidateCount": len(paths) if probe_goal else 0,
            "schemaDocFetchExecuted": False,
            "datasetDownloadExecuted": False,
            "sampleDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_schema_doc_fetch_approval",
        },
    )
    _write_json(
        probe_root / "soccertrack_schema_doc_fetch_plan.json",
        {
            "schemaVersion": "soccertrack_schema_doc_fetch_plan_v1",
            "selectedResourceId": "soccertrack_v2",
            "sourceRepositoryUrl": "https://github.com/AtomScott/SoccerTrack-v2",
            "schemaDocPaths": paths,
            "fetchApprovalRequired": True,
            "schemaDocFetchExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingUseAllowed": False,
        },
    )
    _write_json(
        probe_root / "soccertrack_sample_schema_contract.json",
        {
            "schemaVersion": "soccertrack_sample_schema_contract_v1",
            "selectedResourceId": "soccertrack_v2",
            "detectedTaskIds": ["gsr", "bas", "mot"],
            "schemaDocFetchApproved": False,
            "schemaDocFetchApprovalRequired": True,
            "schemaDocFetchExecuted": False,
            "sampleDownloadApproved": False,
            "sampleDownloadExecuted": False,
            "datasetDownloadApproved": False,
            "datasetDownloadExecuted": False,
            "trainingUseApproved": False,
            "schemaDocPaths": paths,
        },
    )
    return candidate_root


def test_schema_doc_fetch_approval_writes_docs_only_contract(tmp_path: Path) -> None:
    candidate_root = _write_schema_probe_inputs(tmp_path)

    payload = approval.run_football_external_soccertrack_schema_doc_fetch_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_schema_doc_fetch_approval_v1"
    contract = json.loads((output_root / "schema_doc_fetch_approval_contract.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_root / "schema_doc_access_evidence_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["schemaDocFetchApproved"] is True
    assert payload["schemaDocFetchExecuted"] is False
    assert payload["schemaDocApprovedPathCount"] == 5
    assert payload["datasetDownloadExecuted"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_fetch"
    assert contract["approvedFetchScope"] == "schema_docs_only"
    assert contract["schemaDocFetchApproved"] is True
    assert contract["datasetDownloadApproved"] is False
    assert contract["sampleDownloadApproved"] is False
    assert evidence["allSchemaDocPathsSafe"] is True
    assert evidence["unsafeSchemaDocPaths"] == []


def test_schema_doc_fetch_approval_blocks_without_schema_probe(tmp_path: Path) -> None:
    _write_schema_probe_inputs(tmp_path, probe_goal=False)

    payload = approval.run_football_external_soccertrack_schema_doc_fetch_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_sample_schema_probe_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_schema_probe"


def test_schema_doc_fetch_approval_rejects_unsafe_paths(tmp_path: Path) -> None:
    _write_schema_probe_inputs(tmp_path, schema_paths=["docs/format-gsr.md", "../private.zip"])

    payload = approval.run_football_external_soccertrack_schema_doc_fetch_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_schema_doc_path_unsafe"
    assert payload["schemaDocFetchApproved"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_schema_probe"
    assert payload["datasetDownloadExecuted"] is False


def test_schema_doc_fetch_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_schema_probe_inputs(tmp_path)

    payload = approval.run_football_external_soccertrack_schema_doc_fetch_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_schema_doc_fetch_approval",
        "soccertrack_schema_doc_access_contract_repair",
        "soccertrack_schema_doc_approval_blocker_summary",
    ]
