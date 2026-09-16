from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchSummary
from backend.app.storage import Storage
import backend.scripts.run_source_robustness_batch as run_source_robustness_batch


COMPACT_SOURCE_ROBUSTNESS_FIELDS = (
    "sourceRobustnessActiveConfigName",
    "sourceRobustnessBestConfigName",
    "sourceRobustnessBestExploratoryConfigName",
    "sourceRobustnessOutcome",
    "sourceRobustnessDominantFailureSignal",
    "sourceRobustnessImprovedSourceClipId",
    "sourceRobustnessRecommendedNextLever",
    "sourceRobustnessPromotionBlockers",
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


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_compact_source_robustness_fields(payload: dict[str, object], expected: dict[str, object]) -> None:
    for field_name, expected_value in expected.items():
        assert payload[field_name] == expected_value


def _disable_combined_reopen_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_source_robustness_batch,
        "_run_combined_reopen_matrix",
        lambda **_kwargs: None,
    )


def _write_source_match(
    storage: Storage,
    match_id: str,
    *,
    source_clip_id: str,
    video_path: str,
    accepted_frame_ids: list[int],
    edge_frame_ids: set[int],
    controlled_frame_ids: set[int],
    frame_count: int = 20,
    supported_player_frame_ids: set[int] | None = None,
    frame_id_offset: int = 0,
    probe_filtered_ball_rows: list[dict[str, object]] | None = None,
    probe_raw_ball_rows: list[dict[str, object]] | None = None,
) -> None:
    accepted_rows: list[dict[str, object]] = []
    raw_rows: list[dict[str, object]] = []
    frames: list[FrameData] = []
    assignments: list[BallOwnership] = []
    supported_player_frame_ids = set(supported_player_frame_ids or set())

    for frame_id in range(frame_count):
        actual_frame_id = frame_id_offset + frame_id
        is_accepted = frame_id in accepted_frame_ids
        is_edge = frame_id in edge_frame_ids
        x = 2.0 if is_edge else 50.0
        y = 96.0 if is_edge else 45.0
        if is_accepted:
            accepted_rows.append(
                {
                    "Entity_Type": "ball",
                    "Frame_ID": actual_frame_id,
                    "Timestamp": round(frame_id * 0.2, 3),
                    "Track_ID": -1,
                    "X": x,
                    "Y": y,
                }
            )
            raw_rows.append(
                {
                    "Entity_Type": "ball",
                    "Frame_ID": actual_frame_id,
                    "Timestamp": round(frame_id * 0.2, 3),
                    "Track_ID": -1,
                    "X": x,
                    "Y": y,
                }
            )
        if frame_id in supported_player_frame_ids:
            raw_rows.append(
                {
                    "Entity_Type": "player",
                    "Frame_ID": actual_frame_id,
                    "Timestamp": round(frame_id * 0.2, 3),
                    "Track_ID": 7,
                    "X": x + 0.5,
                    "Y": y - 0.5,
                }
            )
        frames.append(
            FrameData(
                frameId=actual_frame_id,
                timestamp=round(frame_id * 0.2, 3),
                ball={"x": x, "y": y, "confidence": 0.9} if is_accepted else None,
            )
        )
        if frame_id in controlled_frame_ids:
            assignments.append(
                BallOwnership(
                    frameId=actual_frame_id,
                    timestamp=round(frame_id * 0.2, 3),
                    team="my_team",
                    trackId=7,
                    distance=1.0,
                )
            )

    storage.save_raw_rows(match_id, raw_rows)
    storage.save_frames(match_id, frames)
    storage.save_analytics(match_id, _summary(), assignments=assignments, formation_timeline=[], shots=[])
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
            "observedBall": {"summary": {"frameCount": len(accepted_rows)}},
            "inferredBall": {"summary": {"frameCount": 0}},
            "acceptedBall": {
                "summary": {"frameCount": len(accepted_rows)},
                "rows": accepted_rows,
            },
            "acceptedSegments": [{"frameCount": len(accepted_rows)}],
            "unknownGaps": [],
            "probeObservedBall": {
                "filteredRows": [dict(row) for row in (probe_filtered_ball_rows or [])],
                "rawRows": [dict(row) for row in (probe_raw_ball_rows or probe_filtered_ball_rows or [])],
            },
            "directObservationBreakdown": {
                "longGapTreatmentOutcome": "long_gap_treatment_partial",
                "controlledPossessionAssignmentOutcome": "controlled_possession_assignment_weak",
                "frozenPrimaryAcquisitionMode": "anchored_player_ranked_context_960",
                "frozenDetectorModelPath": "yolov10n.pt",
            },
            "summary": {
                "fiveMinuteTruthReady": False,
                "truthGateReasons": [
                    "Need at least 60 frame time samples for truthful 5-minute analysis",
                ],
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
            "sourceClipId": source_clip_id,
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
            "acceptedBallFrames": len(accepted_rows),
            "controlledPossessionFrames": len(controlled_frame_ids),
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": round(len(edge_frame_ids) / len(accepted_rows), 3),
            "fiveMinuteTruthReady": False,
            "truthGateReasons": [
                "Need at least 60 frame time samples for truthful 5-minute analysis",
            ],
        },
    )


def _write_realistic_source_robustness_suite(
    storage: Storage,
    manifest_path,
) -> None:
    entries: list[dict[str, object]] = []
    for index in range(4):
        match_id = f"failing-{index}"
        _write_source_match(
            storage,
            match_id,
            source_clip_id="trimed-5min.mp4",
            video_path="/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
            accepted_frame_ids=list(range(16)),
            edge_frame_ids=set(range(12)),
            controlled_frame_ids=set(range(16)),
        )
        entries.append(
            {
                "entryId": match_id,
                "label": match_id,
                "sourceType": "saved_match_artifacts",
                "matchId": match_id,
                "sourceClipId": "trimed-5min.mp4",
                "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
                "notes": "",
                "tags": ["slice"],
            }
        )

    control_match_id = "control-0"
    _write_source_match(
        storage,
        control_match_id,
        source_clip_id="trimed-football-2-1minute.mp4",
        video_path="/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
        accepted_frame_ids=list(range(12)),
        edge_frame_ids=set(),
        controlled_frame_ids=set(range(12)),
    )
    entries.append(
        {
            "entryId": control_match_id,
            "label": control_match_id,
            "sourceType": "saved_match_artifacts",
            "matchId": control_match_id,
            "sourceClipId": "trimed-football-2-1minute.mp4",
            "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
            "notes": "",
            "tags": ["slice"],
        }
    )

    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
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


def _write_plateau_source_robustness_suite(
    storage: Storage,
    manifest_path,
) -> None:
    entries: list[dict[str, object]] = []
    for index in range(9):
        match_id = f"plateau-failing-{index}"
        _write_source_match(
            storage,
            match_id,
            source_clip_id="trimed-5min.mp4",
            video_path="/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
            accepted_frame_ids=list(range(13)),
            edge_frame_ids=set(range(10)),
            controlled_frame_ids={0, 2, 4, 6, 8, 9, 10},
            frame_count=60,
        )
        entries.append(
            {
                "entryId": match_id,
                "label": match_id,
                "sourceType": "saved_match_artifacts",
                "matchId": match_id,
                "sourceClipId": "trimed-5min.mp4",
                "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
                "notes": "",
                "tags": ["slice"],
            }
        )

    control_match_id = "plateau-control-0"
    _write_source_match(
        storage,
        control_match_id,
        source_clip_id="trimed-football-2-1minute.mp4",
        video_path="/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
        accepted_frame_ids=list(range(12)),
        edge_frame_ids=set(),
        controlled_frame_ids=set(range(12)),
        frame_count=60,
    )
    entries.append(
        {
            "entryId": control_match_id,
            "label": control_match_id,
            "sourceType": "saved_match_artifacts",
            "matchId": control_match_id,
            "sourceClipId": "trimed-football-2-1minute.mp4",
            "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
            "notes": "",
            "tags": ["slice"],
        }
    )

    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "plateau-suite",
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


def test_evaluate_source_robustness_outcome_maps_strong_partial_and_weak():
    strong = run_source_robustness_batch.evaluate_source_robustness_outcome(
        baseline_suite_verdict="baseline_not_robust",
        candidate_suite_verdict="viable_but_coverage_limited",
        canonical_proof_floor_intact=True,
        failing_source_baseline={"medianBallTrackEdgeFrameShare": 0.82},
        failing_source_candidate={
            "medianBallTrackEdgeFrameShare": 0.56,
            "sourceViable": True,
            "medianAcceptedRetentionRatio": 0.78,
            "medianControlledRetentionRatio": 0.75,
        },
    )
    partial = run_source_robustness_batch.evaluate_source_robustness_outcome(
        baseline_suite_verdict="baseline_not_robust",
        candidate_suite_verdict="baseline_not_robust",
        canonical_proof_floor_intact=True,
        failing_source_baseline={"medianBallTrackEdgeFrameShare": 0.82},
        failing_source_candidate={
            "medianBallTrackEdgeFrameShare": 0.72,
            "sourceViable": False,
            "medianAcceptedRetentionRatio": 0.72,
            "medianControlledRetentionRatio": 0.68,
        },
    )
    weak = run_source_robustness_batch.evaluate_source_robustness_outcome(
        baseline_suite_verdict="baseline_not_robust",
        candidate_suite_verdict="dataset_too_narrow",
        canonical_proof_floor_intact=True,
        failing_source_baseline={"medianBallTrackEdgeFrameShare": 0.82},
        failing_source_candidate={
            "medianBallTrackEdgeFrameShare": 0.56,
            "sourceViable": True,
            "medianAcceptedRetentionRatio": 0.42,
            "medianControlledRetentionRatio": 0.39,
        },
    )

    assert strong == {
        "configOutcome": "source_robustness_strong",
        "sourceRobustnessOutcome": "source_robustness_strong",
        "sourceRobustnessRecommendedNextLever": "promote_source_conditioned_edge_share_repair",
        "failingSourceEdgeShareImprovement": 0.26,
        "passedPromotionGate": True,
        "promotionBlockers": [],
    }
    assert partial == {
        "configOutcome": "source_robustness_partial",
        "sourceRobustnessOutcome": "source_robustness_partial",
        "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
        "failingSourceEdgeShareImprovement": 0.1,
        "passedPromotionGate": False,
        "promotionBlockers": ["failing_source_not_viable"],
    }
    assert weak == {
        "configOutcome": "source_robustness_weak",
        "sourceRobustnessOutcome": "source_robustness_weak",
        "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
        "failingSourceEdgeShareImprovement": 0.26,
        "passedPromotionGate": False,
        "promotionBlockers": [
            "suite_verdict_regressed",
            "accepted_retention_below_guardrail",
            "controlled_retention_below_guardrail",
        ],
    }


@pytest.mark.parametrize(
    ("forced_outcome", "expected_best_config_name", "expected_best_exploratory_config_name"),
    [
        (
            {
                "configOutcome": "source_robustness_strong",
                "sourceRobustnessOutcome": "source_robustness_strong",
                "sourceRobustnessRecommendedNextLever": "promote_source_conditioned_edge_share_repair",
                "failingSourceEdgeShareImprovement": 0.123,
                "passedPromotionGate": True,
                "promotionBlockers": [],
            },
            "shadow_test",
            "shadow_test",
        ),
        (
            {
                "configOutcome": "source_robustness_partial",
                "sourceRobustnessOutcome": "source_robustness_partial",
                "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
                "failingSourceEdgeShareImprovement": 0.123,
                "passedPromotionGate": False,
                "promotionBlockers": ["failing_source_not_viable"],
            },
            "shadow_test",
            "shadow_test",
        ),
        (
            {
                "configOutcome": "source_robustness_weak",
                "sourceRobustnessOutcome": "source_robustness_weak",
                "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
                "failingSourceEdgeShareImprovement": 0.123,
                "passedPromotionGate": False,
                "promotionBlockers": [
                    "accepted_retention_below_guardrail",
                    "controlled_retention_below_guardrail",
                ],
            },
            None,
            "shadow_test",
        ),
    ],
)
def test_run_source_robustness_batch_writes_consistent_compact_fields_for_each_outcome(
    tmp_path,
    monkeypatch,
    forced_outcome,
    expected_best_config_name,
    expected_best_exploratory_config_name,
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)

    monkeypatch.setattr(
        run_source_robustness_batch,
        "SHADOW_CONFIGS",
        {
            "shadow_test": {
                "keepEvery": 2,
                "minRunLength": 10,
            }
        },
    )
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: dict(forced_outcome),
    )
    _disable_combined_reopen_matrix(monkeypatch)

    run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    expected_compact_fields = {
        "sourceRobustnessActiveConfigName": run_source_robustness_batch.BASELINE_CONFIG_NAME,
        "sourceRobustnessBestConfigName": expected_best_config_name,
        "sourceRobustnessBestExploratoryConfigName": expected_best_exploratory_config_name,
        "sourceRobustnessOutcome": forced_outcome["sourceRobustnessOutcome"],
        "sourceRobustnessDominantFailureSignal": "high_ball_track_edge_frame_share",
        "sourceRobustnessImprovedSourceClipId": "trimed-5min.mp4",
        "sourceRobustnessRecommendedNextLever": forced_outcome["sourceRobustnessRecommendedNextLever"],
        "sourceRobustnessPromotionBlockers": forced_outcome["promotionBlockers"],
    }

    for artifact_name in (
        "suite_summary.json",
        "suite_robustness_diagnosis.json",
        "primary_source_robustness_matrix.json",
        "primary_source_robustness_source_audit.json",
        "primary_source_robustness_slice_projection.json",
        "active_lane_snapshot.json",
    ):
        payload = _load_json(output_dir / artifact_name)
        _assert_compact_source_robustness_fields(payload, expected_compact_fields)

    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")
    assert active_lane_snapshot["activeConfig"]["configName"] == run_source_robustness_batch.BASELINE_CONFIG_NAME
    assert active_lane_snapshot["bestExploratoryConfig"]["configName"] == expected_best_exploratory_config_name
    if expected_best_config_name is None:
        assert active_lane_snapshot["bestQualifyingConfig"] is None
    else:
        assert active_lane_snapshot["bestQualifyingConfig"]["configName"] == expected_best_config_name


def test_run_source_robustness_batch_writes_artifacts_and_updates_suite_surfaces(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )

    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    matrix = json.loads((output_dir / "primary_source_robustness_matrix.json").read_text(encoding="utf-8"))
    source_audit = json.loads((output_dir / "primary_source_robustness_source_audit.json").read_text(encoding="utf-8"))
    slice_projection = json.loads((output_dir / "primary_source_robustness_slice_projection.json").read_text(encoding="utf-8"))
    frontier = json.loads((output_dir / "primary_source_robustness_frontier.json").read_text(encoding="utf-8"))
    failure_audit = json.loads((output_dir / "primary_source_robustness_failure_audit.json").read_text(encoding="utf-8"))
    suite_summary = json.loads((output_dir / "suite_summary.json").read_text(encoding="utf-8"))
    robustness_diagnosis = json.loads((output_dir / "suite_robustness_diagnosis.json").read_text(encoding="utf-8"))
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")

    compact_fields = {
        field_name: result[field_name]
        for field_name in COMPACT_SOURCE_ROBUSTNESS_FIELDS
    }

    assert result["sourceRobustnessActiveConfigName"] == run_source_robustness_batch.BASELINE_CONFIG_NAME
    assert result["sourceRobustnessBestConfigName"] == "source_robustness_shadow_edge_run_keep_every_2_min10"
    assert result["sourceRobustnessBestExploratoryConfigName"] == "source_robustness_shadow_edge_run_keep_every_3_min11"
    assert result["sourceRobustnessOutcome"] == "source_robustness_strong"
    assert result["sourceRobustnessPromotionBlockers"] == []
    assert frontier["plateauDetected"] is False
    assert frontier["exploratoryStrongConfigCount"] >= 1
    assert frontier["bestFrontierConfigName"] is not None
    assert failure_audit["failingSourceClipId"] == "trimed-5min.mp4"
    assert set(failure_audit["configs"]) == {
        run_source_robustness_batch.BASELINE_CONFIG_NAME,
        "source_robustness_shadow_edge_run_keep_every_2_min10",
        "source_robustness_shadow_edge_run_keep_every_3_min11",
        "source_robustness_shadow_touchline_probe_replace_v1",
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    }
    assert matrix["canonicalProofFloor"]["intact"] is True
    assert source_audit["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]["suiteVerdict"] == "baseline_not_robust"
    assert (
        source_audit["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]["sourceSummaries"]["trimed-5min.mp4"]["medianBallTrackEdgeFrameShare"]
        < source_audit["configs"]["source_robustness_baseline_current"]["sourceSummaries"]["trimed-5min.mp4"]["medianBallTrackEdgeFrameShare"]
    )
    assert matrix["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]["configOutcome"] == "source_robustness_strong"
    assert matrix["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]["passedPromotionGate"] is True
    assert matrix["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]["promotionBlockers"] == []
    assert matrix["configs"]["source_robustness_shadow_edge_run_keep_every_3_min10"]["configOutcome"] == "source_robustness_weak"
    assert matrix["configs"]["source_robustness_shadow_edge_run_keep_every_3_min10"]["passedPromotionGate"] is False
    assert matrix["configs"]["source_robustness_shadow_edge_run_keep_every_3_min10"]["promotionBlockers"] == [
        "accepted_retention_below_guardrail",
        "controlled_retention_below_guardrail",
    ]
    assert (
        matrix["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]["failingSourceMedianAcceptedRetentionRatio"]
        >= 0.60
    )
    assert (
        matrix["configs"]["source_robustness_shadow_edge_run_keep_every_3_min10"]["failingSourceMedianAcceptedRetentionRatio"]
        < 0.60
    )
    shadow_rows = slice_projection["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]["rows"]
    control_shadow_row = next(row for row in shadow_rows if row["sourceClipId"] == "trimed-football-2-1minute.mp4")
    assert control_shadow_row["edgeRunThinningApplied"] is False
    failing_shadow_row = next(row for row in shadow_rows if row["sourceClipId"] == "trimed-5min.mp4")
    assert failing_shadow_row["acceptedRetentionRatio"] >= 0.60
    assert failing_shadow_row["controlledRetentionRatio"] >= 0.60
    assert suite_summary["sourceRobustnessBestConfigName"] == "source_robustness_shadow_edge_run_keep_every_2_min10"
    assert suite_summary["sourceRobustnessOutcome"] == "source_robustness_strong"
    assert robustness_diagnosis["sourceRobustnessRecommendedNextLever"] == "promote_source_conditioned_edge_share_repair"
    _assert_compact_source_robustness_fields(matrix, compact_fields)
    _assert_compact_source_robustness_fields(source_audit, compact_fields)
    _assert_compact_source_robustness_fields(slice_projection, compact_fields)
    _assert_compact_source_robustness_fields(suite_summary, compact_fields)
    _assert_compact_source_robustness_fields(robustness_diagnosis, compact_fields)
    _assert_compact_source_robustness_fields(active_lane_snapshot, compact_fields)
    assert active_lane_snapshot["canonicalProofFloor"]["intact"] is True
    assert active_lane_snapshot["suiteVerdict"] == suite_summary["suiteVerdict"]
    assert active_lane_snapshot["suiteRecommendedNextLever"] == suite_summary["suiteRecommendedNextLever"]
    assert active_lane_snapshot["activeConfig"]["configName"] == run_source_robustness_batch.BASELINE_CONFIG_NAME
    assert active_lane_snapshot["bestQualifyingConfig"]["configName"] == "source_robustness_shadow_edge_run_keep_every_2_min10"
    assert active_lane_snapshot["bestExploratoryConfig"]["configName"] == "source_robustness_shadow_edge_run_keep_every_3_min11"
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["plateauDetected"] is False
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["bestFrontierConfigName"] == frontier["bestFrontierConfigName"]
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["exploratoryStrongConfigCount"] == frontier["exploratoryStrongConfigCount"]
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["exploratoryPartialConfigCount"] == frontier["exploratoryPartialConfigCount"]
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["touchlineReplacementCandidateName"] == (
        "source_robustness_shadow_touchline_probe_replace_v1"
    )
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["touchlineReplacementFalsified"] is True
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateName"] == (
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3"
    )
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateBeatsBestThinCandidate"] is False
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateFalsified"] is True
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateWindowKindCounts"] == {}
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateRejectionBlockerCounts"] == {}


def test_run_source_robustness_batch_writes_plateau_diagnosis_for_current_shape(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )

    _write_plateau_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "plateau-suite"
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")
    frontier = _load_json(output_dir / "primary_source_robustness_frontier.json")
    failure_audit = _load_json(output_dir / "primary_source_robustness_failure_audit.json")
    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")

    compact_fields = {
        field_name: result[field_name]
        for field_name in COMPACT_SOURCE_ROBUSTNESS_FIELDS
    }

    assert result["sourceRobustnessActiveConfigName"] == run_source_robustness_batch.BASELINE_CONFIG_NAME
    assert result["sourceRobustnessBestConfigName"] == "source_robustness_shadow_edge_run_keep_every_2_min10"
    assert result["sourceRobustnessBestExploratoryConfigName"] == "source_robustness_shadow_edge_run_keep_every_3_min10"
    assert result["sourceRobustnessOutcome"] == "source_robustness_partial"
    assert result["sourceRobustnessPromotionBlockers"] == ["failing_source_not_viable"]
    _assert_compact_source_robustness_fields(suite_summary, compact_fields)
    _assert_compact_source_robustness_fields(robustness_diagnosis, compact_fields)
    _assert_compact_source_robustness_fields(active_lane_snapshot, compact_fields)
    assert active_lane_snapshot["suiteVerdict"] == "baseline_not_robust"
    assert active_lane_snapshot["suiteEntryCount"] == 10
    assert active_lane_snapshot["distinctSourceClipCount"] == 2
    assert active_lane_snapshot["activeConfig"]["configName"] == run_source_robustness_batch.BASELINE_CONFIG_NAME
    assert active_lane_snapshot["bestQualifyingConfig"]["configName"] == "source_robustness_shadow_edge_run_keep_every_2_min10"
    assert active_lane_snapshot["bestExploratoryConfig"]["configName"] == "source_robustness_shadow_edge_run_keep_every_3_min10"
    assert frontier["exploratoryStrongConfigCount"] == 0
    assert frontier["plateauDetected"] is True
    assert frontier["bestFrontierConfigName"] == "source_robustness_frontier_keep_every_4_min14"
    assert frontier["bestQualifyingConfigName"] == "source_robustness_shadow_edge_run_keep_every_2_min10"
    assert frontier["bestExploratoryConfigName"] == "source_robustness_shadow_edge_run_keep_every_3_min10"
    assert failure_audit["failingSourceClipId"] == "trimed-5min.mp4"
    assert set(failure_audit["configs"]) == {
        run_source_robustness_batch.BASELINE_CONFIG_NAME,
        "source_robustness_shadow_edge_run_keep_every_2_min10",
        "source_robustness_shadow_edge_run_keep_every_3_min10",
        "source_robustness_shadow_touchline_probe_replace_v1",
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    }
    selected_truth_gate_counts = active_lane_snapshot["sourceRobustnessDiagnosis"]["selectedConfigTruthGateCounts"]
    assert selected_truth_gate_counts["Accepted ball layer is still too sparse for truthful 5-10 minute analysis"] == 9
    assert selected_truth_gate_counts["Need controlled possession frames/frameCount >= 20% for truthful 5-10 minute analysis"] == 9
    assert selected_truth_gate_counts["Need viable ball track: meaningful motion and edgeFrameShare <= 60%"] == 9
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["selectedConfigPrimaryBlocker"] == (
        "Accepted ball layer is still too sparse for truthful 5-10 minute analysis"
    )
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["touchlineReplacementCandidateName"] == (
        "source_robustness_shadow_touchline_probe_replace_v1"
    )
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["touchlineReplacementFalsified"] is True
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateName"] == (
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3"
    )
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateBeatsBestThinCandidate"] is False
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateFalsified"] is True
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateWindowKindCounts"] == {}
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["acquisitionCandidateRejectionBlockerCounts"] == {}
    qualifying_failure_config = failure_audit["configs"]["source_robustness_shadow_edge_run_keep_every_2_min10"]
    assert qualifying_failure_config["truthGateCounts"]["Accepted ball layer is still too sparse for truthful 5-10 minute analysis"] == 9
    assert qualifying_failure_config["truthGateCounts"]["Need controlled possession frames/frameCount >= 20% for truthful 5-10 minute analysis"] == 9
    assert qualifying_failure_config["truthGateCounts"]["Need viable ball track: meaningful motion and edgeFrameShare <= 60%"] == 9
    first_slice = qualifying_failure_config["sliceDiagnostics"][0]
    assert list(first_slice["topLongestEdgeRuns"][0]) == [
        "startFrame",
        "endFrame",
        "runLength",
        "keptFrameCount",
        "droppedFrameCount",
    ]
    assert first_slice["topLongestEdgeRuns"] == sorted(
        first_slice["topLongestEdgeRuns"],
        key=lambda run: run["runLength"],
        reverse=True,
    )


def test_run_source_robustness_batch_support_aware_profiles_record_preservation_metrics(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )

    entries = []
    for index in range(4):
        match_id = f"supported-failing-{index}"
        _write_source_match(
            storage,
            match_id,
            source_clip_id="trimed-5min.mp4",
            video_path="/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
            accepted_frame_ids=list(range(16)),
            edge_frame_ids=set(range(12)),
            controlled_frame_ids=set(range(16)),
            frame_count=20,
            supported_player_frame_ids={4, 6},
        )
        entries.append(
            {
                "entryId": match_id,
                "label": match_id,
                "sourceType": "saved_match_artifacts",
                "matchId": match_id,
                "sourceClipId": "trimed-5min.mp4",
                "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
                "notes": "",
                "tags": ["slice"],
            }
        )

    control_match_id = "supported-control-0"
    _write_source_match(
        storage,
        control_match_id,
        source_clip_id="trimed-football-2-1minute.mp4",
        video_path="/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
        accepted_frame_ids=list(range(12)),
        edge_frame_ids=set(),
        controlled_frame_ids=set(range(12)),
        frame_count=20,
    )
    entries.append(
        {
            "entryId": control_match_id,
            "label": control_match_id,
            "sourceType": "saved_match_artifacts",
            "matchId": control_match_id,
            "sourceClipId": "trimed-football-2-1minute.mp4",
            "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
            "notes": "",
            "tags": ["slice"],
        }
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "supported-suite",
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

    support_aware_name = "source_robustness_shadow_supported_edge_run_keep_every_2_min10_guard2"
    monkeypatch.setattr(
        run_source_robustness_batch,
        "SHADOW_CONFIGS",
        {
            support_aware_name: {
                "mode": "support_guarded_thin",
                "keepEvery": 2,
                "minRunLength": 10,
                "guardFrameCount": 2,
            }
        },
    )
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.111,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )
    _disable_combined_reopen_matrix(monkeypatch)

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "supported-suite"
    slice_projection = _load_json(output_dir / "primary_source_robustness_slice_projection.json")
    failure_audit = _load_json(output_dir / "primary_source_robustness_failure_audit.json")
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessBestConfigName"] == support_aware_name
    support_projection_rows = slice_projection["configs"][support_aware_name]["rows"]
    failing_projection_row = next(row for row in support_projection_rows if row["sourceClipId"] == "trimed-5min.mp4")
    assert failing_projection_row["preservedBoundaryFrames"] == 4
    assert failing_projection_row["preservedSupportedFrames"] == 2
    assert failing_projection_row["preservedBridgeFrames"] == 1
    assert failing_projection_row["droppedInteriorUnsupportedFrames"] == 2
    assert failing_projection_row["supportedAcceptedBallRatio"] == 0.143
    assert failing_projection_row["unsupportedAcceptedEdgeFrames"] == 8

    support_failure_audit = failure_audit["configs"][support_aware_name]
    assert support_failure_audit["configOutcome"] == "source_robustness_partial"
    first_slice = support_failure_audit["sliceDiagnostics"][0]
    assert first_slice["preservedBoundaryFrames"] == 4
    assert first_slice["preservedSupportedFrames"] == 2
    assert first_slice["preservedBridgeFrames"] == 1
    assert first_slice["droppedInteriorUnsupportedFrames"] == 2
    assert first_slice["supportedAcceptedBallRatio"] == 0.143
    assert first_slice["unsupportedAcceptedEdgeFrames"] == 8

    selected_summary = active_lane_snapshot["selectedConfig"]["failingSourceSummary"]
    assert selected_summary["medianPreservedBoundaryFrames"] == 4.0
    assert selected_summary["medianPreservedSupportedFrames"] == 2.0
    assert selected_summary["medianPreservedBridgeFrames"] == 1.0
    assert selected_summary["medianDroppedInteriorUnsupportedFrames"] == 2.0
    assert selected_summary["medianSupportedAcceptedBallRatio"] == 0.143
    assert selected_summary["medianUnsupportedAcceptedEdgeFrames"] == 8.0


def test_run_source_robustness_batch_writes_touchline_replacement_falsification_signal(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )

    entries = []
    accepted_frame_ids = list(range(12))
    edge_frame_ids = set(range(10))
    probe_rows = [
        {
            "Entity_Type": "ball",
            "Frame_ID": 340 + frame_id,
            "Timestamp": round(frame_id * 0.2, 3),
            "Track_ID": -1,
            "X": 2.0,
            "Y": 96.0,
        }
        for frame_id in range(10)
    ]
    for index in range(4):
        match_id = f"touchline-failing-{index}"
        _write_source_match(
            storage,
            match_id,
            source_clip_id="trimed-5min.mp4",
            video_path="/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
            accepted_frame_ids=accepted_frame_ids,
            edge_frame_ids=edge_frame_ids,
            controlled_frame_ids=set(accepted_frame_ids),
            frame_count=60,
            frame_id_offset=340,
            supported_player_frame_ids=edge_frame_ids,
            probe_filtered_ball_rows=probe_rows,
            probe_raw_ball_rows=probe_rows,
        )
        entries.append(
            {
                "entryId": match_id,
                "label": match_id,
                "sourceType": "saved_match_artifacts",
                "matchId": match_id,
                "sourceClipId": "trimed-5min.mp4",
                "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
                "notes": "",
                "tags": ["slice"],
            }
        )

    control_match_id = "touchline-control-0"
    _write_source_match(
        storage,
        control_match_id,
        source_clip_id="trimed-football-2-1minute.mp4",
        video_path="/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
        accepted_frame_ids=list(range(12)),
        edge_frame_ids=set(),
        controlled_frame_ids=set(range(12)),
        frame_count=60,
    )
    entries.append(
        {
            "entryId": control_match_id,
            "label": control_match_id,
            "sourceType": "saved_match_artifacts",
            "matchId": control_match_id,
            "sourceClipId": "trimed-football-2-1minute.mp4",
            "videoPath": "/root/WorkSpace/fotball-analyst/videos/trimed-football-2-1minute.mp4",
            "notes": "",
            "tags": ["slice"],
        }
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "touchline-suite",
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
        run_source_robustness_batch,
        "SHADOW_CONFIGS",
        {
            "source_robustness_shadow_edge_run_keep_every_2_min10": {
                "mode": "uniform_edge_run_thin",
                "keepEvery": 2,
                "minRunLength": 10,
                "guardFrameCount": 0,
            },
            "source_robustness_shadow_edge_run_keep_every_3_min10": {
                "mode": "uniform_edge_run_thin",
                "keepEvery": 3,
                "minRunLength": 10,
                "guardFrameCount": 0,
            },
            "source_robustness_shadow_touchline_probe_replace_v1": {
                "mode": "touchline_probe_replace",
                "keepEvery": 0,
                "minRunLength": 10,
                "guardFrameCount": 0,
            },
        },
    )
    _disable_combined_reopen_matrix(monkeypatch)

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "touchline-suite"
    failure_audit = _load_json(output_dir / "primary_source_robustness_failure_audit.json")
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessBestConfigName"] == "source_robustness_shadow_edge_run_keep_every_2_min10"
    assert set(failure_audit["configs"]) == {
        run_source_robustness_batch.BASELINE_CONFIG_NAME,
        "source_robustness_shadow_edge_run_keep_every_2_min10",
        "source_robustness_shadow_edge_run_keep_every_3_min10",
        "source_robustness_shadow_touchline_probe_replace_v1",
    }
    touchline_config = failure_audit["configs"]["source_robustness_shadow_touchline_probe_replace_v1"]
    assert touchline_config["configOutcome"] == "source_robustness_weak"
    assert touchline_config["replacementRunsConsidered"] == 4
    assert touchline_config["replacementRunsAccepted"] == 0
    assert touchline_config["replacementRunsRejected"] == 4
    assert touchline_config["replacementRejectionBlockerCounts"] == {
        "candidate_edge_share_improvement_insufficient": 4
    }
    first_slice = touchline_config["sliceDiagnostics"][0]
    assert first_slice["replacementRunsConsidered"] == 1
    assert first_slice["replacementRunsAccepted"] == 0
    assert first_slice["replacementRunsRejected"] == 1
    assert first_slice["replacementRunDiagnostics"][0]["candidateSourceUsed"] == "probeObservedBall.filteredRows"
    assert first_slice["replacementRunDiagnostics"][0]["rejectionReason"] == "candidate_edge_share_improvement_insufficient"
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["touchlineReplacementCandidateName"] == (
        "source_robustness_shadow_touchline_probe_replace_v1"
    )
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["touchlineReplacementFalsified"] is True
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["touchlineReplacementBeatsBestThinCandidate"] is False


def test_shadow_projection_row_uses_stored_acquisition_diagnostics_without_repair_surrogate(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    match_id = "acquisition-stored"
    _write_source_match(
        storage,
        match_id,
        source_clip_id="trimed-5min.mp4",
        video_path="/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
        accepted_frame_ids=list(range(12)),
        edge_frame_ids=set(range(10)),
        controlled_frame_ids=set(range(12)),
        frame_count=60,
    )
    ball_truth_layers = storage.load_analysis_artifact(match_id, "ball_truth_layers")
    ball_truth_layers["sourceConditionedAcquisitionDiagnostics"] = {
        "applied": True,
        "profileName": "source_robustness_shadow_touchline_acquisition_upgrade_v1",
        "mode": "touchline_acquisition_upgrade",
        "sourceClipId": "trimed-5min.mp4",
        "selectedAcquisitionProfileName": "source_robustness_shadow_touchline_acquisition_upgrade_v1",
        "proposalWindowKindCandidateCounts": {
            "direct_seed_tight": 4,
            "touchline_escape": 4,
        },
        "proposalWindowKindSelectedCounts": {
            "touchline_escape": 3,
        },
        "touchlineEscapeCandidateFrames": 4,
        "touchlineEscapeSelectedFrames": 3,
        "edgeStuckCandidateRejectionCounts": {
            "continuity_rejected": 1,
        },
        "repeatedAnchorSuppressionCount": 2,
        "candidateSourceEdgeShareBeforeSelection": 1.0,
        "candidateSourceEdgeShareAfterSelection": 0.5,
    }
    storage.save_analysis_artifact(match_id, "ball_truth_layers", ball_truth_layers)

    monkeypatch.setattr(
        run_source_robustness_batch,
        "apply_source_conditioned_edge_share_repair",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("repair surrogate should not run")),
    )

    summary = run_source_robustness_batch.summarize_match_benchmark(storage, match_id)
    projection_row = run_source_robustness_batch._shadow_projection_row(
        storage,
        {
            "entryId": match_id,
            "label": match_id,
            "matchId": match_id,
            "sourceClipId": "trimed-5min.mp4",
        },
        summary,
        config_name="source_robustness_shadow_touchline_acquisition_upgrade_v1",
    )

    assert projection_row["acceptedBallFrames"] == 12
    assert projection_row["controlledPossessionFrames"] == 12
    assert projection_row["acquisitionWindowKindCounts"] == {"touchline_escape": 3}
    assert projection_row["acquisitionRejectionBlockerCounts"] == {"continuity_rejected": 1}
    assert projection_row["acquisitionTouchlineEscapeCandidateFrames"] == 4
    assert projection_row["acquisitionTouchlineEscapeSelectedFrames"] == 3
    assert projection_row["acquisitionRepeatedAnchorSuppressionCount"] == 2
    assert projection_row["acquisitionCandidateEdgeShareBeforeSelection"] == 1.0
    assert projection_row["acquisitionCandidateEdgeShareAfterSelection"] == 0.5


def test_shadow_projection_row_uses_replayed_acquisition_projection_for_reopen_v3(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    match_id = "acquisition-replay-v3"
    _write_source_match(
        storage,
        match_id,
        source_clip_id="trimed-5min.mp4",
        video_path="/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
        accepted_frame_ids=list(range(12)),
        edge_frame_ids=set(range(10)),
        controlled_frame_ids=set(range(12)),
        frame_count=60,
    )

    monkeypatch.setattr(
        run_source_robustness_batch,
        "apply_source_conditioned_edge_share_repair",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("repair surrogate should not run")),
    )
    monkeypatch.setattr(
        run_source_robustness_batch,
        "_replay_source_conditioned_acquisition_projection",
        lambda **_kwargs: (
            [
                {
                    "Entity_Type": "ball",
                    "Frame_ID": frame_id,
                    "Timestamp": round(frame_id * 0.2, 3),
                    "Track_ID": -1,
                    "X": 28.0,
                    "Y": 63.0,
                    "Conf": 0.7,
                }
                for frame_id in range(12)
            ],
            {
                "applied": True,
                "profileName": "source_robustness_shadow_touchline_candidate_admission_reopen_v3",
                "mode": "touchline_candidate_admission_reopen",
                "sourceClipId": "trimed-5min.mp4",
                "selectedAcquisitionProfileName": "source_robustness_shadow_touchline_candidate_admission_reopen_v3",
                "proposalWindowKindCandidateCounts": {
                    "touchline_inboard_context": 12,
                },
                "proposalWindowKindSelectedCounts": {
                    "touchline_inboard_context": 12,
                },
                "touchlineCandidateModeEntered": True,
                "touchlineEscapeWindowFrames": 0,
                "touchlineInboardWindowFrames": 12,
                "touchlineEscapeCandidateFrames": 0,
                "touchlineEscapeSelectedFrames": 0,
                "reopenedRawCandidateFrames": 12,
                "reopenedRawCandidateSelectedFrames": 12,
                "edgeStuckCandidateRejectionCounts": {},
                "zeroTouchlineCandidateReasonCounts": {},
                "repeatedAnchorSuppressionCount": 0,
                "candidateSourceEdgeShareBeforeSelection": 1.0,
                "candidateSourceEdgeShareAfterSelection": 0.0,
            },
        ),
    )

    summary = run_source_robustness_batch.summarize_match_benchmark(storage, match_id)
    projection_row = run_source_robustness_batch._shadow_projection_row(
        storage,
        {
            "entryId": match_id,
            "label": match_id,
            "matchId": match_id,
            "sourceClipId": "trimed-5min.mp4",
        },
        summary,
        config_name="source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    )

    assert projection_row["acceptedBallFrames"] == 12
    assert projection_row["acquisitionWindowKindCounts"] == {"touchline_inboard_context": 12}
    assert projection_row["acquisitionTouchlineCandidateModeEntered"] is True
    assert projection_row["acquisitionTouchlineInboardWindowFrames"] == 12
    assert projection_row["acquisitionReopenedRawCandidateFrames"] == 12
    assert projection_row["acquisitionReopenedRawCandidateSelectedFrames"] == 12
    assert projection_row["acquisitionZeroTouchlineCandidateReasonCounts"] == {}


def test_replay_source_conditioned_acquisition_projection_handles_probe_only_frame_without_baseline_row(tmp_path):
    storage = Storage(tmp_path)
    match_id = "probe-only-frame"
    _write_source_match(
        storage,
        match_id,
        source_clip_id="trimed-5min.mp4",
        video_path="/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4",
        accepted_frame_ids=[0, 1, 2, 3],
        edge_frame_ids={0, 1, 2, 3},
        controlled_frame_ids={0, 1, 2, 3},
        frame_count=20,
        probe_filtered_ball_rows=[
            {
                "Entity_Type": "ball",
                "Frame_ID": 10,
                "Timestamp": 2.0,
                "Track_ID": -1,
                "X": 12.0,
                "Y": 50.0,
                "Source_X1": 40.0,
                "Source_Y1": 200.0,
                "Source_X2": 54.0,
                "Source_Y2": 214.0,
            }
        ],
        probe_raw_ball_rows=[
            {
                "Entity_Type": "ball",
                "Frame_ID": 10,
                "Timestamp": 2.0,
                "Track_ID": -1,
                "X": 12.0,
                "Y": 50.0,
                "Source_X1": 40.0,
                "Source_Y1": 200.0,
                "Source_X2": 54.0,
                "Source_Y2": 214.0,
            }
        ],
    )

    replayed_rows, diagnostics = run_source_robustness_batch._replay_source_conditioned_acquisition_projection(
        storage=storage,
        entry={
            "matchId": match_id,
            "sourceClipId": "trimed-5min.mp4",
        },
        config_name="source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    )

    assert isinstance(replayed_rows, list)
    assert diagnostics["applied"] is True


def test_resolve_source_robustness_recommended_next_lever_reopens_detector_and_candidate_source_generation():
    next_lever = run_source_robustness_batch.resolve_source_robustness_recommended_next_lever(
        default_next_lever="iterate_source_conditioned_edge_share_repair",
        source_robustness_diagnosis={
            "touchlineReplacementFalsified": True,
            "acquisitionCandidateFalsified": True,
        },
        combined_reopen_diagnosis=None,
    )

    assert next_lever == "reopen_detector_and_candidate_source_generation"


def test_resolve_source_robustness_recommended_next_lever_prefers_promoted_runtime_default_validation():
    next_lever = run_source_robustness_batch.resolve_source_robustness_recommended_next_lever(
        default_next_lever="promote_touchline_detector_candidate",
        source_robustness_diagnosis={},
        combined_reopen_diagnosis=None,
        detector_candidate_promotion_diagnosis={
            "trainingCandidateName": "touchline_detector_candidate_v6",
            "promotionValidated": True,
            "nextRecommendedNextLever": "promote_touchline_detector_candidate",
        },
        promoted_detector_candidate_robustness_diagnosis={
            "trainingCandidateName": "touchline_detector_candidate_v6",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "winningPassedPromotionGate": True,
            "nextRecommendedNextLever": "validate_promoted_touchline_runtime_default",
        },
    )

    assert next_lever == "validate_promoted_touchline_runtime_default"


def test_resolve_source_robustness_recommended_next_lever_blocks_promoted_runtime_default_validation_without_full_gate():
    next_lever = run_source_robustness_batch.resolve_source_robustness_recommended_next_lever(
        default_next_lever="promote_touchline_detector_candidate",
        source_robustness_diagnosis={},
        combined_reopen_diagnosis=None,
        detector_candidate_promotion_diagnosis={
            "trainingCandidateName": "touchline_detector_candidate_v6",
            "promotionValidated": True,
            "nextRecommendedNextLever": "promote_touchline_detector_candidate",
        },
        promoted_detector_candidate_robustness_diagnosis={
            "trainingCandidateName": "touchline_detector_candidate_v6",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": False,
            "winningPassedPromotionGate": False,
            "nextRecommendedNextLever": "validate_promoted_touchline_runtime_default",
        },
    )

    assert next_lever == "promote_touchline_detector_candidate"


def test_source_robustness_route_prefers_v7_2_promoted_validation_over_stale_evaluation():
    next_lever = run_source_robustness_batch.resolve_source_robustness_recommended_next_lever(
        default_next_lever="iterate_source_conditioned_edge_share_repair",
        source_robustness_diagnosis={},
        combined_reopen_diagnosis=None,
        detector_candidate_evaluation_diagnosis={
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
        },
        detector_candidate_promotion_diagnosis={
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "promotionValidated": True,
            "promotedForControlledRuns": True,
            "nextRecommendedNextLever": "promoted_v7_2_source_robustness_validation",
        },
    )

    assert next_lever == "promoted_v7_2_source_robustness_validation"


def test_source_robustness_route_prefers_v7_2_promoted_validation_over_default_source_conditioned_return():
    next_lever = run_source_robustness_batch.resolve_source_robustness_recommended_next_lever(
        default_next_lever="promote_source_conditioned_edge_share_repair",
        source_robustness_diagnosis={},
        combined_reopen_diagnosis=None,
        detector_candidate_promotion_diagnosis={
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "promotionValidated": True,
            "promotedForControlledRuns": True,
            "nextRecommendedNextLever": "promoted_v7_2_source_robustness_validation",
        },
    )

    assert next_lever == "promoted_v7_2_source_robustness_validation"


def test_run_source_robustness_batch_writes_combined_reopen_diagnosis_and_next_lever(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)

    monkeypatch.setattr(
        run_source_robustness_batch,
        "_run_combined_reopen_matrix",
        lambda **_kwargs: {
            "generatedAt": "2026-04-21T00:00:00+00:00",
            "cells": [],
            "localWinningDetectorModelPath": "yolo11s.pt",
            "localWinningAcquisitionStrategyName": "source_robustness_shadow_touchline_acquisition_reopen_v2",
            "winnerBeatsBestThinCandidate": False,
            "detectorUpliftAloneHelped": True,
            "candidateSourceReopenAloneHelped": False,
            "combinationOnlyHelped": False,
            "combinedReopenFalsified": True,
        },
    )
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")
    matrix = _load_json(output_dir / "primary_source_robustness_matrix.json")
    failure_audit = _load_json(output_dir / "primary_source_robustness_failure_audit.json")
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")
    combined_matrix = _load_json(output_dir / "combined_detector_candidate_source_matrix.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "reopen_detector_and_candidate_source_generation"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "reopen_detector_and_candidate_source_generation"
    assert suite_summary["combinedReopenDiagnosis"]["localWinningDetectorModelPath"] == "yolo11s.pt"
    assert robustness_diagnosis["combinedReopenDiagnosis"]["combinedReopenFalsified"] is True
    assert matrix["combinedReopenDiagnosis"]["localWinningAcquisitionStrategyName"] == (
        "source_robustness_shadow_touchline_acquisition_reopen_v2"
    )
    assert failure_audit["combinedReopenDiagnosis"]["detectorUpliftAloneHelped"] is True
    assert active_lane_snapshot["sourceRobustnessDiagnosis"]["combinedReopenDiagnosis"]["combinedReopenFalsified"] is True
    assert combined_matrix["localWinningDetectorModelPath"] == "yolo11s.pt"


def test_run_combined_reopen_matrix_uses_replay_rows_and_marks_missing_detector_cells():
    baseline_projection_rows = [
        {
            "sourceClipId": "trimed-5min.mp4",
            "acceptedBallFrames": 101,
            "controlledPossessionFrames": 98,
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.812,
            "acceptedRetentionRatio": 1.0,
            "controlledRetentionRatio": 1.0,
            "acquisitionWindowKindCounts": {},
            "acquisitionTouchlineCandidateModeEntered": False,
            "acquisitionTouchlineEscapeWindowFrames": 0,
            "acquisitionTouchlineInboardWindowFrames": 0,
            "acquisitionRejectionBlockerCounts": {},
            "acquisitionZeroTouchlineCandidateReasonCounts": {},
            "acquisitionTouchlineEscapeCandidateFrames": 0,
            "acquisitionTouchlineEscapeSelectedFrames": 0,
            "acquisitionReopenedRawCandidateFrames": 0,
            "acquisitionReopenedRawCandidateSelectedFrames": 0,
        }
    ]
    baseline_config_summary = {
        "suiteVerdict": "baseline_not_robust",
        "baselineFingerprint": {"detectorModelPath": "yolov10n.pt"},
    }
    baseline_source_summaries = {
        "trimed-5min.mp4": {
            "medianAcceptedBallFrames": 101,
            "medianControlledPossessionFrames": 98,
            "sourceViable": False,
            "medianBallTrackEdgeFrameShare": 0.812,
            "medianAcceptedRetentionRatio": 1.0,
            "medianControlledRetentionRatio": 1.0,
        }
    }
    config_rows = {
        "source_robustness_shadow_touchline_acquisition_upgrade_v1": [
            {
                "sourceClipId": "trimed-5min.mp4",
                "acceptedBallFrames": 103,
                "controlledPossessionFrames": 98,
                "ballTrackViable": False,
                "ballTrackEdgeFrameShare": 0.79,
                "acceptedRetentionRatio": 1.0,
                "controlledRetentionRatio": 1.0,
                "acquisitionWindowKindCounts": {"touchline_escape": 4},
                "acquisitionTouchlineCandidateModeEntered": True,
                "acquisitionTouchlineEscapeWindowFrames": 4,
                "acquisitionTouchlineInboardWindowFrames": 0,
                "acquisitionRejectionBlockerCounts": {"continuity_rejected": 1},
                "acquisitionZeroTouchlineCandidateReasonCounts": {},
                "acquisitionTouchlineEscapeCandidateFrames": 4,
                "acquisitionTouchlineEscapeSelectedFrames": 4,
                "acquisitionReopenedRawCandidateFrames": 0,
                "acquisitionReopenedRawCandidateSelectedFrames": 0,
            }
        ],
        "source_robustness_shadow_touchline_acquisition_reopen_v2": [
            {
                "sourceClipId": "trimed-5min.mp4",
                "acceptedBallFrames": 104,
                "controlledPossessionFrames": 98,
                "ballTrackViable": False,
                "ballTrackEdgeFrameShare": 0.77,
                "acceptedRetentionRatio": 1.0,
                "controlledRetentionRatio": 1.0,
                "acquisitionWindowKindCounts": {"touchline_escape": 3},
                "acquisitionTouchlineCandidateModeEntered": True,
                "acquisitionTouchlineEscapeWindowFrames": 3,
                "acquisitionTouchlineInboardWindowFrames": 0,
                "acquisitionRejectionBlockerCounts": {"edge_stuck": 1},
                "acquisitionZeroTouchlineCandidateReasonCounts": {},
                "acquisitionTouchlineEscapeCandidateFrames": 3,
                "acquisitionTouchlineEscapeSelectedFrames": 3,
                "acquisitionReopenedRawCandidateFrames": 0,
                "acquisitionReopenedRawCandidateSelectedFrames": 0,
            }
        ],
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3": [
            {
                "sourceClipId": "trimed-5min.mp4",
                "acceptedBallFrames": 111,
                "controlledPossessionFrames": 99,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.69,
                "acceptedRetentionRatio": 0.66,
                "controlledRetentionRatio": 0.72,
                "acquisitionWindowKindCounts": {"touchline_inboard_context": 6},
                "acquisitionTouchlineCandidateModeEntered": True,
                "acquisitionTouchlineEscapeWindowFrames": 2,
                "acquisitionTouchlineInboardWindowFrames": 6,
                "acquisitionRejectionBlockerCounts": {"edge_stuck": 2},
                "acquisitionZeroTouchlineCandidateReasonCounts": {},
                "acquisitionTouchlineEscapeCandidateFrames": 2,
                "acquisitionTouchlineEscapeSelectedFrames": 2,
                "acquisitionReopenedRawCandidateFrames": 5,
                "acquisitionReopenedRawCandidateSelectedFrames": 4,
            }
        ],
    }
    config_summaries = {
        name: {"suiteVerdict": "baseline_not_robust"} for name in config_rows
    }
    config_source_summaries = {
        "source_robustness_shadow_touchline_acquisition_upgrade_v1": {
            "trimed-5min.mp4": {
                "medianAcceptedBallFrames": 103,
                "medianControlledPossessionFrames": 98,
                "sourceViable": False,
                "medianBallTrackEdgeFrameShare": 0.79,
                "medianAcceptedRetentionRatio": 1.0,
                "medianControlledRetentionRatio": 1.0,
            }
        },
        "source_robustness_shadow_touchline_acquisition_reopen_v2": {
            "trimed-5min.mp4": {
                "medianAcceptedBallFrames": 104,
                "medianControlledPossessionFrames": 98,
                "sourceViable": False,
                "medianBallTrackEdgeFrameShare": 0.77,
                "medianAcceptedRetentionRatio": 1.0,
                "medianControlledRetentionRatio": 1.0,
            }
        },
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3": {
            "trimed-5min.mp4": {
                "medianAcceptedBallFrames": 111,
                "medianControlledPossessionFrames": 99,
                "sourceViable": True,
                "medianBallTrackEdgeFrameShare": 0.69,
                "medianAcceptedRetentionRatio": 0.66,
                "medianControlledRetentionRatio": 0.72,
            }
        },
    }
    config_outcomes = {
        "source_robustness_baseline_current": {
            "configOutcome": "source_robustness_weak",
            "sourceRobustnessOutcome": "source_robustness_weak",
            "promotionBlockers": [],
        },
        "source_robustness_shadow_touchline_acquisition_upgrade_v1": {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "promotionBlockers": ["failing_source_not_viable"],
        },
        "source_robustness_shadow_touchline_acquisition_reopen_v2": {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "promotionBlockers": ["failing_source_not_viable"],
        },
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3": {
            "configOutcome": "source_robustness_strong",
            "sourceRobustnessOutcome": "source_robustness_strong",
            "promotionBlockers": [],
        },
    }

    payload = run_source_robustness_batch._run_combined_reopen_matrix(
        clip_path=None,
        canonical_proof_floor={
            "acceptedBallFrames": 174,
            "controlledPossessionFrames": 137,
            "ballTrackViable": True,
            "ballTrackEdgeFrameShare": 0.586,
            "intact": True,
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        baseline_projection_rows=baseline_projection_rows,
        baseline_config_summary=baseline_config_summary,
        baseline_source_summaries=baseline_source_summaries,
        config_rows=config_rows,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
        failing_source_clip_id="trimed-5min.mp4",
        best_thin_reference={
            "acceptedBallFrames": 101,
            "controlledPossessionFrames": 98,
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.714,
        },
        best_thin_qualifying_config_name="source_robustness_shadow_edge_run_keep_every_2_min10",
    )

    assert payload is not None
    assert len(payload["cells"]) == 8
    assert payload["localWinningDetectorModelPath"] == "yolov10n.pt"
    assert payload["localWinningAcquisitionStrategyName"] == (
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3"
    )
    assert payload["winnerBeatsBestThinCandidate"] is True
    assert payload["combinedReopenFalsified"] is False
    assert payload["touchlineCandidateModeEntered"] is True
    assert payload["touchlineInboardWindowFrames"] == 6
    assert payload["reopenedRawCandidateFrames"] == 5
    assert payload["unsupportedDetectorModels"] == ["yolo11s.pt"]
    yolo11s_cells = [
        cell for cell in payload["cells"] if cell["detectorModelPath"] == "yolo11s.pt"
    ]
    assert len(yolo11s_cells) == 4
    assert all(cell["supportedBySavedArtifacts"] is False for cell in yolo11s_cells)
    assert all(cell["eligibleForLocalWinner"] is False for cell in yolo11s_cells)


def test_run_combined_reopen_matrix_disqualifies_weak_replay_candidates_with_inflated_row_counts():
    baseline_projection_rows = [
        {
            "sourceClipId": "trimed-5min.mp4",
            "acceptedBallFrames": 101,
            "controlledPossessionFrames": 98,
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.812,
            "acceptedRetentionRatio": 1.0,
            "controlledRetentionRatio": 1.0,
            "acquisitionWindowKindCounts": {},
            "acquisitionTouchlineCandidateModeEntered": False,
            "acquisitionTouchlineEscapeWindowFrames": 0,
            "acquisitionTouchlineInboardWindowFrames": 0,
            "acquisitionRejectionBlockerCounts": {},
            "acquisitionZeroTouchlineCandidateReasonCounts": {},
            "acquisitionTouchlineEscapeCandidateFrames": 0,
            "acquisitionTouchlineEscapeSelectedFrames": 0,
            "acquisitionReopenedRawCandidateFrames": 0,
            "acquisitionReopenedRawCandidateSelectedFrames": 0,
        }
    ]
    baseline_config_summary = {
        "suiteVerdict": "baseline_not_robust",
        "baselineFingerprint": {"detectorModelPath": "yolov10n.pt"},
    }
    baseline_source_summaries = {
        "trimed-5min.mp4": {
            "medianAcceptedBallFrames": 101,
            "medianControlledPossessionFrames": 98,
            "sourceViable": False,
            "medianBallTrackEdgeFrameShare": 0.812,
            "medianAcceptedRetentionRatio": 1.0,
            "medianControlledRetentionRatio": 1.0,
        }
    }
    config_rows = {
        "source_robustness_shadow_touchline_acquisition_upgrade_v1": [
            {
                "sourceClipId": "trimed-5min.mp4",
                "acceptedBallFrames": 938,
                "controlledPossessionFrames": 98,
                "ballTrackViable": False,
                "ballTrackEdgeFrameShare": 0.981,
                "acceptedRetentionRatio": 9.287,
                "controlledRetentionRatio": 1.0,
                "acquisitionWindowKindCounts": {"touchline_escape": 6829},
                "acquisitionTouchlineCandidateModeEntered": True,
                "acquisitionTouchlineEscapeWindowFrames": 7473,
                "acquisitionTouchlineInboardWindowFrames": 0,
                "acquisitionRejectionBlockerCounts": {"edge_share_not_improved": 7473},
                "acquisitionZeroTouchlineCandidateReasonCounts": {"no_touchline_candidates_available": 109},
                "acquisitionTouchlineEscapeCandidateFrames": 7473,
                "acquisitionTouchlineEscapeSelectedFrames": 0,
                "acquisitionReopenedRawCandidateFrames": 6803,
                "acquisitionReopenedRawCandidateSelectedFrames": 6723,
            }
        ],
        "source_robustness_shadow_touchline_acquisition_reopen_v2": [],
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3": [],
    }
    config_summaries = {
        "source_robustness_baseline_current": {
            "suiteVerdict": "baseline_not_robust",
            "suiteRecommendedNextLever": "reopen_detector_and_candidate_source_generation",
        },
        "source_robustness_shadow_touchline_acquisition_upgrade_v1": {
            "suiteVerdict": "baseline_not_robust",
            "suiteRecommendedNextLever": "reopen_detector_and_candidate_source_generation",
        },
        "source_robustness_shadow_touchline_acquisition_reopen_v2": {
            "suiteVerdict": "baseline_not_robust",
            "suiteRecommendedNextLever": "reopen_detector_and_candidate_source_generation",
        },
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3": {
            "suiteVerdict": "baseline_not_robust",
            "suiteRecommendedNextLever": "reopen_detector_and_candidate_source_generation",
        },
    }
    config_source_summaries = {
        "source_robustness_baseline_current": {
            "trimed-5min.mp4": {
                "medianAcceptedBallFrames": 101,
                "medianControlledPossessionFrames": 98,
                "sourceViable": False,
                "medianBallTrackEdgeFrameShare": 0.812,
                "medianAcceptedRetentionRatio": 1.0,
                "medianControlledRetentionRatio": 1.0,
            }
        },
        "source_robustness_shadow_touchline_acquisition_upgrade_v1": {
            "trimed-5min.mp4": {
                "medianAcceptedBallFrames": 103,
                "medianControlledPossessionFrames": 98,
                "sourceViable": False,
                "medianBallTrackEdgeFrameShare": 0.79,
                "medianAcceptedRetentionRatio": 1.0,
                "medianControlledRetentionRatio": 1.0,
            }
        },
        "source_robustness_shadow_touchline_acquisition_reopen_v2": {
            "trimed-5min.mp4": {}
        },
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3": {
            "trimed-5min.mp4": {}
        },
    }
    config_outcomes = {
        "source_robustness_baseline_current": {
            "configOutcome": "source_robustness_weak",
            "sourceRobustnessOutcome": "source_robustness_weak",
            "promotionBlockers": [],
        },
        "source_robustness_shadow_touchline_acquisition_upgrade_v1": {
            "configOutcome": "source_robustness_weak",
            "sourceRobustnessOutcome": "source_robustness_weak",
            "promotionBlockers": ["edge_share_improvement_insufficient"],
        },
        "source_robustness_shadow_touchline_acquisition_reopen_v2": {
            "configOutcome": "source_robustness_weak",
            "sourceRobustnessOutcome": "source_robustness_weak",
            "promotionBlockers": ["edge_share_improvement_insufficient"],
        },
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3": {
            "configOutcome": "source_robustness_weak",
            "sourceRobustnessOutcome": "source_robustness_weak",
            "promotionBlockers": ["edge_share_improvement_insufficient"],
        },
    }

    payload = run_source_robustness_batch._run_combined_reopen_matrix(
        clip_path=None,
        canonical_proof_floor={
            "acceptedBallFrames": 174,
            "controlledPossessionFrames": 137,
            "ballTrackViable": True,
            "ballTrackEdgeFrameShare": 0.586,
            "intact": True,
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        baseline_projection_rows=baseline_projection_rows,
        baseline_config_summary=baseline_config_summary,
        baseline_source_summaries=baseline_source_summaries,
        config_rows=config_rows,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
        failing_source_clip_id="trimed-5min.mp4",
        best_thin_reference={
            "acceptedBallFrames": 101,
            "controlledPossessionFrames": 98,
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.714,
        },
        best_thin_qualifying_config_name="source_robustness_shadow_edge_run_keep_every_2_min10",
    )

    assert payload is not None
    upgrade_cell = next(
        cell
        for cell in payload["cells"]
        if cell["acquisitionStrategyName"] == "source_robustness_shadow_touchline_acquisition_upgrade_v1"
        and cell["detectorModelPath"] == "yolov10n.pt"
    )
    assert upgrade_cell["acceptedBallFrames"] == 103
    assert upgrade_cell["ballTrackEdgeFrameShare"] == 0.79
    assert upgrade_cell["eligibleForLocalWinner"] is False
    assert payload["localWinningAcquisitionStrategyName"] == "source_robustness_baseline_current"
    assert payload["winnerBeatsBestThinCandidate"] is False
    assert payload["combinedReopenFalsified"] is True


def test_run_source_robustness_batch_writes_detector_breadth_diagnosis_and_detector_next_lever(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_breadth_matrix.json").write_text(
        json.dumps(
            {
                "generatedAt": "2026-04-22T00:00:00+00:00",
                "screenWinningDetectorModelPath": "yolo11s.pt",
                "remoteWinningDetectorModelPath": "yolo11s.pt",
                "baselineRemoteBeatsPlateau": True,
                "compoundThinRemoteBeatsPlateau": False,
                "detectorBreadthFalsified": False,
                "nextTrainingCandidateNeeded": False,
                "nextRecommendedNextLever": "promote_detector_model_upgrade",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        run_source_robustness_batch,
        "_run_combined_reopen_matrix",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(resolved_output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "promote_detector_model_upgrade"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "promote_detector_model_upgrade"
    assert suite_summary["detectorBreadthDiagnosis"]["remoteWinningDetectorModelPath"] == "yolo11s.pt"
    assert robustness_diagnosis["detectorBreadthDiagnosis"]["baselineRemoteBeatsPlateau"] is True
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["detectorBreadthDiagnosis"]["nextTrainingCandidateNeeded"]
        is False
    )


def test_run_source_robustness_batch_ingests_training_prep_diagnosis_and_flips_next_lever(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    training_prep_dir = tmp_path / "training_prep" / "touchline_training_data_curation_foundation"
    training_prep_dir.mkdir(parents=True, exist_ok=True)
    (training_prep_dir / "curation_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_training_data_curation_foundation",
                "failingSourceClipId": "trimed-5min.mp4",
                "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
                "representativeFailingMatchId": "failing-0",
                "representativeControlMatchId": "control-0",
                "curationUnitCount": 2,
                "positiveSeedExampleCount": 9,
                "negativeSeedExampleCount": 4,
                "yoloExportReady": True,
                "readyForDetectorTraining": True,
                "trainingPrepPrimaryBlocker": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_prep_dir / "split_manifest.json").write_text(
        json.dumps(
            {
                "sourceAwareSplitLeakageDetected": False,
                "splits": {
                    "train": {"sourceClipIds": ["trimed-5min.mp4"]},
                    "val": {"sourceClipIds": ["trimed-football-2-1minute.mp4"]},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_prep_dir / "seeded_issue_report.json").write_text(
        json.dumps(
            {
                "seededIssueCount": 2,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(resolved_output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "train_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "train_touchline_detector_candidate"
    assert suite_summary["trainingPrepDiagnosis"]["trainingPrepBatchName"] == (
        "touchline_training_data_curation_foundation"
    )
    assert suite_summary["trainingPrepDiagnosis"]["readyForDetectorTraining"] is True
    assert robustness_diagnosis["trainingPrepDiagnosis"]["seededIssueCount"] == 2
    assert active_lane_snapshot["trainingPrepDiagnosis"]["representativeFailingMatchId"] == "failing-0"
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["trainingPrepDiagnosis"]["sourceAwareSplitLeakageDetected"]
        is False
    )


def test_run_source_robustness_batch_ingests_detector_training_diagnosis_and_flips_next_lever_to_evaluation(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_plateau_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    training_prep_dir = tmp_path / "training_prep" / "touchline_training_data_curation_foundation"
    training_prep_dir.mkdir(parents=True, exist_ok=True)
    (training_prep_dir / "curation_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_training_data_curation_foundation",
                "failingSourceClipId": "trimed-5min.mp4",
                "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
                "representativeFailingMatchId": "failing-0",
                "representativeControlMatchId": "control-0",
                "curationUnitCount": 2,
                "positiveSeedExampleCount": 9,
                "negativeSeedExampleCount": 4,
                "yoloExportReady": True,
                "readyForDetectorTraining": True,
                "trainingPrepPrimaryBlocker": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_prep_dir / "split_manifest.json").write_text(
        json.dumps({"sourceAwareSplitLeakageDetected": False}, indent=2),
        encoding="utf-8",
    )
    (training_prep_dir / "seeded_issue_report.json").write_text(
        json.dumps({"seededIssueCount": 2}, indent=2),
        encoding="utf-8",
    )

    trained_candidate_dir = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v1"
    trained_candidate_dir.mkdir(parents=True, exist_ok=True)
    (trained_candidate_dir / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v1",
                "trainingBatchName": "touchline_detector_candidate_training_v1",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_candidate_dir / "training_config.json").write_text(
        json.dumps({"trainingRecipe": {"baseModelPath": "yolov10n.pt"}}, indent=2),
        encoding="utf-8",
    )
    (trained_candidate_dir / "evaluation_contract.json").write_text(
        json.dumps({"candidateReadyForEvaluation": True}, indent=2),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(resolved_output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["detectorTrainingDiagnosis"]["trainingCandidateName"] == "touchline_detector_candidate_v1"
    assert suite_summary["detectorTrainingDiagnosis"]["readyForDetectorEvaluation"] is True
    assert robustness_diagnosis["detectorTrainingDiagnosis"]["weightsReady"] is True
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["detectorTrainingDiagnosis"]["evaluationContractReady"] is True
    )


def test_run_source_robustness_batch_ingests_detector_candidate_evaluation_and_flips_next_lever_to_promotion(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    training_prep_dir = tmp_path / "training_prep" / "touchline_training_data_curation_foundation"
    training_prep_dir.mkdir(parents=True, exist_ok=True)
    (training_prep_dir / "curation_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_training_data_curation_foundation",
                "failingSourceClipId": "trimed-5min.mp4",
                "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
                "representativeFailingMatchId": "failing-0",
                "representativeControlMatchId": "control-0",
                "curationUnitCount": 2,
                "yoloExportReady": True,
                "readyForDetectorTraining": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_prep_dir / "split_manifest.json").write_text(
        json.dumps(
            {"sourceAwareSplitLeakageDetected": False, "readyForDetectorTraining": True},
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_prep_dir / "seeded_issue_report.json").write_text(
        json.dumps({"seededIssueCount": 2}, indent=2),
        encoding="utf-8",
    )

    trained_candidate_dir = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v1"
    trained_candidate_dir.mkdir(parents=True, exist_ok=True)
    (trained_candidate_dir / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v1",
                "trainingBatchName": "touchline_detector_candidate_training_v1",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_candidate_dir / "training_config.json").write_text(
        json.dumps({"trainingRecipe": {"baseModelPath": "yolov10n.pt"}}, indent=2),
        encoding="utf-8",
    )
    (trained_candidate_dir / "evaluation_contract.json").write_text(
        json.dumps({"candidateReadyForEvaluation": True}, indent=2),
        encoding="utf-8",
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_evaluation.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v1",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v1",
                "candidateWeightsPath": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v1/weights/best.pt",
                "screenCompleted": True,
                "screenWinningDetectorLabel": "touchline_detector_candidate_v1_best",
                "candidateBaselineProofRan": True,
                "candidateBaselineProductBeatsPlateau": True,
                "baselineControlProofRan": True,
                "candidateCompoundThinProofRan": False,
                "candidateCompoundThinProductBeatsPlateau": False,
                "candidateBeatsSameBatchBaselineControl": True,
                "evaluationPrimaryBlocker": None,
                "readyForPromotion": True,
                "phase1BDensificationRecommended": False,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(resolved_output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "promote_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "promote_touchline_detector_candidate"
    assert suite_summary["detectorCandidateEvaluationDiagnosis"]["trainingCandidateName"] == "touchline_detector_candidate_v1"
    assert suite_summary["detectorCandidateEvaluationDiagnosis"]["readyForPromotion"] is True
    assert robustness_diagnosis["detectorCandidateEvaluationDiagnosis"]["candidateBaselineProductBeatsPlateau"] is True
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["detectorCandidateEvaluationDiagnosis"]["baselineControlProofRan"]
        is True
    )


def test_run_source_robustness_batch_ingests_detector_candidate_promotion_validation(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_evaluation.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v6",
                "candidateWeightsPath": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/weights/best.pt",
                "screenCompleted": True,
                "screenWinningDetectorLabel": "yolov10n.pt_baseline_full_detector",
                "candidateBaselineProofRan": True,
                "candidateBaselineProductBeatsPlateau": True,
                "baselineControlProofRan": True,
                "candidateCompoundThinProofRan": True,
                "candidateCompoundThinProductBeatsPlateau": True,
                "candidateBeatsSameBatchBaselineControl": True,
                "evaluationPrimaryBlocker": None,
                "readyForPromotion": True,
                "phase1BDensificationRecommended": False,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "detector_candidate_promotion.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "promotionBatchName": "touchline_detector_candidate_promotion_validation_v1",
                "promotionValidated": True,
                "promotedForControlledRuns": True,
                "runtimeDefaultChanged": False,
                "runtimeDefaultChangeAllowed": False,
                "runtimeDefaultChangeBlockers": ["failing_source_not_viable"],
                "candidateBaselineProductBeatsPlateau": True,
                "baselineControlProofRan": True,
                "candidateBeatsSameBatchBaselineControl": True,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
                "batchOutcomeAnalysis": {
                    "goalAchieved": True,
                    "roadmapAdvanceAllowed": True,
                    "nextRecommendedNextLever": "promote_touchline_detector_candidate",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(resolved_output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "promote_touchline_detector_candidate"
    assert suite_summary["detectorCandidatePromotionDiagnosis"]["trainingCandidateName"] == "touchline_detector_candidate_v6"
    assert suite_summary["detectorCandidatePromotionDiagnosis"]["promotionValidated"] is True
    assert suite_summary["detectorCandidatePromotionDiagnosis"]["runtimeDefaultChanged"] is False
    assert robustness_diagnosis["detectorCandidatePromotionDiagnosis"]["runtimeDefaultChangeAllowed"] is False
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["detectorCandidatePromotionDiagnosis"][
            "candidateBeatsSameBatchBaselineControl"
        ]
        is True
    )


def test_run_source_robustness_batch_routes_v7_2_promotion_readiness_before_stale_v7_evaluation(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_evaluation.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v7",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v7",
                "readyForPromotion": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "detector_candidate_promotion.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v7",
                "promotionBatchName": "v7_2_promotion_readiness_validation",
                "promotionValidated": True,
                "promotionReady": True,
                "candidateReadyForEvaluation": True,
                "promotedForControlledRuns": True,
                "runtimeDefaultMutationAllowed": False,
                "runtimeDefaultMutationBlockers": ["failing_source_not_viable"],
                "nextRecommendedNextLever": "promoted_v7_2_source_robustness_validation",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "promoted_v7_2_source_robustness_validation"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "promoted_v7_2_source_robustness_validation"
    assert (
        robustness_diagnosis["detectorCandidatePromotionDiagnosis"]["nextRecommendedNextLever"]
        == "promoted_v7_2_source_robustness_validation"
    )


def test_run_source_robustness_batch_ingests_promoted_detector_candidate_robustness_validation(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_promotion.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "promotionBatchName": "touchline_detector_candidate_promotion_validation_v1",
                "promotionValidated": True,
                "promotedForControlledRuns": True,
                "runtimeDefaultChanged": False,
                "runtimeDefaultChangeAllowed": False,
                "runtimeDefaultChangeBlockers": ["failing_source_not_viable"],
                "candidateBaselineProductBeatsPlateau": True,
                "baselineControlProofRan": True,
                "candidateBeatsSameBatchBaselineControl": True,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
                "batchOutcomeAnalysis": {
                    "goalAchieved": True,
                    "roadmapAdvanceAllowed": True,
                    "nextRecommendedNextLever": "promote_touchline_detector_candidate",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    validation_root = output_dir / "promoted_touchline_detector_candidate_robustness_validation_v1"
    validation_root.mkdir(parents=True, exist_ok=True)
    (validation_root / "validation_summary.json").write_text(
        json.dumps(
            {
                "validationBatchName": "promoted_touchline_detector_candidate_robustness_validation_v1",
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "evaluatedArmNames": [
                    "baseline_current",
                    "promoted_v6_baseline",
                    "promoted_v6_plus_best_thin",
                ],
                "winningArmName": "promoted_v6_baseline",
                "winningConfigOutcome": "source_robustness_strong",
                "winningPassedPromotionGate": True,
                "winningPromotionBlockers": [],
                "winningFailingSourceEdgeShareImprovement": 0.112,
                "runtimeDefaultChanged": False,
                "nextRecommendedNextLever": "validate_promoted_touchline_runtime_default",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (validation_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": True,
                "nextRecommendedNextLever": "validate_promoted_touchline_runtime_default",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(resolved_output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "validate_promoted_touchline_runtime_default"
    assert suite_summary["promotedDetectorCandidateRobustnessDiagnosis"]["winningArmName"] == "promoted_v6_baseline"
    assert (
        robustness_diagnosis["promotedDetectorCandidateRobustnessDiagnosis"]["winningPassedPromotionGate"] is True
    )
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["promotedDetectorCandidateRobustnessDiagnosis"][
            "runtimeDefaultChanged"
        ]
        is False
    )


def test_run_source_robustness_batch_ingests_promoted_detector_candidate_retention_delta_analysis(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_promotion.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "promotionBatchName": "touchline_detector_candidate_promotion_validation_v1",
                "promotionValidated": True,
                "promotedForControlledRuns": True,
                "runtimeDefaultChanged": False,
                "runtimeDefaultChangeAllowed": False,
                "runtimeDefaultChangeBlockers": ["failing_source_not_viable"],
                "candidateBaselineProductBeatsPlateau": True,
                "baselineControlProofRan": True,
                "candidateBeatsSameBatchBaselineControl": True,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
                "batchOutcomeAnalysis": {
                    "goalAchieved": True,
                    "roadmapAdvanceAllowed": True,
                    "nextRecommendedNextLever": "promote_touchline_detector_candidate",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    validation_root = output_dir / "promoted_touchline_detector_candidate_robustness_validation_v1"
    validation_root.mkdir(parents=True, exist_ok=True)
    (validation_root / "validation_summary.json").write_text(
        json.dumps(
            {
                "validationBatchName": "promoted_touchline_detector_candidate_robustness_validation_v1",
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "winningArmName": "promoted_v6_baseline",
                "winningConfigOutcome": "source_robustness_weak",
                "winningPassedPromotionGate": False,
                "winningPromotionBlockers": [
                    "accepted_retention_below_guardrail",
                    "controlled_retention_below_guardrail",
                ],
                "winningFailingSourceEdgeShareImprovement": 0.712,
                "runtimeDefaultChanged": False,
                "nextRecommendedNextLever": "validate_promoted_touchline_runtime_default",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (validation_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": False,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "validate_promoted_touchline_runtime_default",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    retention_root = output_dir / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
    retention_root.mkdir(parents=True, exist_ok=True)
    (retention_root / "retention_delta_summary.json").write_text(
        json.dumps(
            {
                "analysisBatchName": "promoted_touchline_detector_candidate_retention_delta_analysis_v1",
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "winningArmName": "promoted_v6_baseline",
                "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
                "acceptedRetentionRatio": 0.099,
                "controlledRetentionRatio": 0.133,
                "selectedClusterStepImplicated": False,
                "nextImplementationBatchRecommendation": (
                    "touchline_detector_candidate_v6_accepted_signal_retention_fix_v1"
                ),
                "goalAchieved": False,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (retention_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": False,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "promote_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    resolved_output_dir = Path(result["outputDir"])
    suite_summary = _load_json(resolved_output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(resolved_output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(resolved_output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "promote_touchline_detector_candidate"
    assert (
        suite_summary["promotedDetectorCandidateRetentionDeltaDiagnosis"]["primaryRetentionBlockerClass"]
        == "accepted_signal_retention_collapse"
    )
    assert (
        robustness_diagnosis["promotedDetectorCandidateRetentionDeltaDiagnosis"][
            "nextImplementationBatchRecommendation"
        ]
        == "touchline_detector_candidate_v6_accepted_signal_retention_fix_v1"
    )
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["promotedDetectorCandidateRetentionDeltaDiagnosis"][
            "selectedClusterStepImplicated"
        ]
        is False
    )


def test_run_source_robustness_batch_prefers_newer_v2_training_over_stale_v1_evaluation(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {"detectorModelPath": "yolov10n.pt"},
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    review_densification_dir = tmp_path / "training_prep" / "touchline_review_densification_v1"
    review_densification_dir.mkdir(parents=True, exist_ok=True)
    (review_densification_dir / "review_densification_manifest.json").write_text(
        json.dumps(
            {
                "reviewDensificationBatchName": "touchline_review_densification_v1",
                "batchName": "touchline_review_densification_v1",
                "representativeFailingMatchId": "failing-0",
                "representativeControlMatchId": "control-0",
                "failingCurationUnitCount": 2,
                "controlCurationUnitCount": 1,
                "reviewItemCount": 73,
                "pendingReviewCount": 13,
                "pendingFailingReviewCount": 0,
                "pendingControlReviewCount": 13,
                "failingSourceReviewComplete": True,
                "controlReviewComplete": False,
                "reviewedPositiveCount": 54,
                "reviewedNegativeCount": 6,
                "yoloExportRegenerated": True,
                "readyForRetraining": True,
                "reviewDensificationPrimaryBlocker": None,
                "nextRecommendedNextLever": "retrain_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (review_densification_dir / "split_manifest.json").write_text(
        json.dumps(
            {
                "sourceAwareSplitLeakageDetected": False,
                "readyForRetraining": True,
                "reviewDensificationPrimaryBlocker": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (review_densification_dir / "review_bundle_report.json").write_text(
        json.dumps({"reviewBundleCount": 2, "seededIssueCount": 3}, indent=2),
        encoding="utf-8",
    )
    (review_densification_dir / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": True,
                "readyForRetraining": True,
                "nextRecommendedNextLever": "retrain_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    trained_v1_dir = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v1"
    trained_v1_dir.mkdir(parents=True, exist_ok=True)
    (trained_v1_dir / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v1",
                "trainingBatchName": "touchline_detector_candidate_training_v1",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_v1_dir / "training_config.json").write_text(
        json.dumps({"trainingRecipe": {"baseModelPath": "yolov10n.pt"}}, indent=2),
        encoding="utf-8",
    )
    (trained_v1_dir / "evaluation_contract.json").write_text(
        json.dumps({"candidateReadyForEvaluation": True}, indent=2),
        encoding="utf-8",
    )

    trained_v2_dir = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v2"
    trained_v2_dir.mkdir(parents=True, exist_ok=True)
    (trained_v2_dir / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v2",
                "trainingBatchName": "touchline_detector_candidate_retraining_v2",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_v2_dir / "training_config.json").write_text(
        json.dumps({"trainingRecipe": {"baseModelPath": "yolov10n.pt"}}, indent=2),
        encoding="utf-8",
    )
    (trained_v2_dir / "evaluation_contract.json").write_text(
        json.dumps(
            {
                "candidateReadyForEvaluation": True,
                "trainingCandidateName": "touchline_detector_candidate_v2",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_v2_dir / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": True,
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "brainstormFixes": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_evaluation.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v1",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v1",
                "screenCompleted": False,
                "candidateBaselineProofRan": True,
                "candidateBaselineProductBeatsPlateau": False,
                "baselineControlProofRan": False,
                "candidateCompoundThinProofRan": False,
                "candidateCompoundThinProductBeatsPlateau": False,
                "candidateBeatsSameBatchBaselineControl": False,
                "evaluationPrimaryBlocker": "candidate_screen_failed",
                "readyForPromotion": False,
                "phase1BDensificationRecommended": True,
                "nextRecommendedNextLever": "start_phase_1b_review_densification",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    suite_summary = _load_json(output_dir / "suite_summary.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["detectorTrainingDiagnosis"]["trainingCandidateName"] == "touchline_detector_candidate_v2"
    assert suite_summary["detectorTrainingDiagnosis"]["readyForDetectorEvaluation"] is True
    assert suite_summary["detectorTrainingDiagnosis"]["batchOutcomeAnalysis"]["goalAchieved"] is True


def test_run_source_robustness_batch_keeps_evaluation_lane_when_v2_evaluation_closeout_fails(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    trained_candidate_dir = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v2"
    trained_candidate_dir.mkdir(parents=True, exist_ok=True)
    (trained_candidate_dir / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingBatchName": "touchline_detector_candidate_retraining_v2",
                "trainingCandidateName": "touchline_detector_candidate_v2",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_candidate_dir / "training_config.json").write_text(
        json.dumps({"trainingRecipe": {"baseModelPath": "yolov10n.pt"}}, indent=2),
        encoding="utf-8",
    )
    (trained_candidate_dir / "evaluation_contract.json").write_text(
        json.dumps({"candidateReadyForEvaluation": True}, indent=2),
        encoding="utf-8",
    )
    (trained_candidate_dir / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_evaluation.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v2",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v1",
                "candidateWeightsPath": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v2/weights/best.pt",
                "screenCompleted": True,
                "screenWinningDetectorLabel": "yolov10n.pt",
                "candidateBaselineProofRan": True,
                "candidateBaselineProductBeatsPlateau": False,
                "baselineControlProofRan": False,
                "candidateCompoundThinProofRan": False,
                "candidateCompoundThinProductBeatsPlateau": False,
                "candidateBeatsSameBatchBaselineControl": False,
                "evaluationPrimaryBlocker": "candidate_baseline_proof_failed",
                "readyForPromotion": False,
                "phase1BDensificationRecommended": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "batchOutcomeAnalysis": {
                    "goalAchieved": False,
                    "roadmapAdvanceAllowed": False,
                    "englishSummary": "The v2 evaluation did not produce a promotable candidate.",
                    "englishDecision": "The roadmap must stay on evaluation until the blocker is fixed.",
                    "primaryBlocker": "candidate_baseline_proof_failed",
                    "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                    "brainstormFixes": [
                        "Inspect the failed baseline proof and rerun bounded evaluation after fixing that blocker."
                    ],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["detectorCandidateEvaluationDiagnosis"]["trainingCandidateName"] == "touchline_detector_candidate_v2"
    assert suite_summary["detectorCandidateEvaluationDiagnosis"]["phase1BDensificationRecommended"] is False
    assert (
        suite_summary["detectorCandidateEvaluationDiagnosis"]["batchOutcomeAnalysis"]["roadmapAdvanceAllowed"] is False
    )
    assert (
        robustness_diagnosis["detectorCandidateEvaluationDiagnosis"]["nextRecommendedNextLever"]
        == "evaluate_touchline_detector_candidate"
    )


def test_run_source_robustness_batch_ingests_detector_candidate_failure_analysis_without_advancing_roadmap(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    trained_candidate_dir = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v3"
    trained_candidate_dir.mkdir(parents=True, exist_ok=True)
    (trained_candidate_dir / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingBatchName": "touchline_detector_candidate_model_data_quality_fix_v1",
                "trainingCandidateName": "touchline_detector_candidate_v3",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_candidate_dir / "training_config.json").write_text(
        json.dumps({"trainingRecipe": {"baseModelPath": "yolov10n.pt"}}, indent=2),
        encoding="utf-8",
    )
    (trained_candidate_dir / "evaluation_contract.json").write_text(
        json.dumps({"candidateReadyForEvaluation": True}, indent=2),
        encoding="utf-8",
    )
    (trained_candidate_dir / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_candidate_dir / "failure_analysis_v1").mkdir(parents=True, exist_ok=True)
    (trained_candidate_dir / "failure_analysis_v1" / "failure_analysis_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v3",
                "previousCandidateName": "touchline_detector_candidate_v2",
                "failureAnalysisBatchName": "touchline_detector_candidate_failure_analysis_v1",
                "screenWinningDetectorLabel": "yolov10n.pt_baseline_full_detector",
                "candidateScreenViable": False,
                "candidateRawProbeRowCount": 0,
                "candidateFilteredProbeRowCount": 0,
                "candidateAcceptedBallFrameCount": 0,
                "previousCandidateRawProbeRowCount": 0,
                "previousCandidateFilteredProbeRowCount": 0,
                "previousCandidateAcceptedBallFrameCount": 0,
                "baselineRawProbeRowCount": 928,
                "baselineFilteredProbeRowCount": 81,
                "baselineAcceptedBallFrameCount": 101,
                "candidateMaxProposalDetectedFramesAcrossProfiles": 0,
                "previousCandidateMaxProposalDetectedFramesAcrossProfiles": 0,
                "baselineMaxProposalDetectedFramesAcrossProfiles": 21,
                "rootCauseClass": "auxiliary_probe_zero_raw_rows",
                "changeFromPreviousCandidateClass": "no_observable_improvement",
                "recommendedFixClass": "model_data_quality",
                "recommendedFixFocus": "proposal_signal_generation",
                "summarySurfaceDriftDetected": True,
                "calibrationSuspicionDetected": False,
                "nextImplementationBatchRecommendation": "canonical_proof_summary_contract_v1",
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "batchOutcomeAnalysis": {
                    "goalAchieved": True,
                    "roadmapAdvanceAllowed": False,
                    "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (trained_candidate_dir / "failure_analysis_v1" / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "recommendedFixClass": "model_data_quality",
                "recommendedFixFocus": "proposal_signal_generation",
                "summarySurfaceDriftDetected": True,
                "calibrationSuspicionDetected": False,
                "nextImplementationBatchRecommendation": "canonical_proof_summary_contract_v1",
                "brainstormFixes": [
                    "Focus the next corrective batch on proposal signal generation before rerunning bounded evaluation."
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_evaluation.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v3",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v3",
                "candidateWeightsPath": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v3/weights/best.pt",
                "screenCompleted": True,
                "screenWinningDetectorLabel": "yolov10n.pt_baseline_full_detector",
                "candidateBaselineProofRan": True,
                "candidateBaselineProductBeatsPlateau": False,
                "baselineControlProofRan": False,
                "candidateCompoundThinProofRan": False,
                "candidateCompoundThinProductBeatsPlateau": False,
                "candidateBeatsSameBatchBaselineControl": False,
                "evaluationPrimaryBlocker": "candidate_baseline_did_not_beat_plateau",
                "readyForPromotion": False,
                "phase1BDensificationRecommended": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "batchOutcomeAnalysis": {
                    "goalAchieved": False,
                    "roadmapAdvanceAllowed": False,
                    "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                    "brainstormFixes": ["Inspect the saved evaluation artifacts before rerunning."],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["rootCauseClass"] == (
        "auxiliary_probe_zero_raw_rows"
    )
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["previousCandidateName"] == (
        "touchline_detector_candidate_v2"
    )
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["changeFromPreviousCandidateClass"] == (
        "no_observable_improvement"
    )
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["recommendedFixClass"] == (
        "model_data_quality"
    )
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["recommendedFixFocus"] == (
        "proposal_signal_generation"
    )
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["summarySurfaceDriftDetected"] is True
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["calibrationSuspicionDetected"] is False
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["nextImplementationBatchRecommendation"] == (
        "canonical_proof_summary_contract_v1"
    )
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["goalAchieved"] is True
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["roadmapAdvanceAllowed"] is False
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["candidateMaxProposalDetectedFramesAcrossProfiles"] == 0
    assert suite_summary["detectorCandidateFailureAnalysisDiagnosis"]["baselineMaxProposalDetectedFramesAcrossProfiles"] == 21
    assert (
        robustness_diagnosis["detectorCandidateFailureAnalysisDiagnosis"]["nextRecommendedNextLever"]
        == "evaluate_touchline_detector_candidate"
    )
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["detectorCandidateFailureAnalysisDiagnosis"][
            "candidateRawProbeRowCount"
        ]
        == 0
    )


def test_run_source_robustness_batch_ingests_review_densification_and_promotes_retrain_next_lever(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    proof_summary_path = tmp_path / "canonical-proof.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    training_prep_dir = tmp_path / "training_prep" / "touchline_training_data_curation_foundation"
    training_prep_dir.mkdir(parents=True, exist_ok=True)
    (training_prep_dir / "curation_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_training_data_curation_foundation",
                "failingSourceClipId": "trimed-5min.mp4",
                "comparisonSourceClipId": "trimed-football-2-1minute.mp4",
                "representativeFailingMatchId": "failing-0",
                "representativeControlMatchId": "control-0",
                "curationUnitCount": 2,
                "yoloExportReady": True,
                "readyForDetectorTraining": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_prep_dir / "split_manifest.json").write_text(
        json.dumps(
            {"sourceAwareSplitLeakageDetected": False, "readyForDetectorTraining": True},
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_prep_dir / "seeded_issue_report.json").write_text(
        json.dumps({"seededIssueCount": 2}, indent=2),
        encoding="utf-8",
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detector_candidate_evaluation.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v1",
                "evaluationBatchName": "touchline_detector_candidate_evaluation_v1",
                "screenCompleted": False,
                "candidateBaselineProofRan": True,
                "candidateBaselineProductBeatsPlateau": False,
                "baselineControlProofRan": False,
                "candidateCompoundThinProofRan": False,
                "candidateCompoundThinProductBeatsPlateau": False,
                "candidateBeatsSameBatchBaselineControl": False,
                "evaluationPrimaryBlocker": "candidate_screen_failed",
                "readyForPromotion": False,
                "phase1BDensificationRecommended": True,
                "nextRecommendedNextLever": "start_phase_1b_review_densification",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    review_densification_dir = tmp_path / "training_prep" / "touchline_review_densification_v1"
    review_densification_dir.mkdir(parents=True, exist_ok=True)
    (review_densification_dir / "review_densification_manifest.json").write_text(
        json.dumps(
            {
                "reviewDensificationBatchName": "touchline_review_densification_v1",
                "batchName": "touchline_review_densification_v1",
                "representativeFailingMatchId": "failing-0",
                "representativeControlMatchId": "control-0",
                "failingCurationUnitCount": 5,
                "controlCurationUnitCount": 1,
                "reviewItemCount": 21,
                "pendingReviewCount": 0,
                "reviewedPositiveCount": 15,
                "reviewedNegativeCount": 6,
                "yoloExportRegenerated": True,
                "readyForRetraining": True,
                "reviewDensificationPrimaryBlocker": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (review_densification_dir / "split_manifest.json").write_text(
        json.dumps(
            {
                "sourceAwareSplitLeakageDetected": False,
                "readyForRetraining": True,
                "reviewDensificationPrimaryBlocker": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (review_densification_dir / "review_bundle_report.json").write_text(
        json.dumps({"reviewBundleCount": 2, "seededIssueCount": 6}, indent=2),
        encoding="utf-8",
    )
    (review_densification_dir / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "batchGoal": "Complete the failing-source review overlay and unlock retraining readiness.",
                "goalAchieved": True,
                "roadmapAdvanceAllowed": True,
                "englishSummary": "The failing-source review items are complete, so retraining can start even though control review items remain pending.",
                "englishDecision": "The batch achieved its goal and the roadmap may advance to retraining.",
                "primaryBlocker": None,
                "pendingFailingReviewCount": 0,
                "pendingControlReviewCount": 4,
                "readyForRetraining": True,
                "nextRecommendedNextLever": "retrain_touchline_detector_candidate",
                "brainstormFixes": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "retrain_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "retrain_touchline_detector_candidate"
    assert suite_summary["reviewDensificationDiagnosis"]["reviewDensificationBatchName"] == (
        "touchline_review_densification_v1"
    )
    assert suite_summary["reviewDensificationDiagnosis"]["readyForRetraining"] is True
    assert suite_summary["reviewDensificationDiagnosis"]["batchOutcomeAnalysis"]["goalAchieved"] is True
    assert robustness_diagnosis["reviewDensificationDiagnosis"]["pendingReviewCount"] == 0
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["reviewDensificationDiagnosis"]["sourceAwareSplitLeakageDetected"]
        is False
    )


def test_run_source_robustness_batch_keeps_phase1b_when_batch_outcome_disallows_advance(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    proof_summary_path = tmp_path / "canonical-proof.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "suiteName": "robustness-suite",
                "suiteType": "saved_match_slice_suite",
                "baselineFingerprint": {
                    "detectorModelPath": "yolov10n.pt",
                },
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)
    monkeypatch.setattr(
        run_source_robustness_batch,
        "evaluate_source_robustness_outcome",
        lambda **_kwargs: {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.077,
            "passedPromotionGate": False,
            "promotionBlockers": ["failing_source_not_viable"],
        },
    )

    review_densification_dir = tmp_path / "training_prep" / "touchline_review_densification_v1"
    review_densification_dir.mkdir(parents=True, exist_ok=True)
    (review_densification_dir / "review_densification_manifest.json").write_text(
        json.dumps(
            {
                "reviewDensificationBatchName": "touchline_review_densification_v1",
                "batchName": "touchline_review_densification_v1",
                "representativeFailingMatchId": "failing-0",
                "representativeControlMatchId": "control-0",
                "failingCurationUnitCount": 2,
                "controlCurationUnitCount": 1,
                "reviewItemCount": 21,
                "pendingReviewCount": 4,
                "pendingFailingReviewCount": 0,
                "pendingControlReviewCount": 4,
                "failingSourceReviewComplete": True,
                "controlReviewComplete": False,
                "reviewedPositiveCount": 15,
                "reviewedNegativeCount": 2,
                "yoloExportRegenerated": True,
                "readyForRetraining": True,
                "reviewDensificationPrimaryBlocker": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (review_densification_dir / "split_manifest.json").write_text(
        json.dumps(
            {
                "sourceAwareSplitLeakageDetected": False,
                "readyForRetraining": True,
                "reviewDensificationPrimaryBlocker": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (review_densification_dir / "review_bundle_report.json").write_text(
        json.dumps({"reviewBundleCount": 2, "seededIssueCount": 3}, indent=2),
        encoding="utf-8",
    )
    (review_densification_dir / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "batchGoal": "Complete the failing-source review overlay and unlock retraining readiness.",
                "goalAchieved": False,
                "roadmapAdvanceAllowed": False,
                "englishSummary": "The export exists, but the batch still failed its gate because overlay validation did not pass cleanly.",
                "englishDecision": "The batch did not achieve its goal, so the roadmap must stay in Phase 1B.",
                "primaryBlocker": "overlay_validation_failed",
                "pendingFailingReviewCount": 0,
                "pendingControlReviewCount": 4,
                "readyForRetraining": False,
                "nextRecommendedNextLever": "start_phase_1b_review_densification",
                "brainstormFixes": [
                    "Fix the invalid overlay decisions and rerun the densification batch.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    suite_summary = _load_json(output_dir / "suite_summary.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "start_phase_1b_review_densification"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "start_phase_1b_review_densification"
    assert suite_summary["reviewDensificationDiagnosis"]["readyForRetraining"] is False
    assert suite_summary["reviewDensificationDiagnosis"]["batchOutcomeAnalysis"]["roadmapAdvanceAllowed"] is False


def test_run_source_robustness_batch_ingests_detector_candidate_data_quality_fix_diagnosis_and_keeps_evaluate_lane(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    proof_summary_path = tmp_path / "canonical-proof.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_plateau_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    data_fix_root = tmp_path / "training_prep" / "touchline_model_data_quality_fix_v1"
    data_fix_root.mkdir(parents=True, exist_ok=True)
    (data_fix_root / "data_quality_fix_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_model_data_quality_fix_v1",
                "dataQualityFixBatchName": "touchline_model_data_quality_fix_v1",
                "trainingCandidateName": "touchline_detector_candidate_v3",
                "selectedNewFailingWindowCount": 2,
                "autoAcceptedPseudoLabelCount": 37,
                "pendingFilteredReviewItemCount": 11,
                "pendingRawReviewItemCount": 7,
                "yoloExportReady": True,
                "trainingCompleted": False,
                "weightsReady": False,
                "readyForDetectorEvaluation": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (data_fix_root / "split_manifest.json").write_text(
        json.dumps(
            {
                "sourceAwareSplitLeakageDetected": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (data_fix_root / "review_bundle_report.json").write_text(
        json.dumps(
            {
                "seededIssueCount": 2,
                "reviewBundleCount": 1,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (data_fix_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": False,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "brainstormFixes": ["Retrain a stronger v3 candidate before rerunning bounded evaluation."],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "plateau-suite"
    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")
    active_lane_snapshot = _load_json(output_dir / "active_lane_snapshot.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["detectorCandidateDataQualityFixDiagnosis"]["trainingCandidateName"] == (
        "touchline_detector_candidate_v3"
    )
    assert suite_summary["detectorCandidateDataQualityFixDiagnosis"]["selectedNewFailingWindowCount"] == 2
    assert suite_summary["detectorCandidateDataQualityFixDiagnosis"]["goalAchieved"] is False
    assert suite_summary["detectorCandidateDataQualityFixDiagnosis"]["roadmapAdvanceAllowed"] is False
    assert (
        robustness_diagnosis["detectorCandidateDataQualityFixDiagnosis"]["nextRecommendedNextLever"]
        == "evaluate_touchline_detector_candidate"
    )
    assert (
        active_lane_snapshot["sourceRobustnessDiagnosis"]["detectorCandidateDataQualityFixDiagnosis"][
            "autoAcceptedPseudoLabelCount"
        ]
        == 37
    )


def test_run_source_robustness_batch_ingests_detector_candidate_proposal_signal_fix_diagnosis_and_keeps_evaluate_lane(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    proof_summary_path = tmp_path / "canonical-proof.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_plateau_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    proposal_fix_root = tmp_path / "training_prep" / "touchline_proposal_signal_generation_fix_v1"
    proposal_fix_root.mkdir(parents=True, exist_ok=True)
    (proposal_fix_root / "proposal_signal_fix_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_proposal_signal_generation_fix_v1",
                "proposalSignalFixBatchName": "touchline_proposal_signal_generation_fix_v1",
                "trainingCandidateName": "touchline_detector_candidate_v4",
                "proposalPositiveExampleCount": 104,
                "proposalNegativeExampleCount": 9,
                "meanRelativeBallAreaInProposalCrops": 0.018,
                "fullFrameMeanRelativeBallArea": 0.000038,
                "trainingCompleted": True,
                "weightsReady": True,
                "readyForDetectorEvaluation": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proposal_fix_root / "split_manifest.json").write_text(
        json.dumps({"sourceAwareSplitLeakageDetected": False}, indent=2),
        encoding="utf-8",
    )
    (proposal_fix_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "brainstormFixes": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v4"
    candidate_root.mkdir(parents=True, exist_ok=True)
    (candidate_root / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingBatchName": "touchline_detector_candidate_proposal_signal_generation_fix_v1",
                "trainingCandidateName": "touchline_detector_candidate_v4",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "readyForDetectorEvaluation": True,
                "trainingPrimaryBlocker": None,
                "baseModelPath": "yolov10n.pt",
                "bestWeightsPath": str(candidate_root / "weights" / "best.pt"),
                "resultsCsvPath": str(candidate_root / "results.csv"),
                "requestedGpuId": "preferred-gpu",
                "allocatedGpuId": "NVIDIA GeForce RTX 5090",
                "remoteDeviceName": "NVIDIA GeForce RTX 5090",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (candidate_root / "training_config.json").write_text(
        json.dumps(
            {
                "trainingRecipe": {
                    "baseModelPath": "yolov10n.pt",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (candidate_root / "evaluation_contract.json").write_text(
        json.dumps(
            {
                "candidateReadyForEvaluation": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (candidate_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "readyForDetectorEvaluation": True,
                "evaluationContractReady": True,
                "weightsReady": True,
                "trainingCompleted": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "plateau-suite"
    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["detectorCandidateProposalSignalFixDiagnosis"]["trainingCandidateName"] == (
        "touchline_detector_candidate_v4"
    )
    assert suite_summary["detectorCandidateProposalSignalFixDiagnosis"]["proposalPositiveExampleCount"] == 104
    assert suite_summary["detectorCandidateProposalSignalFixDiagnosis"]["goalAchieved"] is True
    assert suite_summary["detectorCandidateProposalSignalFixDiagnosis"]["roadmapAdvanceAllowed"] is False
    assert suite_summary["detectorTrainingDiagnosis"]["trainingCandidateName"] == "touchline_detector_candidate_v4"
    assert suite_summary["detectorTrainingDiagnosis"]["readyForDetectorEvaluation"] is True
    assert (
        robustness_diagnosis["detectorCandidateProposalSignalFixDiagnosis"]["nextRecommendedNextLever"]
        == "evaluate_touchline_detector_candidate"
    )


def test_run_source_robustness_batch_prefers_latest_detector_candidate_proposal_signal_fix_diagnosis(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    proof_summary_path = tmp_path / "canonical-proof.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_plateau_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    proposal_fix_v1_root = tmp_path / "training_prep" / "touchline_proposal_signal_generation_fix_v1"
    proposal_fix_v1_root.mkdir(parents=True, exist_ok=True)
    (proposal_fix_v1_root / "proposal_signal_fix_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_proposal_signal_generation_fix_v1",
                "proposalSignalFixBatchName": "touchline_proposal_signal_generation_fix_v1",
                "trainingCandidateName": "touchline_detector_candidate_v4",
                "proposalPositiveExampleCount": 104,
                "proposalNegativeExampleCount": 9,
                "windowFamily": "proposal_crops_v1",
                "trainingCompleted": True,
                "weightsReady": True,
                "readyForDetectorEvaluation": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proposal_fix_v1_root / "split_manifest.json").write_text(
        json.dumps({"sourceAwareSplitLeakageDetected": False}, indent=2),
        encoding="utf-8",
    )
    (proposal_fix_v1_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    proposal_fix_v2_root = tmp_path / "training_prep" / "touchline_proposal_signal_generation_fix_v2"
    proposal_fix_v2_root.mkdir(parents=True, exist_ok=True)
    (proposal_fix_v2_root / "proposal_signal_fix_manifest.json").write_text(
        json.dumps(
            {
                "batchName": "touchline_proposal_signal_generation_fix_v2",
                "proposalSignalFixBatchName": "touchline_proposal_signal_generation_fix_v2",
                "trainingCandidateName": "touchline_detector_candidate_v6",
                "proposalPositiveExampleCount": 212,
                "proposalNegativeExampleCount": 88,
                "windowFamily": "proposal_windows_075",
                "positiveWindowKindCounts": {"direct_seed_tight": 120, "player_ranked": 92},
                "negativeWindowKindCounts": {"player_ranked": 88},
                "proposalWindowValidationPositiveImageCount": 31,
                "proposalWindowSanityDetectedImageCount": 18,
                "trainingCompleted": True,
                "weightsReady": True,
                "readyForDetectorEvaluation": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proposal_fix_v2_root / "split_manifest.json").write_text(
        json.dumps({"sourceAwareSplitLeakageDetected": False}, indent=2),
        encoding="utf-8",
    )
    (proposal_fix_v2_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "brainstormFixes": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "plateau-suite"
    suite_summary = _load_json(output_dir / "suite_summary.json")
    diagnosis = suite_summary["detectorCandidateProposalSignalFixDiagnosis"]

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert diagnosis["trainingCandidateName"] == "touchline_detector_candidate_v6"
    assert diagnosis["proposalSignalFixBatchName"] == "touchline_proposal_signal_generation_fix_v2"
    assert diagnosis["windowFamily"] == "proposal_windows_075"
    assert diagnosis["proposalPositiveExampleCount"] == 212
    assert diagnosis["proposalNegativeExampleCount"] == 88
    assert diagnosis["proposalWindowValidationPositiveImageCount"] == 31
    assert diagnosis["proposalWindowSanityDetectedImageCount"] == 18
    assert diagnosis["positiveWindowKindCounts"] == {"direct_seed_tight": 120, "player_ranked": 92}
    assert diagnosis["negativeWindowKindCounts"] == {"player_ranked": 88}


def test_run_source_robustness_batch_ingests_training_quality_gate_and_validation_gate_remediation_diagnoses(
    tmp_path,
    monkeypatch,
):
    storage = Storage(tmp_path)
    manifest_path = tmp_path / "suite.json"
    proof_summary_path = tmp_path / "canonical-proof-summary.json"
    proof_summary_path.write_text(
        json.dumps(
            {
                "acceptedBallFrames": 174,
                "controlledPossessionFrames": 137,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.586,
            }
        ),
        encoding="utf-8",
    )
    _write_realistic_source_robustness_suite(storage, manifest_path)
    _disable_combined_reopen_matrix(monkeypatch)

    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v5"
    candidate_root.mkdir(parents=True, exist_ok=True)
    (candidate_root / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v5",
                "trainingBatchName": "touchline_validation_gate_remediation_v1",
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "trainingQualityGatePassed": True,
                "trainingQualityGatePrimaryBlocker": None,
                "bestWeightsPath": "/tmp/v5/best.pt",
                "resultsCsvPath": "/tmp/v5/results.csv",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (candidate_root / "training_config.json").write_text(
        json.dumps(
            {
                "trainingRecipe": {
                    "baseModelPath": "yolov10n.pt",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (candidate_root / "evaluation_contract.json").write_text(
        json.dumps({"candidateReadyForEvaluation": True}, indent=2),
        encoding="utf-8",
    )
    (candidate_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    gate_root = candidate_root / "training_quality_gate_v1"
    gate_root.mkdir(parents=True, exist_ok=True)
    (gate_root / "quality_gate_summary.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v5",
                "trainingQualityGatePassed": True,
                "trainingQualityGatePrimaryBlocker": None,
                "validationImageCount": 3,
                "validationPositiveLabelImageCount": 2,
                "validationEmptyLabelImageCount": 1,
                "validationInformative": True,
                "maxValidationPrecision": 0.51,
                "maxValidationRecall": 0.43,
                "maxValidationMap50": 0.49,
                "localPositiveSanityDetectedImageCount": 3,
                "readyForDetectorEvaluation": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (gate_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    remediation_root = tmp_path / "training_prep" / "touchline_validation_gate_remediation_v1"
    remediation_root.mkdir(parents=True, exist_ok=True)
    (remediation_root / "validation_gate_remediation_manifest.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": "touchline_detector_candidate_v5",
                "validationGateRemediationBatchName": "touchline_validation_gate_remediation_v1",
                "blockedCandidateName": "touchline_detector_candidate_v4",
                "selectedValidationPositiveCurationUnitId": "failing-unit-a",
                "validationPositiveLabelImageCount": 2,
                "validationEmptyLabelImageCount": 1,
                "validationInformative": True,
                "trainingCompleted": True,
                "weightsReady": True,
                "readyForDetectorEvaluation": True,
                "goalAchieved": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (remediation_root / "split_manifest.json").write_text(
        json.dumps(
            {
                "sourceAwareSplitLeakageDetected": False,
                "validationPositiveCurationUnitCount": 1,
                "validationControlCurationUnitCount": 1,
                "validationPositiveLabelImageCount": 2,
                "validationEmptyLabelImageCount": 1,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (remediation_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "roadmapAdvanceAllowed": False,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_source_robustness_batch.run_source_robustness_batch(
        storage_root=tmp_path,
        manifest_path=manifest_path,
        failing_source_clip_id="trimed-5min.mp4",
        comparison_source_clip_id="trimed-football-2-1minute.mp4",
        canonical_proof_summary_path=proof_summary_path,
    )

    output_dir = tmp_path / "benchmark_suites" / "robustness-suite"
    suite_summary = _load_json(output_dir / "suite_summary.json")
    robustness_diagnosis = _load_json(output_dir / "suite_robustness_diagnosis.json")

    assert result["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["sourceRobustnessRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert suite_summary["detectorTrainingQualityGateDiagnosis"]["trainingCandidateName"] == "touchline_detector_candidate_v5"
    assert suite_summary["detectorTrainingQualityGateDiagnosis"]["trainingQualityGatePassed"] is True
    assert (
        suite_summary["detectorCandidateValidationGateRemediationDiagnosis"]["blockedCandidateName"]
        == "touchline_detector_candidate_v4"
    )
    assert (
        robustness_diagnosis["detectorCandidateValidationGateRemediationDiagnosis"]["validationPositiveLabelImageCount"]
        == 2
    )
