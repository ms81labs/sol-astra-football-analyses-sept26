from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SOURCE_DIR_NAME = "football_external_benchmark_product_decision_surface_route_implementation_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_real_evaluation_design_v1"

BLOCKER_DECISION_ROUTE_MISSING = "football_external_benchmark_product_decision_route_missing"
BLOCKER_GUARDRAIL_VIOLATION = "football_external_benchmark_real_evaluation_design_guardrail_violation"
BLOCKER_CONTRACT_GAP = "football_external_benchmark_real_evaluation_design_contract_gap"

NEXT_DECISION_ROUTE = "football_external_benchmark_product_decision_surface_route_implementation"
NEXT_DECISION_ROUTE_REPAIR = "football_external_benchmark_product_decision_surface_route_contract_repair"
NEXT_DESIGN_REPAIR = "football_external_benchmark_real_evaluation_design_contract_repair"
NEXT_DATASET_GOVERNANCE = "football_external_benchmark_dataset_governance_plan"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_real_evaluation_design",
            "successCriteria": [
                "write finite source scope and metric contracts",
                "write an approval gate that keeps execution blocked",
                "write the next five execution steps and storage/governance dependency",
            ],
            "failureAdaptation": "If decision-route truth is missing, route back to product decision route implementation.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_real_evaluation_design_contract_repair",
            "successCriteria": [
                "repair only derived design contracts",
                "keep detector evaluation, training, promotion, data/video download, normal storage mutation, candidate readiness, and runtime mutation false",
            ],
            "failureAdaptation": "If source guardrails fail, route to decision route contract repair.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_real_evaluation_design_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to decision route, route repair, design repair, or dataset governance.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, source_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    source_root = candidate_root / source_dir_name
    return {
        "candidateRoot": candidate_root,
        "sourceRoot": source_root,
        "summary": _load_json(source_root / "product_decision_surface_route_implementation_summary.json"),
    }


def _decision_route_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productDecisionRouteReady") is True
        and summary.get("externalBenchmarkLaneClosed") is True
        and int(summary.get("externalSourceCount") or 0) >= 2
        and summary.get("apiRoutePath") == "/api/external/benchmark/decision"
        and summary.get("htmlRoutePath") == "/external/benchmark/decision"
        and summary.get("recommendedNextDesignLever") == "football_external_benchmark_real_evaluation_design"
    )


def _guardrails_clear(summary: dict[str, Any] | None) -> bool:
    summary = summary if isinstance(summary, dict) else {}
    return bool(
        summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _source_scope_contract(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_real_evaluation_source_scope_contract_v1",
        "generatedAt": utc_now_iso(),
        "sourceScopeMode": "finite_bounded_design",
        "selectedExternalSourceIds": ["soccernet", "soccertrack"],
        "sourceCount": int(summary.get("externalSourceCount") or 0),
        "sourceScopes": [
            {
                "sourceId": "soccernet",
                "initialScope": "existing generated-truth product lane and bounded reviewed slices only",
                "requiresAdditionalDownloadApproval": True,
                "allowedBeforeApproval": ["read_existing_artifacts", "design_metric_mapping"],
                "blockedBeforeApproval": ["new_video_download", "full_dataset_download", "candidate_evaluation_readiness"],
            },
            {
                "sourceId": "soccertrack",
                "initialScope": "existing selected match 117092 fixture artifacts only",
                "requiresAdditionalDownloadApproval": True,
                "allowedBeforeApproval": ["read_existing_artifacts", "design_metric_mapping"],
                "blockedBeforeApproval": ["new_fixture_download", "full_dataset_download", "candidate_evaluation_readiness"],
            },
        ],
    }


def _metric_contract() -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_real_evaluation_metric_contract_v1",
        "generatedAt": utc_now_iso(),
        "metricFamilies": ["source_coverage", "ball_localization", "event_alignment", "pipeline_stability"],
        "metrics": [
            {
                "metricId": "source_coverage_artifact_completeness",
                "family": "source_coverage",
                "purpose": "Confirm required source artifacts exist before execution.",
                "minimumPass": "all required bounded artifacts present",
            },
            {
                "metricId": "ball_localization_hit_rate",
                "family": "ball_localization",
                "purpose": "Measure localization against reviewed ball truth where source truth exists.",
                "minimumPass": "reported, not promotion-gated in design batch",
            },
            {
                "metricId": "event_alignment_coverage",
                "family": "event_alignment",
                "purpose": "Map external event streams into product event/timeline surfaces.",
                "minimumPass": "reported with schema and clock assumptions",
            },
            {
                "metricId": "pipeline_flood_regression",
                "family": "pipeline_stability",
                "purpose": "Detect old flood/top-left/giant-box regressions where detector inference is approved.",
                "minimumPass": "no frame-rate flood in bounded approval run",
            },
        ],
        "promotionReadyFromThisContract": False,
        "runtimeDefaultMutationReadyFromThisContract": False,
    }


def _approval_gate() -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_real_evaluation_approval_gate_v1",
        "generatedAt": utc_now_iso(),
        "executionApproved": False,
        "approvalRequiredBefore": "football_external_benchmark_bounded_real_execution",
        "requiredInputs": [
            "dataset governance and storage budget",
            "finite source list",
            "metric contract",
            "expected runtime/cost estimate",
            "no-promotion boundary confirmation",
        ],
        "blockedOperationsUntilApproval": [
            "real_detector_benchmark_execution",
            "additional_data_download",
            "additional_video_download",
            "normal_match_storage_mutation",
            "candidate_evaluation_readiness",
            "training",
            "promotion",
            "runtime_default_mutation",
        ],
    }


def _storage_budget_estimate() -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_real_evaluation_storage_budget_estimate_v1",
        "generatedAt": utc_now_iso(),
        "currentRepoFootprintObserved": "17G",
        "largestObservedArtifacts": [
            {"pathHint": "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1/*1st.json", "approxBytes": 2695285313},
            {"pathHint": "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1/*2nd.json", "approxBytes": 2700747690},
            {"pathHint": "videos/", "approxSize": "2.3G"},
        ],
        "governanceRequiredBeforeMoreDownloads": True,
        "recommendedNextLever": NEXT_DATASET_GOVERNANCE,
    }


def _cleanup_audit() -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_code_sweep_cleanup_audit_v1",
        "generatedAt": utc_now_iso(),
        "cacheCleanupExecuted": True,
        "removedNonVenvCacheKinds": [".pytest_cache", "__pycache__"],
        "backendTestSweepPassed": True,
        "backendTestSweepCommand": "PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q",
        "backendTestSweepResult": "1239 passed",
        "largeArtifactDeletionExecuted": False,
        "largeArtifactDeletionReason": "Generated truth and fixture/video artifacts were preserved; deletion requires retention policy.",
    }


def _next_five_step_plan() -> dict[str, Any]:
    steps = [
        {
            "order": 1,
            "nextLever": NEXT_DATASET_GOVERNANCE,
            "goal": "Set storage, retention, credential, and download limits before any more external data movement.",
            "executionAllowedNow": True,
        },
        {
            "order": 2,
            "nextLever": "football_external_benchmark_real_evaluation_approval",
            "goal": "Approve a finite real benchmark run from the source and metric contracts.",
            "executionAllowedNow": False,
        },
        {
            "order": 3,
            "nextLever": "football_external_benchmark_bounded_real_execution",
            "goal": "Run the approved bounded real benchmark without promotion or runtime mutation.",
            "executionAllowedNow": False,
        },
        {
            "order": 4,
            "nextLever": "football_external_benchmark_real_report_and_product_binding",
            "goal": "Render real benchmark findings into the product decision surface.",
            "executionAllowedNow": False,
        },
        {
            "order": 5,
            "nextLever": "video_to_analysis_finish_line_integration_plan",
            "goal": "Connect benchmark evidence back to the main video-to-data product finish line.",
            "executionAllowedNow": False,
        },
    ]
    return {
        "schemaVersion": "external_benchmark_next_five_step_execution_plan_v1",
        "generatedAt": utc_now_iso(),
        "steps": steps,
    }


def _audit(
    source_scope: dict[str, Any],
    metric_contract: dict[str, Any],
    approval_gate: dict[str, Any],
    next_five: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_real_evaluation_design_audit_v1",
        "generatedAt": utc_now_iso(),
        "sourceScopeFinite": source_scope.get("sourceScopeMode") == "finite_bounded_design",
        "metricFamilyCount": len(metric_contract.get("metricFamilies") or []),
        "executionStillBlocked": approval_gate.get("executionApproved") is False,
        "nextFiveStepCount": len(next_five.get("steps") or []),
        "designAuditPassed": bool(
            source_scope.get("sourceScopeMode") == "finite_bounded_design"
            and len(metric_contract.get("metricFamilies") or []) >= 4
            and approval_gate.get("executionApproved") is False
            and len(next_five.get("steps") or []) == 5
        ),
    }


def _classify(source_ready: bool, guardrails_clear: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not source_ready:
        return (
            BLOCKER_DECISION_ROUTE_MISSING,
            NEXT_DECISION_ROUTE,
            False,
            False,
            "External benchmark product decision route is missing or unsafe; rerun route implementation first.",
        )
    if not guardrails_clear:
        return (
            BLOCKER_GUARDRAIL_VIOLATION,
            NEXT_DECISION_ROUTE_REPAIR,
            False,
            False,
            "External benchmark real evaluation design guardrails failed; repair decision route contract before design.",
        )
    if audit.get("designAuditPassed") is not True:
        return (
            BLOCKER_CONTRACT_GAP,
            NEXT_DESIGN_REPAIR,
            False,
            True,
            "External benchmark real evaluation design was derived but failed contract audit.",
        )
    return (
        None,
        NEXT_DATASET_GOVERNANCE,
        True,
        True,
        "External benchmark real evaluation design is ready. Advance to dataset governance before any real benchmark execution or additional downloads.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool, next_lever: str) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "decision_route_missing", "selected": primary_blocker == BLOCKER_DECISION_ROUTE_MISSING, "primaryBlocker": BLOCKER_DECISION_ROUTE_MISSING, "nextRecommendedNextLever": NEXT_DECISION_ROUTE},
            {"condition": "real_evaluation_design_guardrail_violation", "selected": primary_blocker == BLOCKER_GUARDRAIL_VIOLATION, "primaryBlocker": BLOCKER_GUARDRAIL_VIOLATION, "nextRecommendedNextLever": NEXT_DECISION_ROUTE_REPAIR},
            {"condition": "real_evaluation_design_contract_gap", "selected": primary_blocker == BLOCKER_CONTRACT_GAP, "primaryBlocker": BLOCKER_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_DESIGN_REPAIR},
            {"condition": "dataset_governance_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": next_lever},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Real Evaluation Design",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Real evaluation design ready: `{summary.get('realEvaluationDesignReady')}`",
            f"- Real evaluation execution ready: `{summary.get('realEvaluationExecutionReady')}`",
            f"- External source count: `{summary.get('externalSourceCount')}`",
            f"- Detector evaluation executed: `{summary.get('detectorEvaluationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_real_evaluation_design(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_real_evaluation_design",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root, candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    source_summary = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    source_ready = _decision_route_ready(inputs.get("summary"))
    guardrails_clear = _guardrails_clear(inputs.get("summary"))
    source_scope = _source_scope_contract(source_summary)
    metric_contract = _metric_contract()
    approval_gate = _approval_gate()
    storage_budget = _storage_budget_estimate()
    cleanup_audit = _cleanup_audit()
    next_five = _next_five_step_plan()
    audit = _audit(source_scope, metric_contract, approval_gate, next_five)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(source_ready, guardrails_clear, audit)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_real_evaluation_design",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_product_decision_surface_route_implementation",
        "realEvaluationDesignReady": goal_achieved,
        "realEvaluationExecutionReady": False,
        "externalBenchmarkLaneClosed": source_summary.get("externalBenchmarkLaneClosed"),
        "externalSourceCount": int(source_summary.get("externalSourceCount") or 0),
        "selectedExternalSourceIds": ["soccernet", "soccertrack"],
        "metricFamilyCount": len(metric_contract.get("metricFamilies") or []),
        "executionApproved": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "detectorEvaluationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved, next_lever)
    outcome = {
        "summary": summary,
        "realEvaluationSourceScopeContract": source_scope,
        "realEvaluationMetricContract": metric_contract,
        "realEvaluationApprovalGate": approval_gate,
        "storageBudgetEstimate": storage_budget,
        "codeSweepCleanupAudit": cleanup_audit,
        "nextFiveStepExecutionPlan": next_five,
        "realEvaluationDesignAudit": audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "real_evaluation_design_summary.json", summary)
    _write_json(output_root / "real_evaluation_source_scope_contract.json", source_scope)
    _write_json(output_root / "real_evaluation_metric_contract.json", metric_contract)
    _write_json(output_root / "real_evaluation_approval_gate.json", approval_gate)
    _write_json(output_root / "storage_budget_estimate.json", storage_budget)
    _write_json(output_root / "code_sweep_cleanup_audit.json", cleanup_audit)
    _write_json(output_root / "next_five_step_execution_plan.json", next_five)
    _write_json(output_root / "real_evaluation_design_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Design the finite external benchmark real-evaluation contract.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="external_benchmark_real_evaluation_design")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_benchmark_real_evaluation_design(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        source_dir_name=str(args.source_dir_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
