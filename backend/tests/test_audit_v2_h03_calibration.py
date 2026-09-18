from __future__ import annotations

import math
import json
from pathlib import Path

import pytest

from pydantic import ValidationError

from backend.app.analytics import build_formation_timeline, summarize_match
from backend.app.export_flatteners import flatten_metrics_for_csv
from backend.app.llm import _build_match_signals
from backend.app.main import _dashboard_average
from backend.app.processor import process_match
from backend.app.report_export import render_match_report_html
from backend.app.schemas import (
    BallOwnership,
    DetectedEvent,
    FrameData,
    MatchConfig,
    MatchPeriod,
    PlayerData,
    ShotAnalytics,
)
from backend.app.storage import Storage
from backend.app.workbench.geometry import (
    CalibrationProfile,
    Landmark,
    evaluate_landmarks,
    from_legacy_four_points,
    validate_homography,
)
from backend.app.workbench.perception import Detection, Label, merge_tiled_detections, score_detections
from backend.app.workbench.contracts import CalibrationRevision


def _holdout(name: str, x: float, y: float, *, pitch_x: float | None = None) -> Landmark:
    return Landmark(
        name=name,
        imageX=x,
        imageY=y,
        pitchX=x if pitch_x is None else pitch_x,
        pitchY=y,
        independentHoldout=True,
    )


def test_t06_missing_and_invalid_transforms_fail_closed() -> None:
    """B05 / T06: unavailable or unusable transforms never accept geometry."""
    base = dict(
        calibrationId="cal-test",
        cameraModel="planar_homography",
        pitchLengthM=105.0,
        pitchWidthM=68.0,
        landmarks=[_holdout("only", 10, 10)],
    )
    missing = evaluate_landmarks(CalibrationProfile(**base), max_p95_m=3.0)
    assert missing["accepted"] is False
    assert missing["reasonCodes"] == ["NO_TRANSFORM"]

    matrices = [
        ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], "INVALID_TRANSFORM_SHAPE"),
        ([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], "SINGULAR_TRANSFORM"),
        ([[math.nan, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], "NONFINITE_TRANSFORM"),
    ]
    for matrix, reason in matrices:
        assert reason in validate_homography(matrix)

    valid = CalibrationProfile(
        **{key: value for key, value in base.items() if key != "landmarks"},
        homography=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        cameraSide="touchline_north",
        landmarks=[
            _holdout("nw", 10, 10),
            _holdout("ne", 90, 10),
            _holdout("sw", 10, 60),
            _holdout("se", 90, 60),
        ],
    )
    accepted = evaluate_landmarks(valid, max_p95_m=3.0)
    assert accepted["accepted"] is True
    assert accepted["p95M"] == 0.0


def test_t07_far_side_error_is_invariant_to_holdout_order() -> None:
    """B06 / T07: sorting residuals cannot detach them from their landmarks."""
    bad_far = _holdout("bad-far", 0, 60, pitch_x=100)
    near = [_holdout(f"near-{index}", 10 if index % 2 else 90, 10) for index in range(39)]

    def evaluate(marks: list[Landmark]) -> dict:
        camera_side = {"cameraSide": "touchline_north"} if "cameraSide" in CalibrationProfile.model_fields else {}
        return evaluate_landmarks(
            CalibrationProfile(
                calibrationId="cal-order",
                cameraModel="planar_homography",
                pitchLengthM=105.0,
                pitchWidthM=68.0,
                homography=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                landmarks=marks,
                **camera_side,
            ),
            max_p95_m=3.0,
        )

    first = evaluate([bad_far, *near])
    last = evaluate([*near, bad_far])
    assert first["farSideMaxM"] == pytest.approx(100.0)
    assert last["farSideMaxM"] == pytest.approx(100.0)
    assert first["farSideCount"] == last["farSideCount"] == 1
    assert first["accepted"] is last["accepted"] is False


def test_t06_missing_manual_points_do_not_invent_unit_square(tmp_path: Path) -> None:
    """B33 / T06: missing source points return unavailable without writing review state."""
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    storage = Storage(tmp_path / "storage")
    match = storage.create_match("No calibration", "tracking_json", source.name, source, MatchConfig())
    result = storage.calibration_for_match(
        match.id,
        {
            "landmarks": [
                {"name": "a", "imageX": 0, "imageY": 0, "pitchX": 0, "pitchY": 0, "independentHoldout": True},
                {"name": "b", "imageX": 1, "imageY": 0, "pitchX": 105, "pitchY": 0, "independentHoldout": True},
                {"name": "c", "imageX": 1, "imageY": 1, "pitchX": 105, "pitchY": 68, "independentHoldout": True},
                {"name": "d", "imageX": 0, "imageY": 1, "pitchX": 0, "pitchY": 68, "independentHoldout": True},
            ]
        },
    )

    assert result["committed"] is False
    assert result["availability"] == "calibration_unavailable"
    assert result["reasonCodes"] == ["MANUAL_POINTS_MISSING"]
    assert storage.list_corrections(match.id) == []

    for count in (3, 5):
        storage.update_match_config(
            match.id,
            MatchConfig(manualHomographyPoints=[{"x": float(index), "y": float(index)} for index in range(count)]),
        )
        assert storage.calibration_for_match(match.id)["reasonCodes"] == ["MANUAL_POINTS_MISSING"]

    storage.update_match_config(
        match.id,
        MatchConfig(
            manualHomographyPoints=[
                {"x": -1, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 68},
                {"x": 0, "y": 68},
            ]
        ),
    )
    assert storage.calibration_for_match(match.id)["reasonCodes"] == ["FIT_POINT_OUTSIDE_SOURCE"]


def test_t06_legacy_four_points_preserve_declared_pitch_size() -> None:
    profile = from_legacy_four_points(
        [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 64}, {"x": 0, "y": 64}],
        calibration_id="custom-pitch",
        pitch_length_m=100.0,
        pitch_width_m=64.0,
    )
    assert profile.pitchLengthM == 100.0
    assert profile.pitchWidthM == 64.0
    assert profile.homography is not None


def test_t21_scorer_respects_class_pixels_and_tile_scope() -> None:
    """B22 / T21: wrong classes never match and localisation is measured in pixels."""
    wrong_class = score_detections(
        [Detection(frameId=1, bbox=(0, 0, 10, 10), score=1, kind="ball", stratum="near")],
        [Label(frameId=1, bbox=(0, 0, 10, 10), kind="player", stratum="near")],
        task="player_coverage",
        configuration="test",
        labels_independent=True,
    )
    offset = score_detections(
        [Detection(frameId=1, bbox=(3, 4, 13, 14), score=1, kind="player", stratum="near")],
        [Label(frameId=1, bbox=(0, 0, 10, 10), kind="player", stratum="near")],
        task="player_coverage",
        configuration="test",
        iou_threshold=0.2,
        labels_independent=True,
    )
    merged = merge_tiled_detections(
        [
            {"frameId": 1, "kind": "player", "bbox": (0, 0, 10, 10), "score": 0.9},
            {"frameId": 2, "kind": "player", "bbox": (0, 0, 10, 10), "score": 0.8},
            {"frameId": 1, "kind": "ball", "bbox": (0, 0, 10, 10), "score": 0.7},
        ],
        iou_threshold=0.5,
    )

    assert wrong_class.precision is None
    assert wrong_class.falsePositives == 0
    assert wrong_class.falseNegatives == 1
    assert wrong_class.ignoredOtherClass == 1
    assert offset.centreOffsetPx == 5.0
    assert len(merged) == 3


def test_t04_shot_quality_records_and_report_are_team_scoped() -> None:
    """B23 / T04: one team's report value can never be the sum of both teams."""
    shots = [
        ShotAnalytics(frameId=1, timestamp=1, team="my_team", playerId=9, x=90, y=34, inBox=True, xg=0.4, distanceToGoal=10, angleDegrees=30),
        ShotAnalytics(frameId=2, timestamp=2, team="enemy", playerId=4, x=15, y=34, inBox=True, xg=0.6, distanceToGoal=10, angleDegrees=30),
    ]
    summary = summarize_match([], [], shots)
    records = {item.metric: item for item in summary.metricAvailability}
    assert records["my_team_experimental_shot_quality_sum"].value == 0.4
    assert records["my_team_experimental_shot_quality_sum"].teamScope == "my_team"
    assert records["enemy_experimental_shot_quality_sum"].value == 0.6
    assert records["enemy_experimental_shot_quality_sum"].teamScope == "enemy"
    assert records["experimental_shot_quality"].value is None
    assert records["experimental_shot_quality"].deprecated is True

    payload = summary.model_dump(mode="json")
    rows = {item["metric"]: item for item in flatten_metrics_for_csv(summary.metricAvailability)}
    assert rows["my_team_experimental_shot_quality_sum"]["teamScope"] == "my_team"
    assert rows["enemy_experimental_shot_quality_sum"]["value"] == 0.6
    assert _dashboard_average(
        [payload], field="myTeamXg", metric="my_team_experimental_shot_quality_sum", digits=2
    ) == 0.4
    signals = _build_match_signals(summary, [])
    assert signals["myTeamExperimentalShotQualitySum"] == 0.4
    assert signals["enemyExperimentalShotQualitySum"] == 0.6

    html = render_match_report_html(
        match_name="Team scope",
        input_mode="tracking_json",
        exported_at="2026-09-18T00:00:00Z",
        summary=summary.model_dump(mode="json"),
        formation_timeline=[],
        event_summary={"eventCounts": {}},
        tactical_report=None,
        drills=None,
    )
    assert "My Team experimental shot quality</div><div class=\"metric\">0.40" in html
    assert "Enemy experimental shot quality</div><div class=\"metric\">0.60" in html
    assert ">1.00<" not in html

    my_team_only = summarize_match([], [], shots[:1])
    scoped = {item.metric: item for item in my_team_only.metricAvailability}
    assert scoped["my_team_experimental_shot_quality_sum"].availability == "experimental"
    assert scoped["enemy_experimental_shot_quality_sum"].availability == "unknown"
    assert _build_match_signals(my_team_only, [])["enemyExperimentalShotQualitySum"] is None

    empty = summarize_match([], [], [])
    empty_html = render_match_report_html(
        match_name="No shots",
        input_mode="tracking_json",
        exported_at="2026-09-18T00:00:00Z",
        summary=empty.model_dump(mode="json"),
        formation_timeline=[],
        event_summary={"eventCounts": {}},
        tactical_report=None,
        drills=None,
    )
    assert empty_html.count('experimental shot quality</div><div class="metric">Unavailable') == 2


def test_t22_possession_is_time_weighted_and_physical_metrics_use_declared_pitch() -> None:
    """B24 / T22: duration and pitch dimensions, not frame counts or hidden constants, define metrics."""
    frames = [
        FrameData(frameId=0, timestamp=0.0, myTeam=[PlayerData(id=7, x=0, y=0)]),
        FrameData(frameId=1, timestamp=1.0, myTeam=[PlayerData(id=7, x=10, y=0)]),
        FrameData(frameId=2, timestamp=10.0, myTeam=[PlayerData(id=7, x=20, y=0)]),
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7),
        BallOwnership(frameId=1, timestamp=1.0, team="enemy", trackId=4),
        BallOwnership(frameId=2, timestamp=10.0, team="enemy", trackId=4),
    ]
    summary = summarize_match(
        frames,
        assignments,
        events=[
            DetectedEvent(
                type="through_ball",
                frameId=1,
                timestamp=1.0,
                team="my_team",
                description="review candidate",
            )
        ],
        identity_continuous=True,
        calibration_accepted=True,
        pitch_length_m=100.0,
        pitch_width_m=64.0,
    )
    records = {item.metric: item for item in summary.metricAvailability}
    assert summary.possession == 10
    assert summary.myTeamDistance == 20
    assert records["possession_pct"].eligibleSeconds == 10.0
    assert records["my_team_distance_m"].availability == "available"
    assert records["my_team_distance_m"].pitchDimensions == {"lengthM": 100.0, "widthM": 64.0}
    assert records["my_team_defensive_line_height"].availability == "unknown"
    assert records["my_team_defensive_line_height"].reasonCodes == ["INSUFFICIENT_TEAM_VISIBILITY"]
    assert records["my_team_line_breaking_events"].availability == "unknown"

    no_possession = summarize_match(
        frames,
        [],
        identity_continuous=True,
        calibration_accepted=True,
        pitch_length_m=100.0,
        pitch_width_m=64.0,
    )
    no_possession_records = {item.metric: item for item in no_possession.metricAvailability}
    assert no_possession_records["possession_pct"].availability == "unknown"
    assert no_possession_records["my_team_distance_m"].availability == "available"
    assert no_possession_records["my_team_distance_m"].eligibleSeconds == 10.0

    visible_frames = [
        frame.model_copy(
            update={
                "enemies": [
                    PlayerData(id=index, x=50 + index, y=index * 5)
                    for index in range(1, 5)
                ]
            }
        )
        for frame in frames
    ]
    visible = summarize_match(
        visible_frames,
        assignments,
        events=[
            DetectedEvent(
                type="through_ball",
                frameId=1,
                timestamp=1.0,
                team="my_team",
                description="review candidate",
            )
        ],
    )
    visible_records = {item.metric: item for item in visible.metricAvailability}
    assert visible_records["my_team_line_breaking_events"].availability == "experimental"
    assert visible_records["my_team_line_breaking_events"].value == 1


def test_t22_formation_breaks_across_unknown_gap() -> None:
    players = [PlayerData(id=index, x=float(index * 8), y=float((index % 4) * 15)) for index in range(1, 11)]
    frames = [
        FrameData(frameId=0, timestamp=0.0, myTeam=players),
        FrameData(frameId=1, timestamp=1.0, myTeam=players),
        FrameData(frameId=2, timestamp=8.0),
        FrameData(frameId=3, timestamp=9.0, myTeam=players),
    ]
    timeline = build_formation_timeline(frames, window_size=1)
    assert len(timeline) == 2
    assert timeline[0].endFrameId == 1
    assert timeline[1].startFrameId == 3

    short_gap = [
        frames[0],
        frames[1],
        FrameData(frameId=2, timestamp=1.5),
        FrameData(frameId=3, timestamp=2.0, myTeam=players),
    ]
    assert len(build_formation_timeline(short_gap, window_size=1)) == 1


def test_t22_domain_boundaries_reject_nonfinite_and_reversed_values() -> None:
    """B28 / T22: canonical domain objects reject values legacy adapters must normalise explicitly."""
    with pytest.raises(ValidationError):
        MatchConfig(pitchLengthM=float("nan"))
    with pytest.raises(ValidationError):
        MatchPeriod(name="second", startSeconds=90.0, endSeconds=45.0)
    with pytest.raises(ValidationError):
        MatchConfig(
            periods=[
                MatchPeriod(name="first", startSeconds=0.0, endSeconds=50.0),
                MatchPeriod(name="second", startSeconds=45.0, endSeconds=90.0),
            ]
        )
    with pytest.raises(ValidationError):
        CalibrationRevision(
            revisionId="cal_bad",
            profile={"homography": [[1, 0, 0], [0, 1, 0]]},
            evaluation={},
            accepted=False,
            measured=False,
            sourceSha256="0" * 64,
            validInterval={"start": 0.0, "end": None},
            createdAt="2026-09-18T00:00:00Z",
            pitchLengthM=105.0,
            pitchWidthM=68.0,
        )
    with pytest.raises(ValidationError):
        CalibrationRevision(
            revisionId="cal_bad_interval",
            profile={},
            evaluation={},
            accepted=False,
            measured=False,
            sourceSha256="0" * 64,
            validInterval={"start": 5.0, "end": 4.0},
            createdAt="2026-09-18T00:00:00Z",
            pitchLengthM=float("inf"),
            pitchWidthM=68.0,
        )
    with pytest.raises(ValidationError):
        Landmark(name="bad", imageX=float("inf"), imageY=0, pitchX=0, pitchY=0)
    with pytest.raises(ValidationError):
        CalibrationProfile(
            calibrationId="bad",
            cameraModel="planar_homography",
            homography=[[1, 0, 0], [0, 1, 0]],
        )
    for homography in (
        [[1, 0, 0], [0, 0, 1], [0, 1, 0]],
        [[1e-10, 0, 0], [0, 1, 0], [0, 0, 1]],
    ):
        with pytest.raises(ValidationError):
            CalibrationRevision(
                revisionId="cal_bad_condition",
                profile={"homography": homography},
                evaluation={},
                accepted=False,
                measured=False,
                sourceSha256="0" * 64,
                validInterval={"start": 0.0, "end": None},
                createdAt="2026-09-18T00:00:00Z",
                pitchLengthM=105.0,
                pitchWidthM=68.0,
            )

    legacy = from_legacy_four_points(
        [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 64}, {"x": 0, "y": 64}],
        calibration_id="legacy",
    )
    assert legacy.compatibleWithFourPointV1 is True
    assert legacy.homography is not None


def test_t08_calibration_revision_is_the_single_physical_metric_gate(tmp_path: Path) -> None:
    """B07 / T08: identity alone cannot publish physical metrics; one accepted revision unlocks them."""
    fixture = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    source = tmp_path / "tracking.json"
    source.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    storage = Storage(tmp_path / "storage")
    match = storage.create_match("Calibration revision", "tracking_json", source.name, source, MatchConfig())
    process_match(storage, storage.create_job(match.id).id)
    storage.submit_correction(match.id, kind="identity_validate", payload={"reviewed": True})
    before = {item.metric: item for item in storage.load_analytics(match.id)[0].metricAvailability}
    assert before["my_team_distance_m"].availability == "withheld"
    assert "CALIBRATION_UNAVAILABLE" in before["my_team_distance_m"].reasonCodes

    points = [
        {"x": 0.0, "y": 0.0},
        {"x": 100.0, "y": 0.0},
        {"x": 100.0, "y": 64.0},
        {"x": 0.0, "y": 64.0},
    ]
    storage.update_match_config(
        match.id,
        MatchConfig.model_validate(
            {
                **storage.get_match(match.id).config.model_dump(mode="json"),
                "manualHomographyPoints": points,
                "pitchLengthM": 100.0,
                "pitchWidthM": 64.0,
            }
        ),
    )
    result = storage.calibration_for_match(
        match.id,
        {
            "landmarks": [
                {
                    "name": f"holdout-{index}",
                    "imageX": x,
                    "imageY": y,
                    "pitchX": x,
                    "pitchY": y,
                    "independentHoldout": True,
                }
                for index, (x, y) in enumerate(((10, 10), (90, 10), (10, 60), (90, 60)))
            ]
        },
    )
    revision = storage.calibration_revision(match.id)
    assert result["committed"] is True
    assert revision is not None and revision.accepted and revision.measured
    assert (revision.pitchLengthM, revision.pitchWidthM) == (100.0, 64.0)
    assert storage._stored_calibration_accepted(match.id) is True
    after = {item.metric: item for item in storage.load_analytics(match.id)[0].metricAvailability}
    assert after["my_team_distance_m"].availability == "available"
    pointer = storage.current_generation(match.id)
    assert pointer.calibrationRevision == revision.revisionId
    manifest = json.loads(
        (
            storage._match_dir(match.id)
            / "generations"
            / pointer.generationId
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert set(manifest["stale"]) == {
        "pitch_positions",
        "physical_metrics",
        "tactical_metrics",
        "report",
    }

    rejected = storage.calibration_for_match(
        match.id,
        {
            "landmarks": [
                {
                    "name": "insufficient",
                    "imageX": 20,
                    "imageY": 20,
                    "pitchX": 20,
                    "pitchY": 20,
                    "independentHoldout": True,
                }
            ]
        },
    )
    assert rejected["evaluation"]["accepted"] is False
    assert rejected["committed"] is False
    assert storage.calibration_revision(match.id).revisionId == revision.revisionId


def test_t08_legacy_calibration_artifacts_migrate_to_one_revision(tmp_path: Path) -> None:
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    storage = Storage(tmp_path / "storage")
    match = storage.create_match("Legacy calibration", "tracking_json", source.name, source, MatchConfig())
    storage.save_analysis_artifact(match.id, "calibration_profile", {"calibrationId": "legacy"})
    storage.save_analysis_artifact(
        match.id,
        "calibration_evaluation",
        {"accepted": True, "measured": True, "p95M": 0.5},
    )

    revision = storage.calibration_revision(match.id)

    assert revision is not None
    assert revision.migrated is True
    assert revision.accepted is True
    assert revision.measured is True


def test_t08_direct_calibration_commit_rebuilds_existing_generation(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    source = tmp_path / "tracking.json"
    source.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    storage = Storage(tmp_path / "storage")
    match = storage.create_match("Direct calibration", "tracking_json", source.name, source, MatchConfig())
    process_match(storage, storage.create_job(match.id).id)
    before = storage.current_generation(match.id)
    profile = {
        "calibrationId": "direct",
        "cameraModel": "planar_homography",
        "pitchLengthM": 100.0,
        "pitchWidthM": 64.0,
        "homography": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "landmarks": [
            {
                "name": f"holdout-{index}",
                "imageX": x,
                "imageY": y,
                "pitchX": x,
                "pitchY": y,
                "independentHoldout": True,
            }
            for index, (x, y) in enumerate(((10, 10), (90, 10), (10, 60), (90, 60)))
        ],
    }

    result = storage.commit_calibration_for_match(match.id, profile)
    after = storage.current_generation(match.id)

    assert result["committed"] is True
    assert result["correction"]["kind"] == "calibration"
    assert after.generationId != before.generationId
    assert after.calibrationRevision == storage.calibration_revision(match.id).revisionId
    records = {item.metric: item for item in storage.load_analytics(match.id)[0].metricAvailability}
    assert records["my_team_distance_m"].pitchDimensions == {"lengthM": 100.0, "widthM": 64.0}
    manifest = json.loads(
        (storage._match_dir(match.id) / "generations" / after.generationId / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(manifest["stale"]) == {"pitch_positions", "physical_metrics", "tactical_metrics", "report"}

    first_frames = storage.load_frames(match.id)
    second_profile = {
        **profile,
        "calibrationId": "direct-2",
        "homography": [[1.0, 0.0, 5.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "landmarks": [
            {**landmark, "pitchX": landmark["pitchX"] + 5.0}
            for landmark in profile["landmarks"]
        ],
    }
    second = storage.commit_calibration_for_match(match.id, second_profile)
    second_frames = storage.load_frames(match.id)
    assert second_frames[0].myTeam[0].x != first_frames[0].myTeam[0].x
    latest_revision = storage.calibration_revision(match.id)
    storage.undo_correction(match.id, second["correction"]["correctionId"])
    restored = storage.calibration_revision(match.id)
    assert restored is not None and restored.revisionId != latest_revision.revisionId
    storage.undo_correction(match.id, result["correction"]["correctionId"])
    assert storage.calibration_revision(match.id) is None
    assert storage.assess_stored_match_setup(match.id)["calibrationCommitted"] is False


def test_t08_preprocessing_calibration_is_applied_to_first_generation(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    source = tmp_path / "tracking.json"
    source.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    storage = Storage(tmp_path / "storage")
    match = storage.create_match("Precalibrated", "tracking_json", source.name, source, MatchConfig())
    profile = {
        "calibrationId": "before-processing",
        "cameraModel": "planar_homography",
        "pitchLengthM": 100.0,
        "pitchWidthM": 100.0,
        "homography": [[1.0, 0.0, 5.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "landmarks": [
            {
                "name": f"holdout-{index}",
                "imageX": x,
                "imageY": y,
                "pitchX": x + 5.0,
                "pitchY": y,
                "independentHoldout": True,
            }
            for index, (x, y) in enumerate(((10, 10), (90, 10), (10, 90), (90, 90)))
        ],
    }
    committed = storage.commit_calibration_for_match(match.id, profile)
    assert committed["committed"] is True
    process_match(storage, storage.create_job(match.id).id)

    revision = storage.calibration_revision(match.id)
    pointer = storage.current_generation(match.id)
    frames = storage.load_frames(match.id)
    assert revision is not None
    assert pointer.calibrationRevision == revision.revisionId
    assert frames[0].myTeam[0].x == pytest.approx(26.0)

    storage.submit_correction(match.id, kind="identity_validate", payload={"reviewed": True})
    assert storage.load_frames(match.id)[0].myTeam[0].x == pytest.approx(26.0)
