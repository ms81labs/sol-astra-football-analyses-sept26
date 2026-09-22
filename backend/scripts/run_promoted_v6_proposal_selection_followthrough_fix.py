from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_ANALYSIS_ROOT = DEFAULT_SUITE_ROOT / "proposal_selection_followthrough_fix_v1"
DEFAULT_CROP_BLOCKER_ROOT = DEFAULT_SUITE_ROOT / "proposal_crop_geometry_fix"
DEFAULT_GOLD_TRUTH_ROOT = (
    DEFAULT_SUITE_ROOT
    / "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
    / "gold_truth_bootstrap_attempt_v1"
)
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"

BUCKET_PROFILE_NOT_VIABLE = "profile_generated_candidates_but_not_viable"
BUCKET_SEGMENT_SELECTION_ZERO = "candidate_rows_collapsed_but_segment_selection_zero"
BUCKET_SUPPORT_VIABILITY_REJECTED = "support_viability_followthrough_rejected_all"
BUCKET_TRUTH_GATE_SPARSE = "selected_cluster_truth_gate_sparse"
BUCKET_PROFILE_RANKING_DISCARDED = "profile_ranking_discarded_candidate_profile"
BUCKET_MANUAL_REVIEW = "manual_review_required"
BUCKET_UNRESOLVED = "unresolved_followthrough_gap"

NEXT_SEGMENT_VIABILITY = "selection_segment_viability_fix"
NEXT_PROFILE_RANKING = "selected_profile_ranking_fix"
NEXT_SUPPORT_VIABILITY = "support_viability_followthrough_fix"
NEXT_MANUAL_REVIEW = "manual_review_required"

MIN_CLASSIFIED_SEED_FRAMES = 5
PROPOSAL_PROFILE_NAME = "proposal_windows_075"


def _load_json_dict(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return _load_json_dict(path)




def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _list_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _seed_rows(seed_payload: dict[str, object]) -> list[dict[str, object]]:
    return sorted(
        _list_dicts(seed_payload.get("acceptedBallSeedRows")),
        key=lambda row: (_safe_int(row.get("frameId"), -1), str(row.get("candidateFrameId") or "")),
    )


def _profile_rows(recovery_profile_matrix: dict[str, object]) -> list[dict[str, object]]:
    return _list_dicts(recovery_profile_matrix.get("profiles"))


def _profile_by_name(recovery_profile_matrix: dict[str, object], name: str) -> dict[str, object]:
    for profile in _profile_rows(recovery_profile_matrix):
        if str(profile.get("name") or "") == name:
            return profile
    return {}


def _max_profile_int(recovery_profile_matrix: dict[str, object], key: str) -> int:
    return max((_safe_int(profile.get(key), 0) for profile in _profile_rows(recovery_profile_matrix)), default=0)


def _selected_truth_gate_is_sparse(selected_cluster_delta: dict[str, object]) -> bool:
    reasons = selected_cluster_delta.get("remainingTruthGateReasons")
    if not isinstance(reasons, list):
        return False
    joined = " ".join(str(reason).lower() for reason in reasons)
    return "sparse" in joined or "too sparse" in joined or "controlled possession" in joined


def build_profile_selection_funnel_audit(
    *,
    crop_blocker: dict[str, object],
    proof_summary: dict[str, object],
    recovery_profile_matrix: dict[str, object],
    selected_cluster_delta: dict[str, object],
) -> dict[str, object]:
    proposal_profile = _profile_by_name(recovery_profile_matrix, PROPOSAL_PROFILE_NAME)
    selected_profile_name = str(recovery_profile_matrix.get("selectedProfileName") or "")
    crop_diagnostics = crop_blocker.get("proposalDiagnostics")
    if not isinstance(crop_diagnostics, dict):
        crop_diagnostics = {}

    proposal_candidate_frames = max(
        _safe_int(crop_diagnostics.get("proposalCandidateFrames"), 0),
        _safe_int(proof_summary.get("bestProposalCandidateFrames"), 0),
        _safe_int(proposal_profile.get("proposalCandidateFrames"), 0),
    )
    proposal_raw_detected_frames = max(
        _safe_int(crop_diagnostics.get("proposalRawDetectedFrames"), 0),
        _safe_int(proof_summary.get("bestProposalRawDetectedFrames"), 0),
        _safe_int(proposal_profile.get("proposalRawDetectedFrames"), 0),
    )
    proposal_collapsed_frames = max(
        _safe_int(crop_diagnostics.get("proposalCollapsedFrames"), 0),
        _safe_int(proposal_profile.get("proposalCollapsedFrames"), 0),
        _safe_int(proposal_profile.get("candidateFrames"), 0),
    )
    proposal_selected_frames = max(
        _safe_int(crop_diagnostics.get("selectedFrames"), 0),
        _safe_int(proof_summary.get("bestProposalSelectedFrames"), 0),
        _safe_int(proposal_profile.get("selectedFrames"), 0),
    )
    support_truth_frames = max(
        _safe_int(crop_diagnostics.get("proposalSupportViabilityAdmissionFixTruthSeedFrames"), 0),
        _safe_int(proposal_profile.get("proposalSupportViabilityAdmissionFixTruthSeedFrames"), 0),
    )
    support_accepted_frames = max(
        _safe_int(crop_diagnostics.get("proposalSupportViabilityAdmissionFixAcceptedFrames"), 0),
        _safe_int(proposal_profile.get("proposalSupportViabilityAdmissionFixAcceptedFrames"), 0),
    )

    return {
        "generatedAt": _utc_now_iso(),
        "selectedProfileName": selected_profile_name or None,
        "proposalProfileName": str(proposal_profile.get("name") or PROPOSAL_PROFILE_NAME)
        if proposal_profile
        else PROPOSAL_PROFILE_NAME,
        "proposalCandidateFrames": proposal_candidate_frames,
        "proposalRawDetectedFrames": proposal_raw_detected_frames,
        "proposalAfterSeedCollapseFrames": max(
            _safe_int(proof_summary.get("bestProposalAfterSeedCollapseFrames"), 0),
            _safe_int(proposal_profile.get("proposalAfterSeedCollapseFrames"), 0),
        ),
        "proposalAfterFalseBallSuppressionFrames": max(
            _safe_int(proof_summary.get("bestProposalAfterFalseBallSuppressionFrames"), 0),
            _safe_int(proposal_profile.get("proposalAfterFalseBallSuppressionFrames"), 0),
        ),
        "proposalCollapsedFrames": proposal_collapsed_frames,
        "proposalSelectedFrames": proposal_selected_frames,
        "proposalSelectedSegmentCount": _safe_int(proposal_profile.get("selectedSegmentCount"), 0),
        "proposalProfileViable": bool(proposal_profile.get("viable")) if proposal_profile else False,
        "supportViabilityTruthSeedFrames": support_truth_frames,
        "supportViabilityAcceptedFrames": support_accepted_frames,
        "remainingTruthGateReasons": list(selected_cluster_delta.get("remainingTruthGateReasons") or []),
        "selectedClusterTruthGateSparse": _selected_truth_gate_is_sparse(selected_cluster_delta),
        "profileCount": len(_profile_rows(recovery_profile_matrix)),
        "maxSelectedFramesAcrossProfiles": _max_profile_int(recovery_profile_matrix, "selectedFrames"),
        "maxCollapsedFramesAcrossProfiles": max(
            _max_profile_int(recovery_profile_matrix, "proposalCollapsedFrames"),
            _max_profile_int(recovery_profile_matrix, "candidateFrames"),
        ),
    }


def _bucket_from_funnel(funnel: dict[str, object]) -> str:
    candidate_frames = _safe_int(funnel.get("proposalCandidateFrames"), 0)
    raw_frames = _safe_int(funnel.get("proposalRawDetectedFrames"), 0)
    collapsed_frames = _safe_int(funnel.get("proposalCollapsedFrames"), 0)
    selected_frames = _safe_int(funnel.get("proposalSelectedFrames"), 0)
    selected_profile_name = str(funnel.get("selectedProfileName") or "")
    proposal_viable = bool(funnel.get("proposalProfileViable"))
    support_truth_frames = _safe_int(funnel.get("supportViabilityTruthSeedFrames"), 0)
    support_accepted_frames = _safe_int(funnel.get("supportViabilityAcceptedFrames"), 0)

    if selected_frames > 0 and selected_profile_name and selected_profile_name != PROPOSAL_PROFILE_NAME:
        return BUCKET_PROFILE_RANKING_DISCARDED
    if collapsed_frames > 0 and selected_frames == 0:
        return BUCKET_SEGMENT_SELECTION_ZERO
    if candidate_frames > 0 and raw_frames > 0 and collapsed_frames == 0 and not proposal_viable:
        return BUCKET_PROFILE_NOT_VIABLE
    if support_truth_frames > 0 and support_accepted_frames == 0 and selected_frames == 0:
        return BUCKET_SUPPORT_VIABILITY_REJECTED
    if selected_frames > 0 and bool(funnel.get("selectedClusterTruthGateSparse")):
        return BUCKET_TRUTH_GATE_SPARSE
    if candidate_frames > 0:
        return BUCKET_MANUAL_REVIEW
    return BUCKET_UNRESOLVED


def build_proposal_selection_followthrough_matrix(
    *,
    seed_payload: dict[str, object],
    candidate_manifest: dict[str, object],
    funnel_audit: dict[str, object],
) -> dict[str, object]:
    seed_rows = _seed_rows(seed_payload)
    bucket = _bucket_from_funnel(funnel_audit)
    frames = [
        {
            "frameId": _safe_int(seed_row.get("frameId"), -1),
            "candidateFrameId": seed_row.get("candidateFrameId"),
            "windowId": seed_row.get("windowId"),
            "gapClass": bucket,
            "evidenceSource": "profile_selection_funnel_audit",
            "lineageComplete": bool(seed_row.get("lineage")),
        }
        for seed_row in seed_rows
    ]
    counts = Counter(str(frame["gapClass"]) for frame in frames)
    return {
        "generatedAt": _utc_now_iso(),
        "seedFrameCount": len(seed_rows),
        "classifiedSeedFrameCount": len(frames),
        "representedBootstrapWindowCount": _safe_int(candidate_manifest.get("representedBootstrapWindowCount"), 0),
        "representedMissingAcceptedFrameCount": _safe_int(
            candidate_manifest.get("representedMissingAcceptedFrameCount"), len(frames)
        ),
        "gapClassCounts": dict(sorted(counts.items())),
        "frames": frames,
    }


def build_selected_frame_gap_taxonomy(*, matrix: dict[str, object]) -> dict[str, object]:
    counts = {str(key): _safe_int(value) for key, value in dict(matrix.get("gapClassCounts") or {}).items()}
    dominant_class = BUCKET_UNRESOLVED
    dominant_count = 0
    if counts:
        dominant_class, dominant_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    classified = _safe_int(matrix.get("classifiedSeedFrameCount"), 0)
    return {
        "generatedAt": _utc_now_iso(),
        "classifiedSeedFrameCount": classified,
        "dominantGapClass": dominant_class,
        "dominantGapFrameCount": dominant_count,
        "dominantGapShare": round(dominant_count / classified, 3) if classified else 0.0,
        "gapClassCounts": counts,
    }


def _next_corrective_family(dominant_gap_class: str) -> str:
    if dominant_gap_class in {BUCKET_SEGMENT_SELECTION_ZERO, BUCKET_PROFILE_NOT_VIABLE}:
        return NEXT_SEGMENT_VIABILITY
    if dominant_gap_class == BUCKET_PROFILE_RANKING_DISCARDED:
        return NEXT_PROFILE_RANKING
    if dominant_gap_class == BUCKET_SUPPORT_VIABILITY_REJECTED:
        return NEXT_SUPPORT_VIABILITY
    return NEXT_MANUAL_REVIEW


def build_manual_review_followthrough_overlay(matrix: dict[str, object]) -> dict[str, object]:
    review_items = []
    for frame in _list_dicts(matrix.get("frames")):
        review_items.append(
            {
                "reviewStatus": "pending_review",
                "reviewActionOptions": [
                    "confirm_selected_frame_candidate",
                    "adjust_selected_frame_candidate",
                    "reject_candidate_rows",
                    "confirm_hard_negative",
                ],
                "frameId": frame.get("frameId"),
                "candidateFrameId": frame.get("candidateFrameId"),
                "windowId": frame.get("windowId"),
                "gapClass": frame.get("gapClass"),
                "evidenceSource": frame.get("evidenceSource"),
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        "reviewPurpose": "Resolve proposal follow-through frames that generated/collapsed candidates but selected zero frames.",
        "reviewItemCount": len(review_items),
        "reviewItems": review_items,
    }


def _weak_evidence_reasons(matrix: dict[str, object], funnel_audit: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    if _safe_int(matrix.get("classifiedSeedFrameCount"), 0) < MIN_CLASSIFIED_SEED_FRAMES:
        reasons.append("classified_seed_frame_count_below_5")
    if (
        _safe_int(funnel_audit.get("proposalCandidateFrames"), 0) == 0
        and _safe_int(funnel_audit.get("proposalRawDetectedFrames"), 0) == 0
        and _safe_int(funnel_audit.get("proposalCollapsedFrames"), 0) == 0
        and _safe_int(funnel_audit.get("proposalSelectedFrames"), 0) == 0
    ):
        reasons.append("no_proposal_selection_funnel_signal")
    return reasons


def build_decision_matrix(
    *,
    matrix: dict[str, object],
    taxonomy: dict[str, object],
    funnel_audit: dict[str, object],
    attempt_number: int = 1,
    attempt_approach_family: str = "selection_followthrough_diagnosis",
) -> dict[str, object]:
    weak_reasons = _weak_evidence_reasons(matrix, funnel_audit)
    if weak_reasons:
        return {
            "goalAchieved": False,
            "dominantBlockerClass": "weak_or_insufficient_followthrough_evidence",
            "nextCorrectiveFamily": NEXT_MANUAL_REVIEW,
            "successfulApproach": "C_evidence_only_blocker",
            "weakEvidenceReasons": weak_reasons,
            "rationale": "Saved artifacts do not contain enough proposal selection funnel evidence.",
        }
    dominant_gap_class = str(taxonomy.get("dominantGapClass") or BUCKET_UNRESOLVED)
    if attempt_number >= 3 and attempt_approach_family == "profile_ranking_or_manual_review_fallback":
        selected_frames = _safe_int(funnel_audit.get("proposalSelectedFrames"), 0)
        selected_profile_name = str(funnel_audit.get("selectedProfileName") or "")
        if selected_frames <= 0 or not selected_profile_name:
            return {
                "goalAchieved": False,
                "dominantBlockerClass": dominant_gap_class,
                "nextCorrectiveFamily": NEXT_MANUAL_REVIEW,
                "successfulApproach": "C_profile_ranking_or_manual_review_fallback",
                "weakEvidenceReasons": [
                    "no_selected_frames_available_for_profile_ranking_fix",
                ],
                "rationale": (
                    "Attempt 2 left generated/collapsed proposal candidates with zero selected frames; "
                    "saved artifacts do not justify a profile-ranking detector change."
                ),
            }
    return {
        "goalAchieved": dominant_gap_class != BUCKET_UNRESOLVED,
        "dominantBlockerClass": dominant_gap_class,
        "nextCorrectiveFamily": _next_corrective_family(dominant_gap_class),
        "successfulApproach": "A_saved_artifact_selection_followthrough_diagnosis",
        "weakEvidenceReasons": [],
        "rationale": "Generated proposal candidates have enough selection/follow-through evidence to name a dominant next corrective family.",
    }


def _markdown_summary(summary: dict[str, object], taxonomy: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Proposal Selection Follow-Through Fix",
            "",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- classifiedSeedFrameCount: {summary.get('classifiedSeedFrameCount')}",
            f"- gapClassCounts: {json.dumps(taxonomy.get('gapClassCounts') or {}, sort_keys=True)}",
            "",
        ]
    )


def run_promoted_v6_proposal_selection_followthrough_fix(
    *,
    analysis_root: Path = DEFAULT_ANALYSIS_ROOT,
    crop_blocker_root: Path = DEFAULT_CROP_BLOCKER_ROOT,
    gold_truth_root: Path = DEFAULT_GOLD_TRUTH_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
    attempt_number: int = 1,
    attempt_approach_family: str = "selection_followthrough_diagnosis",
) -> dict[str, object]:
    analysis_root = Path(analysis_root)
    crop_blocker_root = Path(crop_blocker_root)
    gold_truth_root = Path(gold_truth_root)
    validation_root = Path(validation_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)
    promoted_proof_root = Path(promoted_proof_root)

    crop_blocker = _load_json_dict(crop_blocker_root / "blocker_summary.json")
    seed_payload = _load_json_dict(gold_truth_root / "accepted_controlled_truth_seed.json")
    candidate_manifest = _load_json_dict(gold_truth_root / "candidate_frame_truth_manifest.json")
    validation_outcome = _load_optional_json_dict(validation_root / "batch_outcome_analysis.json")
    retention_summary = _load_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(suite_root / "suite_summary.json")
    proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")
    selected_cluster_delta = _load_optional_json_dict(promoted_proof_root / "selected_cluster_delta.json")
    recovery_profile_matrix = _load_optional_json_dict(promoted_proof_root / "recovery_profile_matrix.json")

    funnel_audit = build_profile_selection_funnel_audit(
        crop_blocker=crop_blocker,
        proof_summary=proof_summary,
        recovery_profile_matrix=recovery_profile_matrix,
        selected_cluster_delta=selected_cluster_delta,
    )
    matrix = build_proposal_selection_followthrough_matrix(
        seed_payload=seed_payload,
        candidate_manifest=candidate_manifest,
        funnel_audit=funnel_audit,
    )
    taxonomy = build_selected_frame_gap_taxonomy(matrix=matrix)
    decision = build_decision_matrix(
        matrix=matrix,
        taxonomy=taxonomy,
        funnel_audit=funnel_audit,
        attempt_number=attempt_number,
        attempt_approach_family=attempt_approach_family,
    )
    manual_review_overlay = build_manual_review_followthrough_overlay(matrix)
    batch_status = (
        "exhausted"
        if attempt_number >= 3 and decision.get("nextCorrectiveFamily") == NEXT_MANUAL_REVIEW
        else ("succeeded" if decision.get("goalAchieved") else "in_progress")
    )

    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": "proposal_selection_followthrough_fix",
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "batchStatus": batch_status,
        "failingSourceClipId": failing_source_clip_id,
        "cropGeometryBatchStatus": crop_blocker.get("batchStatus"),
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
        "validationTruth": {
            "winningPassedPromotionGate": validation_outcome.get("winningPassedPromotionGate"),
            "winningPromotionBlockers": validation_outcome.get("winningPromotionBlockers"),
            "runtimeDefaultChanged": validation_outcome.get("runtimeDefaultChanged"),
        },
        "classifiedSeedFrameCount": matrix.get("classifiedSeedFrameCount"),
        "representedBootstrapWindowCount": matrix.get("representedBootstrapWindowCount"),
        "dominantGapFrameCount": taxonomy.get("dominantGapFrameCount"),
        "dominantGapShare": taxonomy.get("dominantGapShare"),
        "proposalDiagnostics": {
            "proposalCandidateFrames": funnel_audit.get("proposalCandidateFrames"),
            "proposalRawDetectedFrames": funnel_audit.get("proposalRawDetectedFrames"),
            "proposalCollapsedFrames": funnel_audit.get("proposalCollapsedFrames"),
            "selectedFrames": funnel_audit.get("proposalSelectedFrames"),
            "supportViabilityAcceptedFrames": funnel_audit.get("supportViabilityAcceptedFrames"),
        },
        **decision,
    }
    batch_outcome = {
        "batchName": "proposal_selection_followthrough_fix",
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "approachFamily": attempt_approach_family,
        "batchStatus": batch_status,
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["goalAchieved"] or batch_status == "exhausted",
        "dominantBlockerClass": summary["dominantBlockerClass"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "nextRecommendedBatch": summary["nextCorrectiveFamily"],
        "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
        "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        "runtimeDefaultChanged": False,
        "artifacts": {
            "proposalSelectionFollowthroughSummaryPath": str(
                analysis_root / "proposal_selection_followthrough_summary.json"
            ),
            "proposalSelectionFollowthroughMatrixPath": str(
                analysis_root / "proposal_selection_followthrough_matrix.json"
            ),
            "selectedFrameGapTaxonomyPath": str(analysis_root / "selected_frame_gap_taxonomy.json"),
            "profileSelectionFunnelAuditPath": str(analysis_root / "profile_selection_funnel_audit.json"),
            "manualReviewFollowthroughOverlayPath": str(
                analysis_root / "manual_review_followthrough_overlay.json"
            ),
        },
    }

    _write_json(analysis_root / "proposal_selection_followthrough_summary.json", summary)
    _write_json(analysis_root / "proposal_selection_followthrough_matrix.json", matrix)
    _write_json(analysis_root / "selected_frame_gap_taxonomy.json", taxonomy)
    _write_json(analysis_root / "profile_selection_funnel_audit.json", funnel_audit)
    _write_json(analysis_root / "manual_review_followthrough_overlay.json", manual_review_overlay)
    _write_json(analysis_root / "decision_matrix.json", decision)
    _write_json(analysis_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(analysis_root / "batch_outcome_analysis.md", _markdown_summary(summary, taxonomy))
    if batch_status == "exhausted":
        blocker_summary = {
            **summary,
            "blockerSummaryType": "proposal_selection_followthrough_fix_exhausted",
            "nextRecommendedBatch": summary["nextCorrectiveFamily"],
            "manualReviewFollowthroughOverlayPath": str(
                analysis_root / "manual_review_followthrough_overlay.json"
            ),
        }
        _write_json(analysis_root / "blocker_summary.json", blocker_summary)

    return {
        "summary": summary,
        "proposalSelectionFollowthroughMatrix": matrix,
        "selectedFrameGapTaxonomy": taxonomy,
        "profileSelectionFunnelAudit": funnel_audit,
        "manualReviewFollowthroughOverlay": manual_review_overlay,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--crop-blocker-root", type=Path, default=DEFAULT_CROP_BLOCKER_ROOT)
    parser.add_argument("--gold-truth-root", type=Path, default=DEFAULT_GOLD_TRUTH_ROOT)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="selection_followthrough_diagnosis")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_proposal_selection_followthrough_fix(
        analysis_root=args.analysis_root,
        crop_blocker_root=args.crop_blocker_root,
        gold_truth_root=args.gold_truth_root,
        validation_root=args.validation_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        promoted_proof_root=args.promoted_proof_root,
        failing_source_clip_id=args.failing_source_clip_id,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
