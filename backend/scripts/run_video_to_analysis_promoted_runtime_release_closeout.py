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

DEFAULT_OPERATOR_ACCEPTANCE_DIR_NAME = "video_to_analysis_promoted_runtime_operator_acceptance_trial_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promoted_runtime_release_closeout_v1"

BLOCKER_OPERATOR_ACCEPTANCE_MISSING = "video_to_analysis_promoted_runtime_operator_acceptance_missing"
NEXT_OPERATOR_ACCEPTANCE = "video_to_analysis_promoted_runtime_operator_acceptance_trial"
NEXT_RELEASE_COMPLETION = "video_to_analysis_release_completion_summary"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promoted_runtime_release_closeout",
                "successCriteria": [
                    "operator acceptance passed",
                    "registry and route smoke audits are present",
                    "close release without executing training, promotion mutation, or runtime-default mutation",
                ],
                "failureAdaptation": "If operator acceptance truth is missing, route back to operator acceptance trial.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promoted_runtime_release_evidence_repair",
                "successCriteria": ["repair only closeout evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promoted_runtime_release_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not force release completion.",
            },
        ],
    }


def _operator_acceptance_ready(summary: dict[str, Any] | None, registry: dict[str, Any] | None, routes: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("promotedRuntimeOperatorAcceptancePassed") is True
        and summary.get("registryMatchesPromotedV7_2DefaultRuntime") is True
        and summary.get("operatorVisibleRouteSmokePassed") is True
        and int(summary.get("routeSmokePassedCount") or 0) >= 5
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(registry, dict)
        and registry.get("registryMatchesPromotedV7_2DefaultRuntime") is True
        and isinstance(routes, dict)
        and routes.get("operatorVisibleRouteSmokePassed") is True
    )


def run_video_to_analysis_promoted_runtime_release_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    input_root = root / DEFAULT_OPERATOR_ACCEPTANCE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    acceptance_summary = load_json(input_root / "promoted_runtime_operator_acceptance_trial_summary.json")
    registry_audit = load_json(input_root / "promoted_runtime_registry_audit.json")
    route_audit = load_json(input_root / "operator_visible_route_smoke_audit.json")
    ready = _operator_acceptance_ready(acceptance_summary, registry_audit, route_audit)

    if ready:
        primary_blocker = None
        next_lever = NEXT_RELEASE_COMPLETION
        goal = True
        english = "Promoted runtime release is closed. Write the release completion summary next."
    else:
        primary_blocker = BLOCKER_OPERATOR_ACCEPTANCE_MISSING
        next_lever = NEXT_OPERATOR_ACCEPTANCE
        goal = False
        english = "Promoted-runtime operator acceptance is missing or unsafe; pass operator acceptance before release closeout."

    release_manifest = {
        "schemaVersion": "video_to_analysis_promoted_runtime_release_manifest_v1",
        "generatedAt": utc_now_iso(),
        "promotedRuntimeReleaseClosed": goal,
        "releasedRuntime": {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.2",
            "runtimeUse": "default_runtime",
        },
        "operatorAcceptanceEvidence": {
            "summaryPath": str(input_root / "promoted_runtime_operator_acceptance_trial_summary.json"),
            "registryAuditPath": str(input_root / "promoted_runtime_registry_audit.json"),
            "routeSmokeAuditPath": str(input_root / "operator_visible_route_smoke_audit.json"),
            "routeSmokePassedCount": acceptance_summary.get("routeSmokePassedCount") if isinstance(acceptance_summary, dict) else 0,
        },
        "mutationPolicy": {
            "trainingExecutedByCloseout": False,
            "promotionMutationExecutedByCloseout": False,
            "runtimeDefaultMutationExecutedByCloseout": False,
        },
    }
    summary = {
        "batchName": "video_to_analysis_promoted_runtime_release_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotedRuntimeReleaseClosed": goal,
        "promotedRuntimeOperatorAcceptancePassed": bool(
            isinstance(acceptance_summary, dict) and acceptance_summary.get("promotedRuntimeOperatorAcceptancePassed") is True
        ),
        "routeSmokePassedCount": acceptance_summary.get("routeSmokePassedCount") if isinstance(acceptance_summary, dict) else 0,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promoted_runtime_release_closeout_summary.json",
        summary=summary,
        artifacts={
            "promoted_runtime_release_manifest.json": release_manifest,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promoted Runtime Release Closeout",
    )


def main() -> None:
    main_for("Close video-to-analysis promoted runtime release.", run_video_to_analysis_promoted_runtime_release_closeout)


if __name__ == "__main__":
    main()
