from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_followthrough_v1"
DEFAULT_FOLLOWTHROUGH_ROOT = DEFAULT_SUITE_ROOT / "proposal_selection_followthrough_fix_v1"
DEFAULT_GOLD_TRUTH_ROOT = (
    DEFAULT_SUITE_ROOT
    / "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
    / "gold_truth_bootstrap_attempt_v1"
)
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"
DEFAULT_RUNTIME_DEFAULT_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_SOURCE_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
DEFAULT_BATCH_NAME = "promoted_v6_manual_review_followthrough_v1"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
EXPECTED_REVIEW_ITEM_COUNT = 78


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


def _safe_float(value: object, default: float | None = 0.0) -> float | None:
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
    x1 = _safe_float(bbox.get("x1"), None)
    y1 = _safe_float(bbox.get("y1"), None)
    x2 = _safe_float(bbox.get("x2"), None)
    y2 = _safe_float(bbox.get("y2"), None)
    if None in {x1, y1, x2, y2}:
        return False
    return float(x2) > float(x1) and float(y2) > float(y1)


def _bbox_from_row(row: object) -> dict[str, float] | None:
    if not isinstance(row, dict):
        return None
    bbox = {
        "x1": _safe_float(row.get("Source_X1"), None),
        "y1": _safe_float(row.get("Source_Y1"), None),
        "x2": _safe_float(row.get("Source_X2"), None),
        "y2": _safe_float(row.get("Source_Y2"), None),
    }
    if any(value is None for value in bbox.values()):
        return None
    normalized = {key: float(value) for key, value in bbox.items() if value is not None}
    return normalized if _valid_bbox_payload(normalized) else None


def _candidate_frame_lookup(candidate_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(frame.get("candidateFrameId")): frame
        for frame in _list_dicts(candidate_manifest.get("candidateFrames"))
        if frame.get("candidateFrameId") is not None
    }


def _seed_row_lookup(seed_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("candidateFrameId")): row
        for row in _list_dicts(seed_payload.get("acceptedBallSeedRows"))
        if row.get("candidateFrameId") is not None
    }


def _overlay_items(followthrough_overlay: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(followthrough_overlay.get("reviewItems")),
        key=lambda item: (_safe_int(item.get("frameId"), -1), str(item.get("candidateFrameId") or "")),
    )


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


def _build_repo_native_review_items(
    *,
    followthrough_overlay: dict[str, Any],
    blocker_summary: dict[str, Any],
    candidate_manifest: dict[str, Any],
    seed_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate_lookup = _candidate_frame_lookup(candidate_manifest)
    seed_lookup = _seed_row_lookup(seed_payload)
    dominant_blocker = str(blocker_summary.get("dominantBlockerClass") or "")
    review_items = []
    for overlay_item in _overlay_items(followthrough_overlay):
        candidate_frame_id = str(overlay_item.get("candidateFrameId") or "")
        candidate_frame = candidate_lookup.get(candidate_frame_id, {})
        seed_row = seed_lookup.get(candidate_frame_id, {})
        frame_index = _safe_int(candidate_frame.get("frameId"), _safe_int(overlay_item.get("frameId"), -1))
        source_clip_id = str(candidate_frame.get("sourceClipId") or DEFAULT_FAILING_SOURCE_CLIP_ID)
        window_id = str(candidate_frame.get("windowId") or overlay_item.get("windowId") or "")
        seed_bbox = candidate_frame.get("seedBBox")
        if not _valid_bbox_payload(seed_bbox):
            seed_bbox = _bbox_from_row(seed_row.get("row"))
        lineage = candidate_frame.get("lineage")
        if not isinstance(lineage, dict) or not lineage:
            lineage = seed_row.get("lineage")
        if not isinstance(lineage, dict):
            lineage = {}
        file_stem = f"{source_clip_id}__f{frame_index:06d}__{candidate_frame_id}"
        review_items.append(
            {
                "reviewItemId": _stable_id(candidate_frame_id, frame_index, "manual_followthrough_review"),
                "curationUnitId": window_id,
                "matchId": None,
                "sourceClipId": source_clip_id,
                "frameIndex": frame_index,
                "timestampSeconds": candidate_frame.get("timestampSeconds"),
                "seedSource": "baseline_current_accepted_ball",
                "seedBBox": seed_bbox,
                "decision": "pending_review",
                "reviewedBBox": None,
                "notes": (
                    f"[{DEFAULT_BATCH_NAME}: {dominant_blocker}] Review whether the seeded candidate "
                    "should become selected/accepted follow-through evidence."
                ),
                "split": "manual_review_followthrough",
                "fileStem": file_stem,
                "candidateFrameId": candidate_frame_id,
                "windowId": window_id,
                "gapClass": overlay_item.get("gapClass") or dominant_blocker,
                "lineage": lineage,
                "lineageComplete": _lineage_complete(lineage),
                "promotedSignalSources": candidate_frame.get("promotedSignalSources") or [],
            }
        )
    return review_items


def _overlay_counts(review_items: list[dict[str, Any]]) -> dict[str, int]:
    pending = sum(str(item.get("decision") or "") == "pending_review" for item in review_items)
    reviewed_positive = sum(
        str(item.get("decision") or "") in {"accept_seed", "adjust_bbox"} for item in review_items
    )
    reviewed_negative = sum(
        str(item.get("decision") or "") in {"reject_seed", "confirm_hard_negative"} for item in review_items
    )
    lineage_complete = sum(bool(item.get("lineageComplete")) for item in review_items)
    valid_seed_bbox = sum(_valid_bbox_payload(item.get("seedBBox")) for item in review_items)
    return {
        "reviewItemCount": len(review_items),
        "pendingReviewCount": pending,
        "reviewedPositiveCount": reviewed_positive,
        "reviewedNegativeCount": reviewed_negative,
        "lineageCompleteCount": lineage_complete,
        "validSeedBBoxCount": valid_seed_bbox,
        "missingSeedBBoxCount": len(review_items) - valid_seed_bbox,
        "lineageIncompleteCount": len(review_items) - lineage_complete,
    }


def build_reviewed_label_overlay(review_items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = _overlay_counts(review_items)
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "reviewPurpose": "Resolve promoted-v6 proposal follow-through frames that generated/collapsed candidates but selected zero frames.",
        **counts,
        "failingSourceReviewComplete": counts["pendingReviewCount"] == 0,
        "controlReviewComplete": True,
        "reviewItems": sorted(review_items, key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("candidateFrameId") or ""))),
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
        "imagePath": str(image_path) if image_path is not None else None,
        "imageExtracted": extracted,
        "imageExtractionError": error,
    }


def build_decision_matrix(
    *,
    overlay_counts: dict[str, int],
    image_extraction_status: str,
) -> dict[str, Any]:
    weak_reasons: list[str] = []
    if overlay_counts.get("reviewItemCount") != EXPECTED_REVIEW_ITEM_COUNT:
        weak_reasons.append("review_item_count_not_78")
    if overlay_counts.get("pendingReviewCount") != overlay_counts.get("reviewItemCount"):
        weak_reasons.append("non_pending_review_decisions_present")
    if overlay_counts.get("missingSeedBBoxCount", 0) > 0:
        weak_reasons.append("missing_seed_bbox_count_nonzero")
    if overlay_counts.get("lineageIncompleteCount", 0) > 0:
        weak_reasons.append("lineage_incomplete_count_nonzero")
    if weak_reasons:
        next_family = "manual_review_lineage_refresh" if "lineage_incomplete_count_nonzero" in weak_reasons else "manual_review_required"
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "successfulApproach": "C_manual_review_blocker_fallback",
            "nextCorrectiveFamily": next_family,
            "weakEvidenceReasons": weak_reasons,
            "rationale": "Manual review package is incomplete and needs evidence refresh before human review.",
        }
    approach = (
        "A_review_package_generation"
        if image_extraction_status in {"images_extracted", "partial_images_extracted"}
        else "B_json_only_review_package_fallback"
    )
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": False,
        "successfulApproach": approach,
        "nextCorrectiveFamily": "manual_review_pending",
        "weakEvidenceReasons": [],
        "rationale": "Manual review package is ready; roadmap pauses until reviewed_label_overlay.json decisions are resolved.",
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Promoted V6 Manual Review Follow-Through",
            "",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewItemCount: {summary.get('reviewItemCount')}",
            f"- pendingReviewCount: {summary.get('pendingReviewCount')}",
            f"- lineageCompleteCount: {summary.get('lineageCompleteCount')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- imageExtractionStatus: {summary.get('imageExtractionStatus')}",
            "",
        ]
    )


def run_promoted_v6_manual_review_followthrough_batch(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    followthrough_root: Path = DEFAULT_FOLLOWTHROUGH_ROOT,
    gold_truth_root: Path = DEFAULT_GOLD_TRUTH_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    video_path: Path = DEFAULT_VIDEO_PATH,
    runtime_default_path: Path = DEFAULT_RUNTIME_DEFAULT_PATH,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    followthrough_root = Path(followthrough_root)
    gold_truth_root = Path(gold_truth_root)
    promoted_proof_root = Path(promoted_proof_root)
    video_path = Path(video_path)

    followthrough_overlay = _load_json_dict(followthrough_root / "manual_review_followthrough_overlay.json")
    blocker_summary = _load_json_dict(followthrough_root / "blocker_summary.json")
    candidate_manifest = _load_json_dict(gold_truth_root / "candidate_frame_truth_manifest.json")
    seed_payload = _load_json_dict(gold_truth_root / "accepted_controlled_truth_seed.json")
    recovery_profile_matrix = _load_optional_json_dict(promoted_proof_root / "recovery_profile_matrix.json")
    proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")

    review_items = _build_repo_native_review_items(
        followthrough_overlay=followthrough_overlay,
        blocker_summary=blocker_summary,
        candidate_manifest=candidate_manifest,
        seed_payload=seed_payload,
    )
    reviewed_overlay = build_reviewed_label_overlay(review_items)
    overlay_counts = {key: _safe_int(reviewed_overlay.get(key), 0) for key in (
        "reviewItemCount",
        "pendingReviewCount",
        "reviewedPositiveCount",
        "reviewedNegativeCount",
        "lineageCompleteCount",
        "validSeedBBoxCount",
        "missingSeedBBoxCount",
        "lineageIncompleteCount",
    )}
    image_extraction_status, review_frames = _extract_review_frames(
        review_items=review_items,
        video_path=video_path,
        output_root=output_root,
    )
    decision = build_decision_matrix(
        overlay_counts=overlay_counts,
        image_extraction_status=image_extraction_status,
    )
    batch_status = "manual_review_pending" if decision["goalAchieved"] else "blocked"

    review_frame_manifest = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "videoPath": str(video_path),
        "imageExtractionStatus": image_extraction_status,
        "reviewFrameCount": len(review_frames),
        "extractedImageCount": sum(bool(item.get("imageExtracted")) for item in review_frames),
        "reviewFrames": sorted(review_frames, key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("candidateFrameId") or ""))),
    }
    review_bundle_manifest = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "reviewedLabelOverlayPath": str(output_root / "reviewed_label_overlay.json"),
        "reviewFrameManifestPath": str(output_root / "review_frame_manifest.json"),
        "reviewFramesRoot": str(output_root / "review_frames"),
        "sourceVideoPath": str(video_path),
        "reviewerInstructions": [
            "Resolve every pending_review item in reviewed_label_overlay.json.",
            "Use accept_seed only when the seedBBox marks the ball well enough for follow-through truth.",
            "Use adjust_bbox with reviewedBBox when the ball is visible but the seed box needs correction.",
            "Use reject_seed or confirm_hard_negative when the candidate should not become selected follow-through evidence.",
        ],
    }
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "activeQueueItem": "manual_review_required",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "review_package_generation",
        "batchStatus": batch_status,
        "dominantInputBlockerClass": blocker_summary.get("dominantBlockerClass"),
        "proposalDiagnostics": blocker_summary.get("proposalDiagnostics") or {},
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "imageExtractionStatus": image_extraction_status,
        **overlay_counts,
        **decision,
    }
    batch_outcome = {
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "approachFamily": "review_package_generation",
        "batchStatus": batch_status,
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "artifacts": {
            "manualReviewFollowthroughSummaryPath": str(output_root / "manual_review_followthrough_summary.json"),
            "reviewedLabelOverlayPath": str(output_root / "reviewed_label_overlay.json"),
            "reviewFrameManifestPath": str(output_root / "review_frame_manifest.json"),
            "reviewBundleManifestPath": str(output_root / "review_bundle_manifest.json"),
        },
    }

    _write_json(output_root / "manual_review_followthrough_summary.json", summary)
    _write_json(output_root / "reviewed_label_overlay.json", reviewed_overlay)
    _write_json(output_root / "review_frame_manifest.json", review_frame_manifest)
    _write_json(output_root / "review_bundle_manifest.json", review_bundle_manifest)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    if not decision["goalAchieved"]:
        _write_json(
            output_root / "blocker_summary.json",
            {
                **summary,
                "blockerSummaryType": "manual_review_followthrough_package_blocked",
            },
        )

    # Touch these paths only by reading existence through Path construction; they are
    # accepted parameters so tests can assert this batch does not mutate them.
    _ = runtime_default_path, source_manifest_path, recovery_profile_matrix, proof_summary

    return {
        "summary": summary,
        "reviewedLabelOverlay": reviewed_overlay,
        "reviewFrameManifest": review_frame_manifest,
        "reviewBundleManifest": review_bundle_manifest,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--followthrough-root", type=Path, default=DEFAULT_FOLLOWTHROUGH_ROOT)
    parser.add_argument("--gold-truth-root", type=Path, default=DEFAULT_GOLD_TRUTH_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--runtime-default-path", type=Path, default=DEFAULT_RUNTIME_DEFAULT_PATH)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_SOURCE_MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_manual_review_followthrough_batch(
        output_root=args.output_root,
        followthrough_root=args.followthrough_root,
        gold_truth_root=args.gold_truth_root,
        promoted_proof_root=args.promoted_proof_root,
        video_path=args.video_path,
        runtime_default_path=args.runtime_default_path,
        source_manifest_path=args.source_manifest_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
