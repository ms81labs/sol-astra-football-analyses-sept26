from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_ROUTE_DIR_NAME = "football_external_soccertrack_product_route_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_analysis_report_smoke_v1"

BLOCKER_PRODUCT_ROUTE_MISSING = "football_external_soccertrack_product_route_smoke_missing"
BLOCKER_REPORT_GAP = "football_external_soccertrack_analysis_report_gap"

NEXT_PRODUCT_ROUTE = "football_external_soccertrack_product_route_smoke"
NEXT_REPORT_REPAIR = "football_external_soccertrack_analysis_report_payload_repair"
NEXT_UI_BINDING = "football_external_soccertrack_analysis_product_ui_binding"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_external_analysis_report_smoke",
            "successCriteria": [
                "load the read-only SoccerTrack product route response audit",
                "render a human-readable external fixture report",
                "preserve non-evaluation, non-training, non-promotion, and no-runtime-mutation flags",
            ],
            "failureAdaptation": "If report rendering fails, repair only the analysis report payload from the route response.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_analysis_report_payload_repair",
            "successCriteria": [
                "repair report fields from the saved product route payload",
                "do not reread raw source files or mutate normal match storage",
            ],
            "failureAdaptation": "If the route response is missing or unsafe, route back to product route smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_analysis_report_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before UI binding if the report smoke is unsafe",
            ],
            "failureAdaptation": "Route to product route smoke or report payload repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, route_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    route_root = candidate_root / route_dir_name
    return {
        "candidateRoot": candidate_root,
        "routeSummary": _load_json(route_root / "soccertrack_product_route_smoke_summary.json"),
        "routeResponseAudit": _load_json(route_root / "product_route_response_audit.json"),
        "routeContractAudit": _load_json(route_root / "external_route_contract_audit.json"),
    }


def _route_ready(summary: dict[str, Any] | None, response: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    body = response.get("body") if isinstance(response, dict) and isinstance(response.get("body"), dict) else {}
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productRouteSmokePassed") is True
        and summary.get("routeStatusCode") == 200
        and summary.get("responseSchemaVersion") == "match_bundle_v1"
        and int(summary.get("externalBundleEventCount") or 0) > 0
        and int(summary.get("externalBundleFrameCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and isinstance(response, dict)
        and response.get("routeStatusCode") == 200
        and isinstance(body, dict)
        and body.get("schemaVersion") == "match_bundle_v1"
        and isinstance(body.get("events"), list)
        and len(body["events"]) > 0
        and isinstance(body.get("frames"), list)
        and len(body["frames"]) > 0
        and isinstance(contract, dict)
        and contract.get("externalRouteContractPassed") is True
    )


def _top_counts(rows: list[Any], field: str, limit: int = 8) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows:
        if isinstance(row, dict):
            value = str(row.get(field) or "unknown")
            counts[value] += 1
    return [{"value": value, "count": count} for value, count in counts.most_common(limit)]


def _report_payload(response: dict[str, Any] | None) -> dict[str, Any]:
    body = response.get("body") if isinstance(response, dict) and isinstance(response.get("body"), dict) else {}
    match = body.get("match") if isinstance(body.get("match"), dict) else {}
    provenance = body.get("provenance") if isinstance(body.get("provenance"), dict) else {}
    analytics = body.get("analytics") if isinstance(body.get("analytics"), dict) else {}
    analytics_summary = analytics.get("summary") if isinstance(analytics.get("summary"), dict) else {}
    events = body.get("events") if isinstance(body.get("events"), list) else []
    frames = body.get("frames") if isinstance(body.get("frames"), list) else []
    return {
        "schemaVersion": "soccertrack_external_analysis_report_payload_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_soccertrack_product_route_smoke",
        "sourceDataset": provenance.get("externalDataset") or "soccertrack_v2",
        "selectedMatchId": provenance.get("externalSourceMatchId"),
        "routePath": response.get("routePath") if isinstance(response, dict) else None,
        "match": {
            "id": match.get("id"),
            "name": match.get("name"),
            "inputMode": match.get("inputMode"),
        },
        "reportedEventCount": len(events),
        "reportedFrameCount": len(frames),
        "taskFixtureSummary": {
            "basEventCount": analytics_summary.get("basEventCount"),
            "gsrHalfCount": analytics_summary.get("gsrHalfCount"),
            "motFrameCount": analytics_summary.get("motFrameCount"),
            "motSampledFrameCount": analytics_summary.get("motSampledFrameCount"),
        },
        "eventTypeBreakdown": _top_counts(events, "type"),
        "teamBreakdown": _top_counts(events, "team"),
        "ballStatusBreakdown": _top_counts(
            [
                {"status": (frame.get("ball") or {}).get("status") if isinstance(frame, dict) and isinstance(frame.get("ball"), dict) else None}
                for frame in frames
            ],
            "status",
        ),
        "readiness": {
            "analysisReportReady": len(events) > 0 and len(frames) > 0,
            "productRouteReady": True,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": [
            "external SoccerTrack fixture report only",
            "not detector evaluation",
            "not ball-localization truth",
            "not full product runtime mutation evidence",
            "does not download videos",
            "does not train or promote a detector",
        ],
    }


def _report_markdown(payload: dict[str, Any]) -> str:
    event_rows = payload.get("eventTypeBreakdown") if isinstance(payload.get("eventTypeBreakdown"), list) else []
    team_rows = payload.get("teamBreakdown") if isinstance(payload.get("teamBreakdown"), list) else []
    ball_rows = payload.get("ballStatusBreakdown") if isinstance(payload.get("ballStatusBreakdown"), list) else []
    lines = [
        "# SoccerTrack External Fixture Report",
        "",
        f"- Match: `{payload.get('match', {}).get('id')}`",
        f"- Source dataset: `{payload.get('sourceDataset')}`",
        f"- Product route: `{payload.get('routePath')}`",
        f"- Events: `{payload.get('reportedEventCount')}`",
        f"- Sampled frames: `{payload.get('reportedFrameCount')}`",
        "",
        "## Fixture Coverage",
        "",
    ]
    for key, value in (payload.get("taskFixtureSummary") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Top Event Types", ""])
    for row in event_rows:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('value')}`: `{row.get('count')}`")
    lines.extend(["", "## Team Split", ""])
    for row in team_rows:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('value')}`: `{row.get('count')}`")
    lines.extend(["", "## Sampled Ball Status", ""])
    for row in ball_rows:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('value')}`: `{row.get('count')}`")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "This is an external SoccerTrack fixture report from the product route payload. It is not detector evaluation, not training evidence, not promotion evidence, and not runtime-default mutation evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_audit(markdown: str, payload: dict[str, Any]) -> dict[str, Any]:
    rendered_lower = markdown.lower()
    checks = {
        "requiredTitlePresent": "SoccerTrack External Fixture Report" in markdown,
        "eventCountRendered": str(payload.get("reportedEventCount")) in markdown,
        "frameCountRendered": str(payload.get("reportedFrameCount")) in markdown,
        "eventBreakdownRendered": "Top Event Types" in markdown and any(str(row.get("value")) in markdown for row in payload.get("eventTypeBreakdown") or [] if isinstance(row, dict)),
        "limitationsRendered": "not detector evaluation" in rendered_lower and "not training evidence" in rendered_lower,
        "nonReadinessRendered": "not promotion evidence" in rendered_lower and "runtime-default mutation" in rendered_lower,
    }
    return {
        "schemaVersion": "soccertrack_analysis_report_render_audit_v1",
        "generatedAt": _utc_now_iso(),
        "renderedReportBytes": len(markdown.encode("utf-8")),
        "checks": checks,
        "reportRenderPassed": all(checks.values()),
    }


def _classify(route_ready: bool, payload: dict[str, Any], render_audit: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not route_ready:
        return (
            BLOCKER_PRODUCT_ROUTE_MISSING,
            NEXT_PRODUCT_ROUTE,
            False,
            False,
            "SoccerTrack analysis report smoke requires a passing product route smoke payload first.",
        )
    if payload.get("readiness", {}).get("analysisReportReady") is not True or render_audit.get("reportRenderPassed") is not True:
        return (
            BLOCKER_REPORT_GAP,
            NEXT_REPORT_REPAIR,
            False,
            True,
            "SoccerTrack analysis report payload or markdown render is incomplete; repair report payload before UI binding.",
        )
    return (
        None,
        NEXT_UI_BINDING,
        True,
        True,
        "SoccerTrack analysis report smoke passed. Advance to product UI binding; no training, promotion, candidate evaluation, video download, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "product_route_smoke_missing", "selected": primary_blocker == BLOCKER_PRODUCT_ROUTE_MISSING, "primaryBlocker": BLOCKER_PRODUCT_ROUTE_MISSING, "nextRecommendedNextLever": NEXT_PRODUCT_ROUTE},
            {"condition": "analysis_report_gap", "selected": primary_blocker == BLOCKER_REPORT_GAP, "primaryBlocker": BLOCKER_REPORT_GAP, "nextRecommendedNextLever": NEXT_REPORT_REPAIR},
            {"condition": "analysis_product_ui_binding_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_UI_BINDING},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Analysis Report Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Analysis report smoke passed: `{summary.get('analysisReportSmokePassed')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Reported events: `{summary.get('reportedEventCount')}`",
            f"- Reported frames: `{summary.get('reportedFrameCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_analysis_report_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    route_dir_name: str = DEFAULT_ROUTE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_external_analysis_report_smoke",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root, candidate_name, route_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    route_ready = _route_ready(inputs["routeSummary"], inputs["routeResponseAudit"], inputs["routeContractAudit"])
    report_payload = _report_payload(inputs["routeResponseAudit"])
    report_md = _report_markdown(report_payload)
    render_audit = _render_audit(report_md, report_payload)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(
        route_ready,
        report_payload,
        render_audit,
    )
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_analysis_report_smoke",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_product_route_smoke",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": report_payload.get("selectedMatchId"),
        "analysisReportSmokePassed": goal_achieved,
        "reportedEventCount": report_payload.get("reportedEventCount"),
        "reportedFrameCount": report_payload.get("reportedFrameCount"),
        "productRouteReady": route_ready,
        "analysisReportReady": goal_achieved,
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
        "analysisReportPayload": report_payload,
        "analysisReportRenderAudit": render_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_analysis_report_smoke_summary.json", summary)
    _write_json(output_root / "soccertrack_analysis_report_payload.json", report_payload)
    (output_root / "soccertrack_analysis_report.md").write_text(report_md, encoding="utf-8")
    _write_json(output_root / "analysis_report_render_audit.json", render_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a read-only SoccerTrack external analysis report from the product route payload.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--route-dir-name", default=DEFAULT_ROUTE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_external_analysis_report_smoke")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_analysis_report_smoke(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        route_dir_name=str(args.route_dir_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
