from backend.app.analytics import (
    apply_match_state_continuity,
    assign_ball_possession,
    build_accepted_match_state,
    build_formation_timeline,
    build_shot_analytics,
    detect_events,
    partition_detected_events,
    summarize_match,
    _get_event_x,
)
from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchStateFrame
from backend.app.team_classification import classify_player_rows_by_cluster, cluster_track_colors


def test_assign_ball_possession_prefers_continuity_for_small_ball_drift():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 28.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 34.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 31.4, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 29.8, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 32.2, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)

    assert assignments[0].team == "my_team"
    assert assignments[0].trackId == 7
    assert assignments[1].team == "my_team"
    assert assignments[1].trackId == 7


def test_assign_ball_possession_uses_unassigned_players_when_teams_are_unresolved():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 31.0, "y": 50.0, "confidence": 0.92},
                {"id": 18, "x": 46.0, "y": 50.0, "confidence": 0.9},
            ],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 44.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 32.0, "y": 50.0, "confidence": 0.92},
                {"id": 18, "x": 45.0, "y": 50.0, "confidence": 0.9},
            ],
        },
    ]

    assignments = assign_ball_possession(frames)

    assert assignments[0].team == "unassigned"
    assert assignments[0].trackId == 7
    assert assignments[1].team == "unassigned"
    assert assignments[1].trackId == 18


def test_assign_ball_possession_bridges_short_dead_ball_gap_for_same_track():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 31.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": None,
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 32.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 33.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 34.0, "y": 50.0, "confidence": 0.92}],
        },
    ]

    assignments = assign_ball_possession(frames)

    assert [assignment.team for assignment in assignments] == ["unassigned", "unassigned", "unassigned"]
    assert [assignment.trackId for assignment in assignments] == [7, 7, 7]


def test_assign_ball_possession_keeps_short_dead_ball_gap_visible_for_resolved_team_regain():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 22.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 21.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 79.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": None,
            "myTeam": [{"id": 7, "x": 23.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 77.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 23.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 77.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [assignment.team for assignment in assignments] == ["my_team", "dead_ball", "my_team"]
    assert [assignment.trackId for assignment in assignments] == [7, None, 7]
    assert [event.type for event in events] == ["recovery"]
    assert events[0].team == "my_team"
    assert events[0].toTrackId == 7


def test_assign_ball_possession_keeps_dead_ball_for_long_or_changed_owner_gap():
    long_gap_frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 31.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 1.2,
            "ball": None,
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 32.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 1.4,
            "ball": {"x": 33.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 34.0, "y": 50.0, "confidence": 0.92}],
        },
    ]

    long_gap_assignments = assign_ball_possession(long_gap_frames)

    assert [assignment.team for assignment in long_gap_assignments] == ["unassigned", "dead_ball", "unassigned"]

    changed_owner_frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 31.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": None,
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 32.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 44.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 34.0, "y": 50.0, "confidence": 0.92},
                {"id": 18, "x": 45.0, "y": 50.0, "confidence": 0.92},
            ],
        },
    ]

    changed_owner_assignments = assign_ball_possession(changed_owner_frames)

    assert [assignment.team for assignment in changed_owner_assignments] == ["unassigned", "dead_ball", "unassigned"]
    assert [assignment.trackId for assignment in changed_owner_assignments] == [7, None, 18]


def test_build_accepted_match_state_derives_observed_inferred_loose_restart_and_unknown_modes():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 20.0, "y": 30.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 19.0, "y": 30.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 42.0, "y": 48.0, "confidence": 0.70},
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": None,
        },
        {
            "frameId": 3,
            "timestamp": 0.6,
            "ball": None,
        },
        {
            "frameId": 4,
            "timestamp": 0.8,
            "ball": {"x": 74.0, "y": 52.0, "confidence": 0.71},
            "enemies": [{"id": 18, "x": 73.0, "y": 52.0, "confidence": 0.91}],
        },
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="contested", trackId=None, distance=4.0),
        BallOwnership(frameId=2, timestamp=0.4, team="dead_ball", trackId=None),
        BallOwnership(frameId=3, timestamp=0.6, team="unassigned", trackId=None),
        BallOwnership(frameId=4, timestamp=0.8, team="enemy", trackId=18, distance=1.0),
    ]
    ball_truth_layers = {
        "observedBall": {
            "rows": [{"Frame_ID": 0, "X": 20.0, "Y": 30.0, "Conf": 0.95}],
            "summary": {"frameCount": 1},
        },
        "inferredBall": {
            "rows": [
                {"Frame_ID": 1, "X": 42.0, "Y": 48.0, "Conf": 0.70},
                {"Frame_ID": 4, "X": 74.0, "Y": 52.0, "Conf": 0.71},
            ],
            "summary": {"frameCount": 2},
        },
        "acceptedBall": {
            "rows": [
                {"Frame_ID": 0, "X": 20.0, "Y": 30.0, "Conf": 0.95},
                {"Frame_ID": 1, "X": 42.0, "Y": 48.0, "Conf": 0.70},
                {"Frame_ID": 4, "X": 74.0, "Y": 52.0, "Conf": 0.71},
            ],
            "summary": {"frameCount": 3},
        },
    }

    accepted_match_state = build_accepted_match_state(frames, assignments, ball_truth_layers=ball_truth_layers)

    assert [frame.mode for frame in accepted_match_state] == [
        "controlled_possession",
        "loose_ball",
        "restart_or_out",
        "unknown",
        "controlled_possession",
    ]
    assert accepted_match_state[0].source == "observed_ball"
    assert accepted_match_state[0].ballVisibility == "visible"
    assert accepted_match_state[0].confidence == 0.90
    assert accepted_match_state[0].ballEstimate is not None
    assert accepted_match_state[0].ballEstimate.x == 20.0
    assert accepted_match_state[1].controllingTeam == "contested"
    assert accepted_match_state[1].source == "inferred_ball"
    assert accepted_match_state[1].ballVisibility == "inferred"
    assert accepted_match_state[1].confidence == 0.60
    assert accepted_match_state[2].mode == "restart_or_out"
    assert accepted_match_state[2].source == "restart_rule"
    assert accepted_match_state[2].ballEstimate is None
    assert accepted_match_state[3].mode == "unknown"
    assert accepted_match_state[3].source == "unknown"
    assert accepted_match_state[4].source == "inferred_ball"
    assert accepted_match_state[4].ballVisibility == "inferred"
    assert accepted_match_state[4].confidence == 0.75


def test_build_accepted_match_state_creates_hidden_player_conditioned_frame_when_same_holder_brackets_gap():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 20.0, "y": 30.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 19.0, "y": 30.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": None,
            "myTeam": [{"id": 7, "x": 21.0, "y": 30.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 22.0, "y": 30.0, "confidence": 0.80},
            "myTeam": [{"id": 7, "x": 21.0, "y": 30.0, "confidence": 0.92}],
        },
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="dead_ball", trackId=None),
        BallOwnership(frameId=2, timestamp=0.4, team="my_team", trackId=7, distance=1.0),
    ]
    ball_truth_layers = {
        "observedBall": {"rows": [{"Frame_ID": 0, "X": 20.0, "Y": 30.0, "Conf": 0.95}], "summary": {"frameCount": 1}},
        "inferredBall": {"rows": [{"Frame_ID": 2, "X": 22.0, "Y": 30.0, "Conf": 0.80}], "summary": {"frameCount": 1}},
        "acceptedBall": {
            "rows": [
                {"Frame_ID": 0, "X": 20.0, "Y": 30.0, "Conf": 0.95},
                {"Frame_ID": 2, "X": 22.0, "Y": 30.0, "Conf": 0.80},
            ],
            "summary": {"frameCount": 2},
        },
    }

    accepted_match_state = build_accepted_match_state(frames, assignments, ball_truth_layers=ball_truth_layers)

    assert accepted_match_state[1].mode == "controlled_possession"
    assert accepted_match_state[1].controllingTeam == "my_team"
    assert accepted_match_state[1].controllingTrackId == 7
    assert accepted_match_state[1].ballVisibility == "hidden"
    assert accepted_match_state[1].source == "player_conditioned"
    assert accepted_match_state[1].confidence == 0.65
    assert accepted_match_state[1].ballEstimate is None


def test_apply_match_state_continuity_bridges_hidden_gap_for_same_holder():
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="dead_ball", trackId=None),
        BallOwnership(frameId=2, timestamp=0.4, team="my_team", trackId=7, distance=1.0),
    ]
    accepted_match_state = [
        MatchStateFrame(
            frameId=0,
            timestamp=0.0,
            mode="controlled_possession",
            controllingTeam="my_team",
            controllingTrackId=7,
            ballVisibility="visible",
            ballEstimate={"x": 20.0, "y": 30.0, "confidence": 0.95, "radius": 0.0},
            source="observed_ball",
            confidence=0.90,
            reasonCodes=[],
        ),
        MatchStateFrame(
            frameId=1,
            timestamp=0.2,
            mode="controlled_possession",
            controllingTeam="my_team",
            controllingTrackId=7,
            ballVisibility="hidden",
            ballEstimate=None,
            source="player_conditioned",
            confidence=0.65,
            reasonCodes=["player_conditioned"],
        ),
        MatchStateFrame(
            frameId=2,
            timestamp=0.4,
            mode="controlled_possession",
            controllingTeam="my_team",
            controllingTrackId=7,
            ballVisibility="inferred",
            ballEstimate={"x": 22.0, "y": 30.0, "confidence": 0.80, "radius": 0.0},
            source="inferred_ball",
            confidence=0.75,
            reasonCodes=[],
        ),
    ]

    adjusted, applied_frames = apply_match_state_continuity(assignments, accepted_match_state)

    assert applied_frames == 1
    assert [assignment.team for assignment in adjusted] == ["my_team", "my_team", "my_team"]
    assert [assignment.trackId for assignment in adjusted] == [7, 7, 7]


def test_apply_match_state_continuity_does_not_override_mismatched_or_existing_control():
    mismatched_state = [
        MatchStateFrame(
            frameId=0,
            timestamp=0.0,
            mode="controlled_possession",
            controllingTeam="my_team",
            controllingTrackId=7,
            ballVisibility="visible",
            ballEstimate={"x": 20.0, "y": 30.0, "confidence": 0.95, "radius": 0.0},
            source="observed_ball",
            confidence=0.90,
            reasonCodes=[],
        ),
        MatchStateFrame(
            frameId=1,
            timestamp=0.2,
            mode="controlled_possession",
            controllingTeam="my_team",
            controllingTrackId=7,
            ballVisibility="hidden",
            ballEstimate=None,
            source="player_conditioned",
            confidence=0.65,
            reasonCodes=[],
        ),
        MatchStateFrame(
            frameId=2,
            timestamp=0.4,
            mode="controlled_possession",
            controllingTeam="enemy",
            controllingTrackId=18,
            ballVisibility="visible",
            ballEstimate={"x": 80.0, "y": 50.0, "confidence": 0.95, "radius": 0.0},
            source="observed_ball",
            confidence=0.90,
            reasonCodes=[],
        ),
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="dead_ball", trackId=None),
        BallOwnership(frameId=2, timestamp=0.4, team="enemy", trackId=18, distance=1.0),
    ]

    adjusted, applied_frames = apply_match_state_continuity(assignments, mismatched_state)

    assert applied_frames == 0
    assert adjusted[1].team == "dead_ball"

    conflicting_assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="enemy", trackId=18, distance=1.0),
        BallOwnership(frameId=2, timestamp=0.4, team="my_team", trackId=7, distance=1.0),
    ]

    conflicting_adjusted, conflicting_applied_frames = apply_match_state_continuity(
        conflicting_assignments,
        [
            MatchStateFrame(
                frameId=0,
                timestamp=0.0,
                mode="controlled_possession",
                controllingTeam="my_team",
                controllingTrackId=7,
                ballVisibility="visible",
                ballEstimate={"x": 20.0, "y": 30.0, "confidence": 0.95, "radius": 0.0},
                source="observed_ball",
                confidence=0.90,
                reasonCodes=[],
            ),
            MatchStateFrame(
                frameId=1,
                timestamp=0.2,
                mode="controlled_possession",
                controllingTeam="my_team",
                controllingTrackId=7,
                ballVisibility="hidden",
                ballEstimate=None,
                source="player_conditioned",
                confidence=0.65,
                reasonCodes=[],
            ),
            MatchStateFrame(
                frameId=2,
                timestamp=0.4,
                mode="controlled_possession",
                controllingTeam="my_team",
                controllingTrackId=7,
                ballVisibility="visible",
                ballEstimate={"x": 22.0, "y": 30.0, "confidence": 0.95, "radius": 0.0},
                source="observed_ball",
                confidence=0.90,
                reasonCodes=[],
            ),
        ],
    )

    assert conflicting_applied_frames == 0
    assert conflicting_adjusted[1].team == "enemy"


def test_cluster_track_colors_groups_similar_tracks_together():
    track_colors = {
        1: [(34, 86, 220), (38, 90, 225)],
        2: [(36, 88, 210), (40, 95, 215)],
        9: [(215, 42, 54), (220, 48, 62)],
        10: [(208, 38, 44), (214, 41, 51)],
    }

    result = cluster_track_colors(track_colors, cluster_count=2)

    assert result.trackToCluster[1] == result.trackToCluster[2]
    assert result.trackToCluster[9] == result.trackToCluster[10]
    assert result.trackToCluster[1] != result.trackToCluster[9]
    assert len(result.clusters) == 2


def test_summarize_match_uses_ball_assignments_in_possession_percentage():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 22.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 21.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 79.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 23.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 22.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 78.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 77.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 25.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 76.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    summary = summarize_match(frames, assignments, identity_continuous=True)

    assert summary.possession == 100
    assert summary.myTeamDistance > 0
    assert summary.enemyDistance > 0


def test_summarize_match_withholds_physical_totals_until_identity_continuity() -> None:
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "myTeam": [{"id": 7, "x": 21.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 79.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "myTeam": [{"id": 7, "x": 22.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 78.0, "y": 50.0, "confidence": 0.9}],
        },
    ]
    summary = summarize_match(frames, [])
    assert summary.myTeamDistance is None
    assert summary.enemyDistance is None
    assert summary.myTeamTopSpeed is None
    assert summary.enemyTopSpeed is None
    assert summary.myTeamSprints is None
    assert summary.enemySprints is None
    physical = {item.metric: item for item in summary.metricAvailability}
    assert physical["my_team_distance_m"].availability == "withheld"
    assert physical["my_team_distance_m"].value is None
    assert physical["my_team_distance_m"].denominator == "identity_continuous_eligible_seconds"
    continuous = summarize_match(frames, [], identity_continuous=True)
    assert continuous.myTeamDistance > 0
    available = {item.metric: item for item in continuous.metricAvailability}
    assert available["my_team_distance_m"].availability == "withheld"
    assert available["my_team_distance_m"].reasonCodes == ["CALIBRATION_UNAVAILABLE"]


def test_summarize_match_keeps_possession_unknown_without_controlled_frames():
    frames = [{"frameId": 0, "timestamp": 0.0, "myTeam": [], "enemies": []}]
    summary = summarize_match(frames, [BallOwnership(frameId=0, timestamp=0.0, team="unassigned", trackId=7)])
    assert summary.possession is None


def test_classify_player_rows_by_cluster_maps_selected_cluster_to_my_team():
    rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 1, "X": 20.0, "Y": 50.0, "Conf": 0.9},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 8, "X": 80.0, "Y": 50.0, "Conf": 0.9},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 50.0, "Conf": 0.95},
    ]
    cluster_result = cluster_track_colors(
        {
            1: [(30, 70, 210), (34, 74, 214)],
            8: [(210, 55, 50), (214, 59, 55)],
        }
    )

    classified_rows = classify_player_rows_by_cluster(rows, cluster_result, my_team_cluster=cluster_result.trackToCluster[8])

    entity_by_track = {
        row["Track_ID"]: row["Entity_Type"]
        for row in classified_rows
        if row["Entity_Type"] != "ball"
    }
    assert entity_by_track[8] == "my_team"
    assert entity_by_track[1] == "enemy"


def test_detect_events_emits_pass_then_turnover_from_control_changes():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 21.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 20.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 35.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 75.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 22.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 21.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 36.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 74.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 34.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 22.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 33.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 73.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 3,
            "timestamp": 0.6,
            "ball": {"x": 35.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 22.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 34.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 72.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 4,
            "timestamp": 0.8,
            "ball": {"x": 74.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 39.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 73.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass", "turnover"]
    assert events[0].team == "my_team"
    assert events[0].fromTrackId == 7
    assert events[0].toTrackId == 11
    assert events[1].team == "enemy"


def test_detect_events_marks_candidates_as_provisional_and_unreviewed():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 21.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 20.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 35.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 75.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 34.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 21.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 33.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 74.0, "y": 50.0, "confidence": 0.9}],
        },
    ]
    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)
    assert events
    assert all(event.reviewStatus == "unreviewed" for event in events)
    assert all(event.heuristicName == "provisional_event_suggestion" for event in events)
    partitioned = partition_detected_events(events)
    assert partitioned["candidates"] == events
    assert partitioned["accepted"] == []
    assert partitioned["rejected"] == []


def test_detect_events_keeps_short_dead_ball_gap_visible_for_resolved_team_regain():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 22.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 21.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 79.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": None,
            "myTeam": [{"id": 7, "x": 23.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 77.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 23.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 77.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [assignment.team for assignment in assignments] == ["my_team", "dead_ball", "my_team"]
    assert [assignment.trackId for assignment in assignments] == [7, None, 7]
    assert [event.type for event in events] == ["recovery"]
    assert events[0].team == "my_team"
    assert events[0].toTrackId == 7


def test_detect_events_emits_pass_across_short_dead_ball_gap_for_same_team_new_receiver():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 18.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 18.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 44.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 75.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": None,
            "myTeam": [
                {"id": 7, "x": 20.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 44.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 74.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 44.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 22.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 44.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 73.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass"]
    assert events[0].team == "my_team"
    assert events[0].fromTrackId == 7
    assert events[0].toTrackId == 11


def test_detect_events_does_not_emit_turnover_when_unassigned_track_resolves_to_team():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 30.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 31.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 31.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [],
            "unassignedPlayers": [],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert events == []


def test_detect_events_does_not_invent_passes_between_unassigned_players():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": None,
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 23.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 36.0, "y": 50.0, "confidence": 0.92},
            ],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 23.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 36.0, "y": 50.0, "confidence": 0.92},
            ],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 35.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 35.0, "y": 50.0, "confidence": 0.92},
            ],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert not any(event.type == "pass" for event in events)
    assert events[0].team == "unassigned"
    assert events[0].toTrackId == 7


def test_detect_events_emits_neutral_carry_after_short_loose_gap_for_same_unassigned_track():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 50.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 28.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 40.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 40.0, "y": 50.0, "confidence": 0.92}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["recovery", "carry"]
    assert events[0].team == "unassigned"
    assert events[0].toTrackId == 7
    assert events[1].team == "unassigned"
    assert events[1].fromTrackId == 7
    assert events[1].toTrackId == 7


def test_detect_events_does_not_emit_neutral_carry_for_stationary_or_backward_signal():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 50.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 25.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 25.0, "y": 50.0, "confidence": 0.92}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["recovery"]

    backward_frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 36.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 36.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 50.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 30.0, "y": 50.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92}],
        },
    ]

    backward_assignments = assign_ball_possession(backward_frames)
    backward_events = detect_events(backward_frames, backward_assignments)

    assert [event.type for event in backward_events] == ["recovery"]


def test_detect_events_emits_controlled_carry_for_forward_same_player_segment():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 75.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 31.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 31.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 74.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 38.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 38.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 73.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["carry"]
    assert events[0].team == "my_team"
    assert events[0].fromTrackId == 7
    assert events[0].toTrackId == 7


def test_detect_events_does_not_emit_controlled_carry_for_stationary_or_backward_segment():
    stationary_frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 24.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 75.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 26.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 26.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 74.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    stationary_assignments = assign_ball_possession(stationary_frames)
    stationary_events = detect_events(stationary_frames, stationary_assignments)

    assert stationary_events == []

    backward_frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 38.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 38.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 75.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 30.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 74.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    backward_assignments = assign_ball_possession(backward_frames)
    backward_events = detect_events(backward_frames, backward_assignments)

    assert backward_events == []


def test_detect_events_suppresses_repeated_neutral_recoveries_for_same_static_ball_cluster():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 36.8, "y": 96.7, "confidence": 0.52},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 35.9, "y": 91.8, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 60.0, "y": 96.7, "confidence": 0.52},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 36.2, "y": 91.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 36.9, "y": 96.8, "confidence": 0.51},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 36.5, "y": 91.1, "confidence": 0.92}],
        },
        {
            "frameId": 3,
            "timestamp": 0.6,
            "ball": {"x": 60.0, "y": 96.75, "confidence": 0.5},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 36.7, "y": 90.9, "confidence": 0.92}],
        },
        {
            "frameId": 4,
            "timestamp": 0.8,
            "ball": {"x": 36.85, "y": 96.75, "confidence": 0.5},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 36.8, "y": 90.8, "confidence": 0.92}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["recovery"]
    assert events[0].toTrackId == 9


def test_detect_events_keeps_new_neutral_recovery_when_ball_cluster_moves_meaningfully():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 36.8, "y": 96.7, "confidence": 0.52},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 35.9, "y": 91.8, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 60.0, "y": 96.7, "confidence": 0.52},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 36.2, "y": 91.0, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 46.8, "y": 90.0, "confidence": 0.51},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 46.1, "y": 88.9, "confidence": 0.92}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["recovery", "carry"]
    assert events[0].toTrackId == 9
    assert events[1].fromTrackId == 9


def test_detect_events_suppresses_repeated_resolved_recoveries_for_same_static_ball_cluster():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 36.8, "y": 96.7, "confidence": 0.52},
            "myTeam": [{"id": 9, "x": 35.9, "y": 91.8, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 60.0, "y": 60.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 60.0, "y": 96.7, "confidence": 0.52},
            "myTeam": [{"id": 9, "x": 36.2, "y": 91.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 60.0, "y": 60.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 36.9, "y": 96.8, "confidence": 0.51},
            "myTeam": [{"id": 9, "x": 36.5, "y": 91.1, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 60.0, "y": 60.0, "confidence": 0.9}],
        },
        {
            "frameId": 3,
            "timestamp": 0.6,
            "ball": {"x": 60.0, "y": 96.75, "confidence": 0.5},
            "myTeam": [{"id": 9, "x": 36.7, "y": 90.9, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 60.0, "y": 60.0, "confidence": 0.9}],
        },
        {
            "frameId": 4,
            "timestamp": 0.8,
            "ball": {"x": 36.85, "y": 96.75, "confidence": 0.5},
            "myTeam": [{"id": 9, "x": 36.8, "y": 90.8, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 60.0, "y": 60.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["recovery"]
    assert events[0].team == "my_team"
    assert events[0].toTrackId == 9


def test_detect_events_suppresses_static_neutral_recovery_cluster_beyond_immediate_previous_event():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 60.0, "y": 96.7, "confidence": 0.52},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 35.8, "y": 91.9, "confidence": 0.92}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 36.8, "y": 96.7, "confidence": 0.52},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 35.9, "y": 91.8, "confidence": 0.92}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 70.0, "y": 90.0, "confidence": 0.51},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 36.2, "y": 91.0, "confidence": 0.92}],
        },
        {
            "frameId": 3,
            "timestamp": 0.6,
            "ball": {"x": 46.8, "y": 90.0, "confidence": 0.51},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 46.1, "y": 88.9, "confidence": 0.92}],
        },
        {
            "frameId": 4,
            "timestamp": 1.6,
            "ball": {"x": 70.0, "y": 90.0, "confidence": 0.5},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 46.0, "y": 88.8, "confidence": 0.92}],
        },
        {
            "frameId": 5,
            "timestamp": 1.8,
            "ball": {"x": 36.9, "y": 96.8, "confidence": 0.5},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [{"id": 9, "x": 36.7, "y": 90.9, "confidence": 0.92}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["recovery", "recovery", "carry"]
    assert events[0].toTrackId == 9
    assert events[1].toTrackId == 9
    assert events[2].toTrackId == 9


def test_detect_events_emits_cross_for_wide_pass_into_box():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 72.0, "y": 9.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 72.0, "y": 9.0, "confidence": 0.92},
                {"id": 11, "x": 88.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 80.0, "y": 44.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 88.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 7, "x": 74.0, "y": 12.0, "confidence": 0.92},
                {"id": 11, "x": 88.0, "y": 50.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 18, "x": 82.0, "y": 47.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass", "cross"]
    assert events[1].team == "my_team"
    assert events[1].fromTrackId == 7
    assert events[1].toTrackId == 11


def test_detect_events_emits_through_ball_for_progressive_line_breaking_pass():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 48.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 48.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 76.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [
                {"id": 3, "x": 58.0, "y": 45.0, "confidence": 0.9},
                {"id": 4, "x": 63.0, "y": 55.0, "confidence": 0.9},
            ],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 76.0, "y": 52.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 50.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 76.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [
                {"id": 3, "x": 59.0, "y": 45.0, "confidence": 0.9},
                {"id": 4, "x": 64.0, "y": 55.0, "confidence": 0.9},
            ],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass"]

    for frame in frames:
        frame["enemies"].extend(
            [
                {"id": 5, "x": 60.0, "y": 35.0, "confidence": 0.9},
                {"id": 6, "x": 62.0, "y": 65.0, "confidence": 0.9},
            ]
        )
    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass", "through_ball"]


def test_detect_events_does_not_mark_regular_forward_pass_as_through_ball():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 40.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 40.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 49.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 3, "x": 70.0, "y": 45.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 49.0, "y": 52.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 41.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 49.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 3, "x": 70.0, "y": 45.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass"]


def test_detect_events_emits_tackle_when_turnover_happens_under_pressure():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 48.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 48.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 52.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 53.6, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 49.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 18, "x": 53.2, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["turnover", "tackle"]
    assert events[1].team == "enemy"
    assert events[1].toTrackId == 18


def test_detect_events_emits_interception_for_non_tackle_turnover():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 58.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 6, "x": 58.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 14, "x": 68.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 68.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 6, "x": 58.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 14, "x": 68.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["turnover", "interception"]


def test_detect_events_emits_shot_when_controlled_attack_ends_near_goal():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 87.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 9, "x": 87.0, "y": 48.0, "confidence": 0.92}],
            "enemies": [{"id": 4, "x": 82.0, "y": 45.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 92.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 9, "x": 91.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 4, "x": 85.0, "y": 47.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": None,
            "myTeam": [{"id": 9, "x": 92.0, "y": 51.0, "confidence": 0.92}],
            "enemies": [{"id": 4, "x": 86.0, "y": 48.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["shot"]
    assert events[0].team == "my_team"
    assert events[0].fromTrackId == 9


def test_build_formation_timeline_detects_smoothed_transition():
    def make_players(rows: list[int]) -> list[dict]:
        players: list[dict] = []
        track_id = 1
        for row_index, row_count in enumerate(rows):
            for column in range(row_count):
                players.append(
                    {
                        "id": track_id,
                        "x": 6 + row_index * 20 + column,
                        "y": 15 + column * 12,
                        "confidence": 0.95,
                    }
                )
                track_id += 1
        return players

    frames = [
        {"frameId": 0, "timestamp": 0.0, "ball": None, "myTeam": make_players([1, 4, 4, 2]), "enemies": []},
        {"frameId": 1, "timestamp": 0.2, "ball": None, "myTeam": make_players([1, 4, 4, 2]), "enemies": []},
        {"frameId": 2, "timestamp": 0.4, "ball": None, "myTeam": make_players([1, 4, 4, 2]), "enemies": []},
        {"frameId": 3, "timestamp": 0.6, "ball": None, "myTeam": make_players([1, 4, 3, 3]), "enemies": []},
        {"frameId": 4, "timestamp": 0.8, "ball": None, "myTeam": make_players([1, 4, 3, 3]), "enemies": []},
        {"frameId": 5, "timestamp": 1.0, "ball": None, "myTeam": make_players([1, 4, 3, 3]), "enemies": []},
    ]

    timeline = build_formation_timeline(frames, window_size=3)

    assert [segment.formation for segment in timeline] == ["4-4-2", "4-3-3"]
    assert timeline[0].startFrameId == 0
    assert timeline[0].endFrameId >= 2
    assert timeline[1].startFrameId >= timeline[0].endFrameId


def test_summarize_match_uses_dominant_windowed_formation_instead_of_last_frame():
    def make_players(rows: list[int]) -> list[dict]:
        players: list[dict] = []
        track_id = 1
        for row_index, row_count in enumerate(rows):
            for column in range(row_count):
                players.append(
                    {
                        "id": track_id,
                        "x": 6 + row_index * 20 + column,
                        "y": 15 + column * 10,
                        "confidence": 0.95,
                    }
                )
                track_id += 1
        return players

    frames = [
        {"frameId": 0, "timestamp": 0.0, "ball": None, "myTeam": make_players([1, 4, 4, 2]), "enemies": []},
        {"frameId": 1, "timestamp": 0.2, "ball": None, "myTeam": make_players([1, 4, 4, 2]), "enemies": []},
        {"frameId": 2, "timestamp": 0.4, "ball": None, "myTeam": make_players([1, 4, 4, 2]), "enemies": []},
        {"frameId": 3, "timestamp": 0.6, "ball": None, "myTeam": make_players([1, 3, 4, 3]), "enemies": []},
    ]

    summary = summarize_match(frames, [])

    assert summary.formation == "4-4-2"


def test_summarize_match_does_not_publish_a_single_last_frame_as_formation():
    def make_players(rows: list[int]) -> list[dict]:
        players: list[dict] = []
        track_id = 1
        for row_index, row_count in enumerate(rows):
            for column in range(row_count):
                players.append(
                    {
                        "id": track_id,
                        "x": 6 + row_index * 20 + column,
                        "y": 15 + column * 10,
                        "confidence": 0.95,
                    }
                )
                track_id += 1
        return players

    frames = [
        {"frameId": 0, "timestamp": 0.0, "ball": None, "myTeam": [{"id": 1, "x": 10.0, "y": 50.0, "confidence": 0.9}], "enemies": []},
        {"frameId": 1, "timestamp": 0.2, "ball": None, "myTeam": [{"id": 1, "x": 10.0, "y": 50.0, "confidence": 0.9}], "enemies": []},
        {"frameId": 2, "timestamp": 0.4, "ball": None, "myTeam": make_players([1, 4, 4, 2]), "enemies": []},
    ]

    summary = summarize_match(frames, [])

    assert summary.formation is None


def test_summarize_match_does_not_invent_midfield_average_without_players():
    frames = [
        {"frameId": 0, "timestamp": 0.0, "ball": None, "myTeam": [], "enemies": []},
    ]

    summary = summarize_match(frames, [])

    assert summary.myTeamAvgPos is None
    assert summary.enemyAvgPos is None


def test_summarize_match_does_not_publish_zero_experimental_shot_quality_without_labelled_shots():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 50.0, "y": 50.0, "confidence": 0.9},
            "myTeam": [{"id": 1, "x": 40.0, "y": 50.0, "confidence": 0.9}],
            "enemies": [{"id": 11, "x": 60.0, "y": 50.0, "confidence": 0.9}],
        }
    ]

    summary = summarize_match(frames, [])

    assert summary.myTeamXg is None
    assert summary.enemyXg is None
    shot_quality = next(item for item in summary.metricAvailability if item.metric == "experimental_shot_quality")
    assert shot_quality.value is None
    assert shot_quality.availability != "experimental"


def test_build_shot_analytics_scores_central_box_shots_higher_than_wide_efforts():
    frames = [
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 91.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 9, "x": 90.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [],
        },
        {
            "frameId": 8,
            "timestamp": 1.6,
            "ball": {"x": 28.0, "y": 8.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [{"id": 4, "x": 28.0, "y": 8.0, "confidence": 0.92}],
        },
    ]
    events = [
        {"type": "shot", "frameId": 2, "timestamp": 0.4, "team": "my_team", "fromTrackId": 9, "description": "Shot attempted"},
        {"type": "shot", "frameId": 8, "timestamp": 1.6, "team": "enemy", "fromTrackId": 4, "description": "Shot attempted"},
    ]

    shots = build_shot_analytics(frames, events)
    summary = summarize_match(frames, [], shots)

    assert len(shots) == 2
    assert shots[0].team == "my_team"
    assert shots[0].inBox is True
    assert shots[0].xg > shots[1].xg
    assert summary.myTeamXg == shots[0].xg
    assert summary.enemyXg == shots[1].xg


def test_summarize_match_tracks_defensive_line_height_and_team_length_out_of_possession():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 70.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 1, "x": 4.0, "y": 50.0, "confidence": 0.9},
                {"id": 2, "x": 18.0, "y": 20.0, "confidence": 0.9},
                {"id": 3, "x": 20.0, "y": 35.0, "confidence": 0.9},
                {"id": 4, "x": 22.0, "y": 50.0, "confidence": 0.9},
                {"id": 5, "x": 24.0, "y": 65.0, "confidence": 0.9},
                {"id": 6, "x": 55.0, "y": 45.0, "confidence": 0.9},
            ],
            "enemies": [
                {"id": 11, "x": 96.0, "y": 50.0, "confidence": 0.9},
                {"id": 12, "x": 70.0, "y": 22.0, "confidence": 0.9},
                {"id": 13, "x": 72.0, "y": 38.0, "confidence": 0.9},
                {"id": 14, "x": 74.0, "y": 52.0, "confidence": 0.9},
                {"id": 15, "x": 76.0, "y": 66.0, "confidence": 0.9},
                {"id": 16, "x": 35.0, "y": 48.0, "confidence": 0.9},
            ],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 30.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 1, "x": 4.0, "y": 50.0, "confidence": 0.9},
                {"id": 2, "x": 18.0, "y": 20.0, "confidence": 0.9},
                {"id": 3, "x": 20.0, "y": 35.0, "confidence": 0.9},
                {"id": 4, "x": 22.0, "y": 50.0, "confidence": 0.9},
                {"id": 5, "x": 24.0, "y": 65.0, "confidence": 0.9},
                {"id": 6, "x": 55.0, "y": 45.0, "confidence": 0.9},
            ],
            "enemies": [
                {"id": 11, "x": 96.0, "y": 50.0, "confidence": 0.9},
                {"id": 12, "x": 70.0, "y": 22.0, "confidence": 0.9},
                {"id": 13, "x": 72.0, "y": 38.0, "confidence": 0.9},
                {"id": 14, "x": 74.0, "y": 52.0, "confidence": 0.9},
                {"id": 15, "x": 76.0, "y": 66.0, "confidence": 0.9},
                {"id": 16, "x": 35.0, "y": 48.0, "confidence": 0.9},
            ],
        },
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="enemy", trackId=12, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="my_team", trackId=6, distance=1.0),
    ]

    summary = summarize_match(frames, assignments)

    assert summary.myTeamDefensiveLineHeight == 21.0
    assert summary.myTeamDefensiveTeamLength == 37.0
    assert summary.enemyDefensiveLineHeight == 27.0
    assert summary.enemyDefensiveTeamLength == 41.0


def test_summarize_match_tracks_pressing_metrics_from_events_and_quick_regains():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 82.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 70.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 20, "x": 82.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 78.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 71.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 21, "x": 78.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 75.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 72.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 22, "x": 75.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 3,
            "timestamp": 0.6,
            "ball": {"x": 73.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 73.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 22, "x": 76.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 4,
            "timestamp": 0.8,
            "ball": {"x": 71.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 71.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 18, "x": 69.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 5,
            "timestamp": 1.0,
            "ball": None,
            "myTeam": [{"id": 7, "x": 69.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 18, "x": 70.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 6,
            "timestamp": 1.2,
            "ball": {"x": 68.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 8, "x": 68.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 18, "x": 70.0, "y": 48.0, "confidence": 0.9}],
        },
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="enemy", trackId=20, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="enemy", trackId=21, distance=1.0),
        BallOwnership(frameId=2, timestamp=0.4, team="enemy", trackId=22, distance=1.0),
        BallOwnership(frameId=3, timestamp=0.6, team="my_team", trackId=7, distance=1.0),
        BallOwnership(frameId=4, timestamp=0.8, team="enemy", trackId=18, distance=1.0),
        BallOwnership(frameId=5, timestamp=1.0, team="dead_ball", trackId=None, distance=None),
        BallOwnership(frameId=6, timestamp=1.2, team="my_team", trackId=8, distance=1.0),
    ]
    events = [
        {"type": "pass", "frameId": 1, "timestamp": 0.2, "team": "enemy", "fromTrackId": 20, "toTrackId": 21, "description": "Pass"},
        {"type": "pass", "frameId": 2, "timestamp": 0.4, "team": "enemy", "fromTrackId": 21, "toTrackId": 22, "description": "Pass"},
        {"type": "turnover", "frameId": 3, "timestamp": 0.6, "team": "my_team", "toTrackId": 7, "description": "Turnover won"},
        {"type": "turnover", "frameId": 4, "timestamp": 0.8, "team": "enemy", "toTrackId": 18, "description": "Turnover won"},
        {"type": "recovery", "frameId": 6, "timestamp": 1.2, "team": "my_team", "toTrackId": 8, "description": "Recovery"},
    ]

    summary = summarize_match(frames, assignments, events=events)

    assert summary.myTeamPpda == 1.0
    assert summary.enemyPpda is None
    assert summary.myTeamHighPressRegains == 2
    assert summary.enemyHighPressRegains == 0
    assert summary.myTeamCounterpressRecoverySeconds == 0.4
    assert summary.enemyCounterpressRecoverySeconds == 0.2


def test_classify_block_height():
    from backend.app.analytics import _classify_block_height
    
    # Low block: defensive line < 35m
    assert _classify_block_height(25.0) == "low_block"
    assert _classify_block_height(30.0) == "low_block"
    
    # Mid block: defensive line 35-50m
    assert _classify_block_height(35.0) == "mid_block"
    assert _classify_block_height(40.0) == "mid_block"
    assert _classify_block_height(50.0) == "mid_block"
    
    # High block: defensive line > 50m
    assert _classify_block_height(55.0) == "high_block"
    assert _classify_block_height(65.0) == "high_block"


def test_pitch_zone():
    from backend.app.analytics import _pitch_zone
    
    # My team perspective
    assert _pitch_zone(20.0, "my_team") == "defensive_third"
    assert _pitch_zone(50.0, "my_team") == "middle_third"
    assert _pitch_zone(80.0, "my_team") == "attacking_third"
    
    # Enemy perspective
    assert _pitch_zone(80.0, "enemy") == "defensive_third"
    assert _pitch_zone(50.0, "enemy") == "middle_third"
    assert _pitch_zone(20.0, "enemy") == "attacking_third"


def test_summarize_match_includes_defensive_context():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 50.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [
                {"id": 1, "x": 25.0, "y": 34.0, "confidence": 0.9},
                {"id": 2, "x": 25.0, "y": 50.0, "confidence": 0.9},
                {"id": 3, "x": 25.0, "y": 66.0, "confidence": 0.9},
                {"id": 4, "x": 35.0, "y": 34.0, "confidence": 0.9},
                {"id": 5, "x": 35.0, "y": 50.0, "confidence": 0.9},
            ],
            "enemies": [
                {"id": 10, "x": 75.0, "y": 34.0, "confidence": 0.9},
                {"id": 11, "x": 75.0, "y": 50.0, "confidence": 0.9},
                {"id": 12, "x": 75.0, "y": 66.0, "confidence": 0.9},
                {"id": 13, "x": 65.0, "y": 34.0, "confidence": 0.9},
                {"id": 14, "x": 65.0, "y": 50.0, "confidence": 0.9},
            ],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 45.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [
                {"id": 1, "x": 28.0, "y": 34.0, "confidence": 0.9},
                {"id": 2, "x": 28.0, "y": 50.0, "confidence": 0.9},
                {"id": 3, "x": 28.0, "y": 66.0, "confidence": 0.9},
                {"id": 4, "x": 38.0, "y": 34.0, "confidence": 0.9},
                {"id": 5, "x": 38.0, "y": 50.0, "confidence": 0.9},
            ],
            "enemies": [
                {"id": 10, "x": 72.0, "y": 34.0, "confidence": 0.9},
                {"id": 11, "x": 72.0, "y": 50.0, "confidence": 0.9},
                {"id": 12, "x": 72.0, "y": 66.0, "confidence": 0.9},
                {"id": 13, "x": 62.0, "y": 34.0, "confidence": 0.9},
                {"id": 14, "x": 62.0, "y": 50.0, "confidence": 0.9},
            ],
        },
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=1, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="enemy", trackId=10, distance=1.0),
    ]
    events = [
        {"type": "turnover", "frameId": 1, "timestamp": 0.2, "team": "enemy", "toTrackId": 10, "description": "Turnover"},
        {"type": "recovery", "frameId": 1, "timestamp": 0.2, "team": "my_team", "toTrackId": 5, "description": "Recovery"},
    ]

    summary = summarize_match(frames, assignments, events=events)

    # Block height classifications should exist and be valid values
    assert summary.myTeamBlockHeight in ["low_block", "mid_block", "high_block"]
    assert summary.enemyBlockHeight in ["low_block", "mid_block", "high_block"]
    
    # Regain zones should exist and have all three zones
    assert "defensive_third" in summary.myTeamRegainZones
    assert "middle_third" in summary.myTeamRegainZones
    assert "attacking_third" in summary.myTeamRegainZones
    assert "defensive_third" in summary.enemyRegainZones
    assert "middle_third" in summary.enemyRegainZones
    assert "attacking_third" in summary.enemyRegainZones
    
    if summary.myTeamTransitionExposure is not None:
        assert summary.myTeamTransitionExposure >= 0
    if summary.enemyTransitionExposure is not None:
        assert summary.enemyTransitionExposure >= 0


def _metric(summary, name: str):
    return next(item for item in summary.metricAvailability if item.metric == name)


def test_summarize_match_marks_ppda_unknown_when_pressing_denominator_is_zero():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 50.0, "y": 50.0, "confidence": 0.9},
            "myTeam": [{"id": 1, "x": 40.0, "y": 50.0, "confidence": 0.9}],
            "enemies": [{"id": 11, "x": 60.0, "y": 50.0, "confidence": 0.9}],
        }
    ]
    assignments = [BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=1, distance=1.0)]

    summary = summarize_match(frames, assignments, events=[])

    my_ppda = _metric(summary, "my_team_ppda")
    enemy_ppda = _metric(summary, "enemy_ppda")
    assert my_ppda.availability == "unknown"
    assert my_ppda.value is None
    assert "ZERO_DENOMINATOR" in my_ppda.reasonCodes
    assert my_ppda.published_value() is None
    assert enemy_ppda.availability == "unknown"
    assert summary.myTeamPpda is None
    assert summary.enemyPpda is None
    assert summary.myTeamCounterpressRecoverySeconds is None
    assert summary.enemyCounterpressRecoverySeconds is None
    assert summary.myTeamDefensiveLineHeight is None
    assert summary.enemyDefensiveLineHeight is None
    assert summary.myTeamDefensiveTeamLength is None
    assert summary.enemyDefensiveTeamLength is None
    assert summary.myTeamBlockHeight is None
    assert summary.enemyBlockHeight is None
    assert summary.myTeamTransitionExposure is None
    assert summary.enemyTransitionExposure is None
    assert summary.myTeamHighPressRegains is None
    assert summary.enemyHighPressRegains is None
    assert summary.myTeamRegainZones is None
    assert summary.enemyRegainZones is None
    shot_quality = _metric(summary, "experimental_shot_quality")
    assert shot_quality.availability == "unknown"
    assert shot_quality.value is None
    assert shot_quality.publishedLabel == "experimental_shot_quality"


def test_summarize_match_keeps_measured_ppda_and_withholds_physical_totals_by_default():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 82.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 70.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 20, "x": 82.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 78.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 71.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 21, "x": 78.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 75.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 72.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 22, "x": 75.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 3,
            "timestamp": 0.6,
            "ball": {"x": 73.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 73.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 22, "x": 76.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 4,
            "timestamp": 0.8,
            "ball": {"x": 71.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 7, "x": 71.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 18, "x": 69.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 5,
            "timestamp": 1.0,
            "ball": None,
            "myTeam": [{"id": 7, "x": 69.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 18, "x": 70.0, "y": 48.0, "confidence": 0.9}],
        },
        {
            "frameId": 6,
            "timestamp": 1.2,
            "ball": {"x": 68.0, "y": 48.0, "confidence": 0.95},
            "myTeam": [{"id": 8, "x": 68.0, "y": 48.0, "confidence": 0.9}],
            "enemies": [{"id": 18, "x": 70.0, "y": 48.0, "confidence": 0.9}],
        },
    ]
    assignments = [
        BallOwnership(frameId=0, timestamp=0.0, team="enemy", trackId=20, distance=1.0),
        BallOwnership(frameId=1, timestamp=0.2, team="enemy", trackId=21, distance=1.0),
        BallOwnership(frameId=2, timestamp=0.4, team="enemy", trackId=22, distance=1.0),
        BallOwnership(frameId=3, timestamp=0.6, team="my_team", trackId=7, distance=1.0),
        BallOwnership(frameId=4, timestamp=0.8, team="enemy", trackId=18, distance=1.0),
        BallOwnership(frameId=5, timestamp=1.0, team="dead_ball", trackId=None, distance=None),
        BallOwnership(frameId=6, timestamp=1.2, team="my_team", trackId=8, distance=1.0),
    ]
    events = [
        {"type": "pass", "frameId": 1, "timestamp": 0.2, "team": "enemy", "fromTrackId": 20, "toTrackId": 21, "description": "Pass"},
        {"type": "pass", "frameId": 2, "timestamp": 0.4, "team": "enemy", "fromTrackId": 21, "toTrackId": 22, "description": "Pass"},
        {"type": "turnover", "frameId": 3, "timestamp": 0.6, "team": "my_team", "toTrackId": 7, "description": "Turnover won"},
        {"type": "turnover", "frameId": 4, "timestamp": 0.8, "team": "enemy", "toTrackId": 18, "description": "Turnover won"},
        {"type": "recovery", "frameId": 6, "timestamp": 1.2, "team": "my_team", "toTrackId": 8, "description": "Recovery"},
    ]

    summary = summarize_match(frames, assignments, events=events)
    my_ppda = _metric(summary, "my_team_ppda")
    assert my_ppda.availability == "experimental"
    assert my_ppda.value == 1.0
    distance = _metric(summary, "my_team_distance_m")
    assert distance.availability in {"unknown", "withheld"}
    assert distance.published_value() is None


def test_event_x_stays_unknown_without_a_source_position() -> None:
    event = DetectedEvent(
        type="recovery",
        frameId=9,
        timestamp=1.8,
        team="my_team",
        toTrackId=7,
        description="missing frame",
    )
    assert _get_event_x(event, {}) is None
    empty = FrameData.model_validate({"frameId": 0, "timestamp": 0.0, "myTeam": [], "enemies": []})
    assert _get_event_x(event.model_copy(update={"frameId": 0}), {0: empty}) is None
