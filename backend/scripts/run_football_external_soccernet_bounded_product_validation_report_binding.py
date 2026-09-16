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

DEFAULT_SOURCE_DIR_NAME = "football_external_soccernet_bounded_product_validation_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_bounded_product_validation_report_binding_v1"

BLOCKER_EXECUTION_GAP = "football_external_soccernet_bounded_product_validation_execution_gap"
BLOCKER_REPORT_CONTRACT_GAP = "football_external_soccernet_bounded_product_validation_report_contract_gap"

NEXT_EXECUTION = "football_external_soccernet_bounded_product_validation_execution"
NEXT_REPORT_REPAIR = "football_external_soccernet_bounded_product_validation_report_contract_repair"
NEXT_REAL_SAMPLE_DECISION = "football_external_soccernet_real_sample_product_pipeline_training_decision"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_product_validation_report_binding",
                "successCriteria": [
                    "read bounded SoccerNet product-validation execution truth",
                    "write operator-facing report payload, markdown, and route contract",
                    "preserve download, training, promotion, candidate-readiness, and runtime-mutation false flags",
                ],
                "failureAdaptation": "If execution truth is missing or failed, route back to product validation execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_product_validation_report_contract_repair",
                "successCriteria": [
                    "repair only report payload or route-contract shape from existing execution truth",
                    "do not alter validation source truth",
                ],
                "failureAdaptation": "If the report contract still overclaims readiness, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_product_validation_report_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before real sample training decision if report binding is unsafe.",
            },
        ],
    }


def _load_inputs(root: Path, source_dir_name: str) -> dict[str, Any]:
    source_root = root / source_dir_name
    return {
        "sourceRoot": source_root,
        "executionSummary": load_json(source_root / "soccernet_bounded_product_validation_execution_summary.json"),
        "executionReport": load_json(source_root / "product_validation_execution_report.json"),
        "sliceAudit": load_json(source_root / "product_validation_slice_audit.json"),
        "productBridgeAudit": load_json(source_root / "soccernet_product_bridge_validation_audit.json"),
        "existingReportAudit": load_json(source_root / "soccernet_existing_report_validation_audit.json"),
        "researchGapAudit": load_json(source_root / "research_gap_validation_audit.json"),
    }


def _execution_ready(summary: dict[str, Any] | None, report: dict[str, Any] | None, slice_audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productValidationExecutionExecuted") is True
        and int(summary.get("validatedProductSliceCount") or 0) >= 4
        and int(summary.get("failedProductSliceCount") or 0) == 0
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(report, dict)
        and report.get("boundedProductValidationPassed") is True
        and int(report.get("validatedProductSliceCount") or 0) >= 4
        and int(report.get("failedProductSliceCount") or 0) == 0
        and isinstance(slice_audit, dict)
        and int(slice_audit.get("failedProductSliceCount") or 0) == 0
    )


def _report_payload(inputs: dict[str, Any], ready: bool) -> dict[str, Any]:
    summary = inputs.get("executionSummary") if isinstance(inputs.get("executionSummary"), dict) else {}
    slice_audit = inputs.get("sliceAudit") if isinstance(inputs.get("sliceAudit"), dict) else {}
    slice_results = slice_audit.get("sliceResults") if isinstance(slice_audit.get("sliceResults"), list) else []
    return {
        "schemaVersion": "soccernet_bounded_product_validation_report_payload_v1",
        "generatedAt": utc_now_iso(),
        "sourceBatch": "football_external_soccernet_bounded_product_validation_execution",
        "sourceSummaryPath": str(inputs["sourceRoot"] / "soccernet_bounded_product_validation_execution_summary.json"),
        "boundedProductValidationPassed": ready,
        "validatedProductSliceCount": int(summary.get("validatedProductSliceCount") or 0),
        "failedProductSliceCount": int(summary.get("failedProductSliceCount") or 0),
        "sliceResults": slice_results,
        "readiness": {
            "reportBindingReady": ready,
            "controlledRealSampleDecisionReady": ready,
            "trainingReady": False,
            "promotionReady": False,
            "candidateEvaluationReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "guardrails": {
            "bulkDownloadExecuted": summary.get("bulkDownloadExecuted") is True,
            "videoDownloadExecuted": summary.get("videoDownloadExecuted") is True,
            "dataDownloadExecuted": summary.get("dataDownloadExecuted") is True,
            "trainingExecuted": summary.get("trainingExecuted") is True,
            "promotionMutationExecuted": summary.get("promotionMutationExecuted") is True,
            "runtimeDefaultMutationExecuted": summary.get("runtimeDefaultMutationExecuted") is True,
            "normalMatchStorageMutationExecuted": summary.get("normalMatchStorageMutationExecuted") is True,
        },
        "limitations": [
            "validates product wiring from existing SoccerNet artifacts only",
            "not a fresh download result",
            "not a detector miss analysis",
            "not training evidence",
            "not promotion evidence",
        ],
    }


def _view_model(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "SoccerNet bounded product validation",
        "subtitle": "Existing SoccerNet product lanes validated before real-sample execution.",
        "status": "passed" if payload.get("boundedProductValidationPassed") else "blocked",
        "summaryCards": [
            {"label": "Validated slices", "value": payload.get("validatedProductSliceCount")},
            {"label": "Failed slices", "value": payload.get("failedProductSliceCount")},
            {"label": "Report binding", "value": payload.get("readiness", {}).get("reportBindingReady")},
        ],
        "sliceRows": payload.get("sliceResults") or [],
        "limitations": payload.get("limitations") or [],
    }


def _route_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_bounded_product_validation_report_binding",
        "apiRoutePath": "/api/external/soccernet/bounded-product-validation",
        "htmlRoutePath": "/external/soccernet/bounded-product-validation",
        "reportBindingReady": payload.get("readiness", {}).get("reportBindingReady") is True,
        "allowsTraining": False,
        "allowsPromotion": False,
        "allowsCandidateEvaluationReadiness": False,
        "allowsRuntimeDefaultMutation": False,
    }


def _markdown_report(payload: dict[str, Any], view_model: dict[str, Any]) -> str:
    lines = [
        "# SoccerNet Bounded Product Validation Report",
        "",
        f"Status: `{view_model.get('status')}`",
        "",
        "## Summary",
        "",
        f"- Validated product slices: `{payload.get('validatedProductSliceCount')}`",
        f"- Failed product slices: `{payload.get('failedProductSliceCount')}`",
        f"- Report binding ready: `{payload.get('readiness', {}).get('reportBindingReady')}`",
        f"- Training ready: `{payload.get('readiness', {}).get('trainingReady')}`",
        f"- Promotion ready: `{payload.get('readiness', {}).get('promotionReady')}`",
        "",
        "## Slice Results",
        "",
    ]
    for row in payload.get("sliceResults") or []:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('sliceId')}`: `{row.get('passed')}`")
    lines.extend(["", "## Limitations", ""])
    for limitation in payload.get("limitations") or []:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def _classify(ready: bool, payload: dict[str, Any], route_contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not ready:
        return (
            BLOCKER_EXECUTION_GAP,
            NEXT_EXECUTION,
            False,
            "SoccerNet bounded product validation execution is missing or failed; rerun execution before report binding.",
        )
    if payload.get("readiness", {}).get("reportBindingReady") is not True or route_contract.get("reportBindingReady") is not True:
        return (
            BLOCKER_REPORT_CONTRACT_GAP,
            NEXT_REPORT_REPAIR,
            False,
            "SoccerNet bounded product validation report contract is incomplete.",
        )
    return (
        None,
        NEXT_REAL_SAMPLE_DECISION,
        True,
        "SoccerNet bounded product validation report is bound. Advance to controlled real-sample product-pipeline training decision.",
    )


def run_football_external_soccernet_bounded_product_validation_report_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    inputs = _load_inputs(root, source_dir_name)
    ready = _execution_ready(inputs["executionSummary"], inputs["executionReport"], inputs["sliceAudit"])
    payload = _report_payload(inputs, ready)
    view_model = _view_model(payload)
    route_contract = _route_contract(payload)
    primary_blocker, next_lever, goal, english = _classify(ready, payload, route_contract)
    markdown = _markdown_report(payload, view_model)
    (output_root / "soccernet_bounded_product_validation_report.md").write_text(markdown, encoding="utf-8")
    summary = {
        "batchName": "football_external_soccernet_bounded_product_validation_report_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "reportBindingReady": goal,
        "validatedProductSliceCount": payload.get("validatedProductSliceCount"),
        "failedProductSliceCount": payload.get("failedProductSliceCount"),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "soccernet_bounded_product_validation_report_binding_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "product_validation_execution_gap",
                "selected": primary_blocker == BLOCKER_EXECUTION_GAP,
                "primaryBlocker": BLOCKER_EXECUTION_GAP,
                "nextRecommendedNextLever": NEXT_EXECUTION,
            },
            {
                "condition": "product_validation_report_contract_gap",
                "selected": primary_blocker == BLOCKER_REPORT_CONTRACT_GAP,
                "primaryBlocker": BLOCKER_REPORT_CONTRACT_GAP,
                "nextRecommendedNextLever": NEXT_REPORT_REPAIR,
            },
            {
                "condition": "report_binding_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_REAL_SAMPLE_DECISION,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="soccernet_bounded_product_validation_report_binding_summary.json",
        summary=summary,
        artifacts={
            "soccernet_bounded_product_validation_report_payload.json": payload,
            "soccernet_bounded_product_validation_view_model.json": view_model,
            "soccernet_bounded_product_validation_route_contract.json": route_contract,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External SoccerNet Bounded Product Validation Report Binding",
    )


def main() -> None:
    main_for(
        "Bind bounded SoccerNet product-validation report artifacts.",
        run_football_external_soccernet_bounded_product_validation_report_binding,
    )


if __name__ == "__main__":
    main()
