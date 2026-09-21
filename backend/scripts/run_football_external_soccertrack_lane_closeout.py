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
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_lane_closeout_v1"

BLOCKER_REQUIRED_EVIDENCE_MISSING = "football_external_soccertrack_lane_required_evidence_missing"
BLOCKER_PRODUCT_LANE_NOT_CLOSED = "football_external_soccertrack_analysis_product_lane_not_closed"

NEXT_BENCHMARK_HARNESS_PREP = "football_external_benchmark_harness_prep"
NEXT_EVIDENCE_REPAIR = "football_external_soccertrack_lane_closeout_evidence_repair"
NEXT_PRODUCT_LANE_CLOSEOUT = "football_external_soccertrack_analysis_product_lane_closeout"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_external_lane_closeout",
            "successCriteria": [
                "summarize the full SoccerTrack external source lane from generated truth",
                "prove Google Drive bounded fixture path, adapter, MatchBundle, product route, report, UI route, and product closeout are complete",
                "select benchmark harness prep as the next cross-source lever",
            ],
            "failureAdaptation": "If required evidence is missing, route back to the first missing evidence family.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_lane_closeout_evidence_repair",
            "successCriteria": [
                "repair closeout-only evidence indexing without modifying source artifacts",
                "preserve no training, no promotion, no candidate evaluation, no video download, and no runtime mutation",
            ],
            "failureAdaptation": "If the product lane is not closed, route back to product lane closeout.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_lane_closeout_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to missing evidence, product closeout, or benchmark harness prep.",
        },
    ]


def _required_sources() -> list[dict[str, str]]:
    return [
        {
            "stage": "google_drive_fixture_access_probe",
            "dir": "football_external_soccertrack_google_drive_fixture_access_probe_v1",
            "summary": "google_drive_fixture_access_probe_summary.json",
            "next": "football_external_soccertrack_google_drive_fixture_access_probe",
        },
        {
            "stage": "google_drive_bounded_fixture_fetch",
            "dir": "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1",
            "summary": "google_drive_bounded_fixture_fetch_summary.json",
            "next": "football_external_soccertrack_google_drive_bounded_fixture_fetch",
        },
        {
            "stage": "sample_fixture_materialization",
            "dir": "football_external_soccertrack_sample_fixture_materialization_v1",
            "summary": "soccertrack_sample_fixture_materialization_summary.json",
            "next": "football_external_soccertrack_sample_fixture_materialization",
        },
        {
            "stage": "adapter_smoke_test",
            "dir": "football_external_soccertrack_adapter_smoke_test_v1",
            "summary": "soccertrack_adapter_smoke_summary.json",
            "next": "football_external_soccertrack_adapter_smoke_test",
        },
        {
            "stage": "match_bundle_bridge_smoke",
            "dir": "football_external_soccertrack_match_bundle_bridge_smoke_v1",
            "summary": "soccertrack_match_bundle_bridge_summary.json",
            "next": "football_external_soccertrack_match_bundle_bridge_smoke",
        },
        {
            "stage": "product_route_smoke",
            "dir": "football_external_soccertrack_product_route_smoke_v1",
            "summary": "soccertrack_product_route_smoke_summary.json",
            "next": "football_external_soccertrack_product_route_smoke",
        },
        {
            "stage": "analysis_report_smoke",
            "dir": "football_external_soccertrack_analysis_report_smoke_v1",
            "summary": "soccertrack_analysis_report_smoke_summary.json",
            "next": "football_external_soccertrack_analysis_report_smoke",
        },
        {
            "stage": "analysis_product_ui_binding",
            "dir": "football_external_soccertrack_analysis_product_ui_binding_v1",
            "summary": "analysis_product_ui_binding_summary.json",
            "next": "football_external_soccertrack_analysis_product_ui_binding",
        },
        {
            "stage": "analysis_product_ui_route_implementation",
            "dir": "football_external_soccertrack_analysis_product_ui_route_implementation_v1",
            "summary": "analysis_product_ui_route_implementation_summary.json",
            "next": "football_external_soccertrack_analysis_product_ui_route_implementation",
        },
        {
            "stage": "analysis_product_lane_closeout",
            "dir": "football_external_soccertrack_analysis_product_lane_closeout_v1",
            "summary": "analysis_product_lane_closeout_summary.json",
            "next": "football_external_soccertrack_analysis_product_lane_closeout",
        },
    ]


def _load_evidence(candidate_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _required_sources():
        path = candidate_root / source["dir"] / source["summary"]
        payload = _load_json(path)
        rows.append(
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
    return rows


def _first_missing_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in evidence:
        if row.get("stage") == "analysis_product_lane_closeout" and row.get("present") is True:
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


def _selected_match_id(evidence: list[dict[str, Any]]) -> str | None:
    for stage in [
        "analysis_product_lane_closeout",
        "analysis_product_ui_route_implementation",
        "product_route_smoke",
        "match_bundle_bridge_smoke",
        "google_drive_bounded_fixture_fetch",
        "google_drive_fixture_access_probe",
    ]:
        value = _value(evidence, stage, "selectedMatchId")
        if value:
            return str(value)
    return None


def _product_lane_closed(evidence: list[dict[str, Any]]) -> bool:
    return bool(_value(evidence, "analysis_product_lane_closeout", "analysisProductLaneClosed") is True)


def _capability_matrix(evidence: list[dict[str, Any]], lane_ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_lane_capability_matrix_v1",
        "generatedAt": _utc_now_iso(),
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": _selected_match_id(evidence),
        "googleDriveFixturePathReady": lane_ready and _value(evidence, "google_drive_bounded_fixture_fetch", "downloadedFixtureFileCount", 0) > 0,
        "boundedFixtureFileCount": _value(evidence, "google_drive_bounded_fixture_fetch", "downloadedFixtureFileCount", 0),
        "materializedFixtureReady": lane_ready and bool(_value(evidence, "sample_fixture_materialization", "goalAchieved")),
        "canonicalAdapterReady": lane_ready and bool(_value(evidence, "adapter_smoke_test", "goalAchieved")),
        "matchBundleBridgeReady": lane_ready and bool(_value(evidence, "match_bundle_bridge_smoke", "matchBundleBridgeReady")),
        "matchBundleRouteReady": lane_ready and bool(_value(evidence, "product_route_smoke", "productRouteSmokePassed")),
        "analysisReportReady": lane_ready and bool(_value(evidence, "analysis_report_smoke", "analysisReportSmokePassed")),
        "analysisProductUiReady": lane_ready and bool(_value(evidence, "analysis_product_ui_binding", "productUiBindingReady")),
        "analysisProductRouteReady": lane_ready and bool(_value(evidence, "analysis_product_ui_route_implementation", "productUiRouteReady")),
        "analysisProductLaneClosed": lane_ready and _product_lane_closed(evidence),
        "reportedEventCount": _value(evidence, "analysis_product_lane_closeout", "reportedEventCount", _value(evidence, "product_route_smoke", "externalBundleEventCount", 0)),
        "reportedFrameCount": _value(evidence, "analysis_product_lane_closeout", "reportedFrameCount", _value(evidence, "product_route_smoke", "externalBundleFrameCount", 0)),
        "detectorEvaluationReady": False,
        "trainingReady": False,
        "promotionReady": False,
        "runtimeDefaultMutationReady": False,
        "videoDownloadRequiredForCurrentLane": False,
        "normalMatchStorageMutationRequiredForCurrentLane": False,
    }


def _evidence_index(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_lane_evidence_index_v1",
        "generatedAt": _utc_now_iso(),
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
        "schemaVersion": "soccertrack_lane_remaining_gap_analysis_v1",
        "generatedAt": _utc_now_iso(),
        "soccertrackLaneClosed": lane_ready,
        "remainingPrimaryGap": "benchmark_harness_not_yet_bound_to_external_sources" if lane_ready else "soccertrack_lane_required_evidence_missing",
        "remainingGaps": []
        if not lane_ready
        else [
            "bind SoccerTrack and SoccerNet external artifacts into a common benchmark harness",
            "external fixture/product route readiness is not detector evaluation readiness",
            "training, promotion, runtime-default mutation, and video download remain separate gates",
        ],
        "nextSafeLever": NEXT_BENCHMARK_HARNESS_PREP if lane_ready else NEXT_EVIDENCE_REPAIR,
    }


def _classify(evidence: list[dict[str, Any]]) -> tuple[str | None, str, bool, bool, str]:
    missing = _first_missing_evidence(evidence)
    if missing is not None:
        return (
            BLOCKER_REQUIRED_EVIDENCE_MISSING,
            str(missing.get("nextIfMissing") or NEXT_EVIDENCE_REPAIR),
            False,
            False,
            f"SoccerTrack lane closeout is missing required generated truth for {missing.get('stage')}.",
        )
    if not _product_lane_closed(evidence):
        return (
            BLOCKER_PRODUCT_LANE_NOT_CLOSED,
            NEXT_PRODUCT_LANE_CLOSEOUT,
            False,
            False,
            "SoccerTrack analysis product lane is not closed yet; rerun product lane closeout before broader lane closeout.",
        )
    return (
        None,
        NEXT_BENCHMARK_HARNESS_PREP,
        True,
        True,
        "SoccerTrack external data/product lane is closed from generated truth. Advance to external benchmark harness prep; do not treat this as detector evaluation, training, promotion, or runtime mutation readiness.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool, next_lever: str) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "required_evidence_missing", "selected": primary_blocker == BLOCKER_REQUIRED_EVIDENCE_MISSING, "primaryBlocker": BLOCKER_REQUIRED_EVIDENCE_MISSING, "nextRecommendedNextLever": next_lever},
            {"condition": "analysis_product_lane_not_closed", "selected": primary_blocker == BLOCKER_PRODUCT_LANE_NOT_CLOSED, "primaryBlocker": BLOCKER_PRODUCT_LANE_NOT_CLOSED, "nextRecommendedNextLever": NEXT_PRODUCT_LANE_CLOSEOUT},
            {"condition": "benchmark_harness_prep_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BENCHMARK_HARNESS_PREP},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Lane Closeout",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- SoccerTrack lane closed: `{summary.get('soccertrackLaneClosed')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Downloaded fixture files: `{summary.get('downloadedFixtureFileCount')}`",
            f"- Reported events: `{summary.get('reportedEventCount')}`",
            f"- Reported frames: `{summary.get('reportedFrameCount')}`",
            f"- Product route ready: `{summary.get('productRouteReady')}`",
            f"- Analysis product lane closed: `{summary.get('analysisProductLaneClosed')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Video download executed: `{summary.get('videoDownloadExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_external_lane_closeout",
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
        "batchName": "football_external_soccertrack_lane_closeout",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "soccertrackLaneClosed": goal_achieved,
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": _selected_match_id(evidence),
        "downloadedFixtureFileCount": _value(evidence, "google_drive_bounded_fixture_fetch", "downloadedFixtureFileCount", 0),
        "reportedEventCount": capability["reportedEventCount"],
        "reportedFrameCount": capability["reportedFrameCount"],
        "productRouteReady": capability["matchBundleRouteReady"],
        "analysisProductLaneClosed": capability["analysisProductLaneClosed"],
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
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved, next_lever)
    batch_outcome = {
        "summary": summary,
        "soccertrackLaneCapabilityMatrix": capability,
        "soccertrackLaneEvidenceIndex": evidence_index,
        "remainingGapAnalysis": gaps,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_lane_closeout_summary.json", summary)
    _write_json(output_root / "soccertrack_lane_capability_matrix.json", capability)
    _write_json(output_root / "soccertrack_lane_evidence_index.json", evidence_index)
    _write_json(output_root / "remaining_gap_analysis.json", gaps)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Close the SoccerTrack external data/product lane from generated truth.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_external_lane_closeout")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_lane_closeout(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
