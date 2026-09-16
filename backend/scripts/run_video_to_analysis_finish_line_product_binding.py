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

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_finish_line_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_product_binding_v1"

BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_finish_line_closeout_missing"
NEXT_CLOSEOUT = "video_to_analysis_finish_line_closeout"
NEXT_ROUTE_IMPL = "video_to_analysis_finish_line_route_implementation"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "video_to_analysis_finish_line_product_binding", "successCriteria": ["write view model, HTML render, and route contract"], "failureAdaptation": "If closeout is missing, route back to closeout."},
            {"attemptNumber": 2, "attemptApproachFamily": "video_to_analysis_finish_line_binding_repair", "successCriteria": ["repair binding artifact mapping only"], "failureAdaptation": "If binding remains invalid, write blocker truth."},
            {"attemptNumber": 3, "attemptApproachFamily": "video_to_analysis_finish_line_binding_blocker_summary", "successCriteria": ["write blocker truth"], "failureAdaptation": "Route to closeout, binding repair, or route implementation."},
        ],
    }


def _closeout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(isinstance(summary, dict) and summary.get("goalAchieved") is True and summary.get("primaryBlocker") is None and summary.get("finishLineClosed") is True)


def _html(view_model: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<li><strong>{item['label']}</strong>: {item['value']}</li>"
        for item in view_model.get("scoreboard", [])
        if isinstance(item, dict)
    )
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Video To Analysis Finish Line</title></head>
<body>
  <h1>Video To Analysis Finish Line</h1>
  <p>{view_model.get('subtitle', '')}</p>
  <ul>{rows}</ul>
  <p>Next: {view_model.get('nextRecommendedNextLever')}</p>
</body>
</html>
"""


def run_video_to_analysis_finish_line_product_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    closeout_root = root / DEFAULT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "finish_line_closeout_summary.json")
    ready = _closeout_ready(closeout_summary)
    primary_blocker = None if ready else BLOCKER_CLOSEOUT_MISSING
    next_lever = NEXT_ROUTE_IMPL if ready else NEXT_CLOSEOUT
    view_model = {
        "schemaVersion": "video_to_analysis_finish_line_product_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Video To Analysis Finish Line",
        "subtitle": "Isolated product smoke proved upload, analysis exports, and canonical match bundle output.",
        "scoreboard": [
            {"label": "Product smoke", "value": "passed" if ready else "blocked"},
            {"label": "API upload/export", "value": str(bool((closeout_summary or {}).get("apiUploadJobSmokePassed")))},
            {"label": "Video bundle export", "value": str(bool((closeout_summary or {}).get("existingVideoBundleSmokePassed")))},
            {"label": "Normal storage mutation", "value": "not executed"},
        ],
        "nextRecommendedNextLever": next_lever,
    }
    route_contract = {
        "schemaVersion": "video_to_analysis_finish_line_product_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/video-to-analysis/finish-line",
        "htmlRoutePath": "/video-to-analysis/finish-line",
        "routeImplementationReady": False,
        "productBindingReady": ready,
    }
    summary = {
        "batchName": "video_to_analysis_finish_line_product_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "finishLineProductBindingReady": ready,
        "apiRoutePath": "/api/video-to-analysis/finish-line",
        "htmlRoutePath": "/video-to-analysis/finish-line",
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Finish-line product binding is ready. Implement and smoke the route next." if ready else "Finish-line closeout is missing; close out smoke evidence first.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "closeout_missing", "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING, "primaryBlocker": BLOCKER_CLOSEOUT_MISSING, "nextRecommendedNextLever": NEXT_CLOSEOUT},
            {"condition": "product_binding_ready", "selected": ready, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_ROUTE_IMPL},
        ],
    }
    (output_root / "finish_line_product_render_smoke.html").write_text(_html(view_model), encoding="utf-8")
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_product_binding_summary.json",
        summary=summary,
        artifacts={
            "finish_line_product_view_model.json": view_model,
            "finish_line_product_route_contract.json": route_contract,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Product Binding",
    )


def main() -> None:
    main_for("Bind finish-line closeout to product-facing view model and route contract.", run_video_to_analysis_finish_line_product_binding)


if __name__ == "__main__":
    main()
