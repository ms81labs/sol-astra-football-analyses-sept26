from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import cv2

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

DEFAULT_TRAINING_DECISION_DIR_NAME = "football_external_soccernet_real_sample_product_pipeline_training_decision_v1"
DEFAULT_VIDEO_EXTRACT_DIR_NAME = "football_external_soccernet_video_member_extract_v1"
DEFAULT_LABEL_EXTRACT_DIR_NAME = "football_external_soccernet_zip_label_member_extract_v1"
DEFAULT_FULL_ANALYSIS_DIR_NAME = "football_external_soccernet_full_analysis_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_detector_miss_capture_and_label_queue_v1"

BLOCKER_TRAINING_DECISION_MISSING = "football_external_soccernet_real_sample_training_decision_missing"
BLOCKER_SAMPLE_MISSING = "football_external_soccernet_real_sample_materialization_missing"
BLOCKER_EVENT_POOL_INSUFFICIENT = "football_external_soccernet_detector_miss_event_pool_insufficient"
BLOCKER_EVIDENCE_GENERATION_FAILED = "football_external_soccernet_detector_miss_evidence_generation_failed"

NEXT_TRAINING_DECISION = "football_external_soccernet_real_sample_product_pipeline_training_decision"
NEXT_SAMPLE_DOWNLOAD = "football_external_soccernet_controlled_real_sample_download_execution"
NEXT_EVENT_SCHEMA_REPAIR = "football_external_soccernet_label_schema_ingestion_probe"
NEXT_MANUAL_REVIEW = "football_external_soccernet_detector_miss_manual_review_resolution"
NEXT_EVIDENCE_REPAIR = "football_external_soccernet_detector_miss_evidence_generation_repair"

PRIORITY_EVENT_LABELS = (
    "SHOT",
    "CROSS",
    "HIGH PASS",
    "HEADER",
    "BALL PLAYER BLOCK",
    "FREE KICK",
    "THROW IN",
    "PASS",
    "DRIVE",
    "OUT",
)


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_event_window_miss_capture_queue",
                "successCriteria": [
                    "read the validated real-sample product-pipeline training decision",
                    "sample SoccerNet event windows from real Labels-ball.json timing",
                    "write human-review rows with full-frame and zoom evidence",
                    "keep v7.3 training locked until reviewed detector-miss boxes exist",
                ],
                "failureAdaptation": "If sample or labels are missing, route to sample materialization/schema repair before review.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_event_queue_sampling_repair",
                "successCriteria": [
                    "repair only event selection, frame-index conversion, or evidence extraction",
                    "do not synthesize source-frame ball boxes",
                    "do not run training, promotion, or runtime mutation",
                ],
                "failureAdaptation": "If evidence cannot be generated from the video, route to evidence generation repair.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_miss_capture_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before v7.3 prep unless reviewed real detector-miss positives exist.",
            },
        ],
    }


def _load_inputs(root: Path) -> dict[str, Any]:
    return {
        "trainingDecisionSummary": load_json(
            root
            / DEFAULT_TRAINING_DECISION_DIR_NAME
            / "soccernet_real_sample_product_pipeline_training_decision_summary.json"
        ),
        "videoInventory": load_json(root / DEFAULT_VIDEO_EXTRACT_DIR_NAME / "extracted_video_member_inventory.json"),
        "fullAnalysisSummary": load_json(root / DEFAULT_FULL_ANALYSIS_DIR_NAME / "full_analysis_execution_summary.json"),
    }


def _training_decision_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("controlledRealSampleMaterialized") is True
        and summary.get("actualProductPipelinePassed") is True
        and summary.get("detectorTrainingNeededFromEvidence") is False
        and summary.get("v7_3TrainingDataReady") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _first_video(root: Path, inventory: dict[str, Any] | None) -> dict[str, Any]:
    extract_root = root / DEFAULT_VIDEO_EXTRACT_DIR_NAME
    files = inventory.get("extractedVideoFiles") if isinstance(inventory, dict) else []
    for row in files if isinstance(files, list) else []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("relativePath") or "")
        if not rel:
            continue
        path = extract_root / rel
        return {
            "inventoryRow": row,
            "path": path,
            "exists": path.exists(),
            "sizeBytes": path.stat().st_size if path.exists() else 0,
        }
    return {"inventoryRow": None, "path": None, "exists": False, "sizeBytes": 0}


def _label_candidates(root: Path, video_row: dict[str, Any] | None) -> list[Path]:
    label_root = root / DEFAULT_LABEL_EXTRACT_DIR_NAME / "extracted_labels"
    member_path = str((video_row or {}).get("memberPath") or "")
    candidates: list[Path] = []
    if member_path.endswith("/224p.mp4"):
        candidates.append(label_root / member_path.removesuffix("/224p.mp4") / "Labels-ball.json")
    candidates.extend(sorted(label_root.rglob("Labels-ball.json"))[:5])
    deduped: list[Path] = []
    for path in candidates:
        if path not in deduped:
            deduped.append(path)
    return deduped


def _load_annotations(label_path: Path | None) -> list[dict[str, Any]]:
    if label_path is None or not label_path.exists():
        return []
    payload = json.loads(label_path.read_text(encoding="utf-8"))
    annotations = payload.get("annotations") if isinstance(payload, dict) else []
    if not isinstance(annotations, list):
        return []
    return [row for row in annotations if isinstance(row, dict)]


def _position_ms(row: dict[str, Any]) -> int | None:
    raw = row.get("position")
    try:
        value = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _select_annotations(annotations: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    usable = [row for row in annotations if _position_ms(row) is not None]
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in usable:
        label = str(row.get("label") or "UNKNOWN").upper()
        buckets.setdefault(label, []).append(row)
    for rows in buckets.values():
        rows.sort(key=lambda item: (_position_ms(item) or 0, str(item.get("gameTime") or "")))

    selected: list[dict[str, Any]] = []
    label_order = list(PRIORITY_EVENT_LABELS) + sorted(label for label in buckets if label not in PRIORITY_EVENT_LABELS)
    while len(selected) < target_count:
        added = False
        for label in label_order:
            rows = buckets.get(label) or []
            if not rows:
                continue
            selected.append(rows.pop(0))
            added = True
            if len(selected) >= target_count:
                break
        if not added:
            break
    return selected


def _video_probe(video_path: Path | None) -> dict[str, Any]:
    if video_path is None or not video_path.exists():
        return {"videoExists": False, "videoOpenable": False}
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        return {"videoExists": True, "videoOpenable": False}
    probe = {
        "videoExists": True,
        "videoOpenable": True,
        "frameCount": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
        "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0.0),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
    }
    cap.release()
    return probe


def _frame_index_for(position_ms: int, fps: float, frame_count: int) -> int:
    if fps <= 0:
        fps = 25.0
    frame_index = int(round((position_ms / 1000.0) * fps))
    return max(0, min(max(0, frame_count - 1), frame_index))


def _split_group_for(position_ms: int) -> str:
    bucket = position_ms // 30000
    return f"soccernet-event-window-bucket-{bucket:04d}"


def _write_review_images(
    *,
    video_path: Path,
    selected: list[dict[str, Any]],
    output_root: Path,
    fps: float,
    frame_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    full_dir = output_root / "review_evidence" / "full_frames"
    crop_dir = output_root / "review_evidence" / "crops"
    full_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    rows: list[dict[str, Any]] = []
    missing = 0
    for index, event in enumerate(selected):
        position_ms = _position_ms(event)
        if position_ms is None:
            missing += 1
            continue
        frame_index = _frame_index_for(position_ms, fps, frame_count)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            missing += 1
            continue
        height, width = int(frame.shape[0]), int(frame.shape[1])
        review_id = f"soccernet-miss-review-{index:04d}-frame-{frame_index:06d}"
        full_path = full_dir / f"{review_id}.jpg"
        crop_path = crop_dir / f"{review_id}-full-frame-zoom.jpg"
        zoom = cv2.resize(frame, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(str(full_path), frame)
        cv2.imwrite(str(crop_path), zoom)
        rows.append(
            {
                "reviewItemId": review_id,
                "candidateKind": "soccernet_event_window_detector_miss_review",
                "source": "Labels-ball.json",
                "eventLabel": str(event.get("label") or "UNKNOWN"),
                "eventPositionMs": position_ms,
                "gameTime": event.get("gameTime"),
                "team": event.get("team"),
                "visibility": event.get("visibility"),
                "frameIndex": frame_index,
                "sourceClipId": video_path.name,
                "splitGroupId": _split_group_for(position_ms),
                "fullFrameImagePath": str(full_path.resolve()),
                "cropImagePath": str(crop_path.resolve()),
                "fullFrameImageRelativePath": str(full_path.relative_to(output_root)),
                "cropImageRelativePath": str(crop_path.relative_to(output_root)),
                "cropBoundsXyxy": [0.0, 0.0, float(width), float(height)],
                "cropKind": "upscaled_full_frame_event_review_no_bbox_truth",
                "zoomScale": 2.0,
                "reviewStatus": "pending_review",
                "allowedReviewStatuses": [
                    "reviewed_real_detector_miss_positive",
                    "reviewed_detector_hit_or_not_miss",
                    "reviewed_not_ball_or_out_of_play",
                    "review_deferred_unclear",
                    "bad_frame_or_unusable",
                ],
                "sourceFrameBbox": None,
                "trainingEligibility": "pending_review",
                "reviewInstruction": (
                    "If the real in-play ball is visible and the detector should have found it, "
                    "draw a tight source-frame bbox and mark reviewed_real_detector_miss_positive. "
                    "If it is a normal detected case, out-of-play/replacement ball, unclear, or unusable, "
                    "reject/defer with a reason."
                ),
            }
        )
    cap.release()
    audit = {
        "schemaVersion": "soccernet_detector_miss_review_evidence_generation_v1",
        "generatedAt": utc_now_iso(),
        "requestedEventCount": len(selected),
        "reviewItemCount": len(rows),
        "missingEvidenceImageCount": missing,
        "fullFrameEvidenceDir": str(full_dir.resolve()),
        "cropEvidenceDir": str(crop_dir.resolve()),
    }
    return rows, audit


def _render_review_index(output_root: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    cards: list[str] = []
    for row in rows:
        full_rel = html.escape(str(row["fullFrameImageRelativePath"]))
        crop_rel = html.escape(str(row["cropImageRelativePath"]))
        cards.append(
            "\n".join(
                [
                    "<section class='card'>",
                    f"<h2>{html.escape(str(row['reviewItemId']))}</h2>",
                    "<div class='meta'>"
                    f"label={html.escape(str(row['eventLabel']))} | "
                    f"frame={row['frameIndex']} | "
                    f"gameTime={html.escape(str(row.get('gameTime')))} | "
                    f"splitGroup={html.escape(str(row['splitGroupId']))}</div>",
                    "<div class='images'>",
                    f"<figure><img src='{full_rel}'><figcaption>Full frame</figcaption></figure>",
                    f"<figure><img src='{crop_rel}'><figcaption>2x review image, no bbox truth yet</figcaption></figure>",
                    "</div>",
                    f"<p>{html.escape(str(row['reviewInstruction']))}</p>",
                    "</section>",
                ]
            )
        )
    html_text = "\n".join(
        [
            "<!doctype html>",
            "<html><head><meta charset='utf-8'><title>SoccerNet Detector Miss Review Queue</title>",
            "<style>",
            "body{font-family:system-ui,sans-serif;margin:24px;background:#f6f7f8;color:#111827}",
            ".summary{background:#fff;border:1px solid #d1d5db;padding:16px;margin-bottom:20px}",
            ".card{background:#fff;border:1px solid #d1d5db;padding:16px;margin:0 0 20px}",
            ".meta{color:#4b5563;margin-bottom:12px}",
            ".images{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}",
            "img{max-width:100%;height:auto;border:1px solid #9ca3af;background:#111}",
            "figcaption{font-size:13px;color:#4b5563;margin-top:4px}",
            "</style></head><body>",
            "<div class='summary'>",
            "<h1>SoccerNet Detector Miss Review Queue</h1>",
            f"<p>Rows: {summary.get('reviewItemCount')} | pending: {summary.get('pendingReviewItemCount')}</p>",
            "<p>Edit <code>soccernet_detector_miss_review_overlay.json</code>. This package does not create training truth by itself.</p>",
            "</div>",
            *cards,
            "</body></html>",
        ]
    )
    (output_root / "detector_miss_review_index.html").write_text(html_text, encoding="utf-8")


def _classify(
    *,
    decision_ready: bool,
    sample_ready: bool,
    annotation_count: int,
    review_item_count: int,
    missing_evidence_count: int,
    min_review_item_count: int,
) -> tuple[str | None, str, bool, bool, str]:
    if not decision_ready:
        return (
            BLOCKER_TRAINING_DECISION_MISSING,
            NEXT_TRAINING_DECISION,
            False,
            False,
            "Real-sample product-pipeline training decision is missing or unsafe; rerun it before detector-miss capture.",
        )
    if not sample_ready:
        return (
            BLOCKER_SAMPLE_MISSING,
            NEXT_SAMPLE_DOWNLOAD,
            False,
            False,
            "Controlled SoccerNet real sample video or Labels-ball.json is missing; materialize the sample before miss capture.",
        )
    if annotation_count < min_review_item_count:
        return (
            BLOCKER_EVENT_POOL_INSUFFICIENT,
            NEXT_EVENT_SCHEMA_REPAIR,
            False,
            False,
            "SoccerNet event label pool is too small to create a useful detector-miss review queue.",
        )
    if review_item_count < min_review_item_count or missing_evidence_count > 0:
        return (
            BLOCKER_EVIDENCE_GENERATION_FAILED,
            NEXT_EVIDENCE_REPAIR,
            False,
            False,
            "Detector-miss review rows could not be fully backed by frame/crop evidence.",
        )
    return (
        None,
        NEXT_MANUAL_REVIEW,
        True,
        True,
        "SoccerNet detector-miss review queue is ready. Human review must create real source-frame miss boxes before any v7.3 training prep.",
    )


def run_football_external_soccernet_detector_miss_capture_and_label_queue(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    target_review_item_count: int = 120,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    inputs = _load_inputs(root)
    decision_ready = _training_decision_ready(inputs["trainingDecisionSummary"])

    video = _first_video(root, inputs["videoInventory"])
    video_row = video.get("inventoryRow") if isinstance(video.get("inventoryRow"), dict) else {}
    label_path = next((path for path in _label_candidates(root, video_row) if path.exists()), None)
    annotations = _load_annotations(label_path)
    video_path = video.get("path") if isinstance(video.get("path"), Path) else None
    probe = _video_probe(video_path)
    sample_ready = bool(video.get("exists") and int(video.get("sizeBytes") or 0) > 0 and label_path and probe.get("videoOpenable"))

    selected = _select_annotations(annotations, max(1, int(target_review_item_count))) if sample_ready else []
    fps = float(probe.get("fps") or 25.0)
    frame_count = int(probe.get("frameCount") or (inputs["fullAnalysisSummary"] or {}).get("processedFrameCount") or 0)
    rows: list[dict[str, Any]] = []
    evidence_audit: dict[str, Any] = {
        "schemaVersion": "soccernet_detector_miss_review_evidence_generation_v1",
        "generatedAt": utc_now_iso(),
        "requestedEventCount": len(selected),
        "reviewItemCount": 0,
        "missingEvidenceImageCount": 0,
    }
    if sample_ready and video_path is not None:
        rows, evidence_audit = _write_review_images(
            video_path=video_path,
            selected=selected,
            output_root=output_root,
            fps=fps,
            frame_count=frame_count,
        )

    min_review_item_count = min(80, max(1, int(target_review_item_count)))
    primary_blocker, next_lever, goal, review_ready, english = _classify(
        decision_ready=decision_ready,
        sample_ready=sample_ready,
        annotation_count=len(annotations),
        review_item_count=len(rows),
        missing_evidence_count=int(evidence_audit.get("missingEvidenceImageCount") or 0),
        min_review_item_count=min_review_item_count,
    )

    attempt_families = [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]]
    summary = {
        "batchName": "football_external_soccernet_detector_miss_capture_and_label_queue",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": attempt_families,
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "sourceTrainingDecisionBatch": "football_external_soccernet_real_sample_product_pipeline_training_decision",
        "trainingDecisionReady": decision_ready,
        "controlledRealSampleMaterialized": sample_ready,
        "sampleVideoPath": str(video_path.resolve()) if video_path else None,
        "sampleLabelPath": str(label_path.resolve()) if label_path else None,
        "soccerNetEventAnnotationCount": len(annotations),
        "targetReviewItemCount": int(target_review_item_count),
        "reviewItemCount": len(rows),
        "reviewQueueReady": review_ready,
        "pendingReviewItemCount": len(rows),
        "missingEvidenceImageCount": int(evidence_audit.get("missingEvidenceImageCount") or 0),
        "reviewedRealDetectorMissPositiveCount": 0,
        "realDetectorMissCount": 0,
        "v7_3TrainingDataReady": False,
        "v7_3RetrainExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    event_sampling_audit = {
        "schemaVersion": "soccernet_detector_miss_event_sampling_audit_v1",
        "generatedAt": utc_now_iso(),
        "sourceLabelPath": str(label_path.resolve()) if label_path else None,
        "eventAnnotationCount": len(annotations),
        "selectedEventCount": len(selected),
        "priorityEventLabels": list(PRIORITY_EVENT_LABELS),
        "selectedEventLabelCounts": {
            label: sum(1 for row in selected if str(row.get("label") or "UNKNOWN").upper() == label)
            for label in sorted({str(row.get("label") or "UNKNOWN").upper() for row in selected})
        },
    }
    queue = {
        "schemaVersion": "soccernet_event_window_review_queue_v1",
        "generatedAt": utc_now_iso(),
        "reviewItems": rows,
    }
    overlay = {
        "schemaVersion": "soccernet_detector_miss_review_overlay_v1",
        "generatedAt": utc_now_iso(),
        "reviewStatusesAllowed": [
            "reviewed_real_detector_miss_positive",
            "reviewed_detector_hit_or_not_miss",
            "reviewed_not_ball_or_out_of_play",
            "review_deferred_unclear",
            "bad_frame_or_unusable",
        ],
        "reviewItems": rows,
    }
    truth_gate = {
        "schemaVersion": "soccernet_detector_miss_truth_gate_v1",
        "generatedAt": utc_now_iso(),
        "reviewQueueReady": review_ready,
        "pendingReviewItemCount": len(rows),
        "reviewedRealDetectorMissPositiveCount": 0,
        "v7_3TrainingDataReady": False,
        "v7_3TrainingDataReadyRequires": [
            "pendingReviewItemCount == 0",
            "reviewedRealDetectorMissPositiveCount > 0",
            "all accepted miss positives have valid source-frame bboxes",
        ],
    }
    decision_matrix = {
        "schemaVersion": "soccernet_detector_miss_capture_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "training_decision_missing",
                "selected": primary_blocker == BLOCKER_TRAINING_DECISION_MISSING,
                "primaryBlocker": BLOCKER_TRAINING_DECISION_MISSING,
                "nextRecommendedNextLever": NEXT_TRAINING_DECISION,
            },
            {
                "condition": "controlled_sample_missing",
                "selected": primary_blocker == BLOCKER_SAMPLE_MISSING,
                "primaryBlocker": BLOCKER_SAMPLE_MISSING,
                "nextRecommendedNextLever": NEXT_SAMPLE_DOWNLOAD,
            },
            {
                "condition": "event_pool_insufficient",
                "selected": primary_blocker == BLOCKER_EVENT_POOL_INSUFFICIENT,
                "primaryBlocker": BLOCKER_EVENT_POOL_INSUFFICIENT,
                "nextRecommendedNextLever": NEXT_EVENT_SCHEMA_REPAIR,
            },
            {
                "condition": "evidence_generation_failed",
                "selected": primary_blocker == BLOCKER_EVIDENCE_GENERATION_FAILED,
                "primaryBlocker": BLOCKER_EVIDENCE_GENERATION_FAILED,
                "nextRecommendedNextLever": NEXT_EVIDENCE_REPAIR,
            },
            {
                "condition": "manual_review_queue_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_MANUAL_REVIEW,
            },
        ],
    }

    write_json(output_root / "soccernet_event_window_review_queue.json", queue)
    write_json(output_root / "soccernet_detector_miss_review_overlay.json", overlay)
    _render_review_index(output_root, rows, summary)
    return write_outcome(
        output_root=output_root,
        summary_filename="detector_miss_capture_summary.json",
        summary=summary,
        artifacts={
            "event_sampling_audit.json": event_sampling_audit,
            "review_evidence_manifest.json": evidence_audit,
            "detector_miss_truth_gate.json": truth_gate,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External SoccerNet Detector Miss Capture And Label Queue",
    )


def main() -> None:
    main_for(
        "Create a SoccerNet detector-miss capture and label review queue from real event windows.",
        run_football_external_soccernet_detector_miss_capture_and_label_queue,
    )


if __name__ == "__main__":
    main()
