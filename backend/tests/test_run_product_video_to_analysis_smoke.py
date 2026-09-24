from __future__ import annotations

from pathlib import Path

import backend.scripts.run_product_video_to_analysis_smoke as smoke
from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchConfig, MatchSummary
from backend.app.storage import Storage


def _seed_ready_video_match(storage_root: Path) -> str:
    storage = Storage(storage_root)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="Ready Video",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.update_match_status(match.id, status="ready")
    storage.save_frames(match.id, [FrameData(frameId=0, timestamp=0.0, ball={"x": 52.0, "y": 50.0, "confidence": 0.95})])
    storage.save_analytics(
        match.id,
        MatchSummary(
            possession=55,
            myTeamDistance=100,
            enemyDistance=90,
            myTeamAvgPos={"x": 50.0, "y": 50.0},
            enemyAvgPos={"x": 55.0, "y": 50.0},
            myTeamTopSpeed=30.0,
            enemyTopSpeed=28.0,
            myTeamSprints=2,
            enemySprints=1,
            formation="4-3-3",
        ),
        [BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0)],
        [],
        [],
    )
    storage.save_events(match.id, [DetectedEvent(type="recovery", frameId=0, timestamp=0.0, description="recovery")])
    storage.save_analysis_artifact(
        match.id,
        "ball_pipeline_trace",
        {
            "traceVersion": 1,
            "auxiliaryBallModelPath": "/tmp/v7_2_best.pt",
            "auxiliaryBallModelProfile": "ball_probe_only_v7_2_crop_256",
        },
    )
    return match.id


def test_product_video_to_analysis_smoke_passes_with_api_upload_and_existing_video_bundle(tmp_path: Path) -> None:
    video_match_id = _seed_ready_video_match(tmp_path)

    payload = smoke.run_product_video_to_analysis_smoke(storage_root=tmp_path)

    output_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "product_video_to_analysis_smoke_v1"
    )
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["apiUploadJobSmokePassed"] is True
    assert payload["existingVideoBundleSmokePassed"] is True
    assert payload["existingVideoBundleMatchId"] == video_match_id
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_adapter_smoke_test"
    assert (output_root / "api_upload_job_smoke_audit.json").exists()
    assert (output_root / "existing_video_bundle_smoke_audit.json").exists()
    assert (output_root / "sample_exported_match_bundle.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_product_video_to_analysis_smoke_routes_when_no_video_bundle_exists(tmp_path: Path) -> None:
    payload = smoke.run_product_video_to_analysis_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["apiUploadJobSmokePassed"] is True
    assert payload["existingVideoBundleSmokePassed"] is False
    assert payload["secondaryConcern"] == "product_video_smoke_no_existing_video_bundle"


def test_product_video_to_analysis_smoke_attempt_plan_has_three_failsafes(tmp_path: Path) -> None:
    _seed_ready_video_match(tmp_path)

    payload = smoke.run_product_video_to_analysis_smoke(storage_root=tmp_path)

    assert [item["attemptApproachFamily"] for item in payload["attemptPlan"]] == [
        "api_upload_export_smoke",
        "video_bundle_contract_repair",
        "product_smoke_blocker_summary",
    ]
