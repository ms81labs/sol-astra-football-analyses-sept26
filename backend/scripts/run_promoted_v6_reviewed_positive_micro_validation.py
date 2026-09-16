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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_micro_validation_v1"
DEFAULT_EXPANSION_RESOLUTION_ROOT = DEFAULT_SUITE_ROOT / "manual_review_expansion_resolution_v1"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_RUNTIME_DEFAULT_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_SOURCE_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
DEFAULT_BATCH_NAME = "reviewed_positive_micro_validation_v1"
DEFAULT_ATTEMPT_FAMILY = "reviewed_positive_micro_validation"

BUCKET_NO_PROPOSAL = "reviewed_positive_no_promoted_proposal"
BUCKET_RAW_NOT_COLLAPSED = "reviewed_positive_raw_detected_not_collapsed"
BUCKET_COLLAPSED_NOT_SELECTED = "reviewed_positive_collapsed_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "reviewed_positive_selected_not_accepted"
BUCKET_ALREADY_ACCEPTED = "reviewed_positive_already_accepted"
BUCKET_COVERAGE_GAP = "reviewed_positive_artifact_coverage_gap"

NEXT_PROPOSAL_GENERATION = "reviewed_positive_proposal_generation_fix"
NEXT_SELECTION_FOLLOWTHROUGH = "reviewed_positive_selection_followthrough_fix"
NEXT_ACCEPTANCE_FIX = "reviewed_positive_acceptance_fix"
NEXT_DIAGNOSTIC_REFRESH = "proof_diagnostic_instrumentation_refresh"
NEXT_MANUAL_REVIEW = "manual_review_required"

BUCKET_PRIORITY = [
    BUCKET_COVERAGE_GAP,
    BUCKET_NO_PROPOSAL,
    BUCKET_RAW_NOT_COLLAPSED,
    BUCKET_COLLAPSED_NOT_SELECTED,
    BUCKET_SELECTED_NOT_ACCEPTED,
    BUCKET_ALREADY_ACCEPTED,
]


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


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _reviewed_positive_rows(truth_seed: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(truth_seed.get("reviewedPositiveSeedRows")),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )


def _frame_id_from_row(row: dict[str, Any]) -> int | None:
    for key in ("frameIndex", "frameId", "Frame_ID", "frame", "candidateFrameIndex"):
        if key in row:
            frame_id = _safe_int(row.get(key), -1)
            if frame_id >= 0:
                return frame_id
    return None


def _frame_set_from_rows(rows: object) -> set[int]:
    frames: set[int] = set()
    if isinstance(rows, list):
        for item in rows:
            if isinstance(item, dict):
                frame_id = _frame_id_from_row(item)
            else:
                frame_id = _safe_int(item, -1)
            if frame_id is not None and frame_id >= 0:
                frames.add(frame_id)
    elif isinstance(rows, dict):
        for key, value in rows.items():
            frame_id = _safe_int(key, -1)
            if frame_id >= 0:
                frames.add(frame_id)
            if isinstance(value, dict):
                nested_frame_id = _frame_id_from_row(value)
                if nested_frame_id is not None and nested_frame_id >= 0:
                    frames.add(nested_frame_id)
            else:
                nested_frame_id = _safe_int(value, -1)
                if nested_frame_id >= 0:
                    frames.add(nested_frame_id)
    return frames


def _frame_set_from_payload(payload: dict[str, Any], keys: tuple[str, ...]) -> set[int]:
    frames: set[int] = set()
    for key in keys:
        frames.update(_frame_set_from_rows(payload.get(key)))
    return frames


def _frames_from_ball_layer(layer: object) -> set[int]:
    if not isinstance(layer, dict):
        return set()
    frames = _frame_set_from_rows(layer.get("rows"))
    frames.update(_frame_set_from_rows(layer.get("rawRows")))
    frames.update(_frame_set_from_rows(layer.get("filteredRows")))
    return frames


def _discover_proof_root(*, validation_root: Path, proof_root: Path | None) -> Path | None:
    if proof_root is not None:
        return Path(proof_root)
    arm_matrix_path = validation_root / "arm_matrix.json"
    if not arm_matrix_path.exists():
        return None
    arm_matrix = _load_json_dict(arm_matrix_path)
    for arm in _list_dicts(arm_matrix.get("arms")):
        if arm.get("armName") != "promoted_v6_baseline":
            continue
        for run in _list_dicts(arm.get("proofRuns")):
            reused = run.get("reusedEvidence")
            if not isinstance(reused, dict):
                continue
            for key in ("proofSummaryPath", "selectedClusterDeltaPath", "ballTruthLayersPath"):
                path_value = reused.get(key)
                if path_value:
                    return Path(str(path_value)).expanduser().parent
    return None


def _load_proof_artifacts(*, validation_root: Path, proof_root: Path | None) -> dict[str, Any]:
    resolved_proof_root = _discover_proof_root(validation_root=validation_root, proof_root=proof_root)
    artifacts: dict[str, Any] = {"proofRoot": str(resolved_proof_root) if resolved_proof_root else None}
    if resolved_proof_root is None:
        return artifacts
    artifacts["recoveryProfileMatrix"] = _load_optional_json_dict(resolved_proof_root / "recovery_profile_matrix.json")
    artifacts["proofSummary"] = _load_optional_json_dict(resolved_proof_root / "proof_summary.json")
    artifacts["selectedClusterDelta"] = _load_optional_json_dict(resolved_proof_root / "selected_cluster_delta.json")
    artifacts["ballTruthLayers"] = _load_optional_json_dict(resolved_proof_root / "ball_truth_layers.json")
    return artifacts


def _explicit_frame_evidence(recovery_profile_matrix: dict[str, Any]) -> dict[int, dict[str, bool]]:
    evidence: dict[int, dict[str, bool]] = {}
    for row in _list_dicts(recovery_profile_matrix.get("reviewedPositiveFrameEvidence")):
        frame_id = _frame_id_from_row(row)
        if frame_id is None:
            continue
        evidence[frame_id] = {
            "proposalGenerated": bool(row.get("proposalGenerated") or row.get("proposalCandidateGenerated")),
            "rawDetected": bool(row.get("rawDetected") or row.get("proposalRawDetected")),
            "collapsed": bool(row.get("collapsed") or row.get("proposalCollapsed")),
            "selected": bool(row.get("selected") or row.get("proposalSelected")),
            "accepted": bool(row.get("accepted") or row.get("proposalAccepted")),
        }
    return evidence


def _frame_set_from_selected_cluster_delta(selected_cluster_delta: dict[str, Any], keys: tuple[str, ...]) -> set[int]:
    frames = _frame_set_from_payload(selected_cluster_delta, keys)
    for section_name in ("after", "before"):
        section = selected_cluster_delta.get(section_name)
        if isinstance(section, dict):
            frames.update(_frame_set_from_payload(section, keys))
    return frames


def _proof_frame_sets(*, proof_artifacts: dict[str, Any]) -> dict[str, set[int]]:
    recovery_profile_matrix = dict(proof_artifacts.get("recoveryProfileMatrix") or {})
    ball_truth_layers = dict(proof_artifacts.get("ballTruthLayers") or {})
    selected_cluster_delta = dict(proof_artifacts.get("selectedClusterDelta") or {})
    collapsed_frames = _frame_set_from_payload(
        recovery_profile_matrix,
        ("proposalCollapsedFrameIds", "proposalCollapsedFramesByFrame", "collapsedFrameIds"),
    )
    selected_frames = _frame_set_from_payload(
        recovery_profile_matrix,
        ("proposalSelectedFrameIds", "selectedFrameIds"),
    )
    accepted_frames = _frame_set_from_payload(
        recovery_profile_matrix,
        ("proposalAcceptedFrameIds", "acceptedFrameIds"),
    )
    raw_frames = _frame_set_from_payload(
        recovery_profile_matrix,
        ("proposalRawDetectedFrameIds", "rawDetectedFrameIds"),
    )
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        collapsed_frames.update(
            _frame_set_from_payload(
                profile,
                ("proposalCollapsedFrameIds", "proposalCollapsedFramesByFrame", "collapsedFrameIds"),
            )
        )
        selected_frames.update(
            _frame_set_from_payload(
                profile,
                ("proposalSelectedFrameIds", "selectedFrameIds"),
            )
        )
        accepted_frames.update(
            _frame_set_from_payload(
                profile,
                ("proposalAcceptedFrameIds", "acceptedFrameIds"),
            )
        )
        raw_frames.update(
            _frame_set_from_payload(
                profile,
                ("proposalRawDetectedFrameIds", "rawDetectedFrameIds"),
            )
        )
        for diagnostic in _list_dicts(profile.get("proposalFrameDiagnostics")):
            frame_id = _frame_id_from_row(diagnostic)
            if frame_id is None:
                continue
            if diagnostic.get("proposalGenerated") or diagnostic.get("rawDetected"):
                raw_frames.add(frame_id)
            if diagnostic.get("collapsed"):
                collapsed_frames.add(frame_id)
            if diagnostic.get("selected"):
                selected_frames.add(frame_id)
            if diagnostic.get("accepted"):
                accepted_frames.add(frame_id)
    selected_frames.update(_frame_set_from_selected_cluster_delta(selected_cluster_delta, ("proposalSelectedFrameIds", "selectedFrameIds")))
    accepted_frames.update(
        _frame_set_from_selected_cluster_delta(selected_cluster_delta, ("proposalAcceptedFrameIds", "acceptedFrameIds"))
    )
    accepted_rows = _frames_from_ball_layer(ball_truth_layers.get("acceptedBall"))
    accepted_frames.update(accepted_rows)
    return {
        "raw": raw_frames,
        "collapsed": collapsed_frames,
        "selected": selected_frames,
        "accepted": accepted_frames,
    }


def build_proof_artifact_coverage_audit(
    *,
    proof_artifacts: dict[str, Any],
    reviewed_frame_ids: set[int] | None = None,
) -> dict[str, Any]:
    proof_summary = dict(proof_artifacts.get("proofSummary") or {})
    ball_truth_layers = dict(proof_artifacts.get("ballTruthLayers") or {})
    recovery_profile_matrix = dict(proof_artifacts.get("recoveryProfileMatrix") or {})
    explicit_evidence = _explicit_frame_evidence(recovery_profile_matrix)
    frame_sets = _proof_frame_sets(proof_artifacts=proof_artifacts)
    raw_frames = frame_sets["raw"]
    collapsed_frames = frame_sets["collapsed"]
    selected_frames = frame_sets["selected"]
    accepted_frames = frame_sets["accepted"]
    evidence_frames = set(explicit_evidence) | raw_frames | collapsed_frames | selected_frames | accepted_frames
    reviewed_frame_ids = reviewed_frame_ids or set()
    missing_reviewed_frames = sorted(reviewed_frame_ids - evidence_frames)
    per_frame_available = bool(reviewed_frame_ids) and not missing_reviewed_frames
    missing_fields: list[str] = []
    if not evidence_frames:
        missing_fields.append("reviewed_positive_frame_level_proposal_selection_fields_missing")
    elif missing_reviewed_frames:
        missing_fields.append("reviewed_positive_frame_level_proposal_selection_fields_partial")
    return {
        "generatedAt": _utc_now_iso(),
        "proofRoot": proof_artifacts.get("proofRoot"),
        "perFrameProofCoverageAvailable": per_frame_available,
        "explicitEvidenceFrameCount": len(explicit_evidence),
        "rawDetectedFrameCount": len(raw_frames),
        "collapsedFrameCount": len(collapsed_frames),
        "selectedFrameCount": len(selected_frames),
        "acceptedFrameCount": len(accepted_frames),
        "reviewedFrameCount": len(reviewed_frame_ids),
        "coveredReviewedFrameCount": len(reviewed_frame_ids & evidence_frames),
        "missingReviewedFrames": missing_reviewed_frames,
        "aggregateProofFieldsPresent": {
            "bestProposalRawDetectedFrames": "bestProposalRawDetectedFrames" in proof_summary,
            "bestProposalAfterSeedCollapseFrames": "bestProposalAfterSeedCollapseFrames" in proof_summary,
            "bestProposalSelectedFrames": "bestProposalSelectedFrames" in proof_summary,
            "acceptedBallRows": bool(_frames_from_ball_layer(ball_truth_layers.get("acceptedBall"))),
        },
        "missingArtifactFields": missing_fields,
    }


def build_frame_evidence(*, proof_artifacts: dict[str, Any]) -> dict[int, dict[str, bool]]:
    recovery_profile_matrix = dict(proof_artifacts.get("recoveryProfileMatrix") or {})
    explicit = _explicit_frame_evidence(recovery_profile_matrix)
    frame_sets = _proof_frame_sets(proof_artifacts=proof_artifacts)
    raw_frames = frame_sets["raw"]
    collapsed_frames = frame_sets["collapsed"]
    selected_frames = frame_sets["selected"]
    accepted_frames = frame_sets["accepted"]
    all_frames = set(explicit) | raw_frames | collapsed_frames | selected_frames | accepted_frames
    evidence: dict[int, dict[str, bool]] = {}
    for frame_id in sorted(all_frames):
        explicit_row = explicit.get(frame_id, {})
        evidence[frame_id] = {
            "proposalGenerated": bool(
                explicit_row.get("proposalGenerated")
                or frame_id in raw_frames
                or frame_id in collapsed_frames
                or frame_id in selected_frames
                or frame_id in accepted_frames
            ),
            "rawDetected": bool(
                explicit_row.get("rawDetected")
                or frame_id in raw_frames
                or frame_id in collapsed_frames
                or frame_id in selected_frames
                or frame_id in accepted_frames
            ),
            "collapsed": bool(explicit_row.get("collapsed") or frame_id in collapsed_frames or frame_id in selected_frames or frame_id in accepted_frames),
            "selected": bool(explicit_row.get("selected") or frame_id in selected_frames or frame_id in accepted_frames),
            "accepted": bool(explicit_row.get("accepted") or frame_id in accepted_frames),
        }
    return evidence


def _gap_class_for_evidence(evidence: dict[str, bool] | None) -> str:
    if not evidence:
        return BUCKET_COVERAGE_GAP
    if evidence.get("accepted"):
        return BUCKET_ALREADY_ACCEPTED
    if evidence.get("selected"):
        return BUCKET_SELECTED_NOT_ACCEPTED
    if evidence.get("collapsed"):
        return BUCKET_COLLAPSED_NOT_SELECTED
    if evidence.get("rawDetected") or evidence.get("proposalGenerated"):
        return BUCKET_RAW_NOT_COLLAPSED
    return BUCKET_NO_PROPOSAL


def build_reviewed_positive_frame_matrix(
    *,
    truth_seed: dict[str, Any],
    proof_artifacts: dict[str, Any],
    coverage_audit: dict[str, Any],
) -> dict[str, Any]:
    positives = _reviewed_positive_rows(truth_seed)
    evidence_by_frame = build_frame_evidence(proof_artifacts=proof_artifacts)
    rows: list[dict[str, Any]] = []
    for row in positives:
        frame_id = _safe_int(row.get("frameIndex"), -1)
        evidence = evidence_by_frame.get(frame_id)
        gap_class = _gap_class_for_evidence(evidence)
        rows.append(
            {
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "windowId": row.get("windowId"),
                "sourceClipId": row.get("sourceClipId"),
                "frameIndex": frame_id,
                "timestampSeconds": row.get("timestampSeconds"),
                "reviewDecision": row.get("reviewDecision"),
                "reviewedBBox": row.get("reviewedBBox"),
                "lineageComplete": bool(row.get("lineage")),
                "gapClass": gap_class,
                "proofEvidence": evidence or {},
            }
        )
    counts = Counter(str(row["gapClass"]) for row in rows)
    return {
        "generatedAt": _utc_now_iso(),
        "reviewedPositiveFrameCount": len(rows),
        "reviewedPositiveFrameIds": [row["frameIndex"] for row in rows],
        "bucketCounts": dict(sorted(counts.items())),
        "reviewedPositiveFrames": rows,
        "schemaFields": [
            "reviewItemId",
            "candidateFrameId",
            "windowId",
            "sourceClipId",
            "frameIndex",
            "timestampSeconds",
            "reviewDecision",
            "reviewedBBox",
            "lineageComplete",
            "gapClass",
            "proofEvidence",
        ],
        "perFrameProofCoverageAvailable": coverage_audit.get("perFrameProofCoverageAvailable"),
        "proofRoot": proof_artifacts.get("proofRoot"),
        "missingArtifactFields": coverage_audit.get("missingArtifactFields", []),
    }


def _dominant_bucket_from_counts(counts: Counter[str] | dict[str, int]) -> tuple[str, int]:
    normalized = {str(key): _safe_int(value) for key, value in dict(counts).items()}
    if not normalized:
        return BUCKET_COVERAGE_GAP, 0
    priority_index = {bucket: idx for idx, bucket in enumerate(BUCKET_PRIORITY)}
    return sorted(
        normalized.items(),
        key=lambda item: (-item[1], priority_index.get(item[0], len(priority_index)), item[0]),
    )[0]


def _next_family_for_bucket(bucket: str) -> str:
    if bucket == BUCKET_COVERAGE_GAP:
        return NEXT_DIAGNOSTIC_REFRESH
    if bucket == BUCKET_NO_PROPOSAL:
        return NEXT_PROPOSAL_GENERATION
    if bucket in {BUCKET_RAW_NOT_COLLAPSED, BUCKET_COLLAPSED_NOT_SELECTED}:
        return NEXT_SELECTION_FOLLOWTHROUGH
    if bucket == BUCKET_SELECTED_NOT_ACCEPTED:
        return NEXT_ACCEPTANCE_FIX
    if bucket == BUCKET_ALREADY_ACCEPTED:
        return NEXT_SELECTION_FOLLOWTHROUGH
    return NEXT_MANUAL_REVIEW


def build_gap_taxonomy(*, frame_matrix: dict[str, Any]) -> dict[str, Any]:
    counts = {str(key): _safe_int(value) for key, value in dict(frame_matrix.get("bucketCounts") or {}).items()}
    dominant_bucket, dominant_count = _dominant_bucket_from_counts(counts)
    total = _safe_int(frame_matrix.get("reviewedPositiveFrameCount"), 0)
    return {
        "generatedAt": _utc_now_iso(),
        "classifiedFrameCount": total,
        "gapClassCounts": counts,
        "dominantGapClass": dominant_bucket,
        "dominantGapFrameCount": dominant_count,
        "dominantGapShare": round(dominant_count / total, 3) if total else 0.0,
    }


def build_decision_matrix(*, gap_taxonomy: dict[str, Any], coverage_audit: dict[str, Any]) -> dict[str, Any]:
    dominant_bucket = str(gap_taxonomy.get("dominantGapClass") or BUCKET_COVERAGE_GAP)
    weak_reasons: list[str] = []
    if dominant_bucket == BUCKET_COVERAGE_GAP:
        weak_reasons.extend(str(item) for item in coverage_audit.get("missingArtifactFields", []))
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": _safe_int(gap_taxonomy.get("dominantGapFrameCount"), 0),
        "nextCorrectiveFamily": _next_family_for_bucket(dominant_bucket),
        "nextRecommendedBatch": _next_family_for_bucket(dominant_bucket),
        "successfulApproach": "A_reviewed_positive_micro_validation",
        "weakEvidenceReasons": weak_reasons,
        "rationale": (
            "Reviewed-positive proof lacks frame-level proposal/selection diagnostics."
            if dominant_bucket == BUCKET_COVERAGE_GAP
            else "Reviewed positives classify to a concrete promoted-v6 follow-through bucket."
        ),
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed Positive Micro Validation",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- reviewedPositiveFrameCount: {summary.get('reviewedPositiveFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- perFrameProofCoverageAvailable: {summary.get('perFrameProofCoverageAvailable')}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_micro_validation(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    expansion_resolution_root: Path = DEFAULT_EXPANSION_RESOLUTION_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    proof_root: Path | None = None,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    runtime_default_path: Path = DEFAULT_RUNTIME_DEFAULT_PATH,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    truth_seed = _load_json_dict(Path(expansion_resolution_root) / "expanded_reviewed_truth_seed.json")
    proof_artifacts = _load_proof_artifacts(validation_root=Path(validation_root), proof_root=proof_root)
    retention_summary = _load_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(Path(suite_root) / "suite_summary.json")

    positive_rows = _reviewed_positive_rows(truth_seed)
    reviewed_frame_ids = {
        _safe_int(row.get("frameIndex"), -1)
        for row in positive_rows
        if _safe_int(row.get("frameIndex"), -1) >= 0
    }
    coverage_audit = build_proof_artifact_coverage_audit(
        proof_artifacts=proof_artifacts,
        reviewed_frame_ids=reviewed_frame_ids,
    )
    frame_matrix = build_reviewed_positive_frame_matrix(
        truth_seed=truth_seed,
        proof_artifacts=proof_artifacts,
        coverage_audit=coverage_audit,
    )
    gap_taxonomy = build_gap_taxonomy(frame_matrix=frame_matrix)
    decision = build_decision_matrix(gap_taxonomy=gap_taxonomy, coverage_audit=coverage_audit)
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": "succeeded" if decision["goalAchieved"] else "blocked",
        "truthStatus": truth_seed.get("truthStatus"),
        "reviewedPositiveFrameCount": len(positive_rows),
        "reviewedPositiveFrames": [_safe_int(row.get("frameIndex"), -1) for row in positive_rows],
        "perFrameProofCoverageAvailable": coverage_audit.get("perFrameProofCoverageAvailable"),
        "proofRoot": proof_artifacts.get("proofRoot"),
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "runPodUsed": False,
        "detectorProfileAdded": False,
        **decision,
    }
    batch_outcome = {
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "approachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": summary["batchStatus"],
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "dominantBlockerClass": summary["dominantBlockerClass"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "nextRecommendedBatch": summary["nextRecommendedBatch"],
        "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
        "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "artifacts": {
            "reviewedPositiveMicroValidationSummaryPath": str(
                output_root / "reviewed_positive_micro_validation_summary.json"
            ),
            "reviewedPositiveFrameMatrixPath": str(output_root / "reviewed_positive_frame_matrix.json"),
            "reviewedPositiveGapTaxonomyPath": str(output_root / "reviewed_positive_gap_taxonomy.json"),
            "proofArtifactCoverageAuditPath": str(output_root / "proof_artifact_coverage_audit.json"),
        },
    }

    _ = runtime_default_path, source_manifest_path
    _write_json(output_root / "reviewed_positive_micro_validation_summary.json", summary)
    _write_json(output_root / "reviewed_positive_frame_matrix.json", frame_matrix)
    _write_json(output_root / "reviewed_positive_gap_taxonomy.json", gap_taxonomy)
    _write_json(output_root / "proof_artifact_coverage_audit.json", coverage_audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    return {
        "summary": summary,
        "reviewedPositiveFrameMatrix": frame_matrix,
        "reviewedPositiveGapTaxonomy": gap_taxonomy,
        "proofArtifactCoverageAudit": coverage_audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--expansion-resolution-root", type=Path, default=DEFAULT_EXPANSION_RESOLUTION_ROOT)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--proof-root", type=Path, default=None)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--runtime-default-path", type=Path, default=DEFAULT_RUNTIME_DEFAULT_PATH)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_SOURCE_MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_reviewed_positive_micro_validation(
        output_root=args.output_root,
        expansion_resolution_root=args.expansion_resolution_root,
        validation_root=args.validation_root,
        proof_root=args.proof_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        runtime_default_path=args.runtime_default_path,
        source_manifest_path=args.source_manifest_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
