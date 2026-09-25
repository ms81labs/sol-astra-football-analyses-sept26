"""Missing event-frame safety and runtime contracts for analytics typing."""
from copy import deepcopy

import pytest

from backend.app.analytics import (
    _goal_geometry,
    _lookup_player_position,
    _pitch_zone,
    build_formation_timeline,
    summarize_match,
)
from backend.app.schemas import DetectedEvent, FrameData


def _frame():
    return FrameData(
        frameId=1, timestamp=0.0,
        myTeam=[{"id": 1, "x": 80.0, "y": 50.0}],
        enemies=[{"id": 11, "x": 20.0, "y": 50.0}],
        unassignedPlayers=[{"id": 21, "x": 50.0, "y": 50.0}],
    )


@pytest.mark.parametrize("team,target", [("my_team", 1), ("enemy", 11), ("unassigned", 21)])
@pytest.mark.parametrize("kind", ["recovery", "tackle", "turnover"])
@pytest.mark.parametrize("available_frame", [False, True])
def test_summary_keeps_missing_event_positions_unknown(team, target, kind, available_frame):
    frames = [_frame()] if available_frame else []
    event = DetectedEvent(type=kind, team=team, frameId=999, timestamp=1.0,
                          fromTrackId=target, toTrackId=target, description="Frame absent")
    snapshot = deepcopy((frames, event))
    summary = summarize_match(frames, [], events=[event])
    assert summary.myTeamRegainZones is None
    assert summary.enemyRegainZones is None
    assert summary.myTeamHighPressRegains is None
    assert summary.enemyHighPressRegains is None
    assert summary.myTeamPpda is None
    assert summary.enemyPpda is None
    assert (frames, event) == snapshot


@pytest.mark.parametrize("team", ["my_team", "enemy", "unassigned", "contested", None])
@pytest.mark.parametrize("track_id", [None, 1])
def test_missing_frame_lookup_does_not_invent_a_position(team, track_id):
    assert _lookup_player_position(None, team, track_id) is None


@pytest.mark.parametrize("team,track_id,expected", [
    ("my_team", 1, (80.0, 50.0)), ("enemy", 11, (20.0, 50.0)),
    ("unassigned", 21, (50.0, 50.0)), ("my_team", 11, None),
    ("enemy", None, None), (None, 1, None), ("contested", 1, None),
])
def test_existing_frame_lookup_keeps_team_and_track_semantics(team, track_id, expected):
    assert _lookup_player_position(_frame(), team, track_id) == expected


def test_missing_event_does_not_discard_a_located_regain():
    events = [
        DetectedEvent(type="recovery", team="my_team", frameId=999, timestamp=0.5,
                      toTrackId=1, description="Missing frame"),
        DetectedEvent(type="recovery", team="my_team", frameId=1, timestamp=1.0,
                      toTrackId=1, description="Located frame"),
    ]
    summary = summarize_match([_frame()], [], events=events)
    assert summary.myTeamRegainZones == {"defensive_third": 0, "middle_third": 0, "attacking_third": 1}
    assert summary.myTeamHighPressRegains == 1
    assert summary.myTeamPpda == 0.0


@pytest.mark.parametrize("team,x,type_", [("my_team", 105, int), ("enemy", 0.0, float)])
def test_goal_geometry_annotations_do_not_coerce_values(team, x, type_):
    center, top, bottom = _goal_geometry(team)
    assert center == (x, 34.0)
    assert top == (x, 34.0 - 3.66)
    assert bottom == (x, 34.0 + 3.66)
    assert type(center[0]) is type_


@pytest.mark.parametrize("container", [list, tuple, iter])
def test_formation_timeline_accepts_read_only_iterables(container):
    positions = [(10, 50), (25, 15), (25, 35), (25, 65), (25, 85),
                 (50, 20), (50, 50), (50, 80), (80, 20), (80, 50), (80, 80)]
    frames = [FrameData(frameId=n, timestamp=float(n), myTeam=[
        {"id": i, "x": x, "y": y} for i, (x, y) in enumerate(positions)
    ]) for n in range(3)]
    before = deepcopy(frames)
    expected = build_formation_timeline(frames)
    assert expected
    assert build_formation_timeline(container(frames)) == expected
    assert frames == before


@pytest.mark.parametrize("x,expected", [(10, "attacking_third"), (50, "middle_third"), (80, "defensive_third")])
def test_unknown_team_pitch_zone_retains_existing_fallback(x, expected):
    assert _pitch_zone(x, None) == expected
