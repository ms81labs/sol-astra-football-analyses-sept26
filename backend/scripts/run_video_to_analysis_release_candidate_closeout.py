from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_BACKLOG_DIR_NAME = "video_to_analysis_acceptance_report_product_backlog_v1"
DEFAULT_ROUTE_BINDING_DIR_NAME = "video_to_analysis_acceptance_report_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_release_candidate_closeout_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_V7_3_ROLLOUT_DIR_NAME = "v7_3_runtime_default_rollout_closeout_v1"

BLOCKER_BACKLOG_MISSING = "video_to_analysis_acceptance_report_product_backlog_missing"
BLOCKER_V7_3_ROLLOUT_MISSING = "video_to_analysis_v7_3_runtime_default_rollout_missing"
NEXT_BACKLOG = "video_to_analysis_acceptance_report_product_backlog"
NEXT_V7_3_ROLLOUT = "v7_3_runtime_default_rollout_closeout"
NEXT_OPERATOR_HANDOFF = "video_to_analysis_operator_handoff_pack"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_release_candidate_closeout",
                "successCriteria": [
                    "verify acceptance report route and product backlog truth",
                    "close the video-to-analysis release candidate without detector/training/runtime mutation",
                ],
                "failureAdaptation": "If backlog truth is missing, route back to acceptance report product backlog.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "release_candidate_evidence_repair",
                "successCriteria": ["repair only release-candidate evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "release_candidate_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to backlog, evidence repair, or operator handoff pack.",
            },
        ],
    }


def _backlog_ready(summary: dict[str, Any] | None, backlog: dict[str, Any] | None, route_summary: dict[str, Any] | None) -> bool:
    priority_order = backlog.get("priorityOrder") if isinstance(backlog, dict) else None
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("acceptanceReportProductBacklogReady") is True
        and summary.get("acceptanceCaseCount") == 5
        and summary.get("acceptancePassedCaseCount") == 5
        and summary.get("priorityBacklogItem") == "release_candidate_closeout"
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(priority_order, list)
        and priority_order[:1] == ["release_candidate_closeout"]
        and isinstance(route_summary, dict)
        and route_summary.get("acceptanceReportRouteReady") is True
        and route_summary.get("acceptanceCaseCount") == 5
        and route_summary.get("acceptancePassedCaseCount") == 5
        and route_summary.get("apiRouteStatusCode") == 200
        and route_summary.get("htmlRouteStatusCode") == 200
    )


def _v7_3_rollout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("runtimeDefaultChanged") is True
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("postRuntimeDefaultSourceRobustnessValidated") is True
        and summary.get("activeFailingSourceNotViableBlockerPresent") is False
        and summary.get("historicalSuiteBlockerArchived") is True
        and summary.get("nextRecommendedNextLever") == "video_to_analysis_release_candidate_closeout"
    )


def run_video_to_analysis_release_candidate_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    backlog_root = root / DEFAULT_BACKLOG_DIR_NAME
    route_root = root / DEFAULT_ROUTE_BINDING_DIR_NAME
    suite_root = Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME
    rollout_root = suite_root / DEFAULT_V7_3_ROLLOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    backlog_summary = load_json(backlog_root / "acceptance_report_product_backlog_summary.json")
    backlog = load_json(backlog_root / "acceptance_report_product_backlog.json")
    route_summary = load_json(route_root / "acceptance_report_route_binding_summary.json")
    rollout_summary = load_json(rollout_root / "runtime_default_rollout_closeout_summary.json")
    backlog_ready = _backlog_ready(backlog_summary, backlog, route_summary)
    rollout_ready = _v7_3_rollout_ready(rollout_summary)
    ready = backlog_ready and rollout_ready

    if ready:
        primary_blocker = None
        next_lever = NEXT_OPERATOR_HANDOFF
        goal = True
        english = "Video-to-analysis release candidate is closed. Build the operator handoff pack next."
    elif not backlog_ready:
        primary_blocker = BLOCKER_BACKLOG_MISSING
        next_lever = NEXT_BACKLOG
        goal = False
        english = "Acceptance report product backlog is missing or unsafe; build backlog before release-candidate closeout."
    else:
        primary_blocker = BLOCKER_V7_3_ROLLOUT_MISSING
        next_lever = NEXT_V7_3_ROLLOUT
        goal = False
        english = "The v7.3 runtime-default rollout is missing or unsafe; close that rollout before release-candidate closeout."

    capability_matrix = {
        "schemaVersion": "video_to_analysis_release_candidate_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "releaseCandidateCapabilities": {
            "acceptanceReportRouteReady": ready,
            "broaderRealVideoAcceptancePassed": ready,
            "normalStorageProductSmokeCovered": ready,
            "csvExportsCovered": ready,
            "htmlReportCovered": ready,
            "finishLineRouteCovered": ready,
            "v7_3RuntimeDefaultRolloutClosed": rollout_ready,
        },
        "guardrails": {
            "detectorEvaluationReady": False,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": rollout_ready,
            "downloadsReady": False,
        },
    }
    operator_snapshot = {
        "schemaVersion": "video_to_analysis_release_candidate_operator_snapshot_v1",
        "generatedAt": utc_now_iso(),
        "status": "release_candidate_closed" if ready else "blocked",
        "primaryRoute": "/video-to-analysis/acceptance-report" if ready else None,
        "apiRoute": "/api/video-to-analysis/acceptance-report" if ready else None,
        "activeRuntimeDefaultVersion": "v7.3" if ready else None,
        "runtimeDefaultRolloutClosed": rollout_ready,
        "nextRecommendedNextLever": next_lever,
    }
    runtime_default_release_candidate_audit = {
        "schemaVersion": "video_to_analysis_release_candidate_runtime_default_audit_v1",
        "generatedAt": utc_now_iso(),
        "rolloutSummaryPath": str(rollout_root / "runtime_default_rollout_closeout_summary.json"),
        "v7_3RuntimeDefaultRolloutClosed": rollout_ready,
        "runtimeDefaultMutationExecuted": bool((rollout_summary or {}).get("runtimeDefaultMutationExecuted")),
        "activeRuntimeDefaultVersion": "v7.3" if rollout_ready else None,
        "activeFailingSourceNotViableBlockerPresent": (rollout_summary or {}).get(
            "activeFailingSourceNotViableBlockerPresent"
        ),
        "historicalSuiteBlockerArchived": (rollout_summary or {}).get("historicalSuiteBlockerArchived"),
    }
    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = rollout_ready
    false_flags["runtimeDefaultMutationAllowed"] = rollout_ready
    summary = {
        "batchName": "video_to_analysis_release_candidate_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "videoToAnalysisReleaseCandidateClosed": goal,
        "videoToAnalysisProductPathReady": goal,
        "acceptanceCaseCount": 5 if goal else 0,
        "acceptancePassedCaseCount": 5 if goal else 0,
        **false_flags,
        "runtimeDefaultRolloutClosed": rollout_ready,
        "activeRuntimeDefaultVersion": "v7.3" if rollout_ready else None,
        "activeFailingSourceNotViableBlockerPresent": (rollout_summary or {}).get(
            "activeFailingSourceNotViableBlockerPresent"
        ),
        "historicalSuiteBlockerArchived": (rollout_summary or {}).get("historicalSuiteBlockerArchived"),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "product_backlog_missing",
                "selected": primary_blocker == BLOCKER_BACKLOG_MISSING,
                "primaryBlocker": BLOCKER_BACKLOG_MISSING,
                "nextRecommendedNextLever": NEXT_BACKLOG,
            },
            {
                "condition": "v7_3_runtime_default_rollout_missing",
                "selected": primary_blocker == BLOCKER_V7_3_ROLLOUT_MISSING,
                "primaryBlocker": BLOCKER_V7_3_ROLLOUT_MISSING,
                "nextRecommendedNextLever": NEXT_V7_3_ROLLOUT,
            },
            {
                "condition": "release_candidate_closed",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_OPERATOR_HANDOFF,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="release_candidate_closeout_summary.json",
        summary=summary,
        artifacts={
            "release_candidate_capability_matrix.json": capability_matrix,
            "release_candidate_operator_snapshot.json": operator_snapshot,
            "runtime_default_release_candidate_audit.json": runtime_default_release_candidate_audit,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Release Candidate Closeout",
    )


def main() -> None:
    main_for("Close video-to-analysis release candidate.", run_video_to_analysis_release_candidate_closeout)


if __name__ == "__main__":
    main()
