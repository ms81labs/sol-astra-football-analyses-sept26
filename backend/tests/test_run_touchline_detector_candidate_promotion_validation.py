from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.run_touchline_detector_candidate_promotion_validation as run_touchline_detector_candidate_promotion_validation


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_suite_root(tmp_path: Path, *, next_lever: str = "promote_touchline_detector_candidate") -> Path:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    suite_root.mkdir(parents=True, exist_ok=True)
    suite_summary = {
        "suiteName": "frozen-viable-baseline-slice-suite",
        "suiteVerdict": "baseline_not_robust",
        "sourceRobustnessOutcome": "source_robustness_partial",
        "sourceRobustnessRecommendedNextLever": next_lever,
        "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
    }
    active_lane_snapshot = {"generatedAt": "2026-04-23T20:19:32+00:00"}
    robustness_diagnosis = {
        "generatedAt": "2026-04-23T20:18:53+00:00",
        "sourceRobustnessRecommendedNextLever": next_lever,
    }
    (suite_root / "suite_summary.json").write_text(json.dumps(suite_summary, indent=2), encoding="utf-8")
    (suite_root / "active_lane_snapshot.json").write_text(
        json.dumps(active_lane_snapshot, indent=2), encoding="utf-8"
    )
    (suite_root / "suite_robustness_diagnosis.json").write_text(
        json.dumps(robustness_diagnosis, indent=2), encoding="utf-8"
    )
    return suite_root


def _write_candidate_root(
    tmp_path: Path,
    *,
    candidate_name: str = "touchline_detector_candidate_v6",
    ready_for_promotion: bool = True,
    candidate_baseline_product_beats_plateau: bool = True,
    baseline_control_proof_ran: bool = True,
    candidate_beats_same_batch_baseline_control: bool = True,
    goal_achieved: bool = True,
    roadmap_advance_allowed: bool = True,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / candidate_name
    weights_root = candidate_root / "weights"
    evaluation_root = candidate_root / "evaluation_v1"
    weights_root.mkdir(parents=True, exist_ok=True)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    best_path = weights_root / "best.pt"
    best_path.write_bytes(b"best")
    (weights_root / "last.pt").write_bytes(b"last")
    (candidate_root / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": candidate_name,
                "trainingBatchName": "touchline_detector_candidate_v5_proposal_signal_generation_fix_v1",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "readyForDetectorEvaluation": True,
                "bestWeightsPath": str(best_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (candidate_root / "evaluation_contract.json").write_text(
        json.dumps(
            {
                "candidateReadyForEvaluation": True,
                "activeFrozenBaseline": {
                    "detectorModelPath": "yolov10n.pt",
                    "primaryMode": "anchored_player_ranked_context_960",
                    "cleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
                },
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (evaluation_root / "evaluation_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": candidate_name,
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v6",
                "readyForPromotion": ready_for_promotion,
                "candidateBaselineProductBeatsPlateau": candidate_baseline_product_beats_plateau,
                "baselineControlProofRan": baseline_control_proof_ran,
                "candidateBeatsSameBatchBaselineControl": candidate_beats_same_batch_baseline_control,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (evaluation_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": goal_achieved,
                "roadmapAdvanceAllowed": roadmap_advance_allowed,
                "readyForPromotion": ready_for_promotion,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return candidate_root


def test_run_touchline_detector_candidate_promotion_validation_writes_expected_artifacts(tmp_path: Path) -> None:
    _write_suite_root(tmp_path)
    candidate_root = _write_candidate_root(tmp_path)

    payload = run_touchline_detector_candidate_promotion_validation.run_touchline_detector_candidate_promotion_validation(
        storage_root=tmp_path,
        candidate_name="touchline_detector_candidate_v6",
    )

    promotion_root = candidate_root / "promotion_v1"
    promotion_summary = _load_json(promotion_root / "promotion_summary.json")
    batch_outcome = _load_json(promotion_root / "batch_outcome_analysis.json")
    suite_promotion = _load_json(
        tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite" / "detector_candidate_promotion.json"
    )
    runtime_registry = _load_json(tmp_path / "runtime" / "promoted_touchline_detector_candidate.json")

    assert payload["promotionValidated"] is True
    assert promotion_summary["promotedForControlledRuns"] is True
    assert promotion_summary["runtimeDefaultChanged"] is False
    assert promotion_summary["runtimeDefaultChangeAllowed"] is False
    assert promotion_summary["runtimeDefaultChangeBlockers"] == ["failing_source_not_viable"]
    assert batch_outcome["goalAchieved"] is True
    assert suite_promotion["trainingCandidateName"] == "touchline_detector_candidate_v6"
    assert suite_promotion["runtimeContract"]["auxiliaryBallModelProfile"] == "ball_probe_only_v1"
    assert runtime_registry["runtimeDefaultChanged"] is False
    assert runtime_registry["sourceRobustnessRecommendedNextLever"] == "promote_touchline_detector_candidate"


@pytest.mark.parametrize(
    ("summary_overrides", "batch_overrides", "suite_next_lever", "expected_blocker"),
    [
        ({"readyForPromotion": False}, {}, "promote_touchline_detector_candidate", "candidate_not_ready_for_promotion"),
        ({}, {"goalAchieved": False}, "promote_touchline_detector_candidate", "evaluation_goal_not_achieved"),
        ({}, {}, "evaluate_touchline_detector_candidate", "suite_active_lane_not_pinned_to_promotion"),
        (
            {"baselineControlProofRan": False},
            {},
            "promote_touchline_detector_candidate",
            "baseline_control_proof_not_run",
        ),
    ],
)
def test_run_touchline_detector_candidate_promotion_validation_blocks_invalid_inputs(
    tmp_path: Path,
    summary_overrides: dict[str, object],
    batch_overrides: dict[str, object],
    suite_next_lever: str,
    expected_blocker: str,
) -> None:
    _write_suite_root(tmp_path, next_lever=suite_next_lever)
    candidate_root = _write_candidate_root(tmp_path)

    evaluation_summary_path = candidate_root / "evaluation_v1" / "evaluation_summary.json"
    evaluation_summary = _load_json(evaluation_summary_path)
    evaluation_summary.update(summary_overrides)
    evaluation_summary_path.write_text(json.dumps(evaluation_summary, indent=2), encoding="utf-8")

    batch_outcome_path = candidate_root / "evaluation_v1" / "batch_outcome_analysis.json"
    batch_outcome = _load_json(batch_outcome_path)
    batch_outcome.update(batch_overrides)
    batch_outcome_path.write_text(json.dumps(batch_outcome, indent=2), encoding="utf-8")

    payload = run_touchline_detector_candidate_promotion_validation.run_touchline_detector_candidate_promotion_validation(
        storage_root=tmp_path,
        candidate_name="touchline_detector_candidate_v6",
    )

    assert payload["promotionValidated"] is False
    assert expected_blocker in payload["promotionValidationBlockers"]
