from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

import anyio
import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SOURCE_DIR_NAME = "football_external_benchmark_product_decision_surface_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_product_decision_surface_route_implementation_v1"

BLOCKER_SURFACE_MISSING = "football_external_benchmark_product_decision_surface_missing"
BLOCKER_ROUTE_CONTRACT_GAP = "football_external_benchmark_product_decision_surface_route_contract_gap"

NEXT_SURFACE = "football_external_benchmark_product_decision_surface"
NEXT_ROUTE_REPAIR = "football_external_benchmark_product_decision_surface_route_contract_repair"
NEXT_REAL_EVALUATION_DESIGN = "football_external_benchmark_real_evaluation_design"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_product_decision_route_smoke",
            "successCriteria": [
                "serve the saved decision view model from /api/external/benchmark/decision",
                "serve the saved decision HTML from /external/benchmark/decision",
                "preserve non-evaluation, non-download, non-training, non-promotion, and non-runtime-mutation flags",
            ],
            "failureAdaptation": "If the route smoke fails with valid inputs, repair only route binding and artifact lookup.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_product_decision_route_contract_repair",
            "successCriteria": [
                "repair API/HTML route contract without changing decision-surface truth",
                "keep readiness false for detector evaluation, training, promotion, data download, and runtime mutation",
            ],
            "failureAdaptation": "If decision surface artifacts are unsafe or missing, route back to the decision-surface batch.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_product_decision_route_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to decision surface, route contract repair, or real evaluation design.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, source_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    source_root = candidate_root / source_dir_name
    return {
        "candidateRoot": candidate_root,
        "sourceRoot": source_root,
        "summary": _load_json(source_root / "external_benchmark_product_decision_surface_summary.json"),
        "routeContract": _load_json(source_root / "product_decision_surface_route_contract.json"),
        "viewModel": _load_json(source_root / "product_decision_surface_view_model.json"),
        "htmlPath": source_root / "product_decision_surface_render_smoke.html",
    }


def _surface_ready(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("summary")
    route_contract = inputs.get("routeContract")
    view_model = inputs.get("viewModel")
    html_path = inputs.get("htmlPath")
    readiness = view_model.get("readiness") if isinstance(view_model, dict) and isinstance(view_model.get("readiness"), dict) else {}
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productDecisionSurfaceReady") is True
        and summary.get("productDecisionRouteImplementationReady") is True
        and int(summary.get("externalSourceCount") or 0) >= 2
        and summary.get("trainingExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(route_contract, dict)
        and route_contract.get("apiRoutePath") == "/api/external/benchmark/decision"
        and route_contract.get("htmlRoutePath") == "/external/benchmark/decision"
        and route_contract.get("productDecisionSurfaceReady") is True
        and route_contract.get("productDecisionRouteImplementationReady") is True
        and route_contract.get("allowsCandidateEvaluationReadiness") is False
        and route_contract.get("allowsRuntimeDefaultMutation") is False
        and route_contract.get("allowsDataDownload") is False
        and isinstance(view_model, dict)
        and view_model.get("schemaVersion") == "external_benchmark_product_decision_surface_view_model_v1"
        and readiness.get("productDecisionSurfaceReady") is True
        and readiness.get("productDecisionRouteImplementationReady") is True
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
        and readiness.get("dataDownloadReady") is False
        and readiness.get("normalMatchStorageMutationReady") is False
        and isinstance(html_path, Path)
        and html_path.exists()
    )


async def _smoke_routes_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/external/benchmark/decision")
        html_response = await client.get("/external/benchmark/decision")
    api_body = api_response.json() if api_response.headers.get("content-type", "").startswith("application/json") else {}
    return {
        "apiRoutePath": "/api/external/benchmark/decision",
        "htmlRoutePath": "/external/benchmark/decision",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiRouteBody": api_body,
        "htmlRouteBody": html_response.text,
    }


def _smoke_routes(storage_root: Path) -> dict[str, Any]:
    return anyio.run(_smoke_routes_async, storage_root)


def _route_smoke_audit(surface_ready: bool, smoke: dict[str, Any]) -> dict[str, Any]:
    body = smoke.get("apiRouteBody") if isinstance(smoke.get("apiRouteBody"), dict) else {}
    readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    html = str(smoke.get("htmlRouteBody") or "")
    api_route_smoke_passed = bool(
        surface_ready
        and smoke.get("apiRouteStatusCode") == 200
        and body.get("schemaVersion") == "external_benchmark_product_decision_surface_view_model_v1"
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
        and readiness.get("dataDownloadReady") is False
        and bool(body.get("recommendations"))
    )
    html_route_smoke_passed = bool(
        surface_ready
        and smoke.get("htmlRouteStatusCode") == 200
        and "External Benchmark Decision Surface" in html
        and "not detector evaluation" in html
        and "real detector benchmark" in html
    )
    return {
        "schemaVersion": "external_benchmark_product_decision_surface_route_smoke_audit_v1",
        "generatedAt": utc_now_iso(),
        "sourceDecisionSurfaceReady": surface_ready,
        "apiRoutePath": smoke.get("apiRoutePath"),
        "htmlRoutePath": smoke.get("htmlRoutePath"),
        "apiRouteStatusCode": smoke.get("apiRouteStatusCode"),
        "htmlRouteStatusCode": smoke.get("htmlRouteStatusCode"),
        "apiRouteSmokePassed": api_route_smoke_passed,
        "htmlRouteSmokePassed": html_route_smoke_passed,
        "candidateEvaluationReady": readiness.get("candidateEvaluationReady"),
        "trainingReady": readiness.get("trainingReady"),
        "promotionReady": readiness.get("promotionReady"),
        "runtimeDefaultMutationReady": readiness.get("runtimeDefaultMutationReady"),
        "dataDownloadReady": readiness.get("dataDownloadReady"),
    }


def _classify(surface_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not surface_ready:
        return (
            BLOCKER_SURFACE_MISSING,
            NEXT_SURFACE,
            False,
            False,
            "External benchmark product decision surface is missing or unsafe; rerun decision surface before route implementation.",
        )
    if audit.get("apiRouteSmokePassed") is not True or audit.get("htmlRouteSmokePassed") is not True:
        return (
            BLOCKER_ROUTE_CONTRACT_GAP,
            NEXT_ROUTE_REPAIR,
            False,
            True,
            "External benchmark product decision surface route smoke failed or overclaimed readiness.",
        )
    return (
        None,
        NEXT_REAL_EVALUATION_DESIGN,
        True,
        True,
        "External benchmark product decision route is live from saved artifacts. Advance to real evaluation design; keep detector execution, training, promotion, download, and runtime mutation separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "product_decision_surface_missing", "selected": primary_blocker == BLOCKER_SURFACE_MISSING, "primaryBlocker": BLOCKER_SURFACE_MISSING, "nextRecommendedNextLever": NEXT_SURFACE},
            {"condition": "product_decision_route_contract_gap", "selected": primary_blocker == BLOCKER_ROUTE_CONTRACT_GAP, "primaryBlocker": BLOCKER_ROUTE_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_ROUTE_REPAIR},
            {"condition": "real_evaluation_design_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_REAL_EVALUATION_DESIGN},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Product Decision Surface Route Implementation",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product decision route ready: `{summary.get('productDecisionRouteReady')}`",
            f"- API route: `{summary.get('apiRoutePath')}`",
            f"- HTML route: `{summary.get('htmlRoutePath')}`",
            f"- External source count: `{summary.get('externalSourceCount')}`",
            f"- Recommended next design lever: `{summary.get('recommendedNextDesignLever')}`",
            f"- Candidate ready for evaluation: `{summary.get('candidateReadyForEvaluation')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_product_decision_surface_route_implementation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_product_decision_route_smoke",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root, candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    surface_ready = _surface_ready(inputs)
    summary_input = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    smoke = _smoke_routes(storage_root)
    audit = _route_smoke_audit(surface_ready, smoke)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(surface_ready, audit)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_product_decision_surface_route_implementation",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_product_decision_surface",
        "productDecisionRouteReady": goal_achieved,
        "externalBenchmarkLaneClosed": summary_input.get("externalBenchmarkLaneClosed"),
        "externalSourceCount": summary_input.get("externalSourceCount"),
        "apiRoutePath": smoke.get("apiRoutePath"),
        "htmlRoutePath": smoke.get("htmlRoutePath"),
        "recommendedNextDesignLever": summary_input.get("recommendedNextDesignLever") or NEXT_REAL_EVALUATION_DESIGN,
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
    response_fixture = {
        "statusCode": smoke.get("apiRouteStatusCode"),
        "headers": {"content-type": "application/json"},
        "body": smoke.get("apiRouteBody") if isinstance(smoke.get("apiRouteBody"), dict) else {},
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    outcome = {
        "summary": summary,
        "productDecisionSurfaceRouteSmokeAudit": audit,
        "productDecisionSurfaceRouteResponseFixture": response_fixture,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "product_decision_surface_route_implementation_summary.json", summary)
    _write_json(output_root / "product_decision_surface_route_smoke_audit.json", audit)
    _write_json(output_root / "product_decision_surface_route_response_fixture.json", response_fixture)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "product_decision_surface_route_rendered.html").write_text(str(smoke.get("htmlRouteBody") or ""), encoding="utf-8")
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke the read-only external benchmark decision surface routes.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="external_benchmark_product_decision_route_smoke")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_benchmark_product_decision_surface_route_implementation(
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
