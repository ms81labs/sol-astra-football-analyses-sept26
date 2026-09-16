from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchConfig, MatchSummary
from backend.app.storage import Storage
from backend.app.trust_crops import TrustCrop
import backend.scripts.run_touchline_training_data_curation_batch as run_touchline_training_data_curation_batch


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


def _write_suite_surfaces(tmp_path: Path) -> Path:
    output_dir = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    output_dir.mkdir(parents=True, exist_ok=True)

    active_lane_snapshot = {
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "sourceRobustnessActiveConfigName": "source_robustness_baseline_current",
        "sourceRobustnessBestConfigName": "source_robustness_shadow_edge_run_keep_every_2_min10",
        "sourceRobustnessBestExploratoryConfigName": "source_robustness_shadow_edge_run_keep_every_3_min10",
        "sourceRobustnessOutcome": "source_robustness_partial",
        "sourceRobustnessRecommendedNextLever": "prepare_touchline_training_data",
    }
    failure_audit = {
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "activeConfigName": "source_robustness_baseline_current",
        "bestQualifyingConfigName": "source_robustness_shadow_edge_run_keep_every_2_min10",
        "bestExploratoryConfigName": "source_robustness_shadow_edge_run_keep_every_3_min10",
        "configs": {
            "source_robustness_baseline_current": {
                "configName": "source_robustness_baseline_current",
                "sliceDiagnostics": [
                    {
                        "matchId": "failing-match-a",
                        "truthGateReasons": [
                            "Need viable ball track: meaningful motion and edgeFrameShare <= 60%",
                        ],
                    },
                    {
                        "matchId": "failing-match-b",
                        "truthGateReasons": [
                            "Accepted ball layer is still too sparse for truthful 5-10 minute analysis",
                        ],
                    },
                    {
                        "matchId": "control-match-a",
                        "truthGateReasons": [],
                    },
                ],
            }
        },
        "sourceRobustnessRecommendedNextLever": "prepare_touchline_training_data",
    }
    slice_projection = {
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "configs": {
            "source_robustness_baseline_current": {
                "rows": [
                    {
                        "configName": "source_robustness_baseline_current",
                        "matchId": "failing-match-a",
                        "label": "Failing A",
                        "sourceClipId": "trimed-5min.mp4",
                        "acceptedBallRatio": 0.12,
                        "controlledPossessionRatio": 0.05,
                        "ballTrackEdgeFrameShare": 0.94,
                        "ballTrackViable": False,
                        "truthGateReasons": [
                            "Need viable ball track: meaningful motion and edgeFrameShare <= 60%",
                        ],
                    },
                    {
                        "configName": "source_robustness_baseline_current",
                        "matchId": "failing-match-b",
                        "label": "Failing B",
                        "sourceClipId": "trimed-5min.mp4",
                        "acceptedBallRatio": 0.07,
                        "controlledPossessionRatio": 0.04,
                        "ballTrackEdgeFrameShare": 0.81,
                        "ballTrackViable": False,
                        "truthGateReasons": [
                            "Accepted ball layer is still too sparse for truthful 5-10 minute analysis",
                        ],
                    },
                    {
                        "configName": "source_robustness_baseline_current",
                        "matchId": "control-match-a",
                        "label": "Control A",
                        "sourceClipId": "trimed-football-2-1minute.mp4",
                        "acceptedBallRatio": 0.04,
                        "controlledPossessionRatio": 0.03,
                        "ballTrackEdgeFrameShare": 0.31,
                        "ballTrackViable": True,
                        "truthGateReasons": [],
                    },
                ],
                "configOutcome": "source_robustness_weak",
                "passedPromotionGate": False,
                "promotionBlockers": [],
            }
        },
        "sourceRobustnessRecommendedNextLever": "prepare_touchline_training_data",
    }
    detector_breadth_matrix = {
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "screenWinningDetectorModelPath": "yolov10n.pt",
        "remoteWinningDetectorModelPath": "yolov10n.pt",
        "baselineRemoteBeatsPlateau": False,
        "compoundThinRemoteBeatsPlateau": False,
        "detectorBreadthFalsified": True,
        "nextTrainingCandidateNeeded": True,
        "nextRecommendedNextLever": "prepare_touchline_training_data",
    }

    (output_dir / "active_lane_snapshot.json").write_text(json.dumps(active_lane_snapshot, indent=2), encoding="utf-8")
    (output_dir / "primary_source_robustness_failure_audit.json").write_text(
        json.dumps(failure_audit, indent=2),
        encoding="utf-8",
    )
    (output_dir / "primary_source_robustness_slice_projection.json").write_text(
        json.dumps(slice_projection, indent=2),
        encoding="utf-8",
    )
    (output_dir / "detector_breadth_matrix.json").write_text(
        json.dumps(detector_breadth_matrix, indent=2),
        encoding="utf-8",
    )
    return output_dir


def _write_match_artifacts(
    storage: Storage,
    *,
    match_id: str,
    source_clip_id: str,
    video_path: str,
    frame_ids: list[int],
    accepted_rows: list[dict[str, object]],
    probe_filtered_rows: list[dict[str, object]],
    probe_raw_rows: list[dict[str, object]],
) -> None:
    with patch("backend.app.storage.uuid.uuid4") as new_id:
        new_id.return_value.hex = match_id
        storage.create_match(source_clip_id, "video", source_clip_id, Path(video_path), MatchConfig())
    storage.update_match_status(match_id, status="ready")
    accepted_frame_ids = {int(row["Frame_ID"]) for row in accepted_rows}
    frames = [
        FrameData(
            frameId=frame_id,
            timestamp=round(frame_id / 25.0, 3),
            ball={"x": 40.0, "y": 25.0, "confidence": 0.9} if frame_id in accepted_frame_ids else None,
        )
        for frame_id in frame_ids
    ]
    assignments = [
        BallOwnership(
            frameId=frame_id,
            timestamp=round(frame_id / 25.0, 3),
            team="my_team",
            trackId=7,
            distance=1.0,
        )
        for frame_id in frame_ids
    ]
    storage.save_frames(match_id, frames)
    storage.save_analytics(match_id, _summary(), assignments=assignments, formation_timeline=[], shots=[])
    storage.save_events(
        match_id,
        [
            DetectedEvent(type="pass", frameId=frame_ids[0], timestamp=0.1, description="pass"),
        ],
    )
    storage.save_analysis_artifact(
        match_id,
        "ball_truth_layers",
        {
            "acceptedBall": {
                "summary": {"frameCount": len(accepted_rows)},
                "rows": accepted_rows,
            },
            "probeObservedBall": {
                "filteredRows": probe_filtered_rows,
                "rawRows": probe_raw_rows,
            },
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "ball_pipeline_trace",
        {
            "matchId": match_id,
            "videoPath": video_path,
            "sourceClipId": source_clip_id,
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "proof_summary",
        {
            "matchId": match_id,
            "savedMatchId": match_id,
            "detectorModelPath": "yolov10n.pt",
            "detectorModelName": "yolov10n.pt",
            "acceptedBallFrames": len(accepted_rows),
            "controlledPossessionFrames": len(accepted_rows),
            "ballTrackViable": source_clip_id != "trimed-5min.mp4",
            "ballTrackEdgeFrameShare": 0.82 if source_clip_id == "trimed-5min.mp4" else 0.31,
        },
    )


def _write_source_matches(tmp_path: Path) -> tuple[Storage, Path, Path]:
    storage = Storage(tmp_path)
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    failing_video = videos_dir / "trimed-5min.mp4"
    control_video = videos_dir / "trimed-football-2-1minute.mp4"
    failing_video.write_bytes(b"video")
    control_video.write_bytes(b"video")

    _write_match_artifacts(
        storage,
        match_id="failing-match-a",
        source_clip_id="trimed-5min.mp4",
        video_path=str(failing_video),
        frame_ids=list(range(10, 16)),
        accepted_rows=[
            {
                "Frame_ID": 10,
                "Timestamp": 0.4,
                "Entity_Type": "ball",
                "Track_ID": -1,
                "X": 40.0,
                "Y": 20.0,
                "Conf": 0.95,
                "Source_X1": 10.0,
                "Source_Y1": 5.0,
                "Source_X2": 20.0,
                "Source_Y2": 15.0,
            },
            {
                "Frame_ID": 11,
                "Timestamp": 0.44,
                "Entity_Type": "ball",
                "Track_ID": -1,
                "X": 41.0,
                "Y": 21.0,
                "Conf": 0.94,
                "Source_X1": 12.0,
                "Source_Y1": 6.0,
                "Source_X2": 22.0,
                "Source_Y2": 16.0,
            },
        ],
        probe_filtered_rows=[
            {
                "Frame_ID": 10,
                "Timestamp": 0.4,
                "Entity_Type": "ball",
                "Track_ID": -1,
                "X": 42.0,
                "Y": 19.0,
                "Conf": 0.50,
                "Source_X1": 30.0,
                "Source_Y1": 10.0,
                "Source_X2": 50.0,
                "Source_Y2": 30.0,
            },
            {
                "Frame_ID": 12,
                "Timestamp": 0.48,
                "Entity_Type": "ball",
                "Track_ID": -1,
                "X": 43.0,
                "Y": 22.0,
                "Conf": 0.91,
                "Source_X1": 14.0,
                "Source_Y1": 7.0,
                "Source_X2": 24.0,
                "Source_Y2": 17.0,
            },
        ],
        probe_raw_rows=[
            {
                "Frame_ID": 13,
                "Timestamp": 0.52,
                "Entity_Type": "ball",
                "Track_ID": -1,
                "X": 44.0,
                "Y": 23.0,
                "Conf": 0.55,
                "Source_X1": 16.0,
                "Source_Y1": 8.0,
                "Source_X2": 26.0,
                "Source_Y2": 18.0,
            },
        ],
    )
    _write_match_artifacts(
        storage,
        match_id="control-match-a",
        source_clip_id="trimed-football-2-1minute.mp4",
        video_path=str(control_video),
        frame_ids=list(range(20, 25)),
        accepted_rows=[
            {
                "Frame_ID": 20,
                "Timestamp": 0.8,
                "Entity_Type": "ball",
                "Track_ID": -1,
                "X": 50.0,
                "Y": 25.0,
                "Conf": 0.99,
                "Source_X1": 40.0,
                "Source_Y1": 12.0,
                "Source_X2": 50.0,
                "Source_Y2": 22.0,
            }
        ],
        probe_filtered_rows=[],
        probe_raw_rows=[],
    )
    return storage, failing_video, control_video


def test_select_representative_rows_prefers_worst_failing_and_viable_control():
    rows = [
        {
            "matchId": "failing-a",
            "sourceClipId": "trimed-5min.mp4",
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.91,
            "acceptedBallRatio": 0.10,
            "controlledPossessionRatio": 0.04,
        },
        {
            "matchId": "failing-b",
            "sourceClipId": "trimed-5min.mp4",
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.83,
            "acceptedBallRatio": 0.06,
            "controlledPossessionRatio": 0.03,
        },
        {
            "matchId": "control-a",
            "sourceClipId": "trimed-football-2-1minute.mp4",
            "ballTrackViable": True,
            "ballTrackEdgeFrameShare": 0.31,
            "acceptedBallRatio": 0.04,
            "controlledPossessionRatio": 0.03,
        },
        {
            "matchId": "control-b",
            "sourceClipId": "trimed-football-2-1minute.mp4",
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.80,
            "acceptedBallRatio": 0.02,
            "controlledPossessionRatio": 0.01,
        },
    ]

    failing_row, control_row = run_touchline_training_data_curation_batch.select_representative_projection_rows(
        rows=rows,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
    )

    assert failing_row["matchId"] == "failing-a"
    assert control_row["matchId"] == "control-a"


def test_run_touchline_training_data_curation_batch_writes_manifest_yolo_export_and_idempotent_seeded_issues(
    tmp_path,
    monkeypatch,
):
    _write_suite_surfaces(tmp_path)
    storage, failing_video, control_video = _write_source_matches(tmp_path)

    crop_map = {
        "failing-match-a": [
            TrustCrop(
                frameStart=10,
                frameEnd=14,
                timestampStart=0.4,
                timestampEnd=0.56,
                score=12.5,
                reasons=["track_switches", "team_flips"],
            )
        ],
        "control-match-a": [
            TrustCrop(
                frameStart=20,
                frameEnd=22,
                timestampStart=0.8,
                timestampEnd=0.88,
                score=4.5,
                reasons=["possession_gap"],
            )
        ],
    }

    monkeypatch.setattr(
        run_touchline_training_data_curation_batch,
        "compute_trust_crops",
        lambda frames, assignments, max_crops=20: list(
            crop_map[
                "failing-match-a"
                if any(frame.get("frameId") == 10 for frame in frames)
                else "control-match-a"
            ][:max_crops]
        ),
    )

    extracted_frames: list[tuple[str, int, str]] = []

    def fake_extract_frame_image(*, video_path: Path, frame_id: int, output_path: Path) -> tuple[int, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")
        extracted_frames.append((str(video_path), frame_id, str(output_path)))
        return (100, 50)

    monkeypatch.setattr(
        run_touchline_training_data_curation_batch,
        "_extract_frame_image",
        fake_extract_frame_image,
    )

    first_result = run_touchline_training_data_curation_batch.run_touchline_training_data_curation_batch(
        storage_root=tmp_path,
    )
    second_result = run_touchline_training_data_curation_batch.run_touchline_training_data_curation_batch(
        storage_root=tmp_path,
    )

    artifact_root = tmp_path / "training_prep" / "touchline_training_data_curation_foundation"
    manifest = json.loads((artifact_root / "curation_manifest.json").read_text(encoding="utf-8"))
    split_manifest = json.loads((artifact_root / "split_manifest.json").read_text(encoding="utf-8"))
    issue_report = json.loads((artifact_root / "seeded_issue_report.json").read_text(encoding="utf-8"))
    dataset_yaml = (artifact_root / "yolo_export" / "dataset.yaml").read_text(encoding="utf-8")

    assert first_result["representativeFailingMatchId"] == "failing-match-a"
    assert first_result["representativeControlMatchId"] == "control-match-a"
    assert first_result["yoloExportReady"] is True
    assert second_result["curationUnitCount"] == first_result["curationUnitCount"]

    assert manifest["curationUnitCount"] == 2
    assert manifest["positiveSeedExampleCount"] >= 4
    assert manifest["negativeSeedExampleCount"] >= 1
    assert manifest["representativeFailingMatchId"] == "failing-match-a"
    assert manifest["representativeControlMatchId"] == "control-match-a"
    assert all(unit["labelStatus"] == "seeded_review_required" for unit in manifest["curationUnits"])
    assert manifest["curationUnits"][0]["artifactLineagePaths"]["ballTruthLayersPath"].endswith("ball_truth_layers.json")

    assert split_manifest["sourceAwareSplitLeakageDetected"] is False
    assert split_manifest["splits"]["train"]["sourceClipIds"] == ["trimed-5min.mp4"]
    assert split_manifest["splits"]["val"]["sourceClipIds"] == ["trimed-football-2-1minute.mp4"]
    assert split_manifest["splits"]["train"]["curationUnitCount"] == 1
    assert split_manifest["splits"]["val"]["curationUnitCount"] == 1

    assert issue_report["seededIssueCount"] == 2
    assert issue_report["removedPriorSeededIssueCount"] == 2

    failing_issues = storage.list_issues("failing-match-a")
    control_issues = storage.list_issues("control-match-a")
    assert len(failing_issues) == 1
    assert len(control_issues) == 1
    assert failing_issues[0].bucket == "tracking_failure"
    assert failing_issues[0].evidenceTarget == "trust_eval"
    assert failing_issues[0].note.startswith(run_touchline_training_data_curation_batch.SEEDED_ISSUE_NOTE_PREFIX)

    assert "train: images/train" in dataset_yaml
    assert "val: images/val" in dataset_yaml
    assert "names:" in dataset_yaml
    assert f"path: {artifact_root / 'yolo_export'}" in dataset_yaml

    train_image = artifact_root / "yolo_export" / "images" / "train" / "failing-match-a__10__f0010.jpg"
    train_label = artifact_root / "yolo_export" / "labels" / "train" / "failing-match-a__10__f0010.txt"
    probe_label = artifact_root / "yolo_export" / "labels" / "train" / "failing-match-a__10__f0012.txt"
    negative_label = artifact_root / "yolo_export" / "labels" / "train" / "failing-match-a__10__f0014.txt"
    control_image = artifact_root / "yolo_export" / "images" / "val" / "control-match-a__20__f0020.jpg"

    assert train_image.exists()
    assert control_image.exists()
    assert train_label.read_text(encoding="utf-8").strip() == "0 0.150000 0.200000 0.100000 0.200000"
    assert probe_label.read_text(encoding="utf-8").strip() == "0 0.190000 0.240000 0.100000 0.200000"
    assert negative_label.read_text(encoding="utf-8") == ""

    assert len(extracted_frames) >= 5
    assert any(video == str(failing_video) for video, _frame_id, _path in extracted_frames)
    assert any(video == str(control_video) for video, _frame_id, _path in extracted_frames)
    assert [unit["curationUnitId"] for unit in manifest["curationUnits"]] == second_result["curationUnitIds"]


def test_run_touchline_training_data_curation_batch_falls_back_when_proof_summary_is_missing(
    tmp_path,
    monkeypatch,
):
    _write_suite_surfaces(tmp_path)
    _storage, _failing_video, _control_video = _write_source_matches(tmp_path)
    for match_id in ("failing-match-a", "control-match-a"):
        proof_summary_path = tmp_path / "matches" / match_id / "proof_summary.json"
        proof_summary_path.unlink()

    monkeypatch.setattr(
        run_touchline_training_data_curation_batch,
        "compute_trust_crops",
        lambda frames, assignments, max_crops=20: [
            TrustCrop(
                frameStart=_safe_frame_start(frames),
                frameEnd=_safe_frame_start(frames) + 1,
                timestampStart=frames[0]["timestamp"],
                timestampEnd=frames[min(1, len(frames) - 1)]["timestamp"],
                score=2.0,
                reasons=["team_flips"],
            )
        ],
    )
    def fake_extract_frame_image(*, video_path: Path, frame_id: int, output_path: Path) -> tuple[int, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"img")
        return (100, 50)
    monkeypatch.setattr(
        run_touchline_training_data_curation_batch,
        "_extract_frame_image",
        fake_extract_frame_image,
    )

    result = run_touchline_training_data_curation_batch.run_touchline_training_data_curation_batch(
        storage_root=tmp_path,
    )

    manifest = json.loads(
        (tmp_path / "training_prep" / "touchline_training_data_curation_foundation" / "curation_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert result["curationUnitCount"] == 2
    assert manifest["curationUnits"][0]["detectorConfigProvenance"]["detectorModelPath"] == "yolov10n.pt"


def _safe_frame_start(frames: list[dict[str, object]]) -> int:
    return int(frames[0]["frameId"])
