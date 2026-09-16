from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_dataset_access_review as access_review


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _resource(resource_id: str, *, access_class: str = "open_data", stages: list[str] | None = None) -> dict[str, object]:
    return {
        "resourceId": resource_id,
        "resourceName": resource_id.replace("_", " ").title(),
        "accessClass": access_class,
        "licenseReviewStatus": "requires_current_manual_verification",
        "executionStatus": "not_downloaded",
        "evidenceOnlyUntilReviewed": True,
        "coveredStages": stages or ["tracking", "ball_localization"],
        "adapterPriority": 1,
    }


def _write_access_review_inputs(
    tmp_path: Path,
    *,
    include_harness: bool = True,
    include_closeout: bool = True,
    resources: list[dict[str, object]] | None = None,
) -> dict[str, Path]:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    harness_root = candidate_root / "football_external_benchmark_harness_prep_v1"
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"

    if include_harness:
        resource_rows = resources if resources is not None else [
            _resource("soccertrack_v2", access_class="open_research_dataset", stages=["tracking", "ball_localization", "possession_event_semantics", "tactical_reporting"]),
            _resource("soccernet_broadcast_tasks", access_class="research_gated", stages=["camera_shot_gate", "calibration", "tracking", "ball_localization", "possession_event_semantics"]),
            _resource("skillcorner_open_data", access_class="open_data", stages=["calibration", "tracking", "ball_localization", "possession_event_semantics", "tactical_reporting"]),
            _resource("metrica_sample_data", access_class="sample_data", stages=["tracking", "ball_localization", "possession_event_semantics", "tactical_reporting"]),
            _resource("statsbomb_open_data_360", access_class="open_event_data", stages=["possession_event_semantics", "tactical_reporting"]),
        ]
        _write_json(
            harness_root / "external_benchmark_harness_summary.json",
            {
                "batchName": "football_external_benchmark_harness_prep",
                "goalAchieved": True,
                "primaryBlocker": None,
                "benchmarkHarnessContractReady": True,
                "datasetAccessReviewReady": True,
                "datasetDownloadExecuted": False,
                "externalBenchmarkExecutionReady": False,
                "nextRecommendedNextLever": "football_external_dataset_access_review",
                "trainingExecuted": False,
                "runtimeDefaultMutationAllowed": False,
            },
        )
        _write_json(
            harness_root / "benchmark_resource_inventory.json",
            {
                "resourceCount": len(resource_rows),
                "licensePolicy": "All external source license/access terms must be manually verified before download.",
                "resources": resource_rows,
            },
        )
        _write_json(
            harness_root / "dataset_adapter_contract.json",
            {"externalBenchmarkExecutionReady": False, "datasetDownloadExecuted": False, "schemas": {"FrameState": {}}},
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

    if include_closeout:
        _write_json(
            suite_root / "v7_2_runtime_default_rollout_closeout_v1" / "runtime_default_rollout_closeout_summary.json",
            {
                "batchName": "v7_2_runtime_default_rollout_closeout",
                "goalAchieved": True,
                "primaryBlocker": None,
                "runtimeDefaultRolloutClosed": True,
                "activeFailingSourceNotViableBlockerPresent": False,
                "historicalSuiteBlockerArchived": True,
                "nextRecommendedNextLever": "football_external_dataset_access_review",
            },
        )

    return {"candidateRoot": candidate_root, "harnessRoot": harness_root, "suiteRoot": suite_root}


def test_access_review_selects_safe_adapter_smoke_and_blocks_gated_downloads(tmp_path: Path) -> None:
    paths = _write_access_review_inputs(tmp_path)

    payload = access_review.run_football_external_dataset_access_review(storage_root=tmp_path)

    output_root = paths["candidateRoot"] / "football_external_dataset_access_review_v1"
    decisions = json.loads((output_root / "dataset_access_decision_matrix.json").read_text(encoding="utf-8"))
    smoke_manifest = json.loads((output_root / "approved_smoke_resource_manifest.json").read_text(encoding="utf-8"))
    gated_audit = json.loads((output_root / "manual_or_gated_access_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["safeSourceAdapterSmokeReady"] is True
    assert payload["fullExternalBenchmarkExecutionReady"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_adapter_smoke_test"
    assert {row["resourceId"] for row in smoke_manifest["approvedSmokeResources"]} == {
        "soccertrack_v2",
        "skillcorner_open_data",
        "statsbomb_open_data_360",
    }
    assert "soccernet_broadcast_tasks" in {row["resourceId"] for row in gated_audit["manualOrGatedResources"]}
    assert "metrica_sample_data" in {row["resourceId"] for row in gated_audit["manualOrGatedResources"]}
    assert decisions["resourceDecisionCounts"]["approved_smoke_only"] == 3


def test_access_review_fails_closed_without_harness_prep(tmp_path: Path) -> None:
    _write_access_review_inputs(tmp_path, include_harness=False)

    payload = access_review.run_football_external_dataset_access_review(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_dataset_access_harness_prep_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_harness_prep"
    assert payload["datasetDownloadExecuted"] is False


def test_access_review_requires_runtime_rollout_closeout(tmp_path: Path) -> None:
    _write_access_review_inputs(tmp_path, include_closeout=False)

    payload = access_review.run_football_external_dataset_access_review(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_dataset_access_runtime_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_default_rollout_closeout"
    assert payload["datasetDownloadExecuted"] is False


def test_access_review_routes_no_safe_resources_to_manual_access_setup(tmp_path: Path) -> None:
    _write_access_review_inputs(
        tmp_path,
        resources=[
            _resource("soccernet_broadcast_tasks", access_class="research_gated"),
            _resource("metrica_sample_data", access_class="sample_data"),
        ],
    )

    payload = access_review.run_football_external_dataset_access_review(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_dataset_access_no_safe_smoke_resources"
    assert payload["nextRecommendedNextLever"] == "football_external_manual_dataset_access_setup"
    assert payload["safeSourceAdapterSmokeReady"] is False


def test_access_review_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_access_review_inputs(tmp_path)

    payload = access_review.run_football_external_dataset_access_review(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_dataset_access_license_review",
        "dataset_access_contract_repair",
        "external_dataset_access_blocker_summary",
    ]
