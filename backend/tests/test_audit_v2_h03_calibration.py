from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.app.analytics import summarize_match
from backend.app.export_flatteners import flatten_metrics_for_csv
from backend.app.llm import _build_match_signals
from backend.app.main import _dashboard_average
from backend.app.report_export import render_match_report_html
from backend.app.schemas import MatchConfig, ShotAnalytics
from backend.app.storage import Storage
from backend.app.workbench.geometry import CalibrationProfile, Landmark, evaluate_landmarks
from backend.app.workbench.perception import Detection, Label, merge_tiled_detections, score_detections


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
        result = evaluate_landmarks(CalibrationProfile(**base, homography=matrix), max_p95_m=3.0)
        assert result["accepted"] is False
        assert reason in result["reasonCodes"]

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
