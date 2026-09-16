from __future__ import annotations

from backend.app.trust_crops import (
    compute_trust_crops,
)


def _frame(frame_id: int, ball_x: float | None = 50.0, ball_y: float = 30.0) -> dict:
    return {"frameId": frame_id, "timestamp": frame_id * 0.04, "ball": {"x": ball_x, "y": ball_y} if ball_x is not None else None}


def _assignment(frame_id: int, team: str, track_id: int | None) -> dict:
    return {"frameId": frame_id, "team": team, "trackId": track_id}


class TestComputeTrustCrops:
    def test_empty_frames_returns_empty(self) -> None:
        assert compute_trust_crops([], []) == []

    def test_frames_only_returns_empty(self) -> None:
        frames = [_frame(0), _frame(1)]
        assert compute_trust_crops(frames, []) == []

    def test_assignments_only_returns_empty(self) -> None:
        assignments = [_assignment(0, "my_team", 1), _assignment(1, "my_team", 1)]
        assert compute_trust_crops([], assignments) == []

    def test_ball_teleport_flagged(self) -> None:
        # Frame 0: ball at (0, 0) → Frame 1: ball at (100, 0) = 100m teleport
        frames = [_frame(0, 0.0, 0.0), _frame(1, 100.0, 0.0), _frame(2, 100.0, 0.0)]
        assignments = [_assignment(0, "my_team", 1), _assignment(1, "my_team", 1), _assignment(2, "my_team", 1)]
        crops = compute_trust_crops(frames, assignments)
        assert len(crops) > 0
        assert "ball_teleport" in crops[0].reasons

    def test_track_switches_flagged(self) -> None:
        frames = [_frame(i) for i in range(40)]
        assignments = [
            _assignment(i, "my_team", i % 2) for i in range(40)
        ]  # Alternating track IDs = many switches
        crops = compute_trust_crops(frames, assignments)
        assert len(crops) > 0
        assert "track_switches" in crops[0].reasons

    def test_team_flips_flagged(self) -> None:
        frames = [_frame(i) for i in range(50)]
        # Rapid team alternation: my_team → enemy → my_team → ...
        assignments = [_assignment(i, "my_team" if i % 2 == 0 else "enemy", 1) for i in range(50)]
        crops = compute_trust_crops(frames, assignments)
        assert len(crops) > 0
        assert "team_flips" in crops[0].reasons

    def test_possession_gap_flagged(self) -> None:
        frames = [_frame(i) for i in range(50)]
        # First 10 frames: team possession, then 25 frames unassigned = possession gap
        assignments = (
            [_assignment(i, "my_team", 1) for i in range(10)]
            + [_assignment(i, "unassigned", None) for i in range(10, 35)]
            + [_assignment(i, "my_team", 1) for i in range(35, 50)]
        )
        crops = compute_trust_crops(frames, assignments)
        assert len(crops) > 0
        assert "possession_gap" in crops[0].reasons

    def test_all_uncontrolled_match_flags_terminal_possession_gap(self) -> None:
        frames = [_frame(i) for i in range(25)]
        assignments = [_assignment(i, "unassigned", None) for i in range(25)]

        crops = compute_trust_crops(frames, assignments)

        assert crops
        assert "possession_gap" in crops[0].reasons

    def test_controlled_prefix_flags_terminal_possession_gap(self) -> None:
        frames = [_frame(i) for i in range(35)]
        assignments = (
            [_assignment(i, "my_team", 1) for i in range(10)]
            + [_assignment(i, "dead_ball", None) for i in range(10, 35)]
        )

        crops = compute_trust_crops(frames, assignments)

        assert crops
        assert "possession_gap" in crops[0].reasons

    def test_max_crops_respected(self) -> None:
        frames = [_frame(i) for i in range(100)]
        # Trigger all heuristics everywhere
        assignments = [_assignment(i, "my_team" if i % 2 == 0 else "enemy", i % 3) for i in range(100)]
        crops = compute_trust_crops(frames, assignments, max_crops=5)
        assert len(crops) <= 5

    def test_scores_sorted_descending(self) -> None:
        frames = [_frame(i) for i in range(100)]
        assignments = [_assignment(i, "my_team" if i % 2 == 0 else "enemy", i % 2) for i in range(100)]
        crops = compute_trust_crops(frames, assignments)
        if len(crops) >= 2:
            assert crops[0].score >= crops[1].score

    def test_frame_ids_in_crops(self) -> None:
        # Trigger a high score near frame 25
        frames = [_frame(i) for i in range(50)]
        # Multiple teleports to push score above threshold
        frames[5] = _frame(5, 100.0, 0.0)
        frames[6] = _frame(6, 100.0, 0.0)
        assignments = [_assignment(i, "my_team", 1) for i in range(50)]
        crops = compute_trust_crops(frames, assignments)
        if crops:
            crop = crops[0]
            assert crop.frameStart <= crop.frameEnd
            assert crop.timestampStart <= crop.timestampEnd

    def test_no_false_positives_clean_data(self) -> None:
        frames = [_frame(i, 50.0, 30.0) for i in range(50)]
        assignments = [_assignment(i, "my_team", 1) for i in range(50)]
        crops = compute_trust_crops(frames, assignments)
        assert crops == []

    def test_missing_ball_handled_gracefully(self) -> None:
        frames = [{"frameId": 0, "timestamp": 0.0, "ball": None}, {"frameId": 1, "timestamp": 0.04, "ball": {"x": 100.0, "y": 0.0}}]
        assignments = [_assignment(0, "my_team", 1), _assignment(1, "my_team", 1)]
        # Should not raise — missing ball in prev frame is skipped
        crops = compute_trust_crops(frames, assignments)
        assert isinstance(crops, list)
