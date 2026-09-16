from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_acceptance_fix_v1"
DEFAULT_SELECTION_FOLLOWTHROUGH_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_selection_followthrough_fix_v1"
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_BATCH_NAME = "reviewed_positive_acceptance_fix_v1"

BUCKET_NOT_IN_TRUTH_LAYER = "reviewed_positive_selected_not_in_truth_layer"
BUCKET_ACCEPTANCE_GATE = "reviewed_positive_selected_rejected_by_acceptance_gate"
BUCKET_CONTINUITY = "reviewed_positive_selected_rejected_by_continuity"
BUCKET_REPEATED_ANCHOR = "reviewed_positive_selected_rejected_by_repeated_anchor"
BUCKET_VIABILITY = "reviewed_positive_selected_rejected_by_viability"
BUCKET_ARTIFACT_GAP = "reviewed_positive_acceptance_artifact_gap"
BUCKET_ALREADY_ACCEPTED = "reviewed_positive_already_accepted"

NEXT_TRACE_REFRESH = "proof_acceptance_gate_trace_refresh"
NEXT_ACCEPTANCE_PROFILE = "reviewed_positive_acceptance_profile"
NEXT_TRUTH_LAYER_INJECTION = "reviewed_positive_truth_layer_injection_probe"
NEXT_PROMOTE_CANDIDATE = "promote_touchline_detector_candidate"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _frame_id_from_row(row: dict[str, Any]) -> int | None:
    for key in ("frameIndex", "Frame_ID", "frameId", "frame"):
        if key in row:
            frame_id = _safe_int(row.get(key), -1)
            if frame_id >= 0:
                return frame_id
    return None


def _frame_set_from_rows(value: object) -> set[int]:
    frames: set[int] = set()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                frame_id = _frame_id_from_row(item)
            else:
                frame_id = _safe_int(item, -1)
            if frame_id is not None and frame_id >= 0:
                frames.add(frame_id)
    elif isinstance(value, dict):
        for key, item in value.items():
            key_frame_id = _safe_int(key, -1)
            if key_frame_id >= 0:
                frames.add(key_frame_id)
            if isinstance(item, dict):
                nested_frame_id = _frame_id_from_row(item)
                if nested_frame_id is not None and nested_frame_id >= 0:
                    frames.add(nested_frame_id)
    return frames


def _accepted_frame_ids(
    *,
    proof_summary: dict[str, Any],
    ball_truth_layers: dict[str, Any],
    recovery_profile_matrix: dict[str, Any],
    selected_cluster_delta: dict[str, Any],
) -> set[int]:
    frames: set[int] = set()
    for key in ("acceptedFrameIds", "acceptedBallFrameIds", "proposalAcceptedFrameIds"):
        frames.update(_frame_set_from_rows(proof_summary.get(key)))
        frames.update(_frame_set_from_rows(recovery_profile_matrix.get(key)))
        frames.update(_frame_set_from_rows(selected_cluster_delta.get(key)))
    accepted_ball = ball_truth_layers.get("acceptedBall")
    if isinstance(accepted_ball, dict):
        frames.update(_frame_set_from_rows(accepted_ball.get("rows")))
        frames.update(_frame_set_from_rows(accepted_ball.get("rawRows")))
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        for key in ("acceptedFrameIds", "acceptedBallFrameIds", "proposalAcceptedFrameIds"):
            frames.update(_frame_set_from_rows(profile.get(key)))
        for diagnostic in _list_dicts(profile.get("proposalFrameDiagnostics")):
            frame_id = _frame_id_from_row(diagnostic)
            if frame_id is not None and bool(diagnostic.get("accepted")):
                frames.add(frame_id)
    return frames


def _diagnostics_by_frame(recovery_profile_matrix: dict[str, Any]) -> dict[int, dict[str, Any]]:
    diagnostics: dict[int, dict[str, Any]] = {}
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        if profile.get("name") != "proposal_windows_075":
            continue
        for diagnostic in _list_dicts(profile.get("proposalFrameDiagnostics")):
            frame_id = _frame_id_from_row(diagnostic)
            if frame_id is not None:
                diagnostics[frame_id] = diagnostic
    return diagnostics


def _selected_reviewed_positive_rows(selection_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in _list_dicts(selection_matrix.get("collapsedReviewedPositiveFrames")):
        frame_id = _safe_int(row.get("frameIndex"), -1)
        if frame_id < 0 or not bool(row.get("selected")):
            continue
        rows.append(row)
    return sorted(rows, key=lambda row: _safe_int(row.get("frameIndex"), -1))


def _acceptance_gate_trace(row: dict[str, Any], diagnostic: dict[str, Any]) -> dict[str, Any]:
    for source in (
        diagnostic,
        dict(row.get("proofEvidence") or {}).get("recoveryProfile"),
        dict(row.get("proofEvidence") or {}).get("coverage"),
        row,
    ):
        if isinstance(source, dict) and isinstance(source.get("acceptanceGateTrace"), dict):
            return dict(source["acceptanceGateTrace"])
    return {}


def _classify_acceptance_trace(
    *,
    frame_id: int,
    row: dict[str, Any],
    diagnostic: dict[str, Any],
    accepted_frames: set[int],
) -> tuple[str, list[str], dict[str, Any]]:
    accepted = bool(row.get("accepted") or diagnostic.get("accepted") or frame_id in accepted_frames)
    trace = _acceptance_gate_trace(row, diagnostic)
    if accepted:
        return BUCKET_ALREADY_ACCEPTED, [], trace
    if not trace:
        return BUCKET_ARTIFACT_GAP, ["reviewed_positive_acceptance_gate_trace_missing"], trace
    if bool(trace.get("continuityRejected")):
        return BUCKET_CONTINUITY, [], trace
    if bool(trace.get("repeatedAnchorRejected")):
        return BUCKET_REPEATED_ANCHOR, [], trace
    if bool(trace.get("viabilityRejected")):
        return BUCKET_VIABILITY, [], trace
    if bool(trace.get("acceptanceGateRejected")):
        return BUCKET_ACCEPTANCE_GATE, [], trace
    if trace.get("acceptedTruthLayerMatch") is False:
        return BUCKET_NOT_IN_TRUTH_LAYER, [], trace
    return BUCKET_ARTIFACT_GAP, ["reviewed_positive_acceptance_gate_trace_inconclusive"], trace


def _dominant(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return BUCKET_ARTIFACT_GAP, 0
    priority = {
        BUCKET_ACCEPTANCE_GATE: 0,
        BUCKET_CONTINUITY: 1,
        BUCKET_REPEATED_ANCHOR: 2,
        BUCKET_VIABILITY: 3,
        BUCKET_NOT_IN_TRUTH_LAYER: 4,
        BUCKET_ARTIFACT_GAP: 5,
        BUCKET_ALREADY_ACCEPTED: 6,
    }
    return sorted(counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[0]


def _next_family(dominant_class: str) -> str:
    if dominant_class == BUCKET_ARTIFACT_GAP:
        return NEXT_TRACE_REFRESH
    if dominant_class in {BUCKET_ACCEPTANCE_GATE, BUCKET_CONTINUITY, BUCKET_REPEATED_ANCHOR, BUCKET_VIABILITY}:
        return NEXT_ACCEPTANCE_PROFILE
    if dominant_class == BUCKET_NOT_IN_TRUTH_LAYER:
        return NEXT_TRUTH_LAYER_INJECTION
    if dominant_class == BUCKET_ALREADY_ACCEPTED:
        return NEXT_PROMOTE_CANDIDATE
    return NEXT_TRACE_REFRESH


def _rationale(dominant_class: str) -> str:
    if dominant_class == BUCKET_ARTIFACT_GAP:
        return (
            "Selected reviewed-positive rows still lack row-level acceptance gate trace; refresh proof "
            "diagnostics before adding an acceptance profile."
        )
    if dominant_class == BUCKET_ALREADY_ACCEPTED:
        return "Reviewed-positive selected rows are already represented in accepted truth; rerun promotion truth."
    if dominant_class == BUCKET_NOT_IN_TRUTH_LAYER:
        return "Reviewed-positive selected rows are absent from accepted truth despite trace coverage."
    return "Reviewed-positive selected rows name a concrete acceptance rejection gate."


def _markdown_summary(summary: dict[str, Any], taxonomy: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed-Positive Acceptance Fix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- reviewedPositiveSelectedFrameCount: {summary.get('reviewedPositiveSelectedFrameCount')}",
            f"- reviewedPositiveAcceptedFrameCount: {summary.get('reviewedPositiveAcceptedFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- gapClassCounts: {json.dumps(taxonomy.get('gapClassCounts') or {}, sort_keys=True)}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_acceptance_fix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    selection_followthrough_root: Path = DEFAULT_SELECTION_FOLLOWTHROUGH_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    attempt_number: int = 1,
    attempt_approach_family: str = "reviewed_positive_acceptance_gate_trace",
) -> dict[str, Any]:
    output_root = Path(output_root)
    selection_followthrough_root = Path(selection_followthrough_root)
    promoted_proof_root = Path(promoted_proof_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)

    selection_matrix = _load_json_dict(
        selection_followthrough_root / "reviewed_positive_selection_followthrough_matrix.json"
    )
    selection_summary = _load_optional_json_dict(
        selection_followthrough_root / "reviewed_positive_selection_followthrough_summary.json"
    )
    recovery_profile_matrix = _load_optional_json_dict(promoted_proof_root / "recovery_profile_matrix.json")
    proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")
    ball_truth_layers = _load_optional_json_dict(promoted_proof_root / "ball_truth_layers.json")
    selected_cluster_delta = _load_optional_json_dict(promoted_proof_root / "selected_cluster_delta.json")
    retention_summary = _load_optional_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(suite_root / "suite_summary.json")

    diagnostics_by_frame = _diagnostics_by_frame(recovery_profile_matrix)
    accepted_frames = _accepted_frame_ids(
        proof_summary=proof_summary,
        ball_truth_layers=ball_truth_layers,
        recovery_profile_matrix=recovery_profile_matrix,
        selected_cluster_delta=selected_cluster_delta,
    )
    rows: list[dict[str, Any]] = []
    weak_reasons: list[str] = []
    for row in _selected_reviewed_positive_rows(selection_matrix):
        frame_id = _safe_int(row.get("frameIndex"), -1)
        diagnostic = diagnostics_by_frame.get(frame_id, {})
        gap_class, row_weak_reasons, trace = _classify_acceptance_trace(
            frame_id=frame_id,
            row=row,
            diagnostic=diagnostic,
            accepted_frames=accepted_frames,
        )
        weak_reasons.extend(row_weak_reasons)
        rows.append(
            {
                "frameIndex": frame_id,
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "windowId": row.get("windowId"),
                "sourceClipId": row.get("sourceClipId"),
                "reviewedBBox": row.get("reviewedBBox"),
                "rawDetected": bool(row.get("rawDetected") or diagnostic.get("rawDetected")),
                "candidateGenerated": bool(
                    row.get("candidateGenerated")
                    or row.get("proposalGenerated")
                    or diagnostic.get("proposalGenerated")
                ),
                "collapsed": bool(row.get("collapsed") or diagnostic.get("collapsed")),
                "selected": True,
                "accepted": bool(row.get("accepted") or diagnostic.get("accepted") or frame_id in accepted_frames),
                "proposalWindowKinds": list(row.get("proposalWindowKinds") or diagnostic.get("proposalWindowKinds") or []),
                "gapClass": gap_class,
                "acceptanceGateTrace": trace,
                "proofEvidence": {
                    "selectionFollowthrough": dict(row.get("proofEvidence") or {}),
                    "recoveryProfile": diagnostic,
                    "acceptedTruthLayerMatch": frame_id in accepted_frames,
                },
            }
        )

    counts = Counter(str(row["gapClass"]) for row in rows)
    dominant_class, dominant_count = _dominant(dict(counts))
    next_family = _next_family(dominant_class)
    generated_at = _utc_now_iso()
    selected_count = len(rows)
    accepted_count = sum(1 for row in rows if bool(row.get("accepted")))
    weak_reasons = sorted(set(weak_reasons))
    rejected_positive_count = _safe_int(
        selection_matrix.get("rejectedBootstrapSeedPositiveEvidenceCount"),
        _safe_int(selection_summary.get("rejectedBootstrapSeedPositiveEvidenceCount"), 0),
    )

    matrix = {
        "generatedAt": generated_at,
        "reviewedPositiveFrameCount": _safe_int(
            selection_matrix.get("reviewedPositiveFrameCount"),
            _safe_int(selection_summary.get("reviewedPositiveFrameCount"), 17),
        ),
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "selectedReviewedPositiveFrames": rows,
        "rejectedBootstrapSeedPositiveEvidenceCount": rejected_positive_count,
    }
    taxonomy = {
        "generatedAt": generated_at,
        "classifiedSelectedFrameCount": selected_count,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "dominantBlockerShare": round(dominant_count / selected_count, 3) if selected_count else 0.0,
        "gapClassCounts": dict(sorted(counts.items())),
        "weakEvidenceReasons": weak_reasons,
    }
    funnel_audit = {
        "generatedAt": generated_at,
        "proofRoot": str(promoted_proof_root),
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "acceptedTruthLayerFrameCount": len(accepted_frames),
        "selectedClusterRemainingTruthGateReasons": list(
            selected_cluster_delta.get("remainingTruthGateReasons") or []
        ),
        "proposalProfileDiagnosticCount": len(diagnostics_by_frame),
        "acceptanceTraceFrameCount": sum(1 for row in rows if bool(row.get("acceptanceGateTrace"))),
    }
    decision = {
        "goalAchieved": selected_count > 0 and dominant_class != "",
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "weakEvidenceReasons": weak_reasons,
        "runtimeDefaultChanged": False,
        "rationale": _rationale(dominant_class),
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": int(attempt_number),
        "attemptBudget": 3,
        "attemptApproachFamily": str(attempt_approach_family),
        "batchStatus": "succeeded" if decision["goalAchieved"] else "needs_next_attempt",
        "goalAchieved": decision["goalAchieved"],
        "roadmapAdvanceAllowed": decision["roadmapAdvanceAllowed"],
        "reviewedPositiveFrameCount": matrix["reviewedPositiveFrameCount"],
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "classifiedSelectedFrameCount": selected_count,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "weakEvidenceReasons": weak_reasons,
        "rejectedBootstrapSeedPositiveEvidenceCount": rejected_positive_count,
        "runtimeDefaultChanged": False,
        "sourceManifestMutationPolicy": "not_mutated",
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
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "reviewed_positive_acceptance_summary.json", summary)
    _write_json(output_root / "reviewed_positive_acceptance_matrix.json", matrix)
    _write_json(output_root / "reviewed_positive_acceptance_gate_taxonomy.json", taxonomy)
    _write_json(output_root / "reviewed_positive_accepted_funnel_audit.json", funnel_audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(
        _markdown_summary(summary, taxonomy),
        encoding="utf-8",
    )
    return {
        "summary": summary,
        "reviewedPositiveAcceptanceMatrix": matrix,
        "reviewedPositiveAcceptanceGateTaxonomy": taxonomy,
        "reviewedPositiveAcceptedFunnelAudit": funnel_audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--selection-followthrough-root", type=Path, default=DEFAULT_SELECTION_FOLLOWTHROUGH_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="reviewed_positive_acceptance_gate_trace")
    args = parser.parse_args()
    payload = run_promoted_v6_reviewed_positive_acceptance_fix(
        output_root=args.output_root,
        selection_followthrough_root=args.selection_followthrough_root,
        promoted_proof_root=args.promoted_proof_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
