from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_event_adapter_fixture_materialization as materialize


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_schema_inputs(tmp_path: Path, *, schema_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    schema_root = candidate_root / "football_external_soccernet_label_schema_ingestion_probe_v1"
    extract_root = candidate_root / "football_external_soccernet_zip_label_member_extract_v1"
    label_rel = "extracted_labels/england_efl/2019-2020/game/Labels-ball.json"
    _write_json(
        schema_root / "soccernet_label_schema_ingestion_summary.json",
        {
            "batchName": "football_external_soccernet_label_schema_ingestion_probe",
            "goalAchieved": schema_goal,
            "primaryBlocker": None if schema_goal else "football_external_soccernet_label_schema_malformed",
            "annotationCount": 2 if schema_goal else 0,
            "distinctLabelCount": 2 if schema_goal else 0,
            "requiredAnnotationFieldsPresent": schema_goal,
            "positionParseRate": 1.0 if schema_goal else 0.0,
            "gameTimeParseRate": 1.0 if schema_goal else 0.0,
            "adapterReadyForFixtureMaterialization": schema_goal,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_event_adapter_fixture_materialization",
        },
    )
    _write_json(
        extract_root / "extracted_label_inventory.json",
        {
            "extractedLabelFileCount": 1 if schema_goal else 0,
            "extractedLabelFiles": [{"relativePath": label_rel, "memberPath": "game/Labels-ball.json", "sizeBytes": 123, "sha256": "abc"}] if schema_goal else [],
        },
    )
    label_path = extract_root / label_rel
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text(
        json.dumps(
            {
                "UrlLocal": "england_efl/2019-2020/game",
                "UrlYoutube": "https://example.invalid",
                "halftime": "45:00",
                "annotations": [
                    {"gameTime": "1 - 00:01", "label": "PASS", "position": "1160", "team": "left", "visibility": "visible"},
                    {"gameTime": "1 - 00:02", "label": "DRIVE", "position": "2840", "team": "right", "visibility": "not shown"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return candidate_root


def test_event_adapter_fixture_materializes_canonical_timeline(tmp_path: Path) -> None:
    candidate_root = _write_schema_inputs(tmp_path)

    payload = materialize.run_football_external_soccernet_event_adapter_fixture_materialization(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_event_adapter_fixture_materialization_v1"
    timeline = json.loads((output_root / "canonical_event_timeline.json").read_text(encoding="utf-8"))
    quality = json.loads((output_root / "event_fixture_quality_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["canonicalEventCount"] == 2
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_adapter_smoke_test"
    assert timeline["events"][0]["eventType"] == "PASS"
    assert timeline["events"][0]["positionMs"] == 1160
    assert quality["eventIdUnique"] is True


def test_event_adapter_fixture_blocks_without_schema_truth(tmp_path: Path) -> None:
    _write_schema_inputs(tmp_path, schema_goal=False)

    payload = materialize.run_football_external_soccernet_event_adapter_fixture_materialization(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_schema_ingestion_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_label_schema_ingestion_probe"


def test_event_adapter_fixture_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_schema_inputs(tmp_path)

    payload = materialize.run_football_external_soccernet_event_adapter_fixture_materialization(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_adapter_fixture_materialization",
        "soccernet_event_adapter_fixture_contract_repair",
        "soccernet_event_adapter_fixture_blocker_summary",
    ]
