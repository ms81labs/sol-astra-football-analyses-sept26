from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SOURCE_DIR_NAME = "football_external_soccertrack_analysis_product_ui_route_implementation_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_analysis_product_lane_closeout_v1"

BLOCKER_ROUTE_MISSING = "football_external_soccertrack_analysis_product_ui_route_missing"
BLOCKER_CLOSEOUT_GAP = "football_external_soccertrack_analysis_product_lane_closeout_gap"

NEXT_ROUTE_IMPLEMENTATION = "football_external_soccertrack_analysis_product_ui_route_implementation"
NEXT_CLOSEOUT_REPAIR = "football_external_soccertrack_analysis_product_route_closeout_repair"
NEXT_SOCCERTRACK_CLOSEOUT = "football_external_soccertrack_lane_closeout"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_analysis_product_lane_closeout",
            "successCriteria": [
                "close the SoccerTrack analysis product lane from route implementation truth",
                "write a capability matrix and remaining-gap analysis",
                "select the broader SoccerTrack lane closeout as the next lever",
            ],
            "failureAdaptation": "If route implementation truth is incomplete, route back to route implementation.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_analysis_product_route_closeout_repair",
            "successCriteria": [
                "repair missing closeout-only fields without modifying route artifacts",
                "keep detector evaluation, training, promotion, video download, and runtime mutation blocked",
            ],
            "failureAdaptation": "If the route itself is unsafe, route back to route implementation.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_analysis_product_lane_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to route implementation or closeout repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, source_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    source_root = candidate_root / source_dir_name
    return {
        "candidateRoot": candidate_root,
        "sourceRoot": source_root,
        "summary": _load_json(source_root / "analysis_product_ui_route_implementation_summary.json"),
        "audit": _load_json(source_root / "analysis_product_ui_route_smoke_audit.json"),
        "responseFixture": _load_json(source_root / "analysis_product_ui_route_response_fixture.json"),
    }


def _route_ready(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("summary")
    audit = inputs.get("audit")
    fixture = inputs.get("responseFixture")
    body = fixture.get("body") if isinstance(fixture, dict) and isinstance(fixture.get("body"), dict) else {}
    readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    selected_match_id = summary.get("selectedMatchId") if isinstance(summary, dict) else None
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productUiRouteReady") is True
        and selected_match_id
        and summary.get("apiRoutePath") == f"/api/external/soccertrack/{selected_match_id}/analysis"
        and summary.get("htmlRoutePath") == f"/external/soccertrack/{selected_match_id}/analysis"
        and int(summary.get("reportedEventCount") or 0) > 0
        and int(summary.get("reportedFrameCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and isinstance(audit, dict)
        and audit.get("apiRouteSmokePassed") is True
        and audit.get("htmlRouteSmokePassed") is True
        and isinstance(fixture, dict)
        and fixture.get("statusCode") == 200
        and body.get("schemaVersion") == "soccertrack_analysis_product_ui_view_model_v1"
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
    )


def _capability_matrix(route_ready: bool, inputs: dict[str, Any]) -> dict[str, Any]:
    summary = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    return {
        "schemaVersion": "soccertrack_analysis_product_capability_matrix_v1",
        "generatedAt": _utc_now_iso(),
        "externalFixtureAnalysisProductReady": route_ready,
        "routeCapabilityReady": route_ready,
        "selectedMatchId": summary.get("selectedMatchId"),
        "apiRoutePath": summary.get("apiRoutePath"),
        "htmlRoutePath": summary.get("htmlRoutePath"),
        "reportedEventCount": summary.get("reportedEventCount"),
        "reportedFrameCount": summary.get("reportedFrameCount"),
        "detectorEvaluationReady": False,
        "trainingReady": False,
        "promotionReady": False,
        "runtimeDefaultMutationReady": False,
        "videoDownloadRequiredForCurrentProductRoute": False,
        "normalMatchStorageMutationRequiredForCurrentProductRoute": False,
    }


def _remaining_gap_analysis(route_ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_analysis_product_remaining_gap_analysis_v1",
        "generatedAt": _utc_now_iso(),
        "analysisProductRouteClosed": route_ready,
        "remainingPrimaryGap": "soccertrack_lane_closeout_ready" if route_ready else "soccertrack_analysis_product_route_not_closed",
        "remainingGaps": []
        if not route_ready
        else [
            "broader SoccerTrack lane closeout should summarize Google Drive fixture fetch, adapter, MatchBundle, product route, report, and UI route truth",
            "detector evaluation and training remain separate from external data/product-route readiness",
        ],
        "nextSafeLever": NEXT_SOCCERTRACK_CLOSEOUT if route_ready else NEXT_ROUTE_IMPLEMENTATION,
    }


def _classify(route_ready: bool) -> tuple[str | None, str, bool, bool, str]:
    if not route_ready:
        return (
            BLOCKER_ROUTE_MISSING,
            NEXT_ROUTE_IMPLEMENTATION,
            False,
            False,
            "SoccerTrack analysis product route implementation is missing or unsafe; rerun route implementation before lane closeout.",
        )
    return (
        None,
        NEXT_SOCCERTRACK_CLOSEOUT,
        True,
        True,
        "SoccerTrack analysis product lane is closed with live route artifacts. Advance to broader SoccerTrack lane closeout; keep detector evaluation, training, promotion, video download, and runtime mutation separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "analysis_product_ui_route_missing", "selected": primary_blocker == BLOCKER_ROUTE_MISSING, "primaryBlocker": BLOCKER_ROUTE_MISSING, "nextRecommendedNextLever": NEXT_ROUTE_IMPLEMENTATION},
            {"condition": "analysis_product_lane_closeout_gap", "selected": primary_blocker == BLOCKER_CLOSEOUT_GAP, "primaryBlocker": BLOCKER_CLOSEOUT_GAP, "nextRecommendedNextLever": NEXT_CLOSEOUT_REPAIR},
            {"condition": "analysis_product_lane_closed", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SOCCERTRACK_CLOSEOUT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Analysis Product Lane Closeout",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Analysis product lane closed: `{summary.get('analysisProductLaneClosed')}`",
            f"- Product UI route ready: `{summary.get('productUiRouteReady')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Reported events: `{summary.get('reportedEventCount')}`",
            f"- Reported frames: `{summary.get('reportedFrameCount')}`",
            f"- Candidate ready for evaluation: `{summary.get('candidateReadyForEvaluation')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Video download executed: `{summary.get('videoDownloadExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_analysis_product_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_analysis_product_lane_closeout",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    route_ready = _route_ready(inputs)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(route_ready)
    capability = _capability_matrix(route_ready, inputs)
    gaps = _remaining_gap_analysis(route_ready)
    attempts = _attempt_plan()
    source_summary = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_analysis_product_lane_closeout",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_analysis_product_ui_route_implementation",
        "analysisProductLaneClosed": goal_achieved,
        "productUiRouteReady": route_ready,
        "selectedMatchId": source_summary.get("selectedMatchId"),
        "reportedEventCount": source_summary.get("reportedEventCount"),
        "reportedFrameCount": source_summary.get("reportedFrameCount"),
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
        "analysisProductCapabilityMatrix": capability,
        "remainingGapAnalysis": gaps,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "analysis_product_lane_closeout_summary.json", summary)
    _write_json(output_root / "analysis_product_capability_matrix.json", capability)
    _write_json(output_root / "remaining_gap_analysis.json", gaps)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Close the SoccerTrack external analysis product lane from route truth.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_analysis_product_lane_closeout")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_analysis_product_lane_closeout(
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
