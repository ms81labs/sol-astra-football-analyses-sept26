"""Behavior boundaries for defensive, possession and physical summary stages."""
from copy import deepcopy

import pytest

from backend.app.analytics import _summarize_defensive_context, summarize_match
from backend.app.schemas import BallOwnership, DetectedEvent, FrameData


def _frame(frame_id=1, *, timestamp=None, my=None, enemy=None):
    return FrameData(
        frameId=frame_id, timestamp=float(frame_id) if timestamp is None else timestamp,
        myTeam=[{"id": i, "x": x, "y": y} for i, x, y in (my or [])],
        enemies=[{"id": i, "x": x, "y": y} for i, x, y in (enemy or [])],
    )


def _event(kind="recovery", team="my_team", *, target=1, source=None, frame_id=1):
    return DetectedEvent(type=kind, team=team, frameId=frame_id, timestamp=1.0,
                         toTrackId=target, fromTrackId=source, description="Summary boundary")


def _context(frames, events, heights=(None, None)):
    return _summarize_defensive_context(frames, [], events, *heights)


def _metric(summary, name):
    return next(record for record in summary.metricAvailability if record.metric == name)


@pytest.mark.parametrize("height,expected", [
    (None, None), (0, "low_block"), (34.999, "low_block"),
    (35, "mid_block"), (50, "mid_block"), (50.001, "high_block"),
])
def test_defensive_block_boundaries_remain_independent_of_event_evidence(height, expected):
    assert _context([], [], (height, height)) == (expected, expected, None, None, None, None)


@pytest.mark.parametrize("team,target,index", [("my_team", 1, 2), ("enemy", 11, 3)])
@pytest.mark.parametrize("x", [20, 35, 40, 60, 70, 80])
def test_regain_zone_and_high_press_use_their_distinct_boundaries(team, target, index, x):
    frame = _frame(my=[(1, x, 50)], enemy=[(11, x, 50)])
    result = _context([frame], [_event(team=team, target=target)])
    expected = {"defensive_third": 0, "middle_third": 0, "attacking_third": 0}
    if team == "my_team":
        zone = "defensive_third" if x < 35 else "attacking_third" if x > 70 else "middle_third"
        high_press = x >= 60
    else:
        zone = "defensive_third" if x > 70 else "attacking_third" if x < 35 else "middle_third"
        high_press = x <= 40
    expected[zone] = 1
    assert result[index] == expected
    assert result[5 - index] is None
    assert result[index + 2] == (0.0 if high_press else None)


@pytest.mark.parametrize("kind", ["recovery", "tackle", "turnover"])
@pytest.mark.parametrize("target,source,zone,exposure", [
    (1, 2, "attacking_third", 0.0),
    (2, 1, "defensive_third", None),
    (99, 1, "attacking_third", None),
    (None, 1, None, 0.0),
    (0, 2, "attacking_third", None),
    (99, None, None, None),
])
def test_regain_receiver_fallback_and_exposure_lookup_are_not_conflated(kind, target, source, zone, exposure):
    frame = _frame(my=[(0, 80, 50), (1, 80, 50), (2, 20, 50)])
    result = _context([frame], [_event(kind, target=target, source=source)])
    expected = None if zone is None else {name: int(name == zone) for name in
                                        ("defensive_third", "middle_third", "attacking_third")}
    assert result[2] == expected
    assert result[4] == exposure


@pytest.mark.parametrize("team", [None, "unassigned", "contested", "other"])
def test_uncontrolled_regains_do_not_create_team_measurements(team):
    frame = _frame(my=[(1, 80, 50)], enemy=[(11, 20, 50)])
    assert _context([frame], [_event(team=team)]) == (None,) * 6


def test_unlocated_turnovers_still_count_as_exposure_numerator():
    frame = _frame(my=[(1, 65, 50)])
    events = [_event("turnover", "enemy", target=None, frame_id=999)] * 2 + [_event()] * 3
    result = _context([frame], events)
    assert result[2] == {"defensive_third": 0, "middle_third": 3, "attacking_third": 0}
    assert result[4] == 0.67
    assert result[5] is None


def test_regain_frame_lookup_is_exact_and_last_duplicate_wins():
    low, high = _frame(my=[(1, 20, 50)]), _frame(my=[(1, 80, 50)])
    assert _context([low, high], [_event()])[2]["attacking_third"] == 1
    assert _context([high, low], [_event()])[2]["defensive_third"] == 1
    assert _context([high], [_event(frame_id=2)]) == (None,) * 6


def test_defensive_results_are_independent_and_do_not_mutate_inputs():
    frames, events = [_frame(my=[(1, 80, 50)])], [_event()]
    original = deepcopy((frames, events))
    first = _context(frames, events)
    first[2]["attacking_third"] = 99
    assert _context(frames, events)[2]["attacking_third"] == 1
    assert (frames, events) == original
    assert _context([], []) == (None,) * 6


@pytest.mark.parametrize("rows,expected,eligible,requested,assumed", [
    ([], None, 0, 0, False),
    ([(0, "my_team")], 100, 1, 1, True),
    ([(0, "enemy")], 0, 1, 1, True),
    ([(0, "my_team"), (0, "enemy")], 50, 2, 2, True),
    ([(2, "my_team"), (1, "enemy")], 50, 2, 2, True),
    ([(0, "my_team"), (1, "enemy"), (4, "dead_ball"), (6, "my_team")], 25, 4, 6, False),
    ([(0, "unassigned"), (3, "contested")], None, 0, 3, False),
    ([(0, "enemy"), (2, "my_team")], 0, 2, 2, False),
    ([(0, "dead_ball"), (2, "my_team")], 100, 1, 1, True),
])
def test_possession_keeps_interval_weights_terminal_exclusion_and_fallback(rows, expected, eligible, requested, assumed):
    assignments = [BallOwnership(frameId=i, timestamp=t, team=team, trackId=1)
                   for i, (t, team) in enumerate(rows)]
    summary = summarize_match([], assignments)
    metric = _metric(summary, "possession_pct")
    assert summary.possession == expected
    assert metric.eligibleSeconds == eligible
    assert metric.requestedSeconds == requested
    assert ("EQUAL_DURATION_ASSUMED" in metric.reasonCodes) is assumed
    assert metric.availability == ("unknown" if expected is None else "available")
    assert ("UNKNOWN_INTERVALS_EXCLUDED" in metric.reasonCodes) == (expected is not None and requested > eligible)


@pytest.mark.parametrize("team,field", [("my", "myTeam"), ("enemy", "enemy")])
@pytest.mark.parametrize("step,sprints,speed", [(25.0, 0, 25.0), (25.001, 1, 25.0), (26.0, 1, 26.0)])
def test_sprint_threshold_is_strict_and_continuous_runs_count_once(team, field, step, sprints, speed):
    frames = [_frame(i, timestamp=i * 3.6, **{team: [(1, i * step, 50)]}) for i in range(3)]
    summary = summarize_match(frames, [], identity_continuous=True, calibration_accepted=True,
                              pitch_length_m=100, pitch_width_m=100)
    assert getattr(summary, field + "Distance") == round(step * 2)
    assert getattr(summary, field + "TopSpeed") == speed
    assert getattr(summary, field + "Sprints") == sprints


@pytest.mark.parametrize("middle_timestamp", [1.0, 0.5])
def test_nonpositive_time_step_resets_sprints_and_is_not_counted(middle_timestamp):
    frames = [_frame(i, timestamp=t, my=[(1, x, 50)]) for i, (t, x) in
              enumerate([(0, 0), (1, 10), (middle_timestamp, 20), (middle_timestamp + 1, 30)])]
    summary = summarize_match(frames, [], identity_continuous=True, calibration_accepted=True, pitch_length_m=100)
    assert summary.myTeamDistance == 20
    assert summary.myTeamTopSpeed == 36.0
    assert summary.myTeamSprints == 2
    assert _metric(summary, "my_team_distance_m").eligibleSeconds == 2
    assert _metric(summary, "my_team_distance_m").requestedSeconds == 2


def test_duplicate_tracks_keep_first_previous_match_and_current_duplicate_counting():
    frames = [_frame(0, timestamp=0, my=[(1, 0, 50), (1, 99, 50)]),
              _frame(1, timestamp=1, my=[(1, 10, 50), (1, 20, 50)])]
    summary = summarize_match(frames, [], identity_continuous=True, pitch_length_m=100)
    assert (summary.myTeamDistance, summary.myTeamTopSpeed, summary.myTeamSprints) == (30, 72, 2)
    assert summary.myTeamAvgPos == {"x": 32.2, "y": 50.0}


def test_shared_track_ids_remain_separate_between_teams():
    frames = [_frame(0, timestamp=0, my=[(1, 0, 0)], enemy=[(1, 100, 100)]),
              _frame(1, timestamp=1, my=[(1, 10, 0)], enemy=[(1, 100, 95)])]
    summary = summarize_match(frames, [], identity_continuous=True, pitch_length_m=100, pitch_width_m=100)
    assert (summary.myTeamDistance, summary.enemyDistance) == (10, 5)
    assert (summary.myTeamTopSpeed, summary.enemyTopSpeed) == (36, 18)
    assert (summary.myTeamSprints, summary.enemySprints) == (1, 0)


def test_missing_track_ends_sprint_without_linking_across_gap():
    frames = [_frame(i, timestamp=i, my=players) for i, players in enumerate([
        [(1, 0, 50)], [(1, 10, 50)], [], [(1, 20, 50)], [(1, 30, 50)]])]
    summary = summarize_match(frames, [], identity_continuous=True, calibration_accepted=True, pitch_length_m=100)
    assert (summary.myTeamDistance, summary.myTeamSprints) == (20, 2)
    metric = _metric(summary, "my_team_distance_m")
    assert (metric.eligibleSeconds, metric.requestedSeconds) == (2, 4)


@pytest.mark.parametrize("identity", [False, True])
@pytest.mark.parametrize("calibration", [False, True])
def test_physical_coverage_is_observed_even_when_values_are_withheld(identity, calibration):
    frames = [_frame(0, timestamp=0, my=[(1, 0, 50)]), _frame(1, timestamp=1, my=[(1, 10, 50)])]
    summary = summarize_match(frames, [], identity_continuous=identity, calibration_accepted=calibration,
                              pitch_length_m=100, pitch_width_m=100)
    assert summary.myTeamDistance == (10 if identity else None)
    assert summary.myTeamAvgPos == {"x": 5.0, "y": 50.0}
    metric = _metric(summary, "my_team_distance_m")
    assert (metric.eligibleSeconds, metric.requestedSeconds) == (1, 1)
    assert metric.availability == ("available" if identity and calibration else "withheld")
    assert ("IDENTITY_DISCONTINUITY" in metric.reasonCodes) is (not identity)
    assert ("CALIBRATION_UNAVAILABLE" in metric.reasonCodes) is (not calibration)
    assert metric.pitchDimensions == {"lengthM": 100, "widthM": 100}


@pytest.mark.parametrize("direction", ["left_to_right", "right_to_left"])
@pytest.mark.parametrize("as_dict", [False, True])
def test_display_positions_and_physical_totals_remain_in_original_coordinates(direction, as_dict):
    frames = [_frame(0, timestamp=0, my=[(1, 10, 20)]), _frame(1, timestamp=1, my=[(1, 13, 24)])]
    frames = [f.model_dump() for f in frames] if as_dict else frames
    before = deepcopy(frames)
    summary = summarize_match(frames, [], attack_direction=direction, identity_continuous=True,
                              pitch_length_m=100, pitch_width_m=100)
    assert summary.myTeamAvgPos == {"x": 11.5, "y": 22.0}
    assert (summary.myTeamDistance, summary.myTeamTopSpeed, summary.myTeamSprints) == (5, 18, 0)
    assert frames == before


def test_empty_summary_physical_zero_is_distinct_from_unknown_observation():
    summary = summarize_match([], [], identity_continuous=True, calibration_accepted=True)
    assert (summary.myTeamDistance, summary.enemyDistance, summary.myTeamTopSpeed, summary.myTeamSprints) == (0, 0, 0, 0)
    assert summary.myTeamAvgPos is None and summary.myTeamXg is None and summary.possession is None
    assert _metric(summary, "my_team_distance_m").reasonCodes == ["ZERO_DENOMINATOR"]
