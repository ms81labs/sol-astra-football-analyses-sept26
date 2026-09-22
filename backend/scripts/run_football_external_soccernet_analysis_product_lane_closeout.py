from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SOURCE_DIR_NAME = "football_external_soccernet_analysis_product_ui_route_implementation_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_analysis_product_lane_closeout_v1"

BLOCKER_ROUTE_MISSING = "football_external_soccernet_analysis_product_ui_route_missing"
BLOCKER_CLOSEOUT_GAP = "football_external_soccernet_analysis_product_lane_closeout_gap"

NEXT_ROUTE_IMPLEMENTATION = "football_external_soccernet_analysis_product_ui_route_implementation"
NEXT_CLOSEOUT_REPAIR = "football_external_soccernet_analysis_product_route_closeout_repair"
NEXT_SAFE_SOURCE_ADAPTER_SMOKE = "football_external_safe_source_adapter_smoke_test"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_analysis_product_lane_closeout",
            "successCriteria": [
                "close the full-analysis product lane from route implementation truth",
                "write a capability matrix and remaining-gap analysis",
                "select the next safe external source adapter lane",
            ],
            "failureAdaptation": "If route implementation truth is incomplete, route back to route implementation.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_analysis_product_route_closeout_repair",
            "successCriteria": [
                "repair missing closeout-only fields without modifying route artifacts",
                "keep detector evaluation, training, promotion, and runtime mutation blocked",
            ],
            "failureAdaptation": "If the route itself is unsafe, route back to route implementation.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_analysis_product_lane_blocker_summary",
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
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productUiRouteReady") is True
        and summary.get("apiRoutePath") == "/api/external/soccernet/full-analysis"
        and summary.get("htmlRoutePath") == "/external/soccernet/full-analysis"
        and int(summary.get("reportedFrameCount") or 0) > 0
        and int(summary.get("segmentCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and audit.get("apiRouteSmokePassed") is True
        and audit.get("htmlRouteSmokePassed") is True
        and isinstance(fixture, dict)
        and fixture.get("statusCode") == 200
        and readiness.get("candidateEvaluationReady") is False
        and readiness.get("trainingReady") is False
        and readiness.get("promotionReady") is False
        and readiness.get("runtimeDefaultMutationReady") is False
    )


def _capability_matrix(route_ready: bool, inputs: dict[str, Any]) -> dict[str, Any]:
    summary = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    return {
        "schemaVersion": "soccernet_analysis_product_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "fullVideoAnalysisProductReady": route_ready,
        "routeCapabilityReady": route_ready,
        "apiRoutePath": summary.get("apiRoutePath"),
        "htmlRoutePath": summary.get("htmlRoutePath"),
        "reportedFrameCount": summary.get("reportedFrameCount"),
        "segmentCount": summary.get("segmentCount"),
        "detectorEvaluationReady": False,
        "trainingReady": False,
        "promotionReady": False,
        "runtimeDefaultMutationReady": False,
        "archiveDownloadRequiredForCurrentProductRoute": False,
        "video720pMemberDownloadRequiredForCurrentProductRoute": False,
    }


def _remaining_gap_analysis(route_ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "soccernet_analysis_product_remaining_gap_analysis_v1",
        "generatedAt": utc_now_iso(),
        "analysisProductRouteClosed": route_ready,
        "remainingPrimaryGap": None if not route_ready else "external_safe_source_adapter_smoke_not_currently_closed",
        "remainingGaps": [] if not route_ready else [
            "safe external source adapter smoke lane still needs current closeout",
            "full benchmark execution remains separate from product-route readiness",
        ],
        "nextSafeLever": NEXT_ROUTE_IMPLEMENTATION if not route_ready else NEXT_SAFE_SOURCE_ADAPTER_SMOKE,
    }


def _classify(route_ready: bool) -> tuple[str | None, str, bool, str]:
    if not route_ready:
        return (
            BLOCKER_ROUTE_MISSING,
            NEXT_ROUTE_IMPLEMENTATION,
            False,
            "SoccerNet analysis product route implementation is missing or unsafe; rerun route implementation before lane closeout.",
        )
    return (
        None,
        NEXT_SAFE_SOURCE_ADAPTER_SMOKE,
        True,
        "SoccerNet full-analysis product lane is closed with live route artifacts. Continue with safe external source adapter smoke work; keep detector evaluation, training, promotion, and runtime mutation separate.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "analysis_product_ui_route_missing", "selected": primary_blocker == BLOCKER_ROUTE_MISSING, "primaryBlocker": BLOCKER_ROUTE_MISSING, "nextRecommendedNextLever": NEXT_ROUTE_IMPLEMENTATION},
            {"condition": "analysis_product_lane_closeout_gap", "selected": primary_blocker == BLOCKER_CLOSEOUT_GAP, "primaryBlocker": BLOCKER_CLOSEOUT_GAP, "nextRecommendedNextLever": NEXT_CLOSEOUT_REPAIR},
            {"condition": "analysis_product_lane_closed", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SAFE_SOURCE_ADAPTER_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Analysis Product Lane Closeout",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Analysis product lane closed: `{summary.get('analysisProductLaneClosed')}`",
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


def run_football_external_soccernet_analysis_product_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    source_dir_name: str = DEFAULT_SOURCE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_analysis_product_lane_closeout",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, source_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    route_ready = _route_ready(inputs)
    primary_blocker, next_lever, goal_achieved, english = _classify(route_ready)
    capability = _capability_matrix(route_ready, inputs)
    gaps = _remaining_gap_analysis(route_ready)
    attempts = _attempt_plan()
    source_summary = inputs.get("summary") if isinstance(inputs.get("summary"), dict) else {}
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_analysis_product_lane_closeout",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_analysis_product_ui_route_implementation",
        "analysisProductLaneClosed": goal_achieved,
        "productUiRouteReady": route_ready,
        "reportedFrameCount": source_summary.get("reportedFrameCount"),
        "segmentCount": source_summary.get("segmentCount"),
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--source-dir-name", default=DEFAULT_SOURCE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_analysis_product_lane_closeout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_analysis_product_lane_closeout(
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
