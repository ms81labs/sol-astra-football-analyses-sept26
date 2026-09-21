from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "residual_segment_selection_microfix_v1"
DEFAULT_RESIDUAL_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_residual_proposal_generation_fix_v1"
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_BATCH_NAME = "residual_segment_selection_microfix"

BUCKET_SEGMENT_LENGTH = "residual_segment_length_rejected"
BUCKET_CONTINUITY = "residual_continuity_rejected"
BUCKET_REPEATED_ANCHOR = "residual_repeated_anchor_rejected"
BUCKET_EDGE_SHARE = "residual_edge_share_rejected"
BUCKET_PROFILE_RANKING = "residual_profile_ranking_rejected"
BUCKET_SELECTED_NOT_ACCEPTED = "residual_selected_not_accepted"
BUCKET_ACCEPTED = "residual_already_accepted"
BUCKET_ARTIFACT_GAP = "residual_selection_artifact_gap"


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json_dict(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _frame_id(row: dict[str, Any]) -> int | None:
    for key in ("frameIndex", "Frame_ID", "frameId", "frame"):
        if key in row:
            frame_id = _safe_int(row.get(key), -1)
            if frame_id >= 0:
                return frame_id
    return None


def _proof_diagnostics_by_frame(proof_matrix: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for profile in _list_dicts(proof_matrix.get("profiles")):
        if profile.get("name") != "proposal_windows_075":
            continue
        for diagnostic in _list_dicts(profile.get("proposalFrameDiagnostics")):
            frame_id = _frame_id(diagnostic)
            if frame_id is not None:
                rows[frame_id] = diagnostic
    return rows


def _collapsed_not_selected_frames(residual_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in _list_dicts(residual_matrix.get("reviewedPositiveFrames")):
        if not bool(row.get("isResidual")):
            continue
        if row.get("gapClass") != "residual_collapsed_not_selected":
            continue
        rows.append(row)
    return sorted(rows, key=lambda row: _safe_int(row.get("frameIndex"), -1))


def _classify_trace(diagnostic: dict[str, Any]) -> str:
    if bool(diagnostic.get("accepted")):
        return BUCKET_ACCEPTED
    if bool(diagnostic.get("selected")):
        return BUCKET_SELECTED_NOT_ACCEPTED
    trace = diagnostic.get("selectionGateTrace")
    if not isinstance(trace, dict) or not trace:
        return BUCKET_ARTIFACT_GAP
    if bool(trace.get("segmentLengthRejected")):
        return BUCKET_SEGMENT_LENGTH
    if bool(trace.get("continuityRejected")):
        return BUCKET_CONTINUITY
    if bool(trace.get("repeatedAnchorRejected")):
        return BUCKET_REPEATED_ANCHOR
    if bool(trace.get("edgeShareRejected")):
        return BUCKET_EDGE_SHARE
    if bool(trace.get("selectedProfileRankingRejected")):
        return BUCKET_PROFILE_RANKING
    return BUCKET_ARTIFACT_GAP


def _dominant(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return BUCKET_ARTIFACT_GAP, 0
    priority = {
        BUCKET_SEGMENT_LENGTH: 0,
        BUCKET_CONTINUITY: 1,
        BUCKET_REPEATED_ANCHOR: 2,
        BUCKET_EDGE_SHARE: 3,
        BUCKET_PROFILE_RANKING: 4,
        BUCKET_SELECTED_NOT_ACCEPTED: 5,
        BUCKET_ACCEPTED: 6,
        BUCKET_ARTIFACT_GAP: 7,
    }
    return sorted(counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[0]


def _next_family(
    *,
    dominant_class: str,
    residual_selected_count: int,
    residual_accepted_count: int,
    accepted_retention_ratio: float,
    promotion_gate_passed: bool,
) -> str:
    if promotion_gate_passed or accepted_retention_ratio > 0.102:
        return "validate_promoted_touchline_runtime_default"
    if residual_accepted_count > 0:
        return "accepted_retention_guardrail_audit"
    if residual_selected_count > 0:
        return "reviewed_positive_acceptance_fix"
    if dominant_class == BUCKET_SEGMENT_LENGTH:
        return "residual_selected_segment_microprofile"
    if dominant_class == BUCKET_ARTIFACT_GAP:
        return "proof_selection_gate_trace_refresh"
    return "accepted_retention_denominator_audit"


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Residual Segment Selection Microfix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- collapsedNotSelectedFrameIds: {summary.get('collapsedNotSelectedFrameIds')}",
            f"- residualSelectedFrameCount: {summary.get('residualSelectedFrameCount')}",
            f"- residualAcceptedFrameCount: {summary.get('residualAcceptedFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- acceptedRetentionRatio: {summary.get('retentionTruth', {}).get('acceptedRetentionRatio')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_residual_segment_selection_microfix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    residual_root: Path = DEFAULT_RESIDUAL_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    attempt_number: int = 1,
    attempt_approach_family: str = "residual_selection_gate_trace_refresh",
) -> dict[str, Any]:
    output_root = Path(output_root)
    residual_root = Path(residual_root)
    promoted_proof_root = Path(promoted_proof_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)

    residual_matrix = _load_json_dict(residual_root / "residual_reviewed_positive_frame_matrix.json")
    residual_summary = _load_optional_json_dict(residual_root / "residual_proposal_generation_summary.json")
    recovery_profile_matrix = _load_optional_json_dict(promoted_proof_root / "recovery_profile_matrix.json")
    proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")
    retention_summary = _load_optional_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(suite_root / "suite_summary.json")

    proof_by_frame = _proof_diagnostics_by_frame(recovery_profile_matrix)
    collapsed_rows = _collapsed_not_selected_frames(residual_matrix)
    frame_rows: list[dict[str, Any]] = []
    for row in collapsed_rows:
        frame_id = _safe_int(row.get("frameIndex"), -1)
        diagnostic = proof_by_frame.get(frame_id, {})
        trace = diagnostic.get("selectionGateTrace") if isinstance(diagnostic.get("selectionGateTrace"), dict) else {}
        gap_class = _classify_trace(diagnostic)
        frame_rows.append(
            {
                "frameIndex": frame_id,
                "reviewedBBox": row.get("reviewedBBox"),
                "proposalGenerated": bool(diagnostic.get("proposalGenerated")),
                "rawDetected": bool(diagnostic.get("rawDetected")),
                "collapsed": bool(diagnostic.get("collapsed")),
                "selected": bool(diagnostic.get("selected")),
                "accepted": bool(diagnostic.get("accepted")),
                "proposalWindowKinds": list(diagnostic.get("proposalWindowKinds") or []),
                "gapClass": gap_class,
                "selectionGateTrace": dict(trace),
                "acceptanceGateTrace": dict(diagnostic.get("acceptanceGateTrace") or {}),
            }
        )

    counts = Counter(str(row["gapClass"]) for row in frame_rows)
    dominant_class, dominant_count = _dominant(dict(counts))
    residual_selected_count = sum(1 for row in frame_rows if bool(row.get("selected")))
    residual_accepted_count = sum(1 for row in frame_rows if bool(row.get("accepted")))
    accepted_retention_ratio = _safe_float(retention_summary.get("acceptedRetentionRatio"), 0.0)
    promotion_gate_passed = bool(
        suite_summary.get("passedPromotionGate")
        or suite_summary.get("winningPassedPromotionGate")
        or not suite_summary.get("sourceRobustnessPromotionBlockers")
        and accepted_retention_ratio > 0.102
    )
    next_family = _next_family(
        dominant_class=dominant_class,
        residual_selected_count=residual_selected_count,
        residual_accepted_count=residual_accepted_count,
        accepted_retention_ratio=accepted_retention_ratio,
        promotion_gate_passed=promotion_gate_passed,
    )
    generated_at = _utc_now_iso()
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": int(attempt_number),
        "attemptBudget": 3,
        "attemptApproachFamily": str(attempt_approach_family),
        "batchStatus": "succeeded" if frame_rows else "needs_next_attempt",
        "goalAchieved": bool(frame_rows),
        "roadmapAdvanceAllowed": True,
        "collapsedNotSelectedFrameIds": [int(row["frameIndex"]) for row in frame_rows],
        "classifiedFrameCount": len(frame_rows),
        "residualSelectedFrameCount": residual_selected_count,
        "residualAcceptedFrameCount": residual_accepted_count,
        "reviewedPositiveAcceptedFrameCount": _safe_int(
            residual_summary.get("reviewedPositiveAcceptedFrameCount"),
            residual_accepted_count,
        ),
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "gapClassCounts": dict(sorted(counts.items())),
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "retentionTruth": {
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
        "proofTruth": {
            "acceptedBallFrames": proof_summary.get("acceptedBallFrames"),
            "bestProposalRawDetectedFrames": proof_summary.get("bestProposalRawDetectedFrames"),
            "bestProposalAfterSeedCollapseFrames": proof_summary.get("bestProposalAfterSeedCollapseFrames"),
            "bestProposalSelectedFrames": proof_summary.get("bestProposalSelectedFrames"),
        },
    }
    trace_artifact = {
        "generatedAt": generated_at,
        "collapsedNotSelectedFrameIds": summary["collapsedNotSelectedFrameIds"],
        "frameGateTrace": frame_rows,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "gapClassCounts": summary["gapClassCounts"],
    }
    decision = {
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "profileCandidate": (
            "source_robustness_shadow_promoted_v6_residual_segment_selection_microfix_v1"
            if next_family == "residual_selected_segment_microprofile"
            else None
        ),
        "runtimeDefaultChanged": False,
        "rationale": (
            "Residual collapsed frames are rejected by the selected-segment minimum length gate."
            if dominant_class == BUCKET_SEGMENT_LENGTH
            else "Residual selected-segment gate no longer points at a segment-length-only microfix."
        ),
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "residual_segment_selection_microfix_summary.json", summary)
    _write_json(output_root / "residual_frame_gate_trace.json", trace_artifact)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "residualFrameGateTrace": trace_artifact,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--residual-root", type=Path, default=DEFAULT_RESIDUAL_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="residual_selection_gate_trace_refresh")
    args = parser.parse_args()
    payload = run_promoted_v6_residual_segment_selection_microfix(
        output_root=args.output_root,
        residual_root=args.residual_root,
        promoted_proof_root=args.promoted_proof_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
