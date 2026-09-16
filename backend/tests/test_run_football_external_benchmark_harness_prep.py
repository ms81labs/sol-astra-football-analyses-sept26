from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_harness_prep as prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_summary(storage_root: Path, dirname: str, filename: str, payload: dict[str, object]) -> None:
    _write_json(_candidate_root(storage_root) / dirname / filename, payload)


def _write_inputs(
    storage_root: Path,
    *,
    soccertrack_ready: bool = True,
    soccernet_analysis_ready: bool = True,
    soccernet_event_ready: bool = True,
) -> None:
    common = {
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
    }
    _write_summary(
        storage_root,
        "football_external_soccertrack_lane_closeout_v1",
        "soccertrack_lane_closeout_summary.json",
        {
            **common,
            "batchName": "football_external_soccertrack_lane_closeout",
            "goalAchieved": soccertrack_ready,
            "primaryBlocker": None if soccertrack_ready else "soccertrack_failed",
            "soccertrackLaneClosed": soccertrack_ready,
            "selectedSampleResourceId": "soccertrack_v2",
            "selectedMatchId": "117092",
            "downloadedFixtureFileCount": 11 if soccertrack_ready else 0,
            "reportedEventCount": 3142 if soccertrack_ready else 0,
            "reportedFrameCount": 20 if soccertrack_ready else 0,
        },
    )
    _write_summary(
        storage_root,
        "football_external_soccernet_analysis_product_lane_closeout_v1",
        "analysis_product_lane_closeout_summary.json",
        {
            **common,
            "batchName": "football_external_soccernet_analysis_product_lane_closeout",
            "goalAchieved": soccernet_analysis_ready,
            "primaryBlocker": None if soccernet_analysis_ready else "soccernet_analysis_failed",
            "analysisProductLaneClosed": soccernet_analysis_ready,
            "reportedFrameCount": 146893 if soccernet_analysis_ready else 0,
            "segmentCount": 196 if soccernet_analysis_ready else 0,
        },
    )
    _write_summary(
        storage_root,
        "football_external_soccernet_event_lane_closeout_v1",
        "soccernet_event_lane_closeout_summary.json",
        {
            **common,
            "batchName": "football_external_soccernet_event_lane_closeout",
            "goalAchieved": soccernet_event_ready,
            "primaryBlocker": None if soccernet_event_ready else "soccernet_event_failed",
            "eventOnlyLaneClosed": soccernet_event_ready,
            "eventCount": 1604 if soccernet_event_ready else 0,
            "distinctEventTypeCount": 12 if soccernet_event_ready else 0,
        },
    )


def test_external_benchmark_harness_prep_writes_cross_source_manifest(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = prep.run_football_external_benchmark_harness_prep(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_benchmark_harness_prep_v1"
    source_manifest = json.loads((output_root / "external_benchmark_source_manifest.json").read_text(encoding="utf-8"))
    capability = json.loads((output_root / "external_benchmark_capability_matrix.json").read_text(encoding="utf-8"))
    gaps = json.loads((output_root / "remaining_gap_analysis.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["benchmarkHarnessPrepReady"] is True
    assert payload["externalSourceCount"] == 2
    assert payload["soccertrackReady"] is True
    assert payload["soccernetReady"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_harness_smoke"
    assert source_manifest["schemaVersion"] == "football_external_benchmark_source_manifest_v1"
    assert [row["sourceId"] for row in source_manifest["sources"]] == ["soccernet", "soccertrack"]
    assert capability["crossSourceHarnessReady"] is True
    assert capability["detectorEvaluationReady"] is False
    assert gaps["remainingPrimaryGap"] == "external_benchmark_harness_smoke_not_run"


def test_external_benchmark_harness_prep_blocks_without_soccertrack_lane(tmp_path: Path) -> None:
    _write_inputs(tmp_path, soccertrack_ready=False)

    payload = prep.run_football_external_benchmark_harness_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_harness_source_lane_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_lane_closeout"


def test_external_benchmark_harness_prep_blocks_without_soccernet_analysis_lane(tmp_path: Path) -> None:
    _write_inputs(tmp_path, soccernet_analysis_ready=False)

    payload = prep.run_football_external_benchmark_harness_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_harness_source_lane_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_lane_closeout"


def test_external_benchmark_harness_prep_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = prep.run_football_external_benchmark_harness_prep(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_harness_prep",
        "external_benchmark_harness_source_contract_repair",
        "external_benchmark_harness_prep_blocker_summary",
    ]
