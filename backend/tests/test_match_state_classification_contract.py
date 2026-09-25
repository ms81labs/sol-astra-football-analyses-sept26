"""Initial-state classification and continuity contracts captured before extraction."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.app.analytics import build_accepted_match_state
from backend.app.schemas import BallOwnership, FrameData


def _frame(frame_id=17, ball=None, timestamp=3.25):
    return {"frameId": frame_id, "timestamp": timestamp, "ball": ball}


def _owner(team, track=7, frame_id=17):
    # Deliberately use a different assignment time: state timestamps belong to frames.
    return BallOwnership(frameId=frame_id, timestamp=99.0, team=team, trackId=track)


def _layer(frame_id=17, x=22.0, y=33.0, confidence=0.8):
    return {"rows": [{"Frame_ID": frame_id, "X": x, "Y": y, "Conf": confidence}]}


def _states(frames, assignments, **kwargs):
    before = deepcopy((frames, assignments, kwargs))
    result = build_accepted_match_state(frames, assignments, **kwargs)
    assert (frames, assignments, kwargs) == before
    return [state.model_dump() for state in result]


@pytest.mark.parametrize("team", ["my_team", "enemy", "unassigned", "contested", "dead_ball"])
@pytest.mark.parametrize("track", [None, 0, 7])
@pytest.mark.parametrize("accepted_source", ["observed", "inferred", "none"])
@pytest.mark.parametrize("has_point", [False, True])
def test_initial_state_classification_preserves_precedence_and_metadata(team, track, accepted_source, has_point):
    layers = {"acceptedBall": _layer()} if has_point else {}
    reasons = [" source ", "", 7, "source", "source"]
    evidence = {"frames": [{"frameId": 17, "acceptedSource": accepted_source, "reasonCodes": reasons}]}
    state, = _states([_frame()], [_owner(team, track)], ball_truth_layers=layers, match_state_evidence=evidence)
    expected = {"frameId": 17, "timestamp": 3.25, "mode": "unknown", "controllingTeam": "none",
                "controllingTrackId": None, "ballVisibility": "hidden", "ballEstimate": None,
                "source": "unknown", "confidence": 0.40, "reasonCodes": [" source ", "source", "source"]}
    estimate = {"x": 22.0, "y": 33.0, "confidence": 0.8, "radius": 0.0} if has_point else None
    visibility = "visible" if accepted_source == "observed" else "inferred"
    source = "observed_ball" if accepted_source == "observed" else "inferred_ball"
    if team in {"my_team", "enemy"} and track is not None:
        expected.update(mode="controlled_possession", controllingTeam=team, controllingTrackId=track,
                        ballVisibility=visibility, ballEstimate=estimate, source=source,
                        confidence=0.90 if accepted_source == "observed" else 0.75)
    elif team == "dead_ball":
        expected.update(mode="restart_or_out", source="restart_rule", confidence=0.70)
    elif accepted_source in {"observed", "inferred"} and has_point:
        expected.update(mode="loose_ball", controllingTeam="contested" if team == "contested" else "unassigned",
                        ballVisibility=visibility, ballEstimate=estimate, source=source, confidence=0.60)
    assert state == expected


@pytest.mark.parametrize("explicit", [None, "invalid", "observed", "inferred"])
@pytest.mark.parametrize("observed,inferred,frame_ball", [(True, True, True), (False, True, True), (False, False, True), (False, False, False)])
def test_source_precedence_is_independent_of_accepted_point_origin(explicit, observed, inferred, frame_ball):
    layers = {"acceptedBall": _layer()}
    if observed:
        layers["observedBall"] = _layer(x=80)
    if inferred:
        layers["inferredBall"] = _layer(x=90)
    ball = {"x": 10.0, "y": 11.0, "confidence": 0.4} if frame_ball else None
    evidence = {"frames": [{"frameId": 17, "acceptedSource": explicit}]}
    state, = _states([_frame(ball=ball)], [_owner("unassigned")], ball_truth_layers=layers, match_state_evidence=evidence)
    expected_source = explicit if explicit in {"observed", "inferred"} else (
        "observed" if observed else "inferred" if inferred else "observed" if frame_ball else "none")
    if expected_source == "none":
        assert state["mode"] == "unknown" and state["ballEstimate"] is None
    else:
        assert state["mode"] == "loose_ball"
        assert state["source"] == expected_source + "_ball"
        assert state["ballEstimate"]["x"] == 22.0


@pytest.mark.parametrize("accepted", [False, True])
def test_accepted_point_wins_over_frame_ball_and_fallback_keeps_frame_confidence(accepted):
    layers = {"acceptedBall": _layer()} if accepted else {}
    ball = {"x": 10.0, "y": 11.0, "confidence": 0.4}
    state, = _states([_frame(ball=ball)], [_owner("contested")], ball_truth_layers=layers)
    assert state["ballEstimate"] == ({"x": 22.0, "y": 33.0, "confidence": 0.8, "radius": 0.0} if accepted else
                                    {"x": 10.0, "y": 11.0, "confidence": 0.4, "radius": 0.0})
    assert state["source"] == "observed_ball"


@pytest.mark.parametrize("middle_team", ["dead_ball", "contested", "unassigned", "enemy", "my_team"])
def test_continuity_runs_after_classification_and_preserves_reason_list_ownership(middle_team):
    frames = [_frame(i, timestamp=float(i)) for i in range(3)]
    assignments = [_owner("my_team", 7, 0), _owner(middle_team, 99, 1), _owner("my_team", 7, 2)]
    reasons = [" original ", "player_conditioned", "player_conditioned"]
    evidence = {"frames": [{"frameId": 1, "reasonCodes": reasons}]}
    state = _states(frames, assignments, match_state_evidence=evidence)[1]
    assert state == {"frameId": 1, "timestamp": 1.0, "mode": "controlled_possession", "controllingTeam": "my_team",
                     "controllingTrackId": 7, "ballVisibility": "hidden", "ballEstimate": None,
                     "source": "player_conditioned", "confidence": 0.65, "reasonCodes": reasons}
    state["reasonCodes"].append("caller")
    assert reasons == [" original ", "player_conditioned", "player_conditioned"]


@pytest.mark.parametrize("left,right", [(1, 1), (2, 2), (3, 1), (1, 3)])
def test_continuity_neighbor_limit_is_frame_based_and_inclusive(left, right):
    n = left + right + 1
    frames = [_frame(i, timestamp=10000.0 * i) for i in range(n)]
    assignments = [_owner("my_team" if i in {0, n - 1} else "dead_ball", 7 if i in {0, n - 1} else None, i)
                   for i in range(n)]
    state = _states(frames, assignments)[left]
    assert (state["source"] == "player_conditioned") == (left <= 2 and right <= 2)


@pytest.mark.parametrize("middle_ball", ["frame", "accepted"])
def test_any_available_point_blocks_hidden_continuity_override(middle_ball):
    frames = [_frame(i, timestamp=float(i)) for i in range(3)]
    layers = {}
    if middle_ball == "frame":
        frames[1]["ball"] = {"x": 0.0, "y": 0.0}
    else:
        layers["acceptedBall"] = _layer(1, x=0, y=0)
    assignments = [_owner("my_team", 7, 0), _owner("dead_ball", None, 1), _owner("my_team", 7, 2)]
    state = _states(frames, assignments, ball_truth_layers=layers)[1]
    assert state["mode"] == "restart_or_out" and state["source"] == "restart_rule"


def test_pairing_is_positional_and_duplicate_evidence_uses_last_row():
    frames = [_frame(17, timestamp=1.0), FrameData.model_validate(_frame(17, timestamp=2.0))]
    assignments = [_owner("my_team", 7, 999).model_dump(), _owner("enemy", 8, 998)]
    evidence = {"frames": [{"frameId": 17, "acceptedSource": "observed", "reasonCodes": ["old"]},
                           {"frameId": 17, "acceptedSource": "inferred", "reasonCodes": ["new"]}]}
    layers = {"acceptedBall": {"rows": _layer(x=1)["rows"] + _layer(x=2)["rows"]}}
    states = _states(frames, assignments, ball_truth_layers=layers, match_state_evidence=evidence)
    assert [(s["frameId"], s["timestamp"], s["controllingTeam"], s["controllingTrackId"]) for s in states] == [
        (17, 1.0, "my_team", 7), (17, 2.0, "enemy", 8)]
    assert all(s["source"] == "inferred_ball" and s["ballEstimate"]["x"] == 2.0 and s["reasonCodes"] == ["new"] for s in states)
    states[0]["reasonCodes"].append("caller")
    assert states[1]["reasonCodes"] == ["new"]


def test_unused_assignment_tail_is_still_validated_eagerly():
    with pytest.raises(ValidationError):
        build_accepted_match_state([], [{"bad": "assignment"}])


def test_frame_validation_precedes_assignment_validation():
    with pytest.raises(ValidationError) as caught:
        build_accepted_match_state([{"frameId": 1}], [{"bad": "assignment"}])
    assert caught.value.title == "FrameData"


@pytest.mark.parametrize("field,value", [("acceptedSource", []), ("reasonCodes", None), ("reasonCodes", 12)])
def test_malformed_evidence_remains_an_error_even_for_restart_state(field, value):
    evidence = {"frames": [{"frameId": 17, field: value}]}
    with pytest.raises(TypeError):
        build_accepted_match_state([_frame()], [_owner("dead_ball")], match_state_evidence=evidence)
