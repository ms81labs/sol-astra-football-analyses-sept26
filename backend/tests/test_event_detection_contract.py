"""Event-family boundary and ordering contracts, captured before decomposition."""
from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.app.analytics import detect_events
from backend.app.schemas import BallOwnership, FrameData


def _frame(frame_id, *, mine=(), enemies=(), unknown=(), ball=(50.0, 50.0)):
    def players(rows):
        return [{"id": ident, "x": x, "y": y} for ident, x, y in rows]

    return {
        "frameId": frame_id, "timestamp": float(frame_id),
        "myTeam": players(mine), "enemies": players(enemies),
        "unassignedPlayers": players(unknown),
        "ball": None if ball is None else {"x": ball[0], "y": ball[1], "confidence": 1.0},
    }


def _owners(rows):
    return [BallOwnership(frameId=frame, timestamp=stamp, team=team, trackId=track, distance=None)
            for frame, stamp, team, track in rows]


def _events(frames, assignments, **kwargs):
    before = deepcopy((frames, assignments))
    result = detect_events(frames, assignments, **kwargs)
    assert (frames, assignments) == before
    return [event.model_dump() for event in result]


@pytest.mark.parametrize("attack_direction", ["left_to_right", "right_to_left"])
def test_empty_assignments_still_validate_frames_first(attack_direction):
    with pytest.raises(ValidationError):
        detect_events([{"frameId": 0}], [], attack_direction=attack_direction)


def test_empty_assignments_do_not_bypass_direction_validation():
    with pytest.raises(ValueError, match="Unsupported attack direction"):
        detect_events([], [], attack_direction="sideways")


def test_invalid_frame_precedes_invalid_direction_error():
    with pytest.raises(ValidationError):
        detect_events([{"frameId": 0}], [], attack_direction="sideways")


@pytest.mark.parametrize("frame_count", [0, 1])
def test_transition_index_mismatch_is_not_silently_truncated(frame_count):
    frames = [_frame(i) for i in range(frame_count)]
    assignments = _owners([(50, 1.0, "my_team", 1), (51, 2.0, "enemy", 2)])
    with pytest.raises(IndexError):
        detect_events(frames, assignments)


@pytest.mark.parametrize("team", ["my_team", "enemy"])
def test_stable_equal_time_order_and_provisional_event_defaults(team):
    # Transition suggestions are appended before carries, even with identical keys.
    def orient(rows):
        return rows if team == "my_team" else [(i, 100.0 - x, y) for i, x, y in rows]

    frames = []
    for i, position in enumerate([50.0, 56.0, 80.0]):
        owner = orient([(1 if i < 2 else 2, position, 50.0)])
        defenders = orient([(10 + j, x, 50.0) for j, x in enumerate([60.0, 65.0, 70.0, 90.0])])
        frames.append(_frame(i, mine=owner if team == "my_team" else defenders,
                             enemies=defenders if team == "my_team" else owner))
    assignments = _owners([(17, 4.0, team, 1), (17, 4.0, team, 1), (17, 4.0, team, 2)])
    result = _events(frames, assignments)
    assert [e["type"] for e in result] == ["pass", "through_ball", "carry"]
    assert [(e["frameId"], e["timestamp"]) for e in result] == [(17, 4.0)] * 3
    assert [e["description"] for e in result] == ["Pass from #1 to #2", "Through ball from #1 to #2", "Carry by #1"]
    for event in result:
        assert event["reviewStatus"] == "unreviewed"
        assert event["heuristicName"] == "provisional_event_suggestion"
        assert event["eventId"] is None and event["evidenceVersion"] is None
        assert event["intervalStart"] is None and event["intervalEnd"] is None


@pytest.mark.parametrize("gap, expected", [(1.0, ["pass"]), (1.0001, ["recovery"]), (-1.0, ["pass"])])
def test_short_loose_bridge_is_plain_pass_without_derived_cross(gap, expected):
    frames = [_frame(0, mine=[(1, 70.0, 10.0)]), _frame(1), _frame(2, mine=[(2, 90.0, 50.0)])]
    result = _events(frames, _owners([(0, 0.0, "my_team", 1), (1, 0.5, "dead_ball", None), (2, gap, "my_team", 2)]))
    assert [e["type"] for e in result] == expected


@pytest.mark.parametrize("distance, derived", [(6.0, "tackle"), (6.0001, "interception"), (18.0, "interception"), (18.0001, None)])
def test_turnover_pressure_boundaries_and_append_order(distance, derived):
    frames = [_frame(0, mine=[(1, 30.0, 50.0)]), _frame(1, enemies=[(2, 30.0 + distance, 50.0)])]
    result = _events(frames, _owners([(0, 0.0, "my_team", 1), (1, 1.0, "enemy", 2)]))
    assert [e["type"] for e in result] == ["turnover"] + ([] if derived is None else [derived])
    assert all((e["fromTrackId"], e["toTrackId"]) == (1, 2) for e in result)


def test_turnover_uses_current_frame_previous_owner_only_when_missing():
    frames = [_frame(0), _frame(1, mine=[(1, 30.0, 50.0)], enemies=[(2, 35.0, 50.0)])]
    result = _events(frames, _owners([(0, 0.0, "my_team", 1), (1, 1.0, "enemy", 2)]))
    assert [e["type"] for e in result] == ["turnover", "tackle"]


@pytest.mark.parametrize("before, after", [("unassigned", "my_team"), ("enemy", "unassigned"), ("my_team", "unassigned"), ("unassigned", "enemy")])
def test_same_track_resolution_does_not_invent_turnover(before, after):
    frames = [_frame(0, mine=[(7, 50.0, 50.0)], enemies=[(7, 50.0, 50.0)], unknown=[(7, 50.0, 50.0)]),
              _frame(1, mine=[(7, 50.0, 50.0)], enemies=[(7, 50.0, 50.0)], unknown=[(7, 50.0, 50.0)])]
    assert _events(frames, _owners([(0, 0.0, before, 7), (1, 1.0, after, 7)])) == []


def test_distinct_unknown_players_do_not_invent_pass():
    frames = [_frame(0, unknown=[(1, 50.0, 50.0)]), _frame(1, unknown=[(2, 70.0, 50.0)])]
    assert _events(frames, _owners([(0, 0.0, "unassigned", 1), (1, 1.0, "unassigned", 2)])) == []


@pytest.mark.parametrize("gap, movement, expected", [(6.0, 1.5, 1), (6.0001, 1.5, 2), (6.0, 1.5001, 2), (-1.0, 1.5, 1)])
def test_recovery_suppression_inclusive_time_and_distance(gap, movement, expected):
    frames = [_frame(0), _frame(1, unknown=[(7, 50.0, 50.0)]), _frame(2),
              _frame(3, unknown=[(7, 50.0, 50.0)], ball=(50.0 + movement, 50.0))]
    assignments = _owners([(0, 0.0, "dead_ball", None), (1, 1.0, "unassigned", 7),
                          (2, 1.5, "dead_ball", None), (3, 1.0 + gap, "unassigned", 7)])
    result = _events(frames, assignments)
    assert [e["type"] for e in result] == ["recovery"] * expected


@pytest.mark.parametrize("gap, progress, expected_carry", [(1.0, 6.0, True), (1.0001, 6.0, False), (1.0, 5.9999, False), (1.0, -6.0, False)])
def test_neutral_carry_gap_and_progress_boundaries(gap, progress, expected_carry):
    frames = [_frame(0, unknown=[(7, 40.0, 50.0)]), _frame(1), _frame(2, unknown=[(7, 40.0 + progress, 50.0)])]
    result = _events(frames, _owners([(0, 0.0, "unassigned", 7), (1, 0.5, "dead_ball", None), (2, gap, "unassigned", 7)]))
    assert [e["type"] for e in result] == ["recovery"] + (["carry"] if expected_carry else [])


def test_duplicate_frame_ids_use_last_ball_for_recovery_lookup():
    frames = [_frame(0), _frame(7, unknown=[(9, 50.0, 50.0)], ball=(10.0, 50.0)),
              _frame(2), _frame(3, unknown=[(9, 50.0, 50.0)], ball=(50.0, 50.0)), _frame(7, ball=(50.0, 50.0))]
    assignments = _owners([(0, 0.0, "dead_ball", None), (7, 1.0, "unassigned", 9),
                          (2, 2.0, "dead_ball", None), (3, 3.0, "unassigned", 9)])
    result = _events(frames, assignments)
    assert [(e["type"], e["frameId"]) for e in result] == [("recovery", 7)]


def test_mirrored_mixed_inputs_keep_exact_directional_suggestions():
    frames = [_frame(0, mine=[(1, 70.0, 10.0)]), _frame(1, mine=[(2, 90.0, 50.0)]), _frame(2)]
    assignments = _owners([(0, 0.0, "my_team", 1), (1, 1.0, "my_team", 2), (2, 2.0, "dead_ball", None)])
    expected = _events(frames, assignments)
    assert [e["type"] for e in expected] == ["pass", "cross", "shot"]
    mirrored = deepcopy(frames)
    for frame in mirrored:
        for field in ("myTeam", "enemies", "unassignedPlayers"):
            for player in frame[field]:
                player["x"] = 100.0 - player["x"]
        frame["ball"]["x"] = 100.0 - frame["ball"]["x"]
    mirrored[1] = FrameData.model_validate(mirrored[1])
    assert _events(mirrored, assignments, attack_direction="right_to_left") == expected
