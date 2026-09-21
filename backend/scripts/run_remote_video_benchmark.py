from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import (  # noqa: E402
    DEFAULT_STORAGE_ROOT,
    DEFAULT_TRIMMED_CLIP_PATH,
    run_remote_video_benchmark,
)
from backend.app.schemas import HomographyPoint  # noqa: E402
from backend.app.settings import ProcessingSettings  # noqa: E402


def _json_model(model: object) -> dict[str, object]:
    return model.model_dump(mode="json")


def _compact_summary(model: object) -> dict[str, object]:
    payload = _json_model(model)
    return {
        "savedMatchId": payload.get("matchId"),
        "jobId": payload.get("jobId"),
        "detectorModelPath": payload.get("detectorModelPath"),
        "detectorModelName": payload.get("detectorModelName"),
        "rawRows": payload.get("rawRowCount", 0),
        "frameCount": payload.get("frameCount", 0),
        "playerFrames": payload.get("playerFrames", 0),
        "ballFrames": payload.get("withBallFrames", 0),
        "observedBallFrames": payload.get("observedBallFrames", 0),
        "inferredBallFrames": payload.get("inferredBallFrames", 0),
        "acceptedBallFrames": payload.get("acceptedBallFrames", 0),
        "trackingObservedBallFrames": payload.get("trackingObservedBallFrames", 0),
        "probeObservedBallFrames": payload.get("probeObservedBallFrames", 0),
        "probeOnlyObservedBallFrames": payload.get("probeOnlyObservedBallFrames", 0),
        "acceptedFromObservedFrames": payload.get("acceptedFromObservedFrames", 0),
        "acceptedFromObservedRatio": payload.get("acceptedFromObservedRatio", 0.0),
        "acceptedBallRatio": payload.get("acceptedBallRatio", 0.0),
        "acceptedSegmentCount": payload.get("acceptedSegmentCount", 0),
        "unknownGapCount": payload.get("unknownGapCount", 0),
        "longestUnknownGapFrames": payload.get("longestUnknownGapFrames", 0),
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
        "warmProofMode": payload.get("warmProofMode", False),
        "warmReadyObserved": payload.get("warmReadyObserved", False),
        "warmupWaitSeconds": payload.get("warmupWaitSeconds", 0.0),
        "fiveMinuteTruthReady": payload.get("fiveMinuteTruthReady", False),
        "fortyFiveMinuteTruthReady": payload.get("fortyFiveMinuteTruthReady", False),
        "truthGateReasons": payload.get("truthGateReasons", []),
    }


def _parse_manual_points(payload: str | None) -> list[HomographyPoint] | None:
    if payload is None:
        return None
    points = json.loads(payload)
    return [HomographyPoint(x=float(point[0]), y=float(point[1])) for point in points]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a video through Daytona, import results, and summarize the benchmark.")
    parser.add_argument("--video-path", default=str(DEFAULT_TRIMMED_CLIP_PATH))
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--name", default=None)
    parser.add_argument(
        "--manual-points-json",
        default=None,
        help='Four pitch corner points as JSON, e.g. "[[10,10],[1270,10],[1270,710],[10,710]]".',
    )
    args = parser.parse_args()

    settings = ProcessingSettings.from_env()
    if not settings.remote_enabled:
        parser.error(
            "Daytona remote processing is not configured. Set PROCESSING_BACKEND=daytona and DAYTONA_API_KEY."
        )

    payload = _compact_summary(
        run_remote_video_benchmark(
            storage_root=Path(args.storage_root),
            clip_path=Path(args.video_path),
            manual_points=_parse_manual_points(args.manual_points_json),
            settings=settings,
            name=args.name,
        )
    )
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
