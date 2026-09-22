from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from html import escape
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SOURCE_DIR_NAME = "football_external_benchmark_operationalization_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_product_decision_surface_v1"

BLOCKER_OPERATIONALIZATION_MISSING = "football_external_benchmark_operationalization_plan_missing"
BLOCKER_GUARDRAIL_VIOLATION = "football_external_benchmark_product_decision_surface_guardrail_violation"
BLOCKER_CONTRACT_GAP = "football_external_benchmark_product_decision_surface_contract_gap"

NEXT_OPERATIONALIZATION_PLAN = "football_external_benchmark_operationalization_plan"
NEXT_CONTRACT_REPAIR = "football_external_benchmark_operationalization_contract_repair"
NEXT_SURFACE_CONTRACT_REPAIR = "football_external_benchmark_product_decision_surface_contract_repair"
NEXT_ROUTE_IMPLEMENTATION = "football_external_benchmark_product_decision_surface_route_implementation"
NEXT_REAL_EVALUATION_DESIGN = "football_external_benchmark_real_evaluation_design"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_product_decision_surface",
            "successCriteria": [
                "render a route-ready read-only product decision surface from operationalization truth",
                "carry explicit limitations that generated-truth smoke is not detector evaluation",
                "select route implementation while keeping real evaluation, training, promotion, download, and runtime mutation blocked",
            ],
            "failureAdaptation": "If operationalization truth is missing, route back to operationalization planning.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_product_decision_surface_contract_repair",
            "successCriteria": [
                "repair only derived view-model, render, or route-contract artifacts",
                "preserve source operationalization truth and all safety guardrails",
            ],
            "failureAdaptation": "If source guardrails fail, route back to operationalization contract repair.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_product_decision_surface_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to operationalization, contract repair, or route implementation.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, source_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    source_root = candidate_root / source_dir_name
    return {
        "candidateRoot": candidate_root,
        "sourceRoot": source_root,
        "summary": _load_json(source_root / "external_benchmark_operationalization_summary.json"),
        "plan": _load_json(source_root / "benchmark_operationalization_plan.json"),
        "contract": _load_json(source_root / "product_decision_surface_contract.json"),
        "gates": _load_json(source_root / "stage_gate_transition_plan.json"),
        "risks": _load_json(source_root / "risk_register.json"),
    }


def _operationalization_ready(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("summary")
    plan = inputs.get("plan")
    contract = inputs.get("contract")
    gates = inputs.get("gates")
    risks = inputs.get("risks")
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("operationalizationPlanReady") is True
        and summary.get("productDecisionSurfaceReady") is True
        and int(summary.get("externalSourceCount") or 0) >= 2
        and isinstance(plan, dict)
        and plan.get("schemaVersion") == "external_benchmark_operationalization_plan_v1"
        and len(plan.get("recommendedMilestones") or []) >= 3
        and isinstance(contract, dict)
        and contract.get("schemaVersion") == "external_benchmark_product_decision_surface_contract_v1"
        and contract.get("productDecisionSurfaceReady") is True
        and isinstance(gates, dict)
        and "read_only_product_decision_surface" in (gates.get("allowedNow") or [])
        and isinstance(risks, dict)
        and int(risks.get("riskCount") or 0) >= 2
    )


def _guardrails_clear(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    contract = inputs.get("contract") if isinstance(inputs.get("contract"), dict) else {}
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
        and contract.get("allowsDetectorEvaluationReadiness") is False
        and contract.get("allowsCandidateEvaluationReadiness") is False
        and contract.get("allowsTraining") is False
        and contract.get("allowsPromotion") is False
        and contract.get("allowsRuntimeDefaultMutation") is False
        and contract.get("allowsDataDownload") is False
        and contract.get("allowsVideoDownload") is False
        and contract.get("allowsNormalMatchStorageMutation") is False
    )


def _recommendation_matrix(plan: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    milestones = [row for row in plan.get("recommendedMilestones") or [] if isinstance(row, dict)]
    real_eval = next((row for row in milestones if row.get("nextLever") == NEXT_REAL_EVALUATION_DESIGN), {})
    governance = next((row for row in milestones if row.get("nextLever") == "football_external_benchmark_dataset_governance_plan"), {})
    return {
        "schemaVersion": "external_benchmark_decision_recommendation_matrix_v1",
        "generatedAt": utc_now_iso(),
        "recommendedNextLever": NEXT_REAL_EVALUATION_DESIGN,
        "routeImplementationNextLever": NEXT_ROUTE_IMPLEMENTATION,
        "decisions": [
            {
                "decisionId": "build_read_only_decision_surface_route",
                "priority": 1,
                "status": "ready",
                "nextLever": NEXT_ROUTE_IMPLEMENTATION,
                "why": "The decision surface artifact is route-ready and safe to expose as read-only product context.",
            },
            {
                "decisionId": "design_real_detector_benchmark",
                "priority": 2,
                "status": "planned_after_surface_route",
                "nextLever": real_eval.get("nextLever") or NEXT_REAL_EVALUATION_DESIGN,
                "why": real_eval.get("purpose") or "A real benchmark needs explicit metric and approval contracts.",
            },
            {
                "decisionId": "define_dataset_governance",
                "priority": 3,
                "status": "planned_after_surface_route",
                "nextLever": governance.get("nextLever") or "football_external_benchmark_dataset_governance_plan",
                "why": governance.get("purpose") or "Downloads and retention need governance before scale.",
            },
        ],
        "allowedNow": list(gates.get("allowedNow") or []),
        "blockedUntilExplicitApproval": list(gates.get("blockedUntilExplicitApproval") or []),
    }


def _view_model(summary: dict[str, Any], plan: dict[str, Any], contract: dict[str, Any], gates: dict[str, Any], risks: dict[str, Any], recommendations: dict[str, Any]) -> dict[str, Any]:
    source_coverage = plan.get("sourceCoverage") if isinstance(plan.get("sourceCoverage"), dict) else {}
    return {
        "schemaVersion": "external_benchmark_product_decision_surface_view_model_v1",
        "generatedAt": utc_now_iso(),
        "hero": {
            "title": "External Benchmark Decision Surface",
            "subtitle": "Read-only product context for SoccerNet and SoccerTrack generated-truth benchmark smoke.",
        },
        "limitationsBanner": "This is generated-truth smoke, not detector evaluation, not training evidence, not promotion evidence, and not runtime-default mutation evidence.",
        "sourceSummary": {
            "externalSourceCount": int(summary.get("externalSourceCount") or 0),
            "soccernetReportedFrameCount": int(source_coverage.get("soccernetReportedFrameCount") or 0),
            "soccertrackReportedEventCount": int(source_coverage.get("soccertrackReportedEventCount") or 0),
            "soccertrackReportedFrameCount": int(source_coverage.get("soccertrackReportedFrameCount") or 0),
        },
        "cards": [
            {"label": "Sources", "value": int(summary.get("externalSourceCount") or 0)},
            {"label": "Decision", "value": "read-only"},
            {"label": "Real eval", "value": "gated"},
            {"label": "Runtime", "value": "frozen"},
        ],
        "readOnlyRoutes": list(plan.get("availableReadOnlyRoutes") or []),
        "requiredCopy": list(contract.get("requiredCopy") or []),
        "recommendations": recommendations.get("decisions") or [],
        "allowedNow": list(gates.get("allowedNow") or []),
        "blockedUntilExplicitApproval": list(gates.get("blockedUntilExplicitApproval") or []),
        "riskSummary": {
            "riskCount": int(risks.get("riskCount") or 0),
            "highSeverityRiskIds": [
                row.get("riskId")
                for row in risks.get("risks") or []
                if isinstance(row, dict) and row.get("severity") == "high"
            ],
        },
        "readiness": {
            "productDecisionSurfaceReady": True,
            "productDecisionRouteImplementationReady": True,
            "detectorEvaluationReady": False,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
            "dataDownloadReady": False,
            "normalMatchStorageMutationReady": False,
        },
    }


def _route_contract(view_model: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_product_decision_surface_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "routeName": "ExternalBenchmarkDecisionSurface",
        "apiRoutePath": "/api/external/benchmark/decision",
        "htmlRoutePath": "/external/benchmark/decision",
        "viewModelSchemaVersion": view_model.get("schemaVersion"),
        "productDecisionSurfaceReady": True,
        "productDecisionRouteImplementationReady": True,
        "requiresLimitationsBanner": True,
        "allowsDetectorEvaluationReadiness": False,
        "allowsCandidateEvaluationReadiness": False,
        "allowsTraining": False,
        "allowsPromotion": False,
        "allowsRuntimeDefaultMutation": False,
        "allowsDataDownload": False,
        "allowsVideoDownload": False,
        "allowsNormalMatchStorageMutation": False,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    title = str(view_model.get("hero", {}).get("title") or "External Benchmark Decision Surface")
    subtitle = str(view_model.get("hero", {}).get("subtitle") or "")
    banner = str(view_model.get("limitationsBanner") or "")
    cards = "".join(
        f'<article class="card"><div class="label">{escape(str(card.get("label", "")))}</div><div class="value">{escape(str(card.get("value", "")))}</div></article>'
        for card in view_model.get("cards", [])
        if isinstance(card, dict)
    )
    recs = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('decisionId', '')))}</td>"
        f"<td>{escape(str(row.get('status', '')))}</td>"
        f"<td>{escape(str(row.get('nextLever', '')))}</td>"
        f"<td>{escape(str(row.get('why', '')))}</td>"
        "</tr>"
        for row in view_model.get("recommendations", [])
        if isinstance(row, dict)
    )
    blocked = "".join(f"<li>{escape(str(row))}</li>" for row in view_model.get("blockedUntilExplicitApproval", []))
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      body {{ margin: 0; font-family: Arial, sans-serif; color: #172033; background: #fff; }}
      main {{ max-width: 1120px; margin: 0 auto; padding: 32px; }}
      .banner {{ border-left: 4px solid #b45309; background: #fffbeb; padding: 12px 14px; margin: 20px 0; }}
      .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
      .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 14px; }}
      .label {{ color: #4b5563; font-size: 12px; text-transform: uppercase; }}
      .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
      th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }}
    </style>
  </head>
  <body>
    <main>
      <h1>{escape(title)}</h1>
      <p>{escape(subtitle)}</p>
      <section class="banner">{escape(banner)}</section>
      <section class="grid">{cards}</section>
      <h2>Recommended decisions</h2>
      <table>
        <thead><tr><th>Decision</th><th>Status</th><th>Next lever</th><th>Why</th></tr></thead>
        <tbody>{recs}</tbody>
      </table>
      <h2>Still blocked</h2>
      <ul>{blocked}</ul>
    </main>
  </body>
</html>
"""


def _guardrail_audit(inputs: dict[str, Any], route_contract: dict[str, Any], view_model: dict[str, Any]) -> dict[str, Any]:
    readiness = view_model.get("readiness") if isinstance(view_model.get("readiness"), dict) else {}
    checks = {
        "sourceOperationalizationReady": _operationalization_ready(inputs),
        "sourceGuardrailsClear": _guardrails_clear(inputs),
        "routeContractReadinessFalse": route_contract.get("allowsDetectorEvaluationReadiness") is False
        and route_contract.get("allowsCandidateEvaluationReadiness") is False
        and route_contract.get("allowsTraining") is False
        and route_contract.get("allowsPromotion") is False
        and route_contract.get("allowsRuntimeDefaultMutation") is False,
        "viewModelReadinessFalse": readiness.get("detectorEvaluationReady") is False
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
        and readiness.get("dataDownloadReady") is False
        and readiness.get("normalMatchStorageMutationReady") is False,
    }
    return {
        "schemaVersion": "external_benchmark_product_decision_surface_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "allGuardrailsPassed": all(checks.values()),
    }


def _classify(operationalization_ready: bool, guardrails_clear: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not operationalization_ready:
        return (
            BLOCKER_OPERATIONALIZATION_MISSING,
            NEXT_OPERATIONALIZATION_PLAN,
            False,
            False,
            "External benchmark operationalization truth is missing or unsafe; rerun operationalization plan.",
        )
    if not guardrails_clear:
        return (
            BLOCKER_GUARDRAIL_VIOLATION,
            NEXT_CONTRACT_REPAIR,
            False,
            False,
            "External benchmark decision surface guardrails failed; repair operationalization contract before surfacing product decisions.",
        )
    if audit.get("allGuardrailsPassed") is not True:
        return (
            BLOCKER_CONTRACT_GAP,
            NEXT_SURFACE_CONTRACT_REPAIR,
            False,
            True,
            "External benchmark product decision surface was derived but failed route/view-model audit.",
        )
    return (
        None,
        NEXT_ROUTE_IMPLEMENTATION,
        True,
        True,
        "External benchmark product decision surface is route-ready. Implement the read-only API/HTML route next; keep real detector evaluation and mutation gates separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool, next_lever: str) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "operationalization_plan_missing", "selected": primary_blocker == BLOCKER_OPERATIONALIZATION_MISSING, "primaryBlocker": BLOCKER_OPERATIONALIZATION_MISSING, "nextRecommendedNextLever": NEXT_OPERATIONALIZATION_PLAN},
            {"condition": "product_decision_surface_guardrail_violation", "selected": primary_blocker == BLOCKER_GUARDRAIL_VIOLATION, "primaryBlocker": BLOCKER_GUARDRAIL_VIOLATION, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "product_decision_surface_contract_gap", "selected": primary_blocker == BLOCKER_CONTRACT_GAP, "primaryBlocker": BLOCKER_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_SURFACE_CONTRACT_REPAIR},
            {"condition": "product_decision_surface_route_implementation_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": next_lever},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Product Decision Surface",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product decision surface ready: `{summary.get('productDecisionSurfaceReady')}`",
            f"- Product decision route implementation ready: `{summary.get('productDecisionRouteImplementationReady')}`",
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


def run_football_external_benchmark_product_decision_surface(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_product_decision_surface",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root, candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    source_summary = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    source_plan = inputs.get("plan") if isinstance(inputs.get("plan"), dict) else {}
    source_contract = inputs.get("contract") if isinstance(inputs.get("contract"), dict) else {}
    source_gates = inputs.get("gates") if isinstance(inputs.get("gates"), dict) else {}
    source_risks = inputs.get("risks") if isinstance(inputs.get("risks"), dict) else {}
    recommendations = _recommendation_matrix(source_plan, source_gates)
    view_model = _view_model(source_summary, source_plan, source_contract, source_gates, source_risks, recommendations)
    route_contract = _route_contract(view_model)
    html = _render_html(view_model)
    audit = _guardrail_audit(inputs, route_contract, view_model)
    source_ready = _operationalization_ready(inputs)
    guardrails_clear = _guardrails_clear(inputs)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(source_ready, guardrails_clear, audit)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_product_decision_surface",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_operationalization_plan",
        "productDecisionSurfaceReady": goal_achieved,
        "productDecisionRouteImplementationReady": goal_achieved,
        "externalBenchmarkLaneClosed": source_summary.get("externalBenchmarkLaneClosed"),
        "externalSourceCount": int(source_summary.get("externalSourceCount") or 0),
        "apiRoutePath": route_contract.get("apiRoutePath"),
        "htmlRoutePath": route_contract.get("htmlRoutePath"),
        "recommendedNextDesignLever": NEXT_REAL_EVALUATION_DESIGN,
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
        "productDecisionSurfaceViewModel": view_model,
        "productDecisionSurfaceRouteContract": route_contract,
        "benchmarkDecisionRecommendationMatrix": recommendations,
        "guardrailStatusAudit": audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "external_benchmark_product_decision_surface_summary.json", summary)
    _write_json(output_root / "product_decision_surface_view_model.json", view_model)
    (output_root / "product_decision_surface_render_smoke.html").write_text(html, encoding="utf-8")
    _write_json(output_root / "product_decision_surface_route_contract.json", route_contract)
    _write_json(output_root / "benchmark_decision_recommendation_matrix.json", recommendations)
    _write_json(output_root / "guardrail_status_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the read-only external benchmark product decision surface.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="external_benchmark_product_decision_surface")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_benchmark_product_decision_surface(
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
