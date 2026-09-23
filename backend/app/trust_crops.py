from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from math import hypot, isclose, isfinite


@dataclass
class TrustCrop:
    """A frame window flagged as uncertain / worth human review."""
    frameStart: int
    frameEnd: int
    timestampStart: float
    timestampEnd: float
    score: float
    reasons: list[str]


WINDOW_SIZE = 30
BALL_TELEPORT_THRESHOLD_M = 15.0
LONG_UNASSIGNED_FRAMES = 20
TRACK_SWITCH_WEIGHT = 2.0
TEAM_FLIP_WEIGHT = 3.0
POSSESSION_GAP_WEIGHT = 4.0
BALL_TELEPORT_WEIGHT = 5.0
HIGH_SCORE_THRESHOLD = 3.0


def _valid_number(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


def compute_trust_crops(
    frames: list[dict],
    assignments: list[dict],
    max_crops: int = 20,
    *,
    pitch_length_m: float | None = None,
    pitch_width_m: float | None = None,
) -> list[TrustCrop]:
    """Score every frame window by uncertainty heuristics.

    Heuristics (no new schema needed — uses existing frames + analytics data):

    1. Ball teleport: large distance jump between consecutive frames
    2. Track ID switches: frequent track ID changes in a window
    3. Team flip rate: rapid alternation between my_team / enemy / contested
    4. Possession gap: long run of unassigned/contested ball states

    Returns top-N windows sorted by score descending.
    """
    if not frames or not assignments:
        return []

    scores: dict[int, float] = {i: 0.0 for i in range(len(frames))}
    reasons: dict[int, list[str]] = {i: [] for i in range(len(frames))}

    # 1. Ball teleport detection. Unknown geometry withholds only this pass.
    if (
        _valid_number(pitch_length_m)
        and _valid_number(pitch_width_m)
        and pitch_length_m > 0
        and pitch_width_m > 0
    ):
        for i in range(1, len(frames)):
            prev_ball = frames[i - 1].get("ball")
            curr_ball = frames[i].get("ball")
            if not isinstance(prev_ball, dict) or not isinstance(curr_ball, dict):
                continue
            coordinates = (
                prev_ball.get("x"), prev_ball.get("y"),
                curr_ball.get("x"), curr_ball.get("y"),
            )
            if not all(_valid_number(value) and 0 <= value <= 100 for value in coordinates):
                continue
            x1, y1, x2, y2 = coordinates
            distance_m = hypot(
                (x2 - x1) * pitch_length_m / 100.0,
                (y2 - y1) * pitch_width_m / 100.0,
            )
            if distance_m < BALL_TELEPORT_THRESHOLD_M or isclose(
                distance_m, BALL_TELEPORT_THRESHOLD_M, abs_tol=1e-9
            ):
                continue
            for j in range(max(0, i - 2), i + 1):
                scores[j] += BALL_TELEPORT_WEIGHT
                if "ball_teleport" not in reasons[j]:
                    reasons[j].append("ball_teleport")

    # 2. Track ID switches in window — bound indices to len(frames)
    prev_track = None
    for i, assign in enumerate(assignments):
        track = assign.get("trackId")
        if prev_track is not None and track != prev_track and track is not None:
            half = WINDOW_SIZE // 2
            for j in range(max(0, i - half), min(len(scores), i + half + 1)):
                scores[j] += TRACK_SWITCH_WEIGHT
                if "track_switches" not in reasons[j]:
                    reasons[j].append("track_switches")
        prev_track = track

    # 3. Team flip rate — bound indices to len(frames)
    prev_team = None
    for i, assign in enumerate(assignments):
        team = assign.get("team")
        if prev_team is not None and team != prev_team and team in {"my_team", "enemy", "contested"}:
            half = WINDOW_SIZE // 2
            for j in range(max(0, i - half), min(len(scores), i + half + 1)):
                scores[j] += TEAM_FLIP_WEIGHT
                if "team_flips" not in reasons[j]:
                    reasons[j].append("team_flips")
        prev_team = team

    # 4. Possession gap — long unassigned/contested — bound to len(frames)
    gap_start: int | None = None
    for i, assign in enumerate(chain(assignments, ({},))):
        team = assign.get("team")
        if team in {"unassigned", "contested", "dead_ball"}:
            if gap_start is None:
                gap_start = i
        else:
            if gap_start is not None and i - gap_start >= LONG_UNASSIGNED_FRAMES:
                half = WINDOW_SIZE // 2
                for j in range(max(0, gap_start), min(len(scores), i + half + 1)):
                    scores[j] += POSSESSION_GAP_WEIGHT
                    if "possession_gap" not in reasons[j]:
                        reasons[j].append("possession_gap")
            gap_start = None

    # Aggregate overlapping windows: score each window by sum of its frame scores
    half = WINDOW_SIZE // 2
    windows: list[tuple[float, TrustCrop]] = []

    for i in range(len(frames)):
        if scores[i] < HIGH_SCORE_THRESHOLD:
            continue
        start = max(0, i - half)
        end = min(len(frames) - 1, i + half)
        window_score = sum(scores[j] for j in range(start, end + 1))
        if window_score < HIGH_SCORE_THRESHOLD:
            continue

        frame_start = frames[start]
        frame_end = frames[end]
        crop = TrustCrop(
            frameStart=frame_start.get("frameId", start),
            frameEnd=frame_end.get("frameId", end),
            timestampStart=frame_start.get("timestamp", float(start)),
            timestampEnd=frame_end.get("timestamp", float(end)),
            score=round(window_score, 2),
            reasons=sorted({r for j in range(start, end + 1) for r in reasons[j]}),
        )
        windows.append((window_score, crop))

    windows.sort(key=lambda x: x[0], reverse=True)

    # Merge crops whose frame ranges overlap by >50% of the smaller crop
    n_frames = len(frames)
    if n_frames > 0:
        filtered: list[tuple[float, TrustCrop]] = []
        for score, crop in windows[:max_crops]:
            # Compute overlap with already-accepted crops
            crop_len = max(1, crop.frameEnd - crop.frameStart + 1)
            dominated = False
            for _, existing in filtered:
                existing_len = max(1, existing.frameEnd - existing.frameStart + 1)
                overlap_start = max(crop.frameStart, existing.frameStart)
                overlap_end = min(crop.frameEnd, existing.frameEnd)
                overlap = max(0, overlap_end - overlap_start + 1)
                smaller_len = min(crop_len, existing_len)
                if smaller_len > 0 and overlap / smaller_len > 0.5:
                    dominated = True
                    break
            if not dominated:
                filtered.append((score, crop))
        return [crop for _, crop in filtered]

    return [crop for _, crop in windows[:max_crops]]
