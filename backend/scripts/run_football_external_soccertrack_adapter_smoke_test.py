from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterator, TextIO

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_FIXTURE_DIR_NAME = "football_external_soccertrack_sample_fixture_materialization_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_adapter_smoke_test_v1"

BLOCKER_FIXTURE_MISSING = "football_external_soccertrack_sample_fixture_missing"
BLOCKER_BAS_CONTRACT = "football_external_soccertrack_bas_adapter_contract_gap"
BLOCKER_GSR_CONTRACT = "football_external_soccertrack_gsr_adapter_contract_gap"
BLOCKER_MOT_CONTRACT = "football_external_soccertrack_mot_adapter_contract_gap"

NEXT_FIXTURE = "football_external_soccertrack_sample_fixture_materialization"
NEXT_EVENT_REPAIR = "football_external_soccertrack_event_mapping_repair"
NEXT_GSR_STREAMING = "football_external_soccertrack_streaming_gsr_adapter"
NEXT_MOT_REPAIR = "football_external_soccertrack_mot_mapping_repair"
NEXT_BRIDGE = "football_external_soccertrack_match_bundle_bridge_smoke"

GSR_WINDOW_START_FRAME = 0
GSR_WINDOW_FRAME_COUNT = 20
GSR_MAX_ANNOTATION_BYTES = 8 * 1024 * 1024


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _iter_json_array(stream: TextIO, key: str, *, chunk_size: int = 64 * 1024) -> Iterator[dict[str, Any]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    marker = json.dumps(key)
    buffer = ""
    while marker not in buffer:
        chunk = stream.read(chunk_size)
        if not chunk:
            raise ValueError(f"JSON key {key!r} not found")
        buffer += chunk
        marker_index = buffer.find(marker)
        if marker_index < 0:
            buffer = buffer[-len(marker) :]
    buffer = buffer[buffer.index(marker) + len(marker) :]

    def require_token(token: str) -> None:
        nonlocal buffer
        while True:
            buffer = buffer.lstrip()
            if buffer:
                if not buffer.startswith(token):
                    raise ValueError(f"JSON key {key!r} must be followed by {token!r}")
                buffer = buffer[len(token) :]
                return
            chunk = stream.read(chunk_size)
            if not chunk:
                raise ValueError(f"JSON key {key!r} ended before {token!r}")
            buffer += chunk

    require_token(":")
    require_token("[")
    decoder = json.JSONDecoder()
    while True:
        buffer = buffer.lstrip()
        if buffer.startswith(","):
            buffer = buffer[1:].lstrip()
        if buffer.startswith("]"):
            return
        try:
            value, end = decoder.raw_decode(buffer)
        except json.JSONDecodeError as exc:
            if len(buffer.encode("utf-8")) > GSR_MAX_ANNOTATION_BYTES:
                raise ValueError("SoccerTrack annotation exceeds 8 MiB") from exc
            chunk = stream.read(chunk_size)
            if not chunk:
                raise ValueError("SoccerTrack annotations contain malformed JSON") from exc
            buffer += chunk
            continue
        if not isinstance(value, dict):
            raise ValueError("SoccerTrack annotations must contain JSON objects")
        buffer = buffer[end:]
        yield value


def _gsr_frame_index(image_id: object) -> int:
    text = str(image_id)
    if len(text) < 7 or not text.isdigit():
        raise ValueError("SoccerTrack image_id must contain a sequence prefix and six-digit frame suffix")
    frame_index = int(text[-6:]) - 1
    if frame_index < 0:
        raise ValueError("SoccerTrack image_id frame suffix must be one-indexed")
    return frame_index


def _finite_float(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _gsr_entity(annotation: dict[str, Any]) -> dict[str, Any] | None:
    pitch = annotation.get("bbox_pitch")
    if not isinstance(pitch, dict):
        return None
    try:
        x_m = _finite_float(pitch.get("x_bottom_middle"), "bbox_pitch.x_bottom_middle")
        y_m = _finite_float(pitch.get("y_bottom_middle"), "bbox_pitch.y_bottom_middle")
    except ValueError:
        return None
    attributes = annotation.get("attributes")
    if not isinstance(attributes, dict) or not str(attributes.get("role") or ""):
        raise ValueError("SoccerTrack object annotation requires attributes.role")
    try:
        track_id = int(annotation["track_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("SoccerTrack object annotation requires integer track_id") from exc
    jersey = attributes.get("jersey")
    try:
        jersey_number = None if jersey in (None, "") else int(jersey)
    except (TypeError, ValueError) as exc:
        raise ValueError("SoccerTrack attributes.jersey must be numeric or null") from exc
    player_id = attributes.get("player_id")
    return {
        "trackId": track_id,
        "playerId": None if player_id is None else str(player_id),
        "role": str(attributes["role"]),
        "jerseyNumber": jersey_number,
        "teamSide": attributes.get("team"),
        "pitchPositionMeters": {"x": x_m, "y": y_m},
        "pitchPositionNormalized": {
            "x": (x_m + 52.5) / 105.0 * 100.0,
            "y": (34.0 - y_m) / 68.0 * 100.0,
        },
        "imageBbox": annotation.get("bbox_image"),
    }


def _stream_gsr_half(
    row: dict[str, Any],
    half: int,
    *,
    start_frame: int = GSR_WINDOW_START_FRAME,
    frame_count: int = GSR_WINDOW_FRAME_COUNT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if half not in {1, 2} or start_frame < 0 or frame_count <= 0:
        raise ValueError("half, start_frame, and frame_count are invalid")
    source_path = Path(str(row.get("sourcePath") or ""))
    if not source_path.is_file():
        raise ValueError("SoccerTrack GSR sourcePath must name an existing file")
    info = row.get("info") if isinstance(row.get("info"), dict) else {}
    frame_rate = _finite_float(info.get("frame_rate"), "info.frame_rate")
    if frame_rate <= 0:
        raise ValueError("info.frame_rate must be positive")
    stop_frame = start_frame + frame_count
    frames: dict[int, dict[str, Any]] = {}
    omitted_positions = 0
    last_frame = -1
    with source_path.open(encoding="utf-8") as stream:
        annotations = _iter_json_array(stream, "annotations")
        try:
            for annotation in annotations:
                frame_index = _gsr_frame_index(annotation.get("image_id"))
                if frame_index < last_frame:
                    raise ValueError("SoccerTrack annotations must be ordered by image_id")
                last_frame = frame_index
                if frame_index >= stop_frame:
                    break
                if frame_index < start_frame or annotation.get("supercategory") != "object":
                    continue
                frame = frames.setdefault(
                    frame_index,
                    {
                        "half": half,
                        "frameIndex": frame_index,
                        "sourceImageId": str(annotation["image_id"]),
                        "timestampSecondsInHalf": frame_index / frame_rate,
                        "entities": [],
                    },
                )
                entity = _gsr_entity(annotation)
                if entity is None:
                    omitted_positions += 1
                else:
                    frame["entities"].append(entity)
        finally:
            annotations.close()
    ordered = [frames[index] for index in sorted(frames)]
    return ordered, {
        "half": half,
        "sourcePath": str(source_path),
        "frameRate": frame_rate,
        "requestedStartFrame": start_frame,
        "requestedFrameCount": frame_count,
        "readFrameCount": len(ordered),
        "entityCount": sum(len(frame["entities"]) for frame in ordered),
        "omittedPositionCount": omitted_positions,
    }


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_lightweight_adapter_smoke",
            "successCriteria": [
                "convert materialized BAS events into normalized canonical event records",
                "verify GSR half metadata without loading full multi-GB JSON files",
                "verify MOT sampled frame/player surfaces and write canonical external fixture",
            ],
            "failureAdaptation": "If a mapping fails, route to the precise BAS/GSR/MOT repair lane.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_adapter_contract_repair",
            "successCriteria": [
                "repair field mapping from saved materialized fixture truth only",
                "preserve no video download, training, promotion, candidate evaluation, or runtime mutation",
            ],
            "failureAdaptation": "If GSR needs more than header metadata, route to streaming adapter work.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_adapter_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not train, promote, mutate runtime defaults, or fetch full videos",
            ],
            "failureAdaptation": "Stop before MatchBundle bridge until adapter smoke passes.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fixture_root = candidate_root / DEFAULT_FIXTURE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fixtureRoot": fixture_root,
        "summary": _load_json(fixture_root / "soccertrack_sample_fixture_materialization_summary.json"),
        "index": _load_json(fixture_root / "soccertrack_sample_fixture_index.json"),
        "bas": _load_json(fixture_root / "soccertrack_bas_event_stream_fixture.json"),
        "gsr": _load_json(fixture_root / "soccertrack_gsr_frame_state_fixture.json"),
        "mot": _load_json(fixture_root / "soccertrack_mot_track_frame_fixture.json"),
        "gameState": _load_json(fixture_root / "soccertrack_game_state_fixture.json"),
    }


def _fixture_ready(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("summary")
    index = inputs.get("index")
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and {"bas", "gsr", "mot"}.issubset(set(summary.get("materializedTaskIds") or []))
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationAllowed") is False
        and isinstance(index, dict)
        and index.get("fixtureMaterializationMode") == "lightweight_index_plus_samples"
        and {"bas", "gsr", "mot"}.issubset(set(index.get("materializedTaskIds") or []))
    )


def _load_bas_actions(bas_fixture: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(bas_fixture, dict):
        return []
    source_path = bas_fixture.get("sourcePath")
    if isinstance(source_path, str) and Path(source_path).exists():
        try:
            payload = json.loads(Path(source_path).read_text(encoding="utf-8"))
            actions = payload.get("actions")
            if isinstance(actions, list):
                return [dict(row) for row in actions if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    sample = bas_fixture.get("sampleActions")
    return [dict(row) for row in sample if isinstance(row, dict)] if isinstance(sample, list) else []


def _period_from_game_time(game_time: Any) -> int | None:
    text = str(game_time or "")
    if " - " in text:
        text = text.split(" - ", 1)[1].strip()
    if ":" not in text:
        return None
    try:
        minute = int(text.split(":", 1)[0])
    except ValueError:
        return None
    return minute // 45 + 1


def _position_ms(action: dict[str, Any]) -> int | None:
    value = action.get("position")
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _normalize_bas_events(match_id: str, actions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        position_ms = _position_ms(action)
        event_type = str(action.get("label") or "").strip()
        period = _period_from_game_time(action.get("gameTime"))
        if position_ms is None or not event_type or period is None:
            failures.append({"actionIndex": index, "reason": "missing_period_position_or_label", "action": action})
            continue
        normalized.append(
            {
                "eventId": f"soccertrack-{match_id}-bas-{index:06d}",
                "sourceOrder": index,
                "sourceMatchId": match_id,
                "source": "soccertrack_bas",
                "period": period,
                "positionMs": position_ms,
                "eventType": event_type,
                "team": action.get("team") or "",
                "playerId": action.get("player_id") or action.get("playerId") or "",
                "rawGameTime": action.get("gameTime"),
            }
        )
    normalized = sorted(normalized, key=lambda row: (int(row["period"]), int(row["positionMs"]), int(row["sourceOrder"])))
    return normalized, failures


def _bas_audit(match_id: str, bas_fixture: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actions = _load_bas_actions(bas_fixture)
    normalized, failures = _normalize_bas_events(match_id, actions)
    timeline_pairs = [(int(row["period"]), int(row["positionMs"])) for row in normalized]
    monotonic = timeline_pairs == sorted(timeline_pairs)
    audit = {
        "schemaVersion": "soccertrack_bas_adapter_audit_v1",
        "generatedAt": _utc_now_iso(),
        "basActionCount": len(actions),
        "normalizedEventCount": len(normalized),
        "normalizationFailureCount": len(failures),
        "normalizationFailuresSample": failures[:20],
        "periodPositionMonotonicNonDecreasing": monotonic,
        "basAdapterPassed": bool(normalized) and not failures and monotonic,
        "trainingExecuted": False,
    }
    return audit, normalized


def _gsr_audit(gsr_fixture: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    half_files = gsr_fixture.get("halfFiles") if isinstance(gsr_fixture, dict) else []
    half_files = half_files if isinstance(half_files, list) else []
    failures = []
    summaries = []
    frames: list[dict[str, Any]] = []
    for index, row in enumerate(half_files):
        if not isinstance(row, dict):
            failures.append({"halfIndex": index, "reason": "half_not_object"})
            continue
        info = row.get("info") if isinstance(row.get("info"), dict) else {}
        seq_length = info.get("seq_length")
        frame_rate = info.get("frame_rate")
        try:
            seq_length_int = int(seq_length)
            frame_rate_float = float(frame_rate)
        except (TypeError, ValueError):
            failures.append({"halfIndex": index, "reason": "invalid_seq_length_or_frame_rate"})
            continue
        try:
            half_frames, window = _stream_gsr_half(row, index + 1)
        except (OSError, ValueError) as exc:
            failures.append({"halfIndex": index, "reason": str(exc)})
            continue
        frames.extend(half_frames)
        summaries.append({
            "halfIndex": index,
            "seqLength": seq_length_int,
            "frameRate": frame_rate_float,
            "gameTimeStart": info.get("game_time_start"),
            "gameTimeStop": info.get("game_time_stop"),
            "sizeBytes": row.get("sizeBytes"),
            "sampleImageIds": row.get("sampleImageIds") or [],
            **window,
        })
    audit = {
        "schemaVersion": "soccertrack_gsr_adapter_audit_v1",
        "generatedAt": _utc_now_iso(),
        "sourceSchema": "soccertrack_coco_as_shipped",
        "largeFileHeaderOnly": bool(isinstance(gsr_fixture, dict) and gsr_fixture.get("largeFileHeaderOnly") is True),
        "gsrHalfCount": len(half_files),
        "halfSummaries": summaries,
        "gsrFrameCount": len(frames),
        "gsrEntityCount": sum(len(frame["entities"]) for frame in frames),
        "omittedPositionCount": sum(int(row["omittedPositionCount"]) for row in summaries),
        "gsrFailureCount": len(failures),
        "gsrFailuresSample": failures[:20],
        "gsrAdapterPassed": len(summaries) >= 2 and bool(frames) and not failures,
        "fullGsrJsonLoaded": False,
        "trainingExecuted": False,
    }
    return audit, frames


def _mot_audit(mot_fixture: dict[str, Any] | None) -> dict[str, Any]:
    tracker = mot_fixture.get("trackerBoxData") if isinstance(mot_fixture, dict) else {}
    player_nodes = mot_fixture.get("playerNodes") if isinstance(mot_fixture, dict) else {}
    tracker = tracker if isinstance(tracker, dict) else {}
    player_nodes = player_nodes if isinstance(player_nodes, dict) else {}
    sample_frames = tracker.get("sampleFrames") if isinstance(tracker.get("sampleFrames"), list) else []
    sample_rows = player_nodes.get("sampleRows") if isinstance(player_nodes.get("sampleRows"), list) else []
    required_frame_fields = {"frameNumber", "matchTime"}
    frame_failures = [
        {"frameIndex": index, "missingFields": sorted(required_frame_fields - set(frame))}
        for index, frame in enumerate(sample_frames)
        if isinstance(frame, dict) and not required_frame_fields.issubset(set(frame))
    ]
    return {
        "schemaVersion": "soccertrack_mot_adapter_audit_v1",
        "generatedAt": _utc_now_iso(),
        "motFrameCount": int(tracker.get("frameCount") or 0),
        "motSampledFrameCount": len(sample_frames),
        "motSampleFrames": sample_frames[:20],
        "playerNodeSampleCount": len(sample_rows),
        "playerNodeFieldNames": player_nodes.get("fieldNames") or [],
        "frameFailureCount": len(frame_failures),
        "frameFailuresSample": frame_failures[:20],
        "motAdapterPassed": int(tracker.get("frameCount") or 0) > 0 and bool(sample_frames) and not frame_failures,
        "trainingExecuted": False,
    }


def _canonical_fixture(
    *,
    match_id: str,
    normalized_events: list[dict[str, Any]],
    gsr_audit: dict[str, Any],
    gsr_frames: list[dict[str, Any]],
    mot_audit: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": "canonical_external_match_fixture_v1",
        "generatedAt": _utc_now_iso(),
        "sourceDataset": "soccertrack_v2",
        "sourceMatchId": match_id,
        "basEventCount": len(normalized_events),
        "normalizedEvents": normalized_events,
        "gsrHalfCount": gsr_audit.get("gsrHalfCount"),
        "gsrHalfSummaries": gsr_audit.get("halfSummaries", []),
        "gsrFrames": gsr_frames,
        "gsrCoordinateSystem": {
            "units": "meters",
            "origin": "pitch_center",
            "sourceAxes": {"x": "right", "y": "up"},
            "pitchDimensionsMeters": {"length": 105.0, "width": 68.0},
            "normalizedDisplayAxes": {"x": "right", "y": "down"},
            "clipped": False,
        },
        "motFrameCount": mot_audit.get("motFrameCount"),
        "motSampledFrameCount": mot_audit.get("motSampledFrameCount"),
        "motSampleFrames": mot_audit.get("motSampleFrames", []),
        "trainingExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _bridge_plan(adapter_ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_match_bundle_bridge_plan_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_soccertrack_adapter_smoke_test",
        "targetNextLever": NEXT_BRIDGE,
        "bridgeSmokeReady": adapter_ready,
        "bridgeInputs": [
            "canonical_external_match_fixture.json",
            "soccertrack_bas_adapter_audit.json",
            "soccertrack_gsr_adapter_audit.json",
            "soccertrack_mot_adapter_audit.json",
        ],
        "trainingUseAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _classify(fixture_ready: bool, bas: dict[str, Any], gsr: dict[str, Any], mot: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not fixture_ready:
        return (
            BLOCKER_FIXTURE_MISSING,
            NEXT_FIXTURE,
            False,
            False,
            "SoccerTrack adapter smoke requires completed sample fixture materialization truth first.",
        )
    if bas.get("basAdapterPassed") is not True:
        return (
            BLOCKER_BAS_CONTRACT,
            NEXT_EVENT_REPAIR,
            False,
            True,
            "SoccerTrack BAS event mapping failed; repair event normalization before MatchBundle bridge.",
        )
    if gsr.get("gsrAdapterPassed") is not True:
        return (
            BLOCKER_GSR_CONTRACT,
            NEXT_GSR_STREAMING,
            False,
            True,
            "SoccerTrack GSR metadata mapping failed; route to streaming GSR adapter work.",
        )
    if mot.get("motAdapterPassed") is not True:
        return (
            BLOCKER_MOT_CONTRACT,
            NEXT_MOT_REPAIR,
            False,
            True,
            "SoccerTrack MOT sample mapping failed; repair MOT frame/player normalization before MatchBundle bridge.",
        )
    return (
        None,
        NEXT_BRIDGE,
        True,
        True,
        "SoccerTrack adapter smoke passed. Advance to MatchBundle bridge smoke; no training, promotion, candidate evaluation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "sample_fixture_missing", "selected": primary_blocker == BLOCKER_FIXTURE_MISSING, "primaryBlocker": BLOCKER_FIXTURE_MISSING, "nextRecommendedNextLever": NEXT_FIXTURE},
            {"condition": "bas_adapter_contract_gap", "selected": primary_blocker == BLOCKER_BAS_CONTRACT, "primaryBlocker": BLOCKER_BAS_CONTRACT, "nextRecommendedNextLever": NEXT_EVENT_REPAIR},
            {"condition": "gsr_adapter_contract_gap", "selected": primary_blocker == BLOCKER_GSR_CONTRACT, "primaryBlocker": BLOCKER_GSR_CONTRACT, "nextRecommendedNextLever": NEXT_GSR_STREAMING},
            {"condition": "mot_adapter_contract_gap", "selected": primary_blocker == BLOCKER_MOT_CONTRACT, "primaryBlocker": BLOCKER_MOT_CONTRACT, "nextRecommendedNextLever": NEXT_MOT_REPAIR},
            {"condition": "match_bundle_bridge_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BRIDGE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Adapter Smoke Test",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Canonical external fixture ready: `{summary.get('canonicalExternalFixtureReady')}`",
            f"- BAS event count: `{summary.get('basEventCount')}`",
            f"- GSR half count: `{summary.get('gsrHalfCount')}`",
            f"- MOT sampled frame count: `{summary.get('motSampledFrameCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_adapter_smoke_test(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_lightweight_adapter_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    fixture_ready = _fixture_ready(inputs)
    match_id = str((inputs.get("summary") or {}).get("selectedMatchId") or (inputs.get("index") or {}).get("selectedMatchId") or "")
    bas_audit, normalized_events = _bas_audit(match_id, inputs.get("bas") if isinstance(inputs.get("bas"), dict) else None)
    gsr_audit, gsr_frames = _gsr_audit(inputs.get("gsr") if isinstance(inputs.get("gsr"), dict) else None)
    mot_audit = _mot_audit(inputs.get("mot") if isinstance(inputs.get("mot"), dict) else None)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(fixture_ready, bas_audit, gsr_audit, mot_audit)
    canonical = _canonical_fixture(
        match_id=match_id,
        normalized_events=normalized_events,
        gsr_audit=gsr_audit,
        gsr_frames=gsr_frames,
        mot_audit=mot_audit,
    )
    bridge_plan = _bridge_plan(goal_achieved)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_adapter_smoke_test",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_sample_fixture_materialization",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": match_id or None,
        "canonicalExternalFixtureReady": goal_achieved,
        "basAdapterPassed": bas_audit["basAdapterPassed"],
        "gsrAdapterPassed": gsr_audit["gsrAdapterPassed"],
        "motAdapterPassed": mot_audit["motAdapterPassed"],
        "basEventCount": bas_audit["normalizedEventCount"],
        "gsrHalfCount": gsr_audit["gsrHalfCount"],
        "gsrFrameCount": gsr_audit["gsrFrameCount"],
        "gsrEntityCount": gsr_audit["gsrEntityCount"],
        "gsrOmittedPositionCount": gsr_audit["omittedPositionCount"],
        "motFrameCount": mot_audit["motFrameCount"],
        "motSampledFrameCount": mot_audit["motSampledFrameCount"],
        "fullGsrJsonLoaded": False,
        "videoDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "soccertrackBasAdapterAudit": bas_audit,
        "soccertrackGsrAdapterAudit": gsr_audit,
        "soccertrackMotAdapterAudit": mot_audit,
        "canonicalExternalMatchFixture": canonical,
        "matchBundleBridgePlan": bridge_plan,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_adapter_smoke_summary.json", summary)
    _write_json(output_root / "soccertrack_bas_adapter_audit.json", bas_audit)
    _write_json(output_root / "soccertrack_gsr_adapter_audit.json", gsr_audit)
    _write_json(output_root / "soccertrack_mot_adapter_audit.json", mot_audit)
    _write_json(output_root / "canonical_external_match_fixture.json", canonical)
    _write_json(output_root / "match_bundle_bridge_plan.json", bridge_plan)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test materialized SoccerTrack fixtures against the external adapter contract.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_lightweight_adapter_smoke")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_adapter_smoke_test(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
