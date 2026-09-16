from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_promoted_runtime_operational_completion_summary as completion
import backend.scripts.run_video_to_analysis_steady_state_monitoring_cycle as steady_state
from backend.tests.test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain import _candidate_root, _seed_route


def test_steady_state_monitoring_cycle_verifies_operational_runtime_health(tmp_path: Path) -> None:
    _seed_route(tmp_path)
    completion.run_video_to_analysis_promoted_runtime_operational_completion_summary(storage_root=tmp_path)

    payload = steady_state.run_video_to_analysis_steady_state_monitoring_cycle(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_steady_state_monitoring_cycle_v1"
    health_audit = json.loads((output_root / "steady_state_monitoring_cycle_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["steadyStateMonitoringCyclePassed"] is True
    assert payload["promotedRuntimeHealthy"] is True
    assert payload["releasedRuntimeVersion"] == "v7.2"
    assert payload["routeSmokePassedCount"] == 5
    assert payload["registryMatchesPromotedV7_2DefaultRuntime"] is True
    assert payload["oldFailingSourceNotViableBlockerDead"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operational_backlog_prioritization"
    assert health_audit["allSteadyStateChecksPassed"] is True
    assert health_audit["guardrailChecks"] == {
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
    }


def test_steady_state_monitoring_cycle_accepts_v7_3_release_archive(tmp_path: Path) -> None:
    _seed_route(tmp_path)
    runtime_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["trainingCandidateVersion"] = "v7.3"
    runtime_path.write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    archive_root = _candidate_root(tmp_path) / "video_to_analysis_release_acceptance_archive_v1"
    archive_root.mkdir(parents=True, exist_ok=True)
    (archive_root / "release_acceptance_archive_summary.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "primaryBlocker": None,
                "videoToAnalysisReleaseAcceptanceArchived": True,
                "currentReleaseFinished": True,
                "activeRuntimeDefaultVersion": "v7.3",
                "trainingExecuted": False,
                "promotionMutationExecuted": False,
                "runtimeDefaultMutationExecuted": True,
                "runtimeDefaultMutationExecutedByThisBatch": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = steady_state.run_video_to_analysis_steady_state_monitoring_cycle(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["steadyStateMonitoringCyclePassed"] is True
    assert payload["releasedRuntimeVersion"] == "v7.3"
    assert payload["registryMatchesActiveDefaultRuntime"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_steady_state_monitoring_cycle_blocks_when_operational_completion_missing(tmp_path: Path) -> None:
    _seed_route(tmp_path)

    payload = steady_state.run_video_to_analysis_steady_state_monitoring_cycle(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_steady_state_operational_completion_missing"
    assert payload["steadyStateMonitoringCyclePassed"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_operational_completion_summary"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
