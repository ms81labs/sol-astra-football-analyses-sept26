from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_promoted_runtime_release_closeout as closeout
import backend.scripts.run_video_to_analysis_release_completion_summary as completion


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_operator_acceptance(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root
        / "video_to_analysis_promoted_runtime_operator_acceptance_trial_v1"
        / "promoted_runtime_operator_acceptance_trial_summary.json",
        {
            "batchName": "video_to_analysis_promoted_runtime_operator_acceptance_trial",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "promotedRuntimeOperatorAcceptancePassed": True,
            "registryMatchesPromotedV7_2DefaultRuntime": True,
            "operatorVisibleRouteSmokePassed": True,
            "routeSmokePassedCount": 5,
            "detectorEvaluationExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateReadyForEvaluation": False,
            "nextRecommendedNextLever": "video_to_analysis_promoted_runtime_release_closeout",
        },
    )
    _write_json(
        root
        / "video_to_analysis_promoted_runtime_operator_acceptance_trial_v1"
        / "promoted_runtime_registry_audit.json",
        {
            "registryMatchesPromotedV7_2DefaultRuntime": True,
            "checks": {
                "candidateNameMatches": True,
                "candidateVersionMatches": True,
                "runtimeUseDefault": True,
                "postRuntimeDefaultSourceRobustnessValidated": True,
            },
        },
    )
    _write_json(
        root
        / "video_to_analysis_promoted_runtime_operator_acceptance_trial_v1"
        / "operator_visible_route_smoke_audit.json",
        {
            "operatorVisibleRouteSmokePassed": True,
            "routeSmokePassedCount": 5,
            "routeSmokes": [
                {"id": "finish_line", "routeSmokePassed": True},
                {"id": "acceptance_report", "routeSmokePassed": True},
                {"id": "operator_handoff", "routeSmokePassed": True},
                {"id": "detector_evaluation_report", "routeSmokePassed": True},
                {"id": "promotion_review", "routeSmokePassed": True},
            ],
        },
    )


def _seed_release_closeout(storage_root: Path) -> None:
    _seed_operator_acceptance(storage_root)
    closeout.run_video_to_analysis_promoted_runtime_release_closeout(storage_root=storage_root)


def test_promoted_runtime_release_closeout_passes_from_operator_acceptance(tmp_path: Path) -> None:
    _seed_operator_acceptance(tmp_path)

    payload = closeout.run_video_to_analysis_promoted_runtime_release_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_promoted_runtime_release_closeout_v1"
    release_manifest = json.loads((output_root / "promoted_runtime_release_manifest.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["promotedRuntimeReleaseClosed"] is True
    assert payload["promotedRuntimeOperatorAcceptancePassed"] is True
    assert payload["routeSmokePassedCount"] == 5
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_completion_summary"
    assert release_manifest["releasedRuntime"]["trainingCandidateVersion"] == "v7.2"


def test_promoted_runtime_release_closeout_blocks_without_operator_acceptance(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_promoted_runtime_release_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_promoted_runtime_operator_acceptance_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_operator_acceptance_trial"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_release_completion_summary_selects_promoted_runtime_monitoring(tmp_path: Path) -> None:
    _seed_release_closeout(tmp_path)

    payload = completion.run_video_to_analysis_release_completion_summary(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_release_completion_summary_v1"
    completion_manifest = json.loads((output_root / "release_completion_manifest.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoToAnalysisPromotedRuntimeReleaseComplete"] is True
    assert payload["releasedRuntimeVersion"] == "v7.2"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_post_release_monitoring_plan"
    assert completion_manifest["nextOperatingMode"] == "post_release_monitoring"
