from __future__ import annotations

import json
from math import gcd, hypot
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from .analytics import (
    MAX_OWNER_DISTANCE,
    add_tracking_row,
    apply_possession_to_frames,
    apply_match_state_continuity,
    assign_ball_possession,
    build_accepted_match_state,
    build_formation_timeline,
    build_shot_analytics,
    detect_events,
    normalize_tracking_rows,
    summarize_match,
)
from .schemas import BallOwnership, ColorClusterSummary, DetectedEvent, FormationSegment, FrameData, MatchConfig, MatchSummary, ShotAnalytics
from .proof_runtime import (
    local_boto3_object_loader,
    load_proof_runtime_options,
    materialize_proof_runtime_options,
)
from .storage import Storage
from .team_classification import classify_player_row_by_cluster, classify_player_rows_by_cluster, cluster_result_from_summaries, cluster_track_colors
from .video_pipeline import process_video_input, reprocess_for_change
from backend.run_guerilla import _best_ball_rows_by_frame, _summarize_ball_truth_layer, split_ball_rows_into_segments

if TYPE_CHECKING:
    from .remote_worker import ProcessorResultStream


BALL_PIPELINE_TRACE_STAGE_ORDER = [
    "processVideoPrimary",
    "processVideoRecovery",
    "processVideoReturnedRows",
    "persistRawRows",
    "normalizedFrames",
    "possessionOutputs",
    "eventOutputs",
]
MATCH_STATE_EDGE_MARGIN = 5.0
WORKER_HEARTBEAT_INTERVAL_SECONDS = 30.0
RUNTIME_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "release" / "v7.3.json"
RUNTIME_ARTIFACT_ROOT = Path(__file__).resolve().parents[2]
WORKER_STAGE_MESSAGES = {
    "modelLoad": "Loading detector",
    "videoOpenAndHomography": "Opening video and resolving homography",
    "trackingPass": "Running tracking pass",
    "probeObservedPass": "Running probe observed pass",
    "recoverySelection": "Running recovery profiles",
    "truthLayerFinalize": "Building truth layers",
    "resultSerialize": "Persisting outputs",
}
WORKER_STAGE_PROGRESS = {
    "modelLoad": 0.05,
    "videoOpenAndHomography": 0.10,
    "trackingPass": 0.35,
    "probeObservedPass": 0.55,
    "recoverySelection": 0.75,
    "truthLayerFinalize": 0.90,
    "resultSerialize": 0.98,
}


def _trace_stage_from_rows(stage: str, rows: list[dict]) -> dict[str, object]:
    ball_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
    player_rows = [row for row in rows if row.get("Entity_Type") != "ball"]
    ball_frames = sorted({int(row.get("Frame_ID", 0)) for row in ball_rows})
    frame_ids = {int(row.get("Frame_ID", 0)) for row in rows}
    return {
        "stage": stage,
        "ballRowCount": len(ball_rows),
        "ballFrameCount": len(ball_frames),
        "playerRowCount": len(player_rows),
        "frameCount": len(frame_ids),
        "trackedPossessionFrames": 0,
        "controlledPossessionFrames": 0,
        "eventCount": 0,
        "eventTypes": {},
        "firstBallFrame": ball_frames[0] if ball_frames else None,
        "lastBallFrame": ball_frames[-1] if ball_frames else None,
    }


def _trace_stage_from_frames(stage: str, frames: list[FrameData]) -> dict[str, object]:
    ball_frames = [frame.frameId for frame in frames if frame.ball is not None]
    player_row_count = sum(len(frame.myTeam) + len(frame.enemies) + len(frame.unassignedPlayers) for frame in frames)
    return {
        "stage": stage,
        "ballRowCount": len(ball_frames),
        "ballFrameCount": len(ball_frames),
        "playerRowCount": player_row_count,
        "frameCount": len(frames),
        "trackedPossessionFrames": 0,
        "controlledPossessionFrames": 0,
        "eventCount": 0,
        "eventTypes": {},
        "firstBallFrame": min(ball_frames) if ball_frames else None,
        "lastBallFrame": max(ball_frames) if ball_frames else None,
    }


def _build_empty_ball_pipeline_trace() -> dict[str, object]:
    return {
        "traceVersion": 1,
        "matchId": None,
        "jobId": None,
        "processingBackend": None,
        "inputMode": None,
        "videoPath": None,
        "workerPath": None,
        "detectorModelPath": None,
        "detectorModelName": None,
        "primaryModelPath": None,
        "primaryModelName": None,
        "primaryAcquisitionMode": None,
        "auxiliaryBallModelPath": None,
        "auxiliaryBallModelName": None,
        "auxiliaryBallModelProfile": None,
        "trackingModelPath": None,
        "trackingDetectorProfile": None,
        "probeModelPath": None,
        "probeDetectorProfile": None,
        "recoveryModelPath": None,
        "recoveryDetectorProfile": None,
        "directSeedRetryPolicy": None,
        "directSeedRetryScales": [],
        "runtimeFingerprint": None,
        "phaseTimings": _empty_phase_timings(),
        "stages": [],
    }


def _empty_phase_timings() -> dict[str, float]:
    return {
        "modelLoadSeconds": 0.0,
        "videoOpenAndHomographySeconds": 0.0,
        "trackingPassSeconds": 0.0,
        "probeObservedPassSeconds": 0.0,
        "recoverySelectionSeconds": 0.0,
        "truthLayerFinalizeSeconds": 0.0,
        "resultSerializeSeconds": 0.0,
        "totalProcessVideoSeconds": 0.0,
    }


def _normalize_phase_timings(payload: object) -> dict[str, float]:
    normalized = _empty_phase_timings()
    if not isinstance(payload, dict):
        return normalized
    for key in normalized:
        value = payload.get(key)
        try:
            normalized[key] = max(float(value), 0.0)
        except (TypeError, ValueError):
            continue
    return normalized


def _normalize_runtime_fingerprint(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None

    normalized: dict[str, object] = {}
    for key in ("configuredImageName", "imageTag", "gitSha", "buildLabel"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()

    dependencies = payload.get("handlerDependencyVersions")
    if isinstance(dependencies, dict):
        normalized_dependencies: dict[str, str] = {}
        for dependency_name in ("python", "opencv", "ultralytics"):
            dependency_version = dependencies.get(dependency_name)
            if isinstance(dependency_version, str) and dependency_version.strip():
                normalized_dependencies[dependency_name] = dependency_version.strip()
        if normalized_dependencies:
            normalized["handlerDependencyVersions"] = normalized_dependencies

    return normalized or None


def _normalize_ball_pipeline_trace(payload: object) -> dict[str, object]:
    trace = _build_empty_ball_pipeline_trace()
    if not isinstance(payload, dict):
        return trace

    for key in (
        "traceVersion",
        "matchId",
        "jobId",
        "processingBackend",
        "inputMode",
        "videoPath",
        "workerPath",
        "detectorModelPath",
        "detectorModelName",
        "primaryModelPath",
        "primaryModelName",
        "primaryAcquisitionMode",
        "auxiliaryBallModelPath",
        "auxiliaryBallModelName",
        "auxiliaryBallModelProfile",
        "trackingModelPath",
        "trackingDetectorProfile",
        "probeModelPath",
        "probeDetectorProfile",
        "recoveryModelPath",
        "recoveryDetectorProfile",
        "directSeedRetryPolicy",
    ):
        if key in payload:
            trace[key] = payload.get(key)
    retry_scales = payload.get("directSeedRetryScales")
    if isinstance(retry_scales, list):
        trace["directSeedRetryScales"] = [
            int(scale)
            for scale in retry_scales
            if isinstance(scale, (int, float)) and not isinstance(scale, bool)
        ]
    runtime_fingerprint = _normalize_runtime_fingerprint(payload.get("runtimeFingerprint"))
    if runtime_fingerprint is not None:
        trace["runtimeFingerprint"] = runtime_fingerprint
    trace["phaseTimings"] = _normalize_phase_timings(payload.get("phaseTimings"))

    stages = payload.get("stages")
    if not isinstance(stages, list):
        return trace

    normalized_stages: list[dict[str, object]] = []
    for stage_payload in stages:
        if not isinstance(stage_payload, dict):
            continue
        stage_name = stage_payload.get("stage")
        if not isinstance(stage_name, str):
            continue
        normalized_stages.append(
            {
                "stage": stage_name,
                "ballRowCount": int(stage_payload.get("ballRowCount", 0) or 0),
                "ballFrameCount": int(stage_payload.get("ballFrameCount", 0) or 0),
                "playerRowCount": int(stage_payload.get("playerRowCount", 0) or 0),
                "frameCount": int(stage_payload.get("frameCount", 0) or 0),
                "trackedPossessionFrames": int(stage_payload.get("trackedPossessionFrames", 0) or 0),
                "controlledPossessionFrames": int(stage_payload.get("controlledPossessionFrames", 0) or 0),
                "eventCount": int(stage_payload.get("eventCount", 0) or 0),
                "eventTypes": dict(stage_payload.get("eventTypes", {}) or {}),
                "firstBallFrame": stage_payload.get("firstBallFrame"),
                "lastBallFrame": stage_payload.get("lastBallFrame"),
            }
        )
    trace["stages"] = normalized_stages
    return trace


def _upsert_ball_pipeline_stage(trace: dict[str, object], stage_payload: dict[str, object]) -> None:
    stages = trace.setdefault("stages", [])
    if not isinstance(stages, list):
        trace["stages"] = []
        stages = trace["stages"]
    for index, existing in enumerate(stages):
        if isinstance(existing, dict) and existing.get("stage") == stage_payload["stage"]:
            stages[index] = stage_payload
            return
    stages.append(stage_payload)


def _finalize_ball_pipeline_trace(
    *,
    trace: dict[str, object],
    match_id: str,
    job_id: str,
    processing_backend: str,
    input_mode: str,
    video_path: Path | None,
    worker_path: str,
) -> dict[str, object]:
    trace["traceVersion"] = 1
    trace["matchId"] = match_id
    trace["jobId"] = job_id
    trace["processingBackend"] = processing_backend
    trace["inputMode"] = input_mode
    trace["videoPath"] = str(video_path) if video_path is not None else None
    trace["workerPath"] = worker_path
    stages = trace.get("stages")
    if not isinstance(stages, list):
        trace["stages"] = []
        stages = trace["stages"]
    ordered_stages = []
    for stage_name in BALL_PIPELINE_TRACE_STAGE_ORDER:
        stage_payload = next(
            (
                stage
                for stage in stages
                if isinstance(stage, dict) and stage.get("stage") == stage_name
            ),
            None,
        )
        if stage_payload is None:
            if stage_name in {"persistRawRows", "processVideoRecovery", "processVideoReturnedRows"}:
                stage_payload = _trace_stage_from_rows(stage_name, [])
            else:
                stage_payload = {
                    "stage": stage_name,
                    "ballRowCount": 0,
                    "ballFrameCount": 0,
                    "playerRowCount": 0,
                    "frameCount": 0,
                    "trackedPossessionFrames": 0,
                    "controlledPossessionFrames": 0,
                    "eventCount": 0,
                    "eventTypes": {},
                    "firstBallFrame": None,
                    "lastBallFrame": None,
                }
        ordered_stages.append(stage_payload)
    trace["stages"] = ordered_stages
    return trace


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
            frame_id = int(row.get("Frame_ID"))
            x = float(row.get("X"))
            y = float(row.get("Y"))
            confidence = float(row.get("Conf", 0.0))
        except (TypeError, ValueError):
            continue
        normalized[frame_id] = {"x": x, "y": y, "confidence": confidence}
    return normalized


def _frame_ball_is_player_supported(frame: FrameData, ball_point: dict[str, float]) -> bool:
    for player in [*frame.myTeam, *frame.enemies, *frame.unassignedPlayers]:
        if hypot(float(player.x) - float(ball_point["x"]), float(player.y) - float(ball_point["y"])) <= MAX_OWNER_DISTANCE:
            return True
    return False


def _frame_ball_is_edge_heavy(ball_point: dict[str, float]) -> bool:
    x = float(ball_point["x"])
    y = float(ball_point["y"])
    return (
        x <= MATCH_STATE_EDGE_MARGIN
        or x >= (100.0 - MATCH_STATE_EDGE_MARGIN)
        or y <= MATCH_STATE_EDGE_MARGIN
        or y >= (100.0 - MATCH_STATE_EDGE_MARGIN)
    )


def _normalize_match_state_evidence(
    frames: list[FrameData],
    *,
    ball_truth_layers: dict[str, object] | None = None,
    match_state_evidence: object = None,
) -> dict[str, object]:
    if isinstance(match_state_evidence, dict):
        frames_payload = match_state_evidence.get("frames")
        if isinstance(frames_payload, list):
            normalized_frames: list[dict[str, object]] = []
            for item in frames_payload:
                if not isinstance(item, dict):
                    continue
                normalized_frames.append(
                    {
                        "frameId": int(item.get("frameId", 0) or 0),
                        "hasAcceptedBall": bool(item.get("hasAcceptedBall", False)),
                        "acceptedSource": str(item.get("acceptedSource", "none")),
                        "playerSupported": bool(item.get("playerSupported", False)),
                        "edgeHeavy": bool(item.get("edgeHeavy", False)),
                        "reasonCodes": [
                            str(code)
                            for code in item.get("reasonCodes", [])
                            if isinstance(code, str) and code.strip()
                        ],
                    }
                )
            return {"frames": normalized_frames}

    observed_rows_by_frame = _ball_rows_by_frame(ball_truth_layers, "observedBall")
    inferred_rows_by_frame = _ball_rows_by_frame(ball_truth_layers, "inferredBall")
    accepted_rows_by_frame = _ball_rows_by_frame(ball_truth_layers, "acceptedBall")
    normalized_frames: list[dict[str, object]] = []
    for frame in frames:
        accepted_point = accepted_rows_by_frame.get(frame.frameId)
        accepted_source = "none"
        if frame.frameId in observed_rows_by_frame:
            accepted_source = "observed"
        elif frame.frameId in inferred_rows_by_frame:
            accepted_source = "inferred"
        elif frame.ball is not None:
            accepted_source = "observed"
            accepted_point = {
                "x": float(frame.ball.x),
                "y": float(frame.ball.y),
                "confidence": float(frame.ball.confidence),
            }
        player_supported = bool(accepted_point) and _frame_ball_is_player_supported(frame, accepted_point)
        edge_heavy = bool(accepted_point) and _frame_ball_is_edge_heavy(accepted_point)
        reason_codes = ["accepted_ball" if accepted_point is not None else "no_accepted_ball"]
        if accepted_source == "observed":
            reason_codes.append("observed_ball")
        elif accepted_source == "inferred":
            reason_codes.append("inferred_ball")
        if player_supported:
            reason_codes.append("player_supported")
        if edge_heavy:
            reason_codes.append("edge_heavy")
        normalized_frames.append(
            {
                "frameId": frame.frameId,
                "hasAcceptedBall": accepted_point is not None,
                "acceptedSource": accepted_source,
                "playerSupported": player_supported,
                "edgeHeavy": edge_heavy,
                "reasonCodes": reason_codes,
            }
        )
    return {"frames": normalized_frames}


def _load_saved_ball_truth_layers(storage: Storage, match_id: str) -> dict[str, object] | None:
    path = storage._match_dir(match_id) / "ball_truth_layers.json"
    if not path.exists():
        return None
    try:
        payload = storage.load_analysis_artifact(match_id, "ball_truth_layers")
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _compute_outputs_and_match_state(
    frames: list[FrameData],
    *,
    attack_direction: str = "left_to_right",
    ball_truth_layers: dict[str, object] | None = None,
    match_state_evidence: dict[str, object] | None = None,
) -> tuple[
    list[FrameData],
    MatchSummary,
    list[DetectedEvent],
    list[BallOwnership],
    list[FormationSegment],
    list[ShotAnalytics],
    dict[str, object],
]:
    baseline_assignments = assign_ball_possession(frames)
    accepted_match_state = build_accepted_match_state(
        frames,
        baseline_assignments,
        ball_truth_layers=ball_truth_layers,
        match_state_evidence=match_state_evidence,
    )
    assignments, continuity_applied_frames = apply_match_state_continuity(
        baseline_assignments,
        accepted_match_state,
    )
    enriched_frames: list[FrameData] = apply_possession_to_frames(frames, assignments)
    formation_timeline = build_formation_timeline(frames, attack_direction=attack_direction)
    events = detect_events(frames, assignments, attack_direction=attack_direction)
    shots = build_shot_analytics(frames, events, attack_direction=attack_direction)
    summary = summarize_match(frames, assignments, shots, events, attack_direction=attack_direction)
    accepted_match_state_payload = {
        "stateContinuityAppliedFrames": continuity_applied_frames,
        "frames": [frame.model_dump(mode="json") for frame in accepted_match_state],
    }
    return enriched_frames, summary, events, assignments, formation_timeline, shots, accepted_match_state_payload


def _normalize_track_colors(track_colors_payload: object) -> dict[int, list[tuple[float, float, float]]]:
    if not isinstance(track_colors_payload, dict):
        return {}

    normalized: dict[int, list[tuple[float, float, float]]] = {}
    for track_id, samples in track_colors_payload.items():
        if not isinstance(samples, list):
            continue
        parsed_samples: list[tuple[float, float, float]] = []
        for sample in samples:
            if not isinstance(sample, (list, tuple)) or len(sample) != 3:
                continue
            parsed_samples.append((float(sample[0]), float(sample[1]), float(sample[2])))
        if parsed_samples:
            normalized[int(track_id)] = parsed_samples
    return normalized


def _resolve_selected_cluster(config: MatchConfig, team_clusters: list[ColorClusterSummary]) -> tuple[int | None, bool]:
    if not team_clusters:
        return None, False
    if config.myTeamCluster is not None:
        if any(cluster.clusterId == config.myTeamCluster for cluster in team_clusters):
            return config.myTeamCluster, False
        return None, True
    return None, True


def _classify_video_rows(
    rows: list[dict],
    config: MatchConfig,
    team_clusters: list[ColorClusterSummary],
) -> tuple[list[dict], bool]:
    selected_cluster, requires_team_selection = _resolve_selected_cluster(config, team_clusters)
    if not team_clusters:
        return [dict(row) for row in rows], False

    if selected_cluster is None:
        return [dict(row) for row in rows], requires_team_selection

    cluster_result = cluster_result_from_summaries(team_clusters)
    return classify_player_rows_by_cluster(rows, cluster_result, selected_cluster), requires_team_selection


def _tracking_rows_from_frames(frames: list[FrameData]) -> list[dict]:
    tracking_rows: list[dict] = []
    for frame in frames:
        frame_data = frame if isinstance(frame, FrameData) else FrameData.model_validate(frame)
        timestamp = float(frame_data.timestamp)
        if frame_data.ball is not None:
            tracking_rows.append(
                {
                    "Frame_ID": frame_data.frameId,
                    "Timestamp": timestamp,
                    "Entity_Type": "ball",
                    "Track_ID": -1,
                    "X": float(frame_data.ball.x),
                    "Y": float(frame_data.ball.y),
                    "Conf": float(frame_data.ball.confidence),
                }
            )
        for player in frame_data.myTeam:
            tracking_rows.append(
                {
                    "Frame_ID": frame_data.frameId,
                    "Timestamp": timestamp,
                    "Entity_Type": "my_team",
                    "Track_ID": player.id,
                    "X": float(player.x),
                    "Y": float(player.y),
                    "Conf": float(player.confidence),
                }
            )
        for player in frame_data.enemies:
            tracking_rows.append(
                {
                    "Frame_ID": frame_data.frameId,
                    "Timestamp": timestamp,
                    "Entity_Type": "enemy",
                    "Track_ID": player.id,
                    "X": float(player.x),
                    "Y": float(player.y),
                    "Conf": float(player.confidence),
                }
            )
        for player in frame_data.unassignedPlayers:
            tracking_rows.append(
                {
                    "Frame_ID": frame_data.frameId,
                    "Timestamp": timestamp,
                    "Entity_Type": "player",
                    "Track_ID": player.id,
                    "X": float(player.x),
                    "Y": float(player.y),
                    "Conf": float(player.confidence),
                }
            )
    return tracking_rows


def _infer_ball_sample_interval(frame_ids: list[int]) -> int:
    ordered_frame_ids = sorted({int(frame_id) for frame_id in frame_ids})
    if len(ordered_frame_ids) < 2:
        return 1

    inferred_interval = 0
    for previous_frame_id, current_frame_id in zip(ordered_frame_ids, ordered_frame_ids[1:]):
        frame_delta = current_frame_id - previous_frame_id
        if frame_delta <= 0:
            continue
        inferred_interval = frame_delta if inferred_interval == 0 else gcd(inferred_interval, frame_delta)
    return max(inferred_interval, 1)


def _normalize_ball_truth_layers_for_persistence(
    ball_truth_layers: object,
    *,
    frames: list[FrameData],
    raw_rows: list[dict] | None,
) -> dict[str, object] | None:
    if not isinstance(ball_truth_layers, dict):
        return None

    source_rows = raw_rows if raw_rows is not None else _tracking_rows_from_frames(frames)
    canonical_rows = _best_ball_rows_by_frame(source_rows)
    canonical_rows_by_frame = {int(row["Frame_ID"]): dict(row) for row in canonical_rows}
    payload_sample_interval = ball_truth_layers.get("sampleInterval")
    if isinstance(payload_sample_interval, int) and payload_sample_interval > 0:
        sample_interval = payload_sample_interval
    else:
        sample_interval = _infer_ball_sample_interval([int(row["Frame_ID"]) for row in canonical_rows])

    def safe_int(value: object, default: int = 0) -> int:
        if isinstance(value, bool):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def safe_float(value: object, default: float = 0.0) -> float:
        if isinstance(value, bool):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def sanitize_layer_rows(layer_payload: object) -> list[dict]:
        if not isinstance(layer_payload, dict):
            return []

        sanitized_rows: list[dict] = []
        for row in layer_payload.get("rows", []):
            if not isinstance(row, dict) or row.get("Entity_Type") != "ball":
                continue
            canonical_row = canonical_rows_by_frame.get(int(row.get("Frame_ID", -1)))
            if canonical_row is not None:
                sanitized_rows.append(dict(canonical_row))
        return _best_ball_rows_by_frame(sanitized_rows)

    observed_rows = sanitize_layer_rows(ball_truth_layers.get("observedBall"))
    inferred_rows = sanitize_layer_rows(ball_truth_layers.get("inferredBall"))
    accepted_rows = _best_ball_rows_by_frame(observed_rows + inferred_rows)
    if not accepted_rows:
        accepted_rows = [dict(row) for row in canonical_rows]
    accepted_segments = []
    source_by_frame: dict[int, set[str]] = {}
    for row in observed_rows:
        source_by_frame.setdefault(int(row["Frame_ID"]), set()).add("observed")
    for row in inferred_rows:
        source_by_frame.setdefault(int(row["Frame_ID"]), set()).add("inferred")

    for segment in split_ball_rows_into_segments(accepted_rows, max_frame_gap=sample_interval):
        segment_frame_ids = {int(row["Frame_ID"]) for row in segment}
        sources = {source for frame_id in segment_frame_ids for source in source_by_frame.get(frame_id, set())}
        if not sources:
            source = "observed"
        elif sources == {"observed"}:
            source = "observed"
        elif sources == {"inferred"}:
            source = "inferred"
        else:
            source = "mixed"
        accepted_segments.append(
            {
                "startFrame": min(segment_frame_ids),
                "endFrame": max(segment_frame_ids),
                "frameCount": len(segment_frame_ids),
                "source": source,
            }
        )

    unknown_gaps = []
    for previous_segment, next_segment in zip(accepted_segments, accepted_segments[1:]):
        gap_start = int(previous_segment["endFrame"]) + sample_interval
        gap_end = int(next_segment["startFrame"]) - sample_interval
        if gap_start > gap_end:
            continue
        unknown_gaps.append(
            {
                "startFrame": gap_start,
                "endFrame": gap_end,
                "frameCount": ((gap_end - gap_start) // sample_interval) + 1,
            }
        )

    normalized_layers = dict(ball_truth_layers)
    normalized_layers["sampleInterval"] = sample_interval
    normalized_layers["observedBall"] = {
        "rows": observed_rows,
        "summary": _summarize_ball_truth_layer(observed_rows, max_frame_gap=sample_interval),
    }
    normalized_layers["inferredBall"] = {
        "rows": inferred_rows,
        "summary": _summarize_ball_truth_layer(inferred_rows, max_frame_gap=sample_interval),
    }
    normalized_layers["acceptedBall"] = {
        "rows": accepted_rows,
        "summary": _summarize_ball_truth_layer(accepted_rows, max_frame_gap=sample_interval),
    }
    normalized_layers["acceptedSegments"] = accepted_segments
    normalized_layers["unknownGaps"] = unknown_gaps
    normalized_layers["acceptedSourceBreakdown"] = {
        "observed": len({int(row["Frame_ID"]) for row in observed_rows}),
        "inferred": len({int(row["Frame_ID"]) for row in inferred_rows}),
    }
    accepted_frame_count = len({int(row["Frame_ID"]) for row in accepted_rows})
    direct_observation_breakdown = ball_truth_layers.get("directObservationBreakdown")
    if isinstance(direct_observation_breakdown, dict):
        tracking_observed_ball_frames = safe_int(
            direct_observation_breakdown.get("trackingObservedBallFrames"),
            len({int(row["Frame_ID"]) for row in observed_rows}),
        )
        probe_observed_ball_frames = safe_int(
            direct_observation_breakdown.get("probeObservedBallFrames"),
            0,
        )
        probe_only_observed_ball_frames = safe_int(
            direct_observation_breakdown.get("probeOnlyObservedBallFrames"),
            max(probe_observed_ball_frames - tracking_observed_ball_frames, 0),
        )
        accepted_from_observed_frames = safe_int(
            direct_observation_breakdown.get("acceptedFromObservedFrames"),
            len({int(row["Frame_ID"]) for row in observed_rows}),
        )
        accepted_from_observed_ratio = safe_float(
            direct_observation_breakdown.get("acceptedFromObservedRatio"),
            (accepted_from_observed_frames / accepted_frame_count) if accepted_frame_count else 0.0,
        )
    else:
        tracking_observed_ball_frames = len({int(row["Frame_ID"]) for row in observed_rows})
        probe_observed_ball_frames = 0
        probe_only_observed_ball_frames = 0
        accepted_from_observed_frames = tracking_observed_ball_frames
        accepted_from_observed_ratio = (
            accepted_from_observed_frames / accepted_frame_count if accepted_frame_count else 0.0
        )
    normalized_layers["directObservationBreakdown"] = {
        "trackingObservedBallFrames": tracking_observed_ball_frames,
        "probeObservedBallFrames": probe_observed_ball_frames,
        "probeOnlyObservedBallFrames": probe_only_observed_ball_frames,
        "acceptedFromObservedFrames": accepted_from_observed_frames,
        "acceptedFromObservedRatio": round(accepted_from_observed_ratio, 3),
    }
    return normalized_layers


def _prepare_video_outputs(
    video_result: object,
    config: MatchConfig,
) -> tuple[list[FrameData], list[ColorClusterSummary], bool, list[dict] | None]:
    if isinstance(video_result, list):
        if not video_result:
            raise RuntimeError("Video pipeline did not return any tracking rows.")
        first_item = video_result[0]
        if isinstance(first_item, FrameData) or (isinstance(first_item, dict) and "frameId" in first_item):
            frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in video_result]
            return frames, [], False, None

        raw_rows = [dict(row) for row in video_result]
        frames = normalize_tracking_rows(raw_rows)
        return frames, [], False, raw_rows

    if not isinstance(video_result, dict) or "rows" not in video_result:
        raise RuntimeError("Video pipeline returned an unsupported payload.")

    raw_rows = [dict(row) for row in video_result.get("rows", [])]
    if not raw_rows:
        raise RuntimeError("Video pipeline did not return any tracking rows.")

    track_colors = _normalize_track_colors(video_result.get("trackColors"))
    cluster_result = cluster_track_colors(track_colors) if track_colors else cluster_track_colors({})
    classified_rows, requires_team_selection = _classify_video_rows(raw_rows, config, cluster_result.clusters)
    frames = normalize_tracking_rows(classified_rows)
    return frames, cluster_result.clusters, requires_team_selection, raw_rows


def reprocess_match_for_change(
    *,
    change: str,
    previous_identity: str | None,
    current_identity: str,
    vision,
) -> dict[str, object]:
    """Selective recomputation facade. Report-only changes skip vision."""

    return reprocess_for_change(
        change=change,
        previous_identity=previous_identity,
        current_identity=current_identity,
        vision=vision,
    )


def _publish_outputs(
    storage: Storage,
    match_id: str,
    *,
    frames: list[FrameData],
    summary: MatchSummary,
    assignments: list[BallOwnership],
    formation_timeline: list[FormationSegment],
    shots: list[ShotAnalytics],
    events: list[DetectedEvent],
) -> None:
    from .review_service import ReviewService

    service = ReviewService(storage)
    with service._match_lock(match_id):
        if any(item["applyState"] == "applied" for item in storage.list_corrections(match_id)):
            service.rebuild_generation(match_id, reason="processing")
            return
        try:
            correction_head = storage.current_generation(match_id).correctionHead
        except FileNotFoundError:
            correction_head = "none"
        storage.publish_generation(
            match_id,
            frames=frames,
            summary=summary,
            assignments=assignments,
            formation_timeline=formation_timeline,
            shots=shots,
            events=events,
            correction_head=correction_head,
        )


def reprocess_video_match(
    storage: Storage,
    match_id: str,
    *,
    config: MatchConfig | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    match = storage.get_match(match_id)
    config = config or match.config
    if config.myTeamCluster != match.config.myTeamCluster:
        change = "team_mapping"
    elif config.attackDirection != match.config.attackDirection:
        change = "ownership"
    else:
        change = "report"

    def refuse_vision() -> dict[str, object]:
        raise RuntimeError("image-space-safe reprocess must not invoke vision")

    plan = reprocess_for_change(
        change=change,
        previous_identity=None,
        current_identity=match.id,
        vision=refuse_vision,
    )
    if plan.get("visionInvoked"):
        raise RuntimeError("image-space-safe reprocess invoked vision")
    storage.save_analysis_artifact(match.id, "reprocess_plan", plan)

    try:
        raw_rows = storage.load_raw_rows(match_id)
    except FileNotFoundError:
        raw_rows = []

    if raw_rows:
        classified_rows, requires_team_selection = _classify_video_rows(raw_rows, config, match.teamClusters)
        frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in normalize_tracking_rows(classified_rows)]
    else:
        if match.inputMode == "video" and config.myTeamCluster != match.config.myTeamCluster:
            raise FileNotFoundError("Raw video rows are required to change team selection")
        frames = storage.load_frames(match_id)
        requires_team_selection = match.requiresTeamSelection
    ball_truth_layers = _load_saved_ball_truth_layers(storage, match_id)
    match_state_evidence = _normalize_match_state_evidence(
        frames,
        ball_truth_layers=ball_truth_layers,
    )
    enriched_frames, summary, events, assignments, formation_timeline, shots, accepted_match_state = _compute_outputs_and_match_state(
        frames,
        attack_direction=config.attackDirection,
        ball_truth_layers=ball_truth_layers,
        match_state_evidence=match_state_evidence,
    )
    if persist:
        _publish_outputs(
            storage, match.id, frames=enriched_frames, summary=summary, assignments=assignments,
            formation_timeline=formation_timeline, shots=shots, events=events,
        )
        storage.save_analysis_artifact(match.id, "accepted_match_state", accepted_match_state)
        storage.update_match_status(
            match.id,
            status="ready",
            requires_team_selection=requires_team_selection,
            team_clusters=match.teamClusters,
        )
    return {
        "frames": enriched_frames,
        "summary": summary,
        "events": events,
        "assignments": assignments,
        "formationTimeline": formation_timeline,
        "shots": shots,
        "acceptedMatchState": accepted_match_state,
        "requiresTeamSelection": requires_team_selection,
    }


def _persist_video_outputs(
    storage: Storage,
    job_id: str,
    match_id: str,
    config: MatchConfig,
    video_result: object,
    *,
    processing_backend: str,
    video_path: Path | None,
    worker_path: str,
) -> None:
    frames, team_clusters, requires_team_selection, raw_rows = _prepare_video_outputs(
        video_result,
        config,
    )
    persisted_raw_rows = raw_rows if raw_rows is not None else _tracking_rows_from_frames(frames)
    _persist_prepared_video_outputs(
        storage, job_id, match_id, video_result,
        frames=frames,
        team_clusters=team_clusters,
        requires_team_selection=requires_team_selection,
        ball_rows=persisted_raw_rows,
        raw_rows_stage=_trace_stage_from_rows("persistRawRows", persisted_raw_rows),
        processing_backend=processing_backend,
        video_path=video_path,
        worker_path=worker_path,
    )


def _persist_prepared_video_outputs(
    storage: Storage,
    job_id: str,
    match_id: str,
    video_result: object,
    *,
    frames: list[FrameData],
    team_clusters: list[ColorClusterSummary],
    requires_team_selection: bool,
    ball_rows: list[dict],
    raw_rows_stage: dict[str, object],
    processing_backend: str,
    video_path: Path | None,
    worker_path: str,
    raw_rows_saved: bool = False,
) -> None:
    ball_pipeline_trace = _normalize_ball_pipeline_trace(
        video_result.get("ballPipelineTrace") if isinstance(video_result, dict) else None
    )
    ball_truth_layers: dict[str, object] | None = None
    if isinstance(video_result, dict):
        runtime_fingerprint = _normalize_runtime_fingerprint(video_result.get("runtimeFingerprint"))
        if runtime_fingerprint is not None:
            ball_pipeline_trace["runtimeFingerprint"] = runtime_fingerprint
        recovery_debug = video_result.get("recoveryDebug")
        if isinstance(recovery_debug, dict):
            storage.save_analysis_artifact(match_id, "recovery_debug", recovery_debug)
        recovery_profile_matrix = video_result.get("recoveryProfileMatrix")
        if isinstance(recovery_profile_matrix, dict):
            storage.save_analysis_artifact(match_id, "recovery_profile_matrix", recovery_profile_matrix)
        ball_truth_layers = _normalize_ball_truth_layers_for_persistence(
            video_result.get("ballTruthLayers"),
            frames=frames,
            raw_rows=ball_rows,
        )
        if ball_truth_layers is not None:
            storage.save_analysis_artifact(match_id, "ball_truth_layers", ball_truth_layers)
        source_clock = video_result.get("sourceClock")
        if isinstance(source_clock, dict):
            storage.save_analysis_artifact(match_id, "source_clock", source_clock)
        decode_memory = video_result.get("decodeMemoryPolicy")
        if isinstance(decode_memory, dict):
            storage.save_analysis_artifact(match_id, "decode_memory_policy", decode_memory)
        four_rates = video_result.get("fourRates")
        if isinstance(four_rates, dict):
            storage.save_analysis_artifact(match_id, "four_rates", four_rates)
        decode_anchors = video_result.get("decodeAnchors")
        if isinstance(decode_anchors, dict):
            storage.save_analysis_artifact(match_id, "decode_anchors", decode_anchors)
        projection_policy = video_result.get("projectionPolicy")
        if isinstance(projection_policy, dict):
            storage.save_analysis_artifact(match_id, "projection_policy", projection_policy)
        sampling = video_result.get("sampling")
        if isinstance(sampling, dict):
            storage.save_analysis_artifact(match_id, "sampling", sampling)
        vid_stride = video_result.get("vidStridePolicy")
        if isinstance(vid_stride, dict):
            storage.save_analysis_artifact(match_id, "vid_stride_policy", vid_stride)
        cache_identity = video_result.get("cacheIdentity")
        if isinstance(cache_identity, dict):
            storage.save_analysis_artifact(match_id, "cache_identity", cache_identity)
        elif cache_identity:
            storage.save_analysis_artifact(match_id, "cache_identity", {"cacheIdentity": cache_identity})
    _upsert_ball_pipeline_stage(ball_pipeline_trace, raw_rows_stage)
    if not raw_rows_saved:
        storage.save_raw_rows(match_id, ball_rows)

    frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]
    match_state_evidence = _normalize_match_state_evidence(
        frames,
        ball_truth_layers=ball_truth_layers,
        match_state_evidence=video_result.get("matchStateEvidence") if isinstance(video_result, dict) else None,
    )
    _upsert_ball_pipeline_stage(ball_pipeline_trace, _trace_stage_from_frames("normalizedFrames", frames))
    storage.update_job(job_id, status="processing", progress=0.55, message="Computing possession and metrics")
    enriched_frames, summary, events, assignments, formation_timeline, shots, accepted_match_state = _compute_outputs_and_match_state(
        frames,
        attack_direction=storage.get_match(match_id).config.attackDirection,
        ball_truth_layers=ball_truth_layers,
        match_state_evidence=match_state_evidence,
    )
    tracked_possession_frames = sum(
        1 for assignment in assignments if assignment.team in {"my_team", "enemy", "unassigned"} and assignment.trackId is not None
    )
    controlled_possession_frames = sum(
        1 for assignment in assignments if assignment.team in {"my_team", "enemy"}
    )
    possession_stage = _trace_stage_from_frames("possessionOutputs", enriched_frames)
    possession_stage["trackedPossessionFrames"] = tracked_possession_frames
    possession_stage["controlledPossessionFrames"] = controlled_possession_frames
    _upsert_ball_pipeline_stage(ball_pipeline_trace, possession_stage)
    event_stage = _trace_stage_from_frames("eventOutputs", enriched_frames)
    event_stage["trackedPossessionFrames"] = tracked_possession_frames
    event_stage["controlledPossessionFrames"] = controlled_possession_frames
    event_stage["eventCount"] = len(events)
    event_counts: dict[str, int] = {}
    for event in events:
        event_counts[event.type] = event_counts.get(event.type, 0) + 1
    event_stage["eventTypes"] = dict(sorted(event_counts.items()))
    _upsert_ball_pipeline_stage(ball_pipeline_trace, event_stage)
    storage.save_analysis_artifact(
        match_id,
        "ball_pipeline_trace",
        _finalize_ball_pipeline_trace(
            trace=ball_pipeline_trace,
            match_id=match_id,
            job_id=job_id,
            processing_backend=processing_backend,
            input_mode="video",
            video_path=video_path,
            worker_path=worker_path,
        ),
    )

    _publish_outputs(
        storage, match_id, frames=enriched_frames, summary=summary, assignments=assignments,
        formation_timeline=formation_timeline, shots=shots, events=events,
    )
    if isinstance(video_result, dict) and not isinstance(video_result.get("decodeAnchors"), dict) and enriched_frames:
        times = [float(frame.timestamp) for frame in enriched_frames]
        storage.save_analysis_artifact(
            match_id,
            "decode_anchors",
            {
                "beginning": times[0],
                "middle": times[len(times) // 2],
                "end": times[-1],
                "source": "persisted_frames",
                "discontinuities": [],
            },
        )
    try:
        storage.publish_ownership_events(match_id)
    except Exception:
        pass
    storage.save_analysis_artifact(match_id, "accepted_match_state", accepted_match_state)
    storage.update_match_status(
        match_id,
        status="ready",
        requires_team_selection=requires_team_selection,
        team_clusters=team_clusters,
    )
    storage.update_job(job_id, status="completed", progress=1.0, message="Processing complete")


def _persist_worker_progress_heartbeat(
    storage: Storage,
    *,
    job_id: str,
    match_id: str,
):
    callback_state = {
        "lastStage": None,
        "lastStatus": None,
        "lastDbUpdateAt": None,
    }

    def _callback(heartbeat: dict[str, object]) -> None:
        worker_stage = str(heartbeat.get("workerStage", "") or "")
        stage_status = str(heartbeat.get("stageStatus", "") or "")
        progress = WORKER_STAGE_PROGRESS.get(worker_stage)
        message = WORKER_STAGE_MESSAGES.get(worker_stage)

        worker_progress_payload = dict(heartbeat)
        if progress is not None:
            worker_progress_payload["jobProgress"] = progress
        if message is not None:
            worker_progress_payload["jobMessage"] = message
        storage.save_analysis_artifact(match_id, "worker_progress", worker_progress_payload)
        storage.append_analysis_artifact_jsonl(
            match_id,
            "worker_progress_history",
            worker_progress_payload,
        )

        should_update_job = False
        now = time.monotonic()
        if worker_stage != callback_state["lastStage"] or stage_status != callback_state["lastStatus"]:
            should_update_job = True
        elif worker_stage in {"trackingPass", "recoverySelection"}:
            last_db_update_at = callback_state["lastDbUpdateAt"]
            if last_db_update_at is None or (now - last_db_update_at) >= WORKER_HEARTBEAT_INTERVAL_SECONDS:
                should_update_job = True

        if should_update_job and progress is not None and message is not None:
            storage.update_job(
                job_id,
                status="processing",
                progress=progress,
                message=message,
            )
            callback_state["lastDbUpdateAt"] = now
        callback_state["lastStage"] = worker_stage
        callback_state["lastStatus"] = stage_status

    return _callback


def persist_remote_video_result(storage: Storage, job_id: str, video_result: object) -> None:
    """Persist output returned by the provider-neutral sealed GPU worker."""

    job = storage.get_job(job_id)
    match = storage.get_match(job.matchId)
    _persist_video_outputs(
        storage,
        job_id,
        match.id,
        match.config,
        video_result,
        processing_backend="remote",
        video_path=storage.get_match_input_path(match.id),
        worker_path="gpu_worker",
    )


def persist_remote_video_result_stream(storage: Storage, job_id: str, source: ProcessorResultStream) -> None:
    """Consume rows inside the caller's remote_result_import and source contexts."""

    job = storage.get_job(job_id)
    match = storage.get_match(job.matchId)
    track_colors = _normalize_track_colors(source.metadata.get("trackColors"))
    cluster_result = cluster_track_colors(track_colors)
    selected_cluster, requires_team_selection = _resolve_selected_cluster(match.config, cluster_result.clusters)
    grouped_frames: dict[int, FrameData] = {}
    ball_rows: list[dict] = []
    row_count = 0

    def persisted_rows():
        nonlocal row_count
        for raw in source.rows:
            add_tracking_row(grouped_frames, classify_player_row_by_cluster(raw, cluster_result, selected_cluster))
            if raw.get("Entity_Type") == "ball":
                ball_rows.append(dict(raw))
            row_count += 1
            yield raw

    storage.save_raw_rows(match.id, persisted_rows())
    if not row_count:
        raise RuntimeError("Video pipeline did not return any tracking rows.")
    frames = [grouped_frames[frame_id] for frame_id in sorted(grouped_frames)]
    raw_rows_stage = _trace_stage_from_rows("persistRawRows", ball_rows)
    raw_rows_stage["playerRowCount"] = row_count - len(ball_rows)
    raw_rows_stage["frameCount"] = len(frames)
    _persist_prepared_video_outputs(
        storage, job_id, match.id, source.metadata,
        frames=frames,
        team_clusters=cluster_result.clusters,
        requires_team_selection=requires_team_selection,
        ball_rows=ball_rows,
        raw_rows_stage=raw_rows_stage,
        processing_backend="remote",
        video_path=storage.get_match_input_path(match.id),
        worker_path="gpu_worker",
        raw_rows_saved=True,
    )


def process_match(storage: Storage, job_id: str) -> None:
    job = storage.get_job(job_id)
    match = storage.get_match(job.matchId)
    input_path = storage.get_match_input_path(match.id)

    storage.update_job(job_id, status="processing", progress=0.1, message="Loading input")
    if match.inputMode == "tracking_json":
        rows = json.loads(input_path.read_text(encoding="utf-8"))
        frames = normalize_tracking_rows(rows)
        team_clusters: list[ColorClusterSummary] = []
        requires_team_selection = False
    elif match.inputMode == "video":
        runtime_options = load_proof_runtime_options(
            storage, match.id, manifest_path=RUNTIME_MANIFEST_PATH
        )
        materialized_runtime_options = materialize_proof_runtime_options(
            runtime_options,
            storage_root=storage.storage_root,
            environment="local",
            manifest_path=RUNTIME_MANIFEST_PATH,
            resolver_root=RUNTIME_ARTIFACT_ROOT,
            object_loader=local_boto3_object_loader,
        )
        progress_callback = _persist_worker_progress_heartbeat(
            storage,
            job_id=job_id,
            match_id=match.id,
        )
        process_video_kwargs = {
            **materialized_runtime_options,
            "progress_callback": progress_callback,
            "match_id": match.id,
            "job_id": job.id,
        }
        _persist_video_outputs(
            storage,
            job_id,
            match.id,
            match.config,
            process_video_input(
                input_path,
                match.config,
                **process_video_kwargs,
            ),
            processing_backend="local",
            video_path=input_path,
            worker_path="local",
        )
        return
    else:
        raise RuntimeError(f"Unsupported input mode: {match.inputMode}")

    frames = [frame if isinstance(frame, FrameData) else FrameData.model_validate(frame) for frame in frames]

    storage.update_job(job_id, status="processing", progress=0.55, message="Computing possession and metrics")
    enriched_frames, summary, events, assignments, formation_timeline, shots, accepted_match_state = _compute_outputs_and_match_state(
        frames,
        attack_direction=match.config.attackDirection,
    )

    _publish_outputs(
        storage, match.id, frames=enriched_frames, summary=summary, assignments=assignments,
        formation_timeline=formation_timeline, shots=shots, events=events,
    )
    storage.save_analysis_artifact(match.id, "accepted_match_state", accepted_match_state)
    storage.update_match_status(
        match.id,
        status="ready",
        requires_team_selection=requires_team_selection,
        team_clusters=team_clusters,
    )
    storage.update_job(job_id, status="completed", progress=1.0, message="Processing complete")
