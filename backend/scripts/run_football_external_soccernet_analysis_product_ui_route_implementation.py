from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import anyio
import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SOURCE_DIR_NAME = "football_external_soccernet_analysis_product_ui_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_analysis_product_ui_route_implementation_v1"

BLOCKER_UI_BINDING_MISSING = "football_external_soccernet_analysis_product_ui_binding_missing"
BLOCKER_ROUTE_CONTRACT_GAP = "football_external_soccernet_analysis_product_ui_route_contract_gap"

NEXT_UI_BINDING = "football_external_soccernet_analysis_product_ui_binding"
NEXT_ROUTE_CONTRACT_REPAIR = "football_external_soccernet_analysis_product_ui_route_contract_repair"
NEXT_PRODUCT_LANE_CLOSEOUT = "football_external_soccernet_analysis_product_lane_closeout"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_analysis_product_ui_route_smoke",
            "successCriteria": [
                "serve the saved UI view model from /api/external/soccernet/full-analysis",
                "serve the saved HTML smoke from /external/soccernet/full-analysis",
                "preserve non-evaluation, non-training, non-promotion, and non-runtime-mutation flags",
            ],
            "failureAdaptation": "If the route smoke fails with valid inputs, repair only route binding and artifact lookup.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_analysis_product_ui_route_contract_repair",
            "successCriteria": [
                "repair API/HTML route contract without changing source analysis truth",
                "keep readiness false for detector evaluation, training, promotion, and runtime mutation",
            ],
            "failureAdaptation": "If UI binding artifacts are unsafe or missing, route back to UI binding.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_analysis_product_ui_route_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to UI binding or route contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, source_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    source_root = candidate_root / source_dir_name
    return {
        "candidateRoot": candidate_root,
        "sourceRoot": source_root,
        "summary": _load_json(source_root / "analysis_product_ui_binding_summary.json"),
        "routeContract": _load_json(source_root / "analysis_product_ui_route_contract.json"),
        "viewModel": _load_json(source_root / "analysis_product_ui_view_model.json"),
        "htmlPath": source_root / "analysis_product_ui_render_smoke.html",
    }


def _ui_binding_ready(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("summary")
    route_contract = inputs.get("routeContract")
    view_model = inputs.get("viewModel")
    html_path = inputs.get("htmlPath")
    readiness = view_model.get("readiness") if isinstance(view_model, dict) and isinstance(view_model.get("readiness"), dict) else {}
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productUiBindingReady") is True
        and int(summary.get("reportedFrameCount") or 0) > 0
        and int(summary.get("segmentCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(route_contract, dict)
        and route_contract.get("routePath") == "/external/soccernet/full-analysis"
        and route_contract.get("productUiBindingReady") is True
        and route_contract.get("allowsCandidateEvaluationReadiness") is False
        and isinstance(view_model, dict)
        and readiness.get("productFullAnalysisReady") is True
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
        and isinstance(html_path, Path)
        and html_path.exists()
    )


async def _smoke_routes_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/external/soccernet/full-analysis")
        html_response = await client.get("/external/soccernet/full-analysis")
    api_body = api_response.json() if api_response.headers.get("content-type", "").startswith("application/json") else {}
    html_body = html_response.text
    return {
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiRouteBody": api_body,
        "htmlRouteBody": html_body,
    }


def _smoke_routes(storage_root: Path) -> dict[str, Any]:
    return anyio.run(_smoke_routes_async, storage_root)


def _route_smoke_audit(binding_ready: bool, smoke: dict[str, Any]) -> dict[str, Any]:
    body = smoke.get("apiRouteBody") if isinstance(smoke.get("apiRouteBody"), dict) else {}
    readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    html = str(smoke.get("htmlRouteBody") or "")
    api_route_smoke_passed = bool(
        binding_ready
        and smoke.get("apiRouteStatusCode") == 200
        and body.get("schemaVersion") == "soccernet_full_analysis_ui_view_model_v1"
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
        and bool(body.get("cards"))
    )
    html_route_smoke_passed = bool(
        binding_ready
        and smoke.get("htmlRouteStatusCode") == 200
        and "SoccerNet" in html
        and "Frames analyzed" in html
        and "not detector evaluation" in html
    )
    return {
        "schemaVersion": "soccernet_full_analysis_ui_route_smoke_audit_v1",
        "generatedAt": _utc_now_iso(),
        "sourceUiBindingReady": binding_ready,
        "apiRouteStatusCode": smoke.get("apiRouteStatusCode"),
        "htmlRouteStatusCode": smoke.get("htmlRouteStatusCode"),
        "apiRouteSmokePassed": api_route_smoke_passed,
        "htmlRouteSmokePassed": html_route_smoke_passed,
        "candidateEvaluationReady": readiness.get("candidateEvaluationReady"),
        "trainingReady": readiness.get("trainingReady"),
        "promotionReady": readiness.get("promotionReady"),
        "runtimeDefaultMutationReady": readiness.get("runtimeDefaultMutationReady"),
    }


def _classify(binding_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not binding_ready:
        return (
            BLOCKER_UI_BINDING_MISSING,
            NEXT_UI_BINDING,
            False,
            "SoccerNet product UI binding is missing or unsafe; rerun UI binding before route implementation.",
        )
    if audit.get("apiRouteSmokePassed") is not True or audit.get("htmlRouteSmokePassed") is not True:
        return (
            BLOCKER_ROUTE_CONTRACT_GAP,
            NEXT_ROUTE_CONTRACT_REPAIR,
            False,
            "SoccerNet product UI route smoke failed or overclaimed readiness.",
        )
    return (
        None,
        NEXT_PRODUCT_LANE_CLOSEOUT,
        True,
        "SoccerNet full-analysis product route is live from saved artifacts. Advance to product lane closeout; keep detector evaluation, training, promotion, and runtime mutation separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "analysis_product_ui_binding_missing", "selected": primary_blocker == BLOCKER_UI_BINDING_MISSING, "primaryBlocker": BLOCKER_UI_BINDING_MISSING, "nextRecommendedNextLever": NEXT_UI_BINDING},
            {"condition": "analysis_product_ui_route_contract_gap", "selected": primary_blocker == BLOCKER_ROUTE_CONTRACT_GAP, "primaryBlocker": BLOCKER_ROUTE_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_ROUTE_CONTRACT_REPAIR},
            {"condition": "analysis_product_ui_route_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_LANE_CLOSEOUT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Analysis Product UI Route Implementation",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product UI route ready: `{summary.get('productUiRouteReady')}`",
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


def run_football_external_soccernet_analysis_product_ui_route_implementation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_analysis_product_ui_route_smoke",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root, candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    binding_ready = _ui_binding_ready(inputs)
    smoke = _smoke_routes(storage_root)
    audit = _route_smoke_audit(binding_ready, smoke)
    primary_blocker, next_lever, goal_achieved, english = _classify(binding_ready, audit)
    attempts = _attempt_plan()
    summary_input = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_analysis_product_ui_route_implementation",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_analysis_product_ui_binding",
        "productUiRouteReady": goal_achieved,
        "apiRoutePath": "/api/external/soccernet/full-analysis",
        "htmlRoutePath": "/external/soccernet/full-analysis",
        "reportedFrameCount": summary_input.get("reportedFrameCount"),
        "segmentCount": summary_input.get("segmentCount"),
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
    response_fixture = {
        "statusCode": smoke.get("apiRouteStatusCode"),
        "headers": {"content-type": "application/json"},
        "body": smoke.get("apiRouteBody") if isinstance(smoke.get("apiRouteBody"), dict) else {},
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "analysisProductUiRouteSmokeAudit": audit,
        "analysisProductUiRouteResponseFixture": response_fixture,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "analysis_product_ui_route_implementation_summary.json", summary)
    _write_json(output_root / "analysis_product_ui_route_smoke_audit.json", audit)
    _write_json(output_root / "analysis_product_ui_route_response_fixture.json", response_fixture)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "analysis_product_ui_route_rendered.html").write_text(str(smoke.get("htmlRouteBody") or ""), encoding="utf-8")
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_analysis_product_ui_route_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_analysis_product_ui_route_implementation(
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
