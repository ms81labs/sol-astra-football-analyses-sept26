from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

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
DEFAULT_BRIDGE_DIR_NAME = "football_external_soccertrack_match_bundle_bridge_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_product_route_smoke_v1"

BLOCKER_BRIDGE_MISSING = "football_external_soccertrack_match_bundle_bridge_missing"
BLOCKER_ROUTE_CONTRACT_GAP = "football_external_soccertrack_product_route_contract_gap"

NEXT_BRIDGE = "football_external_soccertrack_match_bundle_bridge_smoke"
NEXT_ROUTE_REPAIR = "football_external_soccertrack_product_route_contract_repair"
NEXT_ANALYSIS_REPORT = "football_external_soccertrack_analysis_report_smoke"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_external_product_route_smoke",
            "successCriteria": [
                "serve the saved SoccerTrack match_bundle_v1 bridge artifact through a read-only external route",
                "preserve external dataset provenance and non-readiness flags",
                "do not write into normal match storage or mutate runtime defaults",
            ],
            "failureAdaptation": "If the route contract fails, repair only the external route or bridge read contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_product_route_contract_repair",
            "successCriteria": [
                "repair route path, status, or payload checks without altering bridge truth",
                "keep training, promotion, candidate evaluation, and runtime mutation false",
            ],
            "failureAdaptation": "If the bridge artifact is unsafe or missing, route back to bridge smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_product_route_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before analysis report smoke until the product route is valid",
            ],
            "failureAdaptation": "Route to bridge smoke or product route contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, bridge_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    bridge_root = candidate_root / bridge_dir_name
    return {
        "candidateRoot": candidate_root,
        "bridgeRoot": bridge_root,
        "bridgeSummary": _load_json(bridge_root / "soccertrack_match_bundle_bridge_summary.json"),
        "bridgeBundle": _load_json(bridge_root / "soccertrack_external_match_bundle.json"),
    }


def _bridge_ready(summary: dict[str, Any] | None, bundle: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("matchBundleBridgeReady") is True
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationAllowed") is False
        and isinstance(bundle, dict)
        and bundle.get("schemaVersion") == "match_bundle_v1"
        and isinstance(bundle.get("match"), dict)
        and isinstance(bundle.get("provenance"), dict)
        and bundle["provenance"].get("externalDataset") == "soccertrack_v2"
    )


async def _route_response(storage_root: Path, route_path: str) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get(route_path)
    try:
        body: Any = response.json()
    except json.JSONDecodeError:
        body = response.text
    return {
        "schemaVersion": "soccertrack_product_route_response_audit_v1",
        "generatedAt": _utc_now_iso(),
        "routePath": route_path,
        "routeStatusCode": response.status_code,
        "contentType": response.headers.get("content-type"),
        "body": body,
    }


def _call_route(storage_root: Path, route_path: str) -> dict[str, Any]:
    return anyio.run(_route_response, storage_root, route_path)


def _route_contract_audit(route_audit: dict[str, Any], expected_match_id: str | None) -> dict[str, Any]:
    body = route_audit.get("body") if isinstance(route_audit.get("body"), dict) else {}
    match = body.get("match") if isinstance(body.get("match"), dict) else {}
    provenance = body.get("provenance") if isinstance(body.get("provenance"), dict) else {}
    events = body.get("events") if isinstance(body.get("events"), list) else []
    frames = body.get("frames") if isinstance(body.get("frames"), list) else []
    expected_route = f"/api/external/soccertrack/{expected_match_id}/export/match.json" if expected_match_id else None
    checks = {
        "routeReturnedOk": route_audit.get("routeStatusCode") == 200,
        "schemaVersionPresent": body.get("schemaVersion") == "match_bundle_v1",
        "matchIdMatches": match.get("id") == f"soccertrack:{expected_match_id}",
        "externalDatasetProvenancePresent": provenance.get("externalDataset") == "soccertrack_v2",
        "runtimeDefaultMutationNotAllowed": provenance.get("runtimeDefaultMutationAllowed") is False,
        "exportsRouteMatches": body.get("exports", {}).get("matchJson") == expected_route if isinstance(body.get("exports"), dict) else False,
        "eventsPresent": len(events) > 0,
        "framesPresent": len(frames) > 0,
        "normalMatchStorageNotRequired": match.get("inputMode") == "external_soccertrack_fixture",
    }
    return {
        "schemaVersion": "soccertrack_external_product_route_contract_audit_v1",
        "generatedAt": _utc_now_iso(),
        "checks": checks,
        "externalRouteContractPassed": all(checks.values()),
    }


def _classify(bridge_ready: bool, route_contract_passed: bool) -> tuple[str | None, str, bool, bool, str]:
    if not bridge_ready:
        return (
            BLOCKER_BRIDGE_MISSING,
            NEXT_BRIDGE,
            False,
            False,
            "SoccerTrack product route smoke requires a passing external MatchBundle bridge artifact first.",
        )
    if not route_contract_passed:
        return (
            BLOCKER_ROUTE_CONTRACT_GAP,
            NEXT_ROUTE_REPAIR,
            False,
            True,
            "SoccerTrack external product route failed its read-only match bundle contract; repair route wiring before analysis report smoke.",
        )
    return (
        None,
        NEXT_ANALYSIS_REPORT,
        True,
        True,
        "SoccerTrack external match bundle is reachable through the product route. Advance to analysis report smoke; no training, promotion, candidate evaluation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "match_bundle_bridge_missing", "selected": primary_blocker == BLOCKER_BRIDGE_MISSING, "primaryBlocker": BLOCKER_BRIDGE_MISSING, "nextRecommendedNextLever": NEXT_BRIDGE},
            {"condition": "product_route_contract_gap", "selected": primary_blocker == BLOCKER_ROUTE_CONTRACT_GAP, "primaryBlocker": BLOCKER_ROUTE_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_ROUTE_REPAIR},
            {"condition": "analysis_report_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_ANALYSIS_REPORT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Product Route Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Route path: `{summary.get('routePath')}`",
            f"- Route status: `{summary.get('routeStatusCode')}`",
            f"- Product route smoke passed: `{summary.get('productRouteSmokePassed')}`",
            f"- External bundle event count: `{summary.get('externalBundleEventCount')}`",
            f"- External bundle frame count: `{summary.get('externalBundleFrameCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_product_route_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    bridge_dir_name: str = DEFAULT_BRIDGE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_external_product_route_smoke",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root, candidate_name, bridge_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    bridge_ready = _bridge_ready(inputs.get("bridgeSummary"), inputs.get("bridgeBundle"))
    selected_match_id = None
    if isinstance(inputs.get("bridgeBundle"), dict):
        provenance = inputs["bridgeBundle"].get("provenance") if isinstance(inputs["bridgeBundle"].get("provenance"), dict) else {}
        selected_match_id = str(provenance.get("externalSourceMatchId") or "").strip() or None
    route_path = f"/api/external/soccertrack/{selected_match_id}/export/match.json" if selected_match_id else "/api/external/soccertrack/unknown/export/match.json"
    route_audit = _call_route(storage_root, route_path) if bridge_ready else {
        "schemaVersion": "soccertrack_product_route_response_audit_v1",
        "generatedAt": _utc_now_iso(),
        "routePath": route_path,
        "routeStatusCode": None,
        "contentType": None,
        "body": None,
    }
    contract_audit = _route_contract_audit(route_audit, selected_match_id)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(
        bridge_ready,
        contract_audit["externalRouteContractPassed"],
    )
    attempts = _attempt_plan()
    body = route_audit.get("body") if isinstance(route_audit.get("body"), dict) else {}
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_product_route_smoke",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_match_bundle_bridge_smoke",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "routePath": route_path,
        "routeStatusCode": route_audit.get("routeStatusCode"),
        "productRouteSmokePassed": goal_achieved,
        "responseSchemaVersion": body.get("schemaVersion"),
        "externalBundleEventCount": len(body.get("events", [])) if isinstance(body.get("events"), list) else 0,
        "externalBundleFrameCount": len(body.get("frames", [])) if isinstance(body.get("frames"), list) else 0,
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
        "productRouteResponseAudit": route_audit,
        "externalRouteContractAudit": contract_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_product_route_smoke_summary.json", summary)
    _write_json(output_root / "product_route_response_audit.json", route_audit)
    _write_json(output_root / "external_route_contract_audit.json", contract_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke the read-only SoccerTrack external match bundle product route.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--bridge-dir-name", default=DEFAULT_BRIDGE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_external_product_route_smoke")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_product_route_smoke(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        bridge_dir_name=str(args.bridge_dir_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
