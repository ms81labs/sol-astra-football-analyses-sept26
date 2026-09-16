from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    latest_versioned_dir,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_DECISION_SURFACE_DIR_NAME = "video_to_analysis_current_release_acceptance_decision_surface_v2"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_manual_operator_release_decision_v1"

BLOCKER_DECISION_SURFACE_MISSING = "video_to_analysis_manual_operator_release_decision_surface_missing"
NEXT_DECISION_SURFACE = "video_to_analysis_current_release_acceptance_decision_surface"
NEXT_CURRENT_MILESTONE_DONE = "video_to_analysis_current_milestone_done"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "operator_declares_current_milestone_done",
                "successCriteria": [
                    "latest current release decision surface is ready",
                    "v7.3 is the released runtime version",
                    "source-pool cycle is classified as optional coverage",
                    "operator decision is recorded as declare_current_milestone_done",
                    "no training, promotion, runtime mutation, downloads, normal storage mutation, or cleanup deletion",
                ],
                "failureAdaptation": "If the decision surface is missing, route back to the decision surface batch.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "operator_decision_reference_repair",
                "successCriteria": ["repair only generated-truth references and readout metadata"],
                "failureAdaptation": "Do not infer release closure from stale or missing truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "operator_decision_blocker_summary",
                "successCriteria": ["write one blocker and one next family"],
                "failureAdaptation": "Stop without advancing source-pool replenishment automatically.",
            },
        ],
    }


def _decision_surface_ready(summary: dict[str, Any] | None, model: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("roadmapAdvanceAllowed") is True
        and summary.get("releasedRuntimeVersion") == "v7.3"
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and summary.get("currentReleaseFinished") is True
        and summary.get("sourcePoolCycleStillPresent") is True
        and summary.get("recommendedStrategicChoice") == "manual_operator_release_decision"
        and summary.get("nextRecommendedNextLever") == "manual_operator_release_decision_required"
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(model, dict)
        and model.get("currentState") == "current_release_done_optional_coverage_loop"
        and model.get("recommendedNextLever") == "manual_operator_release_decision_required"
    )


def _current_milestone_closeout(summary: dict[str, Any], surface_dir_name: str) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_current_milestone_closeout_v1",
        "generatedAt": utc_now_iso(),
        "sourceDecisionSurfaceDir": surface_dir_name,
        "releasedRuntimeVersion": "v7.3",
        "activeRuntimeDefaultVersion": "v7.3",
        "currentMilestoneStatus": "declared_done_by_operator",
        "sourcePoolCycleDisposition": "deferred_optional_coverage",
        "growthLaneClosedAtVersion": summary.get("growthLaneClosedAtVersion"),
        "growthLaneClosedAtSnapshotDir": summary.get("growthLaneClosedAtSnapshotDir"),
        "safeClaims": [
            "v7.3 is the active packaged runtime for the current milestone",
            "product/release/dashboard/monitoring generated truth is current",
            "source-pool replenishment remains available only as optional coverage",
            "no new training, promotion mutation, runtime-default mutation, video/data download, or storage mutation happened in this decision batch",
        ],
        "notClaimed": [
            "not claiming unlimited generalization",
            "not launching another automatic source-pool replenishment wave",
            "not changing runtime defaults",
            "not training or promoting a detector",
        ],
    }


def _manual_next_choices() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_manual_next_choices_v1",
        "generatedAt": utc_now_iso(),
        "operatorChoices": [
            {
                "id": "keep_current_milestone_done",
                "label": "Keep current v7.3 milestone done",
                "nextLever": NEXT_CURRENT_MILESTONE_DONE,
                "default": True,
            },
            {
                "id": "resume_source_pool_replenishment_as_optional_coverage",
                "label": "Resume source-pool replenishment as optional coverage",
                "nextLever": "video_to_analysis_source_pool_replenishment_plan",
                "default": False,
            },
            {
                "id": "acquire_new_real_sources_before_more_scaleout",
                "label": "Acquire new real sources before more scaleout",
                "nextLever": "football_external_benchmark_real_source_path_consolidation",
                "default": False,
            },
            {
                "id": "reopen_training_only_from_new_miss_truth",
                "label": "Reopen training only from new reviewed miss truth",
                "nextLever": "v7_4_training_decision_from_real_misses",
                "default": False,
            },
        ],
    }


def _operator_readout(closeout: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Video-to-analysis manual operator release decision",
            "",
            "## Decision",
            "",
            "The v7.3 current milestone is declared done.",
            "",
            "## Runtime",
            "",
            "```text",
            f"releasedRuntimeVersion = {closeout['releasedRuntimeVersion']}",
            f"sourcePoolCycleDisposition = {closeout['sourcePoolCycleDisposition']}",
            "```",
            "",
            "## Meaning",
            "",
            "- The current release/product/runtime path is packaged for this milestone.",
            "- More source-pool replenishment is optional coverage work, not an autonomous next step.",
            "- Training, promotion, runtime-default mutation, downloads, and normal storage mutation remain off in this batch.",
            "",
        ]
    )


def run_video_to_analysis_manual_operator_release_decision(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    decision_surface_dir = latest_versioned_dir(
        root,
        "video_to_analysis_current_release_acceptance_decision_surface",
        DEFAULT_DECISION_SURFACE_DIR_NAME,
    )
    surface_summary = load_json(decision_surface_dir / "current_release_acceptance_decision_surface_summary.json")
    decision_model = load_json(decision_surface_dir / "current_operator_decision_model.json")
    ready = _decision_surface_ready(surface_summary, decision_model)

    if ready:
        goal = True
        primary_blocker = None
        next_lever = NEXT_CURRENT_MILESTONE_DONE
        english = (
            "Operator decision recorded: declare the current v7.3 milestone done and defer source-pool "
            "replenishment as optional coverage."
        )
    else:
        goal = False
        primary_blocker = BLOCKER_DECISION_SURFACE_MISSING
        next_lever = NEXT_DECISION_SURFACE
        english = "Current release decision surface is missing or stale; rebuild it before recording operator decision."

    closeout = (
        _current_milestone_closeout(surface_summary or {}, decision_surface_dir.name)
        if goal
        else {
            "schemaVersion": "video_to_analysis_current_milestone_closeout_v1",
            "generatedAt": utc_now_iso(),
            "currentMilestoneStatus": "blocked",
            "sourceDecisionSurfaceDir": decision_surface_dir.name,
        }
    )
    next_choices = _manual_next_choices()
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "operator_release_decision_readout.md").write_text(
        _operator_readout(closeout) if goal else "# Video-to-analysis manual operator release decision\n\nBlocked.\n",
        encoding="utf-8",
    )

    summary = {
        "batchName": "video_to_analysis_manual_operator_release_decision",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "operatorDecisionRecorded": goal,
        "selectedOperatorDecision": "declare_current_milestone_done" if goal else None,
        "v7_3CurrentMilestoneDeclaredDone": goal,
        "releasedRuntimeVersion": "v7.3" if goal else None,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "sourcePoolCycleStillPresent": bool((surface_summary or {}).get("sourcePoolCycleStillPresent")),
        "optionalCoverageLoopDeferred": goal,
        "sourceDecisionSurfaceDir": decision_surface_dir.name if surface_summary else None,
        **standard_false_flags(),
        "cleanupDeletionExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_manual_operator_release_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "decision_surface_missing_or_stale",
                "selected": primary_blocker == BLOCKER_DECISION_SURFACE_MISSING,
                "primaryBlocker": BLOCKER_DECISION_SURFACE_MISSING,
                "nextRecommendedNextLever": NEXT_DECISION_SURFACE,
            },
            {
                "condition": "operator_declares_current_milestone_done",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_CURRENT_MILESTONE_DONE,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="manual_operator_release_decision_summary.json",
        summary=summary,
        artifacts={
            "current_milestone_closeout.json": closeout,
            "manual_next_choices.json": next_choices,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Manual Operator Release Decision",
    )


def main() -> None:
    main_for(
        "Record manual operator release decision for the current video-to-analysis milestone.",
        run_video_to_analysis_manual_operator_release_decision,
    )


if __name__ == "__main__":
    main()
