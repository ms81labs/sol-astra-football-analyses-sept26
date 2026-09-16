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
DEFAULT_REPORT_DIR_NAME = "football_external_soccertrack_analysis_report_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_analysis_product_ui_binding_v1"

BLOCKER_REPORT_MISSING = "football_external_soccertrack_analysis_report_smoke_missing"
BLOCKER_UI_CONTRACT_GAP = "football_external_soccertrack_analysis_product_ui_contract_gap"

NEXT_REPORT = "football_external_soccertrack_analysis_report_smoke"
NEXT_UI_CONTRACT_REPAIR = "football_external_soccertrack_analysis_product_ui_contract_repair"
NEXT_UI_ROUTE_IMPLEMENTATION = "football_external_soccertrack_analysis_product_ui_route_implementation"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_analysis_product_ui_binding",
            "successCriteria": [
                "convert the SoccerTrack analysis report payload into a product UI view model",
                "write a static HTML render smoke and route contract",
                "preserve limitations and non-readiness flags",
            ],
            "failureAdaptation": "If the UI model is incomplete, repair only from the analysis report payload.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_analysis_product_ui_contract_repair",
            "successCriteria": [
                "repair view-model, HTML, or route-contract fields without altering report truth",
                "keep detector evaluation, training, promotion, and runtime mutation false",
            ],
            "failureAdaptation": "If the report smoke is unsafe, route back to report smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_analysis_product_ui_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before route implementation if the UI binding is unsafe",
            ],
            "failureAdaptation": "Route to report smoke or UI contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, report_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    report_root = candidate_root / report_dir_name
    return {
        "candidateRoot": candidate_root,
        "reportSummary": _load_json(report_root / "soccertrack_analysis_report_smoke_summary.json"),
        "reportPayload": _load_json(report_root / "soccertrack_analysis_report_payload.json"),
    }


def _report_ready(summary: dict[str, Any] | None, payload: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("analysisReportSmokePassed") is True
        and int(summary.get("reportedEventCount") or 0) > 0
        and int(summary.get("reportedFrameCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and isinstance(payload, dict)
        and payload.get("schemaVersion") == "soccertrack_external_analysis_report_payload_v1"
        and payload.get("readiness", {}).get("analysisReportReady") is True
        and payload.get("readiness", {}).get("candidateEvaluationReady") is False
    )


def _view_model(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    selected_match_id = payload.get("selectedMatchId") or str(match.get("id") or "").replace("soccertrack:", "")
    fixture = payload.get("taskFixtureSummary") if isinstance(payload.get("taskFixtureSummary"), dict) else {}
    event_types = payload.get("eventTypeBreakdown") if isinstance(payload.get("eventTypeBreakdown"), list) else []
    limitations = payload.get("limitations") if isinstance(payload.get("limitations"), list) else []
    return {
        "schemaVersion": "soccertrack_analysis_product_ui_view_model_v1",
        "generatedAt": _utc_now_iso(),
        "hero": {
            "title": f"SoccerTrack {selected_match_id} external fixture",
            "subtitle": "Read-only external BAS/GSR/MOT fixture surfaced through the MatchBundle product route.",
        },
        "limitationsBanner": "This is not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
        "cards": [
            {"label": "Events", "value": payload.get("reportedEventCount")},
            {"label": "Sampled frames", "value": payload.get("reportedFrameCount")},
            {"label": "GSR halves", "value": fixture.get("gsrHalfCount")},
            {"label": "MOT frames", "value": fixture.get("motFrameCount")},
        ],
        "eventTypeBreakdown": event_types[:8],
        "teamBreakdown": payload.get("teamBreakdown") or [],
        "ballStatusBreakdown": payload.get("ballStatusBreakdown") or [],
        "sourceLinks": {
            "productRoute": payload.get("routePath"),
            "sourceReport": "soccertrack_analysis_report.md",
        },
        "readiness": {
            "analysisProductUiReady": True,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": limitations,
        "safeNextAction": "Implement a read-only product route for this UI binding before broader product integration.",
    }


def _route_contract(view_model: dict[str, Any]) -> dict[str, Any]:
    title = str(view_model.get("hero", {}).get("title") or "")
    selected = title.split(" ")[1] if len(title.split(" ")) > 1 else "117092"
    return {
        "schemaVersion": "soccertrack_analysis_product_ui_route_contract_v1",
        "generatedAt": _utc_now_iso(),
        "routePath": f"/external/soccertrack/{selected}/analysis",
        "apiRoutePath": f"/api/external/soccertrack/{selected}/analysis",
        "routeName": "SoccerTrackExternalAnalysis",
        "viewModelSchemaVersion": view_model.get("schemaVersion"),
        "productUiBindingReady": view_model.get("readiness", {}).get("analysisProductUiReady") is True,
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
    event_rows = "".join(
        f'<li><span>{escape(str(row.get("value", "")))}</span><strong>{escape(str(row.get("count", "")))}</strong></li>'
        for row in view_model.get("eventTypeBreakdown", [])
        if isinstance(row, dict)
    )
    limitations = "".join(f"<li>{escape(str(item))}</li>" for item in view_model.get("limitations", []))
    title = str(view_model.get("hero", {}).get("title") or "SoccerTrack external fixture")
    subtitle = str(view_model.get("hero", {}).get("subtitle") or "")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      body {{ margin: 0; font-family: Arial, sans-serif; color: #111827; background: #ffffff; }}
      main {{ max-width: 960px; margin: 0 auto; padding: 32px; }}
      .banner {{ border-left: 4px solid #0f766e; background: #f0fdfa; padding: 12px 14px; margin: 20px 0; }}
      .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
      .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 14px; }}
      .label {{ color: #4b5563; font-size: 12px; text-transform: uppercase; }}
      .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
      li {{ margin-top: 8px; display: flex; justify-content: space-between; gap: 16px; }}
    </style>
  </head>
  <body>
    <main>
      <h1>{escape(title)}</h1>
      <p>{escape(subtitle)}</p>
      <section class="banner">{escape(str(view_model.get("limitationsBanner", "")))}</section>
      <section class="grid">{cards}</section>
      <h2>Top Event Types</h2>
      <ul>{event_rows}</ul>
      <h2>Limitations</h2>
      <ul>{limitations}</ul>
    </main>
  </body>
</html>
"""


def _ui_binding_audit(report_ready: bool, view_model: dict[str, Any], route_contract: dict[str, Any], html: str) -> dict[str, Any]:
    valid = bool(
        report_ready
        and view_model.get("readiness", {}).get("analysisProductUiReady") is True
        and view_model.get("readiness", {}).get("candidateEvaluationReady") is False
        and bool(view_model.get("limitationsBanner"))
        and bool(view_model.get("cards"))
        and route_contract.get("productUiBindingReady") is True
        and route_contract.get("allowsCandidateEvaluationReadiness") is False
        and "not detector evaluation" in html
    )
    return {
        "schemaVersion": "soccertrack_analysis_product_ui_binding_audit_v1",
        "generatedAt": _utc_now_iso(),
        "sourceReportSmokeReady": report_ready,
        "uiViewModelValid": valid,
        "htmlRenderSmokeValid": "SoccerTrack" in html and "Events" in html and "not detector evaluation" in html,
        "routeContractValid": route_contract.get("productUiBindingReady") is True,
        "candidateEvaluationReady": view_model.get("readiness", {}).get("candidateEvaluationReady"),
        "trainingReady": view_model.get("readiness", {}).get("trainingReady"),
        "promotionReady": view_model.get("readiness", {}).get("promotionReady"),
        "runtimeDefaultMutationReady": view_model.get("readiness", {}).get("runtimeDefaultMutationReady"),
    }


def _classify(report_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not report_ready:
        return (
            BLOCKER_REPORT_MISSING,
            NEXT_REPORT,
            False,
            False,
            "SoccerTrack analysis report smoke is missing or unsafe; rerun report smoke before UI binding.",
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
            True,
            "SoccerTrack analysis product UI binding contract is incomplete or overclaims readiness.",
        )
    return (
        None,
        NEXT_UI_ROUTE_IMPLEMENTATION,
        True,
        True,
        "SoccerTrack analysis UI binding is ready. Advance to read-only route implementation; keep detector evaluation, training, promotion, and runtime mutation separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "analysis_report_smoke_missing", "selected": primary_blocker == BLOCKER_REPORT_MISSING, "primaryBlocker": BLOCKER_REPORT_MISSING, "nextRecommendedNextLever": NEXT_REPORT},
            {"condition": "analysis_product_ui_contract_gap", "selected": primary_blocker == BLOCKER_UI_CONTRACT_GAP, "primaryBlocker": BLOCKER_UI_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_UI_CONTRACT_REPAIR},
            {"condition": "analysis_product_ui_binding_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_UI_ROUTE_IMPLEMENTATION},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Analysis Product UI Binding",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product UI binding ready: `{summary.get('productUiBindingReady')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Reported events: `{summary.get('reportedEventCount')}`",
            f"- Reported frames: `{summary.get('reportedFrameCount')}`",
            f"- Candidate ready for evaluation: `{summary.get('candidateReadyForEvaluation')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_analysis_product_ui_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    report_dir_name: str = DEFAULT_REPORT_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_analysis_product_ui_binding",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, report_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    report_ready = _report_ready(inputs["reportSummary"], inputs["reportPayload"])
    view_model = _view_model(inputs["reportPayload"])
    route_contract = _route_contract(view_model)
    html = _render_html(view_model)
    audit = _ui_binding_audit(report_ready, view_model, route_contract, html)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(report_ready, audit)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_analysis_product_ui_binding",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_analysis_report_smoke",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": (inputs["reportPayload"] or {}).get("selectedMatchId"),
        "productUiBindingReady": goal_achieved,
        "reportedEventCount": (inputs["reportPayload"] or {}).get("reportedEventCount"),
        "reportedFrameCount": (inputs["reportPayload"] or {}).get("reportedFrameCount"),
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "videoDownloadExecuted": False,
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
    parser = argparse.ArgumentParser(description="Bind the SoccerTrack external analysis report into a product UI view model.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--report-dir-name", default=DEFAULT_REPORT_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_analysis_product_ui_binding")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_analysis_product_ui_binding(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        report_dir_name=str(args.report_dir_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
