from __future__ import annotations

import csv
import json

from backend.app.run_benchmarks import discover_saved_match_slice_suite_entries
from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchSummary, ShotAnalytics
from backend.app.storage import Storage
import backend.scripts.run_benchmark_suite as run_benchmark_suite

SOURCE_ROBUSTNESS_OVERLAY_FIELDS = (
    "sourceRobustnessBestConfigName",
    "sourceRobustnessOutcome",
    "sourceRobustnessDominantFailureSignal",
    "sourceRobustnessImprovedSourceClipId",
    "sourceRobustnessRecommendedNextLever",
)


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


def _write_artifact_only_entry(
    storage: Storage,
    match_id: str,
    *,
    video_path: str,
    truth_ready: bool = False,
    accepted_frames: int = 8,
    controlled_frames: int = 6,
    ball_track_viable: bool = True,
    ball_track_edge_frame_share: float = 0.1,
    frame_count: int | None = None,
) -> None:
    total_frame_count = frame_count or accepted_frames
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
                ball=(
                    {
                        "x": (2 + (index % 2)) if not ball_track_viable else (30 + index),
                        "y": (3 + index) if not ball_track_viable else (20 + (index % 3)),
                        "confidence": 0.85,
                    }
                    if index < accepted_frames
                    else None
                ),
            )
            for index in range(total_frame_count)
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
            "observedBall": {"summary": {"frameCount": accepted_frames - 1}},
            "inferredBall": {"summary": {"frameCount": 1}},
            "acceptedBall": {"summary": {"frameCount": accepted_frames}},
            "acceptedSegments": [{"frameCount": accepted_frames}],
            "unknownGaps": [],
            "directObservationBreakdown": {
                "longGapTreatmentOutcome": "long_gap_treatment_partial",
                "controlledPossessionAssignmentOutcome": "controlled_possession_assignment_weak",
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
            "acceptedBallFrames": accepted_frames,
            "controlledPossessionFrames": controlled_frames,
            "ballTrackViable": ball_track_viable,
            "ballTrackEdgeFrameShare": ball_track_edge_frame_share,
            "fiveMinuteTruthReady": truth_ready,
            "truthGateReasons": [] if truth_ready else ["Need controlled possession frames/frameCount >= 20%"],
        },
    )


def test_discover_saved_match_slice_suite_entries_prefers_source_diversity_before_truncating(tmp_path):
    storage = Storage(tmp_path)
    for index in range(10):
        _write_artifact_only_entry(
            storage,
            f"a-match-{index:02d}",
            video_path="/root/WorkSpace/fotball-analyst/videos/clip-a.mp4",
        )
    _write_artifact_only_entry(
        storage,
        "b-match-00",
        video_path="/workspace/fotball-analyst/videos/clip-b.mp4",
    )
    (storage._match_dir("invalid-only") / "ball_pipeline_trace.json").write_text("{}", encoding="utf-8")

    entries = discover_saved_match_slice_suite_entries(tmp_path, max_entries=10)

    assert len(entries) == 10
    assert entries[0]["sourceClipId"] == "clip-a.mp4"
    assert entries[1]["sourceClipId"] == "clip-b.mp4"
    assert any(entry["sourceClipId"] == "clip-b.mp4" for entry in entries)
    assert entries[0]["sourceType"] == "saved_match_artifacts"


def test_run_benchmark_suite_writes_outputs_and_computes_viable_but_coverage_limited(tmp_path, monkeypatch, capsys):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    entries = []
    for index in range(5):
        match_id = f"match-{index}"
        video_path = f"/root/WorkSpace/fotball-analyst/videos/clip-{index % 2}.mp4"
        _write_artifact_only_entry(storage, match_id, video_path=video_path, truth_ready=False)
        entries.append(
            {
                "entryId": f"entry-{index}",
                "label": f"Slice {index}",
                "sourceType": "saved_match_artifacts",
                "matchId": match_id,
                "sourceClipId": f"clip-{index % 2}.mp4",
                "videoPath": video_path,
                "notes": "",
                "tags": ["slice"],
            }
        )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "test-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                    "primaryMode": "anchored_player_ranked_context_960",
                    "keptCleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
                },
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_benchmark_suite.py",
            "--storage-root",
            str(tmp_path),
            "--manifest-path",
            str(manifest_path),
        ],
    )

    run_benchmark_suite.main()

    payload = json.loads(capsys.readouterr().out)
    output_dir = tmp_path / "benchmark_suites" / "test-suite"
    assert payload["suiteVerdict"] == "viable_but_coverage_limited"
    assert payload["suiteRecommendedNextLever"] == "batch_safe_proof_loop_runner"
    assert payload["successfulEntryCount"] == 5
    assert payload["distinctSourceClipCount"] == 2
    assert (output_dir / "suite_summary.json").exists()
    assert (output_dir / "suite_rows.csv").exists()
    assert (output_dir / "suite_summary.md").exists()
    markdown = (output_dir / "suite_summary.md").read_text(encoding="utf-8")
    assert "viable_but_coverage_limited" in markdown
    assert "successfulEntryCount: 5" in markdown


def test_run_benchmark_suite_records_failed_entries_without_aborting(tmp_path):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    _write_artifact_only_entry(
        storage,
        "good-match",
        video_path="/root/WorkSpace/fotball-analyst/videos/clip-a.mp4",
    )
    manifest = {
        "suiteName": "failure-suite",
        "suiteType": "saved_match_slice_suite",
        "baselineFingerprint": {
            "detectorModelPath": "yolov10n.pt",
            "primaryMode": "anchored_player_ranked_context_960",
            "keptCleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
        },
        "entries": [
            {
                "entryId": "good",
                "label": "Good",
                "sourceType": "saved_match_artifacts",
                "matchId": "good-match",
                "sourceClipId": "clip-a.mp4",
                "videoPath": "/root/WorkSpace/fotball-analyst/videos/clip-a.mp4",
                "notes": "",
                "tags": [],
            },
            {
                "entryId": "bad",
                "label": "Bad",
                "sourceType": "saved_match_artifacts",
                "matchId": "missing-match",
                "sourceClipId": "clip-b.mp4",
                "videoPath": "/root/WorkSpace/fotball-analyst/videos/clip-b.mp4",
                "notes": "",
                "tags": [],
            },
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_benchmark_suite.run_benchmark_suite(
        storage_root=tmp_path,
        manifest_path=manifest_path,
    )

    rows = result["rows"]
    assert [row["status"] for row in rows] == ["success", "failed"]
    assert result["summary"]["failedEntryCount"] == 1
    assert result["summary"]["successfulEntryCount"] == 1
    assert result["summary"]["suiteVerdict"] == "dataset_too_narrow"


def test_run_benchmark_suite_writes_source_rollups_and_single_source_dominant_failure(tmp_path):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    entries = []
    for index in range(3):
        match_id = f"clip-a-{index}"
        video_path = "/root/WorkSpace/fotball-analyst/videos/clip-a.mp4"
        _write_artifact_only_entry(
            storage,
            match_id,
            video_path=video_path,
            accepted_frames=101,
            controlled_frames=98,
            ball_track_viable=False,
            ball_track_edge_frame_share=0.822,
            frame_count=1516,
        )
        entries.append(
            {
                "entryId": f"entry-a-{index}",
                "label": f"Clip A Slice {index}",
                "sourceType": "saved_match_artifacts",
                "matchId": match_id,
                "sourceClipId": "clip-a.mp4",
                "videoPath": video_path,
                "notes": "",
                "tags": ["slice"],
            }
        )

    _write_artifact_only_entry(
        storage,
        "clip-b-0",
        video_path="/root/WorkSpace/fotball-analyst/videos/clip-b.mp4",
        accepted_frames=13,
        controlled_frames=12,
        ball_track_viable=True,
        ball_track_edge_frame_share=0.308,
        frame_count=360,
    )
    entries.append(
        {
            "entryId": "entry-b-0",
            "label": "Clip B Slice 0",
            "sourceType": "saved_match_artifacts",
            "matchId": "clip-b-0",
            "sourceClipId": "clip-b.mp4",
            "videoPath": "/root/WorkSpace/fotball-analyst/videos/clip-b.mp4",
            "notes": "",
            "tags": ["slice"],
        }
    )
    _write_artifact_only_entry(
        storage,
        "clip-b-1",
        video_path="/root/WorkSpace/fotball-analyst/videos/clip-b.mp4",
        accepted_frames=14,
        controlled_frames=13,
        ball_track_viable=True,
        ball_track_edge_frame_share=0.3,
        frame_count=360,
    )
    entries.append(
        {
            "entryId": "entry-b-1",
            "label": "Clip B Slice 1",
            "sourceType": "saved_match_artifacts",
            "matchId": "clip-b-1",
            "sourceClipId": "clip-b.mp4",
            "videoPath": "/root/WorkSpace/fotball-analyst/videos/clip-b.mp4",
            "notes": "",
            "tags": ["slice"],
        }
    )

    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "source-rollup-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                    "primaryMode": "anchored_player_ranked_context_960",
                    "keptCleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
                },
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )

    result = run_benchmark_suite.run_benchmark_suite(
        storage_root=tmp_path,
        manifest_path=manifest_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "source-rollup-suite"
    assert result["summary"]["suiteVerdict"] == "baseline_not_robust"
    assert result["summary"]["sourceSummaries"]["clip-a.mp4"]["entryCount"] == 3
    assert result["summary"]["sourceSummaries"]["clip-a.mp4"]["viableEntryCount"] == 0
    assert result["summary"]["sourceSummaries"]["clip-a.mp4"]["medianBallTrackEdgeFrameShare"] > 0.6
    assert result["summary"]["sourceSummaries"]["clip-b.mp4"]["entryCount"] == 2
    assert result["summary"]["sourceSummaries"]["clip-b.mp4"]["viableEntryCount"] == 2
    assert result["robustnessDiagnosis"]["robustnessOutcome"] == "single_source_dominant_failure"
    assert result["robustnessDiagnosis"]["robustnessDominantFailureSignal"] == "high_ball_track_edge_frame_share"
    assert result["robustnessDiagnosis"]["robustnessRecommendedNextLever"] == "multi_match_robustness_repair"
    assert (output_dir / "suite_source_rows.csv").exists()
    assert (output_dir / "suite_robustness_diagnosis.json").exists()
    source_rows = {
        row["sourceClipId"]: row
        for row in csv.DictReader((output_dir / "suite_source_rows.csv").open(encoding="utf-8"))
    }
    assert source_rows["clip-a.mp4"]["entryCount"] == "3"
    assert source_rows["clip-b.mp4"]["viableEntryCount"] == "2"
    diagnosis_payload = json.loads((output_dir / "suite_robustness_diagnosis.json").read_text(encoding="utf-8"))
    assert diagnosis_payload["robustnessOutcome"] == "single_source_dominant_failure"
    suite_summary_payload = json.loads((output_dir / "suite_summary.json").read_text(encoding="utf-8"))
    for field_name in SOURCE_ROBUSTNESS_OVERLAY_FIELDS:
        assert field_name not in suite_summary_payload
        assert field_name not in diagnosis_payload
    markdown = (output_dir / "suite_summary.md").read_text(encoding="utf-8")
    assert "Source-Level Summary" in markdown
    assert "clip-a.mp4" in markdown
    assert "single_source_dominant_failure" in markdown


def test_run_benchmark_suite_writes_dataset_narrow_robustness_diagnosis(tmp_path):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    _write_artifact_only_entry(
        storage,
        "one-source",
        video_path="/root/WorkSpace/fotball-analyst/videos/clip-a.mp4",
        ball_track_viable=False,
        ball_track_edge_frame_share=0.822,
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "narrow-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                    "primaryMode": "anchored_player_ranked_context_960",
                    "keptCleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
                },
                "entries": [
                    {
                        "entryId": "only-entry",
                        "label": "Only Slice",
                        "sourceType": "saved_match_artifacts",
                        "matchId": "one-source",
                        "sourceClipId": "clip-a.mp4",
                        "videoPath": "/root/WorkSpace/fotball-analyst/videos/clip-a.mp4",
                        "notes": "",
                        "tags": ["slice"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = run_benchmark_suite.run_benchmark_suite(
        storage_root=tmp_path,
        manifest_path=manifest_path,
    )

    assert result["summary"]["suiteVerdict"] == "dataset_too_narrow"
    assert result["robustnessDiagnosis"]["robustnessOutcome"] == "dataset_still_too_narrow"
    assert result["robustnessDiagnosis"]["robustnessRecommendedNextLever"] == "expand_clip_manifest"
