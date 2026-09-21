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

DEFAULT_STEADY_STATE_DIR_NAME = "video_to_analysis_steady_state_monitoring_cycle_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_operational_backlog_prioritization_v1"

BLOCKER_STEADY_STATE_MISSING = "video_to_analysis_operational_backlog_steady_state_missing"
NEXT_STEADY_STATE = "video_to_analysis_steady_state_monitoring_cycle"
NEXT_STORAGE_HYGIENE = "video_to_analysis_storage_retention_and_artifact_hygiene"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "operational_backlog_prioritization",
                "successCriteria": [
                    "steady-state monitoring truth is healthy",
                    "prioritized operational backlog is written",
                    "exact next lever is selected",
                ],
                "failureAdaptation": "If steady-state truth is missing or unhealthy, route back to steady-state monitoring.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "operational_backlog_scope_repair",
                "successCriteria": ["repair backlog ordering or missing decision metadata only"],
                "failureAdaptation": "Do not train, download data, mutate runtime defaults, or broaden scope while repairing backlog truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "operational_backlog_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary and preserve promoted runtime guardrails.",
            },
        ],
    }


def _steady_state_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("steadyStateMonitoringCyclePassed") is True
        and summary.get("promotedRuntimeHealthy") is True
        and summary.get("releasedRuntimeVersion") in {"v7.2", "v7.3"}
        and (
            summary.get("registryMatchesActiveDefaultRuntime") is True
            or summary.get("registryMatchesPromotedV7_2DefaultRuntime") is True
        )
        and summary.get("routeSmokePassedCount") == 5
        and summary.get("oldFailingSourceNotViableBlockerDead") is True
        and isinstance(audit, dict)
        and audit.get("allSteadyStateChecksPassed") is True
    )


def _backlog_items() -> list[dict[str, Any]]:
    return [
        {
            "id": "storage_retention_and_artifact_hygiene",
            "title": "Put generated artifacts, caches, and large external data under a clear retention contract",
            "whyNow": "The runtime is healthy; the next risk is disk/repo clutter hiding real state or exhausting local storage.",
            "nextLever": NEXT_STORAGE_HYGIENE,
            "scope": "storage_inventory_retention_policy_and_cleanup_plan",
            "allowedActions": ["inventory generated artifact families", "write retention policy", "identify cleanup-safe cache paths"],
            "forbiddenActions": ["delete user work", "delete generated truth", "download datasets", "train models", "mutate runtime defaults"],
        },
        {
            "id": "operator_dashboard_polish",
            "title": "Polish the operator-visible dashboard for current runtime, health, and next action",
            "whyNow": "The system is operational; users need one glanceable place to understand runtime health and current outputs.",
            "nextLever": "video_to_analysis_operator_dashboard_polish",
            "scope": "product_route_view_model_and_html_only",
            "allowedActions": ["bind existing health truth", "render current runtime and latest reports"],
            "forbiddenActions": ["rerun detector evaluation", "change promotion state", "mutate normal match storage"],
        },
        {
            "id": "external_benchmark_real_source_path_consolidation",
            "title": "Consolidate SoccerNet/SoccerTrack real-source access paths under bounded storage governance",
            "whyNow": "External data paths exist but need a clean, space-aware execution lane before larger runs.",
            "nextLever": "football_external_benchmark_real_source_path_consolidation",
            "scope": "governance_and_access_path_selection",
            "allowedActions": ["summarize existing source artifacts", "select bounded fetch path", "preserve credentials policy"],
            "forbiddenActions": ["full dataset download", "unbounded archive extraction", "training"],
        },
        {
            "id": "real_video_scaleout_plan",
            "title": "Plan scaling from accepted videos to more auditable video-to-analysis outputs",
            "whyNow": "After health and hygiene, the product can move from acceptance cases toward more real video coverage.",
            "nextLever": "video_to_analysis_real_video_scaleout_plan",
            "scope": "execution_plan_and_gate_design",
            "allowedActions": ["choose bounded sample set", "define acceptance metrics", "write approval gate"],
            "forbiddenActions": ["unapproved bulk processing", "runtime mutation", "training"],
        },
        {
            "id": "steady_state_monitoring_recurring_schedule",
            "title": "Define recurring steady-state monitoring cadence and alert/blocker routing",
            "whyNow": "The first steady-state cycle passed; recurrence should be documented after the immediate storage risk is bounded.",
            "nextLever": "video_to_analysis_steady_state_monitoring_recurring_schedule",
            "scope": "monitoring_contract_only",
            "allowedActions": ["write cadence", "write failure routing", "connect existing health artifacts"],
            "forbiddenActions": ["new infrastructure deployment", "runtime mutation", "training"],
        },
    ]


def run_video_to_analysis_operational_backlog_prioritization(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    steady_state_root = root / DEFAULT_STEADY_STATE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    steady_summary = load_json(steady_state_root / "steady_state_monitoring_cycle_summary.json")
    steady_audit = load_json(steady_state_root / "steady_state_monitoring_cycle_audit.json")
    ready = _steady_state_ready(steady_summary, steady_audit)
    items = _backlog_items()
    priority_order = [item["id"] for item in items]

    if ready:
        goal = True
        primary_blocker = None
        next_lever = NEXT_STORAGE_HYGIENE
        english = "Operational backlog is prioritized. Start with storage retention and artifact hygiene before more scaleout."
    else:
        goal = False
        primary_blocker = BLOCKER_STEADY_STATE_MISSING
        next_lever = NEXT_STEADY_STATE
        english = "Steady-state monitoring truth is missing or unhealthy; run the monitoring cycle before prioritizing backlog."

    backlog = {
        "schemaVersion": "video_to_analysis_operational_backlog_prioritization_v1",
        "generatedAt": utc_now_iso(),
        "sourceSteadyStateBatch": "video_to_analysis_steady_state_monitoring_cycle",
        "priorityOrder": priority_order,
        "selectedOperationalLever": NEXT_STORAGE_HYGIENE if ready else None,
        "backlogItems": items,
        "selectionRationale": {
            "runtimeAlreadyOperational": ready,
            "storageAndArtifactHygieneFirst": ready,
            "reason": "A healthy promoted runtime should be protected from artifact sprawl before expanding real-video/data work.",
        },
    }
    scope_guardrail = {
        "schemaVersion": "video_to_analysis_operational_backlog_scope_guardrail_v1",
        "generatedAt": utc_now_iso(),
        "detectorEvaluationAllowed": False,
        "candidateEvaluationAllowed": False,
        "videoDownloadAllowed": False,
        "dataDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionMutationAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "normalMatchStorageMutationAllowed": False,
        "scopeGuardrailPassed": True,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "steady_state_missing_or_unhealthy",
                "selected": not ready,
                "primaryBlocker": BLOCKER_STEADY_STATE_MISSING,
                "nextRecommendedNextLever": NEXT_STEADY_STATE,
            },
            {
                "condition": "steady_state_healthy",
                "selected": ready,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_STORAGE_HYGIENE,
            },
        ],
    }
    summary = {
        "batchName": "video_to_analysis_operational_backlog_prioritization",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "operationalBacklogPrioritized": goal,
        "selectedOperationalLever": NEXT_STORAGE_HYGIENE if ready else None,
        "backlogItemCount": len(items),
        "sourceSteadyStateMonitoringCyclePassed": bool(steady_summary and steady_summary.get("steadyStateMonitoringCyclePassed") is True),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="operational_backlog_prioritization_summary.json",
        summary=summary,
        artifacts={
            "operational_backlog_prioritization.json": backlog,
            "operational_backlog_scope_guardrail.json": scope_guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Operational Backlog Prioritization",
    )


def main() -> None:
    main_for(
        "Prioritize the video-to-analysis operational backlog from steady-state runtime truth.",
        run_video_to_analysis_operational_backlog_prioritization,
    )


if __name__ == "__main__":
    main()
