from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_lane_closeout_v1"

BLOCKER_REQUIRED_EVIDENCE_MISSING = "football_external_benchmark_lane_required_evidence_missing"
BLOCKER_SOURCE_LANE_NOT_CLOSED = "football_external_benchmark_source_lane_not_closed"
BLOCKER_PRODUCT_ROUTE_NOT_READY = "football_external_benchmark_product_ui_route_not_ready"

NEXT_ROUTE_IMPLEMENTATION = "football_external_benchmark_product_ui_route_implementation"
NEXT_EVIDENCE_REPAIR = "football_external_benchmark_closeout_evidence_repair"
NEXT_OPERATIONALIZATION_PLAN = "football_external_benchmark_operationalization_plan"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_lane_closeout",
            "successCriteria": [
                "summarize the closed SoccerNet and SoccerTrack source lanes",
                "prove the benchmark harness, bounded execution smoke, report, UI binding, and UI route chain are complete",
                "select benchmark operationalization planning as the next safe lever",
            ],
            "failureAdaptation": "If required evidence is missing, route back to the first missing evidence family.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_closeout_evidence_repair",
            "successCriteria": [
                "repair closeout-only evidence indexing without modifying source truth",
                "preserve no detector evaluation, no training, no promotion, no video/data download, no normal match storage mutation, and no runtime mutation",
            ],
            "failureAdaptation": "If a source lane is not closed, route back to the specific source lane closeout.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_closeout_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to missing evidence, route implementation, source lane closeout, or operationalization planning.",
        },
    ]


def _required_sources() -> list[dict[str, str]]:
    return [
        {
            "stage": "soccernet_analysis_product_lane_closeout",
            "dir": "football_external_soccernet_analysis_product_lane_closeout_v1",
            "summary": "analysis_product_lane_closeout_summary.json",
            "next": "football_external_soccernet_analysis_product_lane_closeout",
        },
        {
            "stage": "soccertrack_lane_closeout",
            "dir": "football_external_soccertrack_lane_closeout_v1",
            "summary": "soccertrack_lane_closeout_summary.json",
            "next": "football_external_soccertrack_lane_closeout",
        },
        {
            "stage": "benchmark_harness_prep",
            "dir": "football_external_benchmark_harness_prep_v1",
            "summary": "external_benchmark_harness_summary.json",
            "next": "football_external_benchmark_harness_prep",
        },
        {
            "stage": "benchmark_harness_smoke",
            "dir": "football_external_benchmark_harness_smoke_v1",
            "summary": "external_benchmark_smoke_summary.json",
            "next": "football_external_benchmark_harness_smoke",
        },
        {
            "stage": "benchmark_execution_approval",
            "dir": "football_external_benchmark_execution_approval_v1",
            "summary": "external_benchmark_execution_approval_summary.json",
            "next": "football_external_benchmark_execution_approval",
        },
        {
            "stage": "benchmark_bounded_execution_smoke",
            "dir": "football_external_benchmark_bounded_execution_smoke_v1",
            "summary": "external_benchmark_bounded_execution_summary.json",
            "next": "football_external_benchmark_bounded_execution_smoke",
        },
        {
            "stage": "benchmark_report_smoke",
            "dir": "football_external_benchmark_report_smoke_v1",
            "summary": "external_benchmark_report_smoke_summary.json",
            "next": "football_external_benchmark_report_smoke",
        },
        {
            "stage": "benchmark_product_ui_binding",
            "dir": "football_external_benchmark_product_ui_binding_v1",
            "summary": "external_benchmark_product_ui_binding_summary.json",
            "next": "football_external_benchmark_product_ui_binding",
        },
        {
            "stage": "benchmark_product_ui_route_implementation",
            "dir": "football_external_benchmark_product_ui_route_implementation_v1",
            "summary": "external_benchmark_product_ui_route_implementation_summary.json",
            "next": NEXT_ROUTE_IMPLEMENTATION,
        },
    ]


def _load_evidence(candidate_root: Path) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for source in _required_sources():
        path = candidate_root / source["dir"] / source["summary"]
        payload = _load_json(path)
        evidence.append(
            {
                "stage": source["stage"],
                "summaryPath": str(path),
                "present": payload is not None,
                "goalAchieved": payload.get("goalAchieved") is True if isinstance(payload, dict) else False,
                "primaryBlocker": payload.get("primaryBlocker") if isinstance(payload, dict) else "missing_summary",
                "nextIfMissing": source["next"],
                "payload": payload or {},
            }
        )
    return evidence


def _first_missing_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in evidence:
        if row.get("stage") in {"soccernet_analysis_product_lane_closeout", "soccertrack_lane_closeout"} and row.get("present") is True:
            continue
        if row.get("present") is not True or row.get("goalAchieved") is not True or row.get("primaryBlocker") is not None:
            return row
    return None


def _value(evidence: list[dict[str, Any]], stage: str, key: str, default: Any = None) -> Any:
    for row in evidence:
        if row.get("stage") == stage:
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            return payload.get(key, default)
    return default


def _all_source_lanes_closed(evidence: list[dict[str, Any]]) -> bool:
    return bool(
        _value(evidence, "soccernet_analysis_product_lane_closeout", "analysisProductLaneClosed") is True
        and _value(evidence, "soccertrack_lane_closeout", "soccertrackLaneClosed") is True
    )


def _product_route_ready(evidence: list[dict[str, Any]]) -> bool:
    return bool(_value(evidence, "benchmark_product_ui_route_implementation", "productUiRouteReady") is True)


def _source_lane_next(evidence: list[dict[str, Any]]) -> str:
    if _value(evidence, "soccernet_analysis_product_lane_closeout", "analysisProductLaneClosed") is not True:
        return "football_external_soccernet_analysis_product_lane_closeout"
    if _value(evidence, "soccertrack_lane_closeout", "soccertrackLaneClosed") is not True:
        return "football_external_soccertrack_lane_closeout"
    return NEXT_EVIDENCE_REPAIR


def _capability_matrix(evidence: list[dict[str, Any]], lane_ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "externalBenchmarkLaneClosed": lane_ready,
        "externalSourceCount": int(_value(evidence, "benchmark_product_ui_route_implementation", "sourceCount", _value(evidence, "benchmark_harness_prep", "externalSourceCount", 0)) or 0),
        "soccernetAnalysisProductLaneClosed": _value(evidence, "soccernet_analysis_product_lane_closeout", "analysisProductLaneClosed") is True,
        "soccernetReportedFrameCount": int(_value(evidence, "soccernet_analysis_product_lane_closeout", "reportedFrameCount", 0) or 0),
        "soccertrackLaneClosed": _value(evidence, "soccertrack_lane_closeout", "soccertrackLaneClosed") is True,
        "soccertrackReportedEventCount": int(_value(evidence, "soccertrack_lane_closeout", "reportedEventCount", 0) or 0),
        "soccertrackReportedFrameCount": int(_value(evidence, "soccertrack_lane_closeout", "reportedFrameCount", 0) or 0),
        "benchmarkHarnessPrepReady": _value(evidence, "benchmark_harness_prep", "benchmarkHarnessPrepReady") is True,
        "benchmarkHarnessSmokePassed": _value(evidence, "benchmark_harness_smoke", "externalBenchmarkHarnessSmokePassed") is True,
        "benchmarkExecutionApproved": _value(evidence, "benchmark_execution_approval", "externalBenchmarkExecutionApproved") is True,
        "boundedBenchmarkExecutionSmokePassed": _value(evidence, "benchmark_bounded_execution_smoke", "boundedBenchmarkExecutionSmokePassed") is True,
        "externalBenchmarkReportSmokePassed": _value(evidence, "benchmark_report_smoke", "externalBenchmarkReportSmokePassed") is True,
        "benchmarkProductUiBindingReady": _value(evidence, "benchmark_product_ui_binding", "productUiBindingReady") is True,
        "benchmarkProductUiRouteReady": _product_route_ready(evidence),
        "apiRoutePath": _value(evidence, "benchmark_product_ui_route_implementation", "apiRoutePath"),
        "htmlRoutePath": _value(evidence, "benchmark_product_ui_route_implementation", "htmlRoutePath"),
        "detectorEvaluationReady": False,
        "candidateEvaluationReady": False,
        "trainingReady": False,
        "promotionReady": False,
        "runtimeDefaultMutationReady": False,
        "videoDownloadRequiredForCurrentLane": False,
        "normalMatchStorageMutationRequiredForCurrentLane": False,
    }


def _evidence_index(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_evidence_index_v1",
        "generatedAt": utc_now_iso(),
        "requiredEvidence": [
            {
                "stage": row["stage"],
                "summaryPath": row["summaryPath"],
                "present": row["present"],
                "goalAchieved": row["goalAchieved"],
                "primaryBlocker": row["primaryBlocker"],
            }
            for row in evidence
        ],
    }


def _remaining_gap_analysis(lane_ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "external_benchmark_remaining_gap_analysis_v1",
        "generatedAt": utc_now_iso(),
        "externalBenchmarkLaneClosed": lane_ready,
        "remainingPrimaryGap": "external_benchmark_operationalization_not_yet_planned" if lane_ready else "external_benchmark_lane_required_evidence_missing",
        "remainingGaps": []
        if not lane_ready
        else [
            "turn benchmark harness smoke into an operational product decision path",
            "benchmark reports are generated truth smoke, not detector candidate evaluation",
            "normal match storage mutation, training, promotion, runtime-default mutation, and full data/video download remain separate gates",
        ],
        "nextSafeLever": NEXT_OPERATIONALIZATION_PLAN if lane_ready else NEXT_EVIDENCE_REPAIR,
    }


def _classify(evidence: list[dict[str, Any]]) -> tuple[str | None, str, bool, bool, str]:
    missing = _first_missing_evidence(evidence)
    if missing is not None:
        return (
            BLOCKER_REQUIRED_EVIDENCE_MISSING,
            str(missing.get("nextIfMissing") or NEXT_EVIDENCE_REPAIR),
            False,
            False,
            f"External benchmark lane closeout is missing required generated truth for {missing.get('stage')}.",
        )
    if not _all_source_lanes_closed(evidence):
        return (
            BLOCKER_SOURCE_LANE_NOT_CLOSED,
            _source_lane_next(evidence),
            False,
            False,
            "External benchmark source lanes are not all closed; close each source lane before benchmark lane closeout.",
        )
    if not _product_route_ready(evidence):
        return (
            BLOCKER_PRODUCT_ROUTE_NOT_READY,
            NEXT_ROUTE_IMPLEMENTATION,
            False,
            False,
            "External benchmark product UI route is not ready; implement route before benchmark lane closeout.",
        )
    return (
        None,
        NEXT_OPERATIONALIZATION_PLAN,
        True,
        True,
        "External benchmark lane is closed from generated truth. Advance to operationalization planning; do not treat this as detector evaluation, training, promotion, or runtime mutation readiness.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool, next_lever: str) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "required_evidence_missing", "selected": primary_blocker == BLOCKER_REQUIRED_EVIDENCE_MISSING, "primaryBlocker": BLOCKER_REQUIRED_EVIDENCE_MISSING, "nextRecommendedNextLever": next_lever},
            {"condition": "source_lane_not_closed", "selected": primary_blocker == BLOCKER_SOURCE_LANE_NOT_CLOSED, "primaryBlocker": BLOCKER_SOURCE_LANE_NOT_CLOSED, "nextRecommendedNextLever": next_lever},
            {"condition": "product_route_not_ready", "selected": primary_blocker == BLOCKER_PRODUCT_ROUTE_NOT_READY, "primaryBlocker": BLOCKER_PRODUCT_ROUTE_NOT_READY, "nextRecommendedNextLever": NEXT_ROUTE_IMPLEMENTATION},
            {"condition": "external_benchmark_operationalization_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_OPERATIONALIZATION_PLAN},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Lane Closeout",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- External benchmark lane closed: `{summary.get('externalBenchmarkLaneClosed')}`",
            f"- External source count: `{summary.get('externalSourceCount')}`",
            f"- Benchmark product UI route ready: `{summary.get('benchmarkProductUiRouteReady')}`",
            f"- API route: `{summary.get('apiRoutePath')}`",
            f"- HTML route: `{summary.get('htmlRoutePath')}`",
            f"- Detector evaluation executed: `{summary.get('detectorEvaluationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_lane_closeout",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(candidate_root, output_dir_name)

    evidence = _load_evidence(candidate_root)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(evidence)
    capability = _capability_matrix(evidence, goal_achieved)
    evidence_index = _evidence_index(evidence)
    gaps = _remaining_gap_analysis(goal_achieved)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_lane_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "externalBenchmarkLaneClosed": goal_achieved,
        "externalSourceCount": capability["externalSourceCount"],
        "soccernetAnalysisProductLaneClosed": capability["soccernetAnalysisProductLaneClosed"],
        "soccertrackLaneClosed": capability["soccertrackLaneClosed"],
        "benchmarkProductUiRouteReady": capability["benchmarkProductUiRouteReady"],
        "apiRoutePath": capability["apiRoutePath"],
        "htmlRoutePath": capability["htmlRoutePath"],
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
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved, next_lever)
    batch_outcome = {
        "summary": summary,
        "externalBenchmarkCapabilityMatrix": capability,
        "externalBenchmarkEvidenceIndex": evidence_index,
        "remainingGapAnalysis": gaps,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "external_benchmark_lane_closeout_summary.json", summary)
    _write_json(output_root / "external_benchmark_capability_matrix.json", capability)
    _write_json(output_root / "external_benchmark_evidence_index.json", evidence_index)
    _write_json(output_root / "remaining_gap_analysis.json", gaps)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Close the external benchmark lane from generated truth.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="external_benchmark_lane_closeout")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_benchmark_lane_closeout(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
