from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_user_facing_release_readout as readout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_strategic_selection(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_next_strategic_lane_selection_v1"
    _write_json(
        root / "next_strategic_lane_selection_summary.json",
        {
            "batchName": "video_to_analysis_next_strategic_lane_selection",
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "selectedStrategicLane": "user_facing_release_readout",
            "nextRecommendedNextLever": "video_to_analysis_user_facing_release_readout",
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )


def _seed_release_route(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_release_readout_route_binding_v1"
    _write_json(
        root / "release_readout_route_binding_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "releaseReadoutRouteReady": True,
            "apiRoutePath": "/api/video-to-analysis/release-readout",
            "htmlRoutePath": "/video-to-analysis/release-readout",
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )
    _write_json(
        root / "release_readout_view_model.json",
        {
            "schemaVersion": "video_to_analysis_release_readout_view_model_v1",
            "latestSnapshot": "video_to_analysis_next_sample_selection_snapshot_v38",
            "runtimeOperationallyComplete": True,
            "externalBenchmarkProductBindingReady": True,
        },
    )


def test_user_facing_release_readout_writes_shareable_doc_and_manifest(tmp_path: Path) -> None:
    _seed_strategic_selection(tmp_path)
    _seed_release_route(tmp_path)
    output_doc = tmp_path / "docs" / "user-facing-release.md"

    payload = readout.run_video_to_analysis_user_facing_release_readout(
        storage_root=tmp_path,
        output_doc_path=output_doc,
    )

    output_root = _candidate_root(tmp_path) / "video_to_analysis_user_facing_release_readout_v1"
    manifest = json.loads((output_root / "user_facing_release_manifest.json").read_text(encoding="utf-8"))
    checklist = json.loads((output_root / "operator_demo_checklist.json").read_text(encoding="utf-8"))
    doc = output_doc.read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["userFacingReleaseReadoutReady"] is True
    assert payload["shareableReadoutPath"] == str(output_doc)
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_approval"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert manifest["releaseRoute"] == "/video-to-analysis/release-readout"
    assert manifest["latestSnapshot"] == "video_to_analysis_next_sample_selection_snapshot_v38"
    assert checklist["demoSteps"][0]["route"] == "/video-to-analysis/release-readout"
    assert "Video-To-Analysis User-Facing Release Readout" in doc
    assert "v38" in doc
    assert "No new training" in doc


def test_user_facing_release_readout_blocks_without_strategic_selection(tmp_path: Path) -> None:
    _seed_release_route(tmp_path)

    payload = readout.run_video_to_analysis_user_facing_release_readout(
        storage_root=tmp_path,
        output_doc_path=tmp_path / "docs" / "blocked-release.md",
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_user_readout_strategic_selection_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_next_strategic_lane_selection"
