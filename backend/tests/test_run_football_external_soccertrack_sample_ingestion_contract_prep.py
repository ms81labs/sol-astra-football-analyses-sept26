from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_sample_ingestion_contract_prep as contract_prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_parse_inputs(tmp_path: Path, *, parse_ready: bool = True, mapping_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    parse_root = candidate_root / "football_external_soccertrack_schema_doc_parse_v1"
    parsed_tasks = ["gsr", "bas", "mot"] if parse_ready else []
    field_tasks = ["gsr", "bas"] if parse_ready else []
    _write_json(
        parse_root / "schema_doc_parse_summary.json",
        {
            "batchName": "football_external_soccertrack_schema_doc_parse",
            "goalAchieved": parse_ready,
            "roadmapAdvanceAllowed": parse_ready,
            "primaryBlocker": None if parse_ready else "football_external_soccertrack_schema_doc_parse_insufficient",
            "schemaDocParseReady": parse_ready,
            "parsedTaskIds": parsed_tasks,
            "fieldLevelParsedTaskIds": field_tasks,
            "datasetDownloadExecuted": False,
            "sampleDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_sample_ingestion_contract_prep",
        },
    )
    _write_json(
        parse_root / "soccertrack_parsed_schema_contract.json",
        {
            "schemaVersion": "soccertrack_parsed_schema_contract_v1",
            "contractSource": "fetched_schema_docs_only",
            "requiredAdapterSchemaNames": ["FrameState", "GameState", "TrackFrame", "TrackedEntity", "BallActionEvent", "EventStream"],
            "taskContracts": {
                "gsr": {"requiredFields": ["image_id", "track_id", "x", "y"], "frameRateFps": 25},
                "bas": {"requiredFields": ["gameTime", "position", "label", "team"], "labelSet": ["Pass", "Drive", "Shot"]},
                "mot": {"taskLevelParsed": True, "allParsedFields": ["frame", "track_id", "x, y, w, h"]},
            },
            "datasetDownloadExecuted": False,
            "sampleDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    _write_json(
        parse_root / "sample_adapter_mapping_plan.json",
        {
            "schemaVersion": "soccertrack_sample_adapter_mapping_plan_v1",
            "nextRequiredArtifact": "soccertrack_sample_fixture_materialization_plan",
            "mappingRows": [
                {"taskId": "gsr", "sourceField": "image_id", "targetField": "FrameState.frameIndex"},
                {"taskId": "gsr", "sourceField": "x,y", "targetField": "TrackedEntity.pitchPositionMeters"},
                {"taskId": "bas", "sourceField": "position", "targetField": "BallActionEvent.timestampMs"},
                {"taskId": "mot", "sourceField": "frame,bbox,player_id", "targetField": "TrackFrame.entities"},
            ]
            if mapping_ready
            else [],
            "parseReadiness": {"gsrFieldLevelParsed": parse_ready, "basFieldLevelParsed": parse_ready, "motTaskLevelParsed": parse_ready},
            "datasetDownloadExecuted": False,
            "sampleDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    return candidate_root


def test_soccertrack_sample_ingestion_contract_prep_writes_approval_gated_fixture_plan(tmp_path: Path) -> None:
    candidate_root = _write_parse_inputs(tmp_path)

    payload = contract_prep.run_football_external_soccertrack_sample_ingestion_contract_prep(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_sample_ingestion_contract_prep_v1"
    contract = json.loads((output_root / "soccertrack_sample_ingestion_contract.json").read_text(encoding="utf-8"))
    fixture_plan = json.loads((output_root / "soccertrack_sample_fixture_materialization_plan.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "download_scope_guardrail_audit.json").read_text(encoding="utf-8"))
    mapping_audit = json.loads((output_root / "schema_to_adapter_mapping_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["sampleIngestionContractReady"] is True
    assert payload["selectedSampleResourceId"] == "soccertrack_v2"
    assert payload["sampleDownloadApprovalRequired"] is True
    assert payload["datasetDownloadExecuted"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_fixture_materialization_approval"
    assert contract["sampleDownloadApproved"] is False
    assert contract["fullDatasetDownloadApproved"] is False
    assert fixture_plan["materializationApproved"] is False
    assert fixture_plan["requiredTaskFixtures"] == ["gsr", "bas", "mot"]
    assert guardrail["downloadScopeGuardrailPassed"] is True
    assert mapping_audit["mappingCompletenessPassed"] is True


def test_soccertrack_sample_ingestion_contract_prep_blocks_without_parse_truth(tmp_path: Path) -> None:
    _write_parse_inputs(tmp_path, parse_ready=False)

    payload = contract_prep.run_football_external_soccertrack_sample_ingestion_contract_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_schema_doc_parse_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_parse"
    assert payload["sampleDownloadExecuted"] is False


def test_soccertrack_sample_ingestion_contract_prep_blocks_incomplete_mapping(tmp_path: Path) -> None:
    _write_parse_inputs(tmp_path, mapping_ready=False)

    payload = contract_prep.run_football_external_soccertrack_sample_ingestion_contract_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_sample_mapping_incomplete"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_parse_repair"


def test_soccertrack_sample_ingestion_contract_prep_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_parse_inputs(tmp_path)

    payload = contract_prep.run_football_external_soccertrack_sample_ingestion_contract_prep(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_sample_ingestion_contract_prep",
        "soccertrack_sample_ingestion_contract_repair",
        "soccertrack_sample_ingestion_blocker_summary",
    ]
