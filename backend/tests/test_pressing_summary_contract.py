"""Behavior boundaries for decomposition of the existing pressing summary."""
from copy import deepcopy

import pytest

from backend.app.analytics import _summarize_pressing_metrics
from backend.app.schemas import DetectedEvent, FrameData


def _frame(frame_id=1, *, my_x=60.0, enemy_x=40.0):
    return FrameData(
        frameId=frame_id, timestamp=float(frame_id),
        myTeam=[{"id": 1, "x": my_x, "y": 50.0}, {"id": 2, "x": 20.0, "y": 50.0}],
        enemies=[{"id": 11, "x": enemy_x, "y": 50.0}, {"id": 12, "x": 80.0, "y": 50.0}],
    )


def _event(kind, team, *, frame_id=1, timestamp=1.0, source=None, target=None):
    return DetectedEvent(type=kind, team=team, frameId=frame_id, timestamp=timestamp,
                         fromTrackId=source, toTrackId=target, description="Characterization")


def test_empty_and_unlocated_events_keep_unknown_metrics():
    assert _summarize_pressing_metrics([], []) == (None,) * 6
    assert _summarize_pressing_metrics([], [_event("recovery", "my_team", target=1)]) == (None,) * 6


@pytest.mark.parametrize("team,target,index", [("my_team", 1, 2), ("enemy", 11, 3)])
@pytest.mark.parametrize("kind", ["turnover", "recovery", "tackle"])
@pytest.mark.parametrize("inside", [False, True])
def test_observed_regain_distinguishes_zero_from_unknown(team, target, index, kind, inside):
    frame = _frame(my_x=60.0 if inside else 59.999, enemy_x=40.0 if inside else 40.001)
    expected = [None] * 6
    expected[index] = int(inside)
    if inside:
        expected[index - 2] = 0.0
    assert _summarize_pressing_metrics([frame], [_event(kind, team, target=target)]) == tuple(expected)


@pytest.mark.parametrize("team", [None, "unassigned", "contested", "dead_ball", "other"])
def test_uncontrolled_teams_do_not_contribute(team):
    events = [_event("pass", team, source=1, target=11), _event("turnover", team, target=1)]
    assert _summarize_pressing_metrics([_frame()], events) == (None,) * 6


@pytest.mark.parametrize("source,target,passes", [(11, 12, 0), (99, 12, 1), (None, 12, 1), (99, 98, 0)])
def test_pass_position_prefers_sender_then_falls_back_to_receiver(source, target, passes):
    # Enemy id 11 is outside our pressing zone; id 12 is inside it.
    events = [_event("pass", "enemy", source=source, target=target), _event("recovery", "my_team", target=1)]
    assert _summarize_pressing_metrics([_frame()], events) == (float(passes), None, 1, None, None, None)


@pytest.mark.parametrize("source,target,observed,actions", [(2, 1, True, 1), (1, 2, True, 0), (1, 99, True, 1), (1, None, False, 0), (99, 98, False, 0)])
def test_regain_position_prefers_receiver_and_requires_a_target(source, target, observed, actions):
    events = [_event("recovery", "my_team", source=source, target=target)]
    expected = (0.0 if actions else None, None, actions if observed else None, None, None, None)
    assert _summarize_pressing_metrics([_frame()], events) == expected


def test_missing_event_frame_does_not_use_a_neighbor():
    events = [_event("recovery", "my_team", frame_id=2, target=1)]
    assert _summarize_pressing_metrics([_frame(1)], events) == (None,) * 6


def test_duplicate_frame_ids_keep_last_frame_lookup_policy():
    events = [_event("recovery", "my_team", target=1)]
    assert _summarize_pressing_metrics([_frame(my_x=80.0), _frame(my_x=20.0)], events) == (None, None, 0, None, None, None)


@pytest.mark.parametrize("delay,expected", [(0.0, 0.0), (1.25, 1.2), (8.0, 8.0), (8.0001, None), (-1.0, -1.0)])
@pytest.mark.parametrize("kind", ["turnover", "recovery", "tackle"])
def test_counterpress_keeps_window_rounding_and_input_order(delay, expected, kind):
    # Recovery timing intentionally does not require a frame or receiver id.
    events = [_event("turnover", "enemy", timestamp=10.0), _event(kind, "my_team", timestamp=10.0 + delay)]
    result = _summarize_pressing_metrics([], events)
    assert result == (None, None, None, None, expected, None)


def test_counterpress_uses_first_eligible_recovery_not_best_or_last():
    events = [
        _event("turnover", "enemy", timestamp=10.0),
        _event("pass", "my_team", timestamp=10.2),
        _event("recovery", "enemy", timestamp=10.5),
        _event("tackle", "my_team", timestamp=12.0),
        _event("recovery", "my_team", timestamp=11.0),
    ]
    assert _summarize_pressing_metrics([], events)[4:] == (2.0, None)


def test_counterpress_stops_at_first_outside_window_even_with_later_out_of_order_event():
    events = [
        _event("turnover", "enemy", timestamp=10.0),
        _event("pass", "enemy", timestamp=18.01),
        _event("recovery", "my_team", timestamp=11.0),
    ]
    assert _summarize_pressing_metrics([], events) == (None,) * 6


def test_counterpress_averages_individually_rounded_samples_for_each_team():
    events = [
        _event("turnover", "enemy", timestamp=0.0),
        _event("recovery", "my_team", timestamp=1.25),
        _event("turnover", "enemy", timestamp=20.0),
        _event("recovery", "my_team", timestamp=22.75),
        _event("turnover", "my_team", timestamp=40.0),
        _event("recovery", "enemy", timestamp=43.0),
    ]
    assert _summarize_pressing_metrics([], events)[4:] == (2.0, 3.0)


def test_summary_does_not_mutate_inputs_or_retain_counts_between_calls():
    frames = [_frame()]
    events = [_event("pass", "enemy", target=12), _event("recovery", "my_team", target=1)]
    original = deepcopy((frames, events))
    expected = (1.0, None, 1, None, None, None)
    assert _summarize_pressing_metrics(frames, events) == expected
    assert (frames, events) == original
    assert _summarize_pressing_metrics([], []) == (None,) * 6
    assert _summarize_pressing_metrics(frames, events) == expected
