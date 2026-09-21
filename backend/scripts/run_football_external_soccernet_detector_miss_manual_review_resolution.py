from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_json,
    write_outcome,
)

DEFAULT_CAPTURE_DIR_NAME = "football_external_soccernet_detector_miss_capture_and_label_queue_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_detector_miss_manual_review_resolution_v1"

POSITIVE_STATUS = "reviewed_real_detector_miss_positive"
HIT_OR_NOT_MISS_STATUS = "reviewed_detector_hit_or_not_miss"
NOT_BALL_STATUS = "reviewed_not_ball_or_out_of_play"
UNCLEAR_STATUS = "review_deferred_unclear"
BAD_FRAME_STATUS = "bad_frame_or_unusable"
PENDING_STATUS = "pending_review"
ALLOWED_STATUSES = {
    POSITIVE_STATUS,
    HIT_OR_NOT_MISS_STATUS,
    NOT_BALL_STATUS,
    UNCLEAR_STATUS,
    BAD_FRAME_STATUS,
    PENDING_STATUS,
}

MIN_BBOX_SIZE_PX = 2.0
MAX_BBOX_SIZE_PX = 80.0

BLOCKER_CAPTURE_QUEUE_MISSING = "football_external_soccernet_detector_miss_capture_queue_missing"
BLOCKER_PENDING = "football_external_soccernet_detector_miss_manual_review_still_pending"
BLOCKER_INVALID_STATUS = "football_external_soccernet_detector_miss_invalid_review_status"
BLOCKER_INVALID_BBOX = "football_external_soccernet_detector_miss_invalid_bbox"
BLOCKER_LABEL_QUALITY = "football_external_soccernet_detector_miss_label_quality_gap"
BLOCKER_EVIDENCE_MISSING = "football_external_soccernet_detector_miss_evidence_missing"

NEXT_CAPTURE_QUEUE = "football_external_soccernet_detector_miss_capture_and_label_queue"
NEXT_SELF = "football_external_soccernet_detector_miss_manual_review_resolution"
NEXT_V7_3_PREP = "v7_3_training_manifest_prep_from_soccernet_real_misses"
NEXT_NO_TRAINING_CLOSEOUT = "football_external_soccernet_no_detector_training_needed_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_detector_miss_review_resolution_gate",
                "successCriteria": [
                    "load the generated detector-miss review overlay",
                    "validate every review status",
                    "accept only reviewed real detector misses with tight source-frame bboxes",
                    "route to v7.3 manifest prep only if reviewed real miss truth exists",
                ],
                "failureAdaptation": "If rows remain pending, keep roadmap blocked on manual review.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_detector_miss_review_schema_repair",
                "successCriteria": [
                    "repair only review schema, evidence-path, or bbox-field validation issues",
                    "do not infer labels from model detections or SoccerNet event timing",
                    "do not run training, promotion, or runtime mutation",
                ],
                "failureAdaptation": "If accepted rows have invalid bboxes/evidence, route back to manual review resolution.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_detector_miss_resolution_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before v7.3 prep unless reviewed real detector-miss positives exist.",
            },
        ],
    }


def _review_items(overlay: dict[str, Any] | None) -> list[dict[str, Any]]:
    items = overlay.get("reviewItems") if isinstance(overlay, dict) else []
    return [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _bbox_error(row: dict[str, Any]) -> str | None:
    bbox = row.get("sourceFrameBbox")
    if not isinstance(bbox, dict):
        return "missing_source_frame_bbox"
    x1 = _safe_float(bbox.get("x1"))
    y1 = _safe_float(bbox.get("y1"))
    x2 = _safe_float(bbox.get("x2"))
    y2 = _safe_float(bbox.get("y2"))
    if None in {x1, y1, x2, y2}:
        return "non_numeric_source_frame_bbox"
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    width = x2 - x1
    height = y2 - y1
    if x1 < 0 or y1 < 0:
        return "bbox_outside_source_frame"
    if width <= 0 or height <= 0:
        return "bbox_not_ordered"
    if width < MIN_BBOX_SIZE_PX or height < MIN_BBOX_SIZE_PX:
        return "bbox_too_small"
    if width > MAX_BBOX_SIZE_PX or height > MAX_BBOX_SIZE_PX:
        return "bbox_too_large"
    crop_bounds = row.get("cropBoundsXyxy")
    if isinstance(crop_bounds, list) and len(crop_bounds) == 4:
        crop_x1, crop_y1, crop_x2, crop_y2 = (_safe_float(value) for value in crop_bounds)
        if None not in {crop_x1, crop_y1, crop_x2, crop_y2}:
            assert crop_x1 is not None and crop_y1 is not None and crop_x2 is not None and crop_y2 is not None
            if x1 < crop_x1 or y1 < crop_y1 or x2 > crop_x2 or y2 > crop_y2:
                return "bbox_outside_review_frame_bounds"
    return None


def _evidence_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("fullFrameImagePath", "cropImagePath"):
        path = row.get(key)
        if not path or not Path(str(path)).exists():
            errors.append(f"missing_{key}")
    return errors


def _label_quality_error(row: dict[str, Any]) -> str | None:
    status = str(row.get("reviewStatus") or "")
    if status not in ALLOWED_STATUSES:
        return "invalid_review_status"
    if status == POSITIVE_STATUS:
        if row.get("trainingEligibility") != "eligible_real_detector_miss_positive":
            return "accepted_miss_missing_training_eligibility"
        if not row.get("visibilityClass"):
            return "accepted_miss_missing_visibility_class"
        if not isinstance(row.get("contextTags"), list):
            return "accepted_miss_missing_context_tags"
    elif status in {HIT_OR_NOT_MISS_STATUS, NOT_BALL_STATUS, UNCLEAR_STATUS, BAD_FRAME_STATUS}:
        if not row.get("rejectionReason") and not row.get("reviewNotes"):
            return "non_positive_missing_reason"
    return None


def _source_key(row: dict[str, Any]) -> str:
    return f"{row.get('sourceClipId')}:{row.get('frameIndex')}"


def _summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    invalid_status_rows: list[dict[str, Any]] = []
    invalid_bbox_rows: list[dict[str, Any]] = []
    label_quality_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    positive_by_source: dict[str, dict[str, Any]] = {}

    for row in items:
        status = str(row.get("reviewStatus") or "")
        if status in status_counts:
            status_counts[status] += 1
        else:
            invalid_status_rows.append({"reviewItemId": row.get("reviewItemId"), "reviewStatus": status})

        quality_error = _label_quality_error(row)
        if quality_error:
            label_quality_rows.append({"reviewItemId": row.get("reviewItemId"), "error": quality_error})

        evidence_errors = _evidence_errors(row)
        if evidence_errors:
            evidence_rows.append({"reviewItemId": row.get("reviewItemId"), "errors": evidence_errors})

        if status == POSITIVE_STATUS:
            bbox_error = _bbox_error(row)
            if bbox_error:
                invalid_bbox_rows.append(
                    {
                        "reviewItemId": row.get("reviewItemId"),
                        "error": bbox_error,
                        "sourceFrameBbox": row.get("sourceFrameBbox"),
                    }
                )
            elif not evidence_errors and not quality_error:
                positive_by_source.setdefault(_source_key(row), row)

    positive_rows = list(positive_by_source.values())
    groups = {str(row.get("splitGroupId")) for row in positive_rows if row.get("splitGroupId")}
    return {
        "reviewCandidateCount": len(items),
        "pendingReviewItemCount": status_counts[PENDING_STATUS],
        "reviewedRealDetectorMissPositiveCount": len(positive_rows),
        "realDetectorMissCount": len(positive_rows),
        "reviewedDetectorHitOrNotMissCount": status_counts[HIT_OR_NOT_MISS_STATUS],
        "reviewedNotBallOrOutOfPlayCount": status_counts[NOT_BALL_STATUS],
        "reviewDeferredUnclearCount": status_counts[UNCLEAR_STATUS],
        "badFrameOrUnusableCount": status_counts[BAD_FRAME_STATUS],
        "invalidReviewStatusCount": len(invalid_status_rows),
        "invalidBBoxCount": len(invalid_bbox_rows),
        "labelQualityGapCount": len(label_quality_rows),
        "missingEvidenceImageCount": len(evidence_rows),
        "distinctRealMissSplitGroupCount": len(groups),
        "positiveRows": positive_rows,
        "invalidReviewStatusRows": invalid_status_rows,
        "invalidBBoxRows": invalid_bbox_rows,
        "labelQualityRows": label_quality_rows,
        "evidenceRows": evidence_rows,
    }


def _classify(capture_ready: bool, summary: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not capture_ready:
        return (
            BLOCKER_CAPTURE_QUEUE_MISSING,
            NEXT_CAPTURE_QUEUE,
            False,
            False,
            "Detector-miss capture queue is missing or unsafe; generate the review queue before resolution.",
        )
    if summary["invalidReviewStatusCount"] > 0:
        return (
            BLOCKER_INVALID_STATUS,
            NEXT_SELF,
            False,
            False,
            "Detector-miss review contains invalid statuses. Fix the overlay before v7.3 prep.",
        )
    if summary["labelQualityGapCount"] > 0:
        return (
            BLOCKER_LABEL_QUALITY,
            NEXT_SELF,
            False,
            False,
            "Detector-miss review has missing required fields. Fix the overlay before v7.3 prep.",
        )
    if summary["missingEvidenceImageCount"] > 0:
        return (
            BLOCKER_EVIDENCE_MISSING,
            NEXT_SELF,
            False,
            False,
            "Accepted or reviewed detector-miss rows reference missing evidence images.",
        )
    if summary["invalidBBoxCount"] > 0:
        return (
            BLOCKER_INVALID_BBOX,
            NEXT_SELF,
            False,
            False,
            "Accepted real detector-miss positives contain invalid or implausible source-frame bboxes.",
        )
    if summary["pendingReviewItemCount"] > 0:
        return (
            BLOCKER_PENDING,
            NEXT_SELF,
            False,
            False,
            "Detector-miss review is still pending. Resolve all rows before deciding v7.3 training data.",
        )
    if summary["reviewedRealDetectorMissPositiveCount"] > 0:
        return (
            None,
            NEXT_V7_3_PREP,
            True,
            True,
            "Reviewed real detector-miss boxes exist. Advance to v7.3 manifest prep; do not train until export overlay audit passes.",
        )
    return (
        None,
        NEXT_NO_TRAINING_CLOSEOUT,
        True,
        True,
        "Detector-miss review found no real reviewed detector misses. v7.3 retraining is not justified from this sample.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Detector Miss Manual Review Resolution",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Review candidates: `{summary.get('reviewCandidateCount')}`",
            f"- Pending review items: `{summary.get('pendingReviewItemCount')}`",
            f"- Reviewed real detector-miss positives: `{summary.get('reviewedRealDetectorMissPositiveCount')}`",
            f"- Missing evidence images: `{summary.get('missingEvidenceImageCount')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_detector_miss_manual_review_resolution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    capture_root = root / DEFAULT_CAPTURE_DIR_NAME
    output_root = reset_output(root, output_dir_name)

    capture_summary = load_json(capture_root / "detector_miss_capture_summary.json")
    overlay = load_json(capture_root / "soccernet_detector_miss_review_overlay.json")
    capture_ready = bool(
        isinstance(capture_summary, dict)
        and capture_summary.get("goalAchieved") is True
        and capture_summary.get("primaryBlocker") is None
        and capture_summary.get("reviewQueueReady") is True
        and _safe_int(capture_summary.get("missingEvidenceImageCount")) == 0
        and isinstance(overlay, dict)
    )
    items = _review_items(overlay)
    item_summary = _summarize(items)
    primary_blocker, next_lever, goal, roadmap_advance, english = _classify(capture_ready, item_summary)

    summary = {
        "batchName": "football_external_soccernet_detector_miss_manual_review_resolution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "reviewPackagePath": str(capture_root / "soccernet_detector_miss_review_overlay.json"),
        "sourceCaptureBatch": "football_external_soccernet_detector_miss_capture_and_label_queue",
        "captureQueueReady": capture_ready,
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": roadmap_advance,
        "primaryBlocker": primary_blocker,
        "detectorTrainingNeededFromEvidence": item_summary["reviewedRealDetectorMissPositiveCount"] > 0 and primary_blocker is None,
        "v7_3TrainingDataReady": item_summary["reviewedRealDetectorMissPositiveCount"] > 0 and primary_blocker is None,
        "v7_3RetrainExecuted": False,
        **standard_false_flags(),
        **{key: value for key, value in item_summary.items() if not key.endswith("Rows") and key != "positiveRows"},
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }

    write_json(
        output_root / "reviewed_real_detector_miss_truth_additions.json",
        {
            "schemaVersion": "soccernet_reviewed_real_detector_miss_truth_additions_v1",
            "generatedAt": utc_now_iso(),
            "reviewedRealDetectorMissPositiveCount": len(item_summary["positiveRows"]),
            "rows": item_summary["positiveRows"],
        },
    )
    write_json(
        output_root / "detector_miss_review_resolution_counts.json",
        {key: value for key, value in summary.items() if key.endswith("Count") or key in {"primaryBlocker", "nextRecommendedNextLever"}},
    )
    write_json(
        output_root / "detector_miss_invalid_bbox_audit.json",
        {"invalidBBoxCount": len(item_summary["invalidBBoxRows"]), "rows": item_summary["invalidBBoxRows"]},
    )
    write_json(
        output_root / "detector_miss_label_quality_audit.json",
        {
            "invalidReviewStatusCount": len(item_summary["invalidReviewStatusRows"]),
            "labelQualityGapCount": len(item_summary["labelQualityRows"]),
            "invalidReviewStatusRows": item_summary["invalidReviewStatusRows"],
            "labelQualityRows": item_summary["labelQualityRows"],
        },
    )
    write_json(
        output_root / "detector_miss_evidence_audit.json",
        {"missingEvidenceImageCount": len(item_summary["evidenceRows"]), "rows": item_summary["evidenceRows"]},
    )
    artifacts = {
        "decision_matrix.json": {
            "schemaVersion": "soccernet_detector_miss_manual_review_resolution_decision_matrix_v1",
            "generatedAt": utc_now_iso(),
            "summary": summary,
        },
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    summary = write_outcome(
        output_root=output_root,
        summary_filename="detector_miss_manual_review_resolution_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Football External SoccerNet Detector Miss Manual Review Resolution",
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    main_for(
        "Resolve SoccerNet detector-miss manual review rows and decide whether v7.3 manifest prep is allowed.",
        run_football_external_soccernet_detector_miss_manual_review_resolution,
    )


if __name__ == "__main__":
    main()
