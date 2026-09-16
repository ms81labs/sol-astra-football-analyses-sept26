from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_lane_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_summary(storage_root: Path, dirname: str, filename: str, payload: dict[str, object]) -> None:
    _write_json(_candidate_root(storage_root) / dirname / filename, payload)


def _write_lane_inputs(storage_root: Path, *, product_lane_ready: bool = True, missing_bridge: bool = False) -> None:
    base_payload = {
        "goalAchieved": True,
        "primaryBlocker": None,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
    }
    _write_summary(
        storage_root,
        "football_external_soccertrack_google_drive_fixture_access_probe_v1",
        "google_drive_fixture_access_probe_summary.json",
        {
            **base_payload,
            "batchName": "football_external_soccertrack_google_drive_fixture_access_probe",
            "selectedMatchId": "117092",
            "completeFixtureCandidateCount": 10,
            "listedFileCount": 155,
        },
    )
    _write_summary(
        storage_root,
        "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1",
        "google_drive_bounded_fixture_fetch_summary.json",
        {
            **base_payload,
            "batchName": "football_external_soccertrack_google_drive_bounded_fixture_fetch",
            "selectedMatchId": "117092",
            "downloadedFixtureFileCount": 11,
            "videoDownloadExecuted": False,
        },
    )
    _write_summary(
        storage_root,
        "football_external_soccertrack_sample_fixture_materialization_v1",
        "soccertrack_sample_fixture_materialization_summary.json",
        {**base_payload, "batchName": "football_external_soccertrack_sample_fixture_materialization", "selectedMatchId": "117092", "materializedFixtureReady": True},
    )
    _write_summary(
        storage_root,
        "football_external_soccertrack_adapter_smoke_test_v1",
        "soccertrack_adapter_smoke_summary.json",
        {**base_payload, "batchName": "football_external_soccertrack_adapter_smoke_test", "selectedMatchId": "117092", "canonicalExternalFixtureReady": True},
    )
    if not missing_bridge:
        _write_summary(
            storage_root,
            "football_external_soccertrack_match_bundle_bridge_smoke_v1",
            "soccertrack_match_bundle_bridge_summary.json",
            {**base_payload, "batchName": "football_external_soccertrack_match_bundle_bridge_smoke", "selectedMatchId": "117092", "matchBundleBridgeReady": True, "externalBundleEventCount": 3142, "externalBundleFrameCount": 20},
        )
    _write_summary(
        storage_root,
        "football_external_soccertrack_product_route_smoke_v1",
        "soccertrack_product_route_smoke_summary.json",
        {**base_payload, "batchName": "football_external_soccertrack_product_route_smoke", "selectedMatchId": "117092", "productRouteSmokePassed": True, "externalBundleEventCount": 3142, "externalBundleFrameCount": 20},
    )
    _write_summary(
        storage_root,
        "football_external_soccertrack_analysis_report_smoke_v1",
        "soccertrack_analysis_report_smoke_summary.json",
        {**base_payload, "batchName": "football_external_soccertrack_analysis_report_smoke", "selectedMatchId": "117092", "analysisReportSmokePassed": True, "reportedEventCount": 3142, "reportedFrameCount": 20},
    )
    _write_summary(
        storage_root,
        "football_external_soccertrack_analysis_product_ui_binding_v1",
        "analysis_product_ui_binding_summary.json",
        {**base_payload, "batchName": "football_external_soccertrack_analysis_product_ui_binding", "selectedMatchId": "117092", "productUiBindingReady": True, "reportedEventCount": 3142, "reportedFrameCount": 20},
    )
    _write_summary(
        storage_root,
        "football_external_soccertrack_analysis_product_ui_route_implementation_v1",
        "analysis_product_ui_route_implementation_summary.json",
        {**base_payload, "batchName": "football_external_soccertrack_analysis_product_ui_route_implementation", "selectedMatchId": "117092", "productUiRouteReady": True, "reportedEventCount": 3142, "reportedFrameCount": 20},
    )
    _write_summary(
        storage_root,
        "football_external_soccertrack_analysis_product_lane_closeout_v1",
        "analysis_product_lane_closeout_summary.json",
        {
            **base_payload,
            "batchName": "football_external_soccertrack_analysis_product_lane_closeout",
            "goalAchieved": product_lane_ready,
            "primaryBlocker": None if product_lane_ready else "product_lane_failed",
            "selectedMatchId": "117092",
            "analysisProductLaneClosed": product_lane_ready,
            "productUiRouteReady": product_lane_ready,
            "reportedEventCount": 3142 if product_lane_ready else 0,
            "reportedFrameCount": 20 if product_lane_ready else 0,
        },
    )


def test_soccertrack_lane_closeout_summarizes_full_external_lane_and_selects_benchmark_prep(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path)

    payload = closeout.run_football_external_soccertrack_lane_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_soccertrack_lane_closeout_v1"
    capability = json.loads((output_root / "soccertrack_lane_capability_matrix.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_root / "soccertrack_lane_evidence_index.json").read_text(encoding="utf-8"))
    gaps = json.loads((output_root / "remaining_gap_analysis.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["soccertrackLaneClosed"] is True
    assert payload["selectedMatchId"] == "117092"
    assert payload["downloadedFixtureFileCount"] == 11
    assert payload["reportedEventCount"] == 3142
    assert payload["reportedFrameCount"] == 20
    assert payload["productRouteReady"] is True
    assert payload["analysisProductLaneClosed"] is True
    assert payload["videoDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_harness_prep"
    assert capability["googleDriveFixturePathReady"] is True
    assert capability["matchBundleRouteReady"] is True
    assert capability["analysisProductRouteReady"] is True
    assert capability["trainingReady"] is False
    assert len(evidence["requiredEvidence"]) == 10
    assert gaps["remainingPrimaryGap"] == "benchmark_harness_not_yet_bound_to_external_sources"


def test_soccertrack_lane_closeout_blocks_when_required_evidence_missing(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path, missing_bridge=True)

    payload = closeout.run_football_external_soccertrack_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_lane_required_evidence_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_match_bundle_bridge_smoke"


def test_soccertrack_lane_closeout_blocks_when_product_lane_not_closed(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path, product_lane_ready=False)

    payload = closeout.run_football_external_soccertrack_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_analysis_product_lane_not_closed"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_analysis_product_lane_closeout"


def test_soccertrack_lane_closeout_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path)

    payload = closeout.run_football_external_soccertrack_lane_closeout(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_external_lane_closeout",
        "soccertrack_lane_closeout_evidence_repair",
        "soccertrack_lane_closeout_blocker_summary",
    ]
