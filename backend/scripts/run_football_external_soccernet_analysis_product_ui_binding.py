from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
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
DEFAULT_SOURCE_DIR_NAME = "football_external_soccernet_analysis_product_api_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_analysis_product_ui_binding_v1"

BLOCKER_API_SMOKE_MISSING = "football_external_soccernet_analysis_product_api_smoke_missing"
BLOCKER_UI_CONTRACT_GAP = "football_external_soccernet_analysis_product_ui_contract_gap"

NEXT_API_SMOKE = "football_external_soccernet_analysis_product_api_smoke"
NEXT_UI_CONTRACT_REPAIR = "football_external_soccernet_analysis_product_ui_contract_repair"
NEXT_UI_ROUTE_IMPLEMENTATION = "football_external_soccernet_analysis_product_ui_route_implementation"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_analysis_product_ui_binding",
            "successCriteria": [
                "convert the full-analysis API response fixture into a UI view model",
                "write a route contract and HTML render smoke",
                "preserve limitations and non-readiness flags",
            ],
            "failureAdaptation": "If the UI view model is incomplete, repair only from the API smoke response fixture.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_analysis_product_ui_contract_repair",
            "successCriteria": [
                "repair route/view-model fields without altering source analysis truth",
                "keep detector evaluation, training, promotion, and runtime mutation false",
            ],
            "failureAdaptation": "If the API smoke is unsafe, route back to API smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_analysis_product_ui_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before route implementation if the view model is unsafe",
            ],
            "failureAdaptation": "Route to API smoke or UI contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, source_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    source_root = candidate_root / source_dir_name
    return {
        "candidateRoot": candidate_root,
        "summary": _load_json(source_root / "analysis_product_api_smoke_summary.json"),
        "audit": _load_json(source_root / "analysis_product_api_payload_contract_audit.json"),
        "response": _load_json(source_root / "analysis_product_api_response_fixture.json"),
    }


def _api_smoke_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None, response: dict[str, Any] | None) -> bool:
    body = response.get("body") if isinstance(response, dict) and isinstance(response.get("body"), dict) else {}
    readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productApiSmokePassed") is True
        and int(summary.get("reportedFrameCount") or 0) > 0
        and int(summary.get("segmentCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and audit.get("payloadContractValid") is True
        and audit.get("apiResponseFixtureValid") is True
        and isinstance(response, dict)
        and response.get("statusCode") == 200
        and readiness.get("productFullAnalysisReady") is True
        and readiness.get("candidateEvaluationReady") is False
    )


def _view_model(response: dict[str, Any] | None) -> dict[str, Any]:
    body = response.get("body") if isinstance(response, dict) and isinstance(response.get("body"), dict) else {}
    analysis = body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    ui = body.get("ui") if isinstance(body.get("ui"), dict) else {}
    readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    cards = analysis.get("summaryCards") if isinstance(analysis.get("summaryCards"), list) else []
    signals = analysis.get("aggregateFrameSignals") if isinstance(analysis.get("aggregateFrameSignals"), dict) else {}
    return {
        "schemaVersion": "soccernet_full_analysis_ui_view_model_v1",
        "generatedAt": _utc_now_iso(),
        "hero": {
            "title": ui.get("title") or "SoccerNet full analysis",
            "subtitle": ui.get("subtitle") or "Full external match analysis payload.",
        },
        "limitationsBanner": ui.get("limitationsBanner"),
        "safeNextAction": ui.get("safeNextAction"),
        "cards": cards,
        "signals": [
            {"label": "Median brightness", "value": signals.get("meanBrightnessP50")},
            {"label": "Green dominant ratio", "value": signals.get("greenDominantPixelRatioP50")},
            {"label": "Motion delta", "value": signals.get("motionDeltaP50")},
            {"label": "Unreadable frames", "value": signals.get("unreadableFrameCount")},
        ],
        "sourceLinks": {
            "reportPath": analysis.get("sourceReportPath"),
            "videoPath": analysis.get("sourceVideoPath"),
        },
        "readiness": {
            "productFullAnalysisReady": readiness.get("productFullAnalysisReady") is True,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": body.get("limitations") or [],
        "remainingGaps": body.get("remainingGaps") or [],
    }


def _route_contract(view_model: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccernet_full_analysis_ui_route_contract_v1",
        "generatedAt": _utc_now_iso(),
        "routePath": "/external/soccernet/full-analysis",
        "routeName": "SoccerNetFullAnalysis",
        "viewModelSchemaVersion": view_model.get("schemaVersion"),
        "productUiBindingReady": view_model.get("readiness", {}).get("productFullAnalysisReady") is True,
        "requiresLimitationsBanner": True,
        "mustShowLimitationsBanner": bool(view_model.get("limitationsBanner")),
        "allowsCandidateEvaluationReadiness": False,
        "allowsTraining": False,
        "allowsPromotion": False,
        "allowsRuntimeDefaultMutation": False,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    cards = "".join(
        f'<article class="card"><div class="label">{escape(str(card.get("label", "")))}</div><div class="value">{escape(str(card.get("value", "")))}</div></article>'
        for card in view_model.get("cards", [])
        if isinstance(card, dict)
    )
    signals = "".join(
        f'<li><span>{escape(str(row.get("label", "")))}</span><strong>{escape(str(row.get("value", "")))}</strong></li>'
        for row in view_model.get("signals", [])
        if isinstance(row, dict)
    )
    limitations = "".join(f"<li>{escape(str(item))}</li>" for item in view_model.get("limitations", []))
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(str(view_model.get("hero", {}).get("title", "SoccerNet full analysis")))}</title>
    <style>
      body {{ margin: 0; font-family: Arial, sans-serif; color: #111827; background: #ffffff; }}
      main {{ max-width: 960px; margin: 0 auto; padding: 32px; }}
      .banner {{ border-left: 4px solid #b45309; background: #fffbeb; padding: 12px 14px; margin: 20px 0; }}
      .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
      .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 14px; }}
      .label {{ color: #4b5563; font-size: 12px; text-transform: uppercase; }}
      .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
      li {{ margin-top: 8px; }}
    </style>
  </head>
  <body>
    <main>
      <h1>{escape(str(view_model.get("hero", {}).get("title", "")))}</h1>
      <p>{escape(str(view_model.get("hero", {}).get("subtitle", "")))}</p>
      <section class="banner">{escape(str(view_model.get("limitationsBanner", "")))}</section>
      <section class="grid">{cards}</section>
      <h2>Frame Signals</h2>
      <ul>{signals}</ul>
      <h2>Limitations</h2>
      <ul>{limitations}</ul>
    </main>
  </body>
</html>
"""


def _ui_binding_audit(api_ready: bool, view_model: dict[str, Any], route_contract: dict[str, Any], html: str) -> dict[str, Any]:
    valid = bool(
        api_ready
        and view_model.get("readiness", {}).get("productFullAnalysisReady") is True
        and view_model.get("readiness", {}).get("candidateEvaluationReady") is False
        and bool(view_model.get("limitationsBanner"))
        and bool(view_model.get("cards"))
        and route_contract.get("productUiBindingReady") is True
        and route_contract.get("allowsCandidateEvaluationReadiness") is False
        and "not detector evaluation" in html
    )
    return {
        "schemaVersion": "soccernet_full_analysis_ui_binding_audit_v1",
        "generatedAt": _utc_now_iso(),
        "sourceApiSmokeReady": api_ready,
        "uiViewModelValid": valid,
        "htmlRenderSmokeValid": "SoccerNet" in html and "Frames analyzed" in html,
        "routeContractValid": route_contract.get("productUiBindingReady") is True,
        "candidateEvaluationReady": view_model.get("readiness", {}).get("candidateEvaluationReady"),
        "trainingReady": view_model.get("readiness", {}).get("trainingReady"),
        "promotionReady": view_model.get("readiness", {}).get("promotionReady"),
        "runtimeDefaultMutationReady": view_model.get("readiness", {}).get("runtimeDefaultMutationReady"),
    }


def _classify(api_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not api_ready:
        return (
            BLOCKER_API_SMOKE_MISSING,
            NEXT_API_SMOKE,
            False,
            "SoccerNet product API smoke is missing or unsafe; rerun API smoke before UI binding.",
        )
    if (
        audit.get("uiViewModelValid") is not True
        or audit.get("htmlRenderSmokeValid") is not True
        or audit.get("routeContractValid") is not True
    ):
        return (
            BLOCKER_UI_CONTRACT_GAP,
            NEXT_UI_CONTRACT_REPAIR,
            False,
            "SoccerNet product UI binding contract is incomplete or overclaims readiness.",
        )
    return (
        None,
        NEXT_UI_ROUTE_IMPLEMENTATION,
        True,
        "SoccerNet full-analysis UI binding is ready. Advance to route implementation; keep detector evaluation, training, promotion, and runtime mutation separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "analysis_product_api_smoke_missing", "selected": primary_blocker == BLOCKER_API_SMOKE_MISSING, "primaryBlocker": BLOCKER_API_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_API_SMOKE},
            {"condition": "analysis_product_ui_contract_gap", "selected": primary_blocker == BLOCKER_UI_CONTRACT_GAP, "primaryBlocker": BLOCKER_UI_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_UI_CONTRACT_REPAIR},
            {"condition": "analysis_product_ui_binding_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_UI_ROUTE_IMPLEMENTATION},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Analysis Product UI Binding",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product UI binding ready: `{summary.get('productUiBindingReady')}`",
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


def run_football_external_soccernet_analysis_product_ui_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_analysis_product_ui_binding",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    api_ready = _api_smoke_ready(inputs["summary"], inputs["audit"], inputs["response"])
    view_model = _view_model(inputs["response"])
    route_contract = _route_contract(view_model)
    html = _render_html(view_model)
    audit = _ui_binding_audit(api_ready, view_model, route_contract, html)
    primary_blocker, next_lever, goal_achieved, english = _classify(api_ready, audit)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_analysis_product_ui_binding",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_analysis_product_api_smoke",
        "productUiBindingReady": goal_achieved,
        "reportedFrameCount": (inputs["summary"] or {}).get("reportedFrameCount"),
        "segmentCount": (inputs["summary"] or {}).get("segmentCount"),
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
        "analysisProductUiBindingAudit": audit,
        "analysisProductUiRouteContract": route_contract,
        "analysisProductUiViewModel": view_model,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "analysis_product_ui_binding_summary.json", summary)
    _write_json(output_root / "analysis_product_ui_binding_audit.json", audit)
    _write_json(output_root / "analysis_product_ui_route_contract.json", route_contract)
    _write_json(output_root / "analysis_product_ui_view_model.json", view_model)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "analysis_product_ui_render_smoke.html").write_text(html, encoding="utf-8")
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_analysis_product_ui_binding")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_analysis_product_ui_binding(
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
