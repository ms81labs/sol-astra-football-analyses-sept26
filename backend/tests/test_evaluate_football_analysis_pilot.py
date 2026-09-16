from __future__ import annotations

import hashlib
import json

import pytest

import backend.scripts.evaluate_football_analysis_pilot as pilot
from backend.scripts.evaluate_football_analysis_pilot import (
    build_trackeval_sequence_data,
    evaluate_ball,
    evaluate_events,
    evaluate_pitch,
    evaluate_players,
    evaluate_possession,
    evaluate_source_acceptance,
    evaluate_tracking,
    evaluation_frame_ids,
    evaluate_task_artifacts,
    load_prediction_artifacts,
    main,
    normalize_prediction_artifacts,
    wilson_interval,
)


PROTOCOL = {
    "version": 3,
    "evaluationFrames": {"targetFps": 5},
    "ball": {"iouThreshold": 0.5},
    "players": {"detectionIouThreshold": 0.5},
    "confidenceIntervals": {"level": 0.95, "bootstrapSamples": 10_000, "percentileMethod": "linear"},
    "events": {"classes": ["pass", "shot"], "toleranceSeconds": 2.0},
    "acceptance": {
        "ballPrecisionMinimum": 0.95,
        "visibleBallRecallMinimum": 0.85,
        "pitchMedianErrorMetersMaximum": 1.0,
        "pitchP95ErrorMetersMaximum": 3.0,
        "supportedEventPrecisionMinimum": 0.8,
        "supportedEventRecallMinimum": 0.8,
    },
}
TASK = {
    "sourceStartFrame": 10,
    "sourceEndFrameExclusive": 20,
    "sourceFps": 25.0,
    "evaluationFrameStep": 5,
    "evaluationFrameCount": 2,
}


def _frame(frame_id: int, visibility: str, bbox=None) -> dict[str, object]:
    return {
        "frameId": frame_id,
        "ball": {"visibility": visibility, "bbox": bbox},
        "entities": [],
        "possession": {"state": "unknown", "team": "unknown", "trackId": None},
    }


def _ball(frame_id: int, bbox: list[float]) -> dict[str, object]:
    return {
        "Entity_Type": "ball",
        "Frame_ID": frame_id,
        "Source_X1": bbox[0],
        "Source_Y1": bbox[1],
        "Source_X2": bbox[2],
        "Source_Y2": bbox[3],
    }


def test_uses_the_production_aligned_global_frame_modulo_rule() -> None:
    assert evaluation_frame_ids(TASK, PROTOCOL) == [10, 15]


def test_rejects_task_evaluation_cadence_that_drifted_from_protocol() -> None:
    with pytest.raises(ValueError, match="evaluation frame cadence"):
        evaluation_frame_ids({**TASK, "evaluationFrameCount": 3}, PROTOCOL)


def test_wilson_interval_is_defined_only_for_a_nonzero_denominator() -> None:
    assert wilson_interval(1, 2, level=0.95) == pytest.approx((0.094531206, 0.905468794))
    assert wilson_interval(0, 0, level=0.95) is None


def test_scores_ball_predictions_with_ignored_truth_and_source_strata() -> None:
    labels = {
        "frames": [
            _frame(frame_id, "visible", [10, 10, 20, 20])
            if frame_id == 10
            else _frame(frame_id, "not_visible")
            if frame_id == 15
            else _frame(frame_id, "unknown")
            for frame_id in range(10, 20)
        ]
    }
    predictions = [
        _ball(10, [10, 10, 20, 20]),
        _ball(10, [30, 30, 40, 40]),
        _ball(15, [1, 1, 2, 2]),
        _ball(11, [10, 10, 20, 20]),
    ]

    result = evaluate_ball(
        TASK,
        labels,
        predictions,
        PROTOCOL,
        prediction_sources={10: "observed", 15: "inferred"},
    )

    assert result["counts"] == {
        "evaluationFrames": 2,
        "ignoredFrames": 0,
        "visibleTruth": 1,
        "notVisibleTruth": 1,
        "predictions": 3,
        "truePositives": 1,
        "falsePositives": 2,
        "falseNegatives": 0,
    }
    assert result["precision"] == pytest.approx(1 / 3)
    assert result["recall"] == 1.0
    assert result["falsePositivesPerMinute"] == 300.0
    assert result["meanMatchedIoU"] == 1.0
    assert result["medianCenterErrorPixels"] == 0.0
    assert result["predictionSourceBreakdown"] == {"observed": 2, "inferred": 1, "unknown": 0}
    assert result["precision95"] == pytest.approx((0.0614919447, 0.7923403992))
    assert result["recall95"] == pytest.approx((0.2065493144, 1.0))


def test_scores_events_one_to_one_by_class_window_and_known_team() -> None:
    labels = {
        "events": [
            {"eventId": "pass-1", "type": "pass", "startFrame": 10, "endFrameExclusive": 12, "team": "home"},
            {"eventId": "shot-1", "type": "shot", "startFrame": 15, "endFrameExclusive": 16, "team": "unknown"},
        ]
    }
    predictions = [
        {"type": "pass", "frameId": 11, "timestamp": 0.44, "team": "home"},
        {"type": "pass", "frameId": 16, "timestamp": 0.64, "team": "away"},
        {"type": "shot", "frameId": 19, "timestamp": 0.76, "team": "unassigned"},
        {"type": "shot", "frameId": 25, "timestamp": 1.0, "team": "home"},
    ]

    result = evaluate_events(TASK, labels, predictions, PROTOCOL)

    assert result["classes"]["pass"]["counts"] == {
        "truth": 1,
        "predictions": 2,
        "truePositives": 1,
        "falsePositives": 1,
        "falseNegatives": 0,
    }
    assert result["classes"]["pass"]["precision"] == 0.5
    assert result["classes"]["pass"]["recall"] == 1.0
    assert result["classes"]["shot"]["counts"]["truePositives"] == 1
    assert result["classes"]["shot"]["counts"]["predictions"] == 1


def test_event_assignment_maximizes_matches_before_distance() -> None:
    task = {"sourceStartFrame": 0, "sourceEndFrameExclusive": 150, "sourceFps": 25.0}
    labels = {
        "events": [
            {"eventId": "later", "type": "pass", "startFrame": 50, "endFrameExclusive": 51, "team": "unknown"},
            {"eventId": "earlier", "type": "pass", "startFrame": 0, "endFrameExclusive": 1, "team": "unknown"},
        ]
    }
    predictions = [
        {"type": "pass", "frameId": 0, "timestamp": 0.0, "team": "unassigned"},
        {"type": "pass", "frameId": 100, "timestamp": 4.0, "team": "unassigned"},
    ]

    result = evaluate_events(task, labels, predictions, PROTOCOL)

    assert result["classes"]["pass"]["counts"]["truePositives"] == 2
    assert result["classes"]["shot"]["applicable"] is False
    assert result["classes"]["shot"]["precision"] is None
    assert result["classes"]["shot"]["recall"] is None


def test_scores_player_detection_team_role_and_possession_through_association() -> None:
    labels = {
        "frames": [
            {
                **_frame(frame_id, "not_visible"),
                "entities": (
                    [
                        {"trackId": "home-7", "kind": "player", "team": "home", "bbox": [0, 0, 10, 10]},
                        {"trackId": "ref-1", "kind": "referee", "team": "unknown", "bbox": [20, 0, 30, 10]},
                    ]
                    if frame_id == 10
                    else [{"trackId": "away-8", "kind": "player", "team": "away", "bbox": [0, 0, 10, 10]}]
                    if frame_id == 15
                    else []
                ),
                "possession": (
                    {"state": "observed", "team": "home", "trackId": "home-7"}
                    if frame_id == 10
                    else {"state": "unknown", "team": "unknown", "trackId": None}
                ),
            }
            for frame_id in range(10, 20)
        ]
    }
    predictions = [
        {**_ball(10, [0, 0, 10, 10]), "Entity_Type": "my_team", "Track_ID": 101},
        {**_ball(10, [20, 0, 30, 10]), "Entity_Type": "player", "Track_ID": 102},
        {**_ball(10, [40, 0, 50, 10]), "Entity_Type": "player", "Track_ID": 103},
        {**_ball(15, [0, 0, 10, 10]), "Entity_Type": "enemy", "Track_ID": 202},
    ]
    team_mapping = {"my_team": "home", "enemy": "away"}

    player_result = evaluate_players(TASK, labels, predictions, PROTOCOL, team_mapping=team_mapping)

    assert player_result["counts"] == {
        "truth": 3,
        "predictions": 4,
        "truePositives": 2,
        "falsePositives": 2,
        "falseNegatives": 1,
    }
    assert player_result["precision"] == 0.5
    assert player_result["recall"] == pytest.approx(2 / 3)
    assert player_result["teamAgreement"]["correct"] == 2
    assert player_result["teamAgreement"]["total"] == 2
    assert player_result["roleAgreement"]["correct"] == 2
    assert player_result["trackAssociations"] == {10: {"home-7": 101}, 15: {"away-8": 202}}

    possession_result = evaluate_possession(
        TASK,
        labels,
        [
            {"frameId": 10, "possession": {"team": "my_team", "trackId": 101}},
            {"frameId": 15, "possession": {"team": "enemy", "trackId": 202}},
        ],
        PROTOCOL,
        track_associations=player_result["trackAssociations"],
        team_mapping=team_mapping,
    )

    assert possession_result["counts"] == {
        "evaluationFrames": 2,
        "scoredTeamFrames": 1,
        "unknownTruthFrames": 1,
        "correctTeamFrames": 1,
        "scoredEntityFrames": 1,
        "correctEntityFrames": 1,
    }
    assert possession_result["teamAgreement"] == 1.0
    assert possession_result["entityAgreement"] == 1.0


def test_scores_pitch_error_only_from_independent_referenced_positions() -> None:
    labels = {
        "pitchReference": {
            "sourceId": "reference-fixture",
            "sha256": "b" * 64,
            "associationMethod": "predeclared_identity",
        },
        "frames": [
            {
                **_frame(frame_id, "not_visible"),
                "entities": (
                    [{"trackId": "p1", "kind": "player", "team": "home", "bbox": [0, 0, 10, 10], "pitchPositionMeters": [3, 4]}]
                    if frame_id == 10
                    else [{"trackId": "p2", "kind": "player", "team": "away", "bbox": [0, 0, 10, 10], "pitchPositionMeters": [10, 10]}]
                    if frame_id == 15
                    else []
                ),
            }
            for frame_id in range(10, 20)
        ],
    }
    predictions = [
        {**_ball(10, [0, 0, 10, 10]), "Entity_Type": "my_team", "Track_ID": 101, "X": 0, "Y": 0},
        {**_ball(15, [0, 0, 10, 10]), "Entity_Type": "enemy", "Track_ID": 202, "X": 13, "Y": 14},
    ]

    result = evaluate_pitch(
        {**TASK, "sourceId": "fixture-source"},
        labels,
        predictions,
        PROTOCOL,
        track_associations={10: {"p1": 101}, 15: {"p2": 202}},
    )

    assert result["eligibleForAcceptance"] is True
    assert result["referencePositionCount"] == 2
    assert result["matchedPositionCount"] == 2
    assert result["referenceCoverage"] == 1.0
    assert result["medianErrorMeters"] == 5.0
    assert result["p95ErrorMeters"] == 5.0
    assert result["maximumErrorMeters"] == 5.0
    assert result["medianErrorMeters95"] == (5.0, 5.0)

    labels["pitchReference"] = None
    assert evaluate_pitch(
        {**TASK, "sourceId": "fixture-source"},
        labels,
        predictions,
        PROTOCOL,
        track_associations={10: {"p1": 101}, 15: {"p2": 202}},
    )["eligibleForAcceptance"] is False


def test_scores_possession_transitions_across_unknown_gaps() -> None:
    task = {
        "sourceId": "fixture-source",
        "sourceStartFrame": 0,
        "sourceEndFrameExclusive": 30,
        "sourceFps": 25.0,
        "evaluationFrameStep": 5,
        "evaluationFrameCount": 6,
    }
    labels = {
        "frames": [
            {
                **_frame(frame_id, "not_visible"),
                "possession": (
                    {"state": "observed", "team": "home", "trackId": None}
                    if frame_id < 10
                    else {"state": "unknown", "team": "unknown", "trackId": None}
                    if frame_id < 13
                    else {"state": "observed", "team": "away", "trackId": None}
                    if frame_id < 23
                    else {"state": "observed", "team": "home", "trackId": None}
                ),
            }
            for frame_id in range(0, 30, 5)
        ]
    }
    predictions = [
        {"frameId": frame_id, "possession": {"team": team, "trackId": None}}
        for frame_id, team in [(0, "home"), (5, "home"), (10, "unassigned"), (15, "away"), (20, "away"), (25, "home")]
    ]

    result = evaluate_possession(task, labels, predictions, PROTOCOL, track_associations={})

    assert result["transitions"]["counts"] == {"truth": 2, "predictions": 2, "matched": 2}
    assert result["transitions"]["signedErrorsSeconds"] == [0.0, 0.0]
    assert result["transitions"]["medianAbsoluteErrorSeconds"] == 0.0


def test_builds_trackeval_data_with_contiguous_task_local_ids() -> None:
    labels = {
        "frames": [
            {
                **_frame(frame_id, "not_visible"),
                "entities": (
                    [{"trackId": "p1", "kind": "player", "team": "home", "bbox": [0, 0, 10, 10]}]
                    if frame_id in {10, 15}
                    else []
                ),
            }
            for frame_id in range(10, 20)
        ]
    }
    predictions = [
        {**_ball(frame_id, [0, 0, 10, 10]), "Entity_Type": "player", "Track_ID": 99}
        for frame_id in (10, 15)
    ]

    data = build_trackeval_sequence_data(TASK, labels, predictions, PROTOCOL)

    assert data["num_timesteps"] == 2
    assert data["num_gt_dets"] == 2
    assert data["num_tracker_dets"] == 2
    assert data["num_gt_ids"] == 1
    assert data["num_tracker_ids"] == 1
    assert data["gt_ids"][0].tolist() == [0]
    assert data["tracker_ids"][1].tolist() == [0]
    assert data["similarity_scores"][0].tolist() == [[1.0]]


def test_tracking_evaluator_rejects_an_unpinned_trackeval_checkout(tmp_path) -> None:
    with pytest.raises(ValueError, match="pinned TrackEval commit"):
        evaluate_tracking(
            {
                "num_timesteps": 0,
                "num_gt_dets": 0,
                "num_tracker_dets": 0,
                "num_gt_ids": 0,
                "num_tracker_ids": 0,
                "gt_ids": [],
                "tracker_ids": [],
                "similarity_scores": [],
            },
            trackeval_root=tmp_path,
        )


def test_normalizes_task_interval_predictions_to_source_frame_identity() -> None:
    raw_rows, assignments, events, sources = normalize_prediction_artifacts(
        TASK,
        [{**_ball(0, [0, 0, 1, 1]), "Timestamp": 0.0}],
        [{"frameId": 0, "timestamp": 0.0, "team": "unassigned", "trackId": None}],
        [{"type": "pass", "frameId": 0, "timestamp": 0.0, "team": "unassigned"}],
        {0: "observed"},
        prediction_scope="task-interval",
    )

    assert (raw_rows[0]["Frame_ID"], raw_rows[0]["Timestamp"]) == (10, 0.4)
    assert (assignments[0]["frameId"], assignments[0]["timestamp"]) == (10, 0.4)
    assert (events[0]["frameId"], events[0]["timestamp"]) == (10, 0.4)
    assert sources == {10: "observed"}


def test_rejects_task_interval_prediction_grid_that_cannot_overlap_frozen_labels() -> None:
    off_grid = {**TASK, "sourceStartFrame": 12, "sourceEndFrameExclusive": 22}
    # The native pipeline samples local frames 0, 5; frozen labels use source frames 15, 20.
    with pytest.raises(ValueError, match="off-grid task-interval"):
        normalize_prediction_artifacts(
            off_grid,
            [{**_ball(0, [0, 0, 1, 1]), "Timestamp": 0.0}],
            [],
            [],
            {0: "observed"},
            prediction_scope="task-interval",
        )


def test_maps_a_globally_aligned_inference_clip_to_the_exact_frozen_source_frame() -> None:
    off_grid = {**TASK, "sourceStartFrame": 12, "sourceEndFrameExclusive": 22}
    rows, assignments, events, sources = normalize_prediction_artifacts(
        off_grid,
        [{**_ball(5, [0, 0, 1, 1]), "Timestamp": 0.2}],
        [{"frameId": 5, "timestamp": 0.2}],
        [{"type": "pass", "frameId": 5, "timestamp": 0.2}],
        {5: "observed"},
        prediction_scope="task-interval",
        prediction_source_start_frame=10,
    )

    assert rows[0]["Frame_ID"] == 15
    assert rows[0]["Timestamp"] == pytest.approx(0.6)
    assert assignments[0]["frameId"] == events[0]["frameId"] == 15
    assert sources == {15: "observed"}
    assert 15 in evaluation_frame_ids(off_grid, PROTOCOL)


def test_loads_native_match_artifacts_and_scores_one_task(tmp_path, monkeypatch) -> None:
    artifact_dir = tmp_path / "match"
    artifact_dir.mkdir()
    row = {**_ball(5, [10, 10, 20, 20]), "Timestamp": 0.2, "Track_ID": -1, "X": 1.0, "Y": 2.0}
    (artifact_dir / "raw_rows.json").write_text(json.dumps([row]), encoding="utf-8")
    (artifact_dir / "analytics.json").write_text(
        json.dumps({"ballAssignments": [{"frameId": 5, "timestamp": 0.2, "team": "unassigned", "trackId": None}]}),
        encoding="utf-8",
    )
    (artifact_dir / "events.json").write_text(json.dumps([]), encoding="utf-8")
    (artifact_dir / "ball_truth_layers.json").write_text(
        json.dumps({"observedBall": {"rows": [row]}, "inferredBall": {"rows": []}}),
        encoding="utf-8",
    )
    (artifact_dir / "input_video_identity.json").write_text(
        json.dumps({
            "schemaVersion": 1,
            "jobId": "fixture-job",
            "matchId": "match",
            "sourceCommit": "b" * 40,
            "manifestSha256": "b" * 64,
            "receiptSha256": "c" * 64,
            "inputVideoSha256": "a" * 64,
            "inputVideoSizeBytes": 100,
        }),
        encoding="utf-8",
    )

    rows, assignments, events, sources = load_prediction_artifacts(artifact_dir)
    assert (rows, assignments, events, sources) == ([row], [{"frameId": 5, "timestamp": 0.2, "team": "unassigned", "trackId": None}], [], {5: "observed"})

    task = {**TASK, "sourceStartFrame": 12, "sourceEndFrameExclusive": 22, "sourceId": "fixture", "taskId": "fixture-01"}
    labels = {
        "pitchReference": None,
        "frames": [
            {
                **_frame(frame_id, "visible" if frame_id == 15 else "not_visible", [10, 10, 20, 20] if frame_id == 15 else None),
                "entities": [],
            }
            for frame_id in range(12, 22)
        ],
        "events": [],
    }
    monkeypatch.setattr(pilot, "evaluate_tracking", lambda data, *, trackeval_root: {"HOTA": 1.0})

    result = evaluate_task_artifacts(
        task,
        labels,
        PROTOCOL,
        artifact_dir=artifact_dir,
        prediction_scope="task-interval",
        prediction_source_start_frame=10,
        expected_input_video_sha256="a" * 64,
        trackeval_root=tmp_path,
    )

    assert result["taskId"] == "fixture-01"
    assert result["predictionSourceStartFrame"] == 10
    assert result["predictionInputVideoSha256"] == "a" * 64
    assert result["ball"]["counts"]["truePositives"] == 1
    assert result["ball"]["predictionSourceBreakdown"]["observed"] == 1
    assert result["tracking"] == {"HOTA": 1.0}
    assert result["teamMapping"] == {}


def test_rejects_missing_or_mismatched_native_input_video_identity(tmp_path) -> None:
    artifact_dir = tmp_path / "match"
    artifact_dir.mkdir()
    with pytest.raises(ValueError, match="missing or invalid"):
        pilot._validated_input_video_identity(artifact_dir, "a" * 64)

    (artifact_dir / "input_video_identity.json").write_text(json.dumps({
        "schemaVersion": 1,
        "jobId": "fixture-job",
        "matchId": "match",
        "sourceCommit": "b" * 40,
        "manifestSha256": "b" * 64,
        "receiptSha256": "c" * 64,
        "inputVideoSha256": "a" * 64,
        "inputVideoSizeBytes": 100,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        pilot._validated_input_video_identity(artifact_dir, "d" * 64)


def test_held_out_scoring_requires_input_video_hash_before_opening_artifacts(tmp_path) -> None:
    with pytest.raises(ValueError, match="held-out scoring requires"):
        evaluate_task_artifacts(
            {**TASK, "evaluationRole": "held_out_test"},
            {},
            PROTOCOL,
            artifact_dir=tmp_path,
            prediction_scope="task-interval",
            trackeval_root=tmp_path,
        )


def _frozen_clip_fixture(tmp_path, source_start):
    task = {
        "taskId": "fixture-01", "sourceId": "fixture-source", "evaluationRole": "held_out_test",
        "labelOutputPath": str(tmp_path / "missing-independent-label.json"),
        "sourceStartFrame": source_start,
        "sourceEndFrameExclusive": source_start + 10, "frameCount": 10,
        "evaluationFrameStep": 5, "sourceWidth": 40, "sourceHeight": 30,
        "videoSha256": "b" * 64,
    }
    task_manifest = tmp_path / "tasks.json"
    task_manifest.write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    media_root = tmp_path / "media"
    annotation_root = media_root / "annotation_clips"
    aligned_root = media_root / "inference_clips"
    annotation_root.mkdir(parents=True)
    aligned_root.mkdir()
    annotation_clip = annotation_root / "fixture-01.mp4"
    annotation_clip.write_bytes(b"annotation clip")
    annotation_sha = hashlib.sha256(b"annotation clip").hexdigest()
    (annotation_root / "annotation_clips_manifest_v1.json").write_text(json.dumps({
        "taskManifestSha256": hashlib.sha256(task_manifest.read_bytes()).hexdigest(),
        "entries": [{
            "taskId": "fixture-01", "path": str(annotation_clip),
            "sha256": annotation_sha, "sourceStartFrame": source_start,
            "sourceEndFrameExclusive": source_start + 10, "frameCount": 10,
            "width": 40, "height": 30, "sourceVideoSha256": "b" * 64,
        }],
    }), encoding="utf-8")
    declared_clip = annotation_clip
    declared_sha = annotation_sha
    if source_start % 5:
        declared_clip = aligned_root / "fixture-01-aligned.mp4"
        declared_clip.write_bytes(b"aligned clip")
        declared_sha = hashlib.sha256(b"aligned clip").hexdigest()
        aligned_start = source_start - source_start % 5
        (aligned_root / "aligned_media_manifest_v1.tsv").write_text(
            "taskId\talignedStartFrame\tprefixFrames\tframeCount\tsourceVideoSha256\tannotationSha256\talignedSha256\n"
            f"fixture-01\t{aligned_start}\t{source_start - aligned_start}\t{10 + source_start - aligned_start}\t{'b' * 64}\t{annotation_sha}\t{declared_sha}\n",
            encoding="utf-8",
        )

    return task, task_manifest, media_root, declared_clip, declared_sha


@pytest.mark.parametrize("source_start", [7, 10])
def test_declared_held_out_input_hash_matches_the_frozen_clip_bytes(tmp_path, source_start) -> None:
    task, task_manifest, media_root, declared_clip, declared_sha = _frozen_clip_fixture(tmp_path, source_start)
    assert pilot._declared_input_video_sha256(task, task_manifest, media_root) == declared_sha
    declared_clip.write_bytes(b"different footage")
    with pytest.raises(ValueError, match="clip SHA-256"):
        pilot._declared_input_video_sha256(task, task_manifest, media_root)


def test_task_cli_rejects_a_typed_hash_for_the_wrong_held_out_clip_before_labels(tmp_path, monkeypatch) -> None:
    _task, task_manifest, media_root, _clip, declared_sha = _frozen_clip_fixture(tmp_path, 7)
    declaration, _declaration_sha256 = _source_declaration(tmp_path, "fixture-source")
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({"labelingProtocol": {"scoringProtocol": PROTOCOL}}), encoding="utf-8")
    monkeypatch.setattr(pilot, "_PILOT_MEDIA_ROOT", media_root)
    with pytest.raises(ValueError, match="declared clip SHA-256"):
        main([
            "task", "--task-id", "fixture-01", "--task-manifest", str(task_manifest),
            "--corpus", str(corpus), "--artifact-dir", str(tmp_path / "artifacts"),
            "--prediction-scope", "task-interval", "--trackeval-root", str(tmp_path),
            "--source-declaration", str(declaration), "--expected-input-video-sha256", "c" * 64,
        ])
    assert declared_sha != "c" * 64


def test_frozen_media_root_stays_at_the_repository_from_other_working_directories(tmp_path, monkeypatch) -> None:
    before = (pilot._PILOT_MEDIA_ROOT / "annotation_clips").resolve()
    monkeypatch.chdir(tmp_path)
    assert (pilot._PILOT_MEDIA_ROOT / "annotation_clips").resolve() == before


def test_declared_clip_rejects_a_different_relative_manifest_path(tmp_path, monkeypatch) -> None:
    task, task_manifest, media_root, _clip, declared_sha = _frozen_clip_fixture(tmp_path, 10)
    annotation_manifest = media_root / "annotation_clips" / "annotation_clips_manifest_v1.json"
    payload = json.loads(annotation_manifest.read_text(encoding="utf-8"))
    payload["entries"][0]["path"] = "backend/storage/pilot/annotation_clips/fixture-01.mp4"
    annotation_manifest.write_text(json.dumps(payload), encoding="utf-8")
    other_workdir = tmp_path / "other-workdir"
    other_workdir.mkdir()
    monkeypatch.chdir(other_workdir)

    with pytest.raises(ValueError, match="annotation clip does not match"):
        pilot._declared_input_video_sha256(task, task_manifest, media_root)


def test_aggregates_frozen_acceptance_by_source_without_merging_task_frame_ids() -> None:
    def task_result(task_id: str, true_positives: int, errors: list[float]) -> dict[str, object]:
        return {
            "taskId": task_id,
            "sourceId": "two-halves",
            "teamMapping": {"my_team": "home", "enemy": "away"},
            "players": {"precision": 1.0},
            "tracking": {"HOTA": 1.0},
            "possession": {"teamAgreement": 1.0},
            "ball": {"counts": {
                "evaluationFrames": true_positives, "ignoredFrames": 0,
                "visibleTruth": true_positives, "notVisibleTruth": 0,
                "predictions": true_positives, "truePositives": true_positives,
                "falsePositives": 0, "falseNegatives": 0,
            }, "predictionSourceBreakdown": {"observed": true_positives, "inferred": 0, "unknown": 0}},
            "pitch": {
                "eligibleForAcceptance": bool(errors),
                "errorsMeters": errors,
                "referencePositionCount": len(errors),
                "matchedPositionCount": len(errors),
            },
            "events": {
                "classes": {
                    event_type: {"counts": {"truth": 1, "predictions": 1, "truePositives": 1, "falsePositives": 0, "falseNegatives": 0}}
                    for event_type in ("pass", "shot")
                }
            },
        }

    result = evaluate_source_acceptance(
        "two-halves",
        [task_result("half-1", 2, [0.5]), task_result("half-2", 3, [1.0])],
        PROTOCOL,
        expected_task_ids=["half-1", "half-2"],
        team_mapping={"my_team": "home", "enemy": "away"},
    )

    assert result["taskIds"] == ["half-1", "half-2"]
    assert [task["taskId"] for task in result["taskMetrics"]] == ["half-1", "half-2"]
    assert result["taskMetrics"][0]["tracking"] == {"HOTA": 1.0}
    assert result["ball"]["counts"]["truePositives"] == 5
    assert result["pitch"]["medianErrorMeters"] == 0.75
    assert result["events"]["classes"]["pass"]["precision"] == 1.0
    assert result["acceptance"]["passed"] is True
    assert evaluate_source_acceptance(
        "two-halves",
        [task_result("half-2", 3, [1.0]), task_result("half-1", 2, [0.5])],
        PROTOCOL,
        expected_task_ids=["half-1", "half-2"],
        team_mapping={"my_team": "home", "enemy": "away"},
    ) == result

    missing_pitch = task_result("half-2", 3, [])
    assert evaluate_source_acceptance(
        "two-halves",
        [task_result("half-1", 2, [0.5]), missing_pitch],
        PROTOCOL,
        expected_task_ids=["half-1", "half-2"],
        team_mapping={"my_team": "home", "enemy": "away"},
    )["acceptance"]["passed"] is True
    missing_pitch_flag = task_result("half-2", 3, [])
    del missing_pitch_flag["pitch"]["eligibleForAcceptance"]
    with pytest.raises(ValueError, match="pitch eligibility"):
        evaluate_source_acceptance(
            "two-halves", [task_result("half-1", 2, [0.5]), missing_pitch_flag],
            PROTOCOL, expected_task_ids=["half-1", "half-2"],
            team_mapping={"my_team": "home", "enemy": "away"},
        )
    assert evaluate_source_acceptance(
        "two-halves",
        [{**missing_pitch, "taskId": "half-1"}, missing_pitch],
        PROTOCOL,
        expected_task_ids=["half-1", "half-2"],
        team_mapping={"my_team": "home", "enemy": "away"},
    )["acceptance"]["passed"] is False
    with pytest.raises(ValueError, match="exactly the frozen tasks"):
        evaluate_source_acceptance(
            "two-halves",
            [task_result("half-1", 2, [0.5])],
            PROTOCOL,
            expected_task_ids=["half-1", "half-2"],
            team_mapping={"my_team": "home", "enemy": "away"},
        )
    impossible = task_result("half-1", 2, [0.5])
    impossible["events"]["classes"]["pass"]["counts"]["truePositives"] = 2
    with pytest.raises(ValueError, match="invalid pass event counts"):
        evaluate_source_acceptance(
            "two-halves",
            [impossible, task_result("half-2", 3, [1.0])],
            PROTOCOL,
            expected_task_ids=["half-1", "half-2"],
            team_mapping={"my_team": "home", "enemy": "away"},
        )
    inconsistent_mapping = task_result("half-2", 3, [1.0])
    inconsistent_mapping["teamMapping"] = {"my_team": "away", "enemy": "home"}
    with pytest.raises(ValueError, match="team mapping"):
        evaluate_source_acceptance(
            "two-halves",
            [task_result("half-1", 2, [0.5]), inconsistent_mapping],
            PROTOCOL,
            expected_task_ids=["half-1", "half-2"],
            team_mapping={"my_team": "home", "enemy": "away"},
        )


def _source_declaration(tmp_path, source_id: str = "source"):
    path = tmp_path / "team-declaration.json"
    path.write_text(json.dumps({
        "schemaVersion": "football_analysis_pilot_source_declaration_v1",
        "sourceId": source_id,
        "myTeamSide": "home",
        "reviewerId": "independent-reviewer",
        "declaredAt": "2026-09-15T12:00:00Z",
        "footageBasis": "frozen source video only",
        "independentDeclaration": True,
        "pipelineOutputUsed": False,
    }), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_cli_aggregates_saved_task_results(tmp_path, capsys) -> None:
    declaration, declaration_sha256 = _source_declaration(tmp_path)
    task_result = {
        "taskId": "source-01",
        "sourceId": "source",
        "teamMapping": {"my_team": "home", "enemy": "away"},
        "teamDeclarationSha256": declaration_sha256,
        "players": {"precision": 1.0},
        "tracking": {"HOTA": 1.0},
        "possession": {"teamAgreement": 1.0},
        "ball": {"counts": {
            "evaluationFrames": 1, "ignoredFrames": 0, "visibleTruth": 1,
            "notVisibleTruth": 0, "predictions": 1, "truePositives": 1,
            "falsePositives": 0, "falseNegatives": 0,
        }, "predictionSourceBreakdown": {"observed": 1, "inferred": 0, "unknown": 0}},
        "pitch": {
            "eligibleForAcceptance": True,
            "errorsMeters": [0.5],
            "referencePositionCount": 1,
            "matchedPositionCount": 1,
        },
        "events": {"classes": {event_type: {"counts": {"truth": 0, "predictions": 0, "truePositives": 0, "falsePositives": 0, "falseNegatives": 0}} for event_type in ("pass", "shot")}},
    }
    result_path = tmp_path / "task.json"
    corpus_path = tmp_path / "corpus.json"
    task_manifest_path = tmp_path / "tasks.json"
    result_path.write_text(json.dumps(task_result), encoding="utf-8")
    corpus_path.write_text(json.dumps({"labelingProtocol": {"scoringProtocol": PROTOCOL}}), encoding="utf-8")
    task_manifest_path.write_text(json.dumps({"tasks": [{"taskId": "source-01", "sourceId": "source"}]}), encoding="utf-8")

    args = [
        "source",
        "--source-id", "source",
        "--task-result", str(result_path),
        "--task-manifest", str(task_manifest_path),
        "--corpus", str(corpus_path),
        "--source-declaration", str(declaration),
    ]
    main(args)

    result = json.loads(capsys.readouterr().out)
    assert result["acceptance"]["passed"] is True
    assert result["teamDeclarationSha256"] == declaration_sha256

    missing = json.loads(result_path.read_text(encoding="utf-8"))
    del missing["ball"]["counts"]["evaluationFrames"]
    result_path.write_text(json.dumps(missing), encoding="utf-8")
    with pytest.raises(ValueError, match="ball counts"):
        main(args)

    impossible = json.loads(json.dumps(task_result))
    impossible["ball"]["counts"]["evaluationFrames"] = 2
    result_path.write_text(json.dumps(impossible), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid ball counts"):
        main(args)

    missing_sources = json.loads(json.dumps(task_result))
    del missing_sources["ball"]["predictionSourceBreakdown"]
    result_path.write_text(json.dumps(missing_sources), encoding="utf-8")
    with pytest.raises(ValueError, match="ball prediction source"):
        main(args)

    impossible_sources = json.loads(json.dumps(task_result))
    impossible_sources["ball"]["predictionSourceBreakdown"]["observed"] = 0
    result_path.write_text(json.dumps(impossible_sources), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid ball prediction source counts"):
        main(args)

    duplicate_result = json.dumps(task_result).replace(
        '"teamDeclarationSha256": "' + declaration_sha256 + '"',
        '"teamDeclarationSha256": "' + declaration_sha256 + '", "teamDeclarationSha256": "' + declaration_sha256 + '"',
    )
    result_path.write_text(duplicate_result, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        main(args)

    missing_event = json.loads(json.dumps(task_result))
    del missing_event["events"]["classes"]["pass"]["counts"]["falsePositives"]
    result_path.write_text(json.dumps(missing_event), encoding="utf-8")
    with pytest.raises(ValueError, match="pass event counts"):
        main(args)

    impossible_event = json.loads(json.dumps(task_result))
    impossible_event["events"]["classes"]["pass"]["counts"]["falseNegatives"] = 1
    result_path.write_text(json.dumps(impossible_event), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid pass event counts"):
        main(args)


def test_source_cli_rejects_a_changed_team_declaration(tmp_path) -> None:
    declaration, original_sha256 = _source_declaration(tmp_path)
    result_path = tmp_path / "task.json"
    result_path.write_text(json.dumps({
        "taskId": "source-01", "sourceId": "source",
        "teamMapping": {"my_team": "home", "enemy": "away"},
        "teamDeclarationSha256": original_sha256,
    }), encoding="utf-8")
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({"labelingProtocol": {"scoringProtocol": PROTOCOL}}), encoding="utf-8")
    task_manifest_path = tmp_path / "tasks.json"
    task_manifest_path.write_text(json.dumps({"tasks": [{"taskId": "source-01", "sourceId": "source"}]}), encoding="utf-8")
    changed = json.loads(declaration.read_text(encoding="utf-8"))
    changed["footageBasis"] = "changed after task scoring"
    declaration.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(ValueError, match="declaration SHA-256"):
        main([
            "source", "--source-id", "source", "--task-result", str(result_path),
            "--task-manifest", str(task_manifest_path), "--corpus", str(corpus_path),
            "--source-declaration", str(declaration),
        ])


def test_source_declaration_rejects_a_malformed_side_with_value_error(tmp_path) -> None:
    declaration, _sha256 = _source_declaration(tmp_path)
    malformed = json.loads(declaration.read_text(encoding="utf-8"))
    malformed["myTeamSide"] = ["home"]
    declaration.write_text(json.dumps(malformed), encoding="utf-8")

    with pytest.raises(ValueError, match="source declaration"):
        pilot._source_declaration(declaration, "source")


def test_task_cli_derives_team_mapping_and_stamps_declaration_hash(tmp_path, monkeypatch, capsys) -> None:
    declaration, declaration_sha256 = _source_declaration(tmp_path)
    task_manifest = tmp_path / "tasks.json"
    label_path = tmp_path / "labels.json"
    corpus = tmp_path / "corpus.json"
    label_path.write_text("{}", encoding="utf-8")
    task_manifest.write_text(json.dumps({"tasks": [{
        "taskId": "source-01", "sourceId": "source", "labelOutputPath": str(label_path),
        "evaluationRole": "validation",
    }]}), encoding="utf-8")
    corpus.write_text(json.dumps({"labelingProtocol": {"scoringProtocol": PROTOCOL}}), encoding="utf-8")
    import backend.scripts.validate_football_analysis_pilot_labels as label_validator
    monkeypatch.setattr(label_validator, "validate_label_payload", lambda _task, _labels: None)
    def fake_evaluate(_task, _labels, _protocol, **kwargs):
        assert kwargs["team_mapping"] == {"my_team": "home", "enemy": "away"}
        return {"taskId": "source-01"}
    monkeypatch.setattr(pilot, "evaluate_task_artifacts", fake_evaluate)

    args = [
        "task", "--task-id", "source-01", "--task-manifest", str(task_manifest),
        "--corpus", str(corpus), "--source-declaration", str(declaration),
        "--artifact-dir", str(tmp_path), "--prediction-scope", "whole-source",
        "--trackeval-root", str(tmp_path),
    ]
    main(args)
    assert json.loads(capsys.readouterr().out)["teamDeclarationSha256"] == declaration_sha256

    label_path.write_text('{"pipelineOutputUsed": true, "pipelineOutputUsed": false}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        main(args)


def test_source_declaration_rejects_duplicate_attestation_keys(tmp_path) -> None:
    declaration, _sha256 = _source_declaration(tmp_path)
    raw = declaration.read_text(encoding="utf-8")
    declaration.write_text(raw.replace('"pipelineOutputUsed": false', '"pipelineOutputUsed": true, "pipelineOutputUsed": false'), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        pilot._source_declaration(declaration, "source")


def test_source_declaration_rejects_duplicate_source_keys(tmp_path) -> None:
    declaration, _sha256 = _source_declaration(tmp_path)
    raw = declaration.read_text(encoding="utf-8")
    declaration.write_text(raw.replace('"sourceId": "source"', '"sourceId": "other", "sourceId": "source"'), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        pilot._source_declaration(declaration, "source")


@pytest.mark.parametrize("declared_at", ["20260915T120000Z", "2026-09-15Z"])
def test_source_declaration_rejects_non_rfc3339_timestamps(tmp_path, declared_at) -> None:
    declaration, _sha256 = _source_declaration(tmp_path)
    value = json.loads(declaration.read_text(encoding="utf-8"))
    value["declaredAt"] = declared_at
    declaration.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="RFC3339"):
        pilot._source_declaration(declaration, "source")


def test_source_cli_rechecks_and_retains_the_held_out_input_hash(tmp_path, monkeypatch, capsys) -> None:
    _task, task_manifest, media_root, _clip, declared_sha = _frozen_clip_fixture(tmp_path, 7)
    declaration, declaration_sha256 = _source_declaration(tmp_path, "fixture-source")
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({"labelingProtocol": {"scoringProtocol": PROTOCOL}}), encoding="utf-8")
    result_path = tmp_path / "task-result.json"
    task_result = {
        "taskId": "fixture-01", "sourceId": "fixture-source",
        "teamMapping": {"my_team": "home", "enemy": "away"},
        "teamDeclarationSha256": declaration_sha256,
        "predictionScope": "task-interval", "predictionSourceStartFrame": 5,
        "players": {"precision": 1.0}, "tracking": {"HOTA": 1.0},
        "possession": {"teamAgreement": 1.0},
        "ball": {"counts": {
            "evaluationFrames": 1, "ignoredFrames": 0, "visibleTruth": 1,
            "notVisibleTruth": 0, "predictions": 1, "truePositives": 1,
            "falsePositives": 0, "falseNegatives": 0,
        }, "predictionSourceBreakdown": {"observed": 1, "inferred": 0, "unknown": 0}},
        "pitch": {"eligibleForAcceptance": True, "errorsMeters": [0.5],
                  "referencePositionCount": 1, "matchedPositionCount": 1},
        "events": {"classes": {kind: {"counts": {"truth": 0, "predictions": 0, "truePositives": 0, "falsePositives": 0, "falseNegatives": 0}}
                               for kind in ("pass", "shot")}},
    }
    result_path.write_text(json.dumps(task_result), encoding="utf-8")
    monkeypatch.setattr(pilot, "_PILOT_MEDIA_ROOT", media_root)
    args = [
        "source", "--source-id", "fixture-source", "--task-result", str(result_path),
        "--task-manifest", str(task_manifest), "--corpus", str(corpus),
        "--source-declaration", str(declaration),
    ]
    with pytest.raises(ValueError, match="held-out input-video hash"):
        main(args)

    task_result["predictionInputVideoSha256"] = declared_sha
    result_path.write_text(json.dumps(task_result), encoding="utf-8")
    main(args)
    source_result = json.loads(capsys.readouterr().out)
    assert source_result["taskMetrics"][0]["predictionInputVideoSha256"] == declared_sha
    assert source_result["taskMetrics"][0]["predictionSourceStartFrame"] == 5

    task_result["predictionSourceStartFrame"] = 6
    result_path.write_text(json.dumps(task_result), encoding="utf-8")
    with pytest.raises(ValueError, match="aligned prediction scope"):
        main(args)


def test_corpus_acceptance_bars_are_loaded_into_the_scoring_protocol(tmp_path) -> None:
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(
        json.dumps(
            {
                "labelingProtocol": {
                    "acceptanceBars": {"supportedEventPrecisionMinimum": 0.8},
                    "scoringProtocol": {"acceptance": {"unit": "sourceId"}},
                }
            }
        ),
        encoding="utf-8",
    )

    protocol = pilot._scoring_protocol(corpus_path)

    assert protocol["acceptance"] == {"unit": "sourceId", "supportedEventPrecisionMinimum": 0.8}
