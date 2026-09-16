from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
from typing import Any

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_full_analysis_execution_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_full_analysis_execution_v1"

BLOCKER_NOT_APPROVED = "football_external_soccernet_full_analysis_execution_not_approved"
BLOCKER_VIDEO_OPEN_FAILED = "football_external_soccernet_full_analysis_video_open_failed"
BLOCKER_FRAME_COUNT_MISMATCH = "football_external_soccernet_full_analysis_frame_count_mismatch"

NEXT_APPROVAL = "football_external_soccernet_full_analysis_execution_approval"
NEXT_VIDEO_OPEN_DEBUG = "football_external_soccernet_full_analysis_video_open_debug"
NEXT_FRAME_READ_REPAIR = "football_external_soccernet_full_analysis_frame_read_repair"
NEXT_REPORT_SMOKE = "football_external_soccernet_full_analysis_report_smoke"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_full_video_frame_signal_execution",
            "successCriteria": [
                "open the approved extracted 224p SoccerNet video",
                "process every approved frame",
                "write aggregate and segment-level frame signal artifacts",
            ],
            "failureAdaptation": "If frame reading fails, repair only the video path or frame-read contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_full_analysis_frame_read_repair",
            "successCriteria": [
                "repair selected-video path or expected frame count from approval truth",
                "do not download 720p, download archive, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "If approval is invalid, route back to approval.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_full_analysis_execution_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before report smoke if full-frame execution is unsafe",
            ],
            "failureAdaptation": "Route to approval, video-open debug, or frame-read repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, approval_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / approval_dir_name
    return {
        "candidateRoot": candidate_root,
        "approvalSummary": _load_json(approval_root / "full_analysis_execution_approval_summary.json"),
        "executionContract": _load_json(approval_root / "full_analysis_execution_contract.json"),
    }


def _approval_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("fullAnalysisExecutionApproved") is True
        and summary.get("fullAnalysisExecutionExecuted") is False
        and int(summary.get("approvedFrameCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(contract, dict)
        and contract.get("fullAnalysisExecutionApproved") is True
        and contract.get("fullAnalysisExecutionExecuted") is False
        and int(contract.get("approvedFrameCount") or 0) > 0
        and contract.get("video720pMemberDownloadAllowed") is False
        and contract.get("archiveDownloadAllowed") is False
        and contract.get("trainingAllowed") is False
        and contract.get("runtimeDefaultMutationAllowed") is False
        and bool(contract.get("selectedVideoPath"))
    )


def _empty_segment(index: int, start_frame: int, end_frame: int) -> dict[str, Any]:
    return {
        "segmentIndex": index,
        "startFrame": start_frame,
        "endFrame": end_frame,
        "frameCount": 0,
        "meanBrightnessValues": [],
        "greenDominantPixelRatios": [],
        "motionDeltaValues": [],
    }


def _finalize_segment(segment: dict[str, Any]) -> dict[str, Any]:
    brightness = segment.pop("meanBrightnessValues")
    green = segment.pop("greenDominantPixelRatios")
    motion = segment.pop("motionDeltaValues")
    segment["meanBrightnessP50"] = round(statistics.median(brightness), 6) if brightness else None
    segment["greenDominantPixelRatioP50"] = round(statistics.median(green), 6) if green else None
    segment["motionDeltaP50"] = round(statistics.median(motion), 6) if motion else None
    return segment


def _execute_full_video(contract: dict[str, Any]) -> dict[str, Any]:
    video_path = Path(str(contract.get("selectedVideoPath") or ""))
    approved_count = int(contract.get("approvedFrameCount") or 0)
    fps = float(contract.get("fps") or 0.0)
    segment_seconds = 30
    segment_size = max(1, int(round(fps * segment_seconds))) if fps > 0 else 750
    if not video_path.exists():
        return {
            "videoPath": str(video_path),
            "videoExists": False,
            "videoOpenable": False,
            "aggregate": {"approvedFrameCount": approved_count, "processedFrameCount": 0, "unreadableFrameCount": approved_count},
            "segments": [],
        }
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        return {
            "videoPath": str(video_path),
            "videoExists": True,
            "videoOpenable": False,
            "aggregate": {"approvedFrameCount": approved_count, "processedFrameCount": 0, "unreadableFrameCount": approved_count},
            "segments": [],
        }
    reported_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    reported_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    processed = 0
    unreadable = 0
    brightness_values: list[float] = []
    green_values: list[float] = []
    motion_values: list[float] = []
    segment_index = 0
    segment = _empty_segment(segment_index, 0, min(segment_size - 1, max(approved_count - 1, 0)))
    segments: list[dict[str, Any]] = []
    previous_gray = None
    while processed + unreadable < approved_count:
        ok, frame = cap.read()
        if not ok or frame is None:
            unreadable += 1
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        green_channel = frame[:, :, 1].astype("float32")
        red_channel = frame[:, :, 2].astype("float32")
        blue_channel = frame[:, :, 0].astype("float32")
        mean_brightness = float(gray.mean())
        green_ratio = float(((green_channel > red_channel + 8) & (green_channel > blue_channel + 8)).mean())
        motion_delta = 0.0
        if previous_gray is not None:
            motion_delta = float(cv2.absdiff(gray, previous_gray).mean())
        previous_gray = gray
        brightness_values.append(mean_brightness)
        green_values.append(green_ratio)
        motion_values.append(motion_delta)
        if processed > segment["endFrame"]:
            segments.append(_finalize_segment(segment))
            segment_index += 1
            start = segment_index * segment_size
            segment = _empty_segment(segment_index, start, min(start + segment_size - 1, approved_count - 1))
        segment["frameCount"] += 1
        segment["meanBrightnessValues"].append(mean_brightness)
        segment["greenDominantPixelRatios"].append(green_ratio)
        segment["motionDeltaValues"].append(motion_delta)
        processed += 1
    cap.release()
    if segment["frameCount"] > 0:
        segments.append(_finalize_segment(segment))
    aggregate = {
        "approvedFrameCount": approved_count,
        "reportedFrameCount": reported_count,
        "processedFrameCount": processed,
        "unreadableFrameCount": unreadable,
        "width": width,
        "height": height,
        "fps": reported_fps,
        "meanBrightnessP50": round(statistics.median(brightness_values), 6) if brightness_values else None,
        "meanBrightnessMin": round(min(brightness_values), 6) if brightness_values else None,
        "meanBrightnessMax": round(max(brightness_values), 6) if brightness_values else None,
        "greenDominantPixelRatioP50": round(statistics.median(green_values), 6) if green_values else None,
        "motionDeltaP50": round(statistics.median(motion_values), 6) if motion_values else None,
        "segmentCount": len(segments),
    }
    return {
        "schemaVersion": "soccernet_external_full_video_frame_signal_summary_v1",
        "generatedAt": _utc_now_iso(),
        "videoPath": str(video_path),
        "videoExists": True,
        "videoOpenable": True,
        "aggregate": aggregate,
        "segments": segments,
    }


def _product_payload(signal_summary: dict[str, Any]) -> dict[str, Any]:
    aggregate = signal_summary.get("aggregate", {})
    return {
        "schemaVersion": "soccernet_external_full_analysis_product_payload_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_soccernet_full_analysis_execution",
        "videoPath": signal_summary.get("videoPath"),
        "frameCount": aggregate.get("processedFrameCount"),
        "aggregateFrameSignals": aggregate,
        "segmentCount": aggregate.get("segmentCount"),
        "readiness": {
            "fullAnalysisExecutionReady": aggregate.get("processedFrameCount") == aggregate.get("approvedFrameCount"),
            "fullAnalysisReportReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "candidateEvaluationReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": [
            "full extracted 224p member only",
            "lightweight frame-statistics analysis only",
            "not detector evaluation",
            "not training evidence",
            "does not mutate runtime defaults",
        ],
    }


def _classify(approved: bool, signal_summary: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    aggregate = signal_summary.get("aggregate", {})
    if not approved:
        return (
            BLOCKER_NOT_APPROVED,
            NEXT_APPROVAL,
            False,
            "SoccerNet full analysis execution is not approved; run full-analysis approval first.",
        )
    if signal_summary.get("videoOpenable") is not True:
        return (
            BLOCKER_VIDEO_OPEN_FAILED,
            NEXT_VIDEO_OPEN_DEBUG,
            False,
            "Approved SoccerNet 224p video could not be opened for full analysis.",
        )
    if aggregate.get("processedFrameCount") != aggregate.get("approvedFrameCount"):
        return (
            BLOCKER_FRAME_COUNT_MISMATCH,
            NEXT_FRAME_READ_REPAIR,
            False,
            "SoccerNet full analysis did not process every approved frame.",
        )
    return (
        None,
        NEXT_REPORT_SMOKE,
        True,
        "SoccerNet full 224p video analysis executed and wrote aggregate frame-signal artifacts. Advance to full-analysis report smoke; training and promotion remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "full_analysis_execution_not_approved", "selected": primary_blocker == BLOCKER_NOT_APPROVED, "primaryBlocker": BLOCKER_NOT_APPROVED, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "video_open_failed", "selected": primary_blocker == BLOCKER_VIDEO_OPEN_FAILED, "primaryBlocker": BLOCKER_VIDEO_OPEN_FAILED, "nextRecommendedNextLever": NEXT_VIDEO_OPEN_DEBUG},
            {"condition": "frame_count_mismatch", "selected": primary_blocker == BLOCKER_FRAME_COUNT_MISMATCH, "primaryBlocker": BLOCKER_FRAME_COUNT_MISMATCH, "nextRecommendedNextLever": NEXT_FRAME_READ_REPAIR},
            {"condition": "full_analysis_report_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_REPORT_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Full Analysis Execution",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Full analysis executed: `{summary.get('fullAnalysisExecutionExecuted')}`",
            f"- Approved frames: `{summary.get('approvedFrameCount')}`",
            f"- Processed frames: `{summary.get('processedFrameCount')}`",
            f"- Unreadable frames: `{summary.get('unreadableFrameCount')}`",
            f"- Segment count: `{summary.get('segmentCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_full_analysis_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    approval_dir_name: str = DEFAULT_APPROVAL_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_full_video_frame_signal_execution",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, approval_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    approved = _approval_ready(inputs["approvalSummary"], inputs["executionContract"])
    signal_summary = _execute_full_video(inputs["executionContract"] or {}) if approved else {
        "schemaVersion": "soccernet_external_full_video_frame_signal_summary_v1",
        "generatedAt": _utc_now_iso(),
        "videoPath": (inputs["executionContract"] or {}).get("selectedVideoPath"),
        "videoExists": False,
        "videoOpenable": False,
        "aggregate": {"approvedFrameCount": 0, "processedFrameCount": 0, "unreadableFrameCount": 0, "segmentCount": 0},
        "segments": [],
    }
    product_payload = _product_payload(signal_summary)
    primary_blocker, next_lever, goal_achieved, english = _classify(approved, signal_summary)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    aggregate = signal_summary.get("aggregate", {})
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_full_analysis_execution",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_full_analysis_execution_approval",
        "fullAnalysisExecutionApproved": approved,
        "fullAnalysisExecutionExecuted": goal_achieved,
        "approvedFrameCount": aggregate.get("approvedFrameCount"),
        "reportedFrameCount": aggregate.get("reportedFrameCount"),
        "processedFrameCount": aggregate.get("processedFrameCount"),
        "unreadableFrameCount": aggregate.get("unreadableFrameCount"),
        "segmentCount": aggregate.get("segmentCount"),
        "archiveDownloadExecuted": False,
        "video720pMemberDownloadExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "fullVideoFrameSignalSummary": signal_summary,
        "fullAnalysisProductPayload": product_payload,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "full_analysis_execution_summary.json", summary)
    _write_json(output_root / "full_video_frame_signal_summary.json", signal_summary)
    _write_json(output_root / "full_analysis_timeline_segments.json", {"segments": signal_summary.get("segments", [])})
    _write_json(output_root / "full_analysis_product_payload.json", product_payload)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--approval-dir-name", default=DEFAULT_APPROVAL_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_full_video_frame_signal_execution")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_full_analysis_execution(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        approval_dir_name=args.approval_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
