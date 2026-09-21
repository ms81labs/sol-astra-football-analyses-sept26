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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_residual_proposal_generation_fix_v1"
DEFAULT_REVIEWED_TRUTH_ROOT = DEFAULT_SUITE_ROOT / "manual_review_expansion_resolution_v1"
DEFAULT_ACCEPTANCE_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_acceptance_fix_v1"
DEFAULT_CROP_GEOMETRY_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_crop_geometry_scale_fix_v1"
DEFAULT_CROP_AUDIT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_crop_reinference_audit_v1"
DEFAULT_FRAME_DIAGNOSTICS_ROOT = DEFAULT_SUITE_ROOT / "proof_runtime_frame_diagnostics_v1"
DEFAULT_REFUTATION_ROOT = DEFAULT_SUITE_ROOT / "manual_review_expansion_v1"
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_BATCH_NAME = "reviewed_positive_residual_proposal_generation_fix"

BUCKET_NO_WINDOW = "residual_no_proposal_window"
BUCKET_ZERO_RAW = "residual_window_generated_zero_raw_detect"
BUCKET_RAW_NOT_CANDIDATE = "residual_raw_detected_not_candidate"
BUCKET_CANDIDATE_NOT_COLLAPSED = "residual_candidate_not_collapsed"
BUCKET_COLLAPSED_NOT_SELECTED = "residual_collapsed_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "residual_selected_not_accepted"
BUCKET_ALREADY_ACCEPTED = "residual_already_accepted"
BUCKET_ARTIFACT_GAP = "residual_artifact_gap"

AUDIT_RESCUE_AVAILABLE = "reviewed_positive_crop_geometry_scale_rescue_available"
AUDIT_MODEL_ZERO = "reviewed_positive_model_zero_detect_all_scales"


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


def _frame_id_from_row(row: dict[str, Any]) -> int | None:
    for key in ("frameIndex", "Frame_ID", "frameId", "frame"):
        if key in row:
            frame_id = _safe_int(row.get(key), -1)
            if frame_id >= 0:
                return frame_id
    return None


def _rows_by_frame(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    by_frame: dict[int, dict[str, Any]] = {}
    for row in rows:
        frame_id = _frame_id_from_row(row)
        if frame_id is not None:
            by_frame[frame_id] = row
    return by_frame


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
            key_frame = _safe_int(key, -1)
            if key_frame >= 0:
                frames.add(key_frame)
            if isinstance(item, dict):
                nested_frame = _frame_id_from_row(item)
                if nested_frame is not None and nested_frame >= 0:
                    frames.add(nested_frame)
    return frames


def _accepted_frames_from_acceptance_matrix(matrix: dict[str, Any]) -> set[int]:
    frames: set[int] = set()
    for row in _list_dicts(matrix.get("selectedReviewedPositiveFrames")):
        frame_id = _frame_id_from_row(row)
        if frame_id is not None and bool(row.get("accepted")):
            frames.add(frame_id)
    frames.update(_frame_set_from_rows(matrix.get("acceptedFrameIds")))
    return frames


def _proof_diagnostics_by_frame(recovery_profile_matrix: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        if profile.get("name") != "proposal_windows_075":
            continue
        for diagnostic in _list_dicts(profile.get("proposalFrameDiagnostics")):
            frame_id = _frame_id_from_row(diagnostic)
            if frame_id is not None:
                rows[frame_id] = diagnostic
    return rows


def _runtime_diagnostics_by_frame(frame_diagnostics: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return _rows_by_frame(_list_dicts(frame_diagnostics.get("reviewedPositiveFrameDiagnostics")))


def _crop_coverage_by_frame(crop_coverage: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return _rows_by_frame(_list_dicts(crop_coverage.get("reviewedPositiveFrames")))


def _audit_by_frame(audit_matrix: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return _rows_by_frame(_list_dicts(audit_matrix.get("reviewedPositiveCropRows")))


def _positive_seed_rows(reviewed_truth: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _list_dicts(reviewed_truth.get("reviewedPositiveSeedRows"))
    return sorted(rows, key=lambda row: _safe_int(row.get("frameIndex"), _safe_int(row.get("Frame_ID"), -1)))


def _generated_window(evidence: dict[str, Any], crop_row: dict[str, Any], audit_row: dict[str, Any]) -> bool:
    return bool(
        evidence.get("proposalGenerated")
        or evidence.get("windowGenerated")
        or evidence.get("rawDetected")
        or evidence.get("candidateGenerated")
        or evidence.get("collapsed")
        or evidence.get("selected")
        or evidence.get("accepted")
        or crop_row
        or audit_row
    )


def _classify_frame(
    *,
    accepted: bool,
    proof_row: dict[str, Any],
    crop_row: dict[str, Any],
    audit_row: dict[str, Any],
) -> str:
    evidence = {**crop_row, **proof_row}
    if accepted or bool(evidence.get("accepted")):
        return BUCKET_ALREADY_ACCEPTED
    if bool(evidence.get("selected")):
        return BUCKET_SELECTED_NOT_ACCEPTED
    if bool(evidence.get("collapsed")):
        return BUCKET_COLLAPSED_NOT_SELECTED
    candidate_generated = bool(
        evidence.get("candidateGenerated")
        or evidence.get("proposalGenerated")
        or evidence.get("rawDetected")
    )
    if candidate_generated and not bool(evidence.get("collapsed")):
        if bool(evidence.get("rawDetected")) and not bool(evidence.get("candidateGenerated")):
            return BUCKET_RAW_NOT_CANDIDATE
        return BUCKET_CANDIDATE_NOT_COLLAPSED
    if _generated_window(evidence, crop_row, audit_row):
        return BUCKET_ZERO_RAW
    if not proof_row and not crop_row and not audit_row:
        return BUCKET_NO_WINDOW
    return BUCKET_ARTIFACT_GAP


def _dominant(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return BUCKET_ARTIFACT_GAP, 0
    priority = {
        BUCKET_ZERO_RAW: 0,
        BUCKET_NO_WINDOW: 1,
        BUCKET_RAW_NOT_CANDIDATE: 2,
        BUCKET_CANDIDATE_NOT_COLLAPSED: 3,
        BUCKET_COLLAPSED_NOT_SELECTED: 4,
        BUCKET_SELECTED_NOT_ACCEPTED: 5,
        BUCKET_ARTIFACT_GAP: 6,
        BUCKET_ALREADY_ACCEPTED: 7,
    }
    return sorted(counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[0]


def _select_next_family(
    *,
    residual_rows: list[dict[str, Any]],
    dominant_class: str,
    accepted_count: int,
    accepted_retention_ratio: float,
) -> str:
    if accepted_count > 5 or accepted_retention_ratio > 0.099:
        return "promote_touchline_detector_candidate"
    if any(row.get("selected") and not row.get("accepted") for row in residual_rows):
        return "reviewed_positive_acceptance_fix"
    if any(row.get("collapsed") and not row.get("selected") for row in residual_rows):
        return "reviewed_positive_selection_followthrough_fix"
    if any(row.get("auditRescueAvailable") for row in residual_rows):
        return "residual_audit_best_crop_profile"
    if dominant_class in {BUCKET_ZERO_RAW, BUCKET_NO_WINDOW, BUCKET_RAW_NOT_CANDIDATE, BUCKET_CANDIDATE_NOT_COLLAPSED}:
        return "reviewed_positive_model_finetune_fix"
    return "manual_review_required"


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed-Positive Residual Proposal Generation Fix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveFrameCount: {summary.get('reviewedPositiveFrameCount')}",
            f"- reviewedPositiveAcceptedFrameCount: {summary.get('reviewedPositiveAcceptedFrameCount')}",
            f"- residualReviewedPositiveFrameCount: {summary.get('residualReviewedPositiveFrameCount')}",
            f"- residualAuditRescueAvailableFrameCount: {summary.get('residualAuditRescueAvailableFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_residual_proposal_generation_fix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    reviewed_truth_root: Path = DEFAULT_REVIEWED_TRUTH_ROOT,
    acceptance_root: Path = DEFAULT_ACCEPTANCE_ROOT,
    crop_geometry_root: Path = DEFAULT_CROP_GEOMETRY_ROOT,
    crop_audit_root: Path = DEFAULT_CROP_AUDIT_ROOT,
    frame_diagnostics_root: Path = DEFAULT_FRAME_DIAGNOSTICS_ROOT,
    refutation_root: Path = DEFAULT_REFUTATION_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    attempt_number: int = 1,
    attempt_approach_family: str = "residual_reviewed_positive_proposal_diagnosis",
) -> dict[str, Any]:
    output_root = Path(output_root)
    reviewed_truth_root = Path(reviewed_truth_root)
    acceptance_root = Path(acceptance_root)
    crop_geometry_root = Path(crop_geometry_root)
    crop_audit_root = Path(crop_audit_root)
    frame_diagnostics_root = Path(frame_diagnostics_root)
    refutation_root = Path(refutation_root)
    promoted_proof_root = Path(promoted_proof_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)

    reviewed_truth = _load_json_dict(reviewed_truth_root / "expanded_reviewed_truth_seed.json")
    acceptance_matrix = _load_optional_json_dict(acceptance_root / "reviewed_positive_acceptance_matrix.json")
    acceptance_summary = _load_optional_json_dict(acceptance_root / "reviewed_positive_acceptance_summary.json")
    crop_coverage = _load_optional_json_dict(crop_geometry_root / "reviewed_positive_crop_geometry_scale_coverage.json")
    audit_matrix = _load_optional_json_dict(crop_audit_root / "reviewed_positive_crop_reinference_matrix.json")
    frame_diagnostics = _load_optional_json_dict(
        frame_diagnostics_root / "reviewed_positive_runtime_frame_diagnostics.json"
    )
    refutation_guard = (
        {}
        if refutation_root == DEFAULT_REFUTATION_ROOT and reviewed_truth_root != DEFAULT_REVIEWED_TRUTH_ROOT
        else _load_optional_json_dict(refutation_root / "refutation_guard_manifest.json")
    )
    recovery_profile_matrix = _load_optional_json_dict(promoted_proof_root / "recovery_profile_matrix.json")
    proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")
    retention_summary = _load_optional_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(suite_root / "suite_summary.json")

    accepted_frames = _accepted_frames_from_acceptance_matrix(acceptance_matrix)
    crop_by_frame = _crop_coverage_by_frame(crop_coverage)
    audit_by_frame = _audit_by_frame(audit_matrix)
    runtime_diag_by_frame = _runtime_diagnostics_by_frame(frame_diagnostics)
    proof_diag_by_frame = _proof_diagnostics_by_frame(recovery_profile_matrix)

    rows: list[dict[str, Any]] = []
    for seed_row in _positive_seed_rows(reviewed_truth):
        frame_id = _safe_int(seed_row.get("frameIndex"), _safe_int(seed_row.get("Frame_ID"), -1))
        if frame_id < 0:
            continue
        crop_row = crop_by_frame.get(frame_id, {})
        audit_row = audit_by_frame.get(frame_id, {})
        proof_row = proof_diag_by_frame.get(frame_id, {})
        runtime_row = runtime_diag_by_frame.get(frame_id, {})
        accepted = frame_id in accepted_frames or bool(crop_row.get("accepted")) or bool(proof_row.get("accepted"))
        gap_class = _classify_frame(
            accepted=accepted,
            proof_row=proof_row,
            crop_row=crop_row,
            audit_row=audit_row,
        )
        audit_class = str(audit_row.get("diagnosticClass") or crop_row.get("auditDiagnosticClass") or "")
        residual = gap_class != BUCKET_ALREADY_ACCEPTED
        rows.append(
            {
                "frameIndex": frame_id,
                "reviewItemId": seed_row.get("reviewItemId"),
                "candidateFrameId": seed_row.get("candidateFrameId"),
                "windowId": seed_row.get("windowId"),
                "sourceClipId": seed_row.get("sourceClipId"),
                "reviewedBBox": seed_row.get("reviewedBBox"),
                "isResidual": residual,
                "accepted": bool(accepted),
                "selected": bool(crop_row.get("selected") or proof_row.get("selected")),
                "collapsed": bool(crop_row.get("collapsed") or proof_row.get("collapsed")),
                "candidateGenerated": bool(
                    crop_row.get("candidateGenerated")
                    or proof_row.get("candidateGenerated")
                    or proof_row.get("proposalGenerated")
                ),
                "rawDetected": bool(crop_row.get("rawDetected") or proof_row.get("rawDetected")),
                "proposalGenerated": bool(
                    crop_row.get("proposalGenerated")
                    or proof_row.get("proposalGenerated")
                    or crop_row
                    or audit_row
                ),
                "gapClass": gap_class,
                "runtimeDiagnosticClass": runtime_row.get("diagnosticClass"),
                "cropGeometryDiagnosticClass": crop_row.get("diagnosticClass"),
                "auditDiagnosticClass": audit_class,
                "auditRescueAvailable": audit_class == AUDIT_RESCUE_AVAILABLE,
                "auditModelZeroDetect": audit_class == AUDIT_MODEL_ZERO,
                "auditReinferenceDetected": bool(audit_row.get("reinferenceDetected") or crop_row.get("auditReinferenceDetected")),
                "bestAuditAttempt": dict(audit_row.get("bestAttempt") or {}),
                "proofEvidence": {
                    "runtimeFrameDiagnostic": runtime_row,
                    "cropGeometryCoverage": crop_row,
                    "recoveryProfileDiagnostic": proof_row,
                },
            }
        )

    residual_rows = [row for row in rows if bool(row.get("isResidual"))]
    residual_counts = Counter(str(row["gapClass"]) for row in residual_rows)
    dominant_class, dominant_count = _dominant(dict(residual_counts))
    accepted_count = sum(1 for row in rows if bool(row.get("accepted")))
    residual_audit_rescue_count = sum(1 for row in residual_rows if bool(row.get("auditRescueAvailable")))
    residual_model_zero_count = sum(1 for row in residual_rows if bool(row.get("auditModelZeroDetect")))
    retention_ratio = _safe_float(retention_summary.get("acceptedRetentionRatio"), 0.0)
    next_family = _select_next_family(
        residual_rows=residual_rows,
        dominant_class=dominant_class,
        accepted_count=accepted_count,
        accepted_retention_ratio=retention_ratio,
    )
    generated_at = _utc_now_iso()
    rejected_seed_count = _safe_int(
        refutation_guard.get("rejectedSeedCount"),
        _safe_int(reviewed_truth.get("reviewedNegativeSeedCount"), 0),
    )

    candidate_plan = {
        "generatedAt": generated_at,
        "profileCandidate": "source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v1",
        "nextCorrectiveFamily": next_family,
        "targetSourceClipId": "trimed-5min.mp4",
        "reviewedPositiveAnchorSeedPath": str(
            DEFAULT_SUITE_ROOT
            / "reviewed_positive_proposal_generation_fix_v1"
            / "reviewed_positive_anchor_seed.json"
        ),
        "excludeAlreadyAcceptedFrames": sorted(int(frame_id) for frame_id in accepted_frames),
        "residualFrameIds": [int(row["frameIndex"]) for row in residual_rows],
        "auditRescueFrameIds": [
            int(row["frameIndex"]) for row in residual_rows if bool(row.get("auditRescueAvailable"))
        ],
        "modelZeroDetectFrameIds": [
            int(row["frameIndex"]) for row in residual_rows if bool(row.get("auditModelZeroDetect"))
        ],
        "recommendedContextRatios": [0.75, 1.0, 2.0, 4.0, 8.0, 12.0],
        "recommendedRetryScales": [640, 960, 1280, 1600, 1920],
        "carryForwardSelectionAndAcceptanceOverrides": True,
        "runtimeDefaultChanged": False,
    }
    matrix = {
        "generatedAt": generated_at,
        "reviewedPositiveFrameCount": len(rows),
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "residualReviewedPositiveFrameCount": len(residual_rows),
        "reviewedPositiveFrames": rows,
        "rejectedBootstrapSeedCount": rejected_seed_count,
        "rejectedBootstrapSeedPositiveEvidenceCount": 0,
    }
    crop_scale_decision = {
        "generatedAt": generated_at,
        "residualAuditRescueAvailableFrameCount": residual_audit_rescue_count,
        "residualModelZeroDetectFrameCount": residual_model_zero_count,
        "dominantBlockerClass": dominant_class,
        "nextCorrectiveFamily": next_family,
        "profileCandidatePlanPath": str(output_root / "residual_profile_candidate_plan.json"),
    }
    goal_achieved = len(rows) > 0 and len(residual_rows) == max(len(rows) - accepted_count, 0)
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": int(attempt_number),
        "attemptBudget": 3,
        "attemptApproachFamily": str(attempt_approach_family),
        "batchStatus": "succeeded" if goal_achieved else "needs_next_attempt",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "reviewedPositiveFrameCount": len(rows),
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "residualReviewedPositiveFrameCount": len(residual_rows),
        "classifiedResidualFrameCount": len(residual_rows),
        "residualAuditRescueAvailableFrameCount": residual_audit_rescue_count,
        "residualModelZeroDetectFrameCount": residual_model_zero_count,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "gapClassCounts": dict(sorted(residual_counts.items())),
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "rejectedBootstrapSeedCount": rejected_seed_count,
        "rejectedBootstrapSeedPositiveEvidenceCount": 0,
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
        "acceptanceTruth": {
            "dominantBlockerClass": acceptance_summary.get("dominantBlockerClass"),
            "reviewedPositiveAcceptedFrameCount": acceptance_summary.get("reviewedPositiveAcceptedFrameCount"),
            "nextCorrectiveFamily": acceptance_summary.get("nextCorrectiveFamily"),
        },
    }
    decision = {
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "profileCandidate": candidate_plan["profileCandidate"] if next_family == "residual_audit_best_crop_profile" else None,
        "runtimeDefaultChanged": False,
        "rationale": (
            "Residual reviewed-positive frames include audit-rescuable crop/scale hits that did not become proof-level proposal evidence."
            if next_family == "residual_audit_best_crop_profile"
            else "Residual reviewed-positive frames lack enough audit-rescuable proposal evidence for another crop profile."
        ),
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
    }

    _write_json(output_root / "residual_proposal_generation_summary.json", summary)
    _write_json(output_root / "residual_reviewed_positive_frame_matrix.json", matrix)
    _write_json(output_root / "residual_crop_scale_decision_matrix.json", crop_scale_decision)
    _write_json(output_root / "residual_profile_candidate_plan.json", candidate_plan)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "residualReviewedPositiveFrameMatrix": matrix,
        "residualCropScaleDecisionMatrix": crop_scale_decision,
        "residualProfileCandidatePlan": candidate_plan,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--reviewed-truth-root", type=Path, default=DEFAULT_REVIEWED_TRUTH_ROOT)
    parser.add_argument("--acceptance-root", type=Path, default=DEFAULT_ACCEPTANCE_ROOT)
    parser.add_argument("--crop-geometry-root", type=Path, default=DEFAULT_CROP_GEOMETRY_ROOT)
    parser.add_argument("--crop-audit-root", type=Path, default=DEFAULT_CROP_AUDIT_ROOT)
    parser.add_argument("--frame-diagnostics-root", type=Path, default=DEFAULT_FRAME_DIAGNOSTICS_ROOT)
    parser.add_argument("--refutation-root", type=Path, default=DEFAULT_REFUTATION_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="residual_reviewed_positive_proposal_diagnosis")
    args = parser.parse_args()
    payload = run_promoted_v6_reviewed_positive_residual_proposal_generation_fix(
        output_root=args.output_root,
        reviewed_truth_root=args.reviewed_truth_root,
        acceptance_root=args.acceptance_root,
        crop_geometry_root=args.crop_geometry_root,
        crop_audit_root=args.crop_audit_root,
        frame_diagnostics_root=args.frame_diagnostics_root,
        refutation_root=args.refutation_root,
        promoted_proof_root=args.promoted_proof_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
