from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_CLOSEOUT_DIR_NAME = "football_external_benchmark_lane_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_operationalization_plan_v1"

BLOCKER_CLOSEOUT_MISSING = "football_external_benchmark_lane_closeout_missing"
BLOCKER_GUARDRAIL_VIOLATION = "football_external_benchmark_operationalization_guardrail_violation"
BLOCKER_CONTRACT_GAP = "football_external_benchmark_operationalization_contract_gap"

NEXT_CLOSEOUT = "football_external_benchmark_lane_closeout"
NEXT_EVIDENCE_REPAIR = "football_external_benchmark_lane_closeout_evidence_repair"
NEXT_CONTRACT_REPAIR = "football_external_benchmark_operationalization_contract_repair"
NEXT_PRODUCT_DECISION_SURFACE = "football_external_benchmark_product_decision_surface"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_operationalization_plan",
            "successCriteria": [
                "derive a product decision surface contract from closed benchmark lane truth",
                "name next milestones that do not overclaim detector evaluation readiness",
                "preserve no data/video download, no training, no promotion, no normal storage mutation, no candidate readiness, and no runtime mutation",
            ],
            "failureAdaptation": "If closeout truth is missing, route back to benchmark lane closeout.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_operationalization_contract_repair",
            "successCriteria": [
                "repair only the derived plan or contract artifacts",
                "keep all source lane and benchmark lane truth immutable",
            ],
            "failureAdaptation": "If guardrails are violated, route to lane closeout evidence repair.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_operationalization_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to closeout, evidence repair, contract repair, or product decision surface.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, closeout_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    closeout_root = candidate_root / closeout_dir_name
    return {
        "candidateRoot": candidate_root,
        "closeoutRoot": closeout_root,
        "summary": _load_json(closeout_root / "external_benchmark_lane_closeout_summary.json"),
        "capability": _load_json(closeout_root / "external_benchmark_capability_matrix.json"),
        "gaps": _load_json(closeout_root / "remaining_gap_analysis.json"),
    }


def _closeout_ready(summary: dict[str, Any] | None, capability: dict[str, Any] | None, gaps: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("externalBenchmarkLaneClosed") is True
        and int(summary.get("externalSourceCount") or 0) >= 2
        and summary.get("benchmarkProductUiRouteReady") is True
        and summary.get("apiRoutePath") == "/api/external/benchmark/report"
        and summary.get("htmlRoutePath") == "/external/benchmark/report"
        and isinstance(capability, dict)
        and capability.get("schemaVersion") == "external_benchmark_capability_matrix_v1"
        and capability.get("soccernetAnalysisProductLaneClosed") is True
        and capability.get("soccertrackLaneClosed") is True
        and capability.get("benchmarkProductUiRouteReady") is True
        and isinstance(gaps, dict)
        and gaps.get("nextSafeLever") == "football_external_benchmark_operationalization_plan"
    )


def _guardrails_clear(summary: dict[str, Any] | None, capability: dict[str, Any] | None) -> bool:
    summary = summary if isinstance(summary, dict) else {}
    capability = capability if isinstance(capability, dict) else {}
    return bool(
        summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and capability.get("detectorEvaluationReady") is False
        and capability.get("candidateEvaluationReady") is False
        and capability.get("trainingReady") is False
        and capability.get("promotionReady") is False
        and capability.get("runtimeDefaultMutationReady") is False
    )


def _operationalization_plan(summary: dict[str, Any], capability: dict[str, Any], gaps: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_operationalization_plan_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_benchmark_lane_closeout",
        "externalSourceCount": int(summary.get("externalSourceCount") or 0),
        "availableReadOnlyRoutes": [
            {
                "routeKind": "benchmark_report_api",
                "path": summary.get("apiRoutePath"),
                "source": "external_benchmark_product_ui_route_implementation",
            },
            {
                "routeKind": "benchmark_report_html",
                "path": summary.get("htmlRoutePath"),
                "source": "external_benchmark_product_ui_route_implementation",
            },
            {
                "routeKind": "soccernet_analysis_product",
                "path": "/external/soccernet/full-analysis",
                "source": "football_external_soccernet_analysis_product_lane_closeout",
            },
            {
                "routeKind": "soccertrack_analysis_product",
                "path": "/external/soccertrack/117092/analysis",
                "source": "football_external_soccertrack_lane_closeout",
            },
        ],
        "recommendedMilestones": [
            {
                "order": 1,
                "nextLever": NEXT_PRODUCT_DECISION_SURFACE,
                "purpose": "Expose the external benchmark lane as a read-only product decision surface for humans to compare source coverage and limitations.",
                "allowedOperations": ["read_saved_generated_truth", "render_product_summary", "link_existing_source_routes"],
                "blockedOperations": ["detector_evaluation", "training", "promotion", "runtime_default_mutation", "normal_match_storage_mutation", "data_or_video_download"],
            },
            {
                "order": 2,
                "nextLever": "football_external_benchmark_real_evaluation_design",
                "purpose": "Design a future real detector benchmark using explicit approval gates and finite source scopes.",
                "allowedOperations": ["write_design_contract", "define_metric_contract", "define_approval_gate"],
                "blockedOperations": ["execute_full_benchmark_without_approval", "promote_detector"],
            },
            {
                "order": 3,
                "nextLever": "football_external_benchmark_dataset_governance_plan",
                "purpose": "Define storage, download, credential, and retention policy before scaling beyond generated-truth smoke.",
                "allowedOperations": ["write_governance_contract", "estimate_storage_budget"],
                "blockedOperations": ["unbounded_dataset_download"],
            },
        ],
        "sourceCoverage": {
            "soccernetReportedFrameCount": int(capability.get("soccernetReportedFrameCount") or 0),
            "soccertrackReportedEventCount": int(capability.get("soccertrackReportedEventCount") or 0),
            "soccertrackReportedFrameCount": int(capability.get("soccertrackReportedFrameCount") or 0),
        },
        "carriedForwardGap": gaps.get("remainingPrimaryGap"),
    }


def _product_decision_surface_contract(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_product_decision_surface_contract_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_benchmark_lane_closeout",
        "apiRoutePath": summary.get("apiRoutePath"),
        "htmlRoutePath": summary.get("htmlRoutePath"),
        "productDecisionSurfaceReady": True,
        "requiresLimitationsBanner": True,
        "requiredCopy": [
            "This benchmark surface is generated-truth smoke, not detector evaluation.",
            "No model promotion or runtime default mutation is implied.",
            "Source routes are read-only and should not mutate normal match storage.",
        ],
        "allowsDetectorEvaluationReadiness": False,
        "allowsCandidateEvaluationReadiness": False,
        "allowsTraining": False,
        "allowsPromotion": False,
        "allowsRuntimeDefaultMutation": False,
        "allowsDataDownload": False,
        "allowsVideoDownload": False,
        "allowsNormalMatchStorageMutation": False,
    }


def _stage_gate_transition_plan() -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_stage_gate_transition_plan_v1",
        "generatedAt": _utc_now_iso(),
        "allowedNow": ["read_only_product_decision_surface"],
        "blockedUntilExplicitApproval": [
            "real_detector_benchmark_execution",
            "source_video_download",
            "normal_match_storage_ingestion",
            "candidate_evaluation_readiness",
            "promotion",
            "runtime_default_mutation",
        ],
        "futureGates": [
            {
                "gateName": "real_evaluation_design_gate",
                "requiredBefore": "football_external_benchmark_real_evaluation_execution",
                "requirements": ["finite source scope", "metric contract", "storage budget", "approval artifact"],
            },
            {
                "gateName": "dataset_governance_gate",
                "requiredBefore": "any full external dataset download",
                "requirements": ["credential policy", "disk budget", "retention policy", "license constraints"],
            },
            {
                "gateName": "promotion_boundary_gate",
                "requiredBefore": "any detector promotion or runtime default mutation",
                "requirements": ["candidate evaluation truth", "source robustness truth", "rollback plan"],
            },
        ],
    }


def _risk_register() -> dict[str, Any]:
    risks = [
        {
            "riskId": "benchmark_smoke_overclaim",
            "severity": "high",
            "description": "Generated-truth smoke may be mistaken for real detector benchmark performance.",
            "mitigation": "Keep candidate/evaluation/promotion readiness false until explicit real evaluation gate passes.",
        },
        {
            "riskId": "unbounded_external_download",
            "severity": "high",
            "description": "External source expansion can consume large disk and credentialed bandwidth if not gated.",
            "mitigation": "Require dataset governance and finite scope approval before downloads.",
        },
        {
            "riskId": "normal_match_storage_contamination",
            "severity": "medium",
            "description": "External generated-truth artifacts could be mixed into normal user match storage.",
            "mitigation": "Keep product decision surface read-only over trained_detector_candidates artifacts.",
        },
        {
            "riskId": "roadmap_divergence",
            "severity": "medium",
            "description": "External benchmark work can distract from the main video-to-analysis product path.",
            "mitigation": "Use operationalization plan to bind external outputs to product decisions and keep next levers explicit.",
        },
    ]
    return {
        "schemaVersion": "external_benchmark_operationalization_risk_register_v1",
        "generatedAt": _utc_now_iso(),
        "riskCount": len(risks),
        "risks": risks,
    }


def _audit(plan: dict[str, Any], contract: dict[str, Any], gates: dict[str, Any], risks: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_operationalization_audit_v1",
        "generatedAt": _utc_now_iso(),
        "planHasMilestones": len(plan.get("recommendedMilestones") or []) >= 3,
        "contractKeepsReadinessFalse": contract.get("allowsDetectorEvaluationReadiness") is False
        and contract.get("allowsCandidateEvaluationReadiness") is False
        and contract.get("allowsTraining") is False
        and contract.get("allowsPromotion") is False
        and contract.get("allowsRuntimeDefaultMutation") is False,
        "stageGateHasBlockedOperations": len(gates.get("blockedUntilExplicitApproval") or []) >= 5,
        "riskRegisterHasHighSeverityRisks": any(row.get("severity") == "high" for row in risks.get("risks") or [] if isinstance(row, dict)),
        "operationalizationPlanAuditPassed": bool(
            len(plan.get("recommendedMilestones") or []) >= 3
            and contract.get("allowsDetectorEvaluationReadiness") is False
            and contract.get("allowsCandidateEvaluationReadiness") is False
            and contract.get("allowsTraining") is False
            and contract.get("allowsPromotion") is False
            and contract.get("allowsRuntimeDefaultMutation") is False
            and len(gates.get("blockedUntilExplicitApproval") or []) >= 5
            and any(row.get("severity") == "high" for row in risks.get("risks") or [] if isinstance(row, dict))
        ),
    }


def _classify(closeout_ready: bool, guardrails_clear: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not closeout_ready:
        return (
            BLOCKER_CLOSEOUT_MISSING,
            NEXT_CLOSEOUT,
            False,
            False,
            "External benchmark lane closeout is missing or unsafe; rerun lane closeout before operationalization planning.",
        )
    if not guardrails_clear:
        return (
            BLOCKER_GUARDRAIL_VIOLATION,
            NEXT_EVIDENCE_REPAIR,
            False,
            False,
            "External benchmark operationalization guardrails failed; repair closeout evidence before planning product use.",
        )
    if audit.get("operationalizationPlanAuditPassed") is not True:
        return (
            BLOCKER_CONTRACT_GAP,
            NEXT_CONTRACT_REPAIR,
            False,
            True,
            "External benchmark operationalization plan was derived but failed contract audit.",
        )
    return (
        None,
        NEXT_PRODUCT_DECISION_SURFACE,
        True,
        True,
        "External benchmark operationalization plan is ready. Build the read-only product decision surface next; do not treat this as detector evaluation, training, promotion, or runtime mutation readiness.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool, next_lever: str) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "lane_closeout_missing_or_unsafe", "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING, "primaryBlocker": BLOCKER_CLOSEOUT_MISSING, "nextRecommendedNextLever": NEXT_CLOSEOUT},
            {"condition": "operationalization_guardrail_violation", "selected": primary_blocker == BLOCKER_GUARDRAIL_VIOLATION, "primaryBlocker": BLOCKER_GUARDRAIL_VIOLATION, "nextRecommendedNextLever": NEXT_EVIDENCE_REPAIR},
            {"condition": "operationalization_contract_gap", "selected": primary_blocker == BLOCKER_CONTRACT_GAP, "primaryBlocker": BLOCKER_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "product_decision_surface_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": next_lever},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Operationalization Plan",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Operationalization plan ready: `{summary.get('operationalizationPlanReady')}`",
            f"- External source count: `{summary.get('externalSourceCount')}`",
            f"- API route: `{summary.get('apiRoutePath')}`",
            f"- HTML route: `{summary.get('htmlRoutePath')}`",
            f"- Detector evaluation executed: `{summary.get('detectorEvaluationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_operationalization_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    closeout_dir_name: str = DEFAULT_CLOSEOUT_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_operationalization_plan",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root, candidate_name, closeout_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    summary_input = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    capability_input = inputs.get("capability") if isinstance(inputs.get("capability"), dict) else {}
    gaps_input = inputs.get("gaps") if isinstance(inputs.get("gaps"), dict) else {}

    closeout_ready = _closeout_ready(inputs.get("summary"), inputs.get("capability"), inputs.get("gaps"))
    guardrails_clear = _guardrails_clear(inputs.get("summary"), inputs.get("capability"))
    plan = _operationalization_plan(summary_input, capability_input, gaps_input)
    contract = _product_decision_surface_contract(summary_input)
    gates = _stage_gate_transition_plan()
    risks = _risk_register()
    audit = _audit(plan, contract, gates, risks)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(closeout_ready, guardrails_clear, audit)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_operationalization_plan",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_lane_closeout",
        "operationalizationPlanReady": goal_achieved,
        "productDecisionSurfaceReady": goal_achieved,
        "externalBenchmarkLaneClosed": summary_input.get("externalBenchmarkLaneClosed"),
        "externalSourceCount": int(summary_input.get("externalSourceCount") or 0),
        "apiRoutePath": summary_input.get("apiRoutePath"),
        "htmlRoutePath": summary_input.get("htmlRoutePath"),
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
        "benchmarkOperationalizationPlan": plan,
        "productDecisionSurfaceContract": contract,
        "stageGateTransitionPlan": gates,
        "riskRegister": risks,
        "operationalizationAudit": audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "external_benchmark_operationalization_summary.json", summary)
    _write_json(output_root / "benchmark_operationalization_plan.json", plan)
    _write_json(output_root / "product_decision_surface_contract.json", contract)
    _write_json(output_root / "stage_gate_transition_plan.json", gates)
    _write_json(output_root / "risk_register.json", risks)
    _write_json(output_root / "operationalization_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan product operationalization for the closed external benchmark lane.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--closeout-dir-name", default=DEFAULT_CLOSEOUT_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="external_benchmark_operationalization_plan")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_benchmark_operationalization_plan(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        closeout_dir_name=str(args.closeout_dir_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
