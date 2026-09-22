from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_required as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "evaluation_failure_analysis_v1"
DEFAULT_BATCH_NAME = "touchline_detector_candidate_v7_evaluation_failure_analysis"

BLOCKER_ZERO_RAW_SIGNAL = "v7_auxiliary_probe_zero_raw_signal"
BLOCKER_RAW_NOT_PROPOSAL = "v7_raw_probe_not_materialized_into_proposals"
BLOCKER_SELECTION_FOLLOWTHROUGH = "v7_probe_candidates_not_selected"
BLOCKER_ACCEPTANCE_FOLLOWTHROUGH = "v7_selected_signal_not_accepted"
BLOCKER_PROOF_ARTIFACT_GAP = "v7_evaluation_artifact_coverage_gap"

NEXT_INTEGRATION_AUDIT = "v7_probe_assist_integration_audit"
NEXT_PROPOSAL_WINDOW_FIX = "v7_probe_proposal_window_integration_fix"
NEXT_SELECTION_FIX = "v7_probe_selection_followthrough_fix"
NEXT_ACCEPTANCE_FIX = "v7_probe_acceptance_followthrough_fix"
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






def _candidate_label(candidate_name: str) -> str:
    return f"{candidate_name}_probe_assist"


def _artifact_paths(storage_root: Path, candidate_name: str) -> dict[str, Path]:
    candidate_root = storage_root / "trained_detector_candidates" / candidate_name
    evaluation_root = candidate_root / "evaluation_v1"
    output_root = candidate_root / DEFAULT_OUTPUT_DIR_NAME
    suite_root = storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME
    return {
        "candidateRoot": candidate_root,
        "evaluationRoot": evaluation_root,
        "outputRoot": output_root,
        "evaluationSummaryPath": evaluation_root / "evaluation_summary.json",
        "screenMatrixPath": evaluation_root / "screen_matrix.json",
        "proofReportPath": evaluation_root / "proof_report.json",
        "trainingManifestPath": suite_root / "touchline_detector_candidate_v7_training_prep_v1" / "v7_training_manifest.json",
    }


def _proof_bundle_root_from_report(proof_report: dict[str, object]) -> Path | None:
    candidate_result = proof_report.get("candidateBaselineResult")
    candidate_result = candidate_result if isinstance(candidate_result, dict) else {}
    summary_path = candidate_result.get("summaryPath")
    if not isinstance(summary_path, str) or not summary_path.strip():
        return None
    path = Path(summary_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.parent


def _cell_by_label(screen_matrix: dict[str, object], label: str) -> dict[str, object]:
    for cell in list(screen_matrix.get("cells") or []):
        if isinstance(cell, dict) and str(cell.get("detectorLabel") or "") == label:
            return dict(cell)
    return {}


def _baseline_cell(screen_matrix: dict[str, object]) -> dict[str, object]:
    for cell in list(screen_matrix.get("cells") or []):
        if not isinstance(cell, dict):
            continue
        if str(cell.get("detectorLabel") or "") == "yolov10n.pt_baseline_full_detector":
            return dict(cell)
    return {}


def _max_profile_int(recovery_matrix: dict[str, object], field_names: tuple[str, ...]) -> int:
    best = 0
    for profile in list(recovery_matrix.get("profiles") or []):
        if not isinstance(profile, dict):
            continue
        for field_name in field_names:
            best = max(best, _safe_int(profile.get(field_name), 0))
    return best


def _training_manifest_alignment(training_manifest: dict[str, object]) -> dict[str, object]:
    positives = [item for item in list(training_manifest.get("positiveExamples") or []) if isinstance(item, dict)]
    negatives = [item for item in list(training_manifest.get("negativeExamples") or []) if isinstance(item, dict)]
    positives_with_bbox = sum(1 for item in positives if isinstance(item.get("bbox"), dict))
    rejected_as_positive = [
        item
        for item in positives
        if "negative" in str(item.get("truthUse") or "").lower()
        or "refuted" in str(item.get("truthUse") or "").lower()
    ]
    return {
        "positiveExampleCount": _safe_int(training_manifest.get("positiveExampleCount"), len(positives)),
        "negativeExampleCount": _safe_int(training_manifest.get("negativeExampleCount"), len(negatives)),
        "positiveRowsLoaded": len(positives),
        "negativeRowsLoaded": len(negatives),
        "positiveBBoxCount": positives_with_bbox,
        "positiveBBoxMissingCount": max(0, len(positives) - positives_with_bbox),
        "refutedOrNegativeRowsReusedAsPositiveCount": len(rejected_as_positive),
        "remainingPendingReviewCount": _safe_int(training_manifest.get("remainingPendingReviewCount"), 0),
        "positiveTruthPolicy": training_manifest.get("positiveTruthPolicy"),
        "negativeTruthPolicy": training_manifest.get("negativeTruthPolicy"),
    }


def _classify_blocker(
    *,
    proof_summary: dict[str, object],
    recovery_matrix: dict[str, object],
    candidate_cell: dict[str, object],
) -> tuple[str, str, list[str]]:
    raw_probe_frames = _safe_int(proof_summary.get("rawProbeObservedBallFrames"), 0)
    probe_frames = _safe_int(proof_summary.get("probeObservedBallFrames"), 0)
    candidate_frames = max(
        _safe_int(proof_summary.get("bestProposalCandidateFrames"), 0),
        _max_profile_int(recovery_matrix, ("proposalCandidateFrames", "candidateFrames")),
    )
    selected_frames = max(
        _safe_int(proof_summary.get("bestProposalSelectedFrames"), 0),
        _max_profile_int(recovery_matrix, ("selectedFrames", "proposalSelectedFrames")),
        _safe_int(candidate_cell.get("selectedFrames"), 0),
    )
    accepted_frames = _safe_int(proof_summary.get("acceptedBallFrames"), 0)
    if raw_probe_frames <= 0 and probe_frames <= 0:
        return (
            BLOCKER_ZERO_RAW_SIGNAL,
            NEXT_INTEGRATION_AUDIT,
            [
                "The v7 auxiliary probe produced zero raw/probe-observed frames in the bounded proof.",
                "Before retraining, verify the probe-assist invocation, preprocessing, thresholds, and model staging path.",
            ],
        )
    if candidate_frames <= 0:
        return (
            BLOCKER_RAW_NOT_PROPOSAL,
            NEXT_PROPOSAL_WINDOW_FIX,
            [
                "The v7 probe produced raw signal, but no proposal/candidate frames survived into the runtime proposal surface.",
            ],
        )
    if selected_frames <= 0:
        return (
            BLOCKER_SELECTION_FOLLOWTHROUGH,
            NEXT_SELECTION_FIX,
            [
                "The v7 probe produced candidate frames, but none became selected follow-through frames.",
            ],
        )
    if accepted_frames <= 0:
        return (
            BLOCKER_ACCEPTANCE_FOLLOWTHROUGH,
            NEXT_ACCEPTANCE_FIX,
            [
                "The v7 probe produced selected signal, but it did not write accepted ball truth.",
            ],
        )
    return (
        BLOCKER_PROOF_ARTIFACT_GAP,
        NEXT_PROOF_REFRESH,
        ["The saved artifacts do not explain why evaluation failed; refresh proof diagnostics before changing detector behavior."],
    )


def _markdown_summary(summary: dict[str, object], batch_outcome: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Evaluation Failure Analysis",
            "",
            f"- Goal achieved: `{batch_outcome.get('goalAchieved')}`",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            f"- Candidate screen viable: `{summary.get('candidateScreenViable')}`",
            f"- Candidate raw probe frames: `{summary.get('candidateRawProbeObservedBallFrames')}`",
            f"- Candidate accepted frames: `{summary.get('candidateAcceptedBallFrames')}`",
            "",
            str(batch_outcome.get("englishSummary") or ""),
            "",
            str(batch_outcome.get("englishDecision") or ""),
            "",
        ]
    )


def run_touchline_detector_candidate_v7_evaluation_failure_analysis(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    paths = _artifact_paths(storage_root, candidate_name)
    evaluation_summary = _load_json(paths["evaluationSummaryPath"])
    screen_matrix = _load_json(paths["screenMatrixPath"])
    proof_report = _load_json(paths["proofReportPath"])
    training_manifest = _load_json(paths["trainingManifestPath"])
    proof_root = _proof_bundle_root_from_report(proof_report)
    proof_summary = _load_json(proof_root / "proof_summary.json") if proof_root is not None else {}
    recovery_matrix = _load_json(proof_root / "recovery_profile_matrix.json", required=False) if proof_root is not None else {}
    selected_cluster_delta = _load_json(proof_root / "selected_cluster_delta.json", required=False) if proof_root is not None else {}
    ball_truth_layers = _load_json(proof_root / "ball_truth_layers.json", required=False) if proof_root is not None else {}

    candidate_cell = _cell_by_label(screen_matrix, _candidate_label(candidate_name))
    baseline_cell = _baseline_cell(screen_matrix)
    dominant_blocker, next_family, fixes = _classify_blocker(
        proof_summary=proof_summary,
        recovery_matrix=recovery_matrix,
        candidate_cell=candidate_cell,
    )
    manifest_alignment = _training_manifest_alignment(training_manifest)
    candidate_result = proof_report.get("candidateBaselineResult")
    candidate_result = candidate_result if isinstance(candidate_result, dict) else {}
    screen_delta = {
        "generatedAt": _utc_now_iso(),
        "candidateLabel": _candidate_label(candidate_name),
        "screenWinningDetectorLabel": screen_matrix.get("screenWinningDetectorLabel"),
        "baselineRecommendedProfileName": baseline_cell.get("recommendedProfileName"),
        "candidateRecommendedProfileName": candidate_cell.get("recommendedProfileName"),
        "baselineViable": bool(baseline_cell.get("viable")),
        "candidateViable": bool(candidate_cell.get("viable")),
        "baselineSelectedFrames": _safe_int(baseline_cell.get("selectedFrames"), 0),
        "candidateSelectedFrames": _safe_int(candidate_cell.get("selectedFrames"), 0),
        "baselineSelectedScore": _safe_float(baseline_cell.get("selectedScore"), 0.0),
        "candidateSelectedScore": _safe_float(candidate_cell.get("selectedScore"), 0.0),
        "candidateSummaryPresent": bool(candidate_cell.get("candidateSummary")),
        "selectedSummaryPresent": bool(candidate_cell.get("selectedSummary")),
    }
    proof_taxonomy = {
        "generatedAt": _utc_now_iso(),
        "dominantBlockerClass": dominant_blocker,
        "nextCorrectiveFamily": next_family,
        "candidateRawProbeObservedBallFrames": _safe_int(proof_summary.get("rawProbeObservedBallFrames"), 0),
        "candidateProbeObservedBallFrames": _safe_int(proof_summary.get("probeObservedBallFrames"), 0),
        "candidateBestProposalRawDetectedFrames": _safe_int(proof_summary.get("bestProposalRawDetectedFrames"), 0),
        "candidateBestProposalCandidateFrames": _safe_int(proof_summary.get("bestProposalCandidateFrames"), 0),
        "candidateBestProposalSelectedFrames": _safe_int(proof_summary.get("bestProposalSelectedFrames"), 0),
        "candidateAcceptedBallFrames": _safe_int(proof_summary.get("acceptedBallFrames"), 0),
        "candidateControlledPossessionFrames": _safe_int(proof_summary.get("controlledPossessionFrames"), 0),
        "candidateBallTrackViable": bool(proof_summary.get("ballTrackViable")),
        "truthGateReasons": list(proof_summary.get("truthGateReasons") or []),
        "recoveryProfileCount": len(list(recovery_matrix.get("profiles") or [])),
        "selectedClusterDeltaAvailable": bool(selected_cluster_delta),
        "ballTruthLayersAvailable": bool(ball_truth_layers),
    }
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "trainingCandidateName": candidate_name,
        "evaluationBatchName": evaluation_summary.get("evaluationBatchName"),
        "evaluationPrimaryBlocker": evaluation_summary.get("evaluationPrimaryBlocker"),
        "screenCompleted": bool(evaluation_summary.get("screenCompleted")),
        "screenWinningDetectorLabel": evaluation_summary.get("screenWinningDetectorLabel"),
        "candidateScreenViable": bool(candidate_cell.get("viable")),
        "candidateBaselineProductBeatsPlateau": bool(evaluation_summary.get("candidateBaselineProductBeatsPlateau")),
        "candidateRawProbeObservedBallFrames": proof_taxonomy["candidateRawProbeObservedBallFrames"],
        "candidateProbeObservedBallFrames": proof_taxonomy["candidateProbeObservedBallFrames"],
        "candidateBestProposalRawDetectedFrames": proof_taxonomy["candidateBestProposalRawDetectedFrames"],
        "candidateBestProposalCandidateFrames": proof_taxonomy["candidateBestProposalCandidateFrames"],
        "candidateBestProposalSelectedFrames": proof_taxonomy["candidateBestProposalSelectedFrames"],
        "candidateAcceptedBallFrames": proof_taxonomy["candidateAcceptedBallFrames"],
        "candidateControlledPossessionFrames": proof_taxonomy["candidateControlledPossessionFrames"],
        "candidateBallTrackViable": proof_taxonomy["candidateBallTrackViable"],
        "candidateProofSummaryPath": candidate_result.get("summaryPath"),
        "dominantBlockerClass": dominant_blocker,
        "nextCorrectiveFamily": next_family,
        "runtimeDefaultMutationAllowed": False,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "decisions": [
            {
                "condition": "raw probe signal is zero",
                "matched": dominant_blocker == BLOCKER_ZERO_RAW_SIGNAL,
                "nextCorrectiveFamily": NEXT_INTEGRATION_AUDIT,
            },
            {
                "condition": "raw probe exists but proposals are zero",
                "matched": dominant_blocker == BLOCKER_RAW_NOT_PROPOSAL,
                "nextCorrectiveFamily": NEXT_PROPOSAL_WINDOW_FIX,
            },
            {
                "condition": "candidate/proposal rows exist but selected frames are zero",
                "matched": dominant_blocker == BLOCKER_SELECTION_FOLLOWTHROUGH,
                "nextCorrectiveFamily": NEXT_SELECTION_FIX,
            },
            {
                "condition": "selected frames exist but accepted frames are zero",
                "matched": dominant_blocker == BLOCKER_ACCEPTANCE_FOLLOWTHROUGH,
                "nextCorrectiveFamily": NEXT_ACCEPTANCE_FIX,
            },
        ],
        "selectedNextCorrectiveFamily": next_family,
    }
    batch_outcome = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "batchGoal": "Diagnose why touchline_detector_candidate_v7 evaluation produced zero useful accepted frames.",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": False,
        "primaryBlocker": dominant_blocker,
        "nextRecommendedNextLever": next_family,
        "runtimeDefaultMutationAllowed": False,
        "englishSummary": (
            f"V7 evaluation failed because generated proof artifacts classify the dominant blocker as {dominant_blocker}."
        ),
        "englishDecision": (
            f"Do not promote v7. Advance to {next_family} and keep runtime defaults frozen."
        ),
        "brainstormFixes": fixes,
    }

    output_root = paths["outputRoot"]
    _write_json(output_root / "v7_evaluation_failure_summary.json", summary)
    _write_json(output_root / "v7_screen_probe_delta.json", screen_delta)
    _write_json(output_root / "v7_probe_failure_taxonomy.json", proof_taxonomy)
    _write_json(output_root / "v7_training_manifest_alignment.json", manifest_alignment)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(
        _markdown_summary(summary, batch_outcome),
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
    payload = run_touchline_detector_candidate_v7_evaluation_failure_analysis(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
