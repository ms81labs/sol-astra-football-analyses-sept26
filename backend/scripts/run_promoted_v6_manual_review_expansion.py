from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "manual_review_expansion_v1"
DEFAULT_REFUTED_ROOT = DEFAULT_SUITE_ROOT / "gold_truth_seed_refuted_refresh_v1"
DEFAULT_PRIOR_REVIEW_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_followthrough_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"
DEFAULT_RUNTIME_DEFAULT_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_SOURCE_MANIFEST_PATH = (
    REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
)
DEFAULT_BATCH_NAME = "manual_review_expansion_v1"
DEFAULT_TARGET_CLIP_ID = "trimed-5min.mp4"
DEFAULT_EXPANSION_START_FRAME = 240
DEFAULT_EXPANSION_END_FRAME = 320
DEFAULT_EXPANSION_STEP = 5


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


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


def _stable_id(*parts: object) -> str:
    joined = "::".join(str(part) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:20]


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


def _lineage_complete(lineage: object) -> bool:
    if not isinstance(lineage, dict):
        return False
    required = {
        "baselineBallTruthLayersPath",
        "baselineSelectedClusterDeltaPath",
        "promotedBallTruthLayersPath",
        "promotedSelectedClusterDeltaPath",
    }
    return required.issubset({str(key) for key in lineage.keys()})


def _positive_seed_rows(positive_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(positive_manifest.get("reviewedPositiveSeeds")),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )


def _rejected_seed_rows(refutation_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(refutation_manifest.get("rejectedSeeds")),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )


def _expansion_frame_ids(
    *,
    start_frame: int = DEFAULT_EXPANSION_START_FRAME,
    end_frame: int = DEFAULT_EXPANSION_END_FRAME,
    step: int = DEFAULT_EXPANSION_STEP,
) -> list[int]:
    return list(range(start_frame, end_frame + 1, step))


def _refuted_rows_by_frame(refutation_manifest: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in _rejected_seed_rows(refutation_manifest):
        by_frame.setdefault(_safe_int(row.get("frameIndex"), -1), []).append(row)
    return by_frame


def _positive_rows_by_frame(positive_manifest: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        _safe_int(row.get("frameIndex"), -1): row
        for row in _positive_seed_rows(positive_manifest)
        if _safe_int(row.get("frameIndex"), -1) >= 0
    }


def _review_item_for_frame(
    *,
    frame_id: int,
    positive_row: dict[str, Any] | None,
    refuted_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    timestamp_seconds = round(frame_id / 25.0, 3)
    if positive_row is not None:
        seed_bbox = positive_row.get("seedBBox")
        reviewed_bbox = positive_row.get("reviewedBBox") if _valid_bbox_payload(positive_row.get("reviewedBBox")) else seed_bbox
        lineage = positive_row.get("lineage") if isinstance(positive_row.get("lineage"), dict) else {}
        candidate_frame_id = str(positive_row.get("candidateFrameId") or f"reviewed-positive-{frame_id}")
        return {
            "reviewItemId": str(positive_row.get("reviewItemId") or _stable_id(frame_id, "positive_anchor")),
            "curationUnitId": positive_row.get("windowId"),
            "matchId": None,
            "sourceClipId": str(positive_row.get("sourceClipId") or DEFAULT_TARGET_CLIP_ID),
            "frameIndex": frame_id,
            "timestampSeconds": positive_row.get("timestampSeconds") or timestamp_seconds,
            "seedSource": "reviewed_positive_truth_manifest",
            "seedBBox": seed_bbox,
            "decision": "accept_seed",
            "reviewedBBox": reviewed_bbox,
            "notes": "Reviewed-positive anchor preserved from gold_truth_seed_refuted_refresh_v1.",
            "split": "manual_review_expansion",
            "fileStem": f"{DEFAULT_TARGET_CLIP_ID}__f{frame_id:06d}__{candidate_frame_id}",
            "candidateFrameId": candidate_frame_id,
            "windowId": positive_row.get("windowId"),
            "lineage": lineage,
            "lineageComplete": _lineage_complete(lineage),
            "truthUse": "positive_anchor",
            "refutedBBox": None,
            "refutedSeedRows": [],
        }
    refuted_bbox = None
    if refuted_rows:
        maybe_bbox = refuted_rows[0].get("seedBBox")
        if _valid_bbox_payload(maybe_bbox):
            refuted_bbox = maybe_bbox
    review_item_id = _stable_id(DEFAULT_TARGET_CLIP_ID, frame_id, "manual_review_expansion")
    return {
        "reviewItemId": review_item_id,
        "curationUnitId": f"{DEFAULT_TARGET_CLIP_ID}-manual-review-expansion-{DEFAULT_EXPANSION_START_FRAME:04d}-{DEFAULT_EXPANSION_END_FRAME:04d}",
        "matchId": None,
        "sourceClipId": DEFAULT_TARGET_CLIP_ID,
        "frameIndex": frame_id,
        "timestampSeconds": timestamp_seconds,
        "seedSource": "manual_review_expansion_context",
        "seedBBox": None,
        "decision": "pending_review",
        "reviewedBBox": None,
        "notes": "Review this expansion frame near the four positive anchors; do not infer labels from rejected seeds.",
        "split": "manual_review_expansion",
        "fileStem": f"{DEFAULT_TARGET_CLIP_ID}__f{frame_id:06d}__{review_item_id}",
        "candidateFrameId": f"manual-review-expansion-{frame_id}",
        "windowId": f"{DEFAULT_TARGET_CLIP_ID}-manual-review-expansion-{DEFAULT_EXPANSION_START_FRAME:04d}-{DEFAULT_EXPANSION_END_FRAME:04d}",
        "lineage": {},
        "lineageComplete": True,
        "truthUse": "pending_review_context",
        "refutedBBox": refuted_bbox,
        "refutedSeedRows": [
            {
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "frameIndex": row.get("frameIndex"),
                "reviewDecision": row.get("reviewDecision"),
                "refutationUse": "negative_only_do_not_use_as_positive",
            }
            for row in refuted_rows
        ],
    }


def build_expansion_review_items(
    *,
    positive_manifest: dict[str, Any],
    refutation_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    positives_by_frame = _positive_rows_by_frame(positive_manifest)
    refuted_by_frame = _refuted_rows_by_frame(refutation_manifest)
    return [
        _review_item_for_frame(
            frame_id=frame_id,
            positive_row=positives_by_frame.get(frame_id),
            refuted_rows=refuted_by_frame.get(frame_id, []),
        )
        for frame_id in _expansion_frame_ids()
    ]


def _overlay_counts(review_items: list[dict[str, Any]]) -> dict[str, int]:
    pending = sum(str(item.get("decision") or "") == "pending_review" for item in review_items)
    accepted = sum(str(item.get("decision") or "") == "accept_seed" for item in review_items)
    adjusted = sum(str(item.get("decision") or "") == "adjust_bbox" for item in review_items)
    rejected = sum(str(item.get("decision") or "") == "reject_seed" for item in review_items)
    hard_negative = sum(str(item.get("decision") or "") == "confirm_hard_negative" for item in review_items)
    lineage_complete = sum(bool(item.get("lineageComplete")) for item in review_items)
    return {
        "reviewItemCount": len(review_items),
        "pendingReviewCount": pending,
        "acceptedSeedCount": accepted,
        "adjustedBBoxCount": adjusted,
        "rejectedSeedCount": rejected,
        "confirmedHardNegativeCount": hard_negative,
        "reviewedPositiveCount": accepted + adjusted,
        "reviewedNegativeCount": rejected + hard_negative,
        "lineageCompleteCount": lineage_complete,
        "lineageIncompleteCount": len(review_items) - lineage_complete,
    }


def build_reviewed_label_overlay(review_items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = _overlay_counts(review_items)
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "reviewPurpose": "Expand reviewed-positive evidence around the sparse promoted-v6 follow-through truth surface.",
        **counts,
        "failingSourceReviewComplete": counts["pendingReviewCount"] == 0,
        "controlReviewComplete": True,
        "reviewItems": sorted(
            review_items,
            key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("reviewItemId") or "")),
        ),
    }


def build_expansion_manifest(review_items: list[dict[str, Any]]) -> dict[str, Any]:
    positive_frames = [
        _safe_int(item.get("frameIndex"), -1)
        for item in review_items
        if str(item.get("truthUse") or "") == "positive_anchor"
    ]
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "targetClipId": DEFAULT_TARGET_CLIP_ID,
        "expansionStartFrame": DEFAULT_EXPANSION_START_FRAME,
        "expansionEndFrame": DEFAULT_EXPANSION_END_FRAME,
        "expansionStep": DEFAULT_EXPANSION_STEP,
        "expansionFrameIds": _expansion_frame_ids(),
        "reviewedPositiveAnchorFrames": positive_frames,
        "reviewItemCount": len(review_items),
        "expansionItems": [
            {
                "reviewItemId": item.get("reviewItemId"),
                "candidateFrameId": item.get("candidateFrameId"),
                "frameIndex": item.get("frameIndex"),
                "decision": item.get("decision"),
                "truthUse": item.get("truthUse"),
                "hasRefutationContext": bool(item.get("refutedSeedRows")),
            }
            for item in sorted(review_items, key=lambda item: _safe_int(item.get("frameIndex"), -1))
        ],
    }


def build_refutation_guard_manifest(refutation_manifest: dict[str, Any]) -> dict[str, Any]:
    rejected_rows = [
        {
            "reviewItemId": row.get("reviewItemId"),
            "candidateFrameId": row.get("candidateFrameId"),
            "frameIndex": row.get("frameIndex"),
            "reviewDecision": row.get("reviewDecision"),
            "refutationUse": "negative_only_do_not_use_as_positive",
        }
        for row in _rejected_seed_rows(refutation_manifest)
    ]
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "rejectedSeedCount": len(rejected_rows),
        "rejectedSeedsReusedAsPositiveEvidence": False,
        "rejectedSeeds": rejected_rows,
        "policy": "Rejected bootstrap seeds may provide context/refutation only and must never become positive seedBBox evidence.",
    }


def _review_frame_manifest_item(
    item: dict[str, Any],
    *,
    image_path: Path | None,
    extracted: bool,
    error: str | None,
) -> dict[str, Any]:
    return {
        "reviewItemId": item.get("reviewItemId"),
        "candidateFrameId": item.get("candidateFrameId"),
        "windowId": item.get("windowId"),
        "sourceClipId": item.get("sourceClipId"),
        "frameIndex": item.get("frameIndex"),
        "timestampSeconds": item.get("timestampSeconds"),
        "fileStem": item.get("fileStem"),
        "seedBBox": item.get("seedBBox"),
        "reviewedBBox": item.get("reviewedBBox"),
        "refutedBBox": item.get("refutedBBox"),
        "imagePath": str(image_path) if image_path is not None else None,
        "imageExtracted": extracted,
        "imageExtractionError": error,
    }


def _extract_review_frames(
    *,
    review_items: list[dict[str, Any]],
    video_path: Path,
    output_root: Path,
) -> tuple[str, list[dict[str, Any]]]:
    frames_root = output_root / "review_frames"
    review_frames: list[dict[str, Any]] = []
    if not video_path.exists():
        for item in review_items:
            review_frames.append(_review_frame_manifest_item(item, image_path=None, extracted=False, error="video_missing"))
        return "json_only_no_video", review_frames
    try:
        import cv2  # type: ignore
    except ImportError:
        for item in review_items:
            review_frames.append(_review_frame_manifest_item(item, image_path=None, extracted=False, error="cv2_unavailable"))
        return "json_only_cv2_unavailable", review_frames

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        for item in review_items:
            review_frames.append(_review_frame_manifest_item(item, image_path=None, extracted=False, error="video_open_failed"))
        return "json_only_image_extraction_failed", review_frames

    frames_root.mkdir(parents=True, exist_ok=True)
    extracted_count = 0
    for item in review_items:
        frame_index = _safe_int(item.get("frameIndex"), -1)
        output_path = frames_root / f"{item['fileStem']}.jpg"
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            review_frames.append(
                _review_frame_manifest_item(item, image_path=None, extracted=False, error="frame_read_failed")
            )
            continue
        if not cv2.imwrite(str(output_path), frame):
            review_frames.append(
                _review_frame_manifest_item(item, image_path=None, extracted=False, error="frame_write_failed")
            )
            continue
        extracted_count += 1
        review_frames.append(_review_frame_manifest_item(item, image_path=output_path, extracted=True, error=None))
    capture.release()
    if extracted_count == len(review_items):
        return "images_extracted", review_frames
    if extracted_count > 0:
        return "partial_images_extracted", review_frames
    return "json_only_image_extraction_failed", review_frames


def build_decision_matrix(
    *,
    overlay_counts: dict[str, int],
    image_extraction_status: str,
    refutation_guard: dict[str, Any],
) -> dict[str, Any]:
    weak_reasons: list[str] = []
    if overlay_counts.get("reviewItemCount") != len(_expansion_frame_ids()):
        weak_reasons.append("expansion_review_item_count_mismatch")
    if overlay_counts.get("acceptedSeedCount") != 4:
        weak_reasons.append("reviewed_positive_anchor_count_mismatch")
    if overlay_counts.get("pendingReviewCount") != len(_expansion_frame_ids()) - 4:
        weak_reasons.append("pending_expansion_neighbor_count_mismatch")
    if overlay_counts.get("lineageIncompleteCount", 0) > 0:
        weak_reasons.append("lineage_incomplete_count_nonzero")
    if bool(refutation_guard.get("rejectedSeedsReusedAsPositiveEvidence")):
        weak_reasons.append("rejected_seeds_reused_as_positive_evidence")
    if _safe_int(refutation_guard.get("rejectedSeedCount"), 0) != 74:
        weak_reasons.append("rejected_seed_count_not_74")
    if weak_reasons:
        next_family = "manual_review_lineage_refresh" if "lineage_incomplete_count_nonzero" in weak_reasons else "manual_review_required"
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "successfulApproach": "C_manual_review_expansion_blocker",
            "nextCorrectiveFamily": next_family,
            "weakEvidenceReasons": weak_reasons,
            "rationale": "Manual review expansion package is incomplete and cannot safely advance.",
        }
    approach = (
        "A_reviewed_positive_window_expansion"
        if image_extraction_status in {"images_extracted", "partial_images_extracted"}
        else "B_nearby_candidate_context_expansion"
    )
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": False,
        "successfulApproach": approach,
        "nextCorrectiveFamily": "manual_review_pending",
        "weakEvidenceReasons": [],
        "rationale": "Expanded manual review package is ready; roadmap pauses until pending expansion decisions are resolved.",
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Manual Review Expansion",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- reviewItemCount: {summary.get('reviewItemCount')}",
            f"- acceptedSeedCount: {summary.get('acceptedSeedCount')}",
            f"- pendingReviewCount: {summary.get('pendingReviewCount')}",
            f"- rejectedSeedCount: {summary.get('rejectedSeedCount')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- imageExtractionStatus: {summary.get('imageExtractionStatus')}",
            "",
        ]
    )


def run_promoted_v6_manual_review_expansion(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    refuted_root: Path = DEFAULT_REFUTED_ROOT,
    prior_review_root: Path = DEFAULT_PRIOR_REVIEW_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    video_path: Path = DEFAULT_VIDEO_PATH,
    runtime_default_path: Path = DEFAULT_RUNTIME_DEFAULT_PATH,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    refuted_root = Path(refuted_root)
    positive_manifest = _load_json_dict(refuted_root / "reviewed_positive_truth_manifest.json")
    refutation_manifest = _load_json_dict(refuted_root / "rejected_seed_refutation_manifest.json")
    retention_summary = _load_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    suite_summary = _load_json_dict(Path(suite_root) / "suite_summary.json")
    prior_overlay = _load_json_dict(Path(prior_review_root) / "reviewed_label_overlay.json")
    prior_frame_manifest = _load_json_dict(Path(prior_review_root) / "review_frame_manifest.json")

    review_items = build_expansion_review_items(
        positive_manifest=positive_manifest,
        refutation_manifest=refutation_manifest,
    )
    reviewed_overlay = build_reviewed_label_overlay(review_items)
    expansion_manifest = build_expansion_manifest(review_items)
    refutation_guard = build_refutation_guard_manifest(refutation_manifest)
    image_extraction_status, review_frames = _extract_review_frames(
        review_items=review_items,
        video_path=Path(video_path),
        output_root=output_root,
    )
    overlay_counts = {
        key: _safe_int(reviewed_overlay.get(key), 0)
        for key in (
            "reviewItemCount",
            "pendingReviewCount",
            "acceptedSeedCount",
            "adjustedBBoxCount",
            "rejectedSeedCount",
            "confirmedHardNegativeCount",
            "reviewedPositiveCount",
            "reviewedNegativeCount",
            "lineageCompleteCount",
            "lineageIncompleteCount",
        )
    }
    decision = build_decision_matrix(
        overlay_counts=overlay_counts,
        image_extraction_status=image_extraction_status,
        refutation_guard=refutation_guard,
    )
    batch_status = "manual_review_pending" if decision["goalAchieved"] else "blocked"
    review_frame_manifest = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "videoPath": str(video_path),
        "imageExtractionStatus": image_extraction_status,
        "reviewFrameCount": len(review_frames),
        "extractedImageCount": sum(bool(item.get("imageExtracted")) for item in review_frames),
        "reviewFrames": sorted(
            review_frames,
            key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("reviewItemId") or "")),
        ),
    }
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "activeQueueItem": "manual_review_expansion",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "reviewed_positive_window_expansion",
        "batchStatus": batch_status,
        "expansionFrameIds": _expansion_frame_ids(),
        "reviewedPositiveAnchorFrames": expansion_manifest["reviewedPositiveAnchorFrames"],
        "inputReviewedPositiveSeedCount": _safe_int(positive_manifest.get("reviewedPositiveSeedCount"), 0),
        "inputRejectedSeedCount": _safe_int(refutation_manifest.get("rejectedSeedCount"), 0),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "imageExtractionStatus": image_extraction_status,
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
        "priorReviewTruth": {
            "reviewItemCount": prior_overlay.get("reviewItemCount"),
            "acceptedSeedCount": prior_overlay.get("acceptedSeedCount"),
            "rejectedSeedCount": prior_overlay.get("rejectedSeedCount"),
            "reviewFrameCount": prior_frame_manifest.get("reviewFrameCount"),
        },
        **overlay_counts,
        "rejectedRefutationSeedCount": _safe_int(refutation_guard.get("rejectedSeedCount"), 0),
        **decision,
    }
    batch_outcome = {
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "approachFamily": "reviewed_positive_window_expansion",
        "batchStatus": batch_status,
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "artifacts": {
            "manualReviewExpansionSummaryPath": str(output_root / "manual_review_expansion_summary.json"),
            "reviewedPositiveWindowExpansionManifestPath": str(
                output_root / "reviewed_positive_window_expansion_manifest.json"
            ),
            "reviewedLabelOverlayPath": str(output_root / "reviewed_label_overlay.json"),
            "reviewFrameManifestPath": str(output_root / "review_frame_manifest.json"),
            "refutationGuardManifestPath": str(output_root / "refutation_guard_manifest.json"),
        },
    }

    _write_json(output_root / "manual_review_expansion_summary.json", summary)
    _write_json(output_root / "reviewed_positive_window_expansion_manifest.json", expansion_manifest)
    _write_json(output_root / "reviewed_label_overlay.json", reviewed_overlay)
    _write_json(output_root / "review_frame_manifest.json", review_frame_manifest)
    _write_json(output_root / "refutation_guard_manifest.json", refutation_guard)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    if not decision["goalAchieved"]:
        _write_json(
            output_root / "blocker_summary.json",
            {
                **summary,
                "blockerSummaryType": "manual_review_expansion_blocked",
            },
        )

    _ = runtime_default_path, source_manifest_path
    return {
        "summary": summary,
        "reviewedPositiveWindowExpansionManifest": expansion_manifest,
        "reviewedLabelOverlay": reviewed_overlay,
        "reviewFrameManifest": review_frame_manifest,
        "refutationGuardManifest": refutation_guard,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--refuted-root", type=Path, default=DEFAULT_REFUTED_ROOT)
    parser.add_argument("--prior-review-root", type=Path, default=DEFAULT_PRIOR_REVIEW_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--runtime-default-path", type=Path, default=DEFAULT_RUNTIME_DEFAULT_PATH)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_SOURCE_MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_manual_review_expansion(
        output_root=args.output_root,
        refuted_root=args.refuted_root,
        prior_review_root=args.prior_review_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        video_path=args.video_path,
        runtime_default_path=args.runtime_default_path,
        source_manifest_path=args.source_manifest_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
