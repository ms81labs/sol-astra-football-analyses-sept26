from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.run_football_external_benchmark_harness_smoke as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_source_summary(path: Path, source_id: str) -> None:
    if source_id == "soccernet_analysis":
        payload = {
            "batchName": "football_external_soccernet_analysis_product_lane_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "analysisProductLaneClosed": True,
            "reportedFrameCount": 146893,
            "segmentCount": 196,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
        }
    elif source_id == "soccernet_events":
        payload = {
            "batchName": "football_external_soccernet_event_lane_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "eventOnlyLaneClosed": True,
            "eventCount": 1604,
            "distinctEventTypeCount": 12,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
        }
    else:
        payload = {
            "batchName": "football_external_soccertrack_lane_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "soccertrackLaneClosed": True,
            "selectedMatchId": "117092",
            "downloadedFixtureFileCount": 11,
            "reportedEventCount": 3142,
            "reportedFrameCount": 20,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
        }
    _write_json(path, payload)


def _write_prep_inputs(tmp_path: Path, *, missing_source: bool = False) -> Path:
    root = _candidate_root(tmp_path)
    prep_root = root / "football_external_benchmark_harness_prep_v1"
    soccernet_analysis = root / "football_external_soccernet_analysis_product_lane_closeout_v1" / "analysis_product_lane_closeout_summary.json"
    soccernet_events = root / "football_external_soccernet_event_lane_closeout_v1" / "soccernet_event_lane_closeout_summary.json"
    soccertrack = root / "football_external_soccertrack_lane_closeout_v1" / "soccertrack_lane_closeout_summary.json"

    _write_source_summary(soccernet_analysis, "soccernet_analysis")
    if not missing_source:
        _write_source_summary(soccernet_events, "soccernet_events")
    _write_source_summary(soccertrack, "soccertrack")

    _write_json(
        prep_root / "external_benchmark_source_manifest.json",
        {
            "schemaVersion": "football_external_benchmark_source_manifest_v1",
            "sources": [
                {
                    "sourceId": "soccernet",
                    "sourceDataset": "soccernet_external",
                    "sourceLanes": ["analysis_product", "event_lane"],
                    "analysisFrameCount": 146893,
                    "analysisSegmentCount": 196,
                    "eventCount": 1604,
                    "readyForHarnessSmoke": True,
                    "summaryPaths": [str(soccernet_analysis), str(soccernet_events)],
                },
                {
                    "sourceId": "soccertrack",
                    "sourceDataset": "soccertrack_v2",
                    "selectedMatchId": "117092",
                    "downloadedFixtureFileCount": 11,
                    "reportedEventCount": 3142,
                    "reportedFrameCount": 20,
                    "readyForHarnessSmoke": True,
                    "summaryPaths": [str(soccertrack)],
                },
            ],
        },
    )
    _write_json(
        prep_root / "benchmark_harness_readiness_audit.json",
        {
            "summary": {
                "goalAchieved": True,
                "primaryBlocker": None,
                "benchmarkHarnessPrepReady": True,
                "benchmarkHarnessContractReady": True,
                "externalSourceCount": 2,
                "soccernetReady": True,
                "soccertrackReady": True,
                "trainingExecuted": False,
                "promotionReady": False,
                "candidateReadyForEvaluation": False,
                "runtimeDefaultMutationExecuted": False,
            }
        },
    )
    _write_json(
        prep_root / "stage_gate_contract.json",
        {
            "schemaVersion": "football_external_benchmark_stage_gate_contract_v2",
            "requiredStageCoverage": [
                "source_manifest_load",
                "artifact_presence_check",
                "schema_version_check",
                "metric_family_mapping",
                "no_training_or_runtime_mutation",
            ],
        },
    )
    _write_json(
        prep_root / "dataset_adapter_contract.json",
        {
            "schemaVersion": "football_external_benchmark_adapter_contract_v2",
            "externalBenchmarkExecutionReady": False,
            "datasetDownloadExecuted": False,
            "schemas": {
                "ExternalBenchmarkSmokeCase": {
                    "requiredFields": ["sourceId", "caseId", "artifactPath", "expectedMetricFamilies"],
                }
            },
        },
    )
    return root


def test_external_benchmark_harness_smoke_writes_cross_source_cases(tmp_path: Path) -> None:
    root = _write_prep_inputs(tmp_path)

    payload = smoke.run_football_external_benchmark_harness_smoke(storage_root=tmp_path)

    output_root = root / "football_external_benchmark_harness_smoke_v1"
    cases = json.loads((output_root / "benchmark_smoke_case_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((output_root / "cross_source_metric_family_smoke.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["externalBenchmarkHarnessSmokePassed"] is True
    assert payload["smokeCaseCount"] == 2
    assert payload["externalBenchmarkExecutionReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_execution_approval"
    assert [row["sourceId"] for row in cases["smokeCases"]] == ["soccernet", "soccertrack"]
    assert metrics["metricFamilyCoveragePassed"] is True
    assert metrics["metricFamilies"] == ["analysis_product_surface", "event_semantics"]


def test_external_benchmark_harness_smoke_blocks_without_prep_manifest(tmp_path: Path) -> None:
    payload = smoke.run_football_external_benchmark_harness_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_harness_prep_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_harness_prep"


def test_external_benchmark_harness_smoke_blocks_missing_source_artifact(tmp_path: Path) -> None:
    _write_prep_inputs(tmp_path, missing_source=True)

    payload = smoke.run_football_external_benchmark_harness_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_harness_source_artifact_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_harness_source_contract_repair"


def test_external_benchmark_harness_smoke_has_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_prep_inputs(tmp_path)

    payload = smoke.run_football_external_benchmark_harness_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_harness_smoke",
        "external_benchmark_harness_smoke_contract_repair",
        "external_benchmark_harness_smoke_blocker_summary",
    ]
