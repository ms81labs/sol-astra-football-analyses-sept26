from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_probe_assist_integration_audit_v1"
DEFAULT_BATCH_NAME = "v7_probe_assist_integration_audit"

BLOCKER_MODEL_PATH_MISSING = "v7_probe_model_path_missing"
BLOCKER_RUNTIME_OPTION_MISSING = "v7_probe_runtime_option_missing"
BLOCKER_NOT_INVOKED = "v7_auxiliary_detector_not_invoked"
BLOCKER_OUTPUT_NOT_COUNTED = "v7_probe_output_not_counted"
BLOCKER_PREPROCESSING_THRESHOLD = "v7_preprocessing_or_threshold_mismatch"
BLOCKER_MODEL_QUALITY = "v7_model_quality_failure"
BLOCKER_ARTIFACT_GAP = "v7_probe_artifact_gap"

NEXT_RUNTIME_CONTRACT_FIX = "v7_probe_assist_runtime_contract_fix"
NEXT_THRESHOLD_PREPROCESSING_FIX = "v7_probe_threshold_preprocessing_fix"
NEXT_TRAINING_DATA_REFRESH = "v7_training_data_quality_refresh"
NEXT_PROOF_REFRESH = "v7_evaluation_proof_artifact_refresh"


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


def _load_json(path: Path, *, required: bool = True) -> dict[str, object]:
    if not path.exists():
        if required:
            raise FileNotFoundError(str(path))
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _artifact_paths(storage_root: Path, candidate_name: str) -> dict[str, Path]:
    candidate_root = storage_root / "trained_detector_candidates" / candidate_name
    evaluation_root = candidate_root / "evaluation_v1"
    return {
        "candidateRoot": candidate_root,
        "outputRoot": candidate_root / DEFAULT_OUTPUT_DIR_NAME,
        "contractPath": candidate_root / "evaluation_contract.json",
        "trainingSummaryPath": candidate_root / "training_run_summary.json",
        "evaluationSummaryPath": evaluation_root / "evaluation_summary.json",
        "proofReportPath": evaluation_root / "proof_report.json",
    }


def _resolve_path(path_value: object) -> Path | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _proof_root_from_report(proof_report: dict[str, object]) -> Path | None:
    result = proof_report.get("candidateBaselineResult")
    result = result if isinstance(result, dict) else {}
    return _resolve_path(result.get("summaryPath")).parent if _resolve_path(result.get("summaryPath")) else None


def _nested_path(payload: dict[str, object], *keys: str) -> object:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _build_model_path_audit(contract: dict[str, object]) -> dict[str, object]:
    best_path = _resolve_path(
        contract.get("candidateAuxiliaryBallModelPath")
        or _nested_path(contract, "candidateWeights", "bestWeightsPath")
    )
    last_path = _resolve_path(_nested_path(contract, "candidateWeights", "lastWeightsPath"))
    return {
        "generatedAt": _utc_now_iso(),
        "bestWeightsPath": str(best_path) if best_path else None,
        "bestWeightsPathPresent": best_path is not None,
        "bestWeightsPathExists": bool(best_path and best_path.exists()),
        "lastWeightsPath": str(last_path) if last_path else None,
        "lastWeightsPathExists": bool(last_path and last_path.exists()),
        "candidateReadyForEvaluation": bool(contract.get("candidateReadyForEvaluation")),
    }


def _build_runtime_option_audit(
    *,
    contract: dict[str, object],
    proof_report: dict[str, object],
    trace: dict[str, object],
) -> dict[str, object]:
    result = proof_report.get("candidateBaselineResult")
    result = result if isinstance(result, dict) else {}
    return {
        "generatedAt": _utc_now_iso(),
        "contractAuxiliaryBallModelPathPresent": bool(contract.get("candidateAuxiliaryBallModelPath")),
        "contractAuxiliaryBallModelProfile": contract.get("auxiliaryBallModelProfile"),
        "proofReportAuxiliaryBallModelPathPresent": bool(result.get("auxiliaryBallModelPath")),
        "proofReportAuxiliaryBallModelProfile": result.get("auxiliaryBallModelProfile"),
        "traceAuxiliaryBallModelPathPresent": bool(trace.get("auxiliaryBallModelPath")),
        "traceProbeModelPathPresent": bool(trace.get("probeModelPath")),
        "traceAuxiliaryBallModelProfile": trace.get("auxiliaryBallModelProfile"),
        "traceProbeDetectorProfile": trace.get("probeDetectorProfile"),
    }


def _build_invocation_audit(trace: dict[str, object], proof_summary: dict[str, object]) -> dict[str, object]:
    phase_timings = trace.get("phaseTimings")
    phase_timings = phase_timings if isinstance(phase_timings, dict) else {}
    probe_seconds = _safe_float(phase_timings.get("probeObservedPassSeconds"), 0.0)
    raw_probe_frames = _safe_int(proof_summary.get("rawProbeObservedBallFrames"), 0)
    probe_frames = _safe_int(proof_summary.get("probeObservedBallFrames"), 0)
    filtered_frames = _safe_int(proof_summary.get("filteredProbeObservedBallFrames"), 0)
    suppressed_frames = _safe_int(proof_summary.get("suppressedProbeObservedBallFrames"), 0)
    return {
        "generatedAt": _utc_now_iso(),
        "ballPipelineTraceAvailable": bool(trace),
        "probeObservedPassSeconds": probe_seconds,
        "probePassAppearsInvoked": probe_seconds > 0.0,
        "rawProbeObservedBallFrames": raw_probe_frames,
        "probeObservedBallFrames": probe_frames,
        "filteredProbeObservedBallFrames": filtered_frames,
        "suppressedProbeObservedBallFrames": suppressed_frames,
        "probeOutputRowsExistBeforeCounting": raw_probe_frames + probe_frames + filtered_frames + suppressed_frames > 0,
    }


def _classify(
    *,
    model_audit: dict[str, object],
    runtime_audit: dict[str, object],
    invocation_audit: dict[str, object],
) -> tuple[str, str, list[str]]:
    if not model_audit.get("bestWeightsPathPresent") or not model_audit.get("bestWeightsPathExists"):
        return (
            BLOCKER_MODEL_PATH_MISSING,
            NEXT_RUNTIME_CONTRACT_FIX,
            ["The v7 evaluation contract does not resolve to an existing best.pt path."],
        )
    if not runtime_audit.get("contractAuxiliaryBallModelPathPresent") or not runtime_audit.get("proofReportAuxiliaryBallModelPathPresent"):
        return (
            BLOCKER_RUNTIME_OPTION_MISSING,
            NEXT_RUNTIME_CONTRACT_FIX,
            ["The v7 auxiliary model path/profile is not consistently present in contract and proof artifacts."],
        )
    if not runtime_audit.get("traceAuxiliaryBallModelPathPresent") and not runtime_audit.get("traceProbeModelPathPresent"):
        return (
            BLOCKER_RUNTIME_OPTION_MISSING,
            NEXT_RUNTIME_CONTRACT_FIX,
            ["The proof trace does not show the auxiliary/probe model path."],
        )
    if not invocation_audit.get("ballPipelineTraceAvailable"):
        return (
            BLOCKER_ARTIFACT_GAP,
            NEXT_PROOF_REFRESH,
            ["The proof did not emit ball_pipeline_trace.json, so invocation cannot be proven."],
        )
    if not invocation_audit.get("probePassAppearsInvoked"):
        return (
            BLOCKER_NOT_INVOKED,
            NEXT_RUNTIME_CONTRACT_FIX,
            ["The proof trace is present, but probeObservedPassSeconds is zero."],
        )
    if invocation_audit.get("probeOutputRowsExistBeforeCounting"):
        return (
            BLOCKER_OUTPUT_NOT_COUNTED,
            NEXT_RUNTIME_CONTRACT_FIX,
            ["The proof contains probe output counters before accepted counting, but they do not materialize downstream."],
        )
    return (
        BLOCKER_PREPROCESSING_THRESHOLD,
        NEXT_THRESHOLD_PREPROCESSING_FIX,
        ["The v7 auxiliary model is staged and invoked, but produces zero probe detections; audit preprocessing, image size, class id, and confidence threshold."],
    )


def _markdown_summary(summary: dict[str, object], outcome: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Probe Assist Integration Audit",
            "",
            f"- Goal achieved: `{outcome.get('goalAchieved')}`",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            f"- Best weights exist: `{summary.get('bestWeightsPathExists')}`",
            f"- Probe pass invoked: `{summary.get('probePassAppearsInvoked')}`",
            f"- Raw probe frames: `{summary.get('rawProbeObservedBallFrames')}`",
            "",
            str(outcome.get("englishSummary") or ""),
            "",
            str(outcome.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_probe_assist_integration_audit(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    paths = _artifact_paths(storage_root, candidate_name)
    contract = _load_json(paths["contractPath"])
    training_summary = _load_json(paths["trainingSummaryPath"])
    evaluation_summary = _load_json(paths["evaluationSummaryPath"])
    proof_report = _load_json(paths["proofReportPath"])
    proof_root = _proof_root_from_report(proof_report)
    proof_summary = _load_json(proof_root / "proof_summary.json") if proof_root is not None else {}
    trace = _load_json(proof_root / "ball_pipeline_trace.json", required=False) if proof_root is not None else {}

    model_audit = _build_model_path_audit(contract)
    runtime_audit = _build_runtime_option_audit(contract=contract, proof_report=proof_report, trace=trace)
    invocation_audit = _build_invocation_audit(trace, proof_summary)
    dominant_blocker, next_family, reasons = _classify(
        model_audit=model_audit,
        runtime_audit=runtime_audit,
        invocation_audit=invocation_audit,
    )
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "trainingCandidateName": candidate_name,
        "attemptNumber": 1,
        "attemptApproachFamily": "probe_assist_invocation_audit",
        "trainingCompleted": bool(training_summary.get("trainingCompleted")),
        "weightsReady": bool(training_summary.get("weightsReady")),
        "screenCompleted": bool(evaluation_summary.get("screenCompleted")),
        "evaluationPrimaryBlocker": evaluation_summary.get("evaluationPrimaryBlocker"),
        "bestWeightsPathExists": bool(model_audit.get("bestWeightsPathExists")),
        "proofReportAuxiliaryBallModelPathPresent": bool(runtime_audit.get("proofReportAuxiliaryBallModelPathPresent")),
        "traceAuxiliaryBallModelPathPresent": bool(runtime_audit.get("traceAuxiliaryBallModelPathPresent")),
        "probePassAppearsInvoked": bool(invocation_audit.get("probePassAppearsInvoked")),
        "probeObservedPassSeconds": invocation_audit.get("probeObservedPassSeconds"),
        "rawProbeObservedBallFrames": invocation_audit.get("rawProbeObservedBallFrames"),
        "probeObservedBallFrames": invocation_audit.get("probeObservedBallFrames"),
        "dominantBlockerClass": dominant_blocker,
        "nextCorrectiveFamily": next_family,
        "runtimeDefaultMutationAllowed": False,
    }
    taxonomy = {
        "generatedAt": _utc_now_iso(),
        "dominantBlockerClass": dominant_blocker,
        "nextCorrectiveFamily": next_family,
        "classificationReasons": reasons,
        "candidateBlockerClasses": [
            BLOCKER_MODEL_PATH_MISSING,
            BLOCKER_RUNTIME_OPTION_MISSING,
            BLOCKER_NOT_INVOKED,
            BLOCKER_OUTPUT_NOT_COUNTED,
            BLOCKER_PREPROCESSING_THRESHOLD,
            BLOCKER_MODEL_QUALITY,
            BLOCKER_ARTIFACT_GAP,
        ],
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "decisions": [
            {
                "condition": "model path missing",
                "matched": dominant_blocker == BLOCKER_MODEL_PATH_MISSING,
                "nextCorrectiveFamily": NEXT_RUNTIME_CONTRACT_FIX,
            },
            {
                "condition": "runtime option missing",
                "matched": dominant_blocker == BLOCKER_RUNTIME_OPTION_MISSING,
                "nextCorrectiveFamily": NEXT_RUNTIME_CONTRACT_FIX,
            },
            {
                "condition": "auxiliary detector not invoked",
                "matched": dominant_blocker == BLOCKER_NOT_INVOKED,
                "nextCorrectiveFamily": NEXT_RUNTIME_CONTRACT_FIX,
            },
            {
                "condition": "probe invoked with zero signal",
                "matched": dominant_blocker == BLOCKER_PREPROCESSING_THRESHOLD,
                "nextCorrectiveFamily": NEXT_THRESHOLD_PREPROCESSING_FIX,
            },
        ],
        "selectedNextCorrectiveFamily": next_family,
    }
    outcome = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "batchGoal": "Audit why touchline_detector_candidate_v7 probe-assist produced zero raw probe signal.",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": False,
        "primaryBlocker": dominant_blocker,
        "nextRecommendedNextLever": next_family,
        "runtimeDefaultMutationAllowed": False,
        "englishSummary": f"V7 probe-assist audit classified the blocker as {dominant_blocker}.",
        "englishDecision": f"Advance to {next_family}; do not promote v7 or mutate runtime defaults.",
    }

    output_root = paths["outputRoot"]
    _write_json(output_root / "v7_probe_assist_integration_summary.json", summary)
    _write_json(output_root / "model_path_audit.json", model_audit)
    _write_json(output_root / "runtime_option_audit.json", runtime_audit)
    _write_json(output_root / "probe_invocation_audit.json", invocation_audit)
    _write_json(output_root / "v7_probe_assist_failure_taxonomy.json", taxonomy)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(
        _markdown_summary(summary, outcome),
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = run_v7_probe_assist_integration_audit(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
