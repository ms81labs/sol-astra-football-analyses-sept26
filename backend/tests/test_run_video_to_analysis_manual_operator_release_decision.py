from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_manual_operator_release_decision as decision


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _false_guardrails() -> dict[str, bool]:
    return {
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "promotionReady": False,
        "runtimeDefaultMutationAllowed": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
    }


def _seed_decision_surface(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_current_release_acceptance_decision_surface_v2"
    payload = {
        "batchName": "video_to_analysis_current_release_acceptance_decision_surface",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": None,
        "releasedRuntimeVersion": "v7.3",
        "activeRuntimeDefaultVersion": "v7.3",
        "currentReleaseFinished": True,
        "sourcePoolCycleStillPresent": True,
        "recommendedStrategicChoice": "manual_operator_release_decision",
        "nextRecommendedNextLever": "manual_operator_release_decision_required",
        "growthLaneClosedAtVersion": 110,
        "growthLaneClosedAtSnapshotDir": "video_to_analysis_next_sample_selection_snapshot_v110",
        **_false_guardrails(),
    }
    _write_json(root / "current_release_acceptance_decision_surface_summary.json", payload)
    _write_json(
        root / "current_operator_decision_model.json",
        {
            "currentState": "current_release_done_optional_coverage_loop",
            "releasedRuntimeVersion": "v7.3",
            "recommendedStrategicChoice": "manual_operator_release_decision",
            "recommendedNextLever": "manual_operator_release_decision_required",
            "availableStrategicChoices": [
                "declare_current_milestone_done",
                "resume_source_pool_replenishment_as_optional_coverage",
            ],
        },
    )


def test_manual_operator_release_decision_declares_current_milestone_done(tmp_path: Path) -> None:
    _seed_decision_surface(tmp_path)

    payload = decision.run_video_to_analysis_manual_operator_release_decision(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_manual_operator_release_decision_v1"
    closeout = json.loads((output_root / "current_milestone_closeout.json").read_text(encoding="utf-8"))
    next_choices = json.loads((output_root / "manual_next_choices.json").read_text(encoding="utf-8"))
    readout = (output_root / "operator_release_decision_readout.md").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["operatorDecisionRecorded"] is True
    assert payload["selectedOperatorDecision"] == "declare_current_milestone_done"
    assert payload["v7_3CurrentMilestoneDeclaredDone"] is True
    assert payload["optionalCoverageLoopDeferred"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_current_milestone_done"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert closeout["releasedRuntimeVersion"] == "v7.3"
    assert closeout["sourcePoolCycleDisposition"] == "deferred_optional_coverage"
    assert next_choices["operatorChoices"][0]["id"] == "keep_current_milestone_done"
    assert "v7.3 current milestone is declared done" in readout


def test_manual_operator_release_decision_blocks_without_decision_surface(tmp_path: Path) -> None:
    payload = decision.run_video_to_analysis_manual_operator_release_decision(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_manual_operator_release_decision_surface_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_current_release_acceptance_decision_surface"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
