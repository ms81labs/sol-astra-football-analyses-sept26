from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_release_acceptance_archive as archive


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_reconciliation(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
        / "video_to_analysis_roadmap_state_reconciliation_v1"
        / "roadmap_state_reconciliation_summary.json",
        {
            "batchName": "video_to_analysis_roadmap_state_reconciliation",
            "goalAchieved": True,
            "primaryBlocker": None,
            "manualStrategicSentinelResolved": True,
            "runtimeDefaultV7_3Active": True,
            "releaseCandidateClosed": True,
            "productLaneClosed": True,
            "postReleaseMonitoringClosed": True,
            "detectorEvaluationLaneClosed": True,
            "growthLaneClosedManualChoice": True,
            "activeRuntimeDefaultVersion": "v7.3",
            "runtimeDefaultMutationExecuted": True,
            "nextRecommendedNextLever": "video_to_analysis_release_acceptance_archive",
        },
    )
    _write_json(
        _candidate_root(storage_root)
        / "video_to_analysis_roadmap_state_reconciliation_v1"
        / "roadmap_state_readiness_matrix.json",
        {"readiness": {"runtimeDefaultV7_3Active": True}},
    )


def test_release_acceptance_archive_packages_finished_current_release(tmp_path: Path) -> None:
    _seed_reconciliation(tmp_path)

    payload = archive.run_video_to_analysis_release_acceptance_archive(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_release_acceptance_archive_v1"
    manifest = json.loads((output_root / "release_acceptance_archive_manifest.json").read_text(encoding="utf-8"))
    backlog = json.loads((output_root / "remaining_work_backlog.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoToAnalysisReleaseAcceptanceArchived"] is True
    assert payload["currentReleaseFinished"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_steady_state_monitoring_cycle"
    assert manifest["releaseAcceptanceArchived"] is True
    assert manifest["archivedMilestones"]["v7_3RuntimeDefaultActive"] is True
    assert backlog["nextFiveSteps"][0]["lever"] == "video_to_analysis_steady_state_monitoring_cycle"


def test_release_acceptance_archive_blocks_without_reconciliation(tmp_path: Path) -> None:
    payload = archive.run_video_to_analysis_release_acceptance_archive(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_release_archive_reconciliation_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_roadmap_state_reconciliation"
