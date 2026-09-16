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

DEFAULT_CHOICE_DIR_NAME = "football_external_soccernet_broader_validation_choice_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_upload_to_analysis_walkthrough_v1"

BLOCKER_CHOICE_MISSING = "video_to_analysis_upload_walkthrough_broader_choice_missing"
NEXT_CHOICE = "football_external_soccernet_broader_validation_choice"
NEXT_TRAINING_DECISION = "v7_4_training_decision_from_real_misses"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "upload_to_analysis_walkthrough",
                "successCriteria": [
                    "broader validation choice is complete",
                    "write operator walkthrough steps for upload/select-video to analysis",
                    "keep this as documentation/product guidance only",
                ],
                "failureAdaptation": "If broader validation choice is missing, route back to that choice gate.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "upload_walkthrough_content_repair",
                "successCriteria": ["repair only walkthrough copy, route references, or guardrail language"],
                "failureAdaptation": "Do not add execution, training, download, or runtime mutation behavior.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "upload_walkthrough_blocker_summary",
                "successCriteria": ["write one blocker and one next family"],
                "failureAdaptation": "Stop with product guidance truth.",
            },
        ],
    }


def _choice_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("broaderValidationHeldAsOptionalFutureGrowth") is True
    )


def _walkthrough_markdown() -> str:
    return "\n".join(
        [
            "# Upload To Analysis Walkthrough",
            "",
            "## Operator Path",
            "",
            "1. Open the product entry route.",
            "2. Upload or select a bounded football video source.",
            "3. Wait for the job to write the match bundle and analysis artifacts.",
            "4. Open the acceptance report and operator handoff routes.",
            "5. Treat detector training as a separate evidence-driven lane, not part of upload.",
            "",
            "## Guardrails",
            "",
            "- This walkthrough does not download datasets.",
            "- This walkthrough does not train.",
            "- This walkthrough does not promote or mutate runtime defaults.",
            "- v7.4 training only starts if real miss truth proves it is needed.",
            "",
        ]
    )


def run_video_to_analysis_upload_to_analysis_walkthrough(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    choice_summary = load_json(root / DEFAULT_CHOICE_DIR_NAME / "soccernet_broader_validation_choice_summary.json")
    choice_ready = _choice_ready(choice_summary)

    if choice_ready:
        goal = True
        primary_blocker = None
        next_lever = NEXT_TRAINING_DECISION
        english = "Upload-to-analysis walkthrough is packaged. Decide v7.4 training from real miss truth next."
    else:
        goal = False
        primary_blocker = BLOCKER_CHOICE_MISSING
        next_lever = NEXT_CHOICE
        english = "Broader SoccerNet validation choice is missing; choose validation posture before walkthrough packaging."

    walkthrough = {
        "schemaVersion": "video_to_analysis_upload_to_analysis_walkthrough_v1",
        "generatedAt": utc_now_iso(),
        "walkthroughReady": goal,
        "entryRoutes": [
            "/video-to-analysis/acceptance-report",
            "/video-to-analysis/operator-handoff",
            "/video-to-analysis/post-release-monitoring",
        ],
        "operatorSteps": [
            "upload_or_select_bounded_video",
            "wait_for_match_bundle_and_analysis_artifacts",
            "open_acceptance_report",
            "open_operator_handoff",
            "route_detector_training_to_real_miss_decision_lane",
        ],
        "guardrails": {
            "downloadAllowed": False,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    }
    if goal:
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "upload_to_analysis_walkthrough.md").write_text(_walkthrough_markdown(), encoding="utf-8")

    summary = {
        "batchName": "video_to_analysis_upload_to_analysis_walkthrough",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "uploadToAnalysisWalkthroughReady": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="upload_to_analysis_walkthrough_summary.json",
        summary=summary,
        artifacts={
            "upload_to_analysis_walkthrough.json": walkthrough,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Upload To Analysis Walkthrough",
    )


def main() -> None:
    main_for("Package video-to-analysis upload walkthrough.", run_video_to_analysis_upload_to_analysis_walkthrough)


if __name__ == "__main__":
    main()
