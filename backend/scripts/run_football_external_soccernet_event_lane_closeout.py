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
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_event_lane_closeout_v1"

BLOCKER_REPORT_SMOKE_MISSING = "football_external_soccernet_event_report_smoke_missing"
BLOCKER_ARTIFACT_INVENTORY_GAP = "football_external_soccernet_event_lane_artifact_inventory_gap"

NEXT_REPORT_SMOKE = "football_external_soccernet_event_report_smoke"
NEXT_ARTIFACT_REPAIR = "football_external_soccernet_event_lane_artifact_inventory_repair"
NEXT_PRODUCT_INTEGRATION = "football_external_soccernet_event_report_product_integration"

REQUIRED_ARTIFACTS: tuple[dict[str, str], ...] = (
    {
        "stageId": "split_archive_access_review",
        "batchName": "football_external_soccernet_split_archive_access_review",
        "path": "football_external_soccernet_split_archive_access_review_v1/split_archive_access_review_summary.json",
    },
    {
        "stageId": "split_archive_size_probe",
        "batchName": "football_external_soccernet_split_archive_size_probe",
        "path": "football_external_soccernet_split_archive_size_probe_v1/split_archive_size_probe_summary.json",
    },
    {
        "stageId": "split_archive_range_index_probe",
        "batchName": "football_external_soccernet_split_archive_range_index_probe",
        "path": "football_external_soccernet_split_archive_range_index_probe_v1/split_archive_range_index_probe_summary.json",
    },
    {
        "stageId": "zip_label_member_extract",
        "batchName": "football_external_soccernet_zip_label_member_extract",
        "path": "football_external_soccernet_zip_label_member_extract_v1/zip_label_member_extract_summary.json",
    },
    {
        "stageId": "label_schema_ingestion_probe",
        "batchName": "football_external_soccernet_label_schema_ingestion_probe",
        "path": "football_external_soccernet_label_schema_ingestion_probe_v1/soccernet_label_schema_ingestion_summary.json",
    },
    {
        "stageId": "event_adapter_fixture_materialization",
        "batchName": "football_external_soccernet_event_adapter_fixture_materialization",
        "path": "football_external_soccernet_event_adapter_fixture_materialization_v1/soccernet_event_fixture_materialization_summary.json",
    },
    {
        "stageId": "event_adapter_smoke_test",
        "batchName": "football_external_soccernet_event_adapter_smoke_test",
        "path": "football_external_soccernet_event_adapter_smoke_test_v1/soccernet_event_adapter_smoke_summary.json",
    },
    {
        "stageId": "benchmark_adapter_contract_prep",
        "batchName": "football_external_soccernet_benchmark_adapter_contract_prep",
        "path": "football_external_soccernet_benchmark_adapter_contract_prep_v1/soccernet_benchmark_adapter_contract_prep_summary.json",
    },
    {
        "stageId": "event_benchmark_smoke",
        "batchName": "football_external_soccernet_event_benchmark_smoke",
        "path": "football_external_soccernet_event_benchmark_smoke_v1/soccernet_event_benchmark_smoke_summary.json",
    },
    {
        "stageId": "event_report_contract_prep",
        "batchName": "football_external_soccernet_event_report_contract_prep",
        "path": "football_external_soccernet_event_report_contract_prep_v1/soccernet_event_report_contract_prep_summary.json",
    },
    {
        "stageId": "event_report_smoke",
        "batchName": "football_external_soccernet_event_report_smoke",
        "path": "football_external_soccernet_event_report_smoke_v1/soccernet_event_report_smoke_summary.json",
    },
)



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_event_lane_artifact_inventory",
            "successCriteria": [
                "inventory all generated SoccerNet event-only lane truth artifacts",
                "classify proven event-report capability versus unproven video-analysis capability",
                "preserve no-download, no-training, no-runtime-mutation guardrails",
            ],
            "failureAdaptation": "If required artifacts are missing, route to artifact inventory repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_event_lane_gap_classification_repair",
            "successCriteria": [
                "repair closeout classification from saved generated truth only",
                "keep full-match analysis readiness false",
            ],
            "failureAdaptation": "If report smoke is missing or unsafe, route back to report smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_event_lane_closeout_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before video download, training, promotion, or runtime mutation",
            ],
            "failureAdaptation": "Route to report smoke or artifact inventory repair.",
        },
    ]


def _artifact_inventory(candidate_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for spec in REQUIRED_ARTIFACTS:
        path = candidate_root / spec["path"]
        payload = _load_json(path)
        rows.append(
            {
                "stageId": spec["stageId"],
                "batchName": spec["batchName"],
                "path": str(path),
                "exists": path.exists(),
                "goalAchieved": payload.get("goalAchieved") if isinstance(payload, dict) else None,
                "primaryBlocker": payload.get("primaryBlocker") if isinstance(payload, dict) else "missing_artifact",
                "eventCount": payload.get("eventCount") or payload.get("annotationCount") or payload.get("canonicalEventCount") if isinstance(payload, dict) else None,
                "archiveDownloadExecuted": payload.get("archiveDownloadExecuted") if isinstance(payload, dict) else None,
                "videoMemberDownloadExecuted": payload.get("videoMemberDownloadExecuted") if isinstance(payload, dict) else None,
                "trainingExecuted": payload.get("trainingExecuted") if isinstance(payload, dict) else None,
                "runtimeDefaultMutationExecuted": payload.get("runtimeDefaultMutationExecuted") if isinstance(payload, dict) else None,
            }
        )
    missing = [row for row in rows if not row["exists"]]
    failed = [row for row in rows if row["exists"] and row["goalAchieved"] is False]
    return {
        "generatedAt": utc_now_iso(),
        "artifactCount": len(rows),
        "missingArtifactCount": len(missing),
        "failedArtifactCount": len(failed),
        "artifacts": rows,
    }


def _capability_matrix(report_smoke: dict[str, Any] | None) -> dict[str, Any]:
    event_count = int((report_smoke or {}).get("eventCount") or 0)
    distinct_event_count = int((report_smoke or {}).get("distinctEventTypeCount") or 0)
    return {
        "generatedAt": utc_now_iso(),
        "capabilities": [
            {
                "capabilityId": "external_label_access_path",
                "status": "proven",
                "evidence": "SoccerNet label member was extracted without full archive or video download.",
            },
            {
                "capabilityId": "event_schema_ingestion",
                "status": "proven",
                "evidence": f"{event_count} event annotations flowed into canonical event fixtures.",
            },
            {
                "capabilityId": "event_benchmark_smoke",
                "status": "proven",
                "evidence": f"{event_count} events across {distinct_event_count} event types were benchmarked.",
            },
            {
                "capabilityId": "event_only_report_rendering",
                "status": "proven",
                "evidence": "A human-readable event-frequency and event-taxonomy report rendered from saved artifacts.",
            },
            {
                "capabilityId": "full_video_analysis",
                "status": "not_proven",
                "evidence": "Video members were not downloaded or analyzed in this lane.",
            },
            {
                "capabilityId": "ball_localization_benchmark",
                "status": "not_proven",
                "evidence": "SoccerNet labels used here are event labels, not frame-level ball boxes.",
            },
        ],
    }


def _gap_analysis() -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "remainingUnprovenStages": [
            "camera_shot_gate",
            "calibration",
            "tracking",
            "ball_localization",
            "tactical_reporting",
            "full_original_video_analysis",
        ],
        "safeNextLevers": [
            "football_external_soccernet_event_report_product_integration",
            "football_external_multisource_event_benchmark_expansion",
            "football_external_soccernet_video_sample_download_approval",
            "football_external_video_ground_truth_source_search",
        ],
        "blockedWithoutSeparateApproval": [
            "full_archive_download",
            "video_member_download",
            "training",
            "promotion",
            "runtime_default_mutation",
        ],
    }


def _classify(inventory: dict[str, Any], report_smoke: dict[str, Any] | None) -> tuple[str | None, str, bool, str]:
    if not isinstance(report_smoke, dict) or report_smoke.get("eventReportSmokePassed") is not True:
        return (
            BLOCKER_REPORT_SMOKE_MISSING,
            NEXT_REPORT_SMOKE,
            False,
            "SoccerNet event report smoke truth is missing or unsafe; rerun the report smoke before closeout.",
        )
    if inventory.get("missingArtifactCount") or inventory.get("failedArtifactCount"):
        return (
            BLOCKER_ARTIFACT_INVENTORY_GAP,
            NEXT_ARTIFACT_REPAIR,
            False,
            "SoccerNet event lane inventory is incomplete; repair generated artifact coverage before closeout.",
        )
    return (
        None,
        NEXT_PRODUCT_INTEGRATION,
        True,
        "SoccerNet event-only lane closed cleanly. Event reporting can be integrated as an event-only product surface; video-analysis work remains a separate approval lane.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "event_report_smoke_missing", "selected": primary_blocker == BLOCKER_REPORT_SMOKE_MISSING, "primaryBlocker": BLOCKER_REPORT_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_REPORT_SMOKE},
            {"condition": "event_lane_artifact_inventory_gap", "selected": primary_blocker == BLOCKER_ARTIFACT_INVENTORY_GAP, "primaryBlocker": BLOCKER_ARTIFACT_INVENTORY_GAP, "nextRecommendedNextLever": NEXT_ARTIFACT_REPAIR},
            {"condition": "event_lane_closed", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_INTEGRATION},
        ],
    }


def _markdown_summary(summary: dict[str, Any], gaps: dict[str, Any]) -> str:
    lines = [
        "# Football External SoccerNet Event Lane Closeout",
        "",
        f"- Goal achieved: `{summary.get('goalAchieved')}`",
        f"- Primary blocker: `{summary.get('primaryBlocker')}`",
        f"- Event-only lane closed: `{summary.get('eventOnlyLaneClosed')}`",
        f"- Event count: `{summary.get('eventCount')}`",
        f"- Distinct event types: `{summary.get('distinctEventTypeCount')}`",
        f"- Full match analysis ready: `{summary.get('fullMatchAnalysisReady')}`",
        f"- Training executed: `{summary.get('trainingExecuted')}`",
        f"- Runtime mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
        f"- Next: `{summary.get('nextRecommendedNextLever')}`",
        "",
        "## Remaining Unproven Stages",
        "",
    ]
    for stage in gaps.get("remainingUnprovenStages") or []:
        lines.append(f"- `{stage}`")
    lines.extend(["", str(summary.get("englishDecision") or ""), ""])
    return "\n".join(lines)


def run_football_external_soccernet_event_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_event_lane_artifact_inventory",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(candidate_root, output_dir_name)

    report_smoke_path = candidate_root / "football_external_soccernet_event_report_smoke_v1/soccernet_event_report_smoke_summary.json"
    report_smoke = _load_json(report_smoke_path)
    inventory = _artifact_inventory(candidate_root)
    capabilities = _capability_matrix(report_smoke)
    gaps = _gap_analysis()
    primary_blocker, next_lever, goal_achieved, english = _classify(inventory, report_smoke)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_event_lane_closeout",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "eventOnlyLaneClosed": goal_achieved,
        "sourceBatch": "football_external_soccernet_event_report_smoke",
        "eventCount": (report_smoke or {}).get("eventCount"),
        "distinctEventTypeCount": (report_smoke or {}).get("distinctEventTypeCount"),
        "fullMatchAnalysisReady": False,
        "fullBenchmarkExecutionReady": False,
        "archiveDownloadExecuted": False,
        "videoMemberDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "provenArtifactInventory": inventory,
        "eventLaneCapabilityMatrix": capabilities,
        "remainingGapAnalysis": gaps,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_event_lane_closeout_summary.json", summary)
    _write_json(output_root / "proven_artifact_inventory.json", inventory)
    _write_json(output_root / "event_lane_capability_matrix.json", capabilities)
    _write_json(output_root / "remaining_gap_analysis.json", gaps)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary, gaps), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_event_lane_artifact_inventory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_event_lane_closeout(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
