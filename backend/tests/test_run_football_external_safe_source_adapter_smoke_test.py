from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_safe_source_adapter_smoke_test as safe_smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _resource(resource_id: str, *, stages: list[str] | None = None, download_allowed: bool = False) -> dict[str, object]:
    return {
        "resourceId": resource_id,
        "resourceName": resource_id.replace("_", " ").title(),
        "accessDecision": "approved_smoke_only",
        "benchmarkSmokeUseAllowed": True,
        "downloadAllowedByThisBatch": download_allowed,
        "trainingUseAllowed": False,
        "coveredStages": stages or ["tracking", "ball_localization"],
    }


def _write_safe_smoke_inputs(
    tmp_path: Path,
    *,
    safe_resources: list[dict[str, object]] | None = None,
    access_download_executed: bool = False,
    include_access_review: bool = True,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    harness_root = candidate_root / "football_external_benchmark_harness_prep_v1"
    access_root = candidate_root / "football_external_dataset_access_review_v1"

    _write_json(
        harness_root / "external_benchmark_harness_summary.json",
        {
            "batchName": "football_external_benchmark_harness_prep",
            "goalAchieved": True,
            "primaryBlocker": None,
            "benchmarkHarnessContractReady": True,
            "datasetAccessReviewReady": True,
            "externalBenchmarkExecutionReady": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        harness_root / "benchmark_resource_inventory.json",
        {
            "resources": [
                _resource("soccertrack_v2", stages=["tracking", "ball_localization"]),
                _resource("skillcorner_open_data", stages=["calibration", "tracking", "ball_localization"]),
                _resource("statsbomb_open_data_360", stages=["possession_event_semantics", "tactical_reporting"]),
            ]
        },
    )
    _write_json(
        harness_root / "dataset_adapter_contract.json",
        {
            "schemas": {
                "FrameState": {
                    "requiredFields": [
                        "source",
                        "matchId",
                        "frameIndex",
                        "timestampMs",
                        "imagePath",
                        "homography",
                        "players",
                        "ball",
                        "events",
                        "possession",
                    ]
                },
                "GameState": {
                    "requiredFields": [
                        "matchId",
                        "frameIndex",
                        "timestampMs",
                        "entities",
                        "ball",
                        "teamInPossession",
                        "phaseOfPlay",
                        "sourceConfidence",
                    ]
                },
                "CalibrationFrame": {"requiredFields": ["frameIndex", "cameraType", "homography"]},
                "TrackFrame": {"requiredFields": ["frameIndex", "trackId", "teamId", "bbox"]},
                "BallActionEvent": {"requiredFields": ["eventId", "frameIndex", "eventType"]},
                "EventStream": {"requiredFields": ["eventId", "timestampMs", "eventType"]},
            },
            "datasetDownloadExecuted": False,
            "externalBenchmarkExecutionReady": False,
        },
    )
    _write_json(
        harness_root / "stage_gate_contract.json",
        {
            "requiredStageCoverage": [
                "camera_shot_gate",
                "calibration",
                "tracking",
                "ball_localization",
                "possession_event_semantics",
                "tactical_reporting",
            ]
        },
    )

    if include_access_review:
        resources = safe_resources
        if resources is None:
            resources = [
                _resource("soccertrack_v2", stages=["tracking", "ball_localization"]),
                _resource("skillcorner_open_data", stages=["calibration", "tracking", "ball_localization"]),
                _resource("statsbomb_open_data_360", stages=["possession_event_semantics", "tactical_reporting"]),
            ]
        _write_json(
            access_root / "external_dataset_access_review_summary.json",
            {
                "batchName": "football_external_dataset_access_review",
                "goalAchieved": True,
                "primaryBlocker": None,
                "safeSourceAdapterSmokeReady": True,
                "datasetDownloadExecuted": access_download_executed,
                "trainingExecuted": False,
                "runtimeDefaultMutationAllowed": False,
                "nextRecommendedNextLever": "football_external_safe_source_adapter_smoke_test",
            },
        )
        _write_json(
            access_root / "approved_smoke_resource_manifest.json",
            {
                "datasetDownloadExecuted": access_download_executed,
                "approvedSmokeResources": resources,
            },
        )

    return candidate_root


def test_safe_source_adapter_smoke_writes_fixture_contract_without_downloads(tmp_path: Path) -> None:
    candidate_root = _write_safe_smoke_inputs(tmp_path)

    payload = safe_smoke.run_football_external_safe_source_adapter_smoke_test(storage_root=tmp_path)

    output_root = candidate_root / "football_external_safe_source_adapter_smoke_test_v1"
    summary = json.loads((output_root / "safe_source_adapter_smoke_summary.json").read_text(encoding="utf-8"))
    schema_audit = json.loads((output_root / "safe_source_adapter_schema_smoke_audit.json").read_text(encoding="utf-8"))
    download_audit = json.loads((output_root / "dataset_download_guardrail_audit.json").read_text(encoding="utf-8"))
    stage_audit = json.loads((output_root / "adapter_stage_coverage_smoke_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["safeSourceAdapterSmokePassed"] is True
    assert payload["safeSmokeResourceCount"] == 3
    assert payload["syntheticFixtureRowCount"] == 3
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_safe_adapter_fixture_implementation"
    assert summary == payload
    assert schema_audit["allSyntheticRowsSatisfySchema"] is True
    assert download_audit["downloadGuardrailPassed"] is True
    assert stage_audit["safeSmokeStageCoverageComplete"] is False
    assert (output_root / "safe_source_adapter_resource_manifest.json").exists()
    assert (output_root / "decision_matrix.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_safe_source_adapter_smoke_blocks_without_access_review(tmp_path: Path) -> None:
    _write_safe_smoke_inputs(tmp_path, include_access_review=False)

    payload = safe_smoke.run_football_external_safe_source_adapter_smoke_test(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_safe_source_adapter_access_review_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"
    assert payload["datasetDownloadExecuted"] is False


def test_safe_source_adapter_smoke_blocks_when_no_approved_resources(tmp_path: Path) -> None:
    _write_safe_smoke_inputs(tmp_path, safe_resources=[])

    payload = safe_smoke.run_football_external_safe_source_adapter_smoke_test(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_safe_source_adapter_no_approved_resources"
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"


def test_safe_source_adapter_smoke_blocks_download_guardrail_violation(tmp_path: Path) -> None:
    _write_safe_smoke_inputs(
        tmp_path,
        access_download_executed=True,
        safe_resources=[_resource("soccertrack_v2", download_allowed=True)],
    )

    payload = safe_smoke.run_football_external_safe_source_adapter_smoke_test(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_safe_source_adapter_download_guardrail_violation"
    assert payload["datasetDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"


def test_safe_source_adapter_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_safe_smoke_inputs(tmp_path)

    payload = safe_smoke.run_football_external_safe_source_adapter_smoke_test(storage_root=tmp_path)

    assert payload["attemptBudget"] == 3
    assert payload["attemptPlanFamilies"] == [
        "safe_source_schema_adapter_smoke",
        "adapter_contract_repair",
        "safe_source_adapter_blocker_summary",
    ]
