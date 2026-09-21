# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT, summarize_match_benchmark
from backend.app.storage import Storage
from backend.scripts.run_trimmed_ball_recovery_matrix import run_local_ball_recovery_matrix


def _model_dump_payload(model: object) -> dict[str, object]:
    if isinstance(model, dict):
        return dict(model)
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    raise TypeError(f"Unsupported summary payload type: {type(model)!r}")


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _compact_remote_summary(summary: object) -> dict[str, object]:
    payload = _model_dump_payload(summary)
    return {
        "savedMatchId": payload.get("matchId"),
        "jobId": payload.get("jobId"),
        "detectorModelPath": payload.get("detectorModelPath"),
        "detectorModelName": payload.get("detectorModelName"),
        "rawRows": payload.get("rawRowCount", 0),
        "frameCount": payload.get("frameCount", 0),
        "playerFrames": payload.get("playerFrames", 0),
        "ballFrames": payload.get("withBallFrames", 0),
        "trackedPossessionFrames": payload.get("trackedPossessionFrames", 0),
        "controlledPossessionFrames": payload.get("controlledPossessionFrames", 0),
        "eventCount": payload.get("eventCount", 0),
        "eventTypes": payload.get("eventTypes", {}),
        "shotCount": payload.get("shotCount", 0),
        "ballSignalStatus": payload.get("ballSignalStatus"),
        "ballTrackViable": payload.get("ballTrackViable", False),
        "recoveryProfile": payload.get("recoveryProfileName"),
        "recoveryApplied": payload.get("recoveryApplied", False),
        "recoveredSelectedFrames": payload.get("recoveredSelectedFrames", 0),
        "dominantAnchorCoord": payload.get("dominantAnchorCoord"),
        "dominantAnchorCount": payload.get("dominantAnchorCount", 0),
        "dominantAnchorShare": payload.get("dominantAnchorShare", 0.0),
        "meanSourceCenterY": payload.get("meanSourceCenterY", 0.0),
        "meanSourceBoxArea": payload.get("meanSourceBoxArea", 0.0),
        "candidateEdgeShare": payload.get("candidateEdgeShare", 0.0),
        "selectedEdgeFrameShare": payload.get("selectedEdgeFrameShare", 0.0),
        "fiveMinuteTruthReady": payload.get("fiveMinuteTruthReady", False),
        "truthGateReasons": payload.get("truthGateReasons", []),
    }


def _compact_local_summary(local_payload: dict[str, object]) -> dict[str, object]:
    profiles = local_payload.get("profiles") or []
    best_profile = profiles[0] if profiles else {}
    if not isinstance(best_profile, dict):
        best_profile = {}
    best_selected_summary = best_profile.get("selectedSummary", {})
    if not isinstance(best_selected_summary, dict):
        best_selected_summary = {}
    return {
        "recommendedProfile": local_payload.get("recommendedProfile", "no_viable_profile"),
        "bestProfileName": best_profile.get("name"),
        "bestSelectedScore": best_profile.get("selectedScore", 0.0),
        "bestProfileViable": best_profile.get("viable", False),
        "bestSelectedSummary": best_selected_summary,
    }


def _diagnose_proof_gap(local_payload: dict[str, object], remote_payload: dict[str, object]) -> str:
    recommended_profile = local_payload.get("recommendedProfile", "no_viable_profile")
    if recommended_profile in {None, "no_viable_profile"}:
        return "local_not_viable"

    if _safe_int(remote_payload.get("ballFrames", 0), 0) <= 0:
        return "local_viable_but_remote_ball_missing"

    if bool(remote_payload.get("fiveMinuteTruthReady", False)):
        return "remote_truth_ready"

    return "remote_ball_present_but_truth_gates_failed"


def compare_local_remote_proof(
    *,
    video_path: Path,
    match_id: str,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
) -> dict[str, object]:
    local_payload = run_local_ball_recovery_matrix(video_path=video_path)
    remote_summary = summarize_match_benchmark(Storage(storage_root), match_id)
    local_compact = _compact_local_summary(local_payload)
    remote_compact = _compact_remote_summary(remote_summary)
    return {
        "videoPath": str(video_path),
        "matchId": match_id,
        "localRecommendedProfile": local_compact["recommendedProfile"],
        "localBestProfileName": local_compact["bestProfileName"],
        "localBestSelectedScore": local_compact["bestSelectedScore"],
        "localBestSelectedSummary": local_compact["bestSelectedSummary"],
        "remoteImportedBenchmark": remote_compact,
        "diagnosis": _diagnose_proof_gap(local_payload, remote_compact),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a local ball-recovery matrix run against a saved remote proof.")
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    args = parser.parse_args()

    payload = compare_local_remote_proof(
        video_path=Path(args.video_path),
        match_id=args.match_id,
        storage_root=Path(args.storage_root),
    )
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
