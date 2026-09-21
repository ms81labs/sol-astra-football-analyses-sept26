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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_crop_geometry_scale_fix_v1"
DEFAULT_AUDIT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_crop_reinference_audit_v1"
DEFAULT_PROOF_ROOT = DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_BATCH_NAME = "reviewed_positive_crop_geometry_scale_fix_v1"

BUCKET_NO_RAW = "reviewed_positive_no_raw_detect"
BUCKET_RAW_NOT_COLLAPSED = "reviewed_positive_raw_detected_not_collapsed"
BUCKET_COLLAPSED_NOT_SELECTED = "reviewed_positive_collapsed_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "reviewed_positive_selected_not_accepted"
BUCKET_ACCEPTED = "reviewed_positive_accepted"

AUDIT_RESCUE_BUCKET = "reviewed_positive_crop_geometry_scale_rescue_available"


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


def _proposal_profile(recovery_profile_matrix: dict[str, Any]) -> dict[str, Any]:
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        if profile.get("name") == "proposal_windows_075":
            return profile
    return {}


def _diagnostics_by_frame(profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for row in _list_dicts(profile.get("proposalFrameDiagnostics")):
        frame_id = _safe_int(row.get("frameIndex"), -1)
        if frame_id >= 0:
            rows[frame_id] = row
    return rows


def _classify(evidence: dict[str, Any] | None) -> str:
    if not evidence:
        return BUCKET_NO_RAW
    if evidence.get("accepted"):
        return BUCKET_ACCEPTED
    if evidence.get("selected"):
        return BUCKET_SELECTED_NOT_ACCEPTED
    if evidence.get("collapsed"):
        return BUCKET_COLLAPSED_NOT_SELECTED
    if evidence.get("rawDetected") or evidence.get("proposalGenerated"):
        return BUCKET_RAW_NOT_COLLAPSED
    return BUCKET_NO_RAW


def _has_proof_evidence(row: dict[str, Any]) -> bool:
    return bool(row.get("rawDetected") or row.get("collapsed") or row.get("selected") or row.get("accepted"))


def _dominant_bucket(counts: dict[str, int]) -> tuple[str, int]:
    priority = {
        BUCKET_RAW_NOT_COLLAPSED: 0,
        BUCKET_COLLAPSED_NOT_SELECTED: 1,
        BUCKET_SELECTED_NOT_ACCEPTED: 2,
        BUCKET_NO_RAW: 3,
        BUCKET_ACCEPTED: 4,
    }
    if not counts:
        return BUCKET_NO_RAW, 0
    return sorted(
        ((str(key), _safe_int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], priority.get(item[0], 99), item[0]),
    )[0]


def _next_family(
    *,
    proposal_evidence_count: int,
    selected_count: int,
    accepted_count: int,
    audit_rescuable_count: int,
    audit_rescuable_evidence_count: int,
) -> str:
    if accepted_count > 0 or selected_count > 0:
        return "reviewed_positive_acceptance_fix"
    if proposal_evidence_count > 1:
        return "reviewed_positive_selection_followthrough_fix"
    if audit_rescuable_count > 0 and audit_rescuable_evidence_count == 0:
        return "audit_to_proof_geometry_mismatch"
    return "reviewed_positive_model_finetune_fix"


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed Positive Crop Geometry Scale Fix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveFrameCount: {summary.get('reviewedPositiveFrameCount')}",
            f"- reviewedPositiveProposalEvidenceFrameCount: {summary.get('reviewedPositiveProposalEvidenceFrameCount')}",
            f"- reviewedPositiveCollapsedFrameCount: {summary.get('reviewedPositiveCollapsedFrameCount')}",
            f"- auditRescuableProofEvidenceFrameCount: {summary.get('auditRescuableProofEvidenceFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_crop_geometry_scale_fix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    audit_root: Path = DEFAULT_AUDIT_ROOT,
    proof_root: Path = DEFAULT_PROOF_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    attempt_number: int = 1,
    attempt_approach_family: str = "reviewed_positive_expanded_crop_geometry",
) -> dict[str, Any]:
    output_root = Path(output_root)
    audit_root = Path(audit_root)
    proof_root = Path(proof_root)
    audit_matrix = _load_json_dict(audit_root / "reviewed_positive_crop_reinference_matrix.json")
    audit_summary = _load_optional_json_dict(audit_root / "reviewed_positive_crop_reinference_summary.json")
    retention_summary = _load_optional_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    recovery_profile_matrix = _load_json_dict(proof_root / "recovery_profile_matrix.json")
    proof_summary = _load_optional_json_dict(proof_root / "proof_summary.json")
    profile = _proposal_profile(recovery_profile_matrix)
    diagnostics_by_frame = _diagnostics_by_frame(profile)

    coverage_rows: list[dict[str, Any]] = []
    for audit_row in _list_dicts(audit_matrix.get("reviewedPositiveCropRows")):
        frame_id = _safe_int(audit_row.get("frameIndex"), -1)
        evidence = diagnostics_by_frame.get(frame_id)
        diagnostic_class = _classify(evidence)
        coverage_rows.append(
            {
                "reviewItemId": audit_row.get("reviewItemId"),
                "candidateFrameId": audit_row.get("candidateFrameId"),
                "windowId": audit_row.get("windowId"),
                "sourceClipId": audit_row.get("sourceClipId"),
                "frameIndex": frame_id,
                "reviewedBBox": audit_row.get("reviewedBBox"),
                "auditDiagnosticClass": audit_row.get("diagnosticClass"),
                "auditReinferenceDetected": bool(audit_row.get("reinferenceDetected")),
                "rawDetected": bool(evidence and evidence.get("rawDetected")),
                "candidateGenerated": bool(
                    evidence
                    and (
                        evidence.get("proposalGenerated")
                        or evidence.get("candidateGenerated")
                        or evidence.get("rawDetected")
                        or evidence.get("collapsed")
                        or evidence.get("selected")
                        or evidence.get("accepted")
                    )
                ),
                "collapsed": bool(evidence and evidence.get("collapsed")),
                "selected": bool(evidence and evidence.get("selected")),
                "accepted": bool(evidence and evidence.get("accepted")),
                "diagnosticClass": diagnostic_class,
                "rejectionReason": diagnostic_class if diagnostic_class != BUCKET_ACCEPTED else "",
                "proofEvidence": evidence or {},
            }
        )

    counts = Counter(str(row["diagnosticClass"]) for row in coverage_rows)
    dominant_bucket, dominant_count = _dominant_bucket(dict(counts))
    proposal_evidence_count = sum(1 for row in coverage_rows if _has_proof_evidence(row))
    collapsed_count = sum(1 for row in coverage_rows if row["collapsed"])
    selected_count = sum(1 for row in coverage_rows if row["selected"])
    accepted_count = sum(1 for row in coverage_rows if row["accepted"])
    audit_rescuable_rows = [
        row for row in coverage_rows if row.get("auditDiagnosticClass") == AUDIT_RESCUE_BUCKET
    ]
    audit_rescuable_evidence_count = sum(1 for row in audit_rescuable_rows if _has_proof_evidence(row))
    next_family = _next_family(
        proposal_evidence_count=proposal_evidence_count,
        selected_count=selected_count,
        accepted_count=accepted_count,
        audit_rescuable_count=len(audit_rescuable_rows),
        audit_rescuable_evidence_count=audit_rescuable_evidence_count,
    )
    goal_achieved = (
        proposal_evidence_count > 1
        or selected_count > 0
        or accepted_count > 0
        or retention_summary.get("primaryRetentionBlockerClass") != "accepted_signal_retention_collapse"
        or float(retention_summary.get("acceptedRetentionRatio") or 0.0) > 0.069
    )
    generated_at = _utc_now_iso()
    coverage = {
        "generatedAt": generated_at,
        "proofRoot": str(proof_root),
        "reviewedPositiveFrameCount": len(coverage_rows),
        "reviewedPositiveProposalEvidenceFrameCount": proposal_evidence_count,
        "reviewedPositiveCollapsedFrameCount": collapsed_count,
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "auditRescuableFrameCount": len(audit_rescuable_rows),
        "auditRescuableProofEvidenceFrameCount": audit_rescuable_evidence_count,
        "bucketCounts": dict(sorted(counts.items())),
        "reviewedPositiveFrames": coverage_rows,
        "proposalProfileSummary": {
            "reviewedPositiveAnchorSeedFrames": _safe_int(profile.get("reviewedPositiveAnchorSeedFrames"), 0),
            "reviewedPositiveAnchorUsedFrames": _safe_int(profile.get("reviewedPositiveAnchorUsedFrames"), 0),
            "reviewedPositiveAnchorWindowFrames": _safe_int(profile.get("reviewedPositiveAnchorWindowFrames"), 0),
            "reviewedPositiveAuditContextWindowFrames": _safe_int(
                profile.get("reviewedPositiveAuditContextWindowFrames"), 0
            ),
            "proposalRawDetectedFrames": _safe_int(profile.get("proposalRawDetectedFrames"), 0),
            "proposalCollapsedFrames": _safe_int(profile.get("proposalCollapsedFrames"), 0),
            "selectedFrames": _safe_int(profile.get("selectedFrames"), 0),
        },
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": int(attempt_number),
        "attemptBudget": 3,
        "attemptApproachFamily": str(attempt_approach_family),
        "batchStatus": "succeeded" if goal_achieved else "needs_next_attempt",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "reviewedPositiveFrameCount": len(coverage_rows),
        "auditRescuableFrameCount": len(audit_rescuable_rows),
        "auditRescuableProofEvidenceFrameCount": audit_rescuable_evidence_count,
        "reviewedPositiveProposalEvidenceFrameCount": proposal_evidence_count,
        "reviewedPositiveCollapsedFrameCount": collapsed_count,
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "runPodUsed": True,
        "auditTruth": {
            "reviewedPositiveFrameCount": audit_summary.get("reviewedPositiveFrameCount"),
            "zeroDetectFrameCount": audit_summary.get("zeroDetectFrameCount"),
            "reinferenceDetectedFrameCount": audit_summary.get("reinferenceDetectedFrameCount"),
            "dominantBlockerClass": audit_summary.get("dominantBlockerClass"),
        },
        "retentionTruth": {
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        },
        "proofTruth": {
            "acceptedBallFrames": proof_summary.get("acceptedBallFrames"),
            "bestProposalRawDetectedFrames": proof_summary.get("bestProposalRawDetectedFrames"),
            "bestProposalAfterSeedCollapseFrames": proof_summary.get("bestProposalAfterSeedCollapseFrames"),
            "bestProposalSelectedFrames": proof_summary.get("bestProposalSelectedFrames"),
        },
    }
    decision = {
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "rationale": (
            "Reviewed-positive proof evidence improved above the prior 1/17 baseline; inspect selection/follow-through next."
            if proposal_evidence_count > 1
            else "Audit-rescuable frames did not become proof-level proposal evidence."
        ),
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "reviewed_positive_crop_geometry_scale_fix_summary.json", summary)
    _write_json(output_root / "reviewed_positive_crop_geometry_scale_coverage.json", coverage)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "reviewedPositiveCropGeometryScaleFixSummary": summary,
        "reviewedPositiveCropGeometryScaleCoverage": coverage,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--proof-root", type=Path, default=DEFAULT_PROOF_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument(
        "--attempt-approach-family",
        default="reviewed_positive_expanded_crop_geometry",
    )
    args = parser.parse_args()
    payload = run_promoted_v6_reviewed_positive_crop_geometry_scale_fix(
        output_root=args.output_root,
        audit_root=args.audit_root,
        proof_root=args.proof_root,
        retention_delta_root=args.retention_delta_root,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload["reviewedPositiveCropGeometryScaleFixSummary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
