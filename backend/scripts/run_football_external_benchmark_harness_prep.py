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
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_harness_prep_v1"

BLOCKER_SOURCE_LANE_MISSING = "football_external_benchmark_harness_source_lane_missing"
BLOCKER_SOURCE_CONTRACT_GAP = "football_external_benchmark_harness_source_contract_gap"

NEXT_SOCCERTRACK_CLOSEOUT = "football_external_soccertrack_lane_closeout"
NEXT_SOCCERNET_ANALYSIS_CLOSEOUT = "football_external_soccernet_analysis_product_lane_closeout"
NEXT_SOCCERNET_EVENT_CLOSEOUT = "football_external_soccernet_event_lane_closeout"
NEXT_SOURCE_CONTRACT_REPAIR = "football_external_benchmark_harness_source_contract_repair"
NEXT_HARNESS_SMOKE = "football_external_benchmark_harness_smoke"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_harness_prep",
            "successCriteria": [
                "load closed SoccerTrack and SoccerNet generated truth",
                "write a cross-source benchmark source manifest",
                "keep detector evaluation, training, promotion, video download, normal match storage mutation, and runtime-default mutation false",
            ],
            "failureAdaptation": "If a source lane is missing, route back to the missing lane closeout.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_harness_source_contract_repair",
            "successCriteria": [
                "repair source manifest fields without modifying source artifacts",
                "keep benchmark execution blocked until harness smoke",
            ],
            "failureAdaptation": "If source lanes are complete but contract fields are inconsistent, write repair truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_harness_prep_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to missing source lane, source contract repair, or harness smoke.",
        },
    ]


def _source_specs() -> list[dict[str, str]]:
    return [
        {
            "sourceId": "soccernet_analysis",
            "sourceFamily": "soccernet",
            "summaryPath": "football_external_soccernet_analysis_product_lane_closeout_v1/analysis_product_lane_closeout_summary.json",
            "readyFlag": "analysisProductLaneClosed",
            "nextIfMissing": NEXT_SOCCERNET_ANALYSIS_CLOSEOUT,
        },
        {
            "sourceId": "soccernet_events",
            "sourceFamily": "soccernet",
            "summaryPath": "football_external_soccernet_event_lane_closeout_v1/soccernet_event_lane_closeout_summary.json",
            "readyFlag": "eventOnlyLaneClosed",
            "nextIfMissing": NEXT_SOCCERNET_EVENT_CLOSEOUT,
        },
        {
            "sourceId": "soccertrack",
            "sourceFamily": "soccertrack",
            "summaryPath": "football_external_soccertrack_lane_closeout_v1/soccertrack_lane_closeout_summary.json",
            "readyFlag": "soccertrackLaneClosed",
            "nextIfMissing": NEXT_SOCCERTRACK_CLOSEOUT,
        },
    ]


def _load_sources(candidate_root: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for spec in _source_specs():
        path = candidate_root / spec["summaryPath"]
        payload = _load_json(path)
        ready = bool(
            isinstance(payload, dict)
            and payload.get("goalAchieved") is True
            and payload.get("primaryBlocker") is None
            and payload.get(spec["readyFlag"]) is True
            and payload.get("trainingExecuted") is False
            and payload.get("promotionReady") is False
            and payload.get("candidateReadyForEvaluation") is False
            and payload.get("runtimeDefaultMutationExecuted") is False
        )
        sources.append(
            {
                **spec,
                "summaryPathResolved": str(path),
                "present": payload is not None,
                "ready": ready,
                "payload": payload or {},
            }
        )
    return sources


def _first_unready_source(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    for source in sources:
        if source.get("ready") is not True:
            return source
    return None


def _source_manifest(sources: list[dict[str, Any]]) -> dict[str, Any]:
    soccernet_analysis = next(row for row in sources if row["sourceId"] == "soccernet_analysis")
    soccernet_events = next(row for row in sources if row["sourceId"] == "soccernet_events")
    soccertrack = next(row for row in sources if row["sourceId"] == "soccertrack")
    return {
        "schemaVersion": "football_external_benchmark_source_manifest_v1",
        "generatedAt": utc_now_iso(),
        "sources": [
            {
                "sourceId": "soccernet",
                "sourceDataset": "soccernet_external",
                "sourceLanes": ["analysis_product", "event_lane"],
                "analysisFrameCount": soccernet_analysis["payload"].get("reportedFrameCount"),
                "analysisSegmentCount": soccernet_analysis["payload"].get("segmentCount"),
                "eventCount": soccernet_events["payload"].get("eventCount"),
                "readyForHarnessSmoke": soccernet_analysis["ready"] and soccernet_events["ready"],
                "summaryPaths": [
                    soccernet_analysis["summaryPathResolved"],
                    soccernet_events["summaryPathResolved"],
                ],
            },
            {
                "sourceId": "soccertrack",
                "sourceDataset": "soccertrack_v2",
                "selectedMatchId": soccertrack["payload"].get("selectedMatchId"),
                "downloadedFixtureFileCount": soccertrack["payload"].get("downloadedFixtureFileCount"),
                "reportedEventCount": soccertrack["payload"].get("reportedEventCount"),
                "reportedFrameCount": soccertrack["payload"].get("reportedFrameCount"),
                "readyForHarnessSmoke": soccertrack["ready"],
                "summaryPaths": [soccertrack["summaryPathResolved"]],
            },
        ],
    }


def _legacy_resource_inventory(manifest: dict[str, Any]) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        resources.append(
            {
                "resourceId": source["sourceId"],
                "resourceName": str(source["sourceId"]).title(),
                "accessClass": "generated_local_artifact",
                "coveredStages": ["possession_event_semantics", "tactical_reporting"],
                "executionStatus": "generated_truth_ready",
                "benchmarkSmokeUseAllowed": True,
                "downloadAllowedByThisBatch": False,
                "trainingUseAllowed": False,
            }
        )
    return {
        "schemaVersion": "football_external_benchmark_resource_inventory_v2",
        "generatedAt": utc_now_iso(),
        "resourceCount": len(resources),
        "resources": resources,
        "licensePolicy": "This prep consumes existing generated local artifacts only; no new external download is approved here.",
    }


def _adapter_contract() -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_adapter_contract_v2",
        "externalBenchmarkExecutionReady": False,
        "datasetDownloadExecuted": False,
        "adapterImplementationStatus": "contract_prep_only",
        "schemas": {
            "ExternalSourceSummary": {
                "requiredFields": ["sourceId", "sourceDataset", "summaryPaths", "readyForHarnessSmoke"],
            },
            "ExternalBenchmarkSmokeCase": {
                "requiredFields": ["sourceId", "caseId", "artifactPath", "expectedMetricFamilies"],
            },
        },
    }


def _stage_gate_contract() -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_stage_gate_contract_v2",
        "requiredStageCoverage": [
            "source_manifest_load",
            "artifact_presence_check",
            "schema_version_check",
            "metric_family_mapping",
            "no_training_or_runtime_mutation",
        ],
    }


def _capability_matrix(manifest: dict[str, Any], ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "crossSourceHarnessReady": ready,
        "sourceCount": len(manifest["sources"]),
        "sourceIds": [row["sourceId"] for row in manifest["sources"]],
        "soccernetReady": any(row["sourceId"] == "soccernet" and row["readyForHarnessSmoke"] for row in manifest["sources"]),
        "soccertrackReady": any(row["sourceId"] == "soccertrack" and row["readyForHarnessSmoke"] for row in manifest["sources"]),
        "detectorEvaluationReady": False,
        "trainingReady": False,
        "promotionReady": False,
        "runtimeDefaultMutationReady": False,
        "videoDownloadReady": False,
    }


def _remaining_gap_analysis(ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_remaining_gap_analysis_v1",
        "generatedAt": utc_now_iso(),
        "remainingPrimaryGap": "external_benchmark_harness_smoke_not_run" if ready else "external_source_lane_missing",
        "remainingGaps": []
        if not ready
        else [
            "run a harness smoke that loads both external source manifests and emits comparable metric-family placeholders",
            "do not treat harness prep as detector evaluation readiness",
            "training, promotion, video download, normal match storage mutation, and runtime-default mutation remain separate gates",
        ],
    }


def _classify(sources: list[dict[str, Any]]) -> tuple[str | None, str, bool, bool, str]:
    unready = _first_unready_source(sources)
    if unready is not None:
        return (
            BLOCKER_SOURCE_LANE_MISSING,
            str(unready["nextIfMissing"]),
            False,
            False,
            f"External benchmark harness prep requires source lane {unready['sourceId']} to be closed first.",
        )
    manifest = _source_manifest(sources)
    if len(manifest["sources"]) < 2:
        return (
            BLOCKER_SOURCE_CONTRACT_GAP,
            NEXT_SOURCE_CONTRACT_REPAIR,
            False,
            True,
            "External benchmark harness source manifest has too few sources.",
        )
    return (
        None,
        NEXT_HARNESS_SMOKE,
        True,
        True,
        "External benchmark harness prep passed for SoccerNet and SoccerTrack generated artifacts. Advance to harness smoke; no detector evaluation, training, promotion, video download, normal match storage mutation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool, next_lever: str) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "source_lane_missing", "selected": primary_blocker == BLOCKER_SOURCE_LANE_MISSING, "primaryBlocker": BLOCKER_SOURCE_LANE_MISSING, "nextRecommendedNextLever": next_lever},
            {"condition": "source_contract_gap", "selected": primary_blocker == BLOCKER_SOURCE_CONTRACT_GAP, "primaryBlocker": BLOCKER_SOURCE_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_SOURCE_CONTRACT_REPAIR},
            {"condition": "external_benchmark_harness_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_HARNESS_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Harness Prep",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Benchmark harness prep ready: `{summary.get('benchmarkHarnessPrepReady')}`",
            f"- External source count: `{summary.get('externalSourceCount')}`",
            f"- SoccerNet ready: `{summary.get('soccernetReady')}`",
            f"- SoccerTrack ready: `{summary.get('soccertrackReady')}`",
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


def run_football_external_benchmark_harness_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_harness_prep",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(candidate_root, output_dir_name)

    sources = _load_sources(candidate_root)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(sources)
    manifest = _source_manifest(sources)
    capability = _capability_matrix(manifest, goal_achieved)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_harness_prep",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "benchmarkHarnessPrepReady": goal_achieved,
        "benchmarkHarnessContractReady": goal_achieved,
        "datasetAccessReviewReady": False,
        "externalBenchmarkExecutionReady": False,
        "externalSourceCount": len(manifest["sources"]),
        "soccernetReady": capability["soccernetReady"],
        "soccertrackReady": capability["soccertrackReady"],
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
        "datasetDownloadExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    inventory = _legacy_resource_inventory(manifest)
    adapter_contract = _adapter_contract()
    stage_gate = _stage_gate_contract()
    gaps = _remaining_gap_analysis(goal_achieved)
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved, next_lever)
    batch_outcome = {
        "summary": summary,
        "externalBenchmarkSourceManifest": manifest,
        "externalBenchmarkCapabilityMatrix": capability,
        "remainingGapAnalysis": gaps,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "external_benchmark_harness_summary.json", summary)
    _write_json(output_root / "external_benchmark_source_manifest.json", manifest)
    _write_json(output_root / "external_benchmark_capability_matrix.json", capability)
    _write_json(output_root / "benchmark_resource_inventory.json", inventory)
    _write_json(output_root / "dataset_adapter_contract.json", adapter_contract)
    _write_json(output_root / "stage_gate_contract.json", stage_gate)
    _write_json(output_root / "benchmark_split_plan.json", {"schemaVersion": "football_external_benchmark_split_plan_v2", "executionReady": False, "splitPolicy": "source_grouped_no_cross_source_leakage"})
    _write_json(output_root / "remaining_gap_analysis.json", gaps)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "benchmark_harness_readiness_audit.json", batch_outcome)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a cross-source external benchmark harness from generated truth.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="external_benchmark_harness_prep")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_benchmark_harness_prep(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
