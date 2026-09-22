from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_CLOSEOUT_DIR_NAME = "football_external_soccernet_bounded_analysis_lane_closeout_v1"
DEFAULT_PRODUCT_DIR_NAME = "football_external_soccernet_video_product_path_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_full_analysis_execution_approval_v1"

BLOCKER_CLOSEOUT_MISSING = "football_external_soccernet_bounded_analysis_lane_closeout_missing"
BLOCKER_SCOPE_GAP = "football_external_soccernet_full_analysis_execution_scope_gap"

NEXT_CLOSEOUT = "football_external_soccernet_bounded_analysis_lane_closeout"
NEXT_SCOPE_REPAIR = "football_external_soccernet_full_analysis_scope_repair"
NEXT_FULL_EXECUTION = "football_external_soccernet_full_analysis_execution"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_full_analysis_execution_approval",
            "successCriteria": [
                "approve only the extracted 224p SoccerNet member for full-frame analysis",
                "record expected frame count, resolution, and source video path",
                "do not execute full analysis, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "If the video scope is incomplete, repair only from product video bundle truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_full_analysis_scope_repair",
            "successCriteria": [
                "repair video path, frame count, fps, and resolution from generated product bundle",
                "keep fullAnalysisExecutionExecuted false",
            ],
            "failureAdaptation": "If bounded closeout is missing, route back to bounded analysis closeout.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_full_analysis_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before full analysis execution if approval is unsafe",
            ],
            "failureAdaptation": "Route to bounded closeout or scope repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, closeout_dir_name: str, product_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    closeout_root = candidate_root / closeout_dir_name
    product_root = candidate_root / product_dir_name
    return {
        "candidateRoot": candidate_root,
        "closeoutSummary": _load_json(closeout_root / "bounded_analysis_lane_closeout_summary.json"),
        "approvalPrep": _load_json(closeout_root / "full_analysis_execution_approval_contract_prep.json"),
        "productBundle": _load_json(product_root / "external_video_product_bundle.json"),
    }


def _closeout_ready(summary: dict[str, Any] | None, prep: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("boundedAnalysisLaneClosed") is True
        and int(summary.get("reportedFrameCount") or 0) == 300
        and summary.get("fullAnalysisExecutionApprovalReady") is True
        and summary.get("fullAnalysisExecutionApproved") is False
        and summary.get("fullAnalysisExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(prep, dict)
        and prep.get("fullAnalysisExecutionApprovalReady") is True
        and prep.get("fullAnalysisExecutionApproved") is False
        and prep.get("fullAnalysisExecutionExecuted") is False
    )


def _video_ready(bundle: dict[str, Any] | None) -> bool:
    video = bundle.get("video") if isinstance(bundle, dict) else {}
    readiness = bundle.get("readiness") if isinstance(bundle, dict) else {}
    return bool(
        isinstance(video, dict)
        and video.get("exists") is True
        and bool(video.get("path"))
        and int(video.get("frameCount") or 0) > 0
        and int(video.get("width") or 0) > 0
        and int(video.get("height") or 0) > 0
        and float(video.get("fps") or 0.0) > 0.0
        and isinstance(readiness, dict)
        and readiness.get("externalVideoProductPathReady") is True
        and readiness.get("fullAnalysisReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
    )


def _scope_audit(bundle: dict[str, Any] | None) -> dict[str, Any]:
    bundle = bundle or {}
    video = bundle.get("video") if isinstance(bundle.get("video"), dict) else {}
    return {
        "schemaVersion": "soccernet_external_full_analysis_scope_audit_v1",
        "generatedAt": utc_now_iso(),
        "selectedVideoPath": video.get("path"),
        "videoExists": video.get("exists") is True,
        "fullFrameCountApproval": int(video.get("frameCount") or 0),
        "fps": video.get("fps"),
        "resolution": {
            "width": video.get("width"),
            "height": video.get("height"),
        },
        "approvedInputMember": "224p.mp4",
        "video720pMemberDownloadAllowed": False,
        "archiveDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "candidateEvaluationReadinessAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "fullAnalysisExecutionApproved": True,
        "fullAnalysisExecutionExecuted": False,
        "approvalScope": "next_batch_only",
    }


def _execution_contract(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_full_analysis_execution",
        "sourceBatch": "football_external_soccernet_full_analysis_execution_approval",
        "selectedVideoPath": scope.get("selectedVideoPath"),
        "approvedFrameCount": scope.get("fullFrameCountApproval"),
        "fps": scope.get("fps"),
        "resolution": scope.get("resolution"),
        "inputVideoMember": scope.get("approvedInputMember"),
        "fullAnalysisExecutionApproved": True,
        "fullAnalysisExecutionExecuted": False,
        "video720pMemberDownloadAllowed": False,
        "archiveDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "candidateEvaluationReadinessAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "allowedOperations": [
            "open_extracted_224p_video",
            "process_all_frames_in_224p_member",
            "write_full_analysis_artifacts",
            "write_full_analysis_report_payload",
        ],
        "disallowedOperations": [
            "training",
            "promotion",
            "candidate_evaluation_readiness",
            "runtime_default_mutation",
            "full_archive_download",
            "video_720p_member_download",
        ],
    }


def _classify(closeout_ready: bool, video_ready: bool, scope: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not closeout_ready:
        return (
            BLOCKER_CLOSEOUT_MISSING,
            NEXT_CLOSEOUT,
            False,
            "SoccerNet bounded analysis lane closeout is missing or unsafe; rerun closeout before full-analysis approval.",
        )
    if (
        not video_ready
        or not scope.get("selectedVideoPath")
        or int(scope.get("fullFrameCountApproval") or 0) <= 0
        or scope.get("fullAnalysisExecutionApproved") is not True
        or scope.get("fullAnalysisExecutionExecuted") is not False
    ):
        return (
            BLOCKER_SCOPE_GAP,
            NEXT_SCOPE_REPAIR,
            False,
            "SoccerNet full-analysis execution scope is incomplete or unsafe; repair scope before execution.",
        )
    return (
        None,
        NEXT_FULL_EXECUTION,
        True,
        "SoccerNet full-analysis execution is approved for the extracted 224p member. Full analysis has not executed yet; training, promotion, candidate readiness, and runtime mutation remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "bounded_analysis_lane_closeout_missing", "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING, "primaryBlocker": BLOCKER_CLOSEOUT_MISSING, "nextRecommendedNextLever": NEXT_CLOSEOUT},
            {"condition": "full_analysis_execution_scope_gap", "selected": primary_blocker == BLOCKER_SCOPE_GAP, "primaryBlocker": BLOCKER_SCOPE_GAP, "nextRecommendedNextLever": NEXT_SCOPE_REPAIR},
            {"condition": "full_analysis_execution_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_FULL_EXECUTION},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Full Analysis Execution Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Full analysis approved: `{summary.get('fullAnalysisExecutionApproved')}`",
            f"- Full analysis executed: `{summary.get('fullAnalysisExecutionExecuted')}`",
            f"- Approved frame count: `{summary.get('approvedFrameCount')}`",
            f"- Selected video path: `{summary.get('selectedVideoPath')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_full_analysis_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    closeout_dir_name: str = DEFAULT_CLOSEOUT_DIR_NAME,
    product_dir_name: str = DEFAULT_PRODUCT_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_full_analysis_execution_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, closeout_dir_name, product_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    closeout_ready = _closeout_ready(inputs["closeoutSummary"], inputs["approvalPrep"])
    video_ready = _video_ready(inputs["productBundle"])
    scope = _scope_audit(inputs["productBundle"])
    contract = _execution_contract(scope)
    primary_blocker, next_lever, goal_achieved, english = _classify(closeout_ready, video_ready, scope)
    if not goal_achieved:
        scope["fullAnalysisExecutionApproved"] = False
        contract["fullAnalysisExecutionApproved"] = False
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_full_analysis_execution_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_bounded_analysis_lane_closeout",
        "fullAnalysisExecutionApproved": goal_achieved,
        "fullAnalysisExecutionExecuted": False,
        "selectedVideoPath": scope.get("selectedVideoPath"),
        "approvedFrameCount": scope.get("fullFrameCountApproval"),
        "fps": scope.get("fps"),
        "resolution": scope.get("resolution"),
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
        "fullAnalysisScopeAudit": scope,
        "fullAnalysisExecutionContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "full_analysis_execution_approval_summary.json", summary)
    _write_json(output_root / "full_analysis_scope_audit.json", scope)
    _write_json(output_root / "full_analysis_execution_contract.json", contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--closeout-dir-name", default=DEFAULT_CLOSEOUT_DIR_NAME)
    parser.add_argument("--product-dir-name", default=DEFAULT_PRODUCT_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_full_analysis_execution_approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_full_analysis_execution_approval(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        closeout_dir_name=args.closeout_dir_name,
        product_dir_name=args.product_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
