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

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_roadmap_state_reconciliation_v1"

NEXT_RUNTIME_ROLLOUT = "v7_3_runtime_default_rollout_closeout"
NEXT_RELEASE_CLOSEOUT = "video_to_analysis_release_candidate_closeout"
NEXT_PRODUCT_CLOSEOUT = "video_to_analysis_product_lane_closeout"
NEXT_MONITORING_CLOSEOUT = "video_to_analysis_post_release_monitoring_closeout"
NEXT_DETECTOR_CLOSEOUT = "video_to_analysis_detector_evaluation_lane_closeout"
NEXT_RELEASE_ARCHIVE = "video_to_analysis_release_acceptance_archive"
NEXT_STRATEGIC_SELECTOR = "video_to_analysis_next_strategic_lane_selection"

BLOCKER_RUNTIME_ROLLOUT = "video_to_analysis_reconciliation_runtime_rollout_incomplete"
BLOCKER_RELEASE_CLOSEOUT = "video_to_analysis_reconciliation_release_candidate_incomplete"
BLOCKER_PRODUCT_CLOSEOUT = "video_to_analysis_reconciliation_product_lane_incomplete"
BLOCKER_MONITORING_CLOSEOUT = "video_to_analysis_reconciliation_monitoring_incomplete"
BLOCKER_DETECTOR_CLOSEOUT = "video_to_analysis_reconciliation_detector_evaluation_incomplete"
BLOCKER_GROWTH_CLOSEOUT = "video_to_analysis_reconciliation_growth_closeout_missing"


def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "roadmap_state_reconciliation",
                "successCriteria": [
                    "read active v7.3 runtime, release, product, monitoring, detector, SoccerNet, and growth closeout truth",
                    "resolve manual strategic sentinel without auto-consuming stale scaleout queues",
                    "select one concrete next family",
                ],
                "failureAdaptation": "If a required closeout is missing, route to the smallest missing closeout family.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "roadmap_state_reference_repair",
                "successCriteria": ["repair only stale artifact references or selector facts"],
                "failureAdaptation": "If state remains contradictory, write blocker truth instead of scaleout.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "roadmap_state_blocker_summary",
                "successCriteria": ["write exactly one blocker and one next family"],
                "failureAdaptation": "Stop without training, promotion mutation, downloads, or runtime-default mutation.",
            },
        ],
    }


def _ok(summary: dict[str, Any] | None, *, flag: str | None = None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and (flag is None or summary.get(flag) is True)
    )


def _latest_growth_closeout(root: Path) -> tuple[Path, dict[str, Any] | None]:
    path = latest_versioned_dir(
        root,
        "video_to_analysis_growth_lane_closeout_readout",
        "video_to_analysis_growth_lane_closeout_readout_v1",
    )
    return path, load_json(path / "growth_lane_closeout_readout_summary.json")


def _latest_selector(root: Path) -> tuple[Path, dict[str, Any] | None]:
    path = latest_versioned_dir(
        root,
        "video_to_analysis_next_strategic_lane_selection",
        "video_to_analysis_next_strategic_lane_selection_v1",
    )
    return path, load_json(path / "next_strategic_lane_selection_summary.json")


def _source_status(root: Path, suite_root: Path, storage_root: Path) -> dict[str, Any]:
    growth_dir, growth_summary = _latest_growth_closeout(root)
    selector_dir, selector_summary = _latest_selector(root)
    runtime_registry = load_json(Path(storage_root) / "runtime" / "promoted_touchline_detector_candidate.json")
    return {
        "runtimeRegistry": runtime_registry,
        "runtimeRollout": load_json(
            suite_root / "v7_3_runtime_default_rollout_closeout_v1" / "runtime_default_rollout_closeout_summary.json"
        ),
        "releaseCandidate": load_json(root / "video_to_analysis_release_candidate_closeout_v1" / "release_candidate_closeout_summary.json"),
        "operatorHandoffRoute": load_json(
            root / "video_to_analysis_operator_handoff_route_binding_v1" / "operator_handoff_route_binding_summary.json"
        ),
        "productLane": load_json(root / "video_to_analysis_product_lane_closeout_v1" / "product_lane_closeout_summary.json"),
        "postReleaseMonitoring": load_json(
            root / "video_to_analysis_post_release_monitoring_closeout_v1" / "post_release_monitoring_closeout_summary.json"
        ),
        "detectorEvaluation": load_json(
            root / "video_to_analysis_detector_evaluation_lane_closeout_v1" / "detector_evaluation_lane_closeout_summary.json"
        ),
        "promotionReview": load_json(root / "video_to_analysis_promotion_review_closeout_v1" / "promotion_review_closeout_summary.json"),
        "soccerNetAnalysis": load_json(
            root / "football_external_soccernet_full_analysis_lane_closeout_v1" / "full_analysis_lane_closeout_summary.json"
        ),
        "soccerTrackAnalysis": load_json(
            root / "football_external_soccertrack_analysis_product_lane_closeout_v1" / "analysis_product_lane_closeout_summary.json"
        ),
        "growthCloseoutDir": growth_dir.name if growth_dir.exists() else None,
        "growthCloseout": growth_summary,
        "strategicSelectorDir": selector_dir.name if selector_dir.exists() else None,
        "strategicSelector": selector_summary,
    }


def _readiness(status: dict[str, Any]) -> dict[str, bool]:
    registry = status.get("runtimeRegistry") if isinstance(status.get("runtimeRegistry"), dict) else {}
    growth = status.get("growthCloseout") if isinstance(status.get("growthCloseout"), dict) else {}
    selector = status.get("strategicSelector") if isinstance(status.get("strategicSelector"), dict) else {}
    return {
        "runtimeDefaultV7_3Active": bool(
            registry.get("trainingCandidateVersion") == "v7.3"
            and registry.get("runtimeUse") == "default_runtime"
            and registry.get("runtimeDefaultMutationExecuted") is True
            and registry.get("postRuntimeDefaultSourceRobustnessValidated") is True
            and registry.get("activeFailingSourceNotViableBlockerPresent") is False
        ),
        "runtimeRolloutClosed": _ok(status.get("runtimeRollout"), flag="runtimeDefaultRolloutClosed"),
        "releaseCandidateClosed": _ok(status.get("releaseCandidate"), flag="videoToAnalysisReleaseCandidateClosed"),
        "operatorHandoffRouteReady": _ok(status.get("operatorHandoffRoute"), flag="operatorHandoffRouteReady"),
        "productLaneClosed": _ok(status.get("productLane"), flag="videoToAnalysisProductLaneClosed"),
        "postReleaseMonitoringClosed": _ok(status.get("postReleaseMonitoring"), flag="postReleaseMonitoringClosed"),
        "detectorEvaluationLaneClosed": _ok(status.get("detectorEvaluation"), flag="detectorEvaluationLaneClosed"),
        "promotionReviewClosed": _ok(status.get("promotionReview"), flag="promotionReviewClosed"),
        "soccerNetAnalysisClosed": _ok(status.get("soccerNetAnalysis")),
        "soccerTrackAnalysisClosed": _ok(status.get("soccerTrackAnalysis")),
        "growthLaneClosedManualChoice": bool(
            _ok(growth, flag="growthLaneCloseoutReady")
            and growth.get("manualStrategicChoiceRequired") is True
            and growth.get("autoContinueBoundedGrowthRecommended") is False
        ),
        "strategicSelectorParkedOnManualSentinel": bool(
            _ok(selector)
            and selector.get("selectedStrategicLane") == "manual_strategic_lane_selection_required"
            and selector.get("nextRecommendedNextLever") == "manual_strategic_lane_selection_required"
        ),
    }


def _classify(readiness: dict[str, bool]) -> tuple[str | None, str, bool, str]:
    if not (readiness["runtimeDefaultV7_3Active"] and readiness["runtimeRolloutClosed"]):
        return (
            BLOCKER_RUNTIME_ROLLOUT,
            NEXT_RUNTIME_ROLLOUT,
            False,
            "v7.3 default runtime is not fully closed out; finish runtime rollout before archive.",
        )
    if not readiness["releaseCandidateClosed"]:
        return (
            BLOCKER_RELEASE_CLOSEOUT,
            NEXT_RELEASE_CLOSEOUT,
            False,
            "Release candidate closeout is incomplete; close it before archiving.",
        )
    if not (readiness["productLaneClosed"] and readiness["operatorHandoffRouteReady"]):
        return (
            BLOCKER_PRODUCT_CLOSEOUT,
            NEXT_PRODUCT_CLOSEOUT,
            False,
            "Product lane or operator handoff route is incomplete; close the product lane first.",
        )
    if not readiness["postReleaseMonitoringClosed"]:
        return (
            BLOCKER_MONITORING_CLOSEOUT,
            NEXT_MONITORING_CLOSEOUT,
            False,
            "Post-release monitoring is incomplete; close that lane before archive.",
        )
    if not readiness["detectorEvaluationLaneClosed"]:
        return (
            BLOCKER_DETECTOR_CLOSEOUT,
            NEXT_DETECTOR_CLOSEOUT,
            False,
            "Detector-evaluation report lane is incomplete; close that lane before archive.",
        )
    if not readiness["growthLaneClosedManualChoice"]:
        return (
            BLOCKER_GROWTH_CLOSEOUT,
            NEXT_STRATEGIC_SELECTOR,
            False,
            "Growth lane closeout truth is missing; reconcile strategic selection before archive.",
        )
    return (
        None,
        NEXT_RELEASE_ARCHIVE,
        True,
        "Roadmap state reconciled: v7.3 is active, product/monitoring/detector lanes are closed, and bounded growth is intentionally not auto-resumed. Archive the release acceptance state next.",
    )


def run_video_to_analysis_roadmap_state_reconciliation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(root, output_dir_name)

    status = _source_status(root, suite_root, storage_root)
    readiness = _readiness(status)
    primary_blocker, next_lever, goal, english = _classify(readiness)
    generated_at = utc_now_iso()
    attempts = _attempt_plan()

    summary = {
        "batchName": "video_to_analysis_roadmap_state_reconciliation",
        "generatedAt": generated_at,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        **readiness,
        "manualStrategicSentinelResolved": goal,
        "autoContinueBoundedGrowthRecommended": False,
        "growthLaneAutoResumeAllowed": False,
        "selectedStrategicLane": "release_acceptance_archive" if goal else None,
        **standard_false_flags(),
        "runtimeDefaultMutationExecuted": readiness["runtimeDefaultV7_3Active"],
        "runtimeDefaultMutationExecutedByThisBatch": False,
        "runtimeDefaultRolloutClosed": readiness["runtimeRolloutClosed"],
        "activeRuntimeDefaultVersion": "v7.3" if readiness["runtimeDefaultV7_3Active"] else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }

    source_truth_manifest = {
        "schemaVersion": "video_to_analysis_roadmap_state_source_truth_manifest_v1",
        "generatedAt": generated_at,
        "sourceArtifacts": {
            "runtimeRegistry": "backend/storage/runtime/promoted_touchline_detector_candidate.json",
            "runtimeRollout": "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/v7_3_runtime_default_rollout_closeout_v1/runtime_default_rollout_closeout_summary.json",
            "releaseCandidate": "video_to_analysis_release_candidate_closeout_v1/release_candidate_closeout_summary.json",
            "productLane": "video_to_analysis_product_lane_closeout_v1/product_lane_closeout_summary.json",
            "postReleaseMonitoring": "video_to_analysis_post_release_monitoring_closeout_v1/post_release_monitoring_closeout_summary.json",
            "detectorEvaluation": "video_to_analysis_detector_evaluation_lane_closeout_v1/detector_evaluation_lane_closeout_summary.json",
            "growthCloseoutDir": status["growthCloseoutDir"],
            "strategicSelectorDir": status["strategicSelectorDir"],
        },
    }
    stale_surface_audit = {
        "schemaVersion": "video_to_analysis_stale_surface_reconciliation_audit_v1",
        "generatedAt": generated_at,
        "strategicSelectorParkedOnManualSentinel": readiness["strategicSelectorParkedOnManualSentinel"],
        "manualSentinelTreatedAsResolvedByThisBatch": goal,
        "reason": "The newer closeout/product/runtime artifacts prove archive is the next concrete lane; bounded scaleout is optional future work, not automatic continuation.",
    }
    next_five = {
        "schemaVersion": "video_to_analysis_next_five_step_plan_v1",
        "generatedAt": generated_at,
        "steps": [
            {"order": 1, "lever": NEXT_RELEASE_ARCHIVE, "status": "selected_now" if goal else "blocked"},
            {"order": 2, "lever": "video_to_analysis_steady_state_monitoring_cycle", "status": "maintenance_after_archive"},
            {"order": 3, "lever": "football_external_soccernet_broader_validation_choice", "status": "optional_growth"},
            {"order": 4, "lever": "video_to_analysis_upload_to_analysis_walkthrough", "status": "product_polish"},
            {"order": 5, "lever": "v7_4_training_decision_from_real_misses", "status": "only_if_new_miss_truth_accumulates"},
        ],
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_roadmap_state_reconciliation_decision_matrix_v1",
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "runtime_rollout_incomplete", "selected": primary_blocker == BLOCKER_RUNTIME_ROLLOUT, "nextRecommendedNextLever": NEXT_RUNTIME_ROLLOUT},
            {"condition": "release_candidate_incomplete", "selected": primary_blocker == BLOCKER_RELEASE_CLOSEOUT, "nextRecommendedNextLever": NEXT_RELEASE_CLOSEOUT},
            {"condition": "product_lane_incomplete", "selected": primary_blocker == BLOCKER_PRODUCT_CLOSEOUT, "nextRecommendedNextLever": NEXT_PRODUCT_CLOSEOUT},
            {"condition": "monitoring_incomplete", "selected": primary_blocker == BLOCKER_MONITORING_CLOSEOUT, "nextRecommendedNextLever": NEXT_MONITORING_CLOSEOUT},
            {"condition": "detector_evaluation_incomplete", "selected": primary_blocker == BLOCKER_DETECTOR_CLOSEOUT, "nextRecommendedNextLever": NEXT_DETECTOR_CLOSEOUT},
            {"condition": "release_archive_ready", "selected": goal, "nextRecommendedNextLever": NEXT_RELEASE_ARCHIVE},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="roadmap_state_reconciliation_summary.json",
        summary=summary,
        artifacts={
            "roadmap_state_source_truth_manifest.json": source_truth_manifest,
            "roadmap_state_readiness_matrix.json": {"generatedAt": generated_at, "readiness": readiness},
            "stale_surface_reconciliation_audit.json": stale_surface_audit,
            "next_five_step_plan.json": next_five,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": attempts,
        },
        markdown_title="Video To Analysis Roadmap State Reconciliation",
    )


def main() -> None:
    main_for("Reconcile current video-to-analysis roadmap state.", run_video_to_analysis_roadmap_state_reconciliation)


if __name__ == "__main__":
    main()
