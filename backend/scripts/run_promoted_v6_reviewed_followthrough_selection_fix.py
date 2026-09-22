from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_followthrough_selection_fix_v1"
DEFAULT_MANUAL_RESOLUTION_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_resolution_v1"
DEFAULT_MANUAL_REVIEW_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_followthrough_v1"
DEFAULT_FOLLOWTHROUGH_ROOT = DEFAULT_SUITE_ROOT / "proposal_selection_followthrough_fix_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_RUNTIME_DEFAULT_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_SOURCE_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
DEFAULT_BATCH_NAME = "reviewed_followthrough_selection_fix_v1"
DEFAULT_ATTEMPT_FAMILY = "reviewed_truth_followthrough_diagnosis"
MIN_POSITIVE_FRAMES_FOR_DETECTOR_FIX = 5

BUCKET_NOT_GENERATED = "reviewed_positive_candidate_not_generated"
BUCKET_COLLAPSED_NOT_SELECTED = "reviewed_positive_collapsed_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "reviewed_positive_selected_not_accepted"
BUCKET_ALREADY_ACCEPTED_SPARSE = "reviewed_positive_already_accepted_but_retention_sparse"
BUCKET_EVIDENCE_TOO_SPARSE = "reviewed_positive_evidence_too_sparse"

NEXT_GOLD_TRUTH_REFUTED = "gold_truth_seed_refuted_refresh"
NEXT_MANUAL_REVIEW_EXPANSION = "manual_review_expansion"
NEXT_REVIEWED_PROFILE = "reviewed_positive_followthrough_profile"
NEXT_SOURCE_MANIFEST_REFRESH = "source_manifest_refresh"


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, Any]:
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


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _reviewed_positive_rows(truth_seed: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(truth_seed.get("reviewedPositiveSeedRows")),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )


def _reviewed_negative_rows(truth_seed: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(truth_seed.get("reviewedNegativeSeedRows")),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )


def _overlay_counts(overlay: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in _list_dicts(overlay.get("reviewItems")):
        counts[str(item.get("decision") or "")] += 1
    return dict(sorted(counts.items()))


def _funnel_value(funnel: dict[str, Any], summary: dict[str, Any], *keys: str) -> int:
    values = []
    proposal_diagnostics = summary.get("proposalDiagnostics")
    if not isinstance(proposal_diagnostics, dict):
        proposal_diagnostics = {}
    for key in keys:
        values.append(_safe_int(funnel.get(key), 0))
        values.append(_safe_int(proposal_diagnostics.get(key), 0))
    return max(values, default=0)


def build_followthrough_evidence(
    *,
    profile_selection_funnel_audit: dict[str, Any],
    proposal_followthrough_summary: dict[str, Any],
) -> dict[str, Any]:
    candidate_frames = _funnel_value(
        profile_selection_funnel_audit,
        proposal_followthrough_summary,
        "proposalCandidateFrames",
    )
    raw_detected_frames = _funnel_value(
        profile_selection_funnel_audit,
        proposal_followthrough_summary,
        "proposalRawDetectedFrames",
    )
    collapsed_frames = _funnel_value(
        profile_selection_funnel_audit,
        proposal_followthrough_summary,
        "proposalCollapsedFrames",
    )
    selected_frames = max(
        _safe_int(profile_selection_funnel_audit.get("proposalSelectedFrames"), 0),
        _safe_int(profile_selection_funnel_audit.get("selectedFrames"), 0),
        _safe_int(dict(proposal_followthrough_summary.get("proposalDiagnostics") or {}).get("selectedFrames"), 0),
    )
    accepted_frames = max(
        _safe_int(profile_selection_funnel_audit.get("acceptedFrames"), 0),
        _safe_int(profile_selection_funnel_audit.get("proposalAcceptedFrames"), 0),
        _safe_int(dict(proposal_followthrough_summary.get("proposalDiagnostics") or {}).get("acceptedFrames"), 0),
    )
    return {
        "proposalCandidateFrames": candidate_frames,
        "proposalRawDetectedFrames": raw_detected_frames,
        "proposalCollapsedFrames": collapsed_frames,
        "proposalSelectedFrames": selected_frames,
        "proposalAcceptedFrames": accepted_frames,
        "selectedClusterTruthGateSparse": bool(profile_selection_funnel_audit.get("selectedClusterTruthGateSparse")),
        "sourceSummaryBatchStatus": proposal_followthrough_summary.get("batchStatus"),
        "sourceSummaryDominantBlockerClass": proposal_followthrough_summary.get("dominantBlockerClass"),
    }


def _bucket_for_reviewed_positive(
    *,
    positive_count: int,
    followthrough_evidence: dict[str, Any],
) -> str:
    if positive_count < MIN_POSITIVE_FRAMES_FOR_DETECTOR_FIX:
        return BUCKET_EVIDENCE_TOO_SPARSE
    candidate_frames = _safe_int(followthrough_evidence.get("proposalCandidateFrames"), 0)
    collapsed_frames = _safe_int(followthrough_evidence.get("proposalCollapsedFrames"), 0)
    selected_frames = _safe_int(followthrough_evidence.get("proposalSelectedFrames"), 0)
    accepted_frames = _safe_int(followthrough_evidence.get("proposalAcceptedFrames"), 0)
    if candidate_frames <= 0:
        return BUCKET_NOT_GENERATED
    if collapsed_frames > 0 and selected_frames <= 0:
        return BUCKET_COLLAPSED_NOT_SELECTED
    if selected_frames > 0 and accepted_frames <= 0:
        return BUCKET_SELECTED_NOT_ACCEPTED
    if accepted_frames > 0:
        return BUCKET_ALREADY_ACCEPTED_SPARSE
    return BUCKET_NOT_GENERATED


def build_reviewed_positive_followthrough_matrix(
    *,
    truth_seed: dict[str, Any],
    followthrough_evidence: dict[str, Any],
) -> dict[str, Any]:
    positives = _reviewed_positive_rows(truth_seed)
    bucket = _bucket_for_reviewed_positive(
        positive_count=len(positives),
        followthrough_evidence=followthrough_evidence,
    )
    rows = []
    for row in positives:
        rows.append(
            {
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "frameIndex": row.get("frameIndex"),
                "windowId": row.get("windowId"),
                "sourceClipId": row.get("sourceClipId"),
                "reviewDecision": row.get("reviewDecision"),
                "seedBBox": row.get("seedBBox"),
                "reviewedBBox": row.get("reviewedBBox"),
                "lineageComplete": bool(row.get("lineage")),
                "followthroughBucket": bucket,
                "evidence": followthrough_evidence,
            }
        )
    counts = Counter(str(item["followthroughBucket"]) for item in rows)
    return {
        "generatedAt": _utc_now_iso(),
        "reviewedPositiveSeedCount": len(positives),
        "minimumPositiveFramesForDetectorFix": MIN_POSITIVE_FRAMES_FOR_DETECTOR_FIX,
        "bucketCounts": dict(sorted(counts.items())),
        "reviewedPositiveFrames": rows,
    }


def build_reviewed_seed_refutation_matrix(
    *,
    truth_seed: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    negatives = _reviewed_negative_rows(truth_seed)
    rows = [
        {
            "reviewItemId": row.get("reviewItemId"),
            "candidateFrameId": row.get("candidateFrameId"),
            "frameIndex": row.get("frameIndex"),
            "reviewDecision": row.get("reviewDecision"),
            "refutationUse": "negative_only_do_not_use_as_positive",
        }
        for row in negatives
    ]
    return {
        "generatedAt": _utc_now_iso(),
        "rejectedSeedCount": len(rows),
        "rejectedSeedsReusedAsPositiveEvidence": False,
        "overlayDecisionCounts": _overlay_counts(overlay),
        "rejectedSeedRows": rows,
    }


def _dominant_bucket(matrix: dict[str, Any]) -> tuple[str, int]:
    counts = {str(key): _safe_int(value) for key, value in dict(matrix.get("bucketCounts") or {}).items()}
    if not counts:
        return BUCKET_EVIDENCE_TOO_SPARSE, 0
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]


def _next_family_for_bucket(bucket: str) -> str:
    if bucket == BUCKET_EVIDENCE_TOO_SPARSE:
        return NEXT_GOLD_TRUTH_REFUTED
    if bucket == BUCKET_NOT_GENERATED:
        return NEXT_SOURCE_MANIFEST_REFRESH
    if bucket in {BUCKET_COLLAPSED_NOT_SELECTED, BUCKET_SELECTED_NOT_ACCEPTED, BUCKET_ALREADY_ACCEPTED_SPARSE}:
        return NEXT_REVIEWED_PROFILE
    return NEXT_MANUAL_REVIEW_EXPANSION


def build_decision_matrix(
    *,
    positive_matrix: dict[str, Any],
    refutation_matrix: dict[str, Any],
) -> dict[str, Any]:
    dominant_bucket, dominant_count = _dominant_bucket(positive_matrix)
    positive_count = _safe_int(positive_matrix.get("reviewedPositiveSeedCount"), 0)
    rejected_count = _safe_int(refutation_matrix.get("rejectedSeedCount"), 0)
    weak_reasons: list[str] = []
    if positive_count < MIN_POSITIVE_FRAMES_FOR_DETECTOR_FIX:
        weak_reasons.append("reviewed_positive_seed_count_below_detector_fix_floor")
    if rejected_count > positive_count:
        weak_reasons.append("bootstrap_seed_surface_mostly_refuted_by_review")
    return {
        "goalAchieved": dominant_bucket != "",
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": _next_family_for_bucket(dominant_bucket),
        "nextRecommendedBatch": _next_family_for_bucket(dominant_bucket),
        "successfulApproach": "A_reviewed_truth_followthrough_diagnosis",
        "weakEvidenceReasons": weak_reasons,
        "rationale": (
            "Reviewed-positive truth is too sparse for a detector-side profile."
            if dominant_bucket == BUCKET_EVIDENCE_TOO_SPARSE
            else "Reviewed-positive truth names a concrete follow-through family."
        ),
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed Follow-Through Selection Fix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- reviewedPositiveSeedCount: {summary.get('reviewedPositiveSeedCount')}",
            f"- reviewedNegativeSeedCount: {summary.get('reviewedNegativeSeedCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_reviewed_followthrough_selection_fix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    manual_resolution_root: Path = DEFAULT_MANUAL_RESOLUTION_ROOT,
    manual_review_root: Path = DEFAULT_MANUAL_REVIEW_ROOT,
    followthrough_root: Path = DEFAULT_FOLLOWTHROUGH_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    runtime_default_path: Path = DEFAULT_RUNTIME_DEFAULT_PATH,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    truth_seed = _load_json_dict(Path(manual_resolution_root) / "reviewed_followthrough_truth_seed.json")
    overlay = _load_json_dict(Path(manual_review_root) / "reviewed_label_overlay.json")
    funnel_audit = _load_optional_json_dict(Path(followthrough_root) / "profile_selection_funnel_audit.json")
    followthrough_summary = _load_optional_json_dict(
        Path(followthrough_root) / "proposal_selection_followthrough_summary.json"
    )
    retention_summary = _load_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(Path(suite_root) / "suite_summary.json")

    followthrough_evidence = build_followthrough_evidence(
        profile_selection_funnel_audit=funnel_audit,
        proposal_followthrough_summary=followthrough_summary,
    )
    positive_matrix = build_reviewed_positive_followthrough_matrix(
        truth_seed=truth_seed,
        followthrough_evidence=followthrough_evidence,
    )
    refutation_matrix = build_reviewed_seed_refutation_matrix(
        truth_seed=truth_seed,
        overlay=overlay,
    )
    decision = build_decision_matrix(
        positive_matrix=positive_matrix,
        refutation_matrix=refutation_matrix,
    )
    positive_count = _safe_int(positive_matrix.get("reviewedPositiveSeedCount"), 0)
    negative_count = _safe_int(refutation_matrix.get("rejectedSeedCount"), 0)
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": "succeeded" if decision["goalAchieved"] else "in_progress",
        "truthStatus": truth_seed.get("truthStatus"),
        "reviewedPositiveSeedCount": positive_count,
        "reviewedNegativeSeedCount": negative_count,
        "reviewedPositiveFrames": [
            row.get("frameIndex") for row in _list_dicts(positive_matrix.get("reviewedPositiveFrames"))
        ],
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
        "followthroughEvidence": followthrough_evidence,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
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
            "reviewedFollowthroughSelectionSummaryPath": str(
                output_root / "reviewed_followthrough_selection_summary.json"
            ),
            "reviewedPositiveFollowthroughMatrixPath": str(
                output_root / "reviewed_positive_followthrough_matrix.json"
            ),
            "reviewedSeedRefutationMatrixPath": str(output_root / "reviewed_seed_refutation_matrix.json"),
        },
    }

    _ = runtime_default_path, source_manifest_path
    _write_json(output_root / "reviewed_followthrough_selection_summary.json", summary)
    _write_json(output_root / "reviewed_positive_followthrough_matrix.json", positive_matrix)
    _write_json(output_root / "reviewed_seed_refutation_matrix.json", refutation_matrix)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    return {
        "summary": summary,
        "reviewedPositiveFollowthroughMatrix": positive_matrix,
        "reviewedSeedRefutationMatrix": refutation_matrix,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manual-resolution-root", type=Path, default=DEFAULT_MANUAL_RESOLUTION_ROOT)
    parser.add_argument("--manual-review-root", type=Path, default=DEFAULT_MANUAL_REVIEW_ROOT)
    parser.add_argument("--followthrough-root", type=Path, default=DEFAULT_FOLLOWTHROUGH_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--runtime-default-path", type=Path, default=DEFAULT_RUNTIME_DEFAULT_PATH)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_SOURCE_MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_reviewed_followthrough_selection_fix(
        output_root=args.output_root,
        manual_resolution_root=args.manual_resolution_root,
        manual_review_root=args.manual_review_root,
        followthrough_root=args.followthrough_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        runtime_default_path=args.runtime_default_path,
        source_manifest_path=args.source_manifest_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
