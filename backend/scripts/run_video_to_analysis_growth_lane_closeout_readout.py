from __future__ import annotations

from pathlib import Path
import re
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    latest_versioned_dir,
    load_json,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_growth_lane_closeout_readout_v1"

BLOCKER_SNAPSHOT_MISSING = "video_to_analysis_growth_lane_closeout_snapshot_missing"
BLOCKER_SCALEOUT_EVIDENCE_MISSING = "video_to_analysis_growth_lane_closeout_scaleout_evidence_missing"
NEXT_MANUAL_STRATEGIC_CHOICE = "manual_strategic_lane_selection_required"

FALSE_GUARDRAIL_KEYS = (
    "detectorEvaluationExecuted",
    "candidateEvaluationExecuted",
    "candidateReadyForEvaluation",
    "normalMatchStorageMutationExecuted",
    "videoDownloadExecuted",
    "dataDownloadExecuted",
    "trainingExecuted",
    "promotionMutationExecuted",
    "promotionReady",
    "runtimeDefaultMutationExecuted",
)


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "growth_lane_current_snapshot_closeout",
                "successCriteria": [
                    "latest next-sample snapshot is ready",
                    "matching scaleout execution passed",
                    "matching report route smoked API/HTML 200",
                    "matching scaleout lane closeout is ready",
                    "runtime/training/promotion/download guardrails remain false",
                ],
                "failureAdaptation": "If latest evidence is missing, route to exactly that evidence family instead of continuing growth.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "growth_lane_closeout_reference_repair",
                "successCriteria": ["repair only generated-truth references or closeout prose"],
                "failureAdaptation": "Do not consume more bounded queues to fake closeout readiness.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "growth_lane_closeout_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop at blocker truth and preserve all mutation guardrails.",
            },
        ],
    }


def _version(path: Path) -> int:
    match = re.search(r"_v(\d+)$", path.name)
    return int(match.group(1)) if match else 0


def _guardrails_false(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(payload.get(key) is False for key in FALSE_GUARDRAIL_KEYS if key in payload)


def _snapshot_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("candidateSampleCount") == 3
        and isinstance(summary.get("candidateSampleIds"), list)
        and len(summary.get("candidateSampleIds") or []) == 3
        and _guardrails_false(summary)
    )


def _scaleout_evidence_ready(
    execution: dict[str, Any] | None,
    route: dict[str, Any] | None,
    closeout: dict[str, Any] | None,
) -> bool:
    return bool(
        isinstance(execution, dict)
        and execution.get("goalAchieved") is True
        and execution.get("primaryBlocker") is None
        and execution.get("scaleoutPassedCaseCount") == 5
        and _guardrails_false(execution)
        and isinstance(route, dict)
        and route.get("goalAchieved") is True
        and route.get("primaryBlocker") is None
        and route.get("apiRouteStatusCode") == 200
        and route.get("htmlRouteStatusCode") == 200
        and _guardrails_false(route)
        and isinstance(closeout, dict)
        and closeout.get("goalAchieved") is True
        and closeout.get("primaryBlocker") is None
        and closeout.get("realVideoScaleoutLaneClosed") is True
        and _guardrails_false(closeout)
    )


def _latest_consumed_queue_summary(root: Path, snapshot_dir_name: str) -> dict[str, Any] | None:
    dirs = sorted(
        root.glob("video_to_analysis_bounded_next_sample_execution_approval_v*"),
        key=_version,
        reverse=True,
    )
    for path in dirs:
        summary = load_json(path / "bounded_next_sample_execution_approval_summary.json")
        if not isinstance(summary, dict):
            continue
        if (
            summary.get("sourceSnapshotDir") == snapshot_dir_name
            and summary.get("primaryBlocker") == "video_to_analysis_bounded_next_sample_pool_exhausted"
            and summary.get("remainingCandidateSampleCount") == 0
            and _guardrails_false(summary)
        ):
            return {"dirName": path.name, **summary}
    return None


def _latest_recovered_plan_summary(root: Path) -> dict[str, Any] | None:
    dirs = sorted(
        root.glob("video_to_analysis_real_video_scaleout_plan_refresh_v*"),
        key=_version,
        reverse=True,
    )
    for path in dirs:
        summary = load_json(path / "real_video_scaleout_plan_refresh_summary.json")
        if not isinstance(summary, dict):
            continue
        if (
            summary.get("goalAchieved") is True
            and summary.get("primaryBlocker") is None
            and summary.get("availableFreshScaleoutCaseCount", 0) >= summary.get("requiredFreshScaleoutCaseCount", 5)
            and summary.get("refreshedScaleoutCaseCount") == 5
            and _guardrails_false(summary)
        ):
            return {"dirName": path.name, **summary}
    return None


def run_video_to_analysis_growth_lane_closeout_readout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)

    snapshot_dir = latest_versioned_dir(
        root,
        "video_to_analysis_next_sample_selection_snapshot",
        "video_to_analysis_next_sample_selection_snapshot_v1",
    )
    snapshot_summary = load_json(snapshot_dir / "next_sample_selection_snapshot_summary.json")
    closed_version = _version(snapshot_dir)
    execution_dir = root / f"video_to_analysis_real_video_scaleout_bounded_execution_v{closed_version}"
    route_dir = root / f"video_to_analysis_real_video_scaleout_report_route_binding_v{closed_version}"
    closeout_dir = root / f"video_to_analysis_real_video_scaleout_lane_closeout_v{closed_version}"
    execution_summary = load_json(execution_dir / "real_video_scaleout_bounded_execution_summary.json")
    route_summary = load_json(route_dir / "real_video_scaleout_report_route_binding_summary.json")
    closeout_summary = load_json(closeout_dir / "real_video_scaleout_lane_closeout_summary.json")

    snapshot_ready = _snapshot_ready(snapshot_summary)
    scaleout_ready = _scaleout_evidence_ready(execution_summary, route_summary, closeout_summary)
    consumed_queue_summary = _latest_consumed_queue_summary(root, snapshot_dir.name) if snapshot_ready else None
    active_queue_consumed = consumed_queue_summary is not None
    recovered_plan_summary = _latest_recovered_plan_summary(root)
    recovered_plan_ready = bool(
        active_queue_consumed
        and isinstance(recovered_plan_summary, dict)
        and recovered_plan_summary.get("goalAchieved") is True
    )
    goal = bool(snapshot_ready and scaleout_ready and (not active_queue_consumed or recovered_plan_ready))

    if not snapshot_ready:
        primary_blocker = BLOCKER_SNAPSHOT_MISSING
        next_lever = "video_to_analysis_next_sample_selection_snapshot"
        english = "Latest growth-lane next-sample snapshot is missing or unsafe; do not close the growth lane yet."
    elif not scaleout_ready:
        primary_blocker = BLOCKER_SCALEOUT_EVIDENCE_MISSING
        next_lever = "video_to_analysis_real_video_scaleout_lane_closeout"
        english = "Matching scaleout evidence is missing or unsafe; close the scaleout evidence before growth-lane closeout."
    elif active_queue_consumed and not recovered_plan_ready:
        primary_blocker = "video_to_analysis_growth_lane_closeout_recovered_plan_missing"
        next_lever = "video_to_analysis_real_video_scaleout_plan_refresh"
        english = "Latest growth-lane queue is consumed; recover a fresh optional scaleout plan before closeout."
    else:
        primary_blocker = None
        next_lever = NEXT_MANUAL_STRATEGIC_CHOICE
        queue_phrase = (
            f"The latest queue was consumed and recovered into optional future plan `{recovered_plan_summary['dirName']}`."
            if active_queue_consumed and recovered_plan_summary
            else "The active queue remains optional future input."
        )
        english = (
            f"Growth lane is closed at {snapshot_dir.name}. "
            f"{queue_phrase} Choose the next strategic lane manually instead of auto-consuming more bounded samples."
        )

    candidate_ids = list(snapshot_summary.get("candidateSampleIds") or []) if isinstance(snapshot_summary, dict) else []
    manifest = {
        "schemaVersion": "video_to_analysis_growth_lane_closeout_readout_manifest_v1",
        "generatedAt": utc_now_iso(),
        "growthLaneCloseoutReady": goal,
        "growthLaneClosedAtSnapshotDir": snapshot_dir.name if snapshot_ready else None,
        "growthLaneClosedAtVersion": closed_version if snapshot_ready else None,
        "matchingScaleoutExecutionDir": execution_dir.name,
        "matchingScaleoutRouteBindingDir": route_dir.name,
        "matchingScaleoutCloseoutDir": closeout_dir.name,
        "latestConsumedQueueApprovalDir": consumed_queue_summary.get("dirName") if consumed_queue_summary else None,
        "activeQueueConsumed": active_queue_consumed,
        "optionalFutureScaleoutPlanDir": recovered_plan_summary.get("dirName") if recovered_plan_summary else None,
        "optionalFutureScaleoutPlanReady": recovered_plan_ready,
        "activeQueueCandidateIds": candidate_ids,
        "activeQueueRemainsValidForOptionalFutureGrowth": bool(goal and not active_queue_consumed),
        "autoContinueBoundedGrowthRecommended": False,
        "manualStrategicChoiceRequired": goal,
    }
    guardrail_audit = {
        "schemaVersion": "video_to_analysis_growth_lane_closeout_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "snapshotGuardrailsPreserved": _guardrails_false(snapshot_summary),
        "executionGuardrailsPreserved": _guardrails_false(execution_summary),
        "routeGuardrailsPreserved": _guardrails_false(route_summary),
        "closeoutGuardrailsPreserved": _guardrails_false(closeout_summary),
        "allMutationGuardrailsPreserved": bool(
            _guardrails_false(snapshot_summary)
            and _guardrails_false(execution_summary)
            and _guardrails_false(route_summary)
            and _guardrails_false(closeout_summary)
        ),
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
    }
    operator_readout = "\n".join(
        [
            "# Video-to-analysis growth lane closeout readout",
            "",
            f"Closed at: `{manifest['growthLaneClosedAtSnapshotDir']}`",
            "",
            "## Decision",
            "",
            (
                "The bounded growth loop has proven repeatability and is closed for this roadmap module. "
                + (
                    f"The latest queue has already been consumed; `{manifest['optionalFutureScaleoutPlanDir']}` is optional future growth, not unfinished work."
                    if manifest["activeQueueConsumed"]
                    else "The queued samples remain valid, but consuming them is optional future growth, not unfinished work."
                )
            )
            if goal
            else "Growth lane closeout is blocked by missing or unsafe generated truth.",
            "",
            "## Optional future queue",
            "",
            *[f"- `{sample_id}`" for sample_id in candidate_ids],
            "",
        ]
    )

    summary = guarded_summary(
        batch_name="video_to_analysis_growth_lane_closeout_readout",
        goal=goal,
        primary_blocker=primary_blocker,
        next_lever=next_lever,
        english=english,
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "growthLaneCloseoutReady": goal,
            "growthLaneClosedAtSnapshotDir": manifest["growthLaneClosedAtSnapshotDir"],
            "growthLaneClosedAtVersion": manifest["growthLaneClosedAtVersion"],
            "activeQueueCandidateCount": len(candidate_ids),
            "activeQueueCandidateIds": candidate_ids,
            "activeQueueConsumed": active_queue_consumed,
            "latestConsumedQueueApprovalDir": manifest["latestConsumedQueueApprovalDir"],
            "optionalFutureScaleoutPlanDir": manifest["optionalFutureScaleoutPlanDir"],
            "optionalFutureScaleoutPlanReady": recovered_plan_ready,
            "autoContinueBoundedGrowthRecommended": False,
            "manualStrategicChoiceRequired": goal,
        },
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="growth_lane_closeout_readout_summary.json",
        summary=summary,
        artifacts={
            "growth_lane_closeout_readout_manifest.json": manifest,
            "growth_lane_closeout_guardrail_audit.json": guardrail_audit,
            "operator_growth_lane_closeout_readout.json": {"markdown": operator_readout},
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Growth Lane Closeout Readout",
    )


def main() -> None:
    main_for("Close out the current video-to-analysis bounded growth lane.", run_video_to_analysis_growth_lane_closeout_readout)


if __name__ == "__main__":
    main()
