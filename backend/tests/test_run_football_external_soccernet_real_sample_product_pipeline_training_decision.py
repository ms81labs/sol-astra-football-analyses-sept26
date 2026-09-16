from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_real_sample_product_pipeline_training_decision as decision


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_inputs(
    storage_root: Path,
    *,
    report_ready: bool = True,
    sample_ready: bool = True,
    product_ready: bool = True,
    miss_count: int = 0,
) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root
        / "football_external_soccernet_bounded_product_validation_report_binding_v1"
        / "soccernet_bounded_product_validation_report_binding_summary.json",
        {
            "goalAchieved": report_ready,
            "primaryBlocker": None if report_ready else "football_external_soccernet_bounded_product_validation_execution_gap",
            "reportBindingReady": report_ready,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    video_path = (
        root
        / "football_external_soccernet_video_member_extract_v1"
        / "extracted_video"
        / "england_efl"
        / "2019-2020"
        / "fixture"
        / "224p.mp4"
    )
    if sample_ready:
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake-mp4-bytes")
    _write_json(
        root / "football_external_soccernet_video_member_extract_v1" / "extracted_video_member_inventory.json",
        {
            "archiveDownloadExecuted": False,
            "extractedVideoFileCount": 1 if sample_ready else 0,
            "extractedVideoFiles": [
                {
                    "relativePath": str(video_path.relative_to(root / "football_external_soccernet_video_member_extract_v1")),
                    "memberPath": "england_efl/2019-2020/fixture/224p.mp4",
                    "sizeBytes": len(b"fake-mp4-bytes"),
                    "sha256": "test-sha",
                    "mp4FtypPresent": True,
                }
            ]
            if sample_ready
            else [],
        },
    )
    label_path = (
        root
        / "football_external_soccernet_zip_label_member_extract_v1"
        / "extracted_labels"
        / "england_efl"
        / "2019-2020"
        / "fixture"
        / "Labels-ball.json"
    )
    if sample_ready:
        _write_json(label_path, {"annotations": [{"label": "PASS", "position": "1000"}]})
    _write_json(
        root / "football_external_soccernet_full_analysis_execution_v1" / "full_analysis_execution_summary.json",
        {
            "goalAchieved": product_ready,
            "primaryBlocker": None if product_ready else "football_external_soccernet_full_analysis_video_open_failed",
            "fullAnalysisExecutionExecuted": product_ready,
            "processedFrameCount": 146893 if product_ready else 0,
            "reportedFrameCount": 146893 if product_ready else 0,
            "unreadableFrameCount": 0,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        root / "football_external_soccernet_analysis_product_api_smoke_v1" / "analysis_product_api_smoke_summary.json",
        {
            "goalAchieved": product_ready,
            "primaryBlocker": None if product_ready else "football_external_soccernet_analysis_product_api_contract_gap",
            "productApiSmokePassed": product_ready,
            "reportedFrameCount": 146893 if product_ready else 0,
            "segmentCount": 196 if product_ready else 0,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    if miss_count:
        _write_json(
            root / "football_external_soccernet_detector_miss_capture_v1" / "detector_miss_capture_summary.json",
            {
                "goalAchieved": True,
                "primaryBlocker": None,
                "realDetectorMissCount": miss_count,
                "reviewedRealMissPositiveCount": miss_count,
                "trainingExecuted": False,
                "promotionMutationExecuted": False,
                "runtimeDefaultMutationExecuted": False,
            },
        )


def test_decision_binds_real_sample_and_blocks_training_without_real_misses(tmp_path: Path) -> None:
    _seed_inputs(tmp_path)

    payload = decision.run_football_external_soccernet_real_sample_product_pipeline_training_decision(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_real_sample_product_pipeline_training_decision_v1"
    sample_audit = json.loads((output_root / "controlled_real_sample_materialization_audit.json").read_text(encoding="utf-8"))
    training_audit = json.loads((output_root / "detector_training_need_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["controlledRealSampleMaterialized"] is True
    assert payload["actualProductPipelinePassed"] is True
    assert payload["detectorTrainingNeededFromEvidence"] is False
    assert payload["v7_3TrainingDataReady"] is False
    assert payload["v7_3RetrainExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_detector_miss_capture_and_label_queue"
    assert sample_audit["sampleVideoExists"] is True
    assert training_audit["trainingDecision"] == "not_justified_yet_no_real_detector_miss_truth"


def test_decision_routes_to_v7_3_manifest_when_reviewed_real_misses_exist(tmp_path: Path) -> None:
    _seed_inputs(tmp_path, miss_count=18)

    payload = decision.run_football_external_soccernet_real_sample_product_pipeline_training_decision(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["detectorTrainingNeededFromEvidence"] is True
    assert payload["realDetectorMissCount"] == 18
    assert payload["v7_3TrainingDataReady"] is True
    assert payload["v7_3RetrainExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_training_manifest_prep_from_soccernet_real_misses"


def test_decision_blocks_when_sample_is_missing(tmp_path: Path) -> None:
    _seed_inputs(tmp_path, sample_ready=False)

    payload = decision.run_football_external_soccernet_real_sample_product_pipeline_training_decision(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_real_sample_materialization_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_real_sample_download_execution"


def test_decision_blocks_when_product_pipeline_is_missing(tmp_path: Path) -> None:
    _seed_inputs(tmp_path, product_ready=False)

    payload = decision.run_football_external_soccernet_real_sample_product_pipeline_training_decision(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_product_pipeline_execution_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_execution"


def test_decision_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _seed_inputs(tmp_path)

    payload = decision.run_football_external_soccernet_real_sample_product_pipeline_training_decision(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_real_sample_product_pipeline_training_decision",
        "soccernet_real_sample_materialization_or_pipeline_repair",
        "soccernet_training_decision_blocker_summary",
    ]
