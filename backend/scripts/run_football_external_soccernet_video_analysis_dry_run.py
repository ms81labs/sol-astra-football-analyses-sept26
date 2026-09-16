from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
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
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_v1"

BLOCKER_NOT_APPROVED = "football_external_soccernet_video_analysis_dry_run_not_approved"
BLOCKER_VIDEO_OPEN_FAILED = "football_external_soccernet_video_analysis_dry_run_video_open_failed"
BLOCKER_FRAME_SAMPLE_FAILED = "football_external_soccernet_video_analysis_dry_run_frame_sample_failed"

NEXT_APPROVAL = "football_external_soccernet_video_analysis_dry_run_approval"
NEXT_VIDEO_OPEN_DEBUG = "football_external_soccernet_video_analysis_dry_run_video_open_debug"
NEXT_SAMPLE_REPAIR = "football_external_soccernet_video_analysis_dry_run_sampling_repair"
NEXT_PRODUCT_BRIDGE_SMOKE = "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_video_bounded_frame_dry_run",
            "successCriteria": [
                "open the approved SoccerNet 224p video",
                "sample only the approved bounded frame count",
                "write dry-run artifacts without full analysis, training, promotion, or runtime mutation",
            ],
            "failureAdaptation": "If video open or sampling fails, route to the narrow repair family.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_video_dry_run_sampling_repair",
            "successCriteria": [
                "repair only frame stride, max-frame, or selected-video linkage from approval truth",
                "do not broaden scope beyond the approval contract",
            ],
            "failureAdaptation": "If approval itself is invalid, return to dry-run approval.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_video_dry_run_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before product bridge smoke if bounded sampling is unsafe",
            ],
            "failureAdaptation": "Route to approval, video-open debug, or sampling repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, approval_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / approval_dir_name
    return {
        "candidateRoot": candidate_root,
        "approvalSummary": _load_json(approval_root / "video_analysis_dry_run_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "video_analysis_dry_run_contract.json"),
        "scopeAudit": _load_json(approval_root / "dry_run_scope_audit.json"),
    }


def _approval_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("analysisDryRunApproved") is True
        and summary.get("analysisExecutionApproved") is True
        and summary.get("analysisExecutionExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(contract, dict)
        and contract.get("analysisDryRunApproved") is True
        and contract.get("analysisExecutionApproved") is True
        and contract.get("analysisExecutionExecuted") is False
        and contract.get("boundedDryRunOnly") is True
        and contract.get("fullAnalysisAllowed") is False
        and contract.get("runtimeDefaultMutationAllowed") is False
        and bool(contract.get("selectedVideoPath"))
    )


def _sample_indices(frame_count: int, max_frames: int, stride: int) -> list[int]:
    if frame_count <= 0:
        return []
    stride = max(1, stride)
    indices = list(range(0, frame_count, stride))
    if not indices:
        indices = [0]
    return indices[: max(1, max_frames)]


def _sample_video(contract: dict[str, Any] | None, output_root: Path) -> dict[str, Any]:
    contract = contract or {}
    video_path = Path(str(contract.get("selectedVideoPath") or ""))
    max_frames = int(contract.get("maxDryRunFrames") or 0)
    stride = int(contract.get("sampleEveryNFrames") or 1)
    if not video_path.exists():
        return {
            "selectedVideoPath": str(video_path),
            "videoExists": False,
            "videoOpenable": False,
            "sampledFrameCount": 0,
            "sampledFrames": [],
        }
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        return {
            "selectedVideoPath": str(video_path),
            "videoExists": True,
            "videoOpenable": False,
            "sampledFrameCount": 0,
            "sampledFrames": [],
        }
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    sampled_dir = output_root / "sampled_frames"
    sampled_dir.mkdir(parents=True, exist_ok=True)
    sampled: list[dict[str, Any]] = []
    for frame_index in _sample_indices(frame_count, max_frames, stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        out = sampled_dir / f"frame_{frame_index:06d}.jpg"
        cv2.imwrite(str(out), frame)
        sampled.append(
            {
                "frameIndex": frame_index,
                "relativePath": str(out.relative_to(output_root)),
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
            }
        )
    cap.release()
    return {
        "selectedVideoPath": str(video_path),
        "videoExists": True,
        "videoOpenable": True,
        "frameCount": frame_count,
        "fps": fps,
        "width": width,
        "height": height,
        "maxDryRunFrames": max_frames,
        "sampleEveryNFrames": stride,
        "sampledFrameCount": len(sampled),
        "sampledFrames": sampled,
    }


def _classify(approval_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_NOT_APPROVED,
            NEXT_APPROVAL,
            False,
            "SoccerNet video analysis dry run is not approved; run the approval batch first.",
        )
    if audit.get("videoOpenable") is not True:
        return (
            BLOCKER_VIDEO_OPEN_FAILED,
            NEXT_VIDEO_OPEN_DEBUG,
            False,
            "Approved SoccerNet video could not be opened for the bounded dry run.",
        )
    if int(audit.get("sampledFrameCount") or 0) <= 0:
        return (
            BLOCKER_FRAME_SAMPLE_FAILED,
            NEXT_SAMPLE_REPAIR,
            False,
            "Approved SoccerNet video opened but no dry-run frames could be sampled.",
        )
    return (
        None,
        NEXT_PRODUCT_BRIDGE_SMOKE,
        True,
        "Bounded SoccerNet video analysis dry run sampled approved frames and wrote artifacts. Advance to product bridge smoke; full analysis remains unapproved.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "dry_run_not_approved", "selected": primary_blocker == BLOCKER_NOT_APPROVED, "primaryBlocker": BLOCKER_NOT_APPROVED, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "video_open_failed", "selected": primary_blocker == BLOCKER_VIDEO_OPEN_FAILED, "primaryBlocker": BLOCKER_VIDEO_OPEN_FAILED, "nextRecommendedNextLever": NEXT_VIDEO_OPEN_DEBUG},
            {"condition": "frame_sample_failed", "selected": primary_blocker == BLOCKER_FRAME_SAMPLE_FAILED, "primaryBlocker": BLOCKER_FRAME_SAMPLE_FAILED, "nextRecommendedNextLever": NEXT_SAMPLE_REPAIR},
            {"condition": "dry_run_product_bridge_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_BRIDGE_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Analysis Dry Run",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Analysis execution executed: `{summary.get('analysisExecutionExecuted')}`",
            f"- Full analysis executed: `{summary.get('fullAnalysisExecuted')}`",
            f"- Video openable: `{summary.get('videoOpenable')}`",
            f"- Sampled frames: `{summary.get('sampledFrameCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_analysis_dry_run(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    approval_dir_name: str = DEFAULT_APPROVAL_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_video_bounded_frame_dry_run",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, approval_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    approved = _approval_ready(inputs["approvalSummary"], inputs["approvalContract"])
    audit = _sample_video(inputs["approvalContract"], output_root) if approved else {
        "selectedVideoPath": (inputs["approvalContract"] or {}).get("selectedVideoPath"),
        "videoExists": False,
        "videoOpenable": False,
        "sampledFrameCount": 0,
        "sampledFrames": [],
    }
    primary_blocker, next_lever, goal_achieved, english = _classify(approved, audit)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    manifest = {
        "schemaVersion": "soccernet_external_video_analysis_dry_run_manifest_v1",
        "generatedAt": generated_at,
        "sourceApprovalBatch": "football_external_soccernet_video_analysis_dry_run_approval",
        "selectedVideoPath": audit.get("selectedVideoPath"),
        "sampledFrames": audit.get("sampledFrames", []),
        "fullAnalysisExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "candidateEvaluationExecuted": False,
    }
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_analysis_dry_run",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_analysis_dry_run_approval",
        "analysisExecutionApproved": approved,
        "analysisExecutionExecuted": goal_achieved,
        "fullAnalysisExecuted": False,
        "selectedVideoPath": audit.get("selectedVideoPath"),
        "videoExists": audit.get("videoExists"),
        "videoOpenable": audit.get("videoOpenable"),
        "frameCount": audit.get("frameCount"),
        "fps": audit.get("fps"),
        "width": audit.get("width"),
        "height": audit.get("height"),
        "maxDryRunFrames": audit.get("maxDryRunFrames") or (inputs["approvalContract"] or {}).get("maxDryRunFrames"),
        "sampleEveryNFrames": audit.get("sampleEveryNFrames") or (inputs["approvalContract"] or {}).get("sampleEveryNFrames"),
        "sampledFrameCount": audit.get("sampledFrameCount"),
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
        "boundedFrameSampleAudit": audit,
        "dryRunArtifactManifest": manifest,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_analysis_dry_run_summary.json", summary)
    _write_json(output_root / "bounded_frame_sample_audit.json", audit)
    _write_json(output_root / "dry_run_artifact_manifest.json", manifest)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_video_bounded_frame_dry_run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_analysis_dry_run(
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
