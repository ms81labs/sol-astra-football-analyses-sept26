from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_event_lane_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_required_lane_artifacts(tmp_path: Path, *, smoke_passed: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    artifacts = {
        "football_external_soccernet_split_archive_access_review_v1/split_archive_access_review_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
        },
        "football_external_soccernet_split_archive_size_probe_v1/split_archive_size_probe_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "splitArchiveSizeBytes": 2042230928,
            "archiveDownloadExecuted": False,
        },
        "football_external_soccernet_split_archive_range_index_probe_v1/split_archive_range_index_probe_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "zipEntryCount": 6,
            "labelMemberCount": 1,
            "videoMemberCount": 2,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
        },
        "football_external_soccernet_zip_label_member_extract_v1/zip_label_member_extract_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "extractedLabelFileCount": 1,
            "annotationCount": 1604,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
        },
        "football_external_soccernet_label_schema_ingestion_probe_v1/soccernet_label_schema_ingestion_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "annotationCount": 1604,
            "distinctLabelCount": 12,
        },
        "football_external_soccernet_event_adapter_fixture_materialization_v1/soccernet_event_fixture_materialization_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "canonicalEventCount": 1604,
            "eventFixtureQualityPassed": True,
        },
        "football_external_soccernet_event_adapter_smoke_test_v1/soccernet_event_adapter_smoke_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "adapterSmokePassed": True,
            "canonicalEventCount": 1604,
        },
        "football_external_soccernet_benchmark_adapter_contract_prep_v1/soccernet_benchmark_adapter_contract_prep_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "eventBenchmarkSmokeReady": True,
            "fullBenchmarkExecutionReady": False,
        },
        "football_external_soccernet_event_benchmark_smoke_v1/soccernet_event_benchmark_smoke_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "eventBenchmarkSmokePassed": True,
            "eventCount": 1604,
            "distinctEventTypeCount": 12,
            "fullBenchmarkExecutionReady": False,
        },
        "football_external_soccernet_event_report_contract_prep_v1/soccernet_event_report_contract_prep_summary.json": {
            "goalAchieved": True,
            "primaryBlocker": None,
            "reportContractReady": True,
            "eventCount": 1604,
            "fullMatchAnalysisReady": False,
        },
        "football_external_soccernet_event_report_smoke_v1/soccernet_event_report_smoke_summary.json": {
            "goalAchieved": smoke_passed,
            "primaryBlocker": None if smoke_passed else "football_external_soccernet_event_report_render_gap",
            "eventReportSmokePassed": smoke_passed,
            "eventCount": 1604 if smoke_passed else 0,
            "distinctEventTypeCount": 12 if smoke_passed else 0,
            "fullMatchAnalysisReady": False,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    }
    for rel_path, payload in artifacts.items():
        _write_json(candidate_root / rel_path, payload)
    return candidate_root


def test_event_lane_closeout_inventory_and_gap_analysis(tmp_path: Path) -> None:
    candidate_root = _write_required_lane_artifacts(tmp_path)

    payload = closeout.run_football_external_soccernet_event_lane_closeout(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_event_lane_closeout_v1"
    inventory = json.loads((output_root / "proven_artifact_inventory.json").read_text(encoding="utf-8"))
    gaps = json.loads((output_root / "remaining_gap_analysis.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["eventOnlyLaneClosed"] is True
    assert payload["eventCount"] == 1604
    assert payload["fullMatchAnalysisReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_report_product_integration"
    assert len(inventory["artifacts"]) == len(closeout.REQUIRED_ARTIFACTS)
    assert "ball_localization" in gaps["remainingUnprovenStages"]


def test_event_lane_closeout_blocks_when_report_smoke_missing(tmp_path: Path) -> None:
    _write_required_lane_artifacts(tmp_path, smoke_passed=False)

    payload = closeout.run_football_external_soccernet_event_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_event_report_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_report_smoke"


def test_event_lane_closeout_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_required_lane_artifacts(tmp_path)

    payload = closeout.run_football_external_soccernet_event_lane_closeout(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_lane_artifact_inventory",
        "soccernet_event_lane_gap_classification_repair",
        "soccernet_event_lane_closeout_blocker_summary",
    ]
