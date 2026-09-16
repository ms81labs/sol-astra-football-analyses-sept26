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
DEFAULT_SOURCE_DIR_NAME = "football_external_soccernet_full_analysis_product_integration_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_analysis_product_api_smoke_v1"

BLOCKER_PRODUCT_INTEGRATION_MISSING = "football_external_soccernet_full_analysis_product_integration_missing"
BLOCKER_API_CONTRACT_GAP = "football_external_soccernet_analysis_product_api_contract_gap"

NEXT_PRODUCT_INTEGRATION = "football_external_soccernet_full_analysis_product_integration"
NEXT_API_CONTRACT_REPAIR = "football_external_soccernet_analysis_product_api_contract_repair"
NEXT_PRODUCT_UI_BINDING = "football_external_soccernet_analysis_product_ui_binding"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_analysis_product_api_smoke",
            "successCriteria": [
                "load full-analysis product integration truth",
                "write an API-shaped response fixture with report, readiness, UI copy, and limitations",
                "keep training, promotion, candidate evaluation readiness, and runtime mutation blocked",
            ],
            "failureAdaptation": "If the API-shaped payload is incomplete, repair the API contract from saved product integration truth only.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_analysis_product_api_contract_repair",
            "successCriteria": [
                "repair missing response fields without altering source analysis truth",
                "preserve limitations and non-readiness flags",
            ],
            "failureAdaptation": "If product integration truth is unsafe, route back to product integration.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_analysis_product_api_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before UI binding if the API contract is unsafe",
            ],
            "failureAdaptation": "Route to product integration or API contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, source_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    source_root = candidate_root / source_dir_name
    return {
        "candidateRoot": candidate_root,
        "sourceRoot": source_root,
        "summary": _load_json(source_root / "full_analysis_product_integration_summary.json"),
        "payload": _load_json(source_root / "product_full_analysis_payload.json"),
        "copy": _load_json(source_root / "product_ui_copy.json"),
        "contract": _load_json(source_root / "product_integration_contract.json"),
    }


def _product_integration_ready(
    summary: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    copy: dict[str, Any] | None,
    contract: dict[str, Any] | None,
) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productFullAnalysisReady") is True
        and int(summary.get("reportedFrameCount") or 0) > 0
        and int(summary.get("segmentCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(payload, dict)
        and payload.get("schemaVersion") == "soccernet_external_full_analysis_product_payload_v1"
        and payload.get("readiness", {}).get("productFullAnalysisReady") is True
        and payload.get("readiness", {}).get("candidateEvaluationReady") is False
        and isinstance(copy, dict)
        and bool(copy.get("limitationsBanner"))
        and isinstance(contract, dict)
        and contract.get("productFullAnalysisReady") is True
        and contract.get("allowsCandidateEvaluationReadiness") is False
        and contract.get("allowsPromotion") is False
        and contract.get("allowsRuntimeDefaultMutation") is False
        and contract.get("requiresTraining") is False
    )


def _api_response_fixture(payload: dict[str, Any] | None, copy: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    copy = copy or {}
    readiness = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else {}
    signals = payload.get("aggregateFrameSignals") if isinstance(payload.get("aggregateFrameSignals"), dict) else {}
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": {
            "schemaVersion": "soccernet_full_analysis_api_response_v1",
            "analysis": {
                "frameCount": payload.get("frameCount"),
                "segmentCount": payload.get("segmentCount"),
                "sourceReportPath": payload.get("sourceReportPath"),
                "sourceVideoPath": payload.get("sourceVideoPath"),
                "summaryCards": payload.get("summaryCards") or [],
                "aggregateFrameSignals": signals,
            },
            "readiness": {
                "productFullAnalysisReady": readiness.get("productFullAnalysisReady") is True,
                "candidateEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": False,
            },
            "ui": {
                "title": copy.get("title"),
                "subtitle": copy.get("subtitle"),
                "limitationsBanner": copy.get("limitationsBanner"),
                "safeNextAction": copy.get("safeNextAction"),
            },
            "limitations": payload.get("limitations") or [],
            "remainingGaps": payload.get("remainingGaps") or [],
        },
    }


def _contract_audit(
    integration_ready: bool,
    payload: dict[str, Any] | None,
    copy: dict[str, Any] | None,
    contract: dict[str, Any] | None,
    response: dict[str, Any],
) -> dict[str, Any]:
    body = response.get("body") if isinstance(response.get("body"), dict) else {}
    analysis = body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    ui = body.get("ui") if isinstance(body.get("ui"), dict) else {}
    payload_contract_valid = bool(
        integration_ready
        and isinstance(payload, dict)
        and isinstance(copy, dict)
        and isinstance(contract, dict)
        and int(payload.get("frameCount") or 0) > 0
        and int(payload.get("segmentCount") or 0) > 0
        and bool(copy.get("limitationsBanner"))
        and contract.get("allowsCandidateEvaluationReadiness") is False
    )
    api_response_fixture_valid = bool(
        response.get("statusCode") == 200
        and int(analysis.get("frameCount") or 0) > 0
        and int(analysis.get("segmentCount") or 0) > 0
        and readiness.get("productFullAnalysisReady") is True
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
        and bool(ui.get("limitationsBanner"))
    )
    return {
        "schemaVersion": "soccernet_full_analysis_product_api_contract_audit_v1",
        "generatedAt": _utc_now_iso(),
        "sourceProductIntegrationReady": integration_ready,
        "payloadContractValid": payload_contract_valid,
        "apiResponseFixtureValid": api_response_fixture_valid,
        "frameCount": analysis.get("frameCount"),
        "segmentCount": analysis.get("segmentCount"),
        "candidateEvaluationReady": readiness.get("candidateEvaluationReady"),
        "trainingReady": readiness.get("trainingReady"),
        "promotionReady": readiness.get("promotionReady"),
        "runtimeDefaultMutationReady": readiness.get("runtimeDefaultMutationReady"),
    }


def _classify(integration_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not integration_ready:
        return (
            BLOCKER_PRODUCT_INTEGRATION_MISSING,
            NEXT_PRODUCT_INTEGRATION,
            False,
            "SoccerNet full-analysis product integration is missing or unsafe; rerun product integration before API smoke.",
        )
    if audit.get("payloadContractValid") is not True or audit.get("apiResponseFixtureValid") is not True:
        return (
            BLOCKER_API_CONTRACT_GAP,
            NEXT_API_CONTRACT_REPAIR,
            False,
            "SoccerNet full-analysis product API fixture is incomplete or overclaims readiness.",
        )
    return (
        None,
        NEXT_PRODUCT_UI_BINDING,
        True,
        "SoccerNet full-analysis product API smoke passed. Advance to UI binding; keep detector evaluation, training, promotion, and runtime mutation separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "full_analysis_product_integration_missing", "selected": primary_blocker == BLOCKER_PRODUCT_INTEGRATION_MISSING, "primaryBlocker": BLOCKER_PRODUCT_INTEGRATION_MISSING, "nextRecommendedNextLever": NEXT_PRODUCT_INTEGRATION},
            {"condition": "analysis_product_api_contract_gap", "selected": primary_blocker == BLOCKER_API_CONTRACT_GAP, "primaryBlocker": BLOCKER_API_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_API_CONTRACT_REPAIR},
            {"condition": "analysis_product_api_smoke_passed", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_UI_BINDING},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Analysis Product API Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product API smoke passed: `{summary.get('productApiSmokePassed')}`",
            f"- Reported frame count: `{summary.get('reportedFrameCount')}`",
            f"- Segment count: `{summary.get('segmentCount')}`",
            f"- Candidate ready for evaluation: `{summary.get('candidateReadyForEvaluation')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_analysis_product_api_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_analysis_product_api_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    integration_ready = _product_integration_ready(inputs["summary"], inputs["payload"], inputs["copy"], inputs["contract"])
    response = _api_response_fixture(inputs["payload"], inputs["copy"])
    audit = _contract_audit(integration_ready, inputs["payload"], inputs["copy"], inputs["contract"], response)
    primary_blocker, next_lever, goal_achieved, english = _classify(integration_ready, audit)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_analysis_product_api_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_full_analysis_product_integration",
        "productApiSmokePassed": goal_achieved,
        "reportedFrameCount": response["body"]["analysis"].get("frameCount"),
        "segmentCount": response["body"]["analysis"].get("segmentCount"),
        "archiveDownloadExecuted": False,
        "video720pMemberDownloadExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "analysisProductApiPayloadContractAudit": audit,
        "analysisProductApiResponseFixture": response,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "analysis_product_api_smoke_summary.json", summary)
    _write_json(output_root / "analysis_product_api_payload_contract_audit.json", audit)
    _write_json(output_root / "analysis_product_api_response_fixture.json", response)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_analysis_product_api_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_analysis_product_api_smoke(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        source_dir_name=args.source_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
