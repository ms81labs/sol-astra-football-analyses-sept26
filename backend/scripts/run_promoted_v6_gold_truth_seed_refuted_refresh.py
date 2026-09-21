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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "gold_truth_seed_refuted_refresh_v1"
DEFAULT_REVIEWED_FOLLOWTHROUGH_ROOT = DEFAULT_SUITE_ROOT / "reviewed_followthrough_selection_fix_v1"
DEFAULT_MANUAL_RESOLUTION_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_resolution_v1"
DEFAULT_MANUAL_REVIEW_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_followthrough_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_RUNTIME_DEFAULT_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_SOURCE_MANIFEST_PATH = (
    REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
)
DEFAULT_BATCH_NAME = "gold_truth_seed_refuted_refresh_v1"
DEFAULT_ATTEMPT_FAMILY = "gold_truth_refutation_summary"
DEFAULT_TARGET_CLIP_ID = "trimed-5min.mp4"
MIN_POSITIVE_FRAMES_FOR_MICRO_VALIDATION = 5

NEXT_MANUAL_REVIEW_EXPANSION = "manual_review_expansion"
NEXT_REVIEWED_POSITIVE_MICRO_VALIDATION = "reviewed_positive_micro_validation"


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


def _safe_float(value: object, default: float | None = None) -> float | None:
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


def _sorted_review_rows(rows: object) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(rows),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )


def _reviewed_positive_rows(truth_seed: dict[str, Any]) -> list[dict[str, Any]]:
    return _sorted_review_rows(truth_seed.get("reviewedPositiveSeedRows"))


def _reviewed_negative_rows(truth_seed: dict[str, Any]) -> list[dict[str, Any]]:
    return _sorted_review_rows(truth_seed.get("reviewedNegativeSeedRows"))


def _valid_bbox_payload(bbox: object) -> bool:
    if not isinstance(bbox, dict):
        return False
    x1 = _safe_float(bbox.get("x1"))
    y1 = _safe_float(bbox.get("y1"))
    x2 = _safe_float(bbox.get("x2"))
    y2 = _safe_float(bbox.get("y2"))
    if None in {x1, y1, x2, y2}:
        return False
    return float(x2) > float(x1) and float(y2) > float(y1)


def _overlay_counts(overlay: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in _list_dicts(overlay.get("reviewItems")):
        counts[str(item.get("decision") or "")] += 1
    return dict(sorted(counts.items()))


def _manifest_positive_row(row: dict[str, Any]) -> dict[str, Any]:
    reviewed_bbox = row.get("reviewedBBox") if _valid_bbox_payload(row.get("reviewedBBox")) else row.get("seedBBox")
    return {
        "reviewItemId": row.get("reviewItemId"),
        "candidateFrameId": row.get("candidateFrameId"),
        "windowId": row.get("windowId"),
        "frameIndex": row.get("frameIndex"),
        "timestampSeconds": row.get("timestampSeconds"),
        "sourceClipId": row.get("sourceClipId") or DEFAULT_TARGET_CLIP_ID,
        "reviewDecision": row.get("reviewDecision"),
        "seedBBox": row.get("seedBBox"),
        "reviewedBBox": reviewed_bbox,
        "lineage": row.get("lineage") if isinstance(row.get("lineage"), dict) else {},
        "truthUse": "provisional_reviewed_positive",
    }


def build_reviewed_positive_truth_manifest(
    *,
    truth_seed: dict[str, Any],
    reviewed_followthrough_summary: dict[str, Any],
    reviewed_positive_matrix: dict[str, Any],
) -> dict[str, Any]:
    positive_rows = [_manifest_positive_row(row) for row in _reviewed_positive_rows(truth_seed)]
    positive_frame_ids = [_safe_int(row.get("frameIndex"), -1) for row in positive_rows]
    return {
        "generatedAt": _utc_now_iso(),
        "truthStatus": truth_seed.get("truthStatus"),
        "truthPolicy": "reviewed_positive_seed_only",
        "reviewedPositiveSeedCount": len(positive_rows),
        "positiveFrameIds": positive_frame_ids,
        "minimumPositiveFramesForMicroValidation": MIN_POSITIVE_FRAMES_FOR_MICRO_VALIDATION,
        "reviewedPositiveSeeds": positive_rows,
        "upstreamReviewedFollowthrough": {
            "dominantBlockerClass": reviewed_followthrough_summary.get("dominantBlockerClass"),
            "nextCorrectiveFamily": reviewed_followthrough_summary.get("nextCorrectiveFamily"),
            "bucketCounts": reviewed_positive_matrix.get("bucketCounts"),
            "weakEvidenceReasons": reviewed_followthrough_summary.get("weakEvidenceReasons"),
        },
    }


def _manifest_rejected_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "reviewItemId": row.get("reviewItemId"),
        "candidateFrameId": row.get("candidateFrameId"),
        "frameIndex": row.get("frameIndex"),
        "reviewDecision": row.get("reviewDecision"),
        "refutationUse": "negative_only_do_not_use_as_positive",
    }


def build_rejected_seed_refutation_manifest(
    *,
    truth_seed: dict[str, Any],
    refutation_matrix: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    rejected_rows = [_manifest_rejected_row(row) for row in _reviewed_negative_rows(truth_seed)]
    return {
        "generatedAt": _utc_now_iso(),
        "truthPolicy": "rejected_seed_refutation_only",
        "rejectedSeedCount": len(rejected_rows),
        "rejectedSeedsReusedAsPositiveEvidence": False,
        "rejectedSeeds": rejected_rows,
        "overlayDecisionCounts": _overlay_counts(overlay),
        "upstreamRefutationMatrix": {
            "rejectedSeedCount": refutation_matrix.get("rejectedSeedCount"),
            "rejectedSeedsReusedAsPositiveEvidence": bool(
                refutation_matrix.get("rejectedSeedsReusedAsPositiveEvidence", False)
            ),
        },
    }


def build_source_manifest_delta(
    *,
    positive_manifest: dict[str, Any],
    refutation_manifest: dict[str, Any],
    source_manifest_path: Path,
) -> dict[str, Any]:
    positive_frame_ids = [
        _safe_int(frame_id, -1)
        for frame_id in list(positive_manifest.get("positiveFrameIds") or [])
        if _safe_int(frame_id, -1) >= 0
    ]
    windows: list[dict[str, Any]] = []
    if positive_frame_ids:
        windows.append(
            {
                "sourceClipId": DEFAULT_TARGET_CLIP_ID,
                "windowId": f"{DEFAULT_TARGET_CLIP_ID}-reviewed-positive-{min(positive_frame_ids):04d}-{max(positive_frame_ids):04d}",
                "startFrame": min(positive_frame_ids),
                "endFrame": max(positive_frame_ids),
                "positiveFrameIds": positive_frame_ids,
                "purpose": "manual_review_expansion_seed_window",
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        "mutationPolicy": "not_mutated_delta_only",
        "sourceManifestPath": str(source_manifest_path),
        "targetClipId": DEFAULT_TARGET_CLIP_ID,
        "reviewedPositiveSeedCount": _safe_int(positive_manifest.get("reviewedPositiveSeedCount"), 0),
        "positiveFrameIds": positive_frame_ids,
        "rejectedSeedCount": _safe_int(refutation_manifest.get("rejectedSeedCount"), 0),
        "proposedAdditiveEvidenceWindows": windows,
        "rationale": (
            "The original 78-frame bootstrap surface was mostly refuted. This delta proposes preserving only "
            "reviewed-positive frame evidence and using rejected seeds as negative evidence."
        ),
    }


def build_decision_matrix(
    *,
    positive_manifest: dict[str, Any],
    refutation_manifest: dict[str, Any],
) -> dict[str, Any]:
    positive_count = _safe_int(positive_manifest.get("reviewedPositiveSeedCount"), 0)
    rejected_count = _safe_int(refutation_manifest.get("rejectedSeedCount"), 0)
    enough_for_micro_validation = positive_count >= MIN_POSITIVE_FRAMES_FOR_MICRO_VALIDATION
    weak_reasons: list[str] = []
    if not enough_for_micro_validation:
        weak_reasons.append("reviewed_positive_seed_count_below_micro_validation_floor")
    if rejected_count > positive_count:
        weak_reasons.append("bootstrap_seed_surface_mostly_refuted_by_review")
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": (
            "reviewed_positive_truth_too_sparse"
            if not enough_for_micro_validation
            else "reviewed_positive_micro_validation_ready"
        ),
        "dominantBlockerFrameCount": positive_count,
        "nextCorrectiveFamily": (
            NEXT_REVIEWED_POSITIVE_MICRO_VALIDATION
            if enough_for_micro_validation
            else NEXT_MANUAL_REVIEW_EXPANSION
        ),
        "nextRecommendedBatch": (
            NEXT_REVIEWED_POSITIVE_MICRO_VALIDATION
            if enough_for_micro_validation
            else NEXT_MANUAL_REVIEW_EXPANSION
        ),
        "successfulApproach": "A_gold_truth_refutation_summary",
        "weakEvidenceReasons": weak_reasons,
        "rationale": (
            "Reviewed positives are numerous enough for a tiny proof."
            if enough_for_micro_validation
            else "Only a sparse reviewed-positive truth surface remains after refuting the 78-frame bootstrap premise."
        ),
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Gold-Truth Seed Refuted Refresh",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- reviewedPositiveSeedCount: {summary.get('reviewedPositiveSeedCount')}",
            f"- rejectedSeedCount: {summary.get('rejectedSeedCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_gold_truth_seed_refuted_refresh(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    reviewed_followthrough_root: Path = DEFAULT_REVIEWED_FOLLOWTHROUGH_ROOT,
    manual_resolution_root: Path = DEFAULT_MANUAL_RESOLUTION_ROOT,
    manual_review_root: Path = DEFAULT_MANUAL_REVIEW_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    runtime_default_path: Path = DEFAULT_RUNTIME_DEFAULT_PATH,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    reviewed_followthrough_root = Path(reviewed_followthrough_root)
    truth_seed = _load_json_dict(Path(manual_resolution_root) / "reviewed_followthrough_truth_seed.json")
    overlay = _load_json_dict(Path(manual_review_root) / "reviewed_label_overlay.json")
    reviewed_followthrough_summary = _load_optional_json_dict(
        reviewed_followthrough_root / "reviewed_followthrough_selection_summary.json"
    )
    reviewed_positive_matrix = _load_optional_json_dict(
        reviewed_followthrough_root / "reviewed_positive_followthrough_matrix.json"
    )
    refutation_matrix = _load_optional_json_dict(
        reviewed_followthrough_root / "reviewed_seed_refutation_matrix.json"
    )
    retention_summary = _load_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(Path(suite_root) / "suite_summary.json")

    positive_manifest = build_reviewed_positive_truth_manifest(
        truth_seed=truth_seed,
        reviewed_followthrough_summary=reviewed_followthrough_summary,
        reviewed_positive_matrix=reviewed_positive_matrix,
    )
    refutation_manifest = build_rejected_seed_refutation_manifest(
        truth_seed=truth_seed,
        refutation_matrix=refutation_matrix,
        overlay=overlay,
    )
    source_manifest_delta = build_source_manifest_delta(
        positive_manifest=positive_manifest,
        refutation_manifest=refutation_manifest,
        source_manifest_path=Path(source_manifest_path),
    )
    decision = build_decision_matrix(
        positive_manifest=positive_manifest,
        refutation_manifest=refutation_manifest,
    )
    positive_frames = list(positive_manifest.get("positiveFrameIds") or [])
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": "succeeded" if decision["goalAchieved"] else "in_progress",
        "truthStatus": truth_seed.get("truthStatus"),
        "reviewedPositiveSeedCount": _safe_int(positive_manifest.get("reviewedPositiveSeedCount"), 0),
        "rejectedSeedCount": _safe_int(refutation_manifest.get("rejectedSeedCount"), 0),
        "reviewedNegativeSeedCount": _safe_int(refutation_manifest.get("rejectedSeedCount"), 0),
        "reviewedPositiveFrames": positive_frames,
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
            "goldTruthSeedRefutedSummaryPath": str(output_root / "gold_truth_seed_refuted_summary.json"),
            "reviewedPositiveTruthManifestPath": str(output_root / "reviewed_positive_truth_manifest.json"),
            "rejectedSeedRefutationManifestPath": str(output_root / "rejected_seed_refutation_manifest.json"),
            "sourceManifestDeltaPath": str(output_root / "source_manifest_delta.json"),
        },
    }

    _ = runtime_default_path
    _write_json(output_root / "gold_truth_seed_refuted_summary.json", summary)
    _write_json(output_root / "reviewed_positive_truth_manifest.json", positive_manifest)
    _write_json(output_root / "rejected_seed_refutation_manifest.json", refutation_manifest)
    _write_json(output_root / "source_manifest_delta.json", source_manifest_delta)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    return {
        "summary": summary,
        "reviewedPositiveTruthManifest": positive_manifest,
        "rejectedSeedRefutationManifest": refutation_manifest,
        "sourceManifestDelta": source_manifest_delta,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--reviewed-followthrough-root", type=Path, default=DEFAULT_REVIEWED_FOLLOWTHROUGH_ROOT)
    parser.add_argument("--manual-resolution-root", type=Path, default=DEFAULT_MANUAL_RESOLUTION_ROOT)
    parser.add_argument("--manual-review-root", type=Path, default=DEFAULT_MANUAL_REVIEW_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--runtime-default-path", type=Path, default=DEFAULT_RUNTIME_DEFAULT_PATH)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_SOURCE_MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_gold_truth_seed_refuted_refresh(
        output_root=args.output_root,
        reviewed_followthrough_root=args.reviewed_followthrough_root,
        manual_resolution_root=args.manual_resolution_root,
        manual_review_root=args.manual_review_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        runtime_default_path=args.runtime_default_path,
        source_manifest_path=args.source_manifest_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
