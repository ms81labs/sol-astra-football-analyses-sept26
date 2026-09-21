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

DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_bounded_product_validation_execution_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_bounded_product_validation_execution_v1"
DEFAULT_DOCS_ROOT = REPO_ROOT / "docs"

BLOCKER_NOT_APPROVED = "football_external_soccernet_product_validation_execution_not_approved"
BLOCKER_REFERENCE_GAP = "football_external_soccernet_product_validation_reference_gap"
BLOCKER_EXECUTION_FAILED = "football_external_soccernet_product_validation_execution_failed"

NEXT_APPROVAL = "football_external_soccernet_bounded_product_validation_execution_approval"
NEXT_REFERENCE_REPAIR = "football_external_soccernet_bounded_product_validation_reference_repair"
NEXT_EXECUTION_DEBUG = "football_external_soccernet_bounded_product_validation_execution_debug"
NEXT_REPORT_BINDING = "football_external_soccernet_bounded_product_validation_report_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_bounded_product_validation_execution",
                "successCriteria": [
                    "consume only the approved existing-artifact product validation slices",
                    "validate product bridge payloads and existing route-bound reports",
                    "write bounded validation artifacts",
                    "do not download, train, promote, mutate runtime defaults, or mutate normal match storage",
                ],
                "failureAdaptation": "If references are complete, execute the bounded product validation.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_product_validation_reference_repair",
                "successCriteria": ["repair only existing artifact references or schema aliases"],
                "failureAdaptation": "If approval is missing, route back to approval instead of execution.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_product_validation_execution_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before report binding if validation is unsafe.",
            },
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productValidationExecutionApproved") is True
        and summary.get("productValidationExecutionExecuted") is False
        and int(summary.get("approvedProductValidationSliceCount") or 0) >= 3
        and summary.get("bulkDownloadApproved") is False
        and summary.get("trainingApproved") is False
        and summary.get("promotionApproved") is False
        and summary.get("runtimeDefaultMutationApproved") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(scope, dict)
        and scope.get("productValidationExecutionApproved") is True
        and scope.get("productValidationExecutionExecuted") is False
        and isinstance(scope.get("approvedProductValidationSlices"), list)
        and len(scope.get("approvedProductValidationSlices") or []) >= 3
        and scope.get("bulkDownloadApproved") is False
        and scope.get("trainingApproved") is False
        and scope.get("promotionApproved") is False
        and scope.get("runtimeDefaultMutationApproved") is False
        and isinstance(contract, dict)
        and contract.get("productValidationExecutionApproved") is True
        and contract.get("productValidationExecutionExecuted") is False
        and "bulk_soccernet_download" in (contract.get("disallowedOperations") or [])
    )


def _load_inputs(root: Path, approval_dir_name: str) -> dict[str, Any]:
    approval_root = root / approval_dir_name
    return {
        "approvalSummary": load_json(approval_root / "soccernet_bounded_product_validation_execution_approval_summary.json"),
        "approvalScope": load_json(approval_root / "approved_product_validation_scope.json"),
        "approvalContract": load_json(approval_root / "product_validation_execution_contract.json"),
        "bridgeSummary": load_json(
            root
            / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
            / "dry_run_product_bridge_smoke_summary.json"
        ),
        "bridgePayload": load_json(
            root
            / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
            / "dry_run_product_bridge_payload.json"
        ),
        "fullAnalysisCloseout": load_json(
            root / "football_external_soccernet_full_analysis_lane_closeout_v1" / "full_analysis_lane_closeout_summary.json"
        ),
        "analysisProductCloseout": load_json(
            root
            / "football_external_soccernet_analysis_product_lane_closeout_v1"
            / "analysis_product_lane_closeout_summary.json"
        ),
        "realReportBinding": load_json(
            root
            / "football_external_benchmark_real_report_and_product_binding_v1"
            / "real_report_and_product_binding_summary.json"
        ),
        "realReportPayload": load_json(
            root / "football_external_benchmark_real_report_and_product_binding_v1" / "real_report_payload.json"
        ),
    }


def _pass_result(slice_id: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "sliceId": slice_id,
        "passed": passed,
        "evidence": evidence,
    }


def _validate_product_bridge(bridge_summary: dict[str, Any] | None, bridge_payload: dict[str, Any] | None) -> dict[str, Any]:
    frame_count = int((bridge_payload or {}).get("frameCount") or 0)
    passed = bool(
        isinstance(bridge_summary, dict)
        and bridge_summary.get("goalAchieved") is True
        and bridge_summary.get("primaryBlocker") is None
        and bridge_summary.get("productBridgeSmokePassed") is True
        and int(bridge_summary.get("productPayloadFrameCount") or 0) == 300
        and int(bridge_summary.get("missingSampledFrameCount") or 0) == 0
        and isinstance(bridge_payload, dict)
        and bridge_payload.get("schemaVersion") == "soccernet_external_video_dry_run_product_bridge_v1"
        and frame_count == 300
    )
    return _pass_result(
        "soccernet_dry_run_product_bridge",
        passed,
        {
            "productBridgeSmokePassed": (bridge_summary or {}).get("productBridgeSmokePassed"),
            "productPayloadFrameCount": (bridge_summary or {}).get("productPayloadFrameCount"),
            "payloadFrameCount": frame_count,
            "missingSampledFrameCount": (bridge_summary or {}).get("missingSampledFrameCount"),
        },
    )


def _validate_full_analysis_product_lane(
    full_closeout: dict[str, Any] | None,
    product_closeout: dict[str, Any] | None,
) -> dict[str, Any]:
    passed = bool(
        isinstance(full_closeout, dict)
        and full_closeout.get("goalAchieved") is True
        and full_closeout.get("primaryBlocker") is None
        and full_closeout.get("fullAnalysisLaneClosed") is True
        and isinstance(product_closeout, dict)
        and product_closeout.get("goalAchieved") is True
        and product_closeout.get("primaryBlocker") is None
        and product_closeout.get("analysisProductLaneClosed") is True
    )
    return _pass_result(
        "soccernet_full_analysis_product_lane",
        passed,
        {
            "fullAnalysisLaneClosed": (full_closeout or {}).get("fullAnalysisLaneClosed"),
            "analysisProductLaneClosed": (product_closeout or {}).get("analysisProductLaneClosed"),
        },
    )


def _validate_external_report_binding(binding: dict[str, Any] | None, payload: dict[str, Any] | None) -> dict[str, Any]:
    passed = bool(
        isinstance(binding, dict)
        and binding.get("goalAchieved") is True
        and binding.get("primaryBlocker") is None
        and binding.get("roadmapAdvanceAllowed") is True
        and (binding.get("realReportProductBindingReady") is True or binding.get("realReportAndProductBindingReady") is True)
        and isinstance(payload, dict)
    )
    return _pass_result(
        "external_benchmark_report_product_binding",
        passed,
        {
            "realReportProductBindingReady": (binding or {}).get("realReportProductBindingReady")
            or (binding or {}).get("realReportAndProductBindingReady"),
            "realReportPayloadExists": isinstance(payload, dict),
        },
    )


def _validate_research_gap(docs_root: Path) -> dict[str, Any]:
    path = docs_root / "foot-soccer-deepresearch.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    required_terms = ["soccernet", "calibration", "tracking", "ball", "game_state", "pitch"]
    matched = [term for term in required_terms if term in text.lower()]
    return _pass_result(
        "research_game_state_gap_probe",
        len(matched) >= 5,
        {
            "researchPath": str(path),
            "researchDocExists": path.exists(),
            "matchedTerms": matched,
            "futureProductGaps": [
                "metric_pitch_coordinates_not_canonical",
                "game_state_parquet_not_canonical",
                "calibration_tracking_event_stack_future_lane",
            ],
        },
    )


def run_football_external_soccernet_bounded_product_validation_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    approval_dir_name: str = DEFAULT_APPROVAL_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    docs_root: Path = DEFAULT_DOCS_ROOT,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    inputs = _load_inputs(root, approval_dir_name)
    approved = _approval_ready(inputs["approvalSummary"], inputs["approvalScope"], inputs["approvalContract"])

    slice_results = [
        _validate_product_bridge(inputs["bridgeSummary"], inputs["bridgePayload"]),
        _validate_full_analysis_product_lane(inputs["fullAnalysisCloseout"], inputs["analysisProductCloseout"]),
        _validate_external_report_binding(inputs["realReportBinding"], inputs["realReportPayload"]),
        _validate_research_gap(Path(docs_root)),
    ]
    passed_count = sum(1 for row in slice_results if row["passed"] is True)
    failed_count = len(slice_results) - passed_count

    if not approved:
        goal = False
        primary_blocker = BLOCKER_NOT_APPROVED
        next_lever = NEXT_APPROVAL
        english = "SoccerNet bounded product validation execution is not approved; run the approval gate first."
    elif failed_count:
        goal = False
        primary_blocker = BLOCKER_REFERENCE_GAP if passed_count else BLOCKER_EXECUTION_FAILED
        next_lever = NEXT_REFERENCE_REPAIR if primary_blocker == BLOCKER_REFERENCE_GAP else NEXT_EXECUTION_DEBUG
        english = "SoccerNet bounded product validation found missing or failing existing-artifact references; repair references before report binding."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_REPORT_BINDING
        english = (
            "Bounded SoccerNet/external product validation executed from existing artifacts. "
            "Advance to report binding; no bulk download, training, promotion, runtime mutation, or normal storage mutation executed."
        )

    slice_audit = {
        "schemaVersion": "soccernet_bounded_product_validation_slice_audit_v1",
        "generatedAt": utc_now_iso(),
        "approved": approved,
        "validatedProductSliceCount": passed_count,
        "failedProductSliceCount": failed_count,
        "sliceResults": slice_results,
    }
    product_bridge_audit = {
        "schemaVersion": "soccernet_product_bridge_validation_audit_v1",
        "generatedAt": utc_now_iso(),
        **slice_results[0],
    }
    report_audit = {
        "schemaVersion": "soccernet_existing_report_validation_audit_v1",
        "generatedAt": utc_now_iso(),
        "fullAnalysisProductLane": slice_results[1],
        "externalBenchmarkReportBinding": slice_results[2],
    }
    research_audit = {
        "schemaVersion": "soccernet_research_gap_validation_audit_v1",
        "generatedAt": utc_now_iso(),
        **slice_results[3],
    }
    execution_report = {
        "schemaVersion": "soccernet_bounded_product_validation_execution_report_v1",
        "generatedAt": utc_now_iso(),
        "boundedProductValidationPassed": goal,
        "validatedProductSliceCount": passed_count,
        "failedProductSliceCount": failed_count,
        "executionBoundary": {
            "bulkDownloadExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
        "nextRecommendedNextLever": next_lever,
    }
    decision_matrix = {
        "schemaVersion": "soccernet_bounded_product_validation_execution_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "execution_not_approved",
                "selected": primary_blocker == BLOCKER_NOT_APPROVED,
                "primaryBlocker": BLOCKER_NOT_APPROVED,
                "nextRecommendedNextLever": NEXT_APPROVAL,
            },
            {
                "condition": "reference_gap",
                "selected": primary_blocker == BLOCKER_REFERENCE_GAP,
                "primaryBlocker": BLOCKER_REFERENCE_GAP,
                "nextRecommendedNextLever": NEXT_REFERENCE_REPAIR,
            },
            {
                "condition": "bounded_product_validation_passed",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_REPORT_BINDING,
            },
        ],
    }
    summary = {
        "batchName": "football_external_soccernet_bounded_product_validation_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "productValidationExecutionApproved": approved,
        "productValidationExecutionExecuted": goal,
        "validatedProductSliceCount": passed_count,
        "failedProductSliceCount": failed_count,
        "bulkDownloadExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="soccernet_bounded_product_validation_execution_summary.json",
        summary=summary,
        artifacts={
            "product_validation_slice_audit.json": slice_audit,
            "soccernet_product_bridge_validation_audit.json": product_bridge_audit,
            "soccernet_existing_report_validation_audit.json": report_audit,
            "research_gap_validation_audit.json": research_audit,
            "product_validation_execution_report.json": execution_report,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External SoccerNet Bounded Product Validation Execution",
    )


def main() -> None:
    main_for(
        "Execute bounded SoccerNet/external product validation from existing artifacts.",
        run_football_external_soccernet_bounded_product_validation_execution,
    )


if __name__ == "__main__":
    main()
