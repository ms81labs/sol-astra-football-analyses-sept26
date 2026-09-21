from __future__ import annotations

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
    write_outcome,
)

DEFAULT_ROUTE_BINDING_DIR_NAME = "video_to_analysis_acceptance_report_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_acceptance_report_product_backlog_v1"

BLOCKER_ROUTE_BINDING_MISSING = "video_to_analysis_acceptance_report_route_binding_missing"
NEXT_ROUTE_BINDING = "video_to_analysis_acceptance_report_route_binding"
NEXT_RELEASE_CANDIDATE_CLOSEOUT = "video_to_analysis_release_candidate_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_acceptance_report_product_backlog",
                "successCriteria": [
                    "turn accepted five-case report route truth into a product backlog",
                    "select the release-candidate closeout as the next lever",
                ],
                "failureAdaptation": "If route binding is missing, route back to acceptance report route binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "acceptance_report_product_backlog_scope_repair",
                "successCriteria": ["repair only backlog scope and priority order"],
                "failureAdaptation": "If product backlog remains unsafe, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "acceptance_report_product_backlog_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to route binding, backlog scope repair, or release-candidate closeout.",
            },
        ],
    }


def _route_binding_ready(summary: dict[str, Any] | None, view_model: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("acceptanceReportRouteReady") is True
        and summary.get("acceptanceCaseCount") == 5
        and summary.get("acceptancePassedCaseCount") == 5
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
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
        and isinstance(view_model, dict)
        and view_model.get("schemaVersion") == "video_to_analysis_acceptance_report_view_model_v1"
        and view_model.get("acceptanceResult") == "passed"
        and isinstance(contract, dict)
        and contract.get("apiRoutePath") == "/api/video-to-analysis/acceptance-report"
        and contract.get("htmlRoutePath") == "/video-to-analysis/acceptance-report"
        and contract.get("allowsTraining") is False
        and contract.get("allowsPromotion") is False
        and contract.get("allowsRuntimeDefaultMutation") is False
    )


def _backlog() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_acceptance_report_product_backlog_v1",
        "generatedAt": utc_now_iso(),
        "priorityOrder": [
            "release_candidate_closeout",
            "operator_export_packaging",
            "user_visible_acceptance_copy",
            "post_release_detector_evaluation_design",
        ],
        "backlogItems": [
            {
                "id": "release_candidate_closeout",
                "title": "Close the video-to-analysis release candidate",
                "nextLever": NEXT_RELEASE_CANDIDATE_CLOSEOUT,
                "why": "The product path has passed broader five-case acceptance and needs a clean release-candidate truth surface.",
                "allowedMutation": "none",
            },
            {
                "id": "operator_export_packaging",
                "title": "Package operator-facing export references",
                "nextLever": "video_to_analysis_operator_export_packaging",
                "why": "Make the generated report, route, bundle, CSV, and HTML surfaces easier to locate from one product report.",
                "allowedMutation": "artifact_only",
            },
            {
                "id": "user_visible_acceptance_copy",
                "title": "Polish user-visible acceptance/report copy",
                "nextLever": "video_to_analysis_acceptance_copy_polish",
                "why": "The route is functional; copy can now be tightened without changing product behavior.",
                "allowedMutation": "route_copy_only",
            },
            {
                "id": "post_release_detector_evaluation_design",
                "title": "Design post-release detector evaluation lane",
                "nextLever": "video_to_analysis_post_release_detector_eval_design",
                "why": "Detector evaluation remains intentionally blocked until product release-candidate truth is closed.",
                "allowedMutation": "design_only",
            },
        ],
    }


def run_video_to_analysis_acceptance_report_product_backlog(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    binding_root = root / DEFAULT_ROUTE_BINDING_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    binding_summary = load_json(binding_root / "acceptance_report_route_binding_summary.json")
    view_model = load_json(binding_root / "acceptance_report_view_model.json")
    route_contract = load_json(binding_root / "acceptance_report_route_contract.json")
    ready = _route_binding_ready(binding_summary, view_model, route_contract)

    if ready:
        primary_blocker = None
        next_lever = NEXT_RELEASE_CANDIDATE_CLOSEOUT
        goal = True
        english = "Acceptance report product backlog is ready. Close the video-to-analysis release candidate next."
    else:
        primary_blocker = BLOCKER_ROUTE_BINDING_MISSING
        next_lever = NEXT_ROUTE_BINDING
        goal = False
        english = "Acceptance report route binding is missing or unsafe; bind the report route before backlog planning."

    backlog = _backlog() if ready else {"schemaVersion": "video_to_analysis_acceptance_report_product_backlog_v1", "generatedAt": utc_now_iso(), "priorityOrder": [], "backlogItems": []}
    summary = {
        "batchName": "video_to_analysis_acceptance_report_product_backlog",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "acceptanceReportProductBacklogReady": goal,
        "acceptanceCaseCount": 5 if goal else 0,
        "acceptancePassedCaseCount": 5 if goal else 0,
        "priorityBacklogItem": "release_candidate_closeout" if goal else None,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "route_binding_missing",
                "selected": primary_blocker == BLOCKER_ROUTE_BINDING_MISSING,
                "primaryBlocker": BLOCKER_ROUTE_BINDING_MISSING,
                "nextRecommendedNextLever": NEXT_ROUTE_BINDING,
            },
            {
                "condition": "product_backlog_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_RELEASE_CANDIDATE_CLOSEOUT,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="acceptance_report_product_backlog_summary.json",
        summary=summary,
        artifacts={
            "acceptance_report_product_backlog.json": backlog,
            "acceptance_report_product_gap_analysis.json": {
                "generatedAt": utc_now_iso(),
                "routeBindingReady": ready,
                "remainingReleaseCandidateGaps": [] if ready else [BLOCKER_ROUTE_BINDING_MISSING],
                "detectorEvaluationDeferred": True,
                "trainingDeferred": True,
                "promotionDeferred": True,
                "runtimeDefaultMutationDeferred": True,
            },
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Acceptance Report Product Backlog",
    )


def main() -> None:
    main_for("Build acceptance report product backlog.", run_video_to_analysis_acceptance_report_product_backlog)


if __name__ == "__main__":
    main()
