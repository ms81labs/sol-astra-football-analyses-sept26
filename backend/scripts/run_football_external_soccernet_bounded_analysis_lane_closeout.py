from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_REPORT_DIR_NAME = "football_external_soccernet_bounded_analysis_report_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_bounded_analysis_lane_closeout_v1"

BLOCKER_REPORT_MISSING = "football_external_soccernet_bounded_analysis_report_missing"
BLOCKER_CLOSEOUT_GAP = "football_external_soccernet_bounded_analysis_closeout_gap"

NEXT_REPORT_SMOKE = "football_external_soccernet_bounded_analysis_report_smoke"
NEXT_CLOSEOUT_REPAIR = "football_external_soccernet_bounded_analysis_closeout_repair"
NEXT_FULL_ANALYSIS_APPROVAL = "football_external_soccernet_full_analysis_execution_approval"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_bounded_analysis_lane_closeout",
            "successCriteria": [
                "close the bounded 300-frame analysis lane",
                "prepare but do not approve full-analysis execution",
                "keep training, promotion, candidate readiness, and runtime mutation blocked",
            ],
            "failureAdaptation": "If bounded report truth is incomplete, repair closeout from report artifacts.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_bounded_analysis_closeout_repair",
            "successCriteria": [
                "repair capability matrix and next-approval prep fields from report truth",
                "do not execute full analysis",
            ],
            "failureAdaptation": "If report truth is missing, route back to report smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_bounded_analysis_closeout_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before full-analysis approval if closeout is unsafe",
            ],
            "failureAdaptation": "Route to report smoke or closeout repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, report_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    report_root = candidate_root / report_dir_name
    return {
        "candidateRoot": candidate_root,
        "reportSummary": _load_json(report_root / "bounded_analysis_report_smoke_summary.json"),
        "reportPayload": _load_json(report_root / "bounded_analysis_report_payload.json"),
    }


def _report_ready(summary: dict[str, Any] | None, payload: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("boundedAnalysisReportReady") is True
        and int(summary.get("reportedFrameCount") or 0) == 300
        and summary.get("fullAnalysisReady") is False
        and summary.get("fullAnalysisExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(payload, dict)
        and payload.get("schemaVersion") == "soccernet_external_bounded_analysis_report_payload_v1"
        and int(payload.get("reportedFrameCount") or 0) == 300
        and payload.get("readiness", {}).get("boundedAnalysisReportReady") is True
        and payload.get("readiness", {}).get("fullAnalysisReady") is False
    )


def _capability_matrix() -> dict[str, Any]:
    return {
        "schemaVersion": "soccernet_external_bounded_analysis_capability_matrix_v1",
        "generatedAt": _utc_now_iso(),
        "coveredCapabilities": {
            "externalVideoMemberExtracted": True,
            "videoOpenable": True,
            "boundedFrameSampling": True,
            "boundedProductBridge": True,
            "boundedFrameAnalysis": True,
            "boundedAnalysisReport": True,
        },
        "notCoveredCapabilities": {
            "fullMatchAnalysis": True,
            "ballLocalizationTruth": True,
            "detectorEvaluation": True,
            "training": True,
            "promotion": True,
            "runtimeDefaultMutation": True,
        },
    }


def _remaining_gap_analysis() -> dict[str, Any]:
    return {
        "schemaVersion": "soccernet_external_bounded_analysis_remaining_gap_v1",
        "generatedAt": _utc_now_iso(),
        "closedLane": "300_frame_bounded_video_to_product_report",
        "remainingGaps": [
            "full_match_analysis_not_executed",
            "ball_localization_truth_not_evaluated",
            "no_training_or_promotion_signal",
            "candidate_evaluation_readiness_not_requested",
        ],
        "nextApprovalRequired": "football_external_soccernet_full_analysis_execution_approval",
    }


def _full_analysis_approval_prep() -> dict[str, Any]:
    return {
        "schemaVersion": "soccernet_external_full_analysis_execution_approval_prep_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_soccernet_bounded_analysis_lane_closeout",
        "fullAnalysisExecutionApprovalReady": True,
        "fullAnalysisExecutionApproved": False,
        "fullAnalysisExecutionExecuted": False,
        "recommendedScope": {
            "inputVideo": "extracted_224p_soccernet_member",
            "requiresSeparateApproval": True,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    }


def _classify(report_ready: bool, prep: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not report_ready:
        return (
            BLOCKER_REPORT_MISSING,
            NEXT_REPORT_SMOKE,
            False,
            "SoccerNet bounded analysis report truth is missing or unsafe; rerun report smoke before closeout.",
        )
    if prep.get("fullAnalysisExecutionApprovalReady") is not True or prep.get("fullAnalysisExecutionApproved") is not False:
        return (
            BLOCKER_CLOSEOUT_GAP,
            NEXT_CLOSEOUT_REPAIR,
            False,
            "SoccerNet bounded analysis closeout cannot safely prepare the full-analysis approval gate.",
        )
    return (
        None,
        NEXT_FULL_ANALYSIS_APPROVAL,
        True,
        "SoccerNet bounded video-to-report lane is closed. Advance to full-analysis execution approval; do not execute full analysis without that gate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "bounded_analysis_report_missing", "selected": primary_blocker == BLOCKER_REPORT_MISSING, "primaryBlocker": BLOCKER_REPORT_MISSING, "nextRecommendedNextLever": NEXT_REPORT_SMOKE},
            {"condition": "bounded_analysis_closeout_gap", "selected": primary_blocker == BLOCKER_CLOSEOUT_GAP, "primaryBlocker": BLOCKER_CLOSEOUT_GAP, "nextRecommendedNextLever": NEXT_CLOSEOUT_REPAIR},
            {"condition": "full_analysis_execution_approval_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_FULL_ANALYSIS_APPROVAL},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Bounded Analysis Lane Closeout",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Bounded lane closed: `{summary.get('boundedAnalysisLaneClosed')}`",
            f"- Reported frame count: `{summary.get('reportedFrameCount')}`",
            f"- Full analysis approval ready: `{summary.get('fullAnalysisExecutionApprovalReady')}`",
            f"- Full analysis executed: `{summary.get('fullAnalysisExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_bounded_analysis_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    report_dir_name: str = DEFAULT_REPORT_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_bounded_analysis_lane_closeout",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, report_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _report_ready(inputs["reportSummary"], inputs["reportPayload"])
    matrix = _capability_matrix()
    gaps = _remaining_gap_analysis()
    prep = _full_analysis_approval_prep()
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, prep)
    if not goal_achieved:
        prep["fullAnalysisExecutionApprovalReady"] = False
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    reported_frame_count = (inputs["reportSummary"] or {}).get("reportedFrameCount")
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_bounded_analysis_lane_closeout",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_bounded_analysis_report_smoke",
        "boundedAnalysisLaneClosed": goal_achieved,
        "reportedFrameCount": reported_frame_count,
        "fullAnalysisExecutionApprovalReady": goal_achieved,
        "fullAnalysisExecutionApproved": False,
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
        "boundedAnalysisCapabilityMatrix": matrix,
        "remainingGapAnalysis": gaps,
        "fullAnalysisExecutionApprovalContractPrep": prep,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "bounded_analysis_lane_closeout_summary.json", summary)
    _write_json(output_root / "bounded_analysis_capability_matrix.json", matrix)
    _write_json(output_root / "remaining_gap_analysis.json", gaps)
    _write_json(output_root / "full_analysis_execution_approval_contract_prep.json", prep)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--report-dir-name", default=DEFAULT_REPORT_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_bounded_analysis_lane_closeout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_bounded_analysis_lane_closeout(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        report_dir_name=args.report_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
