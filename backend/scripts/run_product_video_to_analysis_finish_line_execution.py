from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.main import create_app  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guardrails_false,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_finish_line_product_execution_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "product_video_to_analysis_finish_line_execution_v1"
DEFAULT_ISOLATED_SMOKE_DIR_NAME = "product_video_to_analysis_smoke_isolated_v1"

BLOCKER_APPROVAL_MISSING = "video_to_analysis_finish_line_product_execution_approval_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "product_video_to_analysis_finish_line_route_smoke_failed"
BLOCKER_BUNDLE_SMOKE_FAILED = "product_video_to_analysis_finish_line_bundle_smoke_failed"
NEXT_APPROVAL = "video_to_analysis_finish_line_product_execution_approval"
NEXT_ROUTE_REPAIR = "video_to_analysis_finish_line_route_implementation"
NEXT_BUNDLE_REPAIR = "product_video_to_analysis_smoke"
NEXT_ACCEPTANCE_CLOSEOUT = "video_to_analysis_finish_line_product_acceptance_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "bounded_product_route_and_bundle_smoke",
                "successCriteria": [
                    "finish-line API and HTML routes return 200",
                    "isolated product video-to-analysis bundle evidence remains readable",
                    "no normal match storage mutation, downloads, detector evaluation, training, promotion, candidate readiness, or runtime-default mutation",
                ],
                "failureAdaptation": "If approval truth is missing, route back to product execution approval.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "bounded_product_route_or_bundle_repair",
                "successCriteria": [
                    "repair only route loading or isolated bundle evidence lookup",
                    "do not mutate normal match storage or run detector/training/proof",
                ],
                "failureAdaptation": "Route to route implementation or product smoke based on failing slice.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "product_execution_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to approval, route repair, bundle repair, or acceptance closeout.",
            },
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineProductExecutionApproved") is True
        and summary.get("approvedExecutionMode") == "bounded_product_route_and_bundle_smoke"
        and guardrails_false(summary)
        and isinstance(scope, dict)
        and scope.get("finishLineProductExecutionApproved") is True
        and scope.get("approvedExecutionMode") == "bounded_product_route_and_bundle_smoke"
        and scope.get("allowedApiRoutePath") == "/api/video-to-analysis/finish-line"
        and scope.get("allowedHtmlRoutePath") == "/video-to-analysis/finish-line"
        and scope.get("normalMatchStorageMutationAllowed") is False
        and scope.get("isolatedBenchmarkStorageMutationAllowed") is True
        and scope.get("trainingAllowed") is False
        and scope.get("promotionAllowed") is False
        and scope.get("runtimeDefaultMutationAllowed") is False
    )


async def _route_smoke(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/finish-line")
        html_response = await client.get("/video-to-analysis/finish-line")
    api_json: dict[str, Any] | None
    try:
        parsed = api_response.json()
        api_json = parsed if isinstance(parsed, dict) else None
    except ValueError:
        api_json = None
    return {
        "schemaVersion": "product_video_to_analysis_finish_line_route_execution_audit_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/video-to-analysis/finish-line",
        "htmlRoutePath": "/video-to-analysis/finish-line",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_json.get("schemaVersion") if api_json else None,
        "htmlContainsHeadline": "Video To Analysis Finish Line" in html_response.text,
        "boundedRouteSmokePassed": (
            api_response.status_code == 200
            and html_response.status_code == 200
            and api_json is not None
            and api_json.get("schemaVersion") == "video_to_analysis_finish_line_product_view_model_v1"
            and "Video To Analysis Finish Line" in html_response.text
        ),
    }


def _bundle_audit(root: Path) -> dict[str, Any]:
    isolated_root = root / DEFAULT_ISOLATED_SMOKE_DIR_NAME
    summary = load_json(isolated_root / "product_video_to_analysis_smoke_summary.json")
    storage_audit = load_json(isolated_root / "isolated_storage_audit.json")
    passed = bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productVideoToAnalysisSmokePassed") is True
        and summary.get("apiUploadJobSmokePassed") is True
        and summary.get("existingVideoBundleSmokePassed") is True
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(storage_audit, dict)
        and storage_audit.get("normalStorageRootUsedForSmoke") is False
        and storage_audit.get("isolatedBenchmarkStorageMutationExecuted") is True
        and storage_audit.get("nestedSmokeSummaryExists") is True
    )
    return {
        "schemaVersion": "product_video_to_analysis_finish_line_bundle_consistency_audit_v1",
        "generatedAt": utc_now_iso(),
        "productVideoToAnalysisSmokePassed": bool(summary and summary.get("productVideoToAnalysisSmokePassed") is True),
        "apiUploadJobSmokePassed": bool(summary and summary.get("apiUploadJobSmokePassed") is True),
        "existingVideoBundleSmokePassed": bool(summary and summary.get("existingVideoBundleSmokePassed") is True),
        "normalStorageRootUsedForSmoke": storage_audit.get("normalStorageRootUsedForSmoke") if isinstance(storage_audit, dict) else None,
        "isolatedBenchmarkStorageMutationExecuted": storage_audit.get("isolatedBenchmarkStorageMutationExecuted") if isinstance(storage_audit, dict) else None,
        "nestedSmokeSummaryExists": storage_audit.get("nestedSmokeSummaryExists") if isinstance(storage_audit, dict) else None,
        "bundleConsistencyPassed": passed,
    }


def run_product_video_to_analysis_finish_line_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    approval_root = root / DEFAULT_APPROVAL_DIR_NAME
    approval_summary = load_json(approval_root / "finish_line_product_execution_approval_summary.json")
    approval_scope = load_json(approval_root / "approved_finish_line_product_execution_scope.json")
    approval_ready = _approval_ready(approval_summary, approval_scope)

    route_audit = (
        asyncio.run(_route_smoke(Path(storage_root)))
        if approval_ready
        else {
            "schemaVersion": "product_video_to_analysis_finish_line_route_execution_audit_v1",
            "generatedAt": utc_now_iso(),
            "boundedRouteSmokePassed": False,
            "skipReason": BLOCKER_APPROVAL_MISSING,
        }
    )
    bundle_audit = _bundle_audit(root) if approval_ready else {
        "schemaVersion": "product_video_to_analysis_finish_line_bundle_consistency_audit_v1",
        "generatedAt": utc_now_iso(),
        "bundleConsistencyPassed": False,
        "skipReason": BLOCKER_APPROVAL_MISSING,
    }

    route_passed = route_audit.get("boundedRouteSmokePassed") is True
    bundle_passed = bundle_audit.get("bundleConsistencyPassed") is True
    if not approval_ready:
        primary_blocker = BLOCKER_APPROVAL_MISSING
        next_lever = NEXT_APPROVAL
        goal = False
        english = "Finish-line product execution approval is missing or unsafe; approve bounded execution before running it."
    elif not route_passed:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_ROUTE_REPAIR
        goal = False
        english = "Finish-line product route smoke failed; repair route implementation before product acceptance closeout."
    elif not bundle_passed:
        primary_blocker = BLOCKER_BUNDLE_SMOKE_FAILED
        next_lever = NEXT_BUNDLE_REPAIR
        goal = False
        english = "Finish-line isolated bundle evidence is missing or unsafe; rerun the isolated product smoke."
    else:
        primary_blocker = None
        next_lever = NEXT_ACCEPTANCE_CLOSEOUT
        goal = True
        english = "Bounded finish-line product route and bundle smoke passed. Close out product acceptance next."

    acceptance_truth = {
        "schemaVersion": "product_video_to_analysis_finish_line_acceptance_truth_v1",
        "generatedAt": utc_now_iso(),
        "finishLineProductExecutionPassed": goal,
        "boundedRouteSmokePassed": route_passed,
        "bundleConsistencyPassed": bundle_passed,
        "normalMatchStorageMutationExecuted": False,
        "detectorEvaluationExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
    }
    summary = {
        "batchName": "product_video_to_analysis_finish_line_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "finishLineProductExecutionPassed": goal,
        "boundedRouteSmokePassed": route_passed,
        "bundleConsistencyPassed": bundle_passed,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "route_smoke_failed", "selected": primary_blocker == BLOCKER_ROUTE_SMOKE_FAILED, "primaryBlocker": BLOCKER_ROUTE_SMOKE_FAILED, "nextRecommendedNextLever": NEXT_ROUTE_REPAIR},
            {"condition": "bundle_smoke_failed", "selected": primary_blocker == BLOCKER_BUNDLE_SMOKE_FAILED, "primaryBlocker": BLOCKER_BUNDLE_SMOKE_FAILED, "nextRecommendedNextLever": NEXT_BUNDLE_REPAIR},
            {"condition": "product_execution_passed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_ACCEPTANCE_CLOSEOUT},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="product_video_to_analysis_finish_line_execution_summary.json",
        summary=summary,
        artifacts={
            "finish_line_product_route_execution_audit.json": route_audit,
            "finish_line_bundle_consistency_audit.json": bundle_audit,
            "finish_line_product_acceptance_truth.json": acceptance_truth,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Product Video To Analysis Finish Line Execution",
    )


def main() -> None:
    main_for("Run bounded finish-line product route and bundle smoke.", run_product_video_to_analysis_finish_line_execution)


if __name__ == "__main__":
    main()
