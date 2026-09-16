from __future__ import annotations

from math import hypot
from statistics import median

from backend.app.analytics import MAX_OWNER_DISTANCE
from backend.app.edge_share_repair_profiles import (
    SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
    TOUCHLINE_ACQUISITION_REOPEN_MODE,
    TOUCHLINE_ACQUISITION_UPGRADE_MODE,
    TOUCHLINE_PROBE_REPLACE_MODE,
    UNIFORM_EDGE_RUN_THIN_MODE,
    get_source_edge_share_repair_config,
)

PITCH_WIDTH = 100.0
PITCH_HEIGHT = 100.0
BALL_EDGE_MARGIN = 5.0
MAX_COHERENT_BALL_STEP_DISTANCE = 25.0
MAX_VIABLE_BALL_EDGE_FRAME_SHARE = 0.6
NEAR_VIABLE_BALL_EDGE_FRAME_SHARE = 0.65
MIN_MEANINGFUL_BALL_FRAMES = 3
MIN_MEANINGFUL_BALL_SPAN = 4.0
MIN_MEANINGFUL_BALL_PATH = 12.0
TOUCHLINE_REPLACEMENT_MIN_EDGE_SHARE = 0.8
TOUCHLINE_REPLACEMENT_MIN_SUPPORTED_SHARE = 0.8
TOUCHLINE_REPLACEMENT_MIN_COVERAGE_RATIO = 0.7
TOUCHLINE_REPLACEMENT_MIN_EDGE_SHARE_DELTA = 0.1
TOUCHLINE_REPLACEMENT_DOMINANT_WINDOWS = (
    (340, 3440),
    (6135, 6200),
    (6300, 6350),
)
TOUCHLINE_REPLACEMENT_CANDIDATE_FILTERED = "probeObservedBall.filteredRows"
TOUCHLINE_REPLACEMENT_CANDIDATE_RAW_REFILTERED = "probeObservedBall.rawRowsRefiltered"
TOUCHLINE_REPLACEMENT_REJECTION_NO_CANDIDATE = "candidate_segment_not_found"
TOUCHLINE_REPLACEMENT_REJECTION_EDGE_SHARE = "candidate_edge_share_improvement_insufficient"
TOUCHLINE_REPLACEMENT_REJECTION_NOT_VIABLE = "candidate_not_viable"
TOUCHLINE_REPLACEMENT_REJECTION_COVERAGE = "candidate_coverage_below_threshold"
TOUCHLINE_REPLACEMENT_REJECTION_RECONNECT = "candidate_reconnect_incoherent"
TOUCHLINE_REPLACEMENT_REJECTION_INTEGRITY = "candidate_frame_integrity_failed"


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_frame_id(row: object) -> int | None:
    if not isinstance(row, dict):
        return None
    if "Frame_ID" in row:
        return _safe_int(row.get("Frame_ID"), default=-1)
    if "frameId" in row:
        return _safe_int(row.get("frameId"), default=-1)
    return None


def _row_confidence(row: dict[str, object]) -> float:
    return _safe_float(row.get("Conf", row.get("confidence")), 0.0)


def _best_ball_rows_by_frame(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    best_rows_by_frame: dict[int, dict[str, object]] = {}
    for row in rows:
        frame_id = _extract_frame_id(row)
        if frame_id is None or frame_id < 0:
            continue
        existing = best_rows_by_frame.get(frame_id)
        if existing is None or _row_confidence(row) >= _row_confidence(existing):
            best_rows_by_frame[frame_id] = dict(row)
    return [best_rows_by_frame[frame_id] for frame_id in sorted(best_rows_by_frame)]


def _group_rows_by_frame(rows: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        frame_id = _extract_frame_id(row)
        if frame_id is None or frame_id < 0:
            continue
        grouped.setdefault(frame_id, []).append(dict(row))
    return grouped


def _split_rows_into_segments(
    rows: list[dict[str, object]],
    *,
    max_frame_gap: int,
) -> list[list[dict[str, object]]]:
    ordered_rows = _best_ball_rows_by_frame(rows)
    if not ordered_rows:
        return []
    segments: list[list[dict[str, object]]] = []
    current_segment = [ordered_rows[0]]
    for row in ordered_rows[1:]:
        previous_frame = _extract_frame_id(current_segment[-1])
        current_frame = _extract_frame_id(row)
        if previous_frame is None or current_frame is None:
            continue
        if current_frame - previous_frame > max_frame_gap:
            segments.append(current_segment)
            current_segment = [row]
            continue
        current_segment.append(row)
    if current_segment:
        segments.append(current_segment)
    return segments


def _row_source_box_center(row: dict[str, object]) -> tuple[float, float] | None:
    x1 = row.get("Source_X1", row.get("sourceX1"))
    y1 = row.get("Source_Y1", row.get("sourceY1"))
    x2 = row.get("Source_X2", row.get("sourceX2"))
    y2 = row.get("Source_Y2", row.get("sourceY2"))
    if any(value is None for value in (x1, y1, x2, y2)):
        return None
    return (
        (_safe_float(x1) + _safe_float(x2)) / 2,
        (_safe_float(y1) + _safe_float(y2)) / 2,
    )


def _row_center(row: dict[str, object]) -> tuple[float, float] | None:
    if "X" in row and "Y" in row:
        return (_safe_float(row.get("X")), _safe_float(row.get("Y")))
    if "x" in row and "y" in row:
        return (_safe_float(row.get("x")), _safe_float(row.get("y")))
    return _row_source_box_center(row)


def _row_is_edge_heavy_ball(row: dict[str, object]) -> bool:
    center = _row_center(row)
    if center is None:
        return False
    x, y = center
    return (
        x <= BALL_EDGE_MARGIN
        or x >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
        or y <= BALL_EDGE_MARGIN
        or y >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
    )


def _nearest_player_distance_for_ball_row(
    ball_row: dict[str, object],
    player_rows_by_frame: dict[int, list[dict[str, object]]],
) -> float | None:
    frame_id = _extract_frame_id(ball_row)
    if frame_id is None or frame_id < 0:
        return None
    player_rows = player_rows_by_frame.get(frame_id, [])
    if not player_rows:
        return None

    ball_center = _row_center(ball_row)
    if ball_center is None:
        return None

    player_distances = []
    for player_row in player_rows:
        player_center = _row_center(player_row)
        if player_center is None:
            continue
        player_distances.append(
            hypot(
                float(player_center[0]) - float(ball_center[0]),
                float(player_center[1]) - float(ball_center[1]),
            )
        )
    if not player_distances:
        return None
    return min(player_distances)


def _ball_row_is_player_supported(
    ball_row: dict[str, object],
    player_rows_by_frame: dict[int, list[dict[str, object]]],
) -> bool:
    nearest_player_distance = _nearest_player_distance_for_ball_row(ball_row, player_rows_by_frame)
    return nearest_player_distance is not None and nearest_player_distance <= MAX_OWNER_DISTANCE


def _bridge_frame_is_eligible(
    run_rows: list[dict[str, object]],
    index: int,
    *,
    player_rows_by_frame: dict[int, list[dict[str, object]]],
    sample_interval: int,
) -> bool:
    if index <= 0 or index >= len(run_rows) - 1:
        return False
    row = run_rows[index]
    previous_row = run_rows[index - 1]
    next_row = run_rows[index + 1]
    previous_anchored = _ball_row_is_player_supported(previous_row, player_rows_by_frame) or not _row_is_edge_heavy_ball(previous_row)
    next_anchored = _ball_row_is_player_supported(next_row, player_rows_by_frame) or not _row_is_edge_heavy_ball(next_row)
    if not previous_anchored or not next_anchored:
        return False

    row_frame = _extract_frame_id(row)
    previous_frame = _extract_frame_id(previous_row)
    next_frame = _extract_frame_id(next_row)
    if row_frame is None or previous_frame is None or next_frame is None:
        return False
    previous_frame_gap = row_frame - previous_frame
    next_frame_gap = next_frame - row_frame
    if previous_frame_gap > sample_interval or next_frame_gap > sample_interval:
        return False

    row_center = _row_center(row)
    previous_center = _row_center(previous_row)
    next_center = _row_center(next_row)
    if row_center is None or previous_center is None or next_center is None:
        return False

    previous_distance = hypot(
        float(row_center[0]) - float(previous_center[0]),
        float(row_center[1]) - float(previous_center[1]),
    )
    next_distance = hypot(
        float(next_center[0]) - float(row_center[0]),
        float(next_center[1]) - float(row_center[1]),
    )
    return (
        previous_distance <= MAX_COHERENT_BALL_STEP_DISTANCE
        and next_distance <= MAX_COHERENT_BALL_STEP_DISTANCE
    )


def _accepted_support_metrics(
    rows: list[dict[str, object]],
    *,
    player_rows_by_frame: dict[int, list[dict[str, object]]],
) -> tuple[float, int]:
    if not rows:
        return 0.0, 0
    supported_frames = 0
    unsupported_edge_frames = 0
    for row in rows:
        if _ball_row_is_player_supported(row, player_rows_by_frame):
            supported_frames += 1
            continue
        if _row_is_edge_heavy_ball(row):
            unsupported_edge_frames += 1
    return round(supported_frames / len(rows), 3), unsupported_edge_frames


def _default_diagnostics(
    *,
    profile_name: str | None,
    config: dict[str, object] | None,
    source_clip_id: str | None,
) -> dict[str, object]:
    return {
        "applied": False,
        "profileName": profile_name if isinstance(profile_name, str) else None,
        "mode": str(config.get("mode")) if isinstance(config, dict) and config.get("mode") is not None else None,
        "keepEvery": _safe_int(config.get("keepEvery"), 0) if isinstance(config, dict) else None,
        "minRunLength": _safe_int(config.get("minRunLength"), 0) if isinstance(config, dict) else None,
        "guardFrameCount": _safe_int(config.get("guardFrameCount"), 0) if isinstance(config, dict) else 0,
        "thinnedEdgeRuns": 0,
        "droppedAcceptedEdgeFrames": 0,
        "retainedAcceptedEdgeFrames": 0,
        "preservedBoundaryFrames": 0,
        "preservedSupportedFrames": 0,
        "preservedBridgeFrames": 0,
        "droppedInteriorUnsupportedFrames": 0,
        "supportedAcceptedBallRatio": 0.0,
        "unsupportedAcceptedEdgeFrames": 0,
        "sourceClipId": source_clip_id,
        "edgeRuns": [],
    }


def _default_replacement_diagnostics(
    *,
    profile_name: str | None,
    mode: str | None,
    source_clip_id: str | None,
) -> dict[str, object]:
    return {
        "applied": False,
        "profileName": profile_name if isinstance(profile_name, str) else None,
        "mode": mode,
        "sourceClipId": source_clip_id,
        "runsConsidered": 0,
        "runsAccepted": 0,
        "runsRejected": 0,
        "medianReplacementCoverageRatio": 0.0,
        "acceptedCandidateSourceCounts": {},
        "replacementRejectionReasonCounts": {},
        "runDiagnostics": [],
    }


def _run_summary(
    *,
    run_rows: list[dict[str, object]],
    kept_count: int,
    dropped_count: int,
    preserved_boundary_count: int = 0,
    preserved_supported_count: int = 0,
    preserved_bridge_count: int = 0,
    dropped_interior_unsupported_count: int = 0,
) -> dict[str, int]:
    frame_ids = [frame_id for frame_id in (_extract_frame_id(row) for row in run_rows) if frame_id is not None]
    return {
        "startFrame": frame_ids[0] if frame_ids else 0,
        "endFrame": frame_ids[-1] if frame_ids else 0,
        "runLength": len(run_rows),
        "keptFrameCount": kept_count,
        "droppedFrameCount": dropped_count,
        "preservedBoundaryFrameCount": preserved_boundary_count,
        "preservedSupportedFrameCount": preserved_supported_count,
        "preservedBridgeFrameCount": preserved_bridge_count,
        "droppedInteriorUnsupportedFrameCount": dropped_interior_unsupported_count,
    }


def _apply_uniform_edge_run_thin(
    run_rows: list[dict[str, object]],
    *,
    keep_every: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    kept_rows: list[dict[str, object]] = []
    last_index = len(run_rows) - 1
    for index, row in enumerate(run_rows):
        if index == 0 or index == last_index or index % keep_every == 0:
            kept_rows.append(row)
    dropped_count = max(len(run_rows) - len(kept_rows), 0)
    return kept_rows, _run_summary(
        run_rows=run_rows,
        kept_count=len(kept_rows),
        dropped_count=dropped_count,
        dropped_interior_unsupported_count=dropped_count,
    )


def _apply_support_guarded_edge_run_thin(
    run_rows: list[dict[str, object]],
    *,
    keep_every: int,
    guard_frame_count: int,
    player_rows_by_frame: dict[int, list[dict[str, object]]],
    sample_interval: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    preserve_indices: set[int] = set()
    run_length = len(run_rows)
    if guard_frame_count > 0:
        preserve_indices.update(range(min(guard_frame_count, run_length)))
        preserve_indices.update(range(max(0, run_length - guard_frame_count), run_length))
    boundary_indices = set(preserve_indices)

    supported_indices = {
        index
        for index, row in enumerate(run_rows)
        if index not in boundary_indices and _ball_row_is_player_supported(row, player_rows_by_frame)
    }
    preserve_indices.update(supported_indices)

    bridge_indices = {
        index
        for index, row in enumerate(run_rows)
        if index not in preserve_indices
        and _row_is_edge_heavy_ball(row)
        and _bridge_frame_is_eligible(
            run_rows,
            index,
            player_rows_by_frame=player_rows_by_frame,
            sample_interval=sample_interval,
        )
    }
    preserve_indices.update(bridge_indices)

    remaining_candidate_indices = [
        index
        for index in range(run_length)
        if index not in preserve_indices
    ]
    interior_kept_indices = {
        remaining_candidate_indices[index]
        for index in range(len(remaining_candidate_indices))
        if index % keep_every == 0
    }
    preserve_indices.update(interior_kept_indices)

    kept_rows = [row for index, row in enumerate(run_rows) if index in preserve_indices]
    dropped_count = max(run_length - len(kept_rows), 0)
    return kept_rows, _run_summary(
        run_rows=run_rows,
        kept_count=len(kept_rows),
        dropped_count=dropped_count,
        preserved_boundary_count=len(boundary_indices),
        preserved_supported_count=len(supported_indices),
        preserved_bridge_count=len(bridge_indices),
        dropped_interior_unsupported_count=dropped_count,
    )


def _run_overlaps_dominant_touchline_window(run_rows: list[dict[str, object]]) -> bool:
    if not run_rows:
        return False
    start_frame = _extract_frame_id(run_rows[0])
    end_frame = _extract_frame_id(run_rows[-1])
    if start_frame is None or end_frame is None:
        return False
    for window_start, window_end in TOUCHLINE_REPLACEMENT_DOMINANT_WINDOWS:
        if start_frame <= window_end and window_start <= end_frame:
            return True
    return False


def _rows_path_length(rows: list[dict[str, object]]) -> float:
    ordered_rows = _best_ball_rows_by_frame(rows)
    path_length = 0.0
    for previous_row, current_row in zip(ordered_rows, ordered_rows[1:]):
        previous_center = _row_center(previous_row)
        current_center = _row_center(current_row)
        if previous_center is None or current_center is None:
            continue
        path_length += hypot(
            float(current_center[0]) - float(previous_center[0]),
            float(current_center[1]) - float(previous_center[1]),
        )
    return path_length


def _segment_motion_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    ordered_rows = _best_ball_rows_by_frame(rows)
    if not ordered_rows:
        return {
            "edgeShare": 0.0,
            "pathLength": 0.0,
            "meaningfulMotion": False,
            "viable": False,
            "nearViable": False,
        }
    frame_ids = [frame_id for frame_id in (_extract_frame_id(row) for row in ordered_rows) if frame_id is not None]
    edge_share = sum(1 for row in ordered_rows if _row_is_edge_heavy_ball(row)) / len(ordered_rows)
    path_length = _rows_path_length(ordered_rows)
    frame_span = float((frame_ids[-1] - frame_ids[0]) if len(frame_ids) > 1 else 0)
    meaningful_motion = (
        len(ordered_rows) >= MIN_MEANINGFUL_BALL_FRAMES
        and frame_span >= MIN_MEANINGFUL_BALL_SPAN
        and path_length >= MIN_MEANINGFUL_BALL_PATH
    )
    viable = meaningful_motion and edge_share <= MAX_VIABLE_BALL_EDGE_FRAME_SHARE
    near_viable = meaningful_motion and edge_share <= NEAR_VIABLE_BALL_EDGE_FRAME_SHARE
    return {
        "edgeShare": round(edge_share, 3),
        "pathLength": round(path_length, 3),
        "meaningfulMotion": meaningful_motion,
        "viable": viable,
        "nearViable": near_viable,
    }


def _filter_probe_rows_for_replacement(
    probe_rows: list[dict[str, object]],
    *,
    player_rows_by_frame: dict[int, list[dict[str, object]]],
    sample_interval: int,
) -> list[dict[str, object]]:
    collapsed_probe_rows = _best_ball_rows_by_frame(
        [dict(row) for row in probe_rows if isinstance(row, dict) and row.get("Entity_Type") == "ball"]
    )
    if not collapsed_probe_rows:
        return []

    filtered_rows: list[dict[str, object]] = []
    for segment in _split_rows_into_segments(collapsed_probe_rows, max_frame_gap=max(sample_interval, 1)):
        segment_meta: list[dict[str, object]] = []
        for row in segment:
            is_supported = _ball_row_is_player_supported(row, player_rows_by_frame)
            is_non_edge = not _row_is_edge_heavy_ball(row)
            segment_meta.append(
                {
                    "row": row,
                    "isAnchored": is_supported or is_non_edge,
                }
            )

        for index, meta in enumerate(segment_meta):
            row = meta["row"]
            if meta["isAnchored"]:
                filtered_rows.append(row)
                continue
            previous_meta = segment_meta[index - 1] if index > 0 else None
            next_meta = segment_meta[index + 1] if index + 1 < len(segment_meta) else None
            if previous_meta is None or next_meta is None:
                continue
            if not previous_meta["isAnchored"] or not next_meta["isAnchored"]:
                continue
            if not _bridge_frame_is_eligible(
                [item["row"] for item in segment_meta],
                index,
                player_rows_by_frame=player_rows_by_frame,
                sample_interval=sample_interval,
            ):
                continue
            filtered_rows.append(row)

    return _best_ball_rows_by_frame(filtered_rows)


def _touchline_candidate_segments(
    rows: list[dict[str, object]],
    *,
    run_start_frame: int,
    run_end_frame: int,
    sample_interval: int,
) -> list[list[dict[str, object]]]:
    candidate_rows = [
        dict(row)
        for row in rows
        if isinstance(row, dict)
        and (frame_id := _extract_frame_id(row)) is not None
        and run_start_frame <= frame_id <= run_end_frame
    ]
    return _split_rows_into_segments(candidate_rows, max_frame_gap=max(sample_interval, 1))


def _replacement_reconnect_ok(
    boundary_row: dict[str, object] | None,
    candidate_row: dict[str, object] | None,
    *,
    sample_interval: int,
    is_before: bool,
) -> bool:
    if boundary_row is None or candidate_row is None:
        return True
    boundary_frame = _extract_frame_id(boundary_row)
    candidate_frame = _extract_frame_id(candidate_row)
    if boundary_frame is None or candidate_frame is None:
        return False
    if is_before and candidate_frame <= boundary_frame:
        return False
    if not is_before and candidate_frame >= boundary_frame:
        return False
    frame_gap = abs(candidate_frame - boundary_frame)
    if frame_gap > sample_interval:
        return True
    boundary_center = _row_center(boundary_row)
    candidate_center = _row_center(candidate_row)
    if boundary_center is None or candidate_center is None:
        return False
    return hypot(
        float(candidate_center[0]) - float(boundary_center[0]),
        float(candidate_center[1]) - float(boundary_center[1]),
    ) <= MAX_COHERENT_BALL_STEP_DISTANCE


def _candidate_integrity_ok(
    candidate_rows: list[dict[str, object]],
    *,
    run_start_frame: int,
    run_end_frame: int,
) -> bool:
    frame_ids = [
        frame_id
        for frame_id in (_extract_frame_id(row) for row in candidate_rows)
        if frame_id is not None
    ]
    if not frame_ids or frame_ids != sorted(frame_ids) or len(frame_ids) != len(set(frame_ids)):
        return False
    return min(frame_ids) >= run_start_frame and max(frame_ids) <= run_end_frame


def _evaluate_touchline_candidate(
    candidate_rows: list[dict[str, object]],
    *,
    candidate_source: str,
    run_rows: list[dict[str, object]],
    previous_row: dict[str, object] | None,
    next_row: dict[str, object] | None,
    sample_interval: int,
) -> dict[str, object]:
    run_frame_ids = {
        frame_id
        for frame_id in (_extract_frame_id(row) for row in run_rows)
        if frame_id is not None
    }
    run_motion = _segment_motion_summary(run_rows)
    candidate_motion = _segment_motion_summary(candidate_rows)
    coverage_ratio = (
        len(run_frame_ids & {frame_id for frame_id in (_extract_frame_id(row) for row in candidate_rows) if frame_id is not None})
        / len(run_frame_ids)
        if run_frame_ids
        else 0.0
    )
    edge_share_delta = round(
        _safe_float(run_motion.get("edgeShare"), 0.0) - _safe_float(candidate_motion.get("edgeShare"), 0.0),
        3,
    )
    reconnect_before_ok = _replacement_reconnect_ok(
        previous_row,
        candidate_rows[0] if candidate_rows else None,
        sample_interval=sample_interval,
        is_before=True,
    )
    reconnect_after_ok = _replacement_reconnect_ok(
        next_row,
        candidate_rows[-1] if candidate_rows else None,
        sample_interval=sample_interval,
        is_before=False,
    )
    reconnect_ok = reconnect_before_ok and reconnect_after_ok
    integrity_ok = _candidate_integrity_ok(
        candidate_rows,
        run_start_frame=_extract_frame_id(run_rows[0]) or 0,
        run_end_frame=_extract_frame_id(run_rows[-1]) or 0,
    )

    rejection_reason: str | None = None
    if edge_share_delta < TOUCHLINE_REPLACEMENT_MIN_EDGE_SHARE_DELTA:
        rejection_reason = TOUCHLINE_REPLACEMENT_REJECTION_EDGE_SHARE
    elif not (
        bool(candidate_motion.get("viable"))
        or bool(candidate_motion.get("nearViable"))
    ):
        rejection_reason = TOUCHLINE_REPLACEMENT_REJECTION_NOT_VIABLE
    elif coverage_ratio < TOUCHLINE_REPLACEMENT_MIN_COVERAGE_RATIO:
        rejection_reason = TOUCHLINE_REPLACEMENT_REJECTION_COVERAGE
    elif not reconnect_ok:
        rejection_reason = TOUCHLINE_REPLACEMENT_REJECTION_RECONNECT
    elif not integrity_ok:
        rejection_reason = TOUCHLINE_REPLACEMENT_REJECTION_INTEGRITY

    return {
        "candidateRows": _best_ball_rows_by_frame(candidate_rows),
        "candidateSourceUsed": candidate_source,
        "candidateFrameCount": len(_best_ball_rows_by_frame(candidate_rows)),
        "replacementCoverageRatio": round(float(coverage_ratio), 3),
        "replacementEdgeShareDelta": edge_share_delta,
        "candidateViable": bool(candidate_motion.get("viable")),
        "candidateNearViable": bool(candidate_motion.get("nearViable")),
        "reconnectBeforeOk": reconnect_before_ok,
        "reconnectAfterOk": reconnect_after_ok,
        "reconnectOk": reconnect_ok,
        "accepted": rejection_reason is None,
        "rejectionReason": rejection_reason,
    }


def _best_rejected_candidate(candidates: list[dict[str, object]]) -> dict[str, object] | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda candidate: (
            _safe_float(candidate.get("replacementCoverageRatio"), 0.0),
            _safe_float(candidate.get("replacementEdgeShareDelta"), 0.0),
            _safe_int(candidate.get("candidateFrameCount"), 0),
        ),
    )


def _choose_touchline_replacement_candidate(
    *,
    run_rows: list[dict[str, object]],
    probe_filtered_rows: list[dict[str, object]],
    probe_raw_rows: list[dict[str, object]],
    player_rows_by_frame: dict[int, list[dict[str, object]]],
    sample_interval: int,
    previous_row: dict[str, object] | None,
    next_row: dict[str, object] | None,
) -> dict[str, object]:
    run_start_frame = _extract_frame_id(run_rows[0]) or 0
    run_end_frame = _extract_frame_id(run_rows[-1]) or 0
    raw_refiltered_rows = _filter_probe_rows_for_replacement(
        probe_raw_rows,
        player_rows_by_frame=player_rows_by_frame,
        sample_interval=sample_interval,
    )
    candidate_sources = (
        (TOUCHLINE_REPLACEMENT_CANDIDATE_FILTERED, probe_filtered_rows),
        (TOUCHLINE_REPLACEMENT_CANDIDATE_RAW_REFILTERED, raw_refiltered_rows),
    )

    best_rejected: dict[str, object] | None = None
    for candidate_source, source_rows in candidate_sources:
        evaluated_candidates = [
            _evaluate_touchline_candidate(
                candidate_segment,
                candidate_source=candidate_source,
                run_rows=run_rows,
                previous_row=previous_row,
                next_row=next_row,
                sample_interval=sample_interval,
            )
            for candidate_segment in _touchline_candidate_segments(
                source_rows,
                run_start_frame=run_start_frame,
                run_end_frame=run_end_frame,
                sample_interval=sample_interval,
            )
        ]
        accepted_candidates = [candidate for candidate in evaluated_candidates if candidate.get("accepted")]
        if accepted_candidates:
            return max(
                accepted_candidates,
                key=lambda candidate: (
                    _safe_float(candidate.get("replacementCoverageRatio"), 0.0),
                    _safe_float(candidate.get("replacementEdgeShareDelta"), 0.0),
                    _safe_int(candidate.get("candidateFrameCount"), 0),
                ),
            )
        source_best_rejected = _best_rejected_candidate(evaluated_candidates)
        if source_best_rejected is not None and best_rejected is None:
            best_rejected = source_best_rejected

    if best_rejected is not None:
        return best_rejected
    return {
        "candidateRows": [],
        "candidateSourceUsed": None,
        "candidateFrameCount": 0,
        "replacementCoverageRatio": 0.0,
        "replacementEdgeShareDelta": 0.0,
        "candidateViable": False,
        "candidateNearViable": False,
        "reconnectBeforeOk": True,
        "reconnectAfterOk": True,
        "reconnectOk": True,
        "accepted": False,
        "rejectionReason": TOUCHLINE_REPLACEMENT_REJECTION_NO_CANDIDATE,
    }


def _final_edge_run_summaries(rows: list[dict[str, object]]) -> list[dict[str, int]]:
    edge_runs: list[dict[str, int]] = []
    current_run: list[dict[str, object]] = []
    for row in _best_ball_rows_by_frame(rows):
        if _row_is_edge_heavy_ball(row):
            current_run.append(row)
            continue
        if current_run:
            edge_runs.append(
                _run_summary(
                    run_rows=current_run,
                    kept_count=len(current_run),
                    dropped_count=0,
                )
            )
            current_run = []
    if current_run:
        edge_runs.append(
            _run_summary(
                run_rows=current_run,
                kept_count=len(current_run),
                dropped_count=0,
            )
        )
    return edge_runs


def _apply_touchline_probe_replacement(
    accepted_rows: list[dict[str, object]],
    *,
    profile_name: str | None,
    source_clip_id: str | None,
    mode: str,
    min_run_length: int,
    probe_filtered_rows: list[dict[str, object]],
    probe_raw_rows: list[dict[str, object]],
    player_rows_by_frame: dict[int, list[dict[str, object]]],
    sample_interval: int,
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object]]:
    diagnostics = _default_diagnostics(
        profile_name=profile_name,
        config={
            "mode": mode,
            "keepEvery": 0,
            "minRunLength": min_run_length,
            "guardFrameCount": 0,
        },
        source_clip_id=source_clip_id,
    )
    replacement_diagnostics = _default_replacement_diagnostics(
        profile_name=profile_name,
        mode=mode,
        source_clip_id=source_clip_id,
    )

    repaired_rows: list[dict[str, object]] = []
    current_edge_run: list[dict[str, object]] = []

    def flush_edge_run() -> None:
        nonlocal current_edge_run
        if not current_edge_run:
            return

        edge_heavy_share = sum(1 for row in current_edge_run if _row_is_edge_heavy_ball(row)) / len(current_edge_run)
        player_supported_share = (
            sum(1 for row in current_edge_run if _ball_row_is_player_supported(row, player_rows_by_frame))
            / len(current_edge_run)
        )
        suspect_run = (
            len(current_edge_run) >= min_run_length
            and edge_heavy_share >= TOUCHLINE_REPLACEMENT_MIN_EDGE_SHARE
            and player_supported_share >= TOUCHLINE_REPLACEMENT_MIN_SUPPORTED_SHARE
            and _run_overlaps_dominant_touchline_window(current_edge_run)
        )
        if not suspect_run:
            repaired_rows.extend(current_edge_run)
            current_edge_run = []
            return

        replacement_diagnostics["runsConsidered"] += 1
        previous_row = repaired_rows[-1] if repaired_rows else None
        run_start_frame = _extract_frame_id(current_edge_run[0]) or 0
        run_end_frame = _extract_frame_id(current_edge_run[-1]) or 0
        next_row = None
        candidate = _choose_touchline_replacement_candidate(
            run_rows=current_edge_run,
            probe_filtered_rows=probe_filtered_rows,
            probe_raw_rows=probe_raw_rows,
            player_rows_by_frame=player_rows_by_frame,
            sample_interval=sample_interval,
            previous_row=previous_row,
            next_row=next_row,
        )
        run_diagnostic = {
            "startFrame": run_start_frame,
            "endFrame": run_end_frame,
            "runLength": len(current_edge_run),
            "edgeHeavyShare": round(float(edge_heavy_share), 3),
            "playerSupportedShare": round(float(player_supported_share), 3),
            "candidateSourceUsed": candidate.get("candidateSourceUsed"),
            "candidateFrameCount": _safe_int(candidate.get("candidateFrameCount"), 0),
            "replacementCoverageRatio": round(_safe_float(candidate.get("replacementCoverageRatio"), 0.0), 3),
            "replacementEdgeShareDelta": round(_safe_float(candidate.get("replacementEdgeShareDelta"), 0.0), 3),
            "candidateViable": bool(candidate.get("candidateViable")),
            "candidateNearViable": bool(candidate.get("candidateNearViable")),
            "reconnectBeforeOk": bool(candidate.get("reconnectBeforeOk", True)),
            "reconnectAfterOk": bool(candidate.get("reconnectAfterOk", True)),
            "reconnectOk": bool(candidate.get("reconnectOk", True)),
            "accepted": bool(candidate.get("accepted")),
            "rejectionReason": candidate.get("rejectionReason"),
        }
        replacement_diagnostics["runDiagnostics"].append(run_diagnostic)
        if candidate.get("accepted"):
            candidate_rows = [dict(row) for row in candidate.get("candidateRows", [])]
            repaired_rows.extend(candidate_rows)
            replacement_diagnostics["applied"] = True
            replacement_diagnostics["runsAccepted"] += 1
            candidate_source = str(candidate.get("candidateSourceUsed") or "").strip()
            if candidate_source:
                replacement_diagnostics["acceptedCandidateSourceCounts"][candidate_source] = (
                    _safe_int(replacement_diagnostics["acceptedCandidateSourceCounts"].get(candidate_source), 0) + 1
                )
            diagnostics["applied"] = True
        else:
            repaired_rows.extend(current_edge_run)
            replacement_diagnostics["runsRejected"] += 1
            rejection_reason = str(candidate.get("rejectionReason") or "").strip()
            if rejection_reason:
                replacement_diagnostics["replacementRejectionReasonCounts"][rejection_reason] = (
                    _safe_int(replacement_diagnostics["replacementRejectionReasonCounts"].get(rejection_reason), 0) + 1
                )
        current_edge_run = []

    for row in _best_ball_rows_by_frame(accepted_rows):
        if _row_is_edge_heavy_ball(row):
            current_edge_run.append(row)
            continue
        flush_edge_run()
        repaired_rows.append(dict(row))
    flush_edge_run()

    repaired_rows = _best_ball_rows_by_frame(repaired_rows)
    coverage_ratios = [
        _safe_float(run.get("replacementCoverageRatio"), 0.0)
        for run in replacement_diagnostics["runDiagnostics"]
        if isinstance(run, dict)
    ]
    replacement_diagnostics["medianReplacementCoverageRatio"] = round(
        float(median(coverage_ratios)) if coverage_ratios else 0.0,
        3,
    )
    diagnostics["retainedAcceptedEdgeFrames"] = len(repaired_rows)
    diagnostics["edgeRuns"] = _final_edge_run_summaries(repaired_rows)
    return repaired_rows, diagnostics, replacement_diagnostics


def apply_source_conditioned_edge_share_repair(
    accepted_rows: list[dict[str, object]],
    *,
    source_clip_id: str | None = None,
    edge_share_repair_profile: str | None = None,
    player_rows: list[dict[str, object]] | None = None,
    sample_interval: int | None = None,
    probe_filtered_rows: list[dict[str, object]] | None = None,
    probe_raw_rows: list[dict[str, object]] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object]]:
    config = get_source_edge_share_repair_config(edge_share_repair_profile)
    diagnostics = _default_diagnostics(
        profile_name=edge_share_repair_profile,
        config=config,
        source_clip_id=source_clip_id,
    )
    replacement_diagnostics = _default_replacement_diagnostics(
        profile_name=edge_share_repair_profile,
        mode=str(config.get("mode")) if isinstance(config, dict) and config.get("mode") is not None else None,
        source_clip_id=source_clip_id,
    )
    normalized_rows = _best_ball_rows_by_frame(
        [dict(row) for row in accepted_rows if isinstance(row, dict)]
    )
    player_rows_by_frame = _group_rows_by_frame(
        [
            dict(row)
            for row in (player_rows or [])
            if isinstance(row, dict) and row.get("Entity_Type") != "ball"
        ]
    )
    effective_sample_interval = max(_safe_int(sample_interval, 1), 1)

    if not normalized_rows:
        return normalized_rows, diagnostics, replacement_diagnostics

    if not config or source_clip_id != SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP:
        supported_ratio, unsupported_edge_frames = _accepted_support_metrics(
            normalized_rows,
            player_rows_by_frame=player_rows_by_frame,
        )
        diagnostics["supportedAcceptedBallRatio"] = supported_ratio
        diagnostics["unsupportedAcceptedEdgeFrames"] = unsupported_edge_frames
        return normalized_rows, diagnostics, replacement_diagnostics

    mode = str(config.get("mode") or UNIFORM_EDGE_RUN_THIN_MODE)
    min_run_length = max(_safe_int(config.get("minRunLength"), 1), 1)
    if mode in {TOUCHLINE_ACQUISITION_UPGRADE_MODE, TOUCHLINE_ACQUISITION_REOPEN_MODE}:
        repaired_rows = normalized_rows
    elif mode == TOUCHLINE_PROBE_REPLACE_MODE:
        repaired_rows, diagnostics, replacement_diagnostics = _apply_touchline_probe_replacement(
            normalized_rows,
            profile_name=edge_share_repair_profile,
            source_clip_id=source_clip_id,
            mode=mode,
            min_run_length=min_run_length,
            probe_filtered_rows=[dict(row) for row in (probe_filtered_rows or []) if isinstance(row, dict)],
            probe_raw_rows=[dict(row) for row in (probe_raw_rows or []) if isinstance(row, dict)],
            player_rows_by_frame=player_rows_by_frame,
            sample_interval=effective_sample_interval,
        )
    else:
        keep_every = max(_safe_int(config.get("keepEvery"), 1), 1)
        guard_frame_count = max(_safe_int(config.get("guardFrameCount"), 0), 0)

        repaired_rows: list[dict[str, object]] = []
        current_edge_run: list[dict[str, object]] = []

        def flush_edge_run() -> None:
            nonlocal current_edge_run
            if not current_edge_run:
                return
            if len(current_edge_run) < min_run_length:
                repaired_rows.extend(current_edge_run)
                diagnostics["retainedAcceptedEdgeFrames"] += len(current_edge_run)
                diagnostics["edgeRuns"].append(
                    _run_summary(
                        run_rows=current_edge_run,
                        kept_count=len(current_edge_run),
                        dropped_count=0,
                    )
                )
                current_edge_run = []
                return

            if mode == UNIFORM_EDGE_RUN_THIN_MODE:
                kept_rows, run_summary = _apply_uniform_edge_run_thin(
                    current_edge_run,
                    keep_every=keep_every,
                )
            else:
                kept_rows, run_summary = _apply_support_guarded_edge_run_thin(
                    current_edge_run,
                    keep_every=keep_every,
                    guard_frame_count=guard_frame_count,
                    player_rows_by_frame=player_rows_by_frame,
                    sample_interval=effective_sample_interval,
                )

            repaired_rows.extend(kept_rows)
            diagnostics["applied"] = diagnostics["applied"] or run_summary["droppedFrameCount"] > 0
            if run_summary["droppedFrameCount"] > 0:
                diagnostics["thinnedEdgeRuns"] += 1
            diagnostics["droppedAcceptedEdgeFrames"] += run_summary["droppedFrameCount"]
            diagnostics["retainedAcceptedEdgeFrames"] += run_summary["keptFrameCount"]
            diagnostics["preservedBoundaryFrames"] += run_summary.get("preservedBoundaryFrameCount", 0)
            diagnostics["preservedSupportedFrames"] += run_summary.get("preservedSupportedFrameCount", 0)
            diagnostics["preservedBridgeFrames"] += run_summary.get("preservedBridgeFrameCount", 0)
            diagnostics["droppedInteriorUnsupportedFrames"] += run_summary.get(
                "droppedInteriorUnsupportedFrameCount",
                0,
            )
            diagnostics["edgeRuns"].append(run_summary)
            current_edge_run = []

        for row in normalized_rows:
            if _row_is_edge_heavy_ball(row):
                current_edge_run.append(row)
                continue
            flush_edge_run()
            repaired_rows.append(row)

        flush_edge_run()
        repaired_rows.sort(key=lambda row: _extract_frame_id(row) or -1)

    supported_ratio, unsupported_edge_frames = _accepted_support_metrics(
        repaired_rows,
        player_rows_by_frame=player_rows_by_frame,
    )
    diagnostics["supportedAcceptedBallRatio"] = supported_ratio
    diagnostics["unsupportedAcceptedEdgeFrames"] = unsupported_edge_frames
    return repaired_rows, diagnostics, replacement_diagnostics
