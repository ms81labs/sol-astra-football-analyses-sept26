from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_BATCH_NAME = "v7_probe_threshold_contract_fix"
DEFAULT_OUTPUT_DIR_NAME = "v7_probe_threshold_contract_fix_v1"
LOW_CONF_PROFILE = "ball_probe_only_v1_low_conf_001"

BLOCKER_RAW_SIGNAL_RECOVERED = "v7_probe_raw_signal_recovered"
BLOCKER_PROPOSALS_RECOVERED = "v7_probe_proposals_recovered"
BLOCKER_SELECTED_RECOVERED = "v7_probe_selected_recovered"
BLOCKER_ACCEPTED_RECOVERED = "v7_probe_accepted_recovered"
BLOCKER_ZERO_RAW_SIGNAL = "v7_probe_zero_raw_signal_after_low_conf_contract"
BLOCKER_ARTIFACT_GAP = "v7_probe_threshold_contract_artifact_gap"

NEXT_PROPOSAL_INTEGRATION = "v7_probe_proposal_window_integration_fix"
NEXT_SELECTION_FOLLOWTHROUGH = "v7_probe_selection_followthrough_fix"
NEXT_ACCEPTANCE_FOLLOWTHROUGH = "v7_probe_acceptance_followthrough_fix"
NEXT_PRECISION_GUARDRAIL_AUDIT = "v7_probe_precision_guardrail_audit"
NEXT_PREPROCESSING_PATH = "v7_probe_preprocessing_path_fix"
NEXT_ARTIFACT_REFRESH = "v7_evaluation_proof_artifact_refresh"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
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


def _resolve_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _candidate_baseline_result(proof_report: dict[str, object]) -> dict[str, object]:
    result = proof_report.get("candidateBaselineResult")
    return dict(result) if isinstance(result, dict) else {}


def _nested_dict(payload: dict[str, object], *keys: str) -> dict[str, object]:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return dict(current) if isinstance(current, dict) else {}


def _proof_summary_from_report(proof_report: dict[str, object]) -> dict[str, object]:
    candidate_result = _candidate_baseline_result(proof_report)
    summary_path = _resolve_path(candidate_result.get("summaryPath"))
    if summary_path and summary_path.exists():
        return _load_json(summary_path)
    return _nested_dict(candidate_result, "summary")


def _trace_from_report(proof_report: dict[str, object]) -> dict[str, object]:
    candidate_result = _candidate_baseline_result(proof_report)
    for key in ("ballPipelineTracePath", "ball_pipeline_trace_path"):
        trace_path = _resolve_path(candidate_result.get(key))
        if trace_path and trace_path.exists():
            return _load_json(trace_path, required=False)
    summary = _proof_summary_from_report(proof_report)
    for key in ("ballPipelineTrace", "pipelineTrace"):
        trace = summary.get(key)
        if isinstance(trace, dict):
            return dict(trace)
    return {}


def _latest_candidate_baseline_pod_cycle(storage_root: Path) -> Path | None:
    pod_root = Path(storage_root) / "pod_cycles"
    if not pod_root.exists():
        return None
    candidates = [
        path
        for path in pod_root.glob("touchline-detector-candidate-v7-probe-assist-baseline-*")
        if (path / "proof_summary.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path / "proof_summary.json").stat().st_mtime)


def _count_first(payload: dict[str, object], keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in payload:
            return _safe_int(payload.get(key), 0)
    return 0


def _coverage_from_artifacts(
    *,
    storage_root: Path,
    proof_report: dict[str, object],
    evaluation_contract: dict[str, object],
) -> dict[str, object]:
    proof_summary = _proof_summary_from_report(proof_report)
    trace = _trace_from_report(proof_report)
    proof_source = "evaluation_proof_report"
    latest_pod_cycle = _latest_candidate_baseline_pod_cycle(storage_root)
    if latest_pod_cycle is not None:
        pod_trace = _load_json(latest_pod_cycle / "ball_pipeline_trace.json", required=False)
        pod_profile = str(pod_trace.get("auxiliaryBallModelProfile") or pod_trace.get("probeDetectorProfile") or "")
        if not proof_summary or pod_profile == LOW_CONF_PROFILE:
            proof_summary = _load_json(latest_pod_cycle / "proof_summary.json", required=False)
            trace = pod_trace
            proof_source = str(latest_pod_cycle)
    raw_frames = _count_first(
        proof_summary,
        (
            "rawProbeObservedBallFrames",
            "probeRawObservedBallFrames",
            "v7RawProbeObservedBallFrames",
        ),
    )
    filtered_frames = _count_first(
        proof_summary,
        (
            "probeObservedBallFrames",
            "filteredProbeObservedBallFrames",
            "v7ProbeObservedBallFrames",
        ),
    )
    proposal_frames = _count_first(
        proof_summary,
        (
            "proposalCandidateFrames",
            "bestProposalCandidateFrames",
            "recoveredCandidateFrames",
        ),
    )
    selected_frames = _count_first(
        proof_summary,
        (
            "recoveredSelectedFrames",
            "selectedBallFrames",
            "reviewedPositiveSelectedFrameCount",
        ),
    )
    accepted_frames = _count_first(
        proof_summary,
        (
            "acceptedBallFrames",
            "reviewedPositiveAcceptedFrameCount",
        ),
    )
    return {
        "auxiliaryBallModelProfile": evaluation_contract.get("auxiliaryBallModelProfile"),
        "traceProbeDetectorProfile": trace.get("probeDetectorProfile"),
        "probeRecoveryConf": trace.get("probeRecoveryConf"),
        "probeRecoveryImgsz": trace.get("probeRecoveryImgsz"),
        "rawProbeObservedBallFrames": raw_frames,
        "probeObservedBallFrames": filtered_frames,
        "proposalCandidateFrames": proposal_frames,
        "selectedFrames": selected_frames,
        "acceptedFrames": accepted_frames,
        "proofSummaryFieldsAvailable": bool(proof_summary),
        "traceFieldsAvailable": bool(trace),
        "proofSource": proof_source,
    }


def _classify(coverage: dict[str, object]) -> tuple[str, str, list[str]]:
    if not bool(coverage.get("proofSummaryFieldsAvailable")):
        return (
            BLOCKER_ARTIFACT_GAP,
            NEXT_ARTIFACT_REFRESH,
            ["The evaluation proof report does not expose a candidate baseline proof summary."],
        )
    raw_frames = _safe_int(coverage.get("rawProbeObservedBallFrames"), 0)
    probe_frames = _safe_int(coverage.get("probeObservedBallFrames"), 0)
    proposal_frames = _safe_int(coverage.get("proposalCandidateFrames"), 0)
    selected_frames = _safe_int(coverage.get("selectedFrames"), 0)
    accepted_frames = _safe_int(coverage.get("acceptedFrames"), 0)
    if accepted_frames > 0:
        return (
            BLOCKER_ACCEPTED_RECOVERED,
            NEXT_PRECISION_GUARDRAIL_AUDIT,
            ["Low-confidence v7 proof contract produced accepted frames; precision must be audited before any promotion path."],
        )
    if selected_frames > 0:
        return (
            BLOCKER_SELECTED_RECOVERED,
            NEXT_ACCEPTANCE_FOLLOWTHROUGH,
            ["Low-confidence v7 proof contract produced selected frames but not accepted frames."],
        )
    if proposal_frames > 0:
        return (
            BLOCKER_PROPOSALS_RECOVERED,
            NEXT_SELECTION_FOLLOWTHROUGH,
            ["Low-confidence v7 proof contract produced proposal/candidate frames but none were selected."],
        )
    if raw_frames > 0 or probe_frames > 0:
        return (
            BLOCKER_RAW_SIGNAL_RECOVERED,
            NEXT_PROPOSAL_INTEGRATION,
            ["Low-confidence v7 proof contract recovered raw/probe signal but no proposal frames."],
        )
    return (
        BLOCKER_ZERO_RAW_SIGNAL,
        NEXT_PREPROCESSING_PATH,
        ["The low-confidence v7 proof contract still produced zero raw probe frames."],
    )


def _markdown_summary(summary: dict[str, object], outcome: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Probe Threshold Contract Fix",
            "",
            f"- Goal achieved: `{outcome.get('goalAchieved')}`",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            f"- Raw probe frames: `{summary.get('rawProbeObservedBallFrames')}`",
            f"- Proposal frames: `{summary.get('proposalCandidateFrames')}`",
            f"- Selected frames: `{summary.get('selectedFrames')}`",
            f"- Accepted frames: `{summary.get('acceptedFrames')}`",
            "",
            str(outcome.get("englishSummary") or ""),
            "",
            str(outcome.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_probe_threshold_contract_fix(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    output_root = candidate_root / DEFAULT_OUTPUT_DIR_NAME
    evaluation_root = candidate_root / "evaluation_v1"
    evaluation_contract = _load_json(evaluation_root / "evaluation_contract.json", required=False)
    if not evaluation_contract:
        evaluation_contract = _load_json(candidate_root / "evaluation_contract.json", required=False)
    proof_report = _load_json(evaluation_root / "proof_report.json", required=False)
    coverage = _coverage_from_artifacts(
        storage_root=storage_root,
        proof_report=proof_report,
        evaluation_contract=evaluation_contract,
    )
    dominant, next_family, reasons = _classify(coverage)
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "trainingCandidateName": candidate_name,
        "attemptNumber": 1,
        "attemptApproachFamily": "proof_only_low_conf_probe_contract",
        "proofProfileExpected": LOW_CONF_PROFILE,
        "proofProfileObserved": coverage.get("auxiliaryBallModelProfile") or coverage.get("traceProbeDetectorProfile"),
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "runtimeDefaultMutationAllowed": False,
        **coverage,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "classificationReasons": reasons,
        "decisions": [
            {
                "condition": "accepted frames recovered",
                "matched": dominant == BLOCKER_ACCEPTED_RECOVERED,
                "nextCorrectiveFamily": NEXT_PRECISION_GUARDRAIL_AUDIT,
            },
            {
                "condition": "selected frames recovered but accepted remains zero",
                "matched": dominant == BLOCKER_SELECTED_RECOVERED,
                "nextCorrectiveFamily": NEXT_ACCEPTANCE_FOLLOWTHROUGH,
            },
            {
                "condition": "proposal frames recovered but selected remains zero",
                "matched": dominant == BLOCKER_PROPOSALS_RECOVERED,
                "nextCorrectiveFamily": NEXT_SELECTION_FOLLOWTHROUGH,
            },
            {
                "condition": "raw/probe frames recovered but proposal frames remain zero",
                "matched": dominant == BLOCKER_RAW_SIGNAL_RECOVERED,
                "nextCorrectiveFamily": NEXT_PROPOSAL_INTEGRATION,
            },
            {
                "condition": "raw probe signal remains zero",
                "matched": dominant == BLOCKER_ZERO_RAW_SIGNAL,
                "nextCorrectiveFamily": NEXT_PREPROCESSING_PATH,
            },
            {
                "condition": "proof artifacts are incomplete",
                "matched": dominant == BLOCKER_ARTIFACT_GAP,
                "nextCorrectiveFamily": NEXT_ARTIFACT_REFRESH,
            },
        ],
        "selectedNextCorrectiveFamily": next_family,
    }
    outcome = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "batchGoal": "Run a non-default low-confidence v7 probe contract and classify whether proof-level probe signal recovers.",
        "goalAchieved": dominant != BLOCKER_ARTIFACT_GAP,
        "roadmapAdvanceAllowed": False,
        "primaryBlocker": dominant,
        "nextRecommendedNextLever": next_family,
        "runtimeDefaultMutationAllowed": False,
        "englishSummary": f"V7 low-confidence threshold contract classified the proof result as {dominant}.",
        "englishDecision": f"Advance to {next_family}; do not promote v7 or mutate runtime defaults.",
    }
    _write_json(output_root / "threshold_contract_summary.json", summary)
    _write_json(output_root / "v7_probe_threshold_contract_coverage.json", coverage)
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
    payload = run_v7_probe_threshold_contract_fix(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
