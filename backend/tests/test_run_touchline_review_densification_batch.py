from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchConfig, MatchSummary
from backend.app.storage import Storage
from backend.app.trust_crops import TrustCrop
import backend.scripts.run_touchline_review_densification_batch as run_touchline_review_densification_batch
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


def _write_suite_surfaces(tmp_path: Path) -> None:
    output_dir = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    output_dir.mkdir(parents=True, exist_ok=True)

    active_lane_snapshot = {
        "suiteName": "frozen-viable-baseline-slice-suite",
        "suiteVerdict": "baseline_not_robust",
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "sourceRobustnessActiveConfigName": "source_robustness_baseline_current",
        "sourceRobustnessBestConfigName": "source_robustness_shadow_edge_run_keep_every_2_min10",
        "sourceRobustnessBestExploratoryConfigName": "source_robustness_shadow_edge_run_keep_every_3_min10",
        "sourceRobustnessOutcome": "source_robustness_partial",
        "sourceRobustnessRecommendedNextLever": "start_phase_1b_review_densification",
        "baselineFingerprint": {
            "detectorModelPath": "yolov10n.pt",
            "primaryMode": "anchored_player_ranked_context_960",
            "cleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
        },
    }
    suite_summary = dict(active_lane_snapshot)
    suite_robustness_diagnosis = dict(active_lane_snapshot)
    suite_robustness_diagnosis["sourceRobustnessDiagnosis"] = {
        "plateauDetected": True,
        "selectedConfigPrimaryBlocker": "high_ball_track_edge_frame_share",
    }
    failure_audit = {
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "activeConfigName": "source_robustness_baseline_current",
        "configs": {
            "source_robustness_baseline_current": {
                "configName": "source_robustness_baseline_current",
                "sliceDiagnostics": [
                    {
                        "matchId": "1c8136cda03240aa8324f676c9bbf99a",
                        "truthGateReasons": [
                            "Need viable ball track: meaningful motion and edgeFrameShare <= 60%",
                        ],
                    },
                    {
                        "matchId": "1d67fa87080446a0a777901aace43809",
                        "truthGateReasons": [],
                    },
                ],
            }
        },
    }
    slice_projection = {
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "configs": {
            "source_robustness_baseline_current": {
                "rows": [
                    {
                        "configName": "source_robustness_baseline_current",
                        "matchId": "1c8136cda03240aa8324f676c9bbf99a",
                        "label": "Failing",
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
                        "matchId": "1d67fa87080446a0a777901aace43809",
                        "label": "Control",
                        "sourceClipId": "trimed-football-2-1minute.mp4",
                        "acceptedBallRatio": 0.61,
                        "controlledPossessionRatio": 0.53,
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
    }
    detector_breadth = {
        "failingSourceClipId": "trimed-5min.mp4",
        "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
        "screenWinningDetectorModelPath": "yolov10n.pt",
        "remoteWinningDetectorModelPath": "yolov10n.pt",
        "baselineRemoteBeatsPlateau": False,
        "compoundThinRemoteBeatsPlateau": False,
        "detectorBreadthFalsified": True,
        "nextTrainingCandidateNeeded": True,
    }

    for name, payload in (
        ("active_lane_snapshot.json", active_lane_snapshot),
        ("suite_summary.json", suite_summary),
        ("suite_robustness_diagnosis.json", suite_robustness_diagnosis),
        ("primary_source_robustness_failure_audit.json", failure_audit),
        ("primary_source_robustness_slice_projection.json", slice_projection),
        ("detector_breadth_matrix.json", detector_breadth),
    ):
        (output_dir / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ball_row(frame_id: int, x1: float, y1: float, x2: float, y2: float) -> dict[str, object]:
    return {
        "Frame_ID": frame_id,
        "Timestamp": round(frame_id / 25.0, 3),
        "Entity_Type": "ball",
        "Track_ID": -1,
        "X": 40.0,
        "Y": 20.0,
        "Conf": 0.95,
        "Source_X1": x1,
        "Source_Y1": y1,
        "Source_X2": x2,
        "Source_Y2": y2,
    }


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
        [DetectedEvent(type="pass", frameId=frame_ids[0], timestamp=0.1, description="pass")],
    )
    storage.save_analysis_artifact(
        match_id,
        "ball_truth_layers",
        {
            "acceptedBall": {"summary": {"frameCount": len(accepted_rows)}, "rows": accepted_rows},
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


def _write_source_matches(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    failing_video = videos_dir / "trimed-5min.mp4"
    control_video = videos_dir / "trimed-football-2-1minute.mp4"
    failing_video.write_bytes(b"video")
    control_video.write_bytes(b"video")

    _write_match_artifacts(
        storage,
        match_id="1c8136cda03240aa8324f676c9bbf99a",
        source_clip_id="trimed-5min.mp4",
        video_path=str(failing_video),
        frame_ids=list(range(10, 56)),
        accepted_rows=[
            _ball_row(10, 10.0, 5.0, 20.0, 15.0),
            _ball_row(20, 12.0, 6.0, 22.0, 16.0),
            _ball_row(30, 14.0, 7.0, 24.0, 17.0),
            _ball_row(40, 16.0, 8.0, 26.0, 18.0),
            _ball_row(50, 18.0, 9.0, 28.0, 19.0),
        ],
        probe_filtered_rows=[
            _ball_row(11, 30.0, 10.0, 40.0, 20.0),
            _ball_row(21, 32.0, 11.0, 42.0, 21.0),
            _ball_row(31, 34.0, 12.0, 44.0, 22.0),
            _ball_row(41, 36.0, 13.0, 46.0, 23.0),
            _ball_row(51, 38.0, 14.0, 48.0, 24.0),
        ],
        probe_raw_rows=[
            _ball_row(12, 50.0, 15.0, 60.0, 25.0),
            _ball_row(22, 52.0, 16.0, 62.0, 26.0),
            _ball_row(32, 54.0, 17.0, 64.0, 27.0),
            _ball_row(42, 56.0, 18.0, 66.0, 28.0),
            _ball_row(52, 58.0, 19.0, 68.0, 29.0),
        ],
    )
    _write_match_artifacts(
        storage,
        match_id="1d67fa87080446a0a777901aace43809",
        source_clip_id="trimed-football-2-1minute.mp4",
        video_path=str(control_video),
        frame_ids=list(range(180, 186)),
        accepted_rows=[_ball_row(180, 40.0, 12.0, 50.0, 22.0)],
        probe_filtered_rows=[],
        probe_raw_rows=[],
    )


def _write_candidate_evaluation_artifact(tmp_path: Path) -> None:
    evaluation_root = (
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v1"
        / "evaluation_v1"
    )
    evaluation_root.mkdir(parents=True, exist_ok=True)
    (evaluation_root / "evaluation_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v1",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v1",
                "screenCompleted": False,
                "candidateBaselineProofRan": True,
                "candidateBaselineProductBeatsPlateau": False,
                "phase1BDensificationRecommended": True,
                "nextRecommendedNextLever": "start_phase_1b_review_densification",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _seed_phase1_artifacts(tmp_path: Path, monkeypatch) -> None:
    _write_suite_surfaces(tmp_path)
    _write_source_matches(tmp_path)
    _write_candidate_evaluation_artifact(tmp_path)

    crop_map = {
        "failing": [
            TrustCrop(
                frameStart=10,
                frameEnd=14,
                timestampStart=0.4,
                timestampEnd=0.56,
                score=12.5,
                reasons=["track_switches", "team_flips"],
            )
        ],
        "control": [
            TrustCrop(
                frameStart=180,
                frameEnd=184,
                timestampStart=7.2,
                timestampEnd=7.36,
                score=4.5,
                reasons=["possession_gap"],
            )
        ],
    }
    monkeypatch.setattr(
        run_touchline_training_data_curation_batch,
        "compute_trust_crops",
        lambda frames, assignments, max_crops=20: list(
            crop_map["failing"] if any(int(frame.get("frameId")) == 10 for frame in frames) else crop_map["control"]
        )[:max_crops],
    )

    def fake_extract_frame_image(*, video_path: Path, frame_id: int, output_path: Path) -> tuple[int, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"phase1-image")
        return (100, 50)

    monkeypatch.setattr(
        run_touchline_training_data_curation_batch,
        "_extract_frame_image",
        fake_extract_frame_image,
    )

    run_touchline_training_data_curation_batch.run_touchline_training_data_curation_batch(
        storage_root=tmp_path,
    )


def test_run_touchline_review_densification_batch_expands_failing_match_and_writes_overlay_bundle_and_export(
    tmp_path,
    monkeypatch,
):
    _seed_phase1_artifacts(tmp_path, monkeypatch)

    densification_crops = [
        TrustCrop(frameStart=10, frameEnd=14, timestampStart=0.4, timestampEnd=0.56, score=12.5, reasons=["track_switches"]),
        TrustCrop(frameStart=20, frameEnd=24, timestampStart=0.8, timestampEnd=0.96, score=11.5, reasons=["team_flips"]),
        TrustCrop(frameStart=12, frameEnd=16, timestampStart=0.48, timestampEnd=0.64, score=11.0, reasons=["overlap_should_skip"]),
        TrustCrop(frameStart=30, frameEnd=34, timestampStart=1.2, timestampEnd=1.36, score=10.5, reasons=["ball_teleport"]),
        TrustCrop(frameStart=40, frameEnd=44, timestampStart=1.6, timestampEnd=1.76, score=9.5, reasons=["possession_gap"]),
        TrustCrop(frameStart=50, frameEnd=54, timestampStart=2.0, timestampEnd=2.16, score=8.5, reasons=["track_switches"]),
    ]
    monkeypatch.setattr(
        run_touchline_review_densification_batch,
        "compute_trust_crops",
        lambda frames, assignments, max_crops=20: list(densification_crops)[:max_crops],
    )

    extracted_frames: list[tuple[int, str]] = []

    def fake_extract_frame_image(*, video_path: Path, frame_id: int, output_path: Path) -> tuple[int, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"phase1b-image")
        extracted_frames.append((frame_id, str(output_path)))
        return (100, 50)

    monkeypatch.setattr(
        run_touchline_review_densification_batch,
        "_extract_frame_image",
        fake_extract_frame_image,
    )

    result = run_touchline_review_densification_batch.run_touchline_review_densification_batch(
        storage_root=tmp_path,
    )

    artifact_root = tmp_path / "training_prep" / "touchline_review_densification_v1"
    manifest = json.loads((artifact_root / "review_densification_manifest.json").read_text(encoding="utf-8"))
    overlay = json.loads((artifact_root / "reviewed_label_overlay.json").read_text(encoding="utf-8"))
    report = json.loads((artifact_root / "review_bundle_report.json").read_text(encoding="utf-8"))
    split_manifest = json.loads((artifact_root / "split_manifest.json").read_text(encoding="utf-8"))
    batch_outcome = json.loads((artifact_root / "batch_outcome_analysis.json").read_text(encoding="utf-8"))
    batch_outcome_md = (artifact_root / "batch_outcome_analysis.md").read_text(encoding="utf-8")
    dataset_yaml = (artifact_root / "yolo_export" / "dataset.yaml").read_text(encoding="utf-8")

    assert result["reviewDensificationBatchName"] == "touchline_review_densification_v1"
    assert result["failingCurationUnitCount"] == 5
    assert result["controlCurationUnitCount"] == 1
    assert result["pendingReviewCount"] == result["reviewItemCount"]
    assert result["pendingFailingReviewCount"] > 0
    assert result["pendingControlReviewCount"] > 0
    assert result["failingSourceReviewComplete"] is False
    assert result["controlReviewComplete"] is False
    assert result["readyForRetraining"] is False
    assert result["nextRecommendedNextLever"] == "start_phase_1b_review_densification"

    assert manifest["representativeFailingMatchId"] == "1c8136cda03240aa8324f676c9bbf99a"
    assert manifest["representativeControlMatchId"] == "1d67fa87080446a0a777901aace43809"
    assert manifest["failingCurationUnitCount"] == 5
    assert manifest["controlCurationUnitCount"] == 1
    assert manifest["selectedAdditionalFailingWindowCount"] == 4
    assert manifest["additionalFailingWindowShortageCount"] == 0
    assert [unit["frameStart"] for unit in manifest["curationUnits"] if unit["sourceClipId"] == "trimed-5min.mp4"] == [
        10,
        20,
        30,
        40,
        50,
    ]
    assert all(unit["labelStatus"] == "seeded_review_required" for unit in manifest["curationUnits"])

    assert overlay["reviewItemCount"] > 0
    assert overlay["pendingReviewCount"] == overlay["reviewItemCount"]
    assert overlay["reviewedPositiveCount"] == 0
    assert overlay["reviewedNegativeCount"] == 0
    assert {item["decision"] for item in overlay["reviewItems"]} == {"pending_review"}
    assert {
        item["seedSource"] for item in overlay["reviewItems"] if item["sourceClipId"] == "trimed-5min.mp4"
    } >= {"accepted_ball", "probe_filtered", "probe_raw", "hard_negative"}

    assert report["seededIssueCount"] == 6
    assert report["reviewBundleCount"] == 2
    assert sorted(report["matches"]) == [
        "1c8136cda03240aa8324f676c9bbf99a",
        "1d67fa87080446a0a777901aace43809",
    ]

    assert split_manifest["sourceAwareSplitLeakageDetected"] is False
    assert split_manifest["splits"]["train"]["curationUnitCount"] == 5
    assert split_manifest["splits"]["val"]["curationUnitCount"] == 1
    assert split_manifest["readyForRetraining"] is False
    assert split_manifest["reviewDensificationPrimaryBlocker"] == "pending_review_items_remaining"

    assert batch_outcome["goalAchieved"] is False
    assert batch_outcome["roadmapAdvanceAllowed"] is False
    assert batch_outcome["readyForRetraining"] is False
    assert batch_outcome["nextRecommendedNextLever"] == "start_phase_1b_review_densification"
    assert batch_outcome["pendingFailingReviewCount"] == result["pendingFailingReviewCount"]
    assert batch_outcome["pendingControlReviewCount"] == result["pendingControlReviewCount"]
    assert batch_outcome["brainstormFixes"]
    assert "did not achieve" in batch_outcome["englishDecision"].lower()
    assert "roadmap" in batch_outcome_md.lower()

    assert "train: images/train" in dataset_yaml
    assert "val: images/val" in dataset_yaml
    assert (artifact_root / "yolo_export" / "labels" / "train" / "1c8136cda03240aa8324f676c9bbf99a__20__f0020.txt").exists()
    assert (artifact_root / "yolo_export" / "labels" / "train" / "1c8136cda03240aa8324f676c9bbf99a__20__f0023.txt").read_text(encoding="utf-8") == ""
    assert len(extracted_frames) >= 20


def test_run_touchline_review_densification_batch_preserves_overlay_edits_and_flips_ready_for_retraining(
    tmp_path,
    monkeypatch,
):
    _seed_phase1_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(
        run_touchline_review_densification_batch,
        "compute_trust_crops",
        lambda frames, assignments, max_crops=20: [
            TrustCrop(frameStart=10, frameEnd=14, timestampStart=0.4, timestampEnd=0.56, score=12.5, reasons=["track_switches"]),
            TrustCrop(frameStart=20, frameEnd=24, timestampStart=0.8, timestampEnd=0.96, score=11.5, reasons=["team_flips"]),
        ][:max_crops],
    )

    def fake_extract_frame_image(*, video_path: Path, frame_id: int, output_path: Path) -> tuple[int, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"img")
        return (100, 50)

    monkeypatch.setattr(
        run_touchline_review_densification_batch,
        "_extract_frame_image",
        fake_extract_frame_image,
    )

    run_touchline_review_densification_batch.run_touchline_review_densification_batch(
        storage_root=tmp_path,
    )

    artifact_root = tmp_path / "training_prep" / "touchline_review_densification_v1"
    overlay_path = artifact_root / "reviewed_label_overlay.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    for item in overlay["reviewItems"]:
        if item["sourceClipId"] != "trimed-5min.mp4":
            continue
        if item["seedSource"] == "hard_negative":
            item["decision"] = "confirm_hard_negative"
        elif item["frameIndex"] == 10:
            item["decision"] = "adjust_bbox"
            item["reviewedBBox"] = {"x1": 20.0, "y1": 10.0, "x2": 40.0, "y2": 30.0}
        else:
            item["decision"] = "accept_seed"
    overlay_path.write_text(json.dumps(overlay, indent=2), encoding="utf-8")

    result = run_touchline_review_densification_batch.run_touchline_review_densification_batch(
        storage_root=tmp_path,
    )
    manifest = json.loads((artifact_root / "review_densification_manifest.json").read_text(encoding="utf-8"))
    overlay_after = json.loads(overlay_path.read_text(encoding="utf-8"))
    batch_outcome = json.loads((artifact_root / "batch_outcome_analysis.json").read_text(encoding="utf-8"))
    adjusted_label = (
        artifact_root / "yolo_export" / "labels" / "train" / "1c8136cda03240aa8324f676c9bbf99a__10__f0010.txt"
    ).read_text(encoding="utf-8").strip()

    assert result["readyForRetraining"] is True
    assert result["pendingFailingReviewCount"] == 0
    assert result["pendingControlReviewCount"] > 0
    assert result["failingSourceReviewComplete"] is True
    assert result["controlReviewComplete"] is False
    assert result["nextRecommendedNextLever"] == "retrain_touchline_detector_candidate"
    assert manifest["pendingReviewCount"] == 4
    assert manifest["pendingFailingReviewCount"] == 0
    assert manifest["pendingControlReviewCount"] == 4
    assert manifest["failingSourceReviewComplete"] is True
    assert manifest["controlReviewComplete"] is False
    assert manifest["readyForRetraining"] is True
    assert manifest["reviewDensificationPrimaryBlocker"] is None
    assert batch_outcome["goalAchieved"] is True
    assert batch_outcome["roadmapAdvanceAllowed"] is True
    assert batch_outcome["nextRecommendedNextLever"] == "retrain_touchline_detector_candidate"
    assert batch_outcome["pendingFailingReviewCount"] == 0
    assert batch_outcome["pendingControlReviewCount"] == 4
    assert any(
        item["decision"] == "adjust_bbox" and item["frameIndex"] == 10 and item["reviewedBBox"]["x1"] == 20.0
        for item in overlay_after["reviewItems"]
    )
    assert adjusted_label == "0 0.300000 0.400000 0.200000 0.400000"


def test_run_touchline_review_densification_batch_reports_overlay_validation_failures(
    tmp_path,
    monkeypatch,
):
    _seed_phase1_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(
        run_touchline_review_densification_batch,
        "compute_trust_crops",
        lambda frames, assignments, max_crops=20: [
            TrustCrop(frameStart=10, frameEnd=14, timestampStart=0.4, timestampEnd=0.56, score=12.5, reasons=["track_switches"]),
            TrustCrop(frameStart=20, frameEnd=24, timestampStart=0.8, timestampEnd=0.96, score=11.5, reasons=["team_flips"]),
        ][:max_crops],
    )

    def fake_extract_frame_image(*, video_path: Path, frame_id: int, output_path: Path) -> tuple[int, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"img")
        return (100, 50)

    monkeypatch.setattr(
        run_touchline_review_densification_batch,
        "_extract_frame_image",
        fake_extract_frame_image,
    )

    run_touchline_review_densification_batch.run_touchline_review_densification_batch(
        storage_root=tmp_path,
    )

    artifact_root = tmp_path / "training_prep" / "touchline_review_densification_v1"
    overlay_path = artifact_root / "reviewed_label_overlay.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    failing_items = [item for item in overlay["reviewItems"] if item["sourceClipId"] == "trimed-5min.mp4"]
    failing_items[0]["decision"] = "adjust_bbox"
    failing_items[0]["reviewedBBox"] = None
    failing_items[1]["decision"] = "not_a_real_decision"
    overlay_path.write_text(json.dumps(overlay, indent=2), encoding="utf-8")

    result = run_touchline_review_densification_batch.run_touchline_review_densification_batch(
        storage_root=tmp_path,
    )
    manifest = json.loads((artifact_root / "review_densification_manifest.json").read_text(encoding="utf-8"))
    batch_outcome = json.loads((artifact_root / "batch_outcome_analysis.json").read_text(encoding="utf-8"))

    assert result["readyForRetraining"] is False
    assert result["reviewDensificationPrimaryBlocker"] == "overlay_validation_failed"
    assert manifest["overlayValidationErrorCount"] == 2
    assert len(manifest["overlayValidationErrors"]) == 2
    assert {
        error["reason"] for error in manifest["overlayValidationErrors"]
    } == {
        "adjust_bbox_requires_reviewed_bbox",
        "unknown_review_decision",
    }
    assert batch_outcome["goalAchieved"] is False
    assert batch_outcome["roadmapAdvanceAllowed"] is False
    assert batch_outcome["primaryBlocker"] == "overlay_validation_failed"
    assert batch_outcome["brainstormFixes"]
