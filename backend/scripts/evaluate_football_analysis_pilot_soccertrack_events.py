from __future__ import annotations

from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
from math import ceil
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence

from backend.app.analytics import detect_events
from backend.app.schemas import BallOwnership
from backend.scripts.evaluate_football_analysis_pilot import evaluate_events, wilson_interval, _scoring_protocol
from backend.scripts.materialize_football_analysis_pilot_reference_intervals import reference_clock_offsets


REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_PATH = REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"
CORPUS_PATH = REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_corpus.json"
LABELS_PATH = REPO_ROOT / (
    "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/"
    "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1/sample_fixture_files/"
    "selected_match_117092/bas__117092__117092_12_class_events.json"
)
OUTPUT_PATH = REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_soccertrack_event_diagnostic.json"
ARTIFACTS = {
    "soccertrack-v2-117092-01": REPO_ROOT / "backend/storage/daytona-g-capacity-v7.3/matches/c43b571fdb1745a08b8209430bb65abe",
    "soccertrack-v2-117092-02": REPO_ROOT / "backend/storage/daytona-g-capacity-v7.3/matches/c43b571fdb1745a08b8209430bb65abe",
    "soccertrack-v2-117092-03": REPO_ROOT / "backend/storage/daytona-g-capacity-v7.3/matches/5b56cbd876664b9b9fe25b1c95515b8f",
}
CLASS_MAP = {"PASS": "pass", "HIGH PASS": "pass", "CROSS": "pass", "SHOT": "shot"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_tracking_continuity(frames: Sequence[Mapping[str, object]]) -> dict[str, object]:
    lifetimes: Counter[int] = Counter()
    player_rows = 0
    untracked_player_rows = 0
    for frame in frames:
        players = [
            player
            for key in ("myTeam", "enemies", "unassignedPlayers")
            for player in frame.get(key, [])
        ]
        player_rows += len(players)
        track_ids = [int(player["id"]) for player in players if player.get("id") is not None]
        untracked_player_rows += sum(track_id < 0 for track_id in track_ids)
        lifetimes.update({track_id for track_id in track_ids if track_id >= 0})
    lengths = sorted(lifetimes.values())
    short = sum(length <= 5 for length in lengths)
    return {
        "sampledFrames": len(frames),
        "playerRows": player_rows,
        "playerRowsPerSampledFrame": player_rows / len(frames) if frames else None,
        "untrackedPlayerRows": untracked_player_rows,
        "uniqueTrackIds": len(lengths),
        "sampledFramesPerTrack": {
            "median": median(lengths) if lengths else None,
            "p90NearestRank": lengths[ceil(0.9 * len(lengths)) - 1] if lengths else None,
            "maximum": lengths[-1] if lengths else None,
            "singleFrameTracks": sum(length == 1 for length in lengths),
            "atMostFiveFrameTracks": short,
            "atMostFiveFrameTrackShare": short / len(lengths) if lengths else None,
        },
    }


def build_event_truth(
    task: Mapping[str, object], actions: Sequence[Mapping[str, object]], *,
    reference_clock_offset_seconds: float = 0.0,
) -> list[dict[str, object]]:
    start = float(task["globalStartSeconds"]) + reference_clock_offset_seconds
    end = float(task["globalEndSeconds"]) + reference_clock_offset_seconds
    offset = float(task["globalStartSeconds"]) - float(task["localStartSeconds"]) + reference_clock_offset_seconds
    fps = float(task["sourceFps"])
    truth = []
    for index, action in enumerate(actions):
        event_type = CLASS_MAP.get(str(action.get("label") or "").upper())
        try:
            seconds = int(str(action["position"])) / 1000
        except (KeyError, TypeError, ValueError):
            continue
        if event_type is None or not start <= seconds < end:
            continue
        frame = round((seconds - offset) * fps)
        truth.append(
            {
                "eventId": f"soccertrack-117092-bas-{index:06d}",
                "type": event_type,
                "startFrame": frame,
                "endFrameExclusive": frame + 1,
                "team": "unknown",
            }
        )
    return truth


def _pool(task_results: Sequence[Mapping[str, object]], protocol: Mapping[str, object]) -> dict[str, object]:
    totals = {event_type: {"truth": 0, "predictions": 0, "truePositives": 0} for event_type in CLASS_MAP.values()}
    for result in task_results:
        for event_type, metrics in result["classes"].items():
            for key in totals[event_type]:
                totals[event_type][key] += metrics["counts"][key]
    pooled = {}
    level = float(protocol["confidenceIntervals"]["level"])
    bars = protocol["acceptance"]
    for event_type, counts in totals.items():
        true_positives = counts["truePositives"]
        precision = true_positives / counts["predictions"] if counts["predictions"] else None
        recall = true_positives / counts["truth"] if counts["truth"] else None
        pooled[event_type] = {
            "counts": {
                **counts,
                "falsePositives": counts["predictions"] - true_positives,
                "falseNegatives": counts["truth"] - true_positives,
            },
            "precision": precision,
            "precision95": wilson_interval(true_positives, counts["predictions"], level=level),
            "recall": recall,
            "recall95": wilson_interval(true_positives, counts["truth"], level=level),
            "diagnosticThresholdChecks": {
                "precision": precision is not None and precision >= float(bars["supportedEventPrecisionMinimum"]),
                "recall": recall is not None and recall >= float(bars["supportedEventRecallMinimum"]),
            },
        }
    return {"classes": pooled}


def main() -> None:
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))["tasks"]
    actions = json.loads(LABELS_PATH.read_text(encoding="utf-8"))["actions"]
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    source_id = "soccertrack-v2-117092"
    source = next(candidate for candidate in corpus["candidates"] if candidate.get("sourceId") == source_id)
    metadata_path = REPO_ROOT / corpus["validationPitchReferenceMaterialization"]["resultsBySource"][source_id]["metadataXmlPath"]
    clock_offsets = reference_clock_offsets(
        [task for task in tasks if task["sourceId"] == source_id], source["paths"], metadata_path
    )
    protocol = _scoring_protocol(CORPUS_PATH)
    task_results = []
    current_task_results = []
    prediction_hashes = {}
    frame_hashes = {}
    current_events_by_artifact = {}
    current_full_event_counts = {}
    tracking_continuity = {}
    for task in tasks:
        task_id = str(task["taskId"])
        artifact_dir = ARTIFACTS.get(task_id)
        if artifact_dir is None:
            continue
        events_path = artifact_dir / "events.json"
        truth = build_event_truth(
            task, actions, reference_clock_offset_seconds=clock_offsets[task_id]
        )
        result = evaluate_events(task, {"events": truth}, json.loads(events_path.read_text(encoding="utf-8")), protocol)
        result = json.loads(json.dumps(result, default=int))
        prediction_hashes[str(events_path.relative_to(REPO_ROOT))] = _sha256(events_path)
        task_results.append({"taskId": task_id, **result})
        if artifact_dir not in current_events_by_artifact:
            frames_path = artifact_dir / "frames.json"
            frames = json.loads(frames_path.read_text(encoding="utf-8"))
            current_events = detect_events(
                frames,
                [BallOwnership.model_validate(frame["possession"]) for frame in frames],
            )
            current_events_by_artifact[artifact_dir] = [event.model_dump() for event in current_events]
            frame_hashes[str(frames_path.relative_to(REPO_ROOT))] = _sha256(frames_path)
            current_full_event_counts[str(artifact_dir.relative_to(REPO_ROOT))] = dict(
                Counter(event.type for event in current_events)
            )
            tracking_continuity[str(frames_path.relative_to(REPO_ROOT))] = summarize_tracking_continuity(frames)
        current_result = evaluate_events(task, {"events": truth}, current_events_by_artifact[artifact_dir], protocol)
        current_task_results.append({"taskId": task_id, **json.loads(json.dumps(current_result, default=int))})
    payload = {
        "schemaVersion": "football_analysis_pilot_soccertrack_event_diagnostic_v3",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceId": "soccertrack-v2-117092",
        "taskIds": sorted(ARTIFACTS),
        "developmentDiagnosticOnly": True,
        "pilotAcceptanceEligible": False,
        "exclusionReasons": [
            "only the event stage and one validation source are scored",
            "the validation source informed prior development and diagnostics",
            "official left/right team labels are intentionally treated as unknown until home/away mapping is declared",
        ],
        "truthAlignment": "BAS position is tracker match milliseconds; use metadata's second-half anchor to map each frozen video task to source frames",
        "sourceMetadataXmlPath": str(metadata_path.relative_to(REPO_ROOT)),
        "sourceMetadataXmlSha256": _sha256(metadata_path),
        "truthReferenceClockOffsetsSecondsByTask": clock_offsets,
        "classMap": CLASS_MAP,
        "sourceLabelsPath": str(LABELS_PATH.relative_to(REPO_ROOT)),
        "sourceLabelsSha256": _sha256(LABELS_PATH),
        "predictionEventSha256ByPath": prediction_hashes,
        "trackingContinuityByPath": tracking_continuity,
        "taskResults": task_results,
        "pooled": _pool(task_results, protocol),
        "currentCodeRecalculation": {
            "method": "rerun detect_events from retained production frames and possession without changing stored artifacts",
            "inputFrameSha256ByPath": frame_hashes,
            "fullArtifactEventTypeCountsByPath": current_full_event_counts,
            "taskResults": current_task_results,
            "pooled": _pool(current_task_results, protocol),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["pooled"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
