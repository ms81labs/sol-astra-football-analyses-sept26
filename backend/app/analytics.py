from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace
from itertools import chain
from math import atan2, degrees, pi, sqrt
from typing import Protocol, runtime_checkable

from .schemas import BallData, BallEstimate, BallOwnership, DetectedEvent, FormationSegment, FrameData, MatchStateFrame, MatchSummary, MetricAvailabilityRecord, PlayerData, ShotAnalytics
from .workbench.metric_definitions import (
    METRIC_DEFINITIONS,
    MIN_VISIBLE_DEFENDERS_FOR_LINE_BREAK,
    MIN_VISIBLE_PLAYERS_FOR_DEFENSIVE_LINE,
)

PITCH_LENGTH_M = 105
PITCH_WIDTH_M = 68
FORMATION_MAX_GAP_S = 2.0
MAX_OWNER_DISTANCE = 12.0
CONTINUITY_DISTANCE = 3.5
MAX_DEAD_BALL_BRIDGE_SECONDS = 1.0
CONTROLLED_TEAMS = {"my_team", "enemy"}
PLAYER_CONTROL_TEAMS = {"my_team", "enemy", "unassigned"}
LOOSE_BALL_STATES = {"contested", "dead_ball", "unassigned"}
MAX_NEUTRAL_CARRY_GAP_SECONDS = 1.0
MIN_NEUTRAL_CARRY_PROGRESS = 6.0
MIN_CONTROLLED_CARRY_PROGRESS = 6.0
MAX_STATIC_NEUTRAL_RECOVERY_GAP_SECONDS = 6.0
MAX_STATIC_NEUTRAL_BALL_DISPLACEMENT = 1.5
MATCH_STATE_CONTINUITY_MAX_NEIGHBOR_FRAMES = 2
MATCH_STATE_CONTINUITY_ELIGIBLE_BASELINE_TEAMS = {"unassigned", "contested", "dead_ball"}


@dataclass
class OwnershipSegment:
    startIndex: int
    endIndex: int
    start: BallOwnership
    end: BallOwnership


def _oriented_frames(frames: list[FrameData], attack_direction: str) -> list[FrameData]:
    """Give directional analytics a left-to-right view without changing display data."""
    if attack_direction == "left_to_right":
        return frames
    if attack_direction != "right_to_left":
        raise ValueError("Unsupported attack direction")
    return [frame.model_copy(update={
        **{field: [replace(player, x=100 - player.x) for player in getattr(frame, field)]
           for field in ("myTeam", "enemies", "unassignedPlayers")},
        "ball": frame.ball.model_copy(update={"x": 100 - frame.ball.x}) if frame.ball else None,
    }) for frame in frames]


def _distance_value(distance: float | None) -> float:
    return MAX_OWNER_DISTANCE + 1 if distance is None else distance


def _build_segments(assignments: list[BallOwnership]) -> list[OwnershipSegment]:
    if not assignments:
        return []

    segments: list[OwnershipSegment] = []
    start_index = 0
    for index in range(1, len(assignments)):
        previous = assignments[index - 1]
        current = assignments[index]
        if current.team == previous.team and current.trackId == previous.trackId:
            continue
        segments.append(
            OwnershipSegment(
                startIndex=start_index,
                endIndex=index - 1,
                start=assignments[start_index],
                end=assignments[index - 1],
            )
        )
        start_index = index

    segments.append(
        OwnershipSegment(
            startIndex=start_index,
            endIndex=len(assignments) - 1,
            start=assignments[start_index],
            end=assignments[-1],
        )
    )
    return segments


def _bridge_short_dead_ball_gaps(assignments: list[BallOwnership]) -> list[BallOwnership]:
    if not assignments:
        return assignments

    bridged = list(assignments)
    segments = _build_segments(assignments)
    for index, segment in enumerate(segments[1:-1], start=1):
        if segment.start.team != "dead_ball":
            continue

        previous_segment = segments[index - 1]
        next_segment = segments[index + 1]
        if (
            previous_segment.end.team != "unassigned"
            or next_segment.start.team != "unassigned"
            or previous_segment.end.trackId is None
            or previous_segment.end.trackId != next_segment.start.trackId
        ):
            continue

        gap_seconds = next_segment.start.timestamp - previous_segment.end.timestamp
        if gap_seconds > MAX_DEAD_BALL_BRIDGE_SECONDS:
            continue

        fill_distance = next_segment.start.distance if next_segment.start.distance is not None else previous_segment.end.distance
        for assignment_index in range(segment.startIndex, segment.endIndex + 1):
            current = bridged[assignment_index]
            bridged[assignment_index] = current.model_copy(
                update={
                    "team": previous_segment.end.team,
                    "trackId": previous_segment.end.trackId,
                    "distance": fill_distance,
                }
            )

    return bridged


def _lookup_player_position(frame: FrameData | None, team: str | None, track_id: int | None) -> tuple[float, float] | None:
    if frame is None or track_id is None:
        return None
    if team == "my_team":
        player = next((player for player in frame.myTeam if player.id == track_id), None)
    elif team == "enemy":
        player = next((player for player in frame.enemies if player.id == track_id), None)
    elif team == "unassigned":
        player = next((player for player in frame.unassignedPlayers if player.id == track_id), None)
    else:
        return None
    if player is None:
        return None
    return (player.x, player.y)


def _is_attacking_wide(team: str, position: tuple[float, float]) -> bool:
    x, y = position
    if team == "my_team":
        return x >= 65 and (y <= 18 or y >= 82)
    return x <= 35 and (y <= 18 or y >= 82)


def _is_attacking_box(team: str, position: tuple[float, float]) -> bool:
    x, y = position
    if team == "my_team":
        return x >= 82 and 18 <= y <= 82
    return x <= 18 and 18 <= y <= 82


def _is_shooting_zone(team: str, position: tuple[float, float]) -> bool:
    x, y = position
    if team == "my_team":
        return x >= 84 and 24 <= y <= 76
    return x <= 16 and 24 <= y <= 76


def _is_forward_progression(team: str, start_x: float, end_x: float, minimum_progress: float = 12.0) -> bool:
    if team == "my_team":
        return (end_x - start_x) >= minimum_progress
    return (start_x - end_x) >= minimum_progress


def _is_neutral_progression(start_x: float, end_x: float, minimum_progress: float = MIN_NEUTRAL_CARRY_PROGRESS) -> bool:
    return (end_x - start_x) >= minimum_progress


def _segment_forward_progression(team: str, start_x: float, end_x: float, minimum_progress: float = MIN_CONTROLLED_CARRY_PROGRESS) -> bool:
    return _is_forward_progression(team, start_x, end_x, minimum_progress=minimum_progress)


def _ball_displacement(start_ball: BallData | None, end_ball: BallData | None) -> float | None:
    if start_ball is None or end_ball is None:
        return None
    return sqrt((end_ball.x - start_ball.x) ** 2 + (end_ball.y - start_ball.y) ** 2)


def _is_advanced_target(team: str, x: float) -> bool:
    if team == "my_team":
        return x >= 70
    return x <= 30


def _count_broken_lines(team: str, passer_x: float, receiver_x: float, opponents: list[PlayerData]) -> int:
    lower, upper = sorted((passer_x, receiver_x))
    return sum(1 for player in opponents if lower < player.x < upper)


def _pitch_position_to_meters(x: float, y: float) -> tuple[float, float]:
    return ((x / 100) * PITCH_LENGTH_M, (y / 100) * PITCH_WIDTH_M)


def _goal_geometry(team: str) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    half_goal_width = 7.32 / 2
    if team == "my_team":
        center: tuple[float, float] = (PITCH_LENGTH_M, PITCH_WIDTH_M / 2)
        top_post: tuple[float, float] = (PITCH_LENGTH_M, (PITCH_WIDTH_M / 2) - half_goal_width)
        bottom_post: tuple[float, float] = (PITCH_LENGTH_M, (PITCH_WIDTH_M / 2) + half_goal_width)
        return center, top_post, bottom_post
    center = (0.0, PITCH_WIDTH_M / 2)
    top_post = (0.0, (PITCH_WIDTH_M / 2) - half_goal_width)
    bottom_post = (0.0, (PITCH_WIDTH_M / 2) + half_goal_width)
    return center, top_post, bottom_post


def _shot_distance_to_goal_m(team: str, position: tuple[float, float]) -> float:
    shot_x, shot_y = _pitch_position_to_meters(*position)
    goal_center, _, _ = _goal_geometry(team)
    return sqrt((goal_center[0] - shot_x) ** 2 + (goal_center[1] - shot_y) ** 2)


def _shot_angle_degrees(team: str, position: tuple[float, float]) -> float:
    shot_x, shot_y = _pitch_position_to_meters(*position)
    _, top_post, bottom_post = _goal_geometry(team)
    angle_top = atan2(top_post[1] - shot_y, top_post[0] - shot_x)
    angle_bottom = atan2(bottom_post[1] - shot_y, bottom_post[0] - shot_x)
    angle = abs(angle_bottom - angle_top)
    if angle > pi:
        angle = (2 * pi) - angle
    return degrees(angle)


def _estimate_shot_xg(team: str, position: tuple[float, float]) -> tuple[float, float, float, bool]:
    distance_to_goal = _shot_distance_to_goal_m(team, position)
    angle_degrees = _shot_angle_degrees(team, position)
    in_box = _is_attacking_box(team, position)
    distance_factor = max(0.0, 1.0 - min(distance_to_goal, 35.0) / 35.0)
    angle_factor = min(angle_degrees / 35.0, 1.0)
    close_range_bonus = 0.08 if distance_to_goal <= 12.0 else 0.0
    xg = 0.02 + (0.30 * distance_factor) + (0.28 * angle_factor) + (0.12 if in_box else 0.0) + close_range_bonus
    return round(min(max(xg, 0.02), 0.95), 2), round(distance_to_goal, 1), round(angle_degrees, 1), in_box


def _summarize_defensive_shape(
    frames: list[FrameData],
    assignments: list[BallOwnership],
) -> tuple[float | None, float | None, float | None, float | None]:
    accumulators = {
        "my_team": {"line_height": 0.0, "team_length": 0.0, "count": 0},
        "enemy": {"line_height": 0.0, "team_length": 0.0, "count": 0},
    }

    for frame, assignment in zip(frames, assignments, strict=False):
        defending_team = "my_team" if assignment.team == "enemy" else "enemy" if assignment.team == "my_team" else None
        if defending_team is None:
            continue

        players = frame.myTeam if defending_team == "my_team" else frame.enemies
        if len(players) < MIN_VISIBLE_PLAYERS_FOR_DEFENSIVE_LINE:
            continue

        sorted_players = sorted(players, key=lambda player: player.x, reverse=defending_team == "enemy")
        outfield_players = sorted_players[1:] if len(sorted_players) >= 5 else sorted_players
        if len(outfield_players) < 4:
            continue

        defensive_line = outfield_players[:4]
        average_raw_x = sum(player.x for player in defensive_line) / len(defensive_line)
        line_height = average_raw_x if defending_team == "my_team" else 100 - average_raw_x
        outfield_x_values = [player.x for player in outfield_players]
        team_length = max(outfield_x_values) - min(outfield_x_values)

        accumulators[defending_team]["line_height"] += line_height
        accumulators[defending_team]["team_length"] += team_length
        accumulators[defending_team]["count"] += 1

    def average(team: str, metric: str) -> float | None:
        count = accumulators[team]["count"]
        if count == 0:
            return None
        return round(accumulators[team][metric] / count, 1)

    return (
        average("my_team", "line_height"),
        average("enemy", "line_height"),
        average("my_team", "team_length"),
        average("enemy", "team_length"),
    )


def _is_pressing_zone(team: str, x: float) -> bool:
    if team == "my_team":
        return x >= 60
    return x <= 40


def _pressing_event_position(
    event: DetectedEvent,
    frame_by_id: dict[int, FrameData],
) -> tuple[float, float] | None:
    """Resolve the original sender/receiver preference within the event's frame."""
    frame = frame_by_id.get(event.frameId)
    if frame is None or event.team is None or event.team not in CONTROLLED_TEAMS:
        return None

    if event.type == "pass":
        candidate_track_ids = [event.fromTrackId, event.toTrackId]
    else:
        candidate_track_ids = [event.toTrackId, event.fromTrackId]

    for track_id in candidate_track_ids:
        position = _lookup_player_position(frame, event.team, track_id)
        if position is not None:
            return position
    return None


def _count_pressing_events(
    events: list[DetectedEvent],
    frame_by_id: dict[int, FrameData],
    regain_types: set[str],
) -> tuple[dict[str, int], dict[str, int], dict[str, bool]]:
    """Count passes and regains while retaining observed-zero versus unknown."""
    teams = ("my_team", "enemy")
    passes_allowed = {team: 0 for team in teams}
    pressing_actions = {team: 0 for team in teams}
    observed_regain = {team: False for team in teams}
    for event in events:
        if event.team is None or event.team not in CONTROLLED_TEAMS:
            continue

        if event.type == "pass":
            position = _pressing_event_position(event, frame_by_id)
            if position is None:
                continue
            opponent = "my_team" if event.team == "enemy" else "enemy"
            if _is_pressing_zone(opponent, position[0]):
                passes_allowed[opponent] += 1
            continue

        if event.type in regain_types and event.toTrackId is not None:
            position = _pressing_event_position(event, frame_by_id)
            if position is None:
                continue
            observed_regain[event.team] = True
            if _is_pressing_zone(event.team, position[0]):
                pressing_actions[event.team] += 1
    return passes_allowed, pressing_actions, observed_regain


def _counterpress_recovery_samples(
    events: list[DetectedEvent],
    regain_types: set[str],
) -> dict[str, list[float]]:
    """Keep input order, the inclusive eight-second window, and first recovery."""
    samples: dict[str, list[float]] = {"my_team": [], "enemy": []}
    for index, event in enumerate(events):
        if event.type != "turnover" or event.team not in CONTROLLED_TEAMS:
            continue
        losing_team = "my_team" if event.team == "enemy" else "enemy"
        for follow_up in events[index + 1:]:
            if follow_up.timestamp - event.timestamp > 8.0:
                break
            if follow_up.team != losing_team or follow_up.type not in regain_types:
                continue
            samples[losing_team].append(round(follow_up.timestamp - event.timestamp, 1))
            break
    return samples


def _average_counterpress_recovery(samples: list[float]) -> float | None:
    if not samples:
        return None
    return round(sum(samples) / len(samples), 1)


def _summarize_pressing_metrics(
    frames: list[FrameData],
    events: list[DetectedEvent],
) -> tuple[float | None, float | None, int | None, int | None, float | None, float | None]:
    frame_by_id = {frame.frameId: frame for frame in frames}
    regain_types = {"turnover", "recovery", "tackle"}
    passes_allowed, pressing_actions, observed_regain = _count_pressing_events(
        events, frame_by_id, regain_types,
    )
    ppda = {
        team: round(passes_allowed[team] / pressing_actions[team], 1) if pressing_actions[team] > 0 else None
        for team in ("my_team", "enemy")
    }
    counterpress_samples = _counterpress_recovery_samples(events, regain_types)
    return (
        ppda["my_team"],
        ppda["enemy"],
        pressing_actions["my_team"] if observed_regain["my_team"] else None,
        pressing_actions["enemy"] if observed_regain["enemy"] else None,
        _average_counterpress_recovery(counterpress_samples["my_team"]),
        _average_counterpress_recovery(counterpress_samples["enemy"]),
    )


def _classify_block_height(defensive_line_height: float) -> str:
    """Classify block height based on defensive line position.
    
    - Low block: defensive line < 35m from own goal (x < 35 for my_team)
    - Mid block: defensive line 35-50m from own goal
    - High block: defensive line > 50m from own goal (x > 50 for my_team)
    """
    if defensive_line_height < 35:
        return "low_block"
    elif defensive_line_height > 50:
        return "high_block"
    return "mid_block"


def _pitch_zone(x: float, team: str | None) -> str:
    """Determine which third of the pitch a position is in.
    
    Pitch is divided into thirds:
    - Defensive third: x < 35 (my_team perspective) / x > 70 (enemy perspective)
    - Attacking third: x > 70 (my_team perspective) / x < 35 (enemy perspective)
    - Middle third: everything in between
    """
    if team == "my_team":
        if x < 35:
            return "defensive_third"
        elif x > 70:
            return "attacking_third"
    else:
        if x > 70:
            return "defensive_third"
        elif x < 35:
            return "attacking_third"
    return "middle_third"


def _summarize_regain_zones(
    events: list[DetectedEvent],
    frame_by_id: dict[int, FrameData],
    regain_types: set[str],
) -> tuple[dict[str, int] | None, dict[str, int] | None]:
    """Count located regains without conflating their fallback with exposure lookup."""
    my_team_regain_zones = {"defensive_third": 0, "middle_third": 0, "attacking_third": 0}
    enemy_regain_zones = {"defensive_third": 0, "middle_third": 0, "attacking_third": 0}
    observed_regain = {"my_team": False, "enemy": False}
    for event in events:
        if event.type not in regain_types or event.toTrackId is None:
            continue

        # Find position of the recovery/turnover
        position = None
        for track_id in [event.toTrackId, event.fromTrackId]:
            if track_id is not None:
                pos = _lookup_player_position(frame_by_id.get(event.frameId), event.team, track_id)
                if pos is not None:
                    position = pos
                    break

        if position is None:
            continue

        zone = _pitch_zone(position[0], event.team)

        if event.team == "my_team":
            my_team_regain_zones[zone] += 1
            observed_regain["my_team"] = True
        elif event.team == "enemy":
            enemy_regain_zones[zone] += 1
            observed_regain["enemy"] = True

    return (
        my_team_regain_zones if observed_regain["my_team"] else None,
        enemy_regain_zones if observed_regain["enemy"] else None,
    )


def _summarize_defensive_context(
    frames: list[FrameData],
    assignments: list[BallOwnership],
    events: list[DetectedEvent],
    my_team_defensive_line_height: float | None,
    enemy_defensive_line_height: float | None,
) -> tuple[str | None, str | None, dict[str, int] | None, dict[str, int] | None, float | None, float | None]:
    """Compute block height classification, regain zones, and transition exposure."""
    # Block height classification
    my_team_block_height = None if my_team_defensive_line_height is None else _classify_block_height(my_team_defensive_line_height)
    enemy_block_height = None if enemy_defensive_line_height is None else _classify_block_height(enemy_defensive_line_height)

    frame_by_id = {frame.frameId: frame for frame in frames}

    regain_types = {"recovery", "tackle", "turnover"}
    teams = ("my_team", "enemy")

    # Count turnovers faced (transitions where team lost ball)
    turnovers_faced = {team: 0 for team in teams}

    my_team_regain_zones, enemy_regain_zones = _summarize_regain_zones(
        events, frame_by_id, regain_types,
    )

    # Transition exposure: ratio of turnovers faced to high-press regains
    # Higher value = more vulnerable (facing turnovers without regaining high up)
    for event in events:
        if event.type == "turnover" and event.team in CONTROLLED_TEAMS:
            # Team that lost the ball "faces" a turnover
            losing_team = "my_team" if event.team == "enemy" else "enemy"
            turnovers_faced[losing_team] += 1

    # Calculate exposure ratio: turnovers faced / high-press regains
    # If no high-press regains but turnovers faced, exposure is high
    def calc_exposure(turnovers: int, high_press_regains: int) -> float | None:
        if high_press_regains == 0:
            return None
        return round(turnovers / high_press_regains, 2)

    # Get high-press regains from events (recoveries in attacking third)
    my_team_high_press = sum(
        1
        for event in events
        if event.team == "my_team"
        and event.type in regain_types
        and (event_x := _get_event_x(event, frame_by_id)) is not None
        and _is_pressing_zone("my_team", event_x)
    )
    enemy_high_press = sum(
        1
        for event in events
        if event.team == "enemy"
        and event.type in regain_types
        and (event_x := _get_event_x(event, frame_by_id)) is not None
        and _is_pressing_zone("enemy", event_x)
    )

    my_team_exposure = calc_exposure(turnovers_faced["my_team"], my_team_high_press)
    enemy_exposure = calc_exposure(turnovers_faced["enemy"], enemy_high_press)

    return (
        my_team_block_height,
        enemy_block_height,
        my_team_regain_zones,
        enemy_regain_zones,
        my_team_exposure,
        enemy_exposure,
    )


def _get_event_x(event: DetectedEvent, frame_by_id: dict[int, FrameData]) -> float | None:
    """Get x position from an event's frame."""
    frame = frame_by_id.get(event.frameId)
    if frame is None:
        return None

    track_id = event.toTrackId or event.fromTrackId
    if track_id is None:
        return None

    position = _lookup_player_position(frame, event.team, track_id)
    return position[0] if position else None


def _turnover_distance(previous_position: tuple[float, float] | None, current_position: tuple[float, float] | None) -> float | None:
    if previous_position is None or current_position is None:
        return None
    return sqrt((previous_position[0] - current_position[0]) ** 2 + (previous_position[1] - current_position[1]) ** 2)


def _is_interception(previous_position: tuple[float, float] | None, current_position: tuple[float, float] | None) -> bool:
    distance = _turnover_distance(previous_position, current_position)
    return distance is not None and 6.0 < distance <= 18.0


def normalize_tracking_rows(rows: Iterable[dict]) -> list[FrameData]:
    iterator = iter(rows)
    try:
        first = next(iterator)
    except StopIteration:
        return []
    rows = chain((first,), iterator)
    if "frameId" in first:
        return [FrameData.model_validate(row) for row in rows]

    grouped: dict[int, FrameData] = {}
    for row in rows:
        add_tracking_row(grouped, row)
    return [grouped[frame_id] for frame_id in sorted(grouped)]


def add_tracking_row(grouped: dict[int, FrameData], row: dict) -> None:
    frame_id = int(row["Frame_ID"])
    frame = grouped.setdefault(
        frame_id,
        FrameData(frameId=frame_id, timestamp=float(row["Timestamp"])),
    )
    entity_type = row["Entity_Type"]
    confidence = float(row.get("Conf", 0.0))
    if entity_type == "ball":
        frame.ball = BallData(x=float(row["X"]), y=float(row["Y"]), confidence=confidence)
    elif entity_type == "my_team":
        frame.myTeam.append(
            PlayerData(
                id=int(row["Track_ID"]),
                x=float(row["X"]),
                y=float(row["Y"]),
                confidence=confidence,
            )
        )
    elif entity_type == "enemy":
        frame.enemies.append(
            PlayerData(
                id=int(row["Track_ID"]),
                x=float(row["X"]),
                y=float(row["Y"]),
                confidence=confidence,
            )
        )
    elif entity_type == "player":
        frame.unassignedPlayers.append(
            PlayerData(
                id=int(row["Track_ID"]),
                x=float(row["X"]),
                y=float(row["Y"]),
                confidence=confidence,
            )
        )


def assign_ball_possession(frames: list[dict | FrameData]) -> list[BallOwnership]:
    canonical_frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]
    assignments: list[BallOwnership] = []
    previous_owner: BallOwnership | None = None

    for frame in canonical_frames:
        if frame.ball is None:
            assignments.append(
                BallOwnership(frameId=frame.frameId, timestamp=frame.timestamp, team="dead_ball", trackId=None)
            )
            previous_owner = assignments[-1]
            continue

        candidates: list[BallOwnership] = []
        for team_name, players in (("my_team", frame.myTeam), ("enemy", frame.enemies), ("unassigned", frame.unassignedPlayers)):
            for player in players:
                distance = sqrt((player.x - frame.ball.x) ** 2 + (player.y - frame.ball.y) ** 2)
                candidates.append(
                    BallOwnership(
                        frameId=frame.frameId,
                        timestamp=frame.timestamp,
                        team=team_name,
                        trackId=player.id,
                        distance=round(distance, 3),
                    )
                )

        if not candidates:
            assignments.append(
                BallOwnership(frameId=frame.frameId, timestamp=frame.timestamp, team="unassigned", trackId=None)
            )
            previous_owner = assignments[-1]
            continue

        candidates.sort(key=lambda item: _distance_value(item.distance))
        best_candidate = candidates[0]
        if _distance_value(best_candidate.distance) > MAX_OWNER_DISTANCE:
            best_candidate = BallOwnership(
                frameId=frame.frameId,
                timestamp=frame.timestamp,
                team="contested",
                trackId=None,
                distance=best_candidate.distance,
            )
        elif (
            previous_owner
            and previous_owner.team in PLAYER_CONTROL_TEAMS
            and previous_owner.trackId is not None
            and previous_owner.team == best_candidate.team
            and previous_owner.trackId == best_candidate.trackId
        ):
            pass
        elif previous_owner and previous_owner.team in PLAYER_CONTROL_TEAMS and previous_owner.trackId is not None:
            continuity_candidate = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.team == previous_owner.team and candidate.trackId == previous_owner.trackId and _distance_value(candidate.distance) <= CONTINUITY_DISTANCE
                ),
                None,
            )
            if continuity_candidate:
                best_candidate = continuity_candidate

        assignments.append(best_candidate)
        previous_owner = best_candidate

    return _bridge_short_dead_ball_gaps(assignments)


def apply_possession_to_frames(frames: list[FrameData], assignments: list[BallOwnership]) -> list[FrameData]:
    assignment_by_frame = {assignment.frameId: assignment for assignment in assignments}
    return [
        frame.model_copy(update={"possession": assignment_by_frame.get(frame.frameId)})
        for frame in frames
    ]


def _ball_rows_by_frame(ball_truth_layers: dict[str, object] | None, layer_name: str) -> dict[int, dict[str, float]]:
    if not isinstance(ball_truth_layers, dict):
        return {}
    layer_payload = ball_truth_layers.get(layer_name)
    if not isinstance(layer_payload, dict):
        return {}
    rows = layer_payload.get("rows")
    if not isinstance(rows, list):
        return {}

    normalized: dict[int, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            raw_frame_id = row.get("Frame_ID")
            if raw_frame_id is None:
                continue
            frame_id = int(raw_frame_id)
            raw_x = row.get("X")
            if raw_x is None:
                continue
            x = float(raw_x)
            raw_y = row.get("Y")
            if raw_y is None:
                continue
            y = float(raw_y)
            confidence = float(row.get("Conf", 0.0))
        except (TypeError, ValueError):
            continue
        normalized[frame_id] = {"x": x, "y": y, "confidence": confidence}
    return normalized


def _normalize_match_state_evidence(match_state_evidence: dict[str, object] | None) -> dict[int, dict[str, object]]:
    if not isinstance(match_state_evidence, dict):
        return {}
    frames_payload = match_state_evidence.get("frames")
    if not isinstance(frames_payload, list):
        return {}

    normalized: dict[int, dict[str, object]] = {}
    for item in frames_payload:
        if not isinstance(item, dict):
            continue
        try:
            raw_frame_id = item.get("frameId")
            if raw_frame_id is None:
                continue
            frame_id = int(raw_frame_id)
        except (TypeError, ValueError):
            continue
        normalized[frame_id] = dict(item)
    return normalized


def _state_ball_estimate(point_payload: dict[str, float] | None) -> BallEstimate | None:
    if not isinstance(point_payload, dict):
        return None
    return BallEstimate(
        x=float(point_payload["x"]),
        y=float(point_payload["y"]),
        confidence=float(point_payload.get("confidence", 0.0)),
        radius=0.0,
    )


def _nearest_controlled_assignment(
    assignments: list[BallOwnership],
    index: int,
    *,
    direction: int,
    max_steps: int = MATCH_STATE_CONTINUITY_MAX_NEIGHBOR_FRAMES,
) -> BallOwnership | None:
    for step in range(1, max_steps + 1):
        probe_index = index + (direction * step)
        if probe_index < 0 or probe_index >= len(assignments):
            break
        candidate = assignments[probe_index]
        if candidate.team in CONTROLLED_TEAMS and candidate.trackId is not None:
            return candidate
    return None


@runtime_checkable
class _IndexableReasonCodes(Protocol):
    """Retain Python's legacy sequence iteration, not just __iter__ objects."""

    def __getitem__(self, index: int, /) -> object: ...


def _match_state_reason_codes(values: object) -> list[str]:
    # Do not coerce invalid containers to []: malformed evidence remains an error.
    # Strings/dict keys and index-based sequences retain their existing semantics.
    iterable: Iterable[object]
    if isinstance(values, Iterable):
        iterable = values
    elif isinstance(values, _IndexableReasonCodes):
        iterable = iter(values)
    else:
        raise TypeError(f"'{type(values).__name__}' object is not iterable")
    return [str(code) for code in iterable if isinstance(code, str) and code.strip()]


def _classify_initial_match_state(
    frame: FrameData,
    assignment: BallOwnership,
    observed_rows_by_frame: dict[int, dict[str, float]],
    inferred_rows_by_frame: dict[int, dict[str, float]],
    accepted_rows_by_frame: dict[int, dict[str, float]],
    evidence_by_frame: dict[int, dict[str, object]],
) -> MatchStateFrame:
    """Classify one frame; temporal continuity is applied in a separate pass."""
    evidence_payload = evidence_by_frame.get(frame.frameId, {})
    accepted_source = evidence_payload.get('acceptedSource')
    if accepted_source not in {'observed', 'inferred'}:
        if frame.frameId in observed_rows_by_frame:
            accepted_source = 'observed'
        elif frame.frameId in inferred_rows_by_frame:
            accepted_source = 'inferred'
        elif frame.ball is not None:
            accepted_source = 'observed'
        else:
            accepted_source = 'none'
    accepted_point = accepted_rows_by_frame.get(frame.frameId)
    if accepted_point is None and frame.ball is not None:
        accepted_point = {'x': float(frame.ball.x), 'y': float(frame.ball.y), 'confidence': float(frame.ball.confidence)}
    reason_codes = _match_state_reason_codes(evidence_payload.get('reasonCodes', []))
    has_accepted_ball = accepted_source in {'observed', 'inferred'} and accepted_point is not None
    if assignment.team in CONTROLLED_TEAMS and assignment.trackId is not None:
        return MatchStateFrame(
            frameId=frame.frameId,
            timestamp=frame.timestamp,
            mode='controlled_possession',
            controllingTeam=assignment.team,
            controllingTrackId=assignment.trackId,
            ballVisibility='visible' if accepted_source == 'observed' else 'inferred',
            ballEstimate=_state_ball_estimate(accepted_point),
            source='observed_ball' if accepted_source == 'observed' else 'inferred_ball',
            confidence=0.9 if accepted_source == 'observed' else 0.75,
            reasonCodes=reason_codes,
        )
    if assignment.team == 'dead_ball':
        return MatchStateFrame(
            frameId=frame.frameId,
            timestamp=frame.timestamp,
            mode='restart_or_out',
            controllingTeam='none',
            controllingTrackId=None,
            ballVisibility='hidden',
            ballEstimate=None,
            source='restart_rule',
            confidence=0.7,
            reasonCodes=reason_codes,
        )
    if has_accepted_ball:
        return MatchStateFrame(
            frameId=frame.frameId,
            timestamp=frame.timestamp,
            mode='loose_ball',
            controllingTeam='contested' if assignment.team == 'contested' else 'unassigned',
            controllingTrackId=None,
            ballVisibility='visible' if accepted_source == 'observed' else 'inferred',
            ballEstimate=_state_ball_estimate(accepted_point),
            source='observed_ball' if accepted_source == 'observed' else 'inferred_ball',
            confidence=0.6,
            reasonCodes=reason_codes,
        )
    return MatchStateFrame(
        frameId=frame.frameId,
        timestamp=frame.timestamp,
        mode='unknown',
        controllingTeam='none',
        controllingTrackId=None,
        ballVisibility='hidden',
        ballEstimate=None,
        source='unknown',
        confidence=0.4,
        reasonCodes=reason_codes,
    )


def build_accepted_match_state(
    frames: list[dict | FrameData],
    assignments: list[BallOwnership],
    *,
    ball_truth_layers: dict[str, object] | None = None,
    match_state_evidence: dict[str, object] | None = None,
) -> list[MatchStateFrame]:
    canonical_frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]
    canonical_assignments = [
        assignment if isinstance(assignment, BallOwnership) else BallOwnership.model_validate(assignment)
        for assignment in assignments
    ]
    observed_rows_by_frame = _ball_rows_by_frame(ball_truth_layers, "observedBall")
    inferred_rows_by_frame = _ball_rows_by_frame(ball_truth_layers, "inferredBall")
    accepted_rows_by_frame = _ball_rows_by_frame(ball_truth_layers, "acceptedBall")
    evidence_by_frame = _normalize_match_state_evidence(match_state_evidence)

    states: list[MatchStateFrame] = []
    for frame, assignment in zip(canonical_frames, canonical_assignments, strict=False):
        states.append(
            _classify_initial_match_state(
                frame, assignment, observed_rows_by_frame, inferred_rows_by_frame,
                accepted_rows_by_frame, evidence_by_frame,
            )
        )

    for index, frame in enumerate(canonical_frames):
        if frame.frameId in accepted_rows_by_frame or frame.ball is not None:
            continue
        previous_controlled = _nearest_controlled_assignment(canonical_assignments, index, direction=-1)
        next_controlled = _nearest_controlled_assignment(canonical_assignments, index, direction=1)
        if previous_controlled is None or next_controlled is None:
            continue
        if (
            previous_controlled.team not in CONTROLLED_TEAMS
            or next_controlled.team not in CONTROLLED_TEAMS
            or previous_controlled.trackId is None
            or next_controlled.trackId is None
            or previous_controlled.team != next_controlled.team
            or previous_controlled.trackId != next_controlled.trackId
        ):
            continue
        reason_codes = list(states[index].reasonCodes)
        if "player_conditioned" not in reason_codes:
            reason_codes.append("player_conditioned")
        states[index] = MatchStateFrame(
            frameId=frame.frameId,
            timestamp=frame.timestamp,
            mode="controlled_possession",
            controllingTeam=previous_controlled.team,
            controllingTrackId=previous_controlled.trackId,
            ballVisibility="hidden",
            ballEstimate=None,
            source="player_conditioned",
            confidence=0.65,
            reasonCodes=reason_codes,
        )

    return states


def apply_match_state_continuity(
    assignments: list[BallOwnership],
    accepted_match_state: list[dict | MatchStateFrame],
) -> tuple[list[BallOwnership], int]:
    canonical_assignments = [
        assignment if isinstance(assignment, BallOwnership) else BallOwnership.model_validate(assignment)
        for assignment in assignments
    ]
    canonical_state = [
        state if isinstance(state, MatchStateFrame) else MatchStateFrame.model_validate(state)
        for state in accepted_match_state
    ]
    adjusted_assignments = list(canonical_assignments)
    applied_frames = 0

    for index, state in enumerate(canonical_state):
        if state.mode != "controlled_possession":
            continue
        if state.source != "player_conditioned" or state.ballVisibility != "hidden" or state.confidence < 0.65:
            continue
        if state.controllingTeam not in CONTROLLED_TEAMS or state.controllingTrackId is None:
            continue
        current_assignment = canonical_assignments[index]
        if current_assignment.team not in MATCH_STATE_CONTINUITY_ELIGIBLE_BASELINE_TEAMS:
            continue
        previous_controlled = _nearest_controlled_assignment(canonical_assignments, index, direction=-1)
        next_controlled = _nearest_controlled_assignment(canonical_assignments, index, direction=1)
        if previous_controlled is None or next_controlled is None:
            continue
        if (
            previous_controlled.team != next_controlled.team
            or previous_controlled.trackId != next_controlled.trackId
            or previous_controlled.team != state.controllingTeam
            or previous_controlled.trackId != state.controllingTrackId
        ):
            continue
        adjusted_assignments[index] = current_assignment.model_copy(
            update={
                "team": state.controllingTeam,
                "trackId": state.controllingTrackId,
                "distance": previous_controlled.distance if previous_controlled.distance is not None else next_controlled.distance,
            }
        )
        applied_frames += 1

    return adjusted_assignments, applied_frames


def detect_formation(players: list[dict[str, float]]) -> str:
    if len(players) < 3:
        return "-"
    sorted_players = sorted(players, key=lambda player: player["x"])
    rows: list[int] = []
    current_row = 1
    for index in range(1, len(sorted_players)):
        gap = sorted_players[index]["x"] - sorted_players[index - 1]["x"]
        if gap > 10:
            rows.append(current_row)
            current_row = 1
        else:
            current_row += 1
    rows.append(current_row)
    if len(rows) > 1 and rows[0] == 1:
        rows = rows[1:]
    return "-".join(str(item) for item in rows) or "-"


def build_formation_timeline(
    frames: Iterable[dict | FrameData],
    *,
    team: str = "my_team",
    window_size: int = 5,
    attack_direction: str = "left_to_right",
) -> list[FormationSegment]:
    canonical_frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]
    canonical_frames = _oriented_frames(canonical_frames, attack_direction)
    if not canonical_frames:
        return []

    raw_formations: list[str] = []
    for frame in canonical_frames:
        players = frame.myTeam if team == "my_team" else frame.enemies
        raw_formations.append(detect_formation([{"x": player.x if team == "my_team" else 100 - player.x, "y": player.y} for player in players]))

    effective_window = max(1, min(window_size, len(canonical_frames)))
    half_window = effective_window // 2
    smoothed_formations: list[str] = []

    for index in range(len(canonical_frames)):
        start = max(0, index - half_window)
        end = min(len(canonical_frames), index + half_window + 1)
        window_formations = [formation for formation in raw_formations[start:end] if formation != "-"]
        if not window_formations or raw_formations[index] == "-":
            smoothed_formations.append("-")
        else:
            smoothed_formations.append(Counter(window_formations).most_common(1)[0][0])

    timeline: list[FormationSegment] = []
    previous_known_index: int | None = None
    for index, formation in enumerate(smoothed_formations):
        if formation == "-":
            continue
        frame = canonical_frames[index]
        gap_exceeded = (
            previous_known_index is not None
            and frame.timestamp - canonical_frames[previous_known_index].timestamp > FORMATION_MAX_GAP_S
        )
        if timeline and timeline[-1].formation == formation and not gap_exceeded:
            timeline[-1] = timeline[-1].model_copy(
                update={"endFrameId": frame.frameId, "endTimestamp": frame.timestamp}
            )
            previous_known_index = index
            continue
        timeline.append(
            FormationSegment(
                formation=formation,
                startFrameId=frame.frameId,
                endFrameId=frame.frameId,
                startTimestamp=frame.timestamp,
                endTimestamp=frame.timestamp,
            )
        )
        previous_known_index = index

    return timeline


def _select_primary_formation(timeline: list[FormationSegment]) -> str | None:
    if not timeline:
        return None
    primary = max(
        timeline,
        key=lambda segment: (
            segment.endFrameId - segment.startFrameId,
            segment.endTimestamp - segment.startTimestamp,
        ),
    )
    if primary.formation == "-" or primary.endFrameId <= primary.startFrameId:
        return None
    return primary.formation


def build_shot_analytics(frames: list[FrameData | dict], events: list[DetectedEvent | dict], *, attack_direction: str = "left_to_right") -> list[ShotAnalytics]:
    canonical_frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]
    canonical_events = [event if isinstance(event, DetectedEvent) else DetectedEvent.model_validate(event) for event in events]
    frame_by_id = {frame.frameId: frame for frame in canonical_frames}

    shots: list[ShotAnalytics] = []
    for event in canonical_events:
        if event.type != "shot" or event.team not in CONTROLLED_TEAMS or event.fromTrackId is None:
            continue
        frame = frame_by_id.get(event.frameId)
        if frame is None:
            continue
        position = _lookup_player_position(frame, event.team, event.fromTrackId)
        if position is None:
            continue

        attacking_position = (100 - position[0], position[1]) if attack_direction == "right_to_left" else position
        xg, distance_to_goal, angle_degrees, in_box = _estimate_shot_xg(event.team, attacking_position)
        shots.append(
            ShotAnalytics(
                frameId=event.frameId,
                timestamp=event.timestamp,
                team=event.team,
                playerId=event.fromTrackId,
                x=round(position[0], 1),
                y=round(position[1], 1),
                inBox=in_box,
                xg=xg,
                distanceToGoal=distance_to_goal,
                angleDegrees=angle_degrees,
            )
        )

    return sorted(shots, key=lambda shot: (shot.timestamp, shot.frameId, shot.playerId))


def _possession_durations(
    assignments: list[BallOwnership],
) -> tuple[float, float, float, bool]:
    """Measure eligible intervals; retain the equal-duration fallback when needed."""
    controlled = [assignment for assignment in assignments if assignment.team in {"my_team", "enemy"}]
    controlled_frames = len(controlled)
    eligible_seconds = 0.0
    requested_seconds = 0.0
    my_team_seconds = 0.0
    for current, following in zip(assignments, assignments[1:], strict=False):
        duration = following.timestamp - current.timestamp
        if duration <= 0:
            continue
        requested_seconds += duration
        if current.team in {"my_team", "enemy"}:
            eligible_seconds += duration
            if current.team == "my_team":
                my_team_seconds += duration
    equal_duration_assumed = eligible_seconds <= 0 and bool(controlled)
    if equal_duration_assumed:
        eligible_seconds = float(controlled_frames)
        requested_seconds = eligible_seconds
        my_team_seconds = float(sum(1 for assignment in controlled if assignment.team == "my_team"))

    return eligible_seconds, requested_seconds, my_team_seconds, equal_duration_assumed


def _accumulate_team_motion(
    players: list[PlayerData],
    previous_players: list[PlayerData],
    *,
    dt: float,
    pitch_length_m: float,
    pitch_width_m: float,
    total_distance: float,
    top_speed: float,
    sprint_count: int,
    previous_sprints: set[int],
) -> tuple[float, float, int, set[int]]:
    """Accumulate in player order and count only entries into a sprint."""
    current_sprints: set[int] = set()
    for current_player in players:
        previous_player = next((player for player in previous_players if player.id == current_player.id), None)
        if previous_player is None:
            continue
        dx = (current_player.x - previous_player.x) / 100 * pitch_length_m
        dy = (current_player.y - previous_player.y) / 100 * pitch_width_m
        distance = sqrt(dx * dx + dy * dy)
        speed = (distance / dt) * 3.6
        total_distance += distance
        top_speed = max(top_speed, speed)
        if speed > 25:
            sprint_count += int(current_player.id not in previous_sprints)
            current_sprints.add(current_player.id)

    return total_distance, top_speed, sprint_count, current_sprints


def summarize_match(
    frames: list[dict | FrameData],
    assignments: list[BallOwnership],
    shots: list[ShotAnalytics] | None = None,
    events: list[DetectedEvent | dict] | None = None,
    *, attack_direction: str = "left_to_right",
    identity_continuous: bool = False,
    calibration_accepted: bool = False,
    pitch_length_m: float = PITCH_LENGTH_M,
    pitch_width_m: float = PITCH_WIDTH_M,
) -> MatchSummary:
    canonical_frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]
    canonical_events = [event if isinstance(event, DetectedEvent) else DetectedEvent.model_validate(event) for event in (events or [])]
    directional_frames = _oriented_frames(canonical_frames, attack_direction)
    formation_timeline = build_formation_timeline(directional_frames)
    eligible_seconds, requested_seconds, my_team_seconds, equal_duration_assumed = _possession_durations(assignments)

    my_team_total_dist = 0.0
    enemy_total_dist = 0.0
    my_team_top_speed = 0.0
    enemy_top_speed = 0.0
    my_team_sprints = 0
    enemy_sprints = 0
    physical_eligible_seconds = 0.0
    physical_requested_seconds = 0.0
    sprinting: dict[str, set[int]] = {"my_team": set(), "enemy": set()}
    my_team_pos_sum = {"x": 0.0, "y": 0.0, "count": 0}
    enemy_pos_sum = {"x": 0.0, "y": 0.0, "count": 0}

    for index, frame in enumerate(canonical_frames):
        for player in frame.myTeam:
            my_team_pos_sum["x"] += player.x
            my_team_pos_sum["y"] += player.y
            my_team_pos_sum["count"] += 1
        for player in frame.enemies:
            enemy_pos_sum["x"] += player.x
            enemy_pos_sum["y"] += player.y
            enemy_pos_sum["count"] += 1

        if index == 0:
            continue

        previous = canonical_frames[index - 1]
        dt = frame.timestamp - previous.timestamp
        if dt <= 0:
            sprinting = {"my_team": set(), "enemy": set()}
            continue
        physical_requested_seconds += dt
        previous_my_ids = {player.id for player in previous.myTeam}
        previous_enemy_ids = {player.id for player in previous.enemies}
        if any(player.id in previous_my_ids for player in frame.myTeam) or any(
            player.id in previous_enemy_ids for player in frame.enemies
        ):
            physical_eligible_seconds += dt
        if not identity_continuous:
            continue
        current_sprints: dict[str, set[int]] = {"my_team": set(), "enemy": set()}

        my_team_total_dist, my_team_top_speed, my_team_sprints, current_sprints["my_team"] = _accumulate_team_motion(
            frame.myTeam, previous.myTeam, dt=dt,
            pitch_length_m=pitch_length_m, pitch_width_m=pitch_width_m,
            total_distance=my_team_total_dist, top_speed=my_team_top_speed,
            sprint_count=my_team_sprints, previous_sprints=sprinting["my_team"],
        )
        enemy_total_dist, enemy_top_speed, enemy_sprints, current_sprints["enemy"] = _accumulate_team_motion(
            frame.enemies, previous.enemies, dt=dt,
            pitch_length_m=pitch_length_m, pitch_width_m=pitch_width_m,
            total_distance=enemy_total_dist, top_speed=enemy_top_speed,
            sprint_count=enemy_sprints, previous_sprints=sprinting["enemy"],
        )
        sprinting = current_sprints

    formation = _select_primary_formation(formation_timeline)
    my_team_avg_x = my_team_pos_sum["x"] / my_team_pos_sum["count"] if my_team_pos_sum["count"] else None
    my_team_avg_y = my_team_pos_sum["y"] / my_team_pos_sum["count"] if my_team_pos_sum["count"] else None
    enemy_avg_x = enemy_pos_sum["x"] / enemy_pos_sum["count"] if enemy_pos_sum["count"] else None
    enemy_avg_y = enemy_pos_sum["y"] / enemy_pos_sum["count"] if enemy_pos_sum["count"] else None
    labelled_shots = shots or []
    my_team_shot_quality = [shot.xg for shot in labelled_shots if shot.team == "my_team"]
    enemy_shot_quality = [shot.xg for shot in labelled_shots if shot.team == "enemy"]
    my_team_xg = round(sum(my_team_shot_quality), 2) if my_team_shot_quality else None
    enemy_xg = round(sum(enemy_shot_quality), 2) if enemy_shot_quality else None
    (
        my_team_defensive_line_height,
        enemy_defensive_line_height,
        my_team_defensive_team_length,
        enemy_defensive_team_length,
    ) = _summarize_defensive_shape(directional_frames, assignments)
    (
        my_team_ppda,
        enemy_ppda,
        my_team_high_press_regains,
        enemy_high_press_regains,
        my_team_counterpress_recovery_seconds,
        enemy_counterpress_recovery_seconds,
    ) = _summarize_pressing_metrics(directional_frames, canonical_events)

    # Defensive context metrics
    (
        my_team_block_height,
        enemy_block_height,
        my_team_regain_zones,
        enemy_regain_zones,
        my_team_transition_exposure,
        enemy_transition_exposure,
    ) = _summarize_defensive_context(
        directional_frames, assignments, canonical_events,
        my_team_defensive_line_height, enemy_defensive_line_height
    )

    possession = round((my_team_seconds / eligible_seconds) * 100) if eligible_seconds else None
    line_break_visibility = {
        "my_team": bool(directional_frames)
        and all(len(frame.enemies) >= MIN_VISIBLE_DEFENDERS_FOR_LINE_BREAK for frame in directional_frames),
        "enemy": bool(directional_frames)
        and all(len(frame.myTeam) >= MIN_VISIBLE_DEFENDERS_FOR_LINE_BREAK for frame in directional_frames),
    }
    line_break_counts = {
        team: sum(event.type == "through_ball" and event.team == team for event in canonical_events)
        for team in ("my_team", "enemy")
    }
    summary = MatchSummary(
        possession=possession,
        myTeamDistance=round(my_team_total_dist) if identity_continuous else None,
        enemyDistance=round(enemy_total_dist) if identity_continuous else None,
        myTeamAvgPos={"x": round(my_team_avg_x, 1), "y": round(my_team_avg_y, 1)} if my_team_avg_x is not None and my_team_avg_y is not None else None,
        enemyAvgPos={"x": round(enemy_avg_x, 1), "y": round(enemy_avg_y, 1)} if enemy_avg_x is not None and enemy_avg_y is not None else None,
        myTeamTopSpeed=round(my_team_top_speed, 1) if identity_continuous else None,
        enemyTopSpeed=round(enemy_top_speed, 1) if identity_continuous else None,
        myTeamSprints=my_team_sprints if identity_continuous else None,
        enemySprints=enemy_sprints if identity_continuous else None,
        myTeamXg=my_team_xg,
        enemyXg=enemy_xg,
        myTeamDefensiveLineHeight=my_team_defensive_line_height,
        enemyDefensiveLineHeight=enemy_defensive_line_height,
        myTeamDefensiveTeamLength=my_team_defensive_team_length,
        enemyDefensiveTeamLength=enemy_defensive_team_length,
        myTeamPpda=my_team_ppda,
        enemyPpda=enemy_ppda,
        myTeamHighPressRegains=my_team_high_press_regains,
        enemyHighPressRegains=enemy_high_press_regains,
        myTeamCounterpressRecoverySeconds=my_team_counterpress_recovery_seconds,
        enemyCounterpressRecoverySeconds=enemy_counterpress_recovery_seconds,
        formation=formation,
        myTeamBlockHeight=my_team_block_height,
        enemyBlockHeight=enemy_block_height,
        myTeamRegainZones=my_team_regain_zones,
        enemyRegainZones=enemy_regain_zones,
        myTeamTransitionExposure=my_team_transition_exposure,
        enemyTransitionExposure=enemy_transition_exposure,
    )
    return summary.model_copy(
        update={
            "metricAvailability": _summary_metric_availability(
                summary,
                my_pressing_actions=my_team_high_press_regains,
                enemy_pressing_actions=enemy_high_press_regains,
                identity_continuous=identity_continuous,
                calibration_accepted=calibration_accepted,
                eligible_seconds=eligible_seconds,
                requested_seconds=requested_seconds,
                physical_eligible_seconds=physical_eligible_seconds,
                physical_requested_seconds=physical_requested_seconds,
                equal_duration_assumed=equal_duration_assumed,
                pitch_length_m=pitch_length_m,
                pitch_width_m=pitch_width_m,
                line_break_visibility=line_break_visibility,
                line_break_counts=line_break_counts,
            )
        }
    )


def _ppda_availability(metric: str, value: float | None, pressing_actions: int | None) -> MetricAvailabilityRecord:
    if pressing_actions is None or pressing_actions <= 0:
        return MetricAvailabilityRecord(
            metric=metric,
            value=None,
            availability="unknown",
            reasonCodes=["ZERO_DENOMINATOR"],
            unit="passes_per_defensive_action",
            denominator="pressing_actions",
        )
    return MetricAvailabilityRecord(
        metric=metric,
        value=value,
        availability="experimental",
        unit="passes_per_defensive_action",
        denominator="pressing_actions",
        publishedLabel="PPDA",
    )


def _summary_metric_availability(
    summary: MatchSummary,
    *,
    my_pressing_actions: int | None,
    enemy_pressing_actions: int | None,
    identity_continuous: bool = False,
    calibration_accepted: bool = False,
    eligible_seconds: float = 0.0,
    requested_seconds: float = 0.0,
    physical_eligible_seconds: float = 0.0,
    physical_requested_seconds: float = 0.0,
    equal_duration_assumed: bool = False,
    pitch_length_m: float = PITCH_LENGTH_M,
    pitch_width_m: float = PITCH_WIDTH_M,
    line_break_visibility: dict[str, bool] | None = None,
    line_break_counts: dict[str, int] | None = None,
) -> list[MetricAvailabilityRecord]:
    possession_definition = METRIC_DEFINITIONS["possession_pct"]
    possession = MetricAvailabilityRecord(
        metric="possession_pct",
        definitionVersion=possession_definition.version,
        value=None if summary.possession is None else float(summary.possession),
        availability="available" if eligible_seconds and summary.possession is not None else "unknown",
        reasonCodes=[
            *(["EQUAL_DURATION_ASSUMED"] if equal_duration_assumed else []),
            *(["UNKNOWN_INTERVALS_EXCLUDED"] if requested_seconds > eligible_seconds else []),
        ] if eligible_seconds and summary.possession is not None else ["ZERO_DENOMINATOR"],
        unit=possession_definition.unit,
        denominator=possession_definition.denominator,
        eligibleSeconds=eligible_seconds,
        requestedSeconds=requested_seconds,
    )
    physical_reason = [
        *([] if calibration_accepted else ["CALIBRATION_UNAVAILABLE"]),
        *([] if identity_continuous else ["IDENTITY_DISCONTINUITY"]),
        *([] if physical_eligible_seconds > 0 else ["ZERO_DENOMINATOR"]),
    ]
    physical_available = identity_continuous and calibration_accepted and physical_eligible_seconds > 0
    physical_values = {
        "my_team_distance_m": None if summary.myTeamDistance is None else float(summary.myTeamDistance),
        "enemy_distance_m": None if summary.enemyDistance is None else float(summary.enemyDistance),
        "my_team_top_speed_kmh": None if summary.myTeamTopSpeed is None else float(summary.myTeamTopSpeed),
        "enemy_top_speed_kmh": None if summary.enemyTopSpeed is None else float(summary.enemyTopSpeed),
        "my_team_sprints": None if summary.myTeamSprints is None else float(summary.myTeamSprints),
        "enemy_sprints": None if summary.enemySprints is None else float(summary.enemySprints),
    }
    physical = [
        MetricAvailabilityRecord(
            metric=name,
            definitionVersion=METRIC_DEFINITIONS[
                "distance_m" if "distance" in name else "speed_kmh" if "speed" in name else "sprints"
            ].version,
            value=physical_values[name] if physical_available else None,
            availability="available" if physical_available else "withheld",
            reasonCodes=[] if physical_available else physical_reason,
            unit=METRIC_DEFINITIONS[
                "distance_m" if "distance" in name else "speed_kmh" if "speed" in name else "sprints"
            ].unit,
            denominator="identity_continuous_eligible_seconds",
            eligibleSeconds=physical_eligible_seconds,
            requestedSeconds=physical_requested_seconds,
            pitchDimensions={"lengthM": pitch_length_m, "widthM": pitch_width_m},
        )
        for name in physical_values
    ]
    shot_quality = [
        MetricAvailabilityRecord(
            metric=f"{team}_experimental_shot_quality_sum",
            value=None if value is None else round(value, 2),
            availability="unknown" if value is None else "experimental",
            publishedLabel="experimental_shot_quality",
            unit="expected_shots_heuristic",
            denominator="labelled_shots",
            reasonCodes=["NO_LABELLED_SHOTS"] if value is None else [],
            teamScope=team,
        )
        for team, value in (("my_team", summary.myTeamXg), ("enemy", summary.enemyXg))
    ]
    shot_quality.append(
        MetricAvailabilityRecord(
            metric="experimental_shot_quality",
            availability="unknown",
            reasonCodes=["DEPRECATED_TEAM_SCOPE_REQUIRED"],
            publishedLabel="experimental_shot_quality",
            deprecated=True,
        )
    )
    defensive_definition = METRIC_DEFINITIONS["defensive_line_height"]
    defensive_line = [
        MetricAvailabilityRecord(
            metric=f"{team}_defensive_line_height",
            definitionVersion=defensive_definition.version,
            value=None if value is None else float(value),
            availability="unknown" if value is None else "experimental",
            reasonCodes=["INSUFFICIENT_TEAM_VISIBILITY"] if value is None else [],
            unit=defensive_definition.unit,
            denominator=defensive_definition.denominator,
            teamScope=team,
        )
        for team, value in (
            ("my_team", summary.myTeamDefensiveLineHeight),
            ("enemy", summary.enemyDefensiveLineHeight),
        )
    ]
    line_break_definition = METRIC_DEFINITIONS["line_breaking_events"]
    line_break_visibility = line_break_visibility or {}
    line_break_counts = line_break_counts or {}
    line_breaking = [
        MetricAvailabilityRecord(
            metric=f"{team}_line_breaking_events",
            definitionVersion=line_break_definition.version,
            value=(float(line_break_counts.get(team, 0)) if line_break_visibility.get(team) else None),
            availability="experimental" if line_break_visibility.get(team) else "unknown",
            reasonCodes=[] if line_break_visibility.get(team) else ["INSUFFICIENT_TEAM_VISIBILITY"],
            unit=line_break_definition.unit,
            denominator=line_break_definition.denominator,
            teamScope=team,
        )
        for team in ("my_team", "enemy")
    ]
    return [
        possession,
        _ppda_availability("my_team_ppda", summary.myTeamPpda, my_pressing_actions),
        _ppda_availability("enemy_ppda", summary.enemyPpda, enemy_pressing_actions),
        *shot_quality,
        *defensive_line,
        *line_breaking,
        *physical,
    ]


def _append_same_team_pass_events(
    previous_segment: OwnershipSegment,
    current_segment: OwnershipSegment,
    current_frame: FrameData,
    previous_position: tuple[float, float] | None,
    current_position: tuple[float, float] | None,
    events: list[DetectedEvent],
) -> None:
    """Append a resolved-team pass and its derived suggestions in original order."""
    if current_segment.start.team == "unassigned":
        return
    events.append(
        DetectedEvent(
            type="pass",
            frameId=current_segment.start.frameId,
            timestamp=current_segment.start.timestamp,
            team=current_segment.start.team,
            fromTrackId=previous_segment.end.trackId,
            toTrackId=current_segment.start.trackId,
            description=f"Pass from #{previous_segment.end.trackId} to #{current_segment.start.trackId}",
        )
    )
    if current_segment.start.team in CONTROLLED_TEAMS:
        opponents = current_frame.enemies if current_segment.start.team == "my_team" else current_frame.myTeam
        if (
            len(opponents) >= MIN_VISIBLE_DEFENDERS_FOR_LINE_BREAK
            and previous_position is not None
            and current_position is not None
            and not _is_attacking_wide(current_segment.start.team, previous_position)
            and _is_forward_progression(current_segment.start.team, previous_position[0], current_position[0])
            and _is_advanced_target(current_segment.start.team, current_position[0])
            and _count_broken_lines(current_segment.start.team, previous_position[0], current_position[0], opponents) >= 1
        ):
            events.append(
                DetectedEvent(
                    type="through_ball",
                    frameId=current_segment.start.frameId,
                    timestamp=current_segment.start.timestamp,
                    team=current_segment.start.team,
                    fromTrackId=previous_segment.end.trackId,
                    toTrackId=current_segment.start.trackId,
                    description=f"Through ball from #{previous_segment.end.trackId} to #{current_segment.start.trackId}",
                )
            )
        if (
            previous_position is not None
            and current_position is not None
            and _is_attacking_wide(previous_segment.end.team, previous_position)
            and _is_attacking_box(current_segment.start.team, current_position)
        ):
            events.append(
                DetectedEvent(
                    type="cross",
                    frameId=current_segment.start.frameId,
                    timestamp=current_segment.start.timestamp,
                    team=current_segment.start.team,
                    fromTrackId=previous_segment.end.trackId,
                    toTrackId=current_segment.start.trackId,
                    description=f"Cross from #{previous_segment.end.trackId} to #{current_segment.start.trackId}",
                )
            )


def _append_turnover_events(
    previous_segment: OwnershipSegment,
    current_segment: OwnershipSegment,
    current_frame: FrameData,
    previous_position: tuple[float, float] | None,
    current_position: tuple[float, float] | None,
    events: list[DetectedEvent],
) -> None:
    """Append the turnover before any pressure-based tackle or interception."""
    events.append(
        DetectedEvent(
            type="turnover",
            frameId=current_segment.start.frameId,
            timestamp=current_segment.start.timestamp,
            team=current_segment.start.team,
            fromTrackId=previous_segment.end.trackId,
            toTrackId=current_segment.start.trackId,
            description=f"Possession changed to {current_segment.start.team.replace('_', ' ')}",
        )
    )
    if previous_position is None:
        previous_position = _lookup_player_position(current_frame, previous_segment.end.team, previous_segment.end.trackId)
    if (
        previous_position is not None
        and current_position is not None
        and current_segment.start.team in CONTROLLED_TEAMS
        and previous_segment.end.team in CONTROLLED_TEAMS
    ):
        pressure_distance = sqrt((previous_position[0] - current_position[0]) ** 2 + (previous_position[1] - current_position[1]) ** 2)
        if pressure_distance <= 6.0:
            events.append(
                DetectedEvent(
                    type="tackle",
                    frameId=current_segment.start.frameId,
                    timestamp=current_segment.start.timestamp,
                    team=current_segment.start.team,
                    fromTrackId=previous_segment.end.trackId,
                    toTrackId=current_segment.start.trackId,
                    description=f"Tackle won by #{current_segment.start.trackId}",
                )
            )
        elif _is_interception(previous_position, current_position):
            events.append(
                DetectedEvent(
                    type="interception",
                    frameId=current_segment.start.frameId,
                    timestamp=current_segment.start.timestamp,
                    team=current_segment.start.team,
                    fromTrackId=previous_segment.end.trackId,
                    toTrackId=current_segment.start.trackId,
                    description=f"Interception by #{current_segment.start.trackId}",
                )
            )


def _is_repeat_static_recovery(
    current_segment: OwnershipSegment,
    current_frame: FrameData,
    frame_by_id: dict[int, FrameData],
    events: list[DetectedEvent],
) -> bool:
    """Inspect prior recoveries with the existing owner, time and movement rules."""
    suppress_recovery = False
    if current_segment.start.team in PLAYER_CONTROL_TEAMS and current_segment.start.trackId is not None:
        for prior_recovery in reversed(events):
            if prior_recovery.type != "recovery":
                continue
            if prior_recovery.team != current_segment.start.team or prior_recovery.toTrackId != current_segment.start.trackId:
                continue
            if current_segment.start.timestamp - prior_recovery.timestamp > MAX_STATIC_NEUTRAL_RECOVERY_GAP_SECONDS:
                break
            last_recovery_frame = frame_by_id.get(prior_recovery.frameId)
            ball_displacement = _ball_displacement(
                last_recovery_frame.ball if last_recovery_frame is not None else None,
                current_frame.ball,
            )
            if (
                ball_displacement is not None
                and ball_displacement <= MAX_STATIC_NEUTRAL_BALL_DISPLACEMENT
            ):
                suppress_recovery = True
                break
    return suppress_recovery


def _append_loose_ball_events(
    index: int,
    current_segment: OwnershipSegment,
    segments: list[OwnershipSegment],
    canonical_frames: list[FrameData],
    frame_by_id: dict[int, FrameData],
    current_frame: FrameData,
    current_position: tuple[float, float] | None,
    events: list[DetectedEvent],
) -> None:
    """Preserve short pass bridges, recovery suppression and neutral carries."""
    emitted_same_team_pass = False
    if index > 0:
        pre_loose_segment = segments[index - 1]
        if (
            pre_loose_segment.end.team in CONTROLLED_TEAMS
            and current_segment.start.team == pre_loose_segment.end.team
            and pre_loose_segment.end.trackId is not None
            and current_segment.start.trackId is not None
            and pre_loose_segment.end.trackId != current_segment.start.trackId
            and current_segment.start.timestamp - pre_loose_segment.end.timestamp <= MAX_DEAD_BALL_BRIDGE_SECONDS
        ):
            events.append(
                DetectedEvent(
                    type="pass",
                    frameId=current_segment.start.frameId,
                    timestamp=current_segment.start.timestamp,
                    team=current_segment.start.team,
                    fromTrackId=pre_loose_segment.end.trackId,
                    toTrackId=current_segment.start.trackId,
                    description=f"Pass from #{pre_loose_segment.end.trackId} to #{current_segment.start.trackId}",
                )
            )
            emitted_same_team_pass = True

    suppress_recovery = _is_repeat_static_recovery(current_segment, current_frame, frame_by_id, events)

    if not suppress_recovery and not emitted_same_team_pass:
        events.append(
            DetectedEvent(
                type="recovery",
                frameId=current_segment.start.frameId,
                timestamp=current_segment.start.timestamp,
                team=current_segment.start.team,
                toTrackId=current_segment.start.trackId,
                description=f"{current_segment.start.team.replace('_', ' ').title()} recovered the ball",
            )
        )
    if (
        current_segment.start.team == "unassigned"
        and current_segment.start.trackId is not None
        and index > 0
    ):
        pre_loose_segment = segments[index - 1]
        pre_loose_frame = canonical_frames[pre_loose_segment.endIndex]
        pre_loose_position = _lookup_player_position(
            pre_loose_frame,
            pre_loose_segment.end.team,
            pre_loose_segment.end.trackId,
        )
        loose_gap_seconds = current_segment.start.timestamp - pre_loose_segment.end.timestamp
        if (
            pre_loose_segment.end.team == "unassigned"
            and pre_loose_segment.end.trackId == current_segment.start.trackId
            and pre_loose_position is not None
            and current_position is not None
            and loose_gap_seconds <= MAX_NEUTRAL_CARRY_GAP_SECONDS
            and _is_neutral_progression(
                pre_loose_position[0],
                current_position[0],
            )
        ):
            events.append(
                DetectedEvent(
                    type="carry",
                    frameId=current_segment.start.frameId,
                    timestamp=current_segment.start.timestamp,
                    team="unassigned",
                    fromTrackId=current_segment.start.trackId,
                    toTrackId=current_segment.start.trackId,
                    description=f"Carry by #{current_segment.start.trackId}",
                )
            )


def _append_controlled_carry_events(
    segments: list[OwnershipSegment],
    canonical_frames: list[FrameData],
    events: list[DetectedEvent],
) -> None:
    """Append within-owner carries only after transition events are collected."""
    for segment in segments:
        if (
            segment.start.team not in CONTROLLED_TEAMS
            or segment.start.trackId is None
            or segment.startIndex >= segment.endIndex
        ):
            continue

        start_frame = canonical_frames[segment.startIndex]
        end_frame = canonical_frames[segment.endIndex]
        start_position = _lookup_player_position(start_frame, segment.start.team, segment.start.trackId)
        end_position = _lookup_player_position(end_frame, segment.end.team, segment.end.trackId)
        if start_position is None or end_position is None:
            continue

        if not _segment_forward_progression(segment.start.team, start_position[0], end_position[0]):
            continue

        events.append(
            DetectedEvent(
                type="carry",
                frameId=segment.end.frameId,
                timestamp=segment.end.timestamp,
                team=segment.start.team,
                fromTrackId=segment.start.trackId,
                toTrackId=segment.end.trackId,
                description=f"Carry by #{segment.start.trackId}",
            )
        )


def detect_events(frames: list[FrameData | dict], assignments: list[BallOwnership], *, attack_direction: str = "left_to_right") -> list[DetectedEvent]:
    canonical_frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]
    canonical_frames = _oriented_frames(canonical_frames, attack_direction)
    frame_by_id = {frame.frameId: frame for frame in canonical_frames}
    events: list[DetectedEvent] = []

    if not assignments:
        return events

    segments = _build_segments(assignments)

    for index, (previous_segment, current_segment) in enumerate(zip(segments, segments[1:], strict=False)):
        previous_frame = canonical_frames[previous_segment.endIndex]
        current_frame = canonical_frames[current_segment.startIndex]
        previous_position = _lookup_player_position(previous_frame, previous_segment.end.team, previous_segment.end.trackId)
        current_position = _lookup_player_position(current_frame, current_segment.start.team, current_segment.start.trackId)

        if (
            previous_segment.end.team in CONTROLLED_TEAMS
            and current_segment.start.team in LOOSE_BALL_STATES
            and previous_position is not None
            and _is_shooting_zone(previous_segment.end.team, previous_position)
        ):
            events.append(
                DetectedEvent(
                    type="shot",
                    frameId=current_segment.start.frameId,
                    timestamp=current_segment.start.timestamp,
                    team=previous_segment.end.team,
                    fromTrackId=previous_segment.end.trackId,
                    description=f"Shot attempted by #{previous_segment.end.trackId}",
                )
            )

        if current_segment.start.team not in PLAYER_CONTROL_TEAMS:
            continue

        if (
            previous_segment.end.team in PLAYER_CONTROL_TEAMS
            and previous_segment.end.team == current_segment.start.team
            and previous_segment.end.trackId is not None
            and current_segment.start.trackId is not None
            and previous_segment.end.trackId != current_segment.start.trackId
        ):
            _append_same_team_pass_events(
                previous_segment, current_segment, current_frame,
                previous_position, current_position, events,
            )
            continue

        if (
            previous_segment.end.trackId is not None
            and previous_segment.end.trackId == current_segment.start.trackId
            and {previous_segment.end.team, current_segment.start.team} & {"unassigned"}
            and {previous_segment.end.team, current_segment.start.team} <= PLAYER_CONTROL_TEAMS
        ):
            continue

        if previous_segment.end.team in PLAYER_CONTROL_TEAMS and previous_segment.end.team != current_segment.start.team:
            _append_turnover_events(
                previous_segment, current_segment, current_frame,
                previous_position, current_position, events,
            )
            continue

        if previous_segment.end.team in LOOSE_BALL_STATES:
            _append_loose_ball_events(
                index, current_segment, segments, canonical_frames, frame_by_id,
                current_frame, current_position, events,
            )

    _append_controlled_carry_events(segments, canonical_frames, events)

    return sorted(events, key=lambda event: (event.timestamp, event.frameId))


def partition_detected_events(events: list[DetectedEvent]) -> dict[str, list[DetectedEvent]]:
    """Keep heuristic candidates separate from accepted/rejected analyst events."""

    accepted: list[DetectedEvent] = []
    candidates: list[DetectedEvent] = []
    rejected: list[DetectedEvent] = []
    for event in events:
        if event.reviewStatus == "accepted":
            accepted.append(event)
        elif event.reviewStatus == "rejected":
            rejected.append(event)
        else:
            candidates.append(event)
    return {"accepted": accepted, "candidates": candidates, "rejected": rejected}
