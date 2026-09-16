from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_label_schema_ingestion_probe as schema_probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_extract_inputs(tmp_path: Path, *, extract_goal: bool = True, malformed: bool = False) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    extract_root = candidate_root / "football_external_soccernet_zip_label_member_extract_v1"
    label_rel = "extracted_labels/england_efl/2019-2020/game/Labels-ball.json"
    _write_json(
        extract_root / "zip_label_member_extract_summary.json",
        {
            "batchName": "football_external_soccernet_zip_label_member_extract",
            "goalAchieved": extract_goal,
            "primaryBlocker": None if extract_goal else "football_external_soccernet_zip_label_member_extract_failed",
            "downloadedLabelFileCount": 1 if extract_goal else 0,
            "labelJsonParseSucceeded": extract_goal,
            "annotationCount": 2 if extract_goal else 0,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_label_schema_ingestion_probe",
        },
    )
    _write_json(
        extract_root / "extracted_label_inventory.json",
        {
            "extractedLabelFileCount": 1 if extract_goal else 0,
            "extractedLabelFiles": [{"relativePath": label_rel, "memberPath": "game/Labels-ball.json", "sizeBytes": 123, "sha256": "abc"}] if extract_goal else [],
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
        },
    )
    label_path = extract_root / label_rel
    label_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"annotations": [{"bad": "shape"}]} if malformed else {
        "UrlLocal": "england_efl/2019-2020/game",
        "UrlYoutube": "https://example.invalid",
        "halftime": "45:00",
        "annotations": [
            {"gameTime": "1 - 00:01", "label": "PASS", "position": "1160", "team": "left", "visibility": "visible"},
            {"gameTime": "1 - 00:02", "label": "DRIVE", "position": "2840", "team": "right", "visibility": "not shown"},
        ],
    }
    label_path.write_text(json.dumps(payload), encoding="utf-8")
    return candidate_root


def test_label_schema_ingestion_probe_builds_adapter_plan(tmp_path: Path) -> None:
    candidate_root = _write_extract_inputs(tmp_path)

    payload = schema_probe.run_football_external_soccernet_label_schema_ingestion_probe(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_label_schema_ingestion_probe_v1"
    schema_audit = json.loads((output_root / "label_schema_audit.json").read_text(encoding="utf-8"))
    mapping_plan = json.loads((output_root / "adapter_mapping_plan.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["annotationCount"] == 2
    assert payload["requiredAnnotationFieldsPresent"] is True
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_adapter_fixture_materialization"
    assert schema_audit["requiredAnnotationFields"] == ["gameTime", "label", "position", "team", "visibility"]
    assert mapping_plan["adapterReadyForFixtureMaterialization"] is True


def test_label_schema_ingestion_probe_blocks_without_extract_truth(tmp_path: Path) -> None:
    _write_extract_inputs(tmp_path, extract_goal=False)

    payload = schema_probe.run_football_external_soccernet_label_schema_ingestion_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_extract_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_zip_label_member_extract"


def test_label_schema_ingestion_probe_blocks_malformed_schema(tmp_path: Path) -> None:
    _write_extract_inputs(tmp_path, malformed=True)

    payload = schema_probe.run_football_external_soccernet_label_schema_ingestion_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_schema_malformed"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_label_schema_contract_repair"


def test_label_schema_ingestion_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_extract_inputs(tmp_path)

    payload = schema_probe.run_football_external_soccernet_label_schema_ingestion_probe(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_label_schema_ingestion_probe",
        "soccernet_label_schema_contract_repair",
        "soccernet_label_schema_blocker_summary",
    ]
