from __future__ import annotations

from html import escape
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

DEFAULT_EXECUTION_DIR_NAME = "video_to_analysis_promotion_review_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promotion_review_report_binding_v1"

BLOCKER_EXECUTION_MISSING = "video_to_analysis_promotion_review_execution_missing"
NEXT_EXECUTION = "video_to_analysis_promotion_review_execution"
NEXT_ROUTE_BINDING = "video_to_analysis_promotion_review_report_route_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promotion_review_report_binding",
                "successCriteria": ["bind promotion review execution truth into API/HTML report artifacts"],
                "failureAdaptation": "If execution truth is missing, route back to promotion review execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promotion_review_report_contract_repair",
                "successCriteria": ["repair only report schema or route contract"],
                "failureAdaptation": "If report contract remains invalid, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promotion_review_report_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to execution, contract repair, or route binding.",
            },
        ],
    }


def _execution_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("promotionReviewPassed") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and audit.get("registryMatchesV7_2DefaultRuntime") is True
        and audit.get("postRuntimeDefaultSourceRobustnessValidated") is True
    )


def _view_model(summary: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_promotion_review_report_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Promotion Review",
        "promotionReviewPassed": summary.get("promotionReviewPassed") is True,
        "registryMatchesV7_2DefaultRuntime": audit.get("registryMatchesV7_2DefaultRuntime") is True,
        "postRuntimeDefaultSourceRobustnessValidated": audit.get("postRuntimeDefaultSourceRobustnessValidated") is True,
        "activeFailingSourceNotViableBlockerPresent": audit.get("activeFailingSourceNotViableBlockerPresent"),
        "reviewMutations": audit.get("reviewMutations", {}),
        "nextRecommendedNextLever": NEXT_ROUTE_BINDING,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<li>{escape(key)}: {escape(str(view_model.get(key)))}</li>"
        for key in (
            "promotionReviewPassed",
            "registryMatchesV7_2DefaultRuntime",
            "postRuntimeDefaultSourceRobustnessValidated",
            "activeFailingSourceNotViableBlockerPresent",
        )
    )
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Promotion Review</title></head>",
            "<body>",
            "<h1>Promotion Review</h1>",
            f"<ul>{rows}</ul>",
            "</body>",
            "</html>",
            "",
        ]
    )


def run_video_to_analysis_promotion_review_report_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    execution_root = root / DEFAULT_EXECUTION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    execution_summary = load_json(execution_root / "promotion_review_execution_summary.json")
    audit = load_json(execution_root / "promotion_review_execution_audit.json")
    ready = _execution_ready(execution_summary, audit)

    if ready and isinstance(execution_summary, dict) and isinstance(audit, dict):
        primary_blocker = None
        next_lever = NEXT_ROUTE_BINDING
        goal = True
        english = "Promotion review report is ready. Bind and smoke the route next."
        view_model = _view_model(execution_summary, audit)
    else:
        primary_blocker = BLOCKER_EXECUTION_MISSING
        next_lever = NEXT_EXECUTION
        goal = False
        english = "Promotion review execution is missing or unsafe; execute review before report binding."
        view_model = _view_model({}, {})

    route_contract = {
        "schemaVersion": "video_to_analysis_promotion_review_report_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/video-to-analysis/promotion-review",
        "htmlRoutePath": "/video-to-analysis/promotion-review",
        "promotionReviewReportReady": goal,
    }
    (output_root / "promotion_review_report_render_smoke.html").write_text(_render_html(view_model), encoding="utf-8")
    summary = {
        "batchName": "video_to_analysis_promotion_review_report_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotionReviewReportReady": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promotion_review_report_binding_summary.json",
        summary=summary,
        artifacts={
            "promotion_review_report_view_model.json": view_model,
            "promotion_review_report_route_contract.json": route_contract,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promotion Review Report Binding",
    )


def main() -> None:
    main_for("Bind video-to-analysis promotion review report.", run_video_to_analysis_promotion_review_report_binding)


if __name__ == "__main__":
    main()
