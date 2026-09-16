from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_4_training_decision_from_real_misses as decision


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_walkthrough(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
        / "video_to_analysis_upload_to_analysis_walkthrough_v1"
        / "upload_to_analysis_walkthrough_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "uploadToAnalysisWalkthroughReady": True,
        },
    )


def _seed_release_context(storage_root: Path, *, unresolved: int = 0, reviewed: int = 0) -> None:
    root = _candidate_root(storage_root)
    _seed_walkthrough(storage_root)
    _write_json(
        root / "football_external_soccernet_detector_miss_manual_review_resolution_v1" / "detector_miss_manual_review_resolution_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "unresolvedNewMissCount": unresolved,
            "newReviewedPositiveSourceCount": reviewed,
        },
    )
    _write_json(
        root / "v7_3_training_manifest_prep_from_soccernet_real_misses_v1" / "v7_3_training_manifest_prep_summary.json",
        {"goalAchieved": True, "primaryBlocker": None},
    )
    _write_json(
        root / "v7_3_promotion_readiness_validation_v1" / "v7_3_promotion_readiness_summary.json",
        {"goalAchieved": True, "primaryBlocker": None},
    )
    _write_json(
        root / "video_to_analysis_release_acceptance_archive_v1" / "release_acceptance_archive_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "currentReleaseFinished": True},
    )


def test_v7_4_training_decision_defers_without_new_real_miss_pressure(tmp_path: Path) -> None:
    _seed_release_context(tmp_path)

    payload = decision.run_v7_4_training_decision_from_real_misses(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "v7_4_training_decision_from_real_misses_v1"
    decision_payload = json.loads((output_root / "v7_4_training_decision.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["v7_4TrainingNeeded"] is False
    assert payload["trainingDeferred"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_retention_and_artifact_hygiene"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert decision_payload["v7_4TrainingNeeded"] is False


def test_v7_4_training_decision_routes_to_miss_capture_when_real_misses_accumulate(tmp_path: Path) -> None:
    _seed_release_context(tmp_path, unresolved=21, reviewed=24)

    payload = decision.run_v7_4_training_decision_from_real_misses(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["v7_4TrainingNeeded"] is True
    assert payload["trainingDeferred"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_detector_miss_capture_and_label_queue"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_v7_4_training_decision_blocks_without_walkthrough(tmp_path: Path) -> None:
    payload = decision.run_v7_4_training_decision_from_real_misses(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_4_training_decision_upload_walkthrough_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_upload_to_analysis_walkthrough"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
