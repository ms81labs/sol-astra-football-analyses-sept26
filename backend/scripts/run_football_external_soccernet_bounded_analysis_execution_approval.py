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
DEFAULT_PRODUCT_BRIDGE_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_bounded_analysis_execution_approval_v1"

BLOCKER_BRIDGE_MISSING = "football_external_soccernet_dry_run_product_bridge_missing"
BLOCKER_SCOPE_GAP = "football_external_soccernet_bounded_analysis_execution_scope_gap"

NEXT_PRODUCT_BRIDGE_SMOKE = "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke"
NEXT_SCOPE_REPAIR = "football_external_soccernet_bounded_analysis_execution_scope_repair"
NEXT_BOUNDED_EXECUTION = "football_external_soccernet_bounded_analysis_execution"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_bounded_analysis_execution_approval",
            "successCriteria": [
                "approve only the product-bridge 300-frame bounded execution scope",
                "keep full analysis, training, promotion, candidate readiness, and runtime mutation blocked",
                "do not execute analysis in this approval batch",
            ],
            "failureAdaptation": "If bridge payload is ready but scope is incomplete, repair only scope fields.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_bounded_analysis_scope_repair",
            "successCriteria": [
                "repair approved frame count and source payload linkage from product bridge truth",
                "keep boundedAnalysisExecutionExecuted false",
            ],
            "failureAdaptation": "If product bridge truth is missing, route back to product bridge smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_bounded_analysis_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before bounded execution if approval is unsafe",
            ],
            "failureAdaptation": "Route to product bridge smoke or scope repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, product_bridge_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    bridge_root = candidate_root / product_bridge_dir_name
    return {
        "candidateRoot": candidate_root,
        "bridgeSummary": _load_json(bridge_root / "dry_run_product_bridge_smoke_summary.json"),
        "bridgePayload": _load_json(bridge_root / "dry_run_product_bridge_payload.json"),
        "frameAudit": _load_json(bridge_root / "sampled_frame_existence_audit.json"),
    }


def _bridge_ready(
    summary: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    frame_audit: dict[str, Any] | None,
) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productBridgeSmokePassed") is True
        and int(summary.get("productPayloadFrameCount") or 0) == 300
        and int(summary.get("missingSampledFrameCount") or 0) == 0
        and summary.get("fullAnalysisReady") is False
        and summary.get("fullAnalysisExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(payload, dict)
        and payload.get("schemaVersion") == "soccernet_external_video_dry_run_product_bridge_v1"
        and int(payload.get("frameCount") or 0) == 300
        and payload.get("readiness", {}).get("productBridgeSmokePassed") is True
        and payload.get("readiness", {}).get("fullAnalysisReady") is False
        and isinstance(frame_audit, dict)
        and frame_audit.get("allSampledFramesExist") is True
        and int(frame_audit.get("missingSampledFrameCount") or 0) == 0
    )


def _scope_audit(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    frames = payload.get("frames") if isinstance(payload.get("frames"), list) else []
    return {
        "schemaVersion": "soccernet_external_bounded_analysis_execution_scope_v1",
        "generatedAt": _utc_now_iso(),
        "sourceProductBridgeBatch": "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke",
        "selectedVideoPath": payload.get("selectedVideoPath"),
        "approvedFrameCount": len(frames),
        "maxApprovedFrameCount": 300,
        "frameIndexSetPreview": [row.get("frameIndex") for row in frames[:10] if isinstance(row, dict)],
        "boundedAnalysisOnly": True,
        "fullAnalysisAllowed": False,
        "fullMatchFrameCountAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "candidateEvaluationReadinessAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "boundedAnalysisExecutionApproved": True,
        "boundedAnalysisExecutionExecuted": False,
        "approvalScope": "next_batch_only",
    }


def _execution_contract(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_bounded_analysis_execution",
        "sourceBatch": "football_external_soccernet_bounded_analysis_execution_approval",
        "selectedVideoPath": scope.get("selectedVideoPath"),
        "approvedFrameCount": scope.get("approvedFrameCount"),
        "maxApprovedFrameCount": scope.get("maxApprovedFrameCount"),
        "boundedAnalysisOnly": True,
        "fullAnalysisAllowed": False,
        "boundedAnalysisExecutionApproved": True,
        "boundedAnalysisExecutionExecuted": False,
        "allowedOperations": [
            "load_product_bridge_payload",
            "consume_300_sampled_frame_manifest",
            "run_lightweight_product_analysis_on_sampled_frames",
            "write_bounded_analysis_artifacts",
        ],
        "disallowedOperations": [
            "full_match_analysis",
            "training",
            "promotion",
            "candidate_evaluation_readiness",
            "runtime_default_mutation",
            "full_archive_download",
            "video_720p_member_download",
        ],
    }


def _classify(bridge_ready: bool, scope: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not bridge_ready:
        return (
            BLOCKER_BRIDGE_MISSING,
            NEXT_PRODUCT_BRIDGE_SMOKE,
            False,
            "SoccerNet dry-run product bridge truth is missing or unsafe; rerun product bridge smoke before bounded execution approval.",
        )
    if (
        scope.get("approvedFrameCount") != 300
        or scope.get("maxApprovedFrameCount") != 300
        or scope.get("boundedAnalysisExecutionApproved") is not True
        or scope.get("boundedAnalysisExecutionExecuted") is not False
        or scope.get("fullAnalysisAllowed") is not False
    ):
        return (
            BLOCKER_SCOPE_GAP,
            NEXT_SCOPE_REPAIR,
            False,
            "SoccerNet bounded analysis execution scope is incomplete or unsafe; repair scope before execution.",
        )
    return (
        None,
        NEXT_BOUNDED_EXECUTION,
        True,
        "Bounded SoccerNet analysis execution is approved for the next batch only. Full analysis, training, promotion, candidate readiness, and runtime mutation remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "dry_run_product_bridge_missing", "selected": primary_blocker == BLOCKER_BRIDGE_MISSING, "primaryBlocker": BLOCKER_BRIDGE_MISSING, "nextRecommendedNextLever": NEXT_PRODUCT_BRIDGE_SMOKE},
            {"condition": "bounded_analysis_execution_scope_gap", "selected": primary_blocker == BLOCKER_SCOPE_GAP, "primaryBlocker": BLOCKER_SCOPE_GAP, "nextRecommendedNextLever": NEXT_SCOPE_REPAIR},
            {"condition": "bounded_analysis_execution_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BOUNDED_EXECUTION},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Bounded Analysis Execution Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Bounded execution approved: `{summary.get('boundedAnalysisExecutionApproved')}`",
            f"- Bounded execution executed: `{summary.get('boundedAnalysisExecutionExecuted')}`",
            f"- Approved frame count: `{summary.get('approvedFrameCount')}`",
            f"- Full analysis allowed: `{summary.get('fullAnalysisAllowed')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_bounded_analysis_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    product_bridge_dir_name: str = DEFAULT_PRODUCT_BRIDGE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_bounded_analysis_execution_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, product_bridge_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _bridge_ready(inputs["bridgeSummary"], inputs["bridgePayload"], inputs["frameAudit"])
    scope = _scope_audit(inputs["bridgePayload"])
    contract = _execution_contract(scope)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, scope)
    if not goal_achieved:
        scope["boundedAnalysisExecutionApproved"] = False
        contract["boundedAnalysisExecutionApproved"] = False
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_bounded_analysis_execution_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke",
        "boundedAnalysisExecutionApproved": goal_achieved,
        "boundedAnalysisExecutionExecuted": False,
        "approvedFrameCount": scope.get("approvedFrameCount"),
        "maxApprovedFrameCount": scope.get("maxApprovedFrameCount"),
        "fullAnalysisAllowed": False,
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
        "boundedAnalysisScopeAudit": scope,
        "boundedAnalysisExecutionContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "bounded_analysis_execution_approval_summary.json", summary)
    _write_json(output_root / "bounded_analysis_scope_audit.json", scope)
    _write_json(output_root / "bounded_analysis_execution_contract.json", contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--product-bridge-dir-name", default=DEFAULT_PRODUCT_BRIDGE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_bounded_analysis_execution_approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_bounded_analysis_execution_approval(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        product_bridge_dir_name=args.product_bridge_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
