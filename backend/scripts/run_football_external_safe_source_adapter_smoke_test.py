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
DEFAULT_HARNESS_DIR_NAME = "football_external_benchmark_harness_prep_v1"
DEFAULT_ACCESS_REVIEW_DIR_NAME = "football_external_dataset_access_review_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_safe_source_adapter_smoke_test_v1"

BLOCKER_HARNESS_MISSING = "football_external_safe_source_adapter_harness_missing"
BLOCKER_ACCESS_REVIEW_MISSING = "football_external_safe_source_adapter_access_review_missing"
BLOCKER_NO_APPROVED_RESOURCES = "football_external_safe_source_adapter_no_approved_resources"
BLOCKER_DOWNLOAD_GUARDRAIL = "football_external_safe_source_adapter_download_guardrail_violation"
BLOCKER_SCHEMA_CONTRACT = "football_external_safe_source_adapter_schema_contract_gap"

NEXT_HARNESS = "football_external_benchmark_harness_prep"
NEXT_ACCESS_REVIEW = "football_external_dataset_access_review"
NEXT_ADAPTER_FIX = "football_external_adapter_contract_fix"
NEXT_FIXTURE_IMPLEMENTATION = "football_external_safe_adapter_fixture_implementation"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "safe_source_schema_adapter_smoke",
            "successCriteria": [
                "read only approved smoke resources",
                "build synthetic adapter rows that satisfy the saved schema contract",
                "prove no dataset download, training, promotion, or runtime mutation occurred",
            ],
            "failureAdaptation": "If schemas or approved resources are incomplete, move to adapter-contract repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "adapter_contract_repair",
            "successCriteria": [
                "repair missing schema metadata from saved harness artifacts only",
                "preserve no-download guardrails",
                "do not fetch external datasets",
            ],
            "failureAdaptation": "If smoke inputs remain insufficient, write a safe-source adapter blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "safe_source_adapter_blocker_summary",
            "successCriteria": [
                "write blocker truth with exactly one next family",
                "keep external resources evidence-only",
                "stop before training or benchmark execution",
            ],
            "failureAdaptation": "Route to access review or adapter contract fix without downloading data.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    harness_root = candidate_root / DEFAULT_HARNESS_DIR_NAME
    access_root = candidate_root / DEFAULT_ACCESS_REVIEW_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "harnessRoot": harness_root,
        "accessRoot": access_root,
        "harnessSummary": _load_json(harness_root / "external_benchmark_harness_summary.json"),
        "resourceInventory": _load_json(harness_root / "benchmark_resource_inventory.json"),
        "adapterContract": _load_json(harness_root / "dataset_adapter_contract.json"),
        "stageGateContract": _load_json(harness_root / "stage_gate_contract.json"),
        "accessSummary": _load_json(access_root / "external_dataset_access_review_summary.json"),
        "approvedSmokeManifest": _load_json(access_root / "approved_smoke_resource_manifest.json"),
    }


def _schemas(adapter_contract: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = (adapter_contract or {}).get("schemas")
    if not isinstance(raw, dict):
        return {}
    return {str(name): dict(schema) for name, schema in raw.items() if isinstance(schema, dict)}


def _required_fields(schema: dict[str, Any]) -> list[str]:
    fields = schema.get("requiredFields")
    if not isinstance(fields, list):
        return []
    return [str(field) for field in fields if str(field).strip()]


def _approved_resources(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (manifest or {}).get("approvedSmokeResources")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict) and row.get("benchmarkSmokeUseAllowed") is True]


def _default_value(field: str, resource_id: str, frame_index: int) -> Any:
    if field in {"source", "resourceId"}:
        return resource_id
    if field in {"matchId"}:
        return f"{resource_id}_synthetic_match"
    if field in {"frameIndex"}:
        return frame_index
    if field in {"timestampMs"}:
        return frame_index * 100
    if field in {"imagePath"}:
        return f"synthetic://{resource_id}/frame_{frame_index:06d}.jpg"
    if field in {"homography"}:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    if field in {"players", "entities"}:
        return []
    if field in {"ball"}:
        return {"visible": False, "confidence": 0.0}
    if field in {"events"}:
        return []
    if field in {"possession", "teamInPossession"}:
        return None
    if field in {"phaseOfPlay"}:
        return "unknown"
    if field in {"sourceConfidence", "trackConfidence", "calibrationConfidence", "confidence"}:
        return 1.0
    if field in {"cameraType"}:
        return "unknown"
    if field in {"pitchKeypoints"}:
        return []
    if field in {"trackId"}:
        return "synthetic_track"
    if field in {"teamId", "playerId"}:
        return None
    if field in {"bbox"}:
        return [0.0, 0.0, 1.0, 1.0]
    if field in {"pitchX", "ballPitchX", "pitchY", "ballPitchY"}:
        return None
    if field in {"eventId"}:
        return f"{resource_id}_synthetic_event"
    if field in {"eventType"}:
        return "synthetic_noop"
    return None


def _synthetic_rows(resources: list[dict[str, Any]], schemas: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    frame_state_fields = _required_fields(schemas.get("FrameState", {}))
    game_state_fields = _required_fields(schemas.get("GameState", {}))
    for index, resource in enumerate(resources):
        resource_id = str(resource.get("resourceId") or f"resource_{index}")
        frame_index = index + 1
        row = {
            "resourceId": resource_id,
            "sourceResource": resource,
            "FrameState": {field: _default_value(field, resource_id, frame_index) for field in frame_state_fields},
            "GameState": {field: _default_value(field, resource_id, frame_index) for field in game_state_fields},
            "datasetDownloadExecuted": False,
            "syntheticOnly": True,
        }
        rows.append(row)
    return rows


def _schema_audit(rows: list[dict[str, Any]], schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    audited_schema_names = [name for name in ("FrameState", "GameState") if name in schemas]
    failures: list[dict[str, Any]] = []
    for row in rows:
        for schema_name in audited_schema_names:
            required = _required_fields(schemas[schema_name])
            payload = row.get(schema_name)
            if not isinstance(payload, dict):
                failures.append({"resourceId": row.get("resourceId"), "schema": schema_name, "missingFields": required})
                continue
            missing = [field for field in required if field not in payload]
            if missing:
                failures.append({"resourceId": row.get("resourceId"), "schema": schema_name, "missingFields": missing})
    return {
        "auditedSchemaNames": audited_schema_names,
        "syntheticFixtureRowCount": len(rows),
        "schemaFailureCount": len(failures),
        "allSyntheticRowsSatisfySchema": len(failures) == 0 and bool(audited_schema_names),
        "failures": failures,
        "syntheticRows": rows,
    }


def _required_stage_coverage(stage_gate_contract: dict[str, Any] | None) -> list[str]:
    raw = (stage_gate_contract or {}).get("requiredStageCoverage")
    if isinstance(raw, list):
        return [str(stage) for stage in raw if str(stage).strip()]
    stage_gates = (stage_gate_contract or {}).get("stageGates")
    if isinstance(stage_gates, list):
        return [str(row.get("stageId")) for row in stage_gates if isinstance(row, dict) and row.get("stageId")]
    return []


def _stage_audit(resources: list[dict[str, Any]], stage_gate_contract: dict[str, Any] | None) -> dict[str, Any]:
    covered: set[str] = set()
    for resource in resources:
        stages = resource.get("coveredStages")
        if isinstance(stages, list):
            covered.update(str(stage) for stage in stages if str(stage).strip())
    required = _required_stage_coverage(stage_gate_contract)
    missing = [stage for stage in required if stage not in covered]
    return {
        "requiredStages": required,
        "safeSmokeCoveredStages": sorted(covered),
        "missingSafeSmokeStages": missing,
        "safeSmokeStageCoverageComplete": bool(required) and not missing,
    }


def _download_guardrail(access_summary: dict[str, Any] | None, manifest: dict[str, Any] | None, resources: list[dict[str, Any]]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if bool((access_summary or {}).get("datasetDownloadExecuted")):
        violations.append({"scope": "accessSummary", "field": "datasetDownloadExecuted"})
    if bool((manifest or {}).get("datasetDownloadExecuted")):
        violations.append({"scope": "approvedSmokeManifest", "field": "datasetDownloadExecuted"})
    for resource in resources:
        if bool(resource.get("downloadAllowedByThisBatch")):
            violations.append({"scope": "resource", "resourceId": resource.get("resourceId"), "field": "downloadAllowedByThisBatch"})
        if bool(resource.get("datasetDownloadExecuted")):
            violations.append({"scope": "resource", "resourceId": resource.get("resourceId"), "field": "datasetDownloadExecuted"})
    return {
        "downloadGuardrailPassed": not violations,
        "violationCount": len(violations),
        "violations": violations,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
    }


def _classify(
    *,
    harness_summary: dict[str, Any] | None,
    access_summary: dict[str, Any] | None,
    resources: list[dict[str, Any]],
    download_audit: dict[str, Any],
    schema_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not (
        isinstance(harness_summary, dict)
        and harness_summary.get("goalAchieved") is True
        and harness_summary.get("benchmarkHarnessContractReady") is True
    ):
        return (
            BLOCKER_HARNESS_MISSING,
            NEXT_HARNESS,
            False,
            "External benchmark harness prep is missing or not contract-ready.",
        )
    if not (
        isinstance(access_summary, dict)
        and access_summary.get("goalAchieved") is True
        and access_summary.get("safeSourceAdapterSmokeReady") is True
    ):
        return (
            BLOCKER_ACCESS_REVIEW_MISSING,
            NEXT_ACCESS_REVIEW,
            False,
            "Dataset access review is missing or did not approve safe-source adapter smoke.",
        )
    if not download_audit["downloadGuardrailPassed"]:
        return (
            BLOCKER_DOWNLOAD_GUARDRAIL,
            NEXT_ACCESS_REVIEW,
            False,
            "A dataset download or download-allowance signal was present; safe-source smoke refused to proceed.",
        )
    if not resources:
        return (
            BLOCKER_NO_APPROVED_RESOURCES,
            NEXT_ACCESS_REVIEW,
            False,
            "No approved smoke resources are available for safe-source adapter smoke.",
        )
    if not schema_audit["allSyntheticRowsSatisfySchema"]:
        return (
            BLOCKER_SCHEMA_CONTRACT,
            NEXT_ADAPTER_FIX,
            False,
            "Synthetic safe-source adapter rows did not satisfy the saved adapter schema contract.",
        )
    return (
        None,
        NEXT_FIXTURE_IMPLEMENTATION,
        True,
        "Safe-source adapter smoke passed on synthetic rows from approved resources. Advance to fixture adapter implementation; do not download datasets, train, promote, or mutate runtime defaults.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Safe Source Adapter Smoke Test",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Safe smoke resources: `{summary.get('safeSmokeResourceCount')}`",
            f"- Synthetic fixture rows: `{summary.get('syntheticFixtureRowCount')}`",
            f"- Schema smoke passed: `{summary.get('safeSourceAdapterSmokePassed')}`",
            f"- Safe stage coverage complete: `{summary.get('safeSmokeStageCoverageComplete')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_safe_source_adapter_smoke_test(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "safe_source_schema_adapter_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    resources = _approved_resources(inputs["approvedSmokeManifest"])
    schemas = _schemas(inputs["adapterContract"])
    rows = _synthetic_rows(resources, schemas)
    schema_audit = _schema_audit(rows, schemas)
    stage_audit = _stage_audit(resources, inputs["stageGateContract"])
    download_audit = _download_guardrail(inputs["accessSummary"], inputs["approvedSmokeManifest"], resources)
    attempts = _attempt_plan()
    primary_blocker, next_lever, goal_achieved, english = _classify(
        harness_summary=inputs["harnessSummary"],
        access_summary=inputs["accessSummary"],
        resources=resources,
        download_audit=download_audit,
        schema_audit=schema_audit,
    )
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_safe_source_adapter_smoke_test",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceHarnessBatch": "football_external_benchmark_harness_prep",
        "sourceAccessReviewBatch": "football_external_dataset_access_review",
        "safeSmokeResourceCount": len(resources),
        "safeSmokeResourceIds": [str(row.get("resourceId")) for row in resources],
        "syntheticFixtureRowCount": len(rows),
        "adapterSchemaCount": len(schemas),
        "auditedSchemaNames": schema_audit["auditedSchemaNames"],
        "safeSourceAdapterSmokePassed": goal_achieved,
        "schemaSmokePassed": schema_audit["allSyntheticRowsSatisfySchema"],
        "safeSmokeStageCoverageComplete": stage_audit["safeSmokeStageCoverageComplete"],
        "safeSmokeCoveredStages": stage_audit["safeSmokeCoveredStages"],
        "missingSafeSmokeStages": stage_audit["missingSafeSmokeStages"],
        "fullExternalBenchmarkExecutionReady": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
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
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "harness_missing", "selected": primary_blocker == BLOCKER_HARNESS_MISSING, "nextRecommendedNextLever": NEXT_HARNESS},
            {"condition": "access_review_missing", "selected": primary_blocker == BLOCKER_ACCESS_REVIEW_MISSING, "nextRecommendedNextLever": NEXT_ACCESS_REVIEW},
            {"condition": "download_guardrail_violation", "selected": primary_blocker == BLOCKER_DOWNLOAD_GUARDRAIL, "nextRecommendedNextLever": NEXT_ACCESS_REVIEW},
            {"condition": "no_approved_resources", "selected": primary_blocker == BLOCKER_NO_APPROVED_RESOURCES, "nextRecommendedNextLever": NEXT_ACCESS_REVIEW},
            {"condition": "schema_contract_gap", "selected": primary_blocker == BLOCKER_SCHEMA_CONTRACT, "nextRecommendedNextLever": NEXT_ADAPTER_FIX},
            {"condition": "safe_source_adapter_smoke_passed", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_FIXTURE_IMPLEMENTATION},
        ],
    }
    resource_manifest = {
        "generatedAt": generated_at,
        "datasetDownloadExecuted": False,
        "safeSmokeResources": resources,
        "syntheticFixtureRows": rows,
        "note": "Rows are synthetic contract fixtures only; no external dataset bytes were fetched.",
    }
    batch_outcome = {
        "summary": summary,
        "decisionMatrix": decision_matrix,
        "schemaSmokeAudit": schema_audit,
        "stageCoverageSmokeAudit": stage_audit,
        "datasetDownloadGuardrailAudit": download_audit,
        "resourceManifest": resource_manifest,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "safe_source_adapter_smoke_summary.json", summary)
    _write_json(output_root / "safe_source_adapter_schema_smoke_audit.json", schema_audit)
    _write_json(output_root / "safe_source_adapter_resource_manifest.json", resource_manifest)
    _write_json(output_root / "adapter_stage_coverage_smoke_audit.json", stage_audit)
    _write_json(output_root / "dataset_download_guardrail_audit.json", download_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test approved external-source adapter contracts without downloading datasets.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="safe_source_schema_adapter_smoke")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_safe_source_adapter_smoke_test(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
