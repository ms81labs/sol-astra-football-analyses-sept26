from __future__ import annotations

import json
from pathlib import Path

from backend.app.run_benchmarks import summarize_match_benchmark
from backend.app.schemas import (
    BallOwnership,
    DetectedEvent,
    FrameData,
    HomographyPoint,
    MatchConfig,
    MatchSummary,
    ShotAnalytics,
)
from backend.app.storage import Storage
import backend.scripts.run_clip_manifest_expansion as run_clip_manifest_expansion


def _summary() -> MatchSummary:
    return MatchSummary(
        possession=55,
        myTeamDistance=1000,
        enemyDistance=950,
        myTeamAvgPos={"x": 52.0, "y": 48.0},
        enemyAvgPos={"x": 48.0, "y": 52.0},
        myTeamTopSpeed=30.1,
        enemyTopSpeed=29.0,
        myTeamSprints=10,
        enemySprints=9,
        formation="4-3-3",
    )


def _write_saved_match_entry(
    storage: Storage,
    match_id: str,
    *,
    video_path: str,
    accepted_frames: int = 8,
    controlled_frames: int = 6,
    truth_ready: bool = False,
    viable: bool = True,
) -> None:
    storage.save_raw_rows(
        match_id,
        [{"Frame_ID": index, "Timestamp": index * 0.2, "Entity_Type": "ball"} for index in range(accepted_frames)],
    )
    storage.save_frames(
        match_id,
        [
            FrameData(
                frameId=index,
                timestamp=index * 0.2,
                ball={"x": 30 + index, "y": 20 + (index % 3), "confidence": 0.85},
            )
            for index in range(accepted_frames)
        ],
    )
    storage.save_analytics(
        match_id,
        _summary(),
        assignments=[
            BallOwnership(frameId=index, timestamp=index * 0.2, team="my_team", trackId=7, distance=1.0)
            for index in range(controlled_frames)
        ],
        formation_timeline=[],
        shots=[
            ShotAnalytics(
                frameId=2,
                timestamp=0.4,
                team="my_team",
                playerId=7,
                x=39.0,
                y=17.0,
                onTarget=True,
                inBox=False,
                distanceToGoal=20.0,
                angleDegrees=22.0,
                xg=0.2,
            )
        ],
    )
    storage.save_events(
        match_id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.2, description="pass"),
            DetectedEvent(type="shot", frameId=2, timestamp=0.4, description="shot"),
            DetectedEvent(type="recovery", frameId=3, timestamp=0.6, description="recovery"),
        ],
    )
    storage.save_analysis_artifact(
        match_id,
        "ball_truth_layers",
        {
            "observedBall": {"summary": {"frameCount": max(accepted_frames - 1, 0)}},
            "inferredBall": {"summary": {"frameCount": 1 if accepted_frames else 0}},
            "acceptedBall": {"summary": {"frameCount": accepted_frames}},
            "acceptedSegments": [{"frameCount": accepted_frames}] if accepted_frames else [],
            "unknownGaps": [],
            "directObservationBreakdown": {
                "longGapTreatmentOutcome": "long_gap_treatment_partial",
                "controlledPossessionAssignmentOutcome": "controlled_possession_assignment_weak",
                "frozenPrimaryAcquisitionMode": "anchored_player_ranked_context_960",
                "frozenDetectorModelPath": "yolov10n.pt",
            },
            "summary": {
                "fiveMinuteTruthReady": truth_ready,
                "truthGateReasons": [] if truth_ready else ["Need controlled possession frames/frameCount >= 20%"],
            },
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "ball_pipeline_trace",
        {
            "matchId": match_id,
            "jobId": f"job-{match_id}",
            "inputMode": "video",
            "videoPath": video_path,
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "selected_cluster_delta",
        {
            "after": {
                "matchId": match_id,
                "jobId": f"job-{match_id}",
                "inputMode": "video",
                "matchStatus": "ready",
                "requiresTeamSelection": False,
            }
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "proof_summary",
        {
            "matchId": match_id,
            "savedMatchId": match_id,
            "jobId": f"job-{match_id}",
            "detectorModelName": "yolov10n.pt",
            "detectorModelPath": "yolov10n.pt",
            "acceptedBallFrames": accepted_frames,
            "controlledPossessionFrames": controlled_frames,
            "ballTrackViable": viable,
            "ballTrackEdgeFrameShare": 0.1 if viable else 0.8,
            "fiveMinuteTruthReady": truth_ready,
            "truthGateReasons": [] if truth_ready else ["Need controlled possession frames/frameCount >= 20%"],
        },
    )


def _create_remote_imported_match(
    storage_root: Path,
    clip_path: Path,
    *,
    manual_points: list[HomographyPoint] | None = None,
    truth_ready: bool = False,
    viable: bool = True,
) -> object:
    storage = Storage(storage_root)
    match = storage.create_match(
        name=f"{clip_path.stem}-manifest-import",
        input_mode="video",
        original_filename=clip_path.name,
        input_path=clip_path,
        config=MatchConfig(
            attackDirection="left_to_right",
            manualHomographyPoints=manual_points or [],
            autoHomography=False,
        ),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])
    _write_saved_match_entry(
        storage,
        match.id,
        video_path=str(clip_path),
        truth_ready=truth_ready,
        viable=viable,
    )
    return summarize_match_benchmark(storage, match.id)


def test_run_clip_manifest_expansion_enforces_caps_and_refreshes_suite(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    _write_saved_match_entry(storage, "covered-a", video_path="/videos/existing-source-a.mp4")
    _write_saved_match_entry(storage, "covered-b", video_path="/videos/existing-source-b.mp4")
    _write_saved_match_entry(storage, "covered-c", video_path="/videos/existing-source-b.mp4")

    existing_clip = tmp_path / "existing-source-a.mp4"
    existing_clip.write_bytes(b"existing")
    missing_clip = tmp_path / "missing-source.mp4"
    fresh_one = tmp_path / "fresh-source-1.mp4"
    fresh_two = tmp_path / "fresh-source-2.mp4"
    fresh_three = tmp_path / "fresh-source-3.mp4"
    fresh_one.write_bytes(b"one")
    fresh_two.write_bytes(b"two")
    fresh_three.write_bytes(b"three")

    source_manifest_path = tmp_path / "source_manifest.json"
    suite_manifest_path = tmp_path / "slice_suite.json"
    source_manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "frozen-viable-baseline-source-manifest",
                "suiteType": "user_supplied_source_clip_manifest",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                    "primaryMode": "anchored_player_ranked_context_960",
                    "keptCleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
                },
                "entries": [
                    {
                        "clipId": "covered-a",
                        "label": "Covered clip",
                        "localPath": str(existing_clip),
                        "sourceType": "user_supplied_local_video",
                        "notes": "",
                        "tags": ["covered"],
                    },
                    {
                        "clipId": "missing",
                        "label": "Missing clip",
                        "localPath": str(missing_clip),
                        "sourceType": "user_supplied_local_video",
                        "notes": "",
                        "tags": ["missing"],
                    },
                    {
                        "clipId": "fresh-one",
                        "label": "Fresh One",
                        "localPath": str(fresh_one),
                        "sourceType": "user_supplied_local_video",
                        "notes": "",
                        "tags": ["fresh"],
                    },
                    {
                        "clipId": "fresh-two",
                        "label": "Fresh Two",
                        "localPath": str(fresh_two),
                        "sourceType": "user_supplied_local_video",
                        "notes": "",
                        "tags": ["fresh"],
                    },
                    {
                        "clipId": "fresh-three",
                        "label": "Fresh Three",
                        "localPath": str(fresh_three),
                        "sourceType": "user_supplied_local_video",
                        "notes": "",
                        "tags": ["fresh"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    remote_calls: list[str] = []

    def fake_run_remote_video_benchmark(**kwargs):  # noqa: ANN003
        remote_calls.append(Path(kwargs["clip_path"]).name)
        return _create_remote_imported_match(
            kwargs["storage_root"],
            Path(kwargs["clip_path"]),
            manual_points=kwargs.get("manual_points"),
        )

    monkeypatch.setattr(
        "backend.scripts.run_clip_manifest_expansion.run_remote_video_benchmark",
        fake_run_remote_video_benchmark,
    )

    result = run_clip_manifest_expansion.run_clip_manifest_expansion(
        storage_root=tmp_path,
        source_manifest_path=source_manifest_path,
        suite_manifest_path=suite_manifest_path,
        timestamp_label="20260420T230000Z",
    )

    rows = result["rows"]
    assert [row["status"] for row in rows] == [
        "already_covered",
        "missing_file",
        "success",
        "success",
        "not_reached_attempt_cap",
    ]
    assert [row["attemptIndex"] for row in rows] == [None, 1, 2, 3, None]
    assert remote_calls == ["fresh-source-1.mp4", "fresh-source-2.mp4"]
    assert result["summary"]["successfulImports"] == 2
    assert result["summary"]["totalAttempts"] == 3
    assert result["summary"]["outcome"] == "clip_manifest_expansion_strong"
    assert result["summary"]["refreshedSuiteDistinctSourceClipCount"] == 4
    assert (tmp_path / "benchmark_suites" / "clip_manifest_expansion_20260420T230000Z" / "import_summary.json").exists()
    assert (tmp_path / "benchmark_suites" / "clip_manifest_expansion_20260420T230000Z" / "import_rows.csv").exists()
    assert (tmp_path / "benchmark_suites" / "clip_manifest_expansion_20260420T230000Z" / "import_summary.md").exists()

    refreshed_manifest = json.loads(suite_manifest_path.read_text(encoding="utf-8"))
    refreshed_source_ids = [entry["sourceClipId"] for entry in refreshed_manifest["entries"]]
    assert "fresh-source-1.mp4" in refreshed_source_ids
    assert "fresh-source-2.mp4" in refreshed_source_ids


def test_run_clip_manifest_expansion_records_remote_failures_without_aborting(tmp_path, monkeypatch):
    source_manifest_path = tmp_path / "source_manifest.json"
    suite_manifest_path = tmp_path / "slice_suite.json"
    storage = Storage(tmp_path)
    _write_saved_match_entry(storage, "covered-a", video_path="/videos/existing-source-a.mp4")
    clip_one = tmp_path / "clip-one.mp4"
    clip_two = tmp_path / "clip-two.mp4"
    clip_three = tmp_path / "clip-three.mp4"
    clip_one.write_bytes(b"one")
    clip_two.write_bytes(b"two")
    clip_three.write_bytes(b"three")
    source_manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "frozen-viable-baseline-source-manifest",
                "suiteType": "user_supplied_source_clip_manifest",
                "baselineFingerprint": {},
                "entries": [
                    {"clipId": "one", "label": "One", "localPath": str(clip_one), "sourceType": "user_supplied_local_video", "notes": "", "tags": []},
                    {"clipId": "two", "label": "Two", "localPath": str(clip_two), "sourceType": "user_supplied_local_video", "notes": "", "tags": []},
                    {"clipId": "three", "label": "Three", "localPath": str(clip_three), "sourceType": "user_supplied_local_video", "notes": "", "tags": []},
                ],
            }
        ),
        encoding="utf-8",
    )

    remote_calls: list[str] = []

    def fake_run_remote_video_benchmark(**kwargs):  # noqa: ANN003
        clip_name = Path(kwargs["clip_path"]).name
        remote_calls.append(clip_name)
        if clip_name == "clip-one.mp4":
            raise RuntimeError("remote failure")
        return _create_remote_imported_match(kwargs["storage_root"], Path(kwargs["clip_path"]))

    monkeypatch.setattr(
        "backend.scripts.run_clip_manifest_expansion.run_remote_video_benchmark",
        fake_run_remote_video_benchmark,
    )

    result = run_clip_manifest_expansion.run_clip_manifest_expansion(
        storage_root=tmp_path,
        source_manifest_path=source_manifest_path,
        suite_manifest_path=suite_manifest_path,
        timestamp_label="20260420T231500Z",
    )

    assert remote_calls == ["clip-one.mp4", "clip-two.mp4", "clip-three.mp4"]
    assert [row["status"] for row in result["rows"]] == ["failed", "success", "success"]
    assert result["summary"]["successfulImports"] == 2
    assert result["summary"]["totalAttempts"] == 3


def test_run_clip_manifest_expansion_rejects_duplicate_enabled_source_clip_ids_before_remote_spend(
    tmp_path, monkeypatch
):
    source_manifest_path = tmp_path / "source_manifest.json"
    suite_manifest_path = tmp_path / "slice_suite.json"
    clip_one = tmp_path / "clip-one.mp4"
    clip_two = tmp_path / "clip-two.mp4"
    clip_three = tmp_path / "clip-three.mp4"
    clip_one.write_bytes(b"one")
    clip_two.write_bytes(b"two")
    clip_three.write_bytes(b"three")
    source_manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "frozen-viable-baseline-source-manifest",
                "suiteType": "user_supplied_source_clip_manifest",
                "baselineFingerprint": {},
                "entries": [
                    {"clipId": "one", "label": "One", "localPath": str(clip_one), "sourceType": "user_supplied_local_video", "notes": "", "tags": []},
                    {"clipId": "two", "label": "Two", "localPath": str(clip_one), "sourceType": "user_supplied_local_video", "notes": "", "tags": []},
                    {"clipId": "three", "label": "Three", "localPath": str(clip_three), "sourceType": "user_supplied_local_video", "notes": "", "tags": []},
                ],
            }
        ),
        encoding="utf-8",
    )

    remote_calls: list[str] = []

    def fake_run_remote_video_benchmark(**kwargs):  # noqa: ANN003
        remote_calls.append(Path(kwargs["clip_path"]).name)
        return _create_remote_imported_match(kwargs["storage_root"], Path(kwargs["clip_path"]))

    monkeypatch.setattr(
        "backend.scripts.run_clip_manifest_expansion.run_remote_video_benchmark",
        fake_run_remote_video_benchmark,
    )

    result = run_clip_manifest_expansion.run_clip_manifest_expansion(
        storage_root=tmp_path,
        source_manifest_path=source_manifest_path,
        suite_manifest_path=suite_manifest_path,
        timestamp_label="20260421T000000Z",
    )

    assert remote_calls == ["clip-three.mp4"]
    assert [row["status"] for row in result["rows"]] == ["invalid_entry", "invalid_entry", "success"]
    assert [row["attemptIndex"] for row in result["rows"]] == [None, None, 1]
    assert all("Duplicate enabled sourceClipId" in str(row["error"]) for row in result["rows"][:2])
    assert result["summary"]["successfulImports"] == 1
    assert result["summary"]["totalAttempts"] == 1


def test_clip_manifest_expansion_outcome_and_next_lever_mapping():
    assert (
        run_clip_manifest_expansion.clip_manifest_expansion_outcome(
            successful_imports=2,
            refreshed_suite_distinct_source_clip_count=3,
        )
        == "clip_manifest_expansion_strong"
    )
    assert (
        run_clip_manifest_expansion.clip_manifest_expansion_recommended_next_lever(
            outcome="clip_manifest_expansion_strong",
            suite_verdict="baseline_not_robust",
        )
        == "multi_match_robustness_repair"
    )
    assert (
        run_clip_manifest_expansion.clip_manifest_expansion_recommended_next_lever(
            outcome="clip_manifest_expansion_strong",
            suite_verdict="viable_but_coverage_limited",
        )
        == "batch_safe_proof_loop_runner"
    )
    assert (
        run_clip_manifest_expansion.clip_manifest_expansion_recommended_next_lever(
            outcome="clip_manifest_expansion_partial",
            suite_verdict="truth_ready_on_suite",
        )
        == "expand_clip_manifest"
    )
