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
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_bounded_analysis_execution_approval_v1"
DEFAULT_PRODUCT_BRIDGE_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
DEFAULT_DRY_RUN_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_bounded_analysis_execution_v1"

BLOCKER_NOT_APPROVED = "football_external_soccernet_bounded_analysis_execution_not_approved"
BLOCKER_FRAME_MANIFEST_GAP = "football_external_soccernet_bounded_analysis_frame_manifest_gap"
BLOCKER_EXECUTION_FAILED = "football_external_soccernet_bounded_analysis_execution_failed"

NEXT_APPROVAL = "football_external_soccernet_bounded_analysis_execution_approval"
NEXT_FRAME_MANIFEST_REPAIR = "football_external_soccernet_bounded_analysis_frame_manifest_repair"
NEXT_EXECUTION_DEBUG = "football_external_soccernet_bounded_analysis_execution_debug"
NEXT_REPORT_SMOKE = "football_external_soccernet_bounded_analysis_report_smoke"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_bounded_frame_analysis_execution",
            "successCriteria": [
                "consume exactly the approved 300-frame product bridge manifest",
                "compute lightweight image/frame statistics",
                "write bounded analysis artifacts without full analysis, training, promotion, or runtime mutation",
            ],
            "failureAdaptation": "If frame references are incomplete, repair only the bounded frame manifest.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_bounded_analysis_frame_manifest_repair",
            "successCriteria": [
                "repair only sampled-frame path resolution from dry-run/product-bridge truth",
                "do not expand beyond the approved 300-frame scope",
            ],
            "failureAdaptation": "If approval is invalid, route back to bounded execution approval.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_bounded_analysis_execution_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before report smoke if bounded execution is unsafe",
            ],
            "failureAdaptation": "Route to approval, frame-manifest repair, or execution debug.",
        },
    ]


def _load_inputs(
    storage_root: Path,
    candidate_name: str,
    approval_dir_name: str,
    product_bridge_dir_name: str,
    dry_run_dir_name: str,
) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / approval_dir_name
    bridge_root = candidate_root / product_bridge_dir_name
    dry_run_root = candidate_root / dry_run_dir_name
    return {
        "candidateRoot": candidate_root,
        "dryRunRoot": dry_run_root,
        "approvalSummary": _load_json(approval_root / "bounded_analysis_execution_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "bounded_analysis_execution_contract.json"),
        "bridgePayload": _load_json(bridge_root / "dry_run_product_bridge_payload.json"),
    }


def _approval_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("boundedAnalysisExecutionApproved") is True
        and summary.get("boundedAnalysisExecutionExecuted") is False
        and int(summary.get("approvedFrameCount") or 0) == 300
        and summary.get("fullAnalysisAllowed") is False
        and summary.get("fullAnalysisExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(contract, dict)
        and contract.get("boundedAnalysisExecutionApproved") is True
        and contract.get("boundedAnalysisExecutionExecuted") is False
        and int(contract.get("approvedFrameCount") or 0) == 300
        and int(contract.get("maxApprovedFrameCount") or 0) == 300
        and contract.get("fullAnalysisAllowed") is False
    )


def _resolve_frame_path(dry_run_root: Path, relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    path = dry_run_root / relative_path
    if path.exists():
        return path
    # Some tests or repaired payloads may include paths relative to the candidate root.
    candidate_root = dry_run_root.parent
    path = candidate_root / relative_path
    if path.exists():
        return path
    return None


def _frame_metrics(path: Path, row: dict[str, Any]) -> dict[str, Any] | None:
    image = cv2.imread(str(path))
    if image is None:
        return None
    mean_bgr = image.mean(axis=(0, 1))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    green_channel = image[:, :, 1].astype("float32")
    red_channel = image[:, :, 2].astype("float32")
    blue_channel = image[:, :, 0].astype("float32")
    green_dominance = float((green_channel - ((red_channel + blue_channel) / 2.0)).mean())
    green_dominant_ratio = float(((green_channel > red_channel + 8) & (green_channel > blue_channel + 8)).mean())
    return {
        "frameIndex": row.get("frameIndex"),
        "relativePath": row.get("relativePath"),
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "meanBrightness": round(float(gray.mean()), 6),
        "meanBlue": round(float(mean_bgr[0]), 6),
        "meanGreen": round(float(mean_bgr[1]), 6),
        "meanRed": round(float(mean_bgr[2]), 6),
        "greenDominance": round(green_dominance, 6),
        "greenDominantPixelRatio": round(green_dominant_ratio, 6),
        "edgeDensity": round(float((edges > 0).mean()), 6),
    }


def _analyze_frames(dry_run_root: Path, bridge_payload: dict[str, Any] | None) -> dict[str, Any]:
    frames = bridge_payload.get("frames") if isinstance(bridge_payload, dict) else []
    if not isinstance(frames, list):
        frames = []
    analyzed: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    for row in frames:
        if not isinstance(row, dict):
            continue
        path = _resolve_frame_path(dry_run_root, row.get("relativePath"))
        if path is None:
            missing.append(row)
            continue
        metrics = _frame_metrics(path, row)
        if metrics is None:
            unreadable.append(row)
            continue
        analyzed.append(metrics)
    brightness = [float(row["meanBrightness"]) for row in analyzed]
    green_ratio = [float(row["greenDominantPixelRatio"]) for row in analyzed]
    edge_density = [float(row["edgeDensity"]) for row in analyzed]
    aggregate = {
        "requestedFrameCount": len(frames),
        "analyzedFrameCount": len(analyzed),
        "missingFrameCount": len(missing),
        "unreadableFrameCount": len(unreadable),
        "meanBrightnessP50": round(statistics.median(brightness), 6) if brightness else None,
        "meanBrightnessMin": round(min(brightness), 6) if brightness else None,
        "meanBrightnessMax": round(max(brightness), 6) if brightness else None,
        "greenDominantPixelRatioP50": round(statistics.median(green_ratio), 6) if green_ratio else None,
        "edgeDensityP50": round(statistics.median(edge_density), 6) if edge_density else None,
    }
    return {
        "schemaVersion": "soccernet_external_bounded_frame_analysis_v1",
        "generatedAt": _utc_now_iso(),
        "aggregate": aggregate,
        "frames": analyzed,
        "missingFrames": missing,
        "unreadableFrames": unreadable,
    }


def _product_payload(analysis: dict[str, Any], source_payload: dict[str, Any] | None) -> dict[str, Any]:
    aggregate = analysis.get("aggregate", {})
    return {
        "schemaVersion": "soccernet_external_bounded_analysis_product_payload_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_soccernet_bounded_analysis_execution",
        "selectedVideoPath": (source_payload or {}).get("selectedVideoPath"),
        "frameCount": aggregate.get("analyzedFrameCount"),
        "aggregateFrameSignals": aggregate,
        "readiness": {
            "boundedAnalysisExecutionReady": aggregate.get("analyzedFrameCount") == 300,
            "boundedReportReady": aggregate.get("analyzedFrameCount") == 300,
            "fullAnalysisReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "candidateEvaluationReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": [
            "300-frame bounded sample only",
            "lightweight frame-statistics analysis only",
            "not ball localization truth",
            "not full match analysis",
            "not training evidence",
            "does not mutate runtime defaults",
        ],
    }


def _classify(approved: bool, analysis: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    aggregate = analysis.get("aggregate", {})
    if not approved:
        return (
            BLOCKER_NOT_APPROVED,
            NEXT_APPROVAL,
            False,
            "SoccerNet bounded analysis execution is not approved; run the approval batch first.",
        )
    if aggregate.get("requestedFrameCount") != 300 or aggregate.get("missingFrameCount") != 0:
        return (
            BLOCKER_FRAME_MANIFEST_GAP,
            NEXT_FRAME_MANIFEST_REPAIR,
            False,
            "SoccerNet bounded frame manifest is incomplete; repair sampled-frame paths before analysis.",
        )
    if aggregate.get("analyzedFrameCount") != 300 or aggregate.get("unreadableFrameCount") != 0:
        return (
            BLOCKER_EXECUTION_FAILED,
            NEXT_EXECUTION_DEBUG,
            False,
            "SoccerNet bounded analysis could not read all approved sampled frames.",
        )
    return (
        None,
        NEXT_REPORT_SMOKE,
        True,
        "SoccerNet bounded 300-frame analysis executed and produced product payload metrics. Advance to bounded analysis report smoke; full analysis remains blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "bounded_analysis_execution_not_approved", "selected": primary_blocker == BLOCKER_NOT_APPROVED, "primaryBlocker": BLOCKER_NOT_APPROVED, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "bounded_analysis_frame_manifest_gap", "selected": primary_blocker == BLOCKER_FRAME_MANIFEST_GAP, "primaryBlocker": BLOCKER_FRAME_MANIFEST_GAP, "nextRecommendedNextLever": NEXT_FRAME_MANIFEST_REPAIR},
            {"condition": "bounded_analysis_execution_failed", "selected": primary_blocker == BLOCKER_EXECUTION_FAILED, "primaryBlocker": BLOCKER_EXECUTION_FAILED, "nextRecommendedNextLever": NEXT_EXECUTION_DEBUG},
            {"condition": "bounded_analysis_report_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_REPORT_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Bounded Analysis Execution",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Bounded execution executed: `{summary.get('boundedAnalysisExecutionExecuted')}`",
            f"- Analyzed frames: `{summary.get('analyzedFrameCount')}`",
            f"- Missing frames: `{summary.get('missingFrameCount')}`",
            f"- Full analysis executed: `{summary.get('fullAnalysisExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_bounded_analysis_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    approval_dir_name: str = DEFAULT_APPROVAL_DIR_NAME,
    product_bridge_dir_name: str = DEFAULT_PRODUCT_BRIDGE_DIR_NAME,
    dry_run_dir_name: str = DEFAULT_DRY_RUN_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_bounded_frame_analysis_execution",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, approval_dir_name, product_bridge_dir_name, dry_run_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    approved = _approval_ready(inputs["approvalSummary"], inputs["approvalContract"])
    analysis = _analyze_frames(inputs["dryRunRoot"], inputs["bridgePayload"]) if approved else {
        "schemaVersion": "soccernet_external_bounded_frame_analysis_v1",
        "generatedAt": _utc_now_iso(),
        "aggregate": {"requestedFrameCount": 0, "analyzedFrameCount": 0, "missingFrameCount": 0, "unreadableFrameCount": 0},
        "frames": [],
        "missingFrames": [],
        "unreadableFrames": [],
    }
    product_payload = _product_payload(analysis, inputs["bridgePayload"])
    primary_blocker, next_lever, goal_achieved, english = _classify(approved, analysis)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    aggregate = analysis.get("aggregate", {})
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_bounded_analysis_execution",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_bounded_analysis_execution_approval",
        "boundedAnalysisExecutionApproved": approved,
        "boundedAnalysisExecutionExecuted": goal_achieved,
        "requestedFrameCount": aggregate.get("requestedFrameCount"),
        "analyzedFrameCount": aggregate.get("analyzedFrameCount"),
        "missingFrameCount": aggregate.get("missingFrameCount"),
        "unreadableFrameCount": aggregate.get("unreadableFrameCount"),
        "fullAnalysisReady": False,
        "fullAnalysisExecuted": False,
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
        "boundedFrameAnalysis": analysis,
        "boundedAnalysisProductPayload": product_payload,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "bounded_analysis_execution_summary.json", summary)
    _write_json(output_root / "bounded_frame_analysis.json", analysis)
    _write_json(output_root / "bounded_analysis_product_payload.json", product_payload)
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
    parser.add_argument("--product-bridge-dir-name", default=DEFAULT_PRODUCT_BRIDGE_DIR_NAME)
    parser.add_argument("--dry-run-dir-name", default=DEFAULT_DRY_RUN_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_bounded_frame_analysis_execution")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_bounded_analysis_execution(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        approval_dir_name=args.approval_dir_name,
        product_bridge_dir_name=args.product_bridge_dir_name,
        dry_run_dir_name=args.dry_run_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
