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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_selection_followthrough_fix_v1"
DEFAULT_CROP_GEOMETRY_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_crop_geometry_scale_fix_v1"
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_BATCH_NAME = "reviewed_positive_selection_followthrough_fix_v1"

BUCKET_SEGMENT_SELECTION_ZERO = "reviewed_positive_segment_selection_zero"
BUCKET_EDGE_SHARE_GUARD = "reviewed_positive_edge_share_guard_rejected"
BUCKET_REPEATED_ANCHOR_GUARD = "reviewed_positive_repeated_anchor_guard_rejected"
BUCKET_CONTINUITY_GUARD = "reviewed_positive_continuity_guard_rejected"
BUCKET_SUPPORT_VIABILITY = "reviewed_positive_support_viability_rejected"
BUCKET_PROFILE_RANKING = "reviewed_positive_profile_ranking_discarded"
BUCKET_EVIDENCE_GAP = "reviewed_positive_selection_evidence_gap"
BUCKET_EDGE_GATE_REJECTION = "reviewed_positive_edge_share_gate_rejection"
BUCKET_CONTINUITY_GATE_REJECTION = "reviewed_positive_continuity_gate_rejection"
BUCKET_REPEATED_ANCHOR_GATE_REJECTION = "reviewed_positive_repeated_anchor_gate_rejection"
BUCKET_SEGMENT_LENGTH_GATE_REJECTION = "reviewed_positive_segment_length_gate_rejection"
BUCKET_SYNTHETIC_ROW_REJECTION = "reviewed_positive_synthetic_row_rejection"
BUCKET_LINEAGE_MISMATCH = "reviewed_positive_lineage_mismatch"
BUCKET_SELECTION_ARTIFACT_GAP = "reviewed_positive_selection_artifact_coverage_gap"
BUCKET_STRUCTURAL_SELECTION_GAP = "reviewed_positive_selection_funnel_structural_gap"

NEXT_SEGMENT_PROFILE = "reviewed_positive_selected_segment_profile"
NEXT_SUPPORT_VIABILITY = "reviewed_positive_support_viability_followthrough_fix"
NEXT_PROFILE_RANKING = "reviewed_positive_profile_ranking_fix"
NEXT_DIAGNOSTIC_REFRESH = "proof_diagnostic_instrumentation_refresh"
NEXT_MANUAL_REVIEW = "manual_review_required"
NEXT_ACCEPTANCE_FIX = "reviewed_positive_acceptance_fix"
NEXT_SELECTION_BLOCKER_SUMMARY = "reviewed_positive_selection_blocker_summary"
NEXT_PROOF_SELECTION_TRACE_REFRESH = "proof_selection_gate_trace_refresh"
NEXT_EDGE_SHARE_OVERRIDE = "reviewed_positive_edge_share_gate_override"
NEXT_CONTINUITY_FIX = "reviewed_positive_continuity_followthrough_fix"
NEXT_REPEATED_ANCHOR_FIX = "reviewed_positive_repeated_anchor_followthrough_fix"
NEXT_TRUTH_LAYER_INJECTION_PROBE = "reviewed_positive_truth_layer_injection_probe"
NEXT_EDGE_SHARE_PLUS_ACCEPTANCE_TRACE = "reviewed_positive_edge_share_plus_acceptance_trace"


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


def _proposal_profile(recovery_profile_matrix: dict[str, Any]) -> dict[str, Any]:
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        if profile.get("name") == "proposal_windows_075":
            return profile
    return {}


def _profile_diagnostics_by_frame(recovery_profile_matrix: dict[str, Any]) -> dict[int, dict[str, Any]]:
    profile = _proposal_profile(recovery_profile_matrix)
    diagnostics = {}
    for row in _list_dicts(profile.get("proposalFrameDiagnostics")):
        frame_id = _safe_int(row.get("frameIndex"), -1)
        if frame_id >= 0:
            diagnostics[frame_id] = row
    return diagnostics


def _selected_frame_ids(recovery_profile_matrix: dict[str, Any]) -> set[int]:
    profile = _proposal_profile(recovery_profile_matrix)
    frame_ids = set()
    for key in ("selectedRows", "rows"):
        for row in _list_dicts(profile.get(key)):
            frame_id = _safe_int(row.get("Frame_ID", row.get("frameIndex")), -1)
            if frame_id >= 0:
                frame_ids.add(frame_id)
    return frame_ids


def _accepted_frame_ids(proof_summary: dict[str, Any]) -> set[int]:
    frame_ids = set()
    for key in ("acceptedFrameIds", "acceptedBallFrameIds"):
        value = proof_summary.get(key)
        if isinstance(value, list):
            for frame_id in value:
                parsed = _safe_int(frame_id, -1)
                if parsed >= 0:
                    frame_ids.add(parsed)
    return frame_ids


def _collapsed_reviewed_positive_rows(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in _list_dicts(coverage.get("reviewedPositiveFrames")):
        if not bool(row.get("collapsed")):
            continue
        frame_id = _safe_int(row.get("frameIndex"), -1)
        if frame_id < 0:
            continue
        rows.append(row)
    return sorted(rows, key=lambda row: _safe_int(row.get("frameIndex"), -1))


def _row_rejection_text(row: dict[str, Any], profile_row: dict[str, Any]) -> str:
    text_parts = []
    for source in (row, profile_row, dict(row.get("proofEvidence") or {})):
        if not isinstance(source, dict):
            continue
        for key in ("rejectionReason", "rejectionClass", "gapClass", "diagnosticClass"):
            value = source.get(key)
            if value:
                text_parts.append(str(value))
        reasons = source.get("rejectionReasons")
        if isinstance(reasons, list):
            text_parts.extend(str(reason) for reason in reasons)
    return " ".join(text_parts).lower()


def _has_required_selection_fields(row: dict[str, Any], profile_row: dict[str, Any]) -> bool:
    evidence = row.get("proofEvidence")
    if not isinstance(evidence, dict):
        evidence = {}
    return (
        "selected" in row
        and "accepted" in row
        and ("selected" in profile_row or "selected" in evidence)
        and ("accepted" in profile_row or "accepted" in evidence)
    )


def _classify_collapsed_row(
    row: dict[str, Any],
    *,
    profile_row: dict[str, Any],
    selected_frame_ids: set[int],
    accepted_frame_ids: set[int],
    selected_profile_name: str,
) -> str:
    frame_id = _safe_int(row.get("frameIndex"), -1)
    if not _has_required_selection_fields(row, profile_row):
        return BUCKET_EVIDENCE_GAP
    if frame_id in selected_frame_ids and selected_profile_name and selected_profile_name != "proposal_windows_075":
        return BUCKET_PROFILE_RANKING
    text = _row_rejection_text(row, profile_row)
    if "edge" in text:
        return BUCKET_EDGE_SHARE_GUARD
    if "repeated" in text or "anchor" in text:
        return BUCKET_REPEATED_ANCHOR_GUARD
    if "continuity" in text:
        return BUCKET_CONTINUITY_GUARD
    if "support" in text or "viability" in text:
        return BUCKET_SUPPORT_VIABILITY
    selected = bool(row.get("selected") or profile_row.get("selected") or frame_id in selected_frame_ids)
    accepted = bool(row.get("accepted") or profile_row.get("accepted") or frame_id in accepted_frame_ids)
    if not selected and not accepted:
        return BUCKET_SEGMENT_SELECTION_ZERO
    if selected and selected_profile_name and selected_profile_name != "proposal_windows_075":
        return BUCKET_PROFILE_RANKING
    return BUCKET_EVIDENCE_GAP


def _next_family(dominant_class: str) -> str:
    if dominant_class == BUCKET_SEGMENT_SELECTION_ZERO:
        return NEXT_SEGMENT_PROFILE
    if dominant_class == BUCKET_SUPPORT_VIABILITY:
        return NEXT_SUPPORT_VIABILITY
    if dominant_class == BUCKET_PROFILE_RANKING:
        return NEXT_PROFILE_RANKING
    if dominant_class == BUCKET_EVIDENCE_GAP:
        return NEXT_DIAGNOSTIC_REFRESH
    if dominant_class in {
        BUCKET_EDGE_SHARE_GUARD,
        BUCKET_REPEATED_ANCHOR_GUARD,
        BUCKET_CONTINUITY_GUARD,
    }:
        return NEXT_SEGMENT_PROFILE
    return NEXT_MANUAL_REVIEW


def _dominant(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return BUCKET_EVIDENCE_GAP, 0
    priority = {
        BUCKET_SEGMENT_SELECTION_ZERO: 0,
        BUCKET_SUPPORT_VIABILITY: 1,
        BUCKET_EDGE_SHARE_GUARD: 2,
        BUCKET_REPEATED_ANCHOR_GUARD: 3,
        BUCKET_CONTINUITY_GUARD: 4,
        BUCKET_PROFILE_RANKING: 5,
        BUCKET_EVIDENCE_GAP: 6,
    }
    return sorted(counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[0]


def _dominant_blocker_summary(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return BUCKET_SELECTION_ARTIFACT_GAP, 0
    priority = {
        BUCKET_EDGE_GATE_REJECTION: 0,
        BUCKET_CONTINUITY_GATE_REJECTION: 1,
        BUCKET_REPEATED_ANCHOR_GATE_REJECTION: 2,
        BUCKET_SEGMENT_LENGTH_GATE_REJECTION: 3,
        BUCKET_SYNTHETIC_ROW_REJECTION: 4,
        BUCKET_LINEAGE_MISMATCH: 5,
        BUCKET_PROFILE_RANKING: 6,
        BUCKET_STRUCTURAL_SELECTION_GAP: 7,
        BUCKET_SELECTION_ARTIFACT_GAP: 8,
    }
    return sorted(counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[0]


def _selection_gate_trace(profile_row: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    trace = profile_row.get("selectionGateTrace")
    if not isinstance(trace, dict):
        trace = dict(row.get("selectionGateTrace") or {})
    return trace if isinstance(trace, dict) else {}


def _classify_selection_gate_trace(trace: dict[str, Any]) -> tuple[str, list[str]]:
    if not trace:
        return BUCKET_SELECTION_ARTIFACT_GAP, ["reviewed_positive_selection_gate_trace_missing"]
    if "reviewedPositiveLineageMatch" not in trace:
        return BUCKET_SELECTION_ARTIFACT_GAP, ["reviewed_positive_lineage_trace_missing"]
    if not bool(trace.get("reviewedPositiveLineageMatch")):
        return BUCKET_LINEAGE_MISMATCH, []
    if bool(trace.get("syntheticRowRejected")):
        return BUCKET_SYNTHETIC_ROW_REJECTION, []
    if bool(trace.get("repeatedAnchorRejected")):
        return BUCKET_REPEATED_ANCHOR_GATE_REJECTION, []
    if bool(trace.get("continuityRejected")):
        return BUCKET_CONTINUITY_GATE_REJECTION, []
    if bool(trace.get("segmentLengthRejected")):
        return BUCKET_SEGMENT_LENGTH_GATE_REJECTION, []
    if bool(trace.get("edgeShareRejected")):
        return BUCKET_EDGE_GATE_REJECTION, []
    if bool(trace.get("selectedProfileRankingRejected")):
        return BUCKET_PROFILE_RANKING, []
    return BUCKET_STRUCTURAL_SELECTION_GAP, []


def _next_family_for_blocker_summary(dominant_class: str) -> str:
    if dominant_class == BUCKET_EDGE_GATE_REJECTION:
        return NEXT_EDGE_SHARE_OVERRIDE
    if dominant_class == BUCKET_CONTINUITY_GATE_REJECTION:
        return NEXT_CONTINUITY_FIX
    if dominant_class == BUCKET_REPEATED_ANCHOR_GATE_REJECTION:
        return NEXT_REPEATED_ANCHOR_FIX
    if dominant_class == BUCKET_SELECTION_ARTIFACT_GAP:
        return NEXT_PROOF_SELECTION_TRACE_REFRESH
    if dominant_class in {BUCKET_STRUCTURAL_SELECTION_GAP, BUCKET_PROFILE_RANKING}:
        return NEXT_TRUTH_LAYER_INJECTION_PROBE
    return NEXT_PROOF_SELECTION_TRACE_REFRESH


def _blocker_rationale(dominant_class: str, dominant_count: int) -> str:
    if dominant_class == BUCKET_EDGE_GATE_REJECTION:
        return (
            f"{dominant_count} reviewed-positive collapsed frames were rejected by the selected-segment "
            "edge-share gate. Queue a reviewed-positive-only edge-share override; do not relax the "
            "general runtime gate."
        )
    if dominant_class == BUCKET_CONTINUITY_GATE_REJECTION:
        return (
            f"{dominant_count} reviewed-positive collapsed frames were rejected by continuity. Queue a "
            "reviewed-positive continuity follow-through fix scoped to reviewed-positive proposal lineage."
        )
    if dominant_class == BUCKET_REPEATED_ANCHOR_GATE_REJECTION:
        return (
            f"{dominant_count} reviewed-positive collapsed frames were rejected by repeated-anchor safety. "
            "Queue a narrow reviewed-positive repeated-anchor follow-through fix."
        )
    if dominant_class == BUCKET_SELECTION_ARTIFACT_GAP:
        return (
            "The saved proof artifacts still do not include enough row-level selected-segment gate trace "
            "to name a detector-side rejection honestly. Add proof trace instrumentation and rerun."
        )
    if dominant_class == BUCKET_STRUCTURAL_SELECTION_GAP:
        return (
            "Reviewed-positive collapsed rows have trace coverage but no single rejection gate explains "
            "selection failure. Treat this as a structural selection-funnel gap before adding another profile."
        )
    return "Reviewed-positive selected-segment blocker summary selected the next family from generated trace evidence."


def _markdown_summary(summary: dict[str, Any], taxonomy: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed-Positive Selection Follow-Through Fix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- collapsedReviewedPositiveFrameCount: {summary.get('reviewedPositiveCollapsedFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- gapClassCounts: {json.dumps(taxonomy.get('gapClassCounts') or {}, sort_keys=True)}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_selection_followthrough_fix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    crop_geometry_root: Path = DEFAULT_CROP_GEOMETRY_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    attempt_number: int = 1,
    attempt_approach_family: str = "reviewed_positive_selection_followthrough_diagnosis",
) -> dict[str, Any]:
    output_root = Path(output_root)
    crop_geometry_root = Path(crop_geometry_root)
    promoted_proof_root = Path(promoted_proof_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)

    coverage = _load_json_dict(crop_geometry_root / "reviewed_positive_crop_geometry_scale_coverage.json")
    recovery_profile_matrix = _load_json_dict(promoted_proof_root / "recovery_profile_matrix.json")
    proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")
    selected_cluster_delta = _load_optional_json_dict(promoted_proof_root / "selected_cluster_delta.json")
    retention_summary = _load_optional_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(suite_root / "suite_summary.json")

    diagnostics_by_frame = _profile_diagnostics_by_frame(recovery_profile_matrix)
    selected_frames = _selected_frame_ids(recovery_profile_matrix)
    accepted_frames = _accepted_frame_ids(proof_summary)
    selected_profile_name = str(recovery_profile_matrix.get("selectedProfileName") or "")
    rows = []
    for row in _collapsed_reviewed_positive_rows(coverage):
        frame_id = _safe_int(row.get("frameIndex"), -1)
        profile_row = diagnostics_by_frame.get(frame_id, {})
        gap_class = _classify_collapsed_row(
            row,
            profile_row=profile_row,
            selected_frame_ids=selected_frames,
            accepted_frame_ids=accepted_frames,
            selected_profile_name=selected_profile_name,
        )
        rows.append(
            {
                "frameIndex": frame_id,
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "windowId": row.get("windowId"),
                "sourceClipId": row.get("sourceClipId"),
                "reviewedBBox": row.get("reviewedBBox"),
                "rawDetected": bool(row.get("rawDetected") or profile_row.get("rawDetected")),
                "candidateGenerated": bool(
                    row.get("candidateGenerated")
                    or row.get("proposalGenerated")
                    or profile_row.get("proposalGenerated")
                ),
                "collapsed": bool(row.get("collapsed") or profile_row.get("collapsed")),
                "selected": bool(row.get("selected") or profile_row.get("selected") or frame_id in selected_frames),
                "accepted": bool(row.get("accepted") or profile_row.get("accepted") or frame_id in accepted_frames),
                "proposalWindowKinds": list(
                    profile_row.get("proposalWindowKinds")
                    or dict(row.get("proofEvidence") or {}).get("proposalWindowKinds")
                    or []
                ),
                "gapClass": gap_class,
                "proofEvidence": {
                    "coverage": dict(row.get("proofEvidence") or {}),
                    "recoveryProfile": profile_row,
                },
            }
        )

    attempt_three_blocker_summary = (
        int(attempt_number) >= 3
        and str(attempt_approach_family) == "reviewed_positive_selection_blocker_summary"
    )
    if attempt_three_blocker_summary:
        gate_trace_rows = []
        trace_weak_reasons: list[str] = []
        for row in rows:
            frame_id = _safe_int(row.get("frameIndex"), -1)
            profile_row = diagnostics_by_frame.get(frame_id, {})
            trace = _selection_gate_trace(profile_row, row)
            dominant_gate_class, row_weak_reasons = _classify_selection_gate_trace(trace)
            trace_weak_reasons.extend(row_weak_reasons)
            gate_trace_rows.append(
                {
                    "frameIndex": frame_id,
                    "reviewItemId": row.get("reviewItemId"),
                    "candidateFrameId": row.get("candidateFrameId"),
                    "windowId": row.get("windowId"),
                    "sourceClipId": row.get("sourceClipId"),
                    "proposalWindowKinds": row.get("proposalWindowKinds") or [],
                    "dominantGateClass": dominant_gate_class,
                    "reviewedPositiveLineageMatch": trace.get("reviewedPositiveLineageMatch"),
                    "syntheticRowRejected": bool(trace.get("syntheticRowRejected", False)),
                    "repeatedAnchorRejected": bool(trace.get("repeatedAnchorRejected", False)),
                    "continuityRejected": bool(trace.get("continuityRejected", False)),
                    "segmentLengthRejected": bool(trace.get("segmentLengthRejected", False)),
                    "edgeShareRejected": bool(trace.get("edgeShareRejected", False)),
                    "selectedProfileRankingRejected": bool(
                        trace.get("selectedProfileRankingRejected", False)
                    ),
                    "edgeShareForSegment": trace.get("edgeShareForSegment"),
                    "segmentFrameCount": trace.get("segmentFrameCount"),
                    "weakEvidenceReasons": row_weak_reasons,
                }
            )
        trace_counts = Counter(str(row["dominantGateClass"]) for row in gate_trace_rows)
        dominant_trace_class, dominant_trace_count = _dominant_blocker_summary(dict(trace_counts))
        next_family = _next_family_for_blocker_summary(dominant_trace_class)
        weak_reasons = sorted(set(trace_weak_reasons))
        generated_at = _utc_now_iso()
        classification = {
            "generatedAt": generated_at,
            "attemptNumber": int(attempt_number),
            "attemptApproachFamily": str(attempt_approach_family),
            "classifiedFrameCount": len(gate_trace_rows),
            "dominantBlockerClass": dominant_trace_class,
            "dominantBlockerFrameCount": dominant_trace_count,
            "gateClassCounts": dict(sorted(trace_counts.items())),
            "nextCorrectiveFamily": next_family,
            "weakEvidenceReasons": weak_reasons,
        }
        gate_trace = {
            "generatedAt": generated_at,
            "frameGateTrace": gate_trace_rows,
            "requiredGateFields": [
                "reviewedPositiveLineageMatch",
                "syntheticRowRejected",
                "repeatedAnchorRejected",
                "continuityRejected",
                "segmentLengthRejected",
                "edgeShareRejected",
                "selectedProfileRankingRejected",
            ],
        }
        blocker_summary = {
            "generatedAt": generated_at,
            "batchName": DEFAULT_BATCH_NAME,
            "attemptNumber": int(attempt_number),
            "attemptBudget": 3,
            "attemptApproachFamily": str(attempt_approach_family),
            "batchStatus": "exhausted",
            "goalAchieved": False,
            "roadmapAdvanceAllowed": True,
            "dominantBlockerClass": dominant_trace_class,
            "dominantBlockerFrameCount": dominant_trace_count,
            "blockerRationale": _blocker_rationale(dominant_trace_class, dominant_trace_count),
            "nextCorrectiveFamily": next_family,
            "nextRecommendedBatch": next_family,
            "reviewedPositiveFrameCount": _safe_int(coverage.get("reviewedPositiveFrameCount"), len(rows)),
            "reviewedPositiveCollapsedFrameCount": len(rows),
            "reviewedPositiveSelectedFrameCount": sum(1 for row in rows if bool(row.get("selected"))),
            "reviewedPositiveAcceptedFrameCount": sum(1 for row in rows if bool(row.get("accepted"))),
            "weakEvidenceReasons": weak_reasons,
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
        decision = {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": True,
            "dominantBlockerClass": dominant_trace_class,
            "dominantBlockerFrameCount": dominant_trace_count,
            "nextCorrectiveFamily": next_family,
            "nextRecommendedBatch": next_family,
            "weakEvidenceReasons": weak_reasons,
            "runtimeDefaultChanged": False,
            "rationale": blocker_summary["blockerRationale"],
        }
        batch_outcome = {
            **blocker_summary,
            "decisionMatrix": decision,
        }
        _write_json(output_root / "reviewed_positive_selection_blocker_classification.json", classification)
        _write_json(output_root / "reviewed_positive_selection_gate_trace.json", gate_trace)
        _write_json(output_root / "blocker_summary.json", blocker_summary)
        _write_json(output_root / "decision_matrix.json", decision)
        _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
        _write_json(output_root / "reviewed_positive_selection_followthrough_summary.json", blocker_summary)
        (output_root / "batch_outcome_analysis.md").write_text(
            _markdown_summary(blocker_summary, {"gapClassCounts": classification["gateClassCounts"]}),
            encoding="utf-8",
        )
        return {
            "summary": blocker_summary,
            "reviewedPositiveSelectionBlockerClassification": classification,
            "reviewedPositiveSelectionGateTrace": gate_trace,
            "blockerSummary": blocker_summary,
            "decisionMatrix": decision,
            "batchOutcomeAnalysis": batch_outcome,
        }

    counts = Counter(str(row["gapClass"]) for row in rows)
    dominant_class, dominant_count = _dominant(dict(counts))
    reviewed_positive_selected_frame_count = sum(1 for row in rows if bool(row.get("selected")))
    reviewed_positive_accepted_frame_count = sum(1 for row in rows if bool(row.get("accepted")))
    weak_reasons = []
    if dominant_class == BUCKET_EVIDENCE_GAP:
        weak_reasons.append("reviewed_positive_selected_followthrough_rejection_fields_missing")
    next_family = _next_family(dominant_class)
    attempt_two_selected_profile = (
        int(attempt_number) >= 2
        and str(attempt_approach_family) == "reviewed_positive_selected_segment_profile"
    )
    edge_share_override_attempt = str(attempt_approach_family) == "reviewed_positive_edge_share_override"
    if edge_share_override_attempt and reviewed_positive_selected_frame_count > 0:
        weak_reasons = []
        next_family = NEXT_ACCEPTANCE_FIX
    elif edge_share_override_attempt and reviewed_positive_selected_frame_count == 0:
        weak_reasons = ["reviewed_positive_edge_share_override_selected_zero_frames"]
        next_family = NEXT_EDGE_SHARE_PLUS_ACCEPTANCE_TRACE
    elif attempt_two_selected_profile and reviewed_positive_selected_frame_count > 0:
        weak_reasons = []
        next_family = NEXT_ACCEPTANCE_FIX
    elif attempt_two_selected_profile and reviewed_positive_selected_frame_count == 0:
        weak_reasons = ["reviewed_positive_selected_segment_profile_selected_zero_frames"]
        next_family = NEXT_SELECTION_BLOCKER_SUMMARY
    generated_at = _utc_now_iso()
    rejected_positive_count = sum(
        1
        for row in _list_dicts(coverage.get("refutedSeeds"))
        if bool(row.get("selected") or row.get("accepted") or row.get("positiveEvidence"))
    )
    matrix = {
        "generatedAt": generated_at,
        "reviewedPositiveFrameCount": _safe_int(coverage.get("reviewedPositiveFrameCount"), len(rows)),
        "collapsedReviewedPositiveFrameCount": len(rows),
        "classifiedCollapsedFrameCount": len(rows),
        "collapsedReviewedPositiveFrames": rows,
        "rejectedBootstrapSeedPositiveEvidenceCount": rejected_positive_count,
    }
    taxonomy = {
        "generatedAt": generated_at,
        "classifiedCollapsedFrameCount": len(rows),
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "dominantBlockerShare": round(dominant_count / len(rows), 3) if rows else 0.0,
        "gapClassCounts": dict(sorted(counts.items())),
    }
    proposal_profile = _proposal_profile(recovery_profile_matrix)
    funnel_audit = {
        "generatedAt": generated_at,
        "selectedProfileName": selected_profile_name or None,
        "proposalProfileName": "proposal_windows_075",
        "reviewedPositiveProposalEvidenceFrameCount": _safe_int(
            coverage.get("reviewedPositiveProposalEvidenceFrameCount"), 0
        ),
        "reviewedPositiveCollapsedFrameCount": _safe_int(
            coverage.get("reviewedPositiveCollapsedFrameCount"), len(rows)
        ),
        "reviewedPositiveSelectedFrameCount": reviewed_positive_selected_frame_count,
        "reviewedPositiveAcceptedFrameCount": reviewed_positive_accepted_frame_count,
        "proposalProfileCollapsedFrames": _safe_int(proposal_profile.get("proposalCollapsedFrames"), 0),
        "proposalProfileSelectedFrames": _safe_int(proposal_profile.get("selectedFrames"), 0),
        "proposalFrameDiagnosticCount": len(diagnostics_by_frame),
        "selectedClusterRemainingTruthGateReasons": list(
            selected_cluster_delta.get("remainingTruthGateReasons") or []
        ),
    }
    decision_goal_achieved = len(rows) > 0 and dominant_class != ""
    if attempt_two_selected_profile:
        decision_goal_achieved = reviewed_positive_selected_frame_count > 0
    if edge_share_override_attempt:
        decision_goal_achieved = reviewed_positive_selected_frame_count > 0
    if edge_share_override_attempt and reviewed_positive_selected_frame_count > 0:
        rationale = (
            "Reviewed-positive edge-share override moved rows into selected-frame follow-through; "
            "move to acceptance diagnostics next."
        )
    elif edge_share_override_attempt:
        rationale = (
            "Reviewed-positive edge-share override still selected zero frames; add acceptance-gate trace "
            "only if generated proof evidence justifies it."
        )
    elif attempt_two_selected_profile and reviewed_positive_selected_frame_count > 0:
        rationale = (
            "Reviewed-positive rows now reach selected-frame follow-through; move to acceptance diagnostics next."
        )
    elif attempt_two_selected_profile:
        rationale = (
            "Reviewed-positive selected-segment profile still selected zero frames; advance to the blocker-summary attempt."
        )
    elif dominant_class == BUCKET_SEGMENT_SELECTION_ZERO:
        rationale = (
            "Reviewed-positive candidate rows collapse but are not selected; test a reviewed-positive selected segment profile next."
        )
    else:
        rationale = "Reviewed-positive selection follow-through artifacts are missing rejection-level proof fields."
    decision = {
        "goalAchieved": decision_goal_achieved,
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "reviewedPositiveSelectedFrameCount": reviewed_positive_selected_frame_count,
        "reviewedPositiveAcceptedFrameCount": reviewed_positive_accepted_frame_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "weakEvidenceReasons": weak_reasons,
        "runtimeDefaultChanged": False,
        "rationale": rationale,
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": int(attempt_number),
        "attemptBudget": 3,
        "attemptApproachFamily": str(attempt_approach_family),
        "batchStatus": "succeeded" if decision["goalAchieved"] else "needs_next_attempt",
        "goalAchieved": decision["goalAchieved"],
        "roadmapAdvanceAllowed": bool(decision["goalAchieved"]),
        "reviewedPositiveFrameCount": matrix["reviewedPositiveFrameCount"],
        "reviewedPositiveCollapsedFrameCount": len(rows),
        "reviewedPositiveSelectedFrameCount": reviewed_positive_selected_frame_count,
        "reviewedPositiveAcceptedFrameCount": reviewed_positive_accepted_frame_count,
        "classifiedCollapsedFrameCount": len(rows),
        "dominantBlockerClass": dominant_class,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "weakEvidenceReasons": weak_reasons,
        "rejectedBootstrapSeedPositiveEvidenceCount": rejected_positive_count,
        "runtimeDefaultChanged": False,
        "sourceManifestMutationPolicy": "not_mutated",
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
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
    }
    _write_json(output_root / "reviewed_positive_selection_followthrough_summary.json", summary)
    _write_json(output_root / "reviewed_positive_selection_followthrough_matrix.json", matrix)
    _write_json(output_root / "reviewed_positive_selection_gate_taxonomy.json", taxonomy)
    _write_json(output_root / "reviewed_positive_selected_funnel_audit.json", funnel_audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(
        _markdown_summary(summary, taxonomy),
        encoding="utf-8",
    )
    return {
        "summary": summary,
        "reviewedPositiveSelectionFollowthroughMatrix": matrix,
        "reviewedPositiveSelectionGateTaxonomy": taxonomy,
        "reviewedPositiveSelectedFunnelAudit": funnel_audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--crop-geometry-root", type=Path, default=DEFAULT_CROP_GEOMETRY_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument(
        "--attempt-approach-family",
        default="reviewed_positive_selection_followthrough_diagnosis",
    )
    args = parser.parse_args()
    payload = run_promoted_v6_reviewed_positive_selection_followthrough_fix(
        output_root=args.output_root,
        crop_geometry_root=args.crop_geometry_root,
        promoted_proof_root=args.promoted_proof_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
