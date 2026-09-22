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
DEFAULT_REPORT_DIR_NAME = "football_external_benchmark_report_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_product_ui_binding_v1"

BLOCKER_REPORT_MISSING = "football_external_benchmark_report_smoke_missing"
BLOCKER_UI_CONTRACT_GAP = "football_external_benchmark_product_ui_contract_gap"

NEXT_REPORT_SMOKE = "football_external_benchmark_report_smoke"
NEXT_UI_CONTRACT_REPAIR = "football_external_benchmark_product_ui_contract_repair"
NEXT_UI_ROUTE_IMPLEMENTATION = "football_external_benchmark_product_ui_route_implementation"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_product_ui_binding",
            "successCriteria": [
                "convert report smoke output into a product UI view model",
                "write static HTML render smoke and route contract",
                "keep detector evaluation, training, promotion, video download, normal match storage mutation, and runtime-default mutation false",
            ],
            "failureAdaptation": "If report smoke is missing, rerun benchmark report smoke.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_product_ui_contract_repair",
            "successCriteria": [
                "repair view model, HTML, or route contract from report smoke artifacts only",
                "do not execute detector evaluation or mutate runtime defaults",
            ],
            "failureAdaptation": "If the report payload remains unsafe, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_product_ui_binding_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to report smoke, UI contract repair, or route implementation.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, report_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    report_root = candidate_root / report_dir_name
    return {
        "candidateRoot": candidate_root,
        "reportSummary": _load_json(report_root / "external_benchmark_report_smoke_summary.json"),
        "reportViewModel": _load_json(report_root / "external_benchmark_report_view_model.json"),
        "reportMarkdownPath": report_root / "external_benchmark_report.md",
    }


def _report_ready(summary: dict[str, Any] | None, view_model: dict[str, Any] | None, markdown_path: Path) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("externalBenchmarkReportSmokePassed") is True
        and summary.get("productUiBindingReady") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(view_model, dict)
        and view_model.get("schemaVersion") == "football_external_benchmark_report_view_model_v1"
        and view_model.get("reportReady") is True
        and isinstance(view_model.get("sources"), list)
        and len(view_model["sources"]) >= 2
        and markdown_path.exists()
    )


def _product_view_model(report_view_model: dict[str, Any] | None) -> dict[str, Any]:
    sources = list((report_view_model or {}).get("sources") or [])
    total_events = sum(int(row.get("eventCount") or 0) for row in sources if isinstance(row, dict))
    total_frames = sum(int(row.get("reportedFrameCount") or 0) for row in sources if isinstance(row, dict))
    return {
        "schemaVersion": "football_external_benchmark_product_ui_view_model_v1",
        "generatedAt": utc_now_iso(),
        "hero": {
            "title": "External Benchmark",
            "subtitle": "Generated-truth smoke report for SoccerNet and SoccerTrack external football sources.",
        },
        "limitationsBanner": "This is a bounded report smoke, not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
        "cards": [
            {"label": "Sources", "value": len(sources)},
            {"label": "Events", "value": total_events},
            {"label": "Frames", "value": total_frames},
            {"label": "Detector eval", "value": "blocked"},
        ],
        "sources": sources,
        "sourceIds": [row.get("sourceId") for row in sources if isinstance(row, dict)],
        "readiness": {
            "productUiBindingReady": True,
            "productRouteImplementationReady": True,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "safeNextAction": NEXT_UI_ROUTE_IMPLEMENTATION,
    }


def _route_contract(view_model: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_product_ui_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "routeName": "ExternalBenchmarkReport",
        "apiRoutePath": "/api/external/benchmark/report",
        "htmlRoutePath": "/external/benchmark/report",
        "viewModelSchemaVersion": view_model.get("schemaVersion"),
        "productUiBindingReady": True,
        "requiresLimitationsBanner": True,
        "mustShowLimitationsBanner": bool(view_model.get("limitationsBanner")),
        "allowsDetectorEvaluation": False,
        "allowsCandidateEvaluationReadiness": False,
        "allowsTraining": False,
        "allowsPromotion": False,
        "allowsRuntimeDefaultMutation": False,
        "allowsVideoDownload": False,
        "allowsNormalMatchStorageMutation": False,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    cards = "".join(
        f'<article class="card"><div class="label">{escape(str(card.get("label", "")))}</div><div class="value">{escape(str(card.get("value", "")))}</div></article>'
        for card in view_model.get("cards", [])
        if isinstance(card, dict)
    )
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('sourceId', '')))}</td>"
        f"<td>{escape(str(row.get('eventCount', 0)))}</td>"
        f"<td>{escape(str(row.get('reportedFrameCount', 0)))}</td>"
        f"<td>{escape(str(row.get('segmentCount', 0)))}</td>"
        "</tr>"
        for row in view_model.get("sources", [])
        if isinstance(row, dict)
    )
    title = str(view_model.get("hero", {}).get("title") or "External Benchmark")
    subtitle = str(view_model.get("hero", {}).get("subtitle") or "")
    banner = str(view_model.get("limitationsBanner") or "")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      body {{ margin: 0; font-family: Arial, sans-serif; color: #172033; background: #fff; }}
      main {{ max-width: 1080px; margin: 0 auto; padding: 32px; }}
      .banner {{ border-left: 4px solid #2563eb; background: #eff6ff; padding: 12px 14px; margin: 20px 0; }}
      .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
      .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 14px; }}
      .label {{ color: #4b5563; font-size: 12px; text-transform: uppercase; }}
      .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
      th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; }}
    </style>
  </head>
  <body>
    <main>
      <h1>{escape(title)}</h1>
      <p>{escape(subtitle)}</p>
      <section class="banner">{escape(banner)}</section>
      <section class="grid">{cards}</section>
      <h2>Sources</h2>
      <table>
        <thead><tr><th>Source</th><th>Events</th><th>Frames</th><th>Segments</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </main>
  </body>
</html>
"""


def _audit(report_ready: bool, view_model: dict[str, Any], route_contract: dict[str, Any], html: str) -> dict[str, Any]:
    checks = {
        "sourceReportSmokeReady": report_ready,
        "uiViewModelValid": view_model.get("readiness", {}).get("productUiBindingReady") is True and len(view_model.get("sources") or []) >= 2,
        "htmlRenderSmokeValid": "External Benchmark" in html and "soccernet" in html and "soccertrack" in html,
        "routeContractValid": route_contract.get("productUiBindingReady") is True and route_contract.get("allowsRuntimeDefaultMutation") is False,
        "candidateEvaluationReady": False,
        "trainingReady": False,
        "promotionReady": False,
        "runtimeDefaultMutationReady": False,
    }
    return {
        "schemaVersion": "football_external_benchmark_product_ui_binding_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "productUiBindingAuditPassed": all(
            value is True for key, value in checks.items() if key.endswith("Valid") or key == "sourceReportSmokeReady"
        )
        and checks["candidateEvaluationReady"] is False
        and checks["trainingReady"] is False
        and checks["promotionReady"] is False
        and checks["runtimeDefaultMutationReady"] is False,
    }


def _classify(report_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not report_ready:
        return (
            BLOCKER_REPORT_MISSING,
            NEXT_REPORT_SMOKE,
            False,
            "External benchmark report smoke is missing or unsafe; rerun report smoke before product UI binding.",
        )
    if audit.get("productUiBindingAuditPassed") is not True:
        return (
            BLOCKER_UI_CONTRACT_GAP,
            NEXT_UI_CONTRACT_REPAIR,
            False,
            "External benchmark product UI binding is incomplete; repair view model or route contract before route implementation.",
        )
    return (
        None,
        NEXT_UI_ROUTE_IMPLEMENTATION,
        True,
        "External benchmark product UI binding passed and produced a route-ready view model. Advance to route implementation; no detector evaluation, data/video download, training, promotion, normal storage mutation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "report_smoke_missing", "selected": primary_blocker == BLOCKER_REPORT_MISSING, "primaryBlocker": BLOCKER_REPORT_MISSING, "nextRecommendedNextLever": NEXT_REPORT_SMOKE},
            {"condition": "product_ui_contract_gap", "selected": primary_blocker == BLOCKER_UI_CONTRACT_GAP, "primaryBlocker": BLOCKER_UI_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_UI_CONTRACT_REPAIR},
            {"condition": "product_ui_route_implementation_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_UI_ROUTE_IMPLEMENTATION},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Product UI Binding",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Source count: `{summary.get('sourceCount')}`",
            f"- Product route implementation ready: `{summary.get('productRouteImplementationReady')}`",
            f"- Detector evaluation executed: `{summary.get('detectorEvaluationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime-default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_product_ui_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    report_dir_name: str = DEFAULT_REPORT_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_product_ui_binding",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, report_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _report_ready(inputs["reportSummary"], inputs["reportViewModel"], inputs["reportMarkdownPath"])
    view_model = _product_view_model(inputs["reportViewModel"])
    route_contract = _route_contract(view_model)
    html = _render_html(view_model)
    audit = _audit(ready, view_model, route_contract, html)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, audit)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_product_ui_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_report_smoke",
        "productUiBindingReady": goal_achieved,
        "productRouteImplementationReady": goal_achieved,
        "sourceCount": len(view_model.get("sources") or []),
        "apiRoutePath": route_contract.get("apiRoutePath"),
        "htmlRoutePath": route_contract.get("htmlRoutePath"),
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "datasetDownloadExecuted": False,
        "videoDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    failsafe = {"attemptBudget": 3, "attempts": attempts}
    outcome = {
        "summary": summary,
        "externalBenchmarkProductUiViewModel": view_model,
        "externalBenchmarkProductUiRouteContract": route_contract,
        "productUiBindingAudit": audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": failsafe,
    }
    _write_json(output_root / "external_benchmark_product_ui_binding_summary.json", summary)
    _write_json(output_root / "external_benchmark_product_ui_view_model.json", view_model)
    (output_root / "external_benchmark_product_ui_render_smoke.html").write_text(html, encoding="utf-8")
    _write_json(output_root / "external_benchmark_product_ui_route_contract.json", route_contract)
    _write_json(output_root / "product_ui_binding_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", failsafe)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--report-dir-name", default=DEFAULT_REPORT_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    args = parser.parse_args()
    summary = run_football_external_benchmark_product_ui_binding(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        report_dir_name=args.report_dir_name,
        output_dir_name=args.output_dir_name,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("goalAchieved") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
