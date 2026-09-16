from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT, summarize_match_benchmark  # noqa: E402
from backend.app.storage import Storage  # noqa: E402

STAGE_ORDER = [
    "processVideoPrimary",
    "processVideoRecovery",
    "processVideoReturnedRows",
    "persistRawRows",
    "normalizedFrames",
    "possessionOutputs",
    "eventOutputs",
]
STAGE_KEYS = [
    "ballRowCount",
    "ballFrameCount",
    "trackedPossessionFrames",
    "controlledPossessionFrames",
    "eventCount",
    "eventTypes",
]


def _load_trace(storage: Storage, match_id: str) -> dict[str, object]:
    return storage.load_analysis_artifact(match_id, "ball_pipeline_trace")


def _stage_map(trace: dict[str, object]) -> dict[str, dict[str, object]]:
    stages = trace.get("stages")
    if not isinstance(stages, list):
        return {}
    return {
        str(stage.get("stage")): dict(stage)
        for stage in stages
        if isinstance(stage, dict) and isinstance(stage.get("stage"), str)
    }


def _stage_diff(local_stage: dict[str, object], remote_stage: dict[str, object]) -> dict[str, object]:
    differing_keys = [
        key
        for key in STAGE_KEYS
        if local_stage.get(key) != remote_stage.get(key)
    ]
    return {
        "local": local_stage,
        "remote": remote_stage,
        "diverged": bool(differing_keys),
        "differingKeys": differing_keys,
    }


def _diagnosis_for_stage(first_diverging_stage: str | None, remote_truth_ready: bool) -> str:
    if first_diverging_stage in {"processVideoPrimary", "processVideoRecovery", "processVideoReturnedRows"}:
        return "diverges_before_returned_rows"
    if first_diverging_stage in {"persistRawRows", "normalizedFrames"}:
        return "diverges_during_import_normalization"
    if first_diverging_stage == "possessionOutputs":
        return "diverges_during_possession_assignment"
    if first_diverging_stage == "eventOutputs":
        return "diverges_during_event_detection"
    if not remote_truth_ready:
        return "no_divergence_but_truth_gates_fail"
    return "no_divergence_but_truth_gates_fail"


def compare_ball_pipeline_trace(
    *,
    local_match_id: str,
    remote_match_id: str,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
) -> dict[str, object]:
    storage = Storage(storage_root)
    local_trace = _load_trace(storage, local_match_id)
    remote_trace = _load_trace(storage, remote_match_id)
    local_stages = _stage_map(local_trace)
    remote_stages = _stage_map(remote_trace)

    stage_comparisons: dict[str, dict[str, object]] = {}
    first_diverging_stage: str | None = None
    for stage_name in STAGE_ORDER:
        local_stage = local_stages.get(stage_name, {"stage": stage_name})
        remote_stage = remote_stages.get(stage_name, {"stage": stage_name})
        comparison = _stage_diff(local_stage, remote_stage)
        stage_comparisons[stage_name] = comparison
        if first_diverging_stage is None and comparison["diverged"]:
            first_diverging_stage = stage_name

    remote_summary = summarize_match_benchmark(storage, remote_match_id)
    diagnosis = _diagnosis_for_stage(first_diverging_stage, bool(remote_summary.fiveMinuteTruthReady))
    return {
        "localMatchId": local_match_id,
        "remoteMatchId": remote_match_id,
        "firstDivergingStage": first_diverging_stage,
        "stageComparisons": stage_comparisons,
        "diagnosis": diagnosis,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local and remote ball pipeline traces.")
    parser.add_argument("--local-match-id", required=True)
    parser.add_argument("--remote-match-id", required=True)
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    args = parser.parse_args()

    payload = compare_ball_pipeline_trace(
        local_match_id=args.local_match_id,
        remote_match_id=args.remote_match_id,
        storage_root=Path(args.storage_root),
    )
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
