from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .run_benchmarks import summarize_match_benchmark
from .storage import Storage

SCHEMA_VERSION = "match_bundle_v1"


def _optional_artifact(storage: Storage, match_id: str, artifact_name: str) -> dict[str, Any] | None:
    try:
        return storage.load_analysis_artifact(match_id, artifact_name)
    except FileNotFoundError:
        return None


def build_match_bundle(storage: Storage, match_id: str) -> dict[str, Any]:
    match = storage.get_match(match_id)
    frames = storage.load_frames(match_id)
    summary, assignments, formation_timeline, shots = storage.load_analytics(match_id)
    events = storage.load_events(match_id)
    accepted_match_state = _optional_artifact(storage, match_id, "accepted_match_state")
    ball_truth_layers = _optional_artifact(storage, match_id, "ball_truth_layers")
    ball_pipeline_trace = _optional_artifact(storage, match_id, "ball_pipeline_trace")
    proof_runtime_options = _optional_artifact(storage, match_id, "proof_runtime_options")
    recovery_debug = _optional_artifact(storage, match_id, "recovery_debug")

    try:
        benchmark = summarize_match_benchmark(storage, match_id).model_dump(mode="json")
    except (FileNotFoundError, KeyError, ValueError, TypeError):
        benchmark = None

    artifact_availability = {
        "frames": True,
        "analytics": True,
        "events": True,
        "acceptedMatchState": accepted_match_state is not None,
        "ballTruthLayers": ball_truth_layers is not None,
        "ballPipelineTrace": ball_pipeline_trace is not None,
        "proofRuntimeOptions": proof_runtime_options is not None,
        "recoveryDebug": recovery_debug is not None,
        "benchmark": benchmark is not None,
    }
    exports = {
        "matchJson": f"/api/matches/{match_id}/export/match.json",
        "framesCsv": f"/api/matches/{match_id}/export/frames.csv",
        "eventsCsv": f"/api/matches/{match_id}/export/events.csv",
        "reportHtml": f"/api/matches/{match_id}/report/html",
        "benchmark": f"/api/matches/{match_id}/benchmark",
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "match": match.model_dump(mode="json"),
        "provenance": {
            "deterministicCore": True,
            "llmGenerated": False,
            "storageArtifactsAreSourceOfTruth": True,
        },
        "artifactAvailability": artifact_availability,
        "exports": exports,
        "frames": [frame.model_dump(mode="json") for frame in frames],
        "analytics": {
            "summary": summary.model_dump(mode="json"),
            "ballAssignments": [assignment.model_dump(mode="json") for assignment in assignments],
            "formationTimeline": [segment.model_dump(mode="json") for segment in formation_timeline],
            "shots": [shot.model_dump(mode="json") for shot in shots],
        },
        "events": [event.model_dump(mode="json") for event in events],
        "acceptedMatchState": accepted_match_state,
        "ballTruthLayers": ball_truth_layers,
        "ballPipelineTrace": ball_pipeline_trace,
        "proofRuntimeOptions": proof_runtime_options,
        "recoveryDebug": recovery_debug,
        "benchmark": benchmark,
    }
