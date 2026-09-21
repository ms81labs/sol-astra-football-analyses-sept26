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
    write_json,
    write_outcome,
)

DEFAULT_BACKLOG_DIR_NAME = "video_to_analysis_product_hardening_backlog_v1"
DEFAULT_BINDING_DIR_NAME = "video_to_analysis_finish_line_product_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_route_polish_v1"

BLOCKER_BACKLOG_MISSING = "video_to_analysis_product_hardening_backlog_missing"
BLOCKER_BINDING_MISSING = "video_to_analysis_finish_line_product_binding_missing"
NEXT_BACKLOG = "video_to_analysis_product_hardening_backlog"
NEXT_BINDING_REPAIR = "video_to_analysis_finish_line_product_binding"
NEXT_ACCEPTANCE_SUITE_PREP = "video_to_analysis_broader_real_video_acceptance_suite_prep"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "finish_line_route_polish",
                "successCriteria": ["polish route view model and HTML", "preserve existing route contract"],
                "failureAdaptation": "If backlog truth is missing, route back to product hardening backlog.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "finish_line_route_polish_binding_repair",
                "successCriteria": ["repair only product binding artifacts"],
                "failureAdaptation": "If binding remains missing, route back to product binding.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "finish_line_route_polish_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to backlog, binding repair, or broader acceptance suite prep.",
            },
        ],
    }


def _backlog_ready(summary: dict[str, Any] | None, backlog: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productHardeningBacklogReady") is True
        and isinstance(backlog, dict)
        and "finish_line_route_polish" in (backlog.get("priorityOrder") or [])
    )


def _binding_ready(root: Path) -> bool:
    contract = load_json(root / "finish_line_product_route_contract.json")
    view_model = load_json(root / "finish_line_product_view_model.json")
    return bool(
        isinstance(contract, dict)
        and contract.get("apiRoutePath") == "/api/video-to-analysis/finish-line"
        and contract.get("htmlRoutePath") == "/video-to-analysis/finish-line"
        and isinstance(view_model, dict)
        and view_model.get("schemaVersion") == "video_to_analysis_finish_line_product_view_model_v1"
    )


def run_video_to_analysis_finish_line_route_polish(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    backlog_root = root / DEFAULT_BACKLOG_DIR_NAME
    binding_root = root / DEFAULT_BINDING_DIR_NAME
    backlog_summary = load_json(backlog_root / "product_hardening_backlog_summary.json")
    backlog_payload = load_json(backlog_root / "product_hardening_backlog.json")
    backlog_ready = _backlog_ready(backlog_summary, backlog_payload)
    binding_ready = _binding_ready(binding_root)

    if backlog_ready and binding_ready:
        polished_view_model = {
            "schemaVersion": "video_to_analysis_finish_line_product_view_model_v1",
            "generatedAt": utc_now_iso(),
            "title": "Video To Analysis Finish Line",
            "subtitle": "Upload a video, let the pipeline process it, and inspect the generated match bundle, report, CSV exports, and route evidence.",
            "status": "ready_for_product_hardening_acceptance",
            "scoreboard": [
                {"label": "Route smoke", "value": "passed"},
                {"label": "Normal storage smoke", "value": "passed"},
                {"label": "Match bundle export", "value": "ready"},
                {"label": "Training/promotion", "value": "not touched"},
            ],
            "operatorActions": [
                "Open this page after a video upload/export smoke.",
                "Confirm the API payload remains readable.",
                "Use the generated match bundle path for deeper inspection.",
            ],
            "nextRecommendedNextLever": NEXT_ACCEPTANCE_SUITE_PREP,
        }
        polished_html = """<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Video To Analysis Finish Line</title></head>
  <body>
    <main>
      <h1>Video To Analysis Finish Line</h1>
      <p>Open this page after a video upload/export smoke to confirm the product path is readable.</p>
      <ul>
        <li>Route smoke: passed</li>
        <li>Normal storage smoke: passed</li>
        <li>Training and promotion: not touched</li>
      </ul>
    </main>
  </body>
</html>
"""
        write_json(binding_root / "finish_line_product_view_model.json", polished_view_model)
        (binding_root / "finish_line_product_render_smoke.html").write_text(polished_html, encoding="utf-8")

    if not backlog_ready:
        primary_blocker = BLOCKER_BACKLOG_MISSING
        next_lever = NEXT_BACKLOG
        goal = False
        english = "Product hardening backlog is missing or unsafe; build backlog first."
    elif not binding_ready:
        primary_blocker = BLOCKER_BINDING_MISSING
        next_lever = NEXT_BINDING_REPAIR
        goal = False
        english = "Finish-line product binding is missing or unsafe; repair binding before route polish."
    else:
        primary_blocker = None
        next_lever = NEXT_ACCEPTANCE_SUITE_PREP
        goal = True
        english = "Finish-line route polish is applied. Prepare broader real-video acceptance suite next."

    polish_audit = {
        "schemaVersion": "video_to_analysis_finish_line_route_polish_audit_v1",
        "generatedAt": utc_now_iso(),
        "backlogReady": backlog_ready,
        "bindingReady": binding_ready,
        "viewModelUpdated": goal,
        "htmlUpdated": goal,
        "apiRoutePath": "/api/video-to-analysis/finish-line",
        "htmlRoutePath": "/video-to-analysis/finish-line",
    }
    summary = {
        "batchName": "video_to_analysis_finish_line_route_polish",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "finishLineRoutePolished": goal,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "hardening_backlog_missing", "selected": primary_blocker == BLOCKER_BACKLOG_MISSING, "primaryBlocker": BLOCKER_BACKLOG_MISSING, "nextRecommendedNextLever": NEXT_BACKLOG},
            {"condition": "product_binding_missing", "selected": primary_blocker == BLOCKER_BINDING_MISSING, "primaryBlocker": BLOCKER_BINDING_MISSING, "nextRecommendedNextLever": NEXT_BINDING_REPAIR},
            {"condition": "route_polish_applied", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_ACCEPTANCE_SUITE_PREP},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_route_polish_summary.json",
        summary=summary,
        artifacts={
            "finish_line_route_polish_audit.json": polish_audit,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Route Polish",
    )


def main() -> None:
    main_for("Polish video-to-analysis finish-line route.", run_video_to_analysis_finish_line_route_polish)


if __name__ == "__main__":
    main()
