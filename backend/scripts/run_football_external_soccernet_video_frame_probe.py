from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_EXTRACT_DIR_NAME = "football_external_soccernet_video_member_extract_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_frame_probe_v1"

BLOCKER_EXTRACT_MISSING = "football_external_soccernet_video_member_extract_missing"
BLOCKER_VIDEO_OPEN_FAILED = "football_external_soccernet_video_frame_probe_open_failed"
BLOCKER_FRAME_SAMPLE_FAILED = "football_external_soccernet_video_frame_probe_sample_failed"

NEXT_EXTRACT = "football_external_soccernet_video_member_extract"
NEXT_OPEN_DEBUG = "football_external_soccernet_video_open_debug"
NEXT_SAMPLE_DEBUG = "football_external_soccernet_video_frame_sample_debug"
NEXT_PRODUCT_PATH_SMOKE = "football_external_soccernet_video_product_path_smoke"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_extracted_video_frame_probe",
            "successCriteria": [
                "open the extracted 224p MP4 with local video tooling",
                "record FPS/dimensions/frame count",
                "export a few sampled frames for inspection",
            ],
            "failureAdaptation": "If video cannot open, route to video-open debug.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_video_frame_probe_contract_repair",
            "successCriteria": [
                "repair extracted video path or inventory linkage from saved extract artifacts",
                "do not download more video or train",
            ],
            "failureAdaptation": "If frames still cannot be sampled, route to frame sample debug.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_video_frame_probe_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before product-path smoke if no sampled frames exist",
            ],
            "failureAdaptation": "Route to extract, open debug, or sample debug.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    extract_root = candidate_root / DEFAULT_EXTRACT_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "extractRoot": extract_root,
        "extractSummary": _load_json(extract_root / "video_member_extract_summary.json"),
        "inventory": _load_json(extract_root / "extracted_video_member_inventory.json"),
    }


def _extract_ready(summary: dict[str, Any] | None, inventory: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoMemberExtractionExecuted") is True
        and summary.get("archiveDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(inventory, dict)
        and int(inventory.get("extractedVideoFileCount") or 0) > 0
    )


def _video_path(extract_root: Path, inventory: dict[str, Any] | None) -> Path | None:
    files = inventory.get("extractedVideoFiles") if isinstance(inventory, dict) else None
    if not isinstance(files, list) or not files or not isinstance(files[0], dict):
        return None
    relative = files[0].get("relativePath")
    if not relative:
        return None
    return extract_root / str(relative)


def _sample_indices(frame_count: int, sample_frame_count: int) -> list[int]:
    if frame_count <= 0:
        return list(range(max(sample_frame_count, 1)))
    if sample_frame_count <= 1:
        return [0]
    return sorted({round(i * (frame_count - 1) / (sample_frame_count - 1)) for i in range(sample_frame_count)})


def _probe_video(video_path: Path | None, output_root: Path, sample_frame_count: int) -> dict[str, Any]:
    if video_path is None or not video_path.exists():
        return {"videoPath": str(video_path) if video_path else None, "videoExists": False, "videoOpenable": False, "sampledFrameCount": 0}
    cap = cv2.VideoCapture(str(video_path))
    opened = bool(cap.isOpened())
    if not opened:
        cap.release()
        return {"videoPath": str(video_path), "videoExists": True, "videoOpenable": False, "sampledFrameCount": 0}
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frames_dir = output_root / "sampled_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    sampled = []
    for index in _sample_indices(frame_count, sample_frame_count):
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        out = frames_dir / f"frame_{index:06d}.jpg"
        cv2.imwrite(str(out), frame)
        sampled.append({"frameIndex": index, "relativePath": str(out.relative_to(output_root)), "width": int(frame.shape[1]), "height": int(frame.shape[0])})
    cap.release()
    return {
        "videoPath": str(video_path),
        "videoExists": True,
        "videoOpenable": True,
        "frameCount": frame_count,
        "fps": fps,
        "width": width,
        "height": height,
        "sampledFrameCount": len(sampled),
        "sampledFrames": sampled,
    }


def _classify(extract_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not extract_ready:
        return (
            BLOCKER_EXTRACT_MISSING,
            NEXT_EXTRACT,
            False,
            "Extracted SoccerNet video member truth is missing or unsafe; rerun video member extraction.",
        )
    if audit.get("videoOpenable") is not True:
        return (
            BLOCKER_VIDEO_OPEN_FAILED,
            NEXT_OPEN_DEBUG,
            False,
            "Extracted SoccerNet video could not be opened by local video tooling.",
        )
    if int(audit.get("sampledFrameCount") or 0) <= 0:
        return (
            BLOCKER_FRAME_SAMPLE_FAILED,
            NEXT_SAMPLE_DEBUG,
            False,
            "Extracted SoccerNet video opened but no frames could be sampled.",
        )
    return (
        None,
        NEXT_PRODUCT_PATH_SMOKE,
        True,
        "Extracted SoccerNet 224p video opened and sampled frames were written. Advance to video product-path smoke without training or promotion.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "video_member_extract_missing", "selected": primary_blocker == BLOCKER_EXTRACT_MISSING, "primaryBlocker": BLOCKER_EXTRACT_MISSING, "nextRecommendedNextLever": NEXT_EXTRACT},
            {"condition": "video_open_failed", "selected": primary_blocker == BLOCKER_VIDEO_OPEN_FAILED, "primaryBlocker": BLOCKER_VIDEO_OPEN_FAILED, "nextRecommendedNextLever": NEXT_OPEN_DEBUG},
            {"condition": "video_frame_sample_failed", "selected": primary_blocker == BLOCKER_FRAME_SAMPLE_FAILED, "primaryBlocker": BLOCKER_FRAME_SAMPLE_FAILED, "nextRecommendedNextLever": NEXT_SAMPLE_DEBUG},
            {"condition": "video_product_path_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_PATH_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Frame Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Video openable: `{summary.get('videoOpenable')}`",
            f"- Frame count: `{summary.get('frameCount')}`",
            f"- FPS: `{summary.get('fps')}`",
            f"- Sampled frames: `{summary.get('sampledFrameCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_frame_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    sample_frame_count: int = 5,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_extracted_video_frame_probe",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _extract_ready(inputs["extractSummary"], inputs["inventory"])
    audit = _probe_video(_video_path(inputs["extractRoot"], inputs["inventory"]), output_root, sample_frame_count)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, audit)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_frame_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_member_extract",
        "videoFrameProbePassed": goal_achieved,
        "videoOpenable": audit.get("videoOpenable") is True,
        "frameCount": audit.get("frameCount"),
        "fps": audit.get("fps"),
        "width": audit.get("width"),
        "height": audit.get("height"),
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "videoFrameProbeAudit": audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_frame_probe_summary.json", summary)
    _write_json(output_root / "video_frame_probe_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--sample-frame-count", type=int, default=5)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_extracted_video_frame_probe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_frame_probe(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        sample_frame_count=args.sample_frame_count,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
