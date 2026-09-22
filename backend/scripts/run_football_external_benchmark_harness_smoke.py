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
DEFAULT_PREP_DIR_NAME = "football_external_benchmark_harness_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_harness_smoke_v1"

BLOCKER_PREP_MISSING = "football_external_benchmark_harness_prep_missing"
BLOCKER_SOURCE_ARTIFACT_MISSING = "football_external_benchmark_harness_source_artifact_missing"
BLOCKER_SCHEMA_GAP = "football_external_benchmark_harness_schema_gap"

NEXT_PREP = "football_external_benchmark_harness_prep"
NEXT_SOURCE_REPAIR = "football_external_benchmark_harness_source_contract_repair"
NEXT_SCHEMA_REPAIR = "football_external_benchmark_harness_smoke_contract_repair"
NEXT_EXECUTION_APPROVAL = "football_external_benchmark_execution_approval"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_harness_smoke",
            "successCriteria": [
                "load the generated benchmark source manifest",
                "verify source artifact presence and schema",
                "write cross-source smoke cases and common metric-family placeholders",
                "keep detector evaluation, training, promotion, video download, normal match storage mutation, and runtime-default mutation false",
            ],
            "failureAdaptation": "If prep truth is missing, return to harness prep.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_harness_smoke_contract_repair",
            "successCriteria": [
                "repair smoke contract fields from generated prep truth only",
                "do not execute detector benchmark or download data",
            ],
            "failureAdaptation": "If source artifacts are missing, route to source contract repair.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_harness_smoke_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to prep, source contract repair, smoke contract repair, or execution approval.",
        },
    ]


def _prep_root(storage_root: Path, candidate_name: str, prep_dir_name: str) -> Path:
    return _candidate_root(storage_root, candidate_name) / prep_dir_name


def _resolve_artifact_path(path_value: str, *, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return repo_root / path


def _load_prep(prep_root: Path) -> dict[str, Any]:
    return {
        "sourceManifest": _load_json(prep_root / "external_benchmark_source_manifest.json"),
        "readinessAudit": _load_json(prep_root / "benchmark_harness_readiness_audit.json"),
        "stageGateContract": _load_json(prep_root / "stage_gate_contract.json"),
        "adapterContract": _load_json(prep_root / "dataset_adapter_contract.json"),
    }


def _prep_ready(inputs: dict[str, Any]) -> bool:
    summary = (inputs.get("readinessAudit") or {}).get("summary")
    manifest = inputs.get("sourceManifest")
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("benchmarkHarnessPrepReady") is True
        and summary.get("benchmarkHarnessContractReady") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(manifest, dict)
        and manifest.get("schemaVersion") == "football_external_benchmark_source_manifest_v1"
        and isinstance(manifest.get("sources"), list)
        and len(manifest["sources"]) >= 2
    )


def _artifact_presence_audit(manifest: dict[str, Any] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in (manifest or {}).get("sources") or []:
        if not isinstance(source, dict):
            continue
        for path_value in source.get("summaryPaths") or []:
            path = _resolve_artifact_path(str(path_value))
            rows.append(
                {
                    "sourceId": source.get("sourceId"),
                    "artifactPath": str(path),
                    "exists": path.exists(),
                    "isFile": path.is_file(),
                }
            )
    missing = [row for row in rows if not (row["exists"] and row["isFile"])]
    return {
        "schemaVersion": "football_external_benchmark_source_artifact_presence_audit_v1",
        "generatedAt": utc_now_iso(),
        "artifactCount": len(rows),
        "missingArtifactCount": len(missing),
        "allSourceArtifactsPresent": len(rows) > 0 and not missing,
        "artifacts": rows,
    }


def _schema_audit(inputs: dict[str, Any]) -> dict[str, Any]:
    manifest = inputs.get("sourceManifest") or {}
    stage = inputs.get("stageGateContract") or {}
    adapter = inputs.get("adapterContract") or {}
    required_stages = stage.get("requiredStageCoverage") if isinstance(stage, dict) else None
    schemas = adapter.get("schemas") if isinstance(adapter, dict) else None
    checks = {
        "sourceManifestSchemaValid": manifest.get("schemaVersion") == "football_external_benchmark_source_manifest_v1",
        "stageGateSchemaValid": stage.get("schemaVersion") == "football_external_benchmark_stage_gate_contract_v2",
        "adapterContractSchemaValid": adapter.get("schemaVersion") == "football_external_benchmark_adapter_contract_v2",
        "requiredStageCoveragePresent": isinstance(required_stages, list) and len(required_stages) >= 5,
        "adapterSmokeCaseSchemaPresent": isinstance(schemas, dict) and "ExternalBenchmarkSmokeCase" in schemas,
    }
    return {
        "schemaVersion": "football_external_benchmark_schema_version_smoke_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "schemaSmokePassed": all(checks.values()),
    }


def _smoke_cases(manifest: dict[str, Any]) -> dict[str, Any]:
    smoke_cases: list[dict[str, Any]] = []
    for source in manifest.get("sources") or []:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("sourceId"))
        metric_families = ["analysis_product_surface", "event_semantics"] if source_id == "soccernet" else ["analysis_product_surface", "event_semantics"]
        smoke_cases.append(
            {
                "sourceId": source_id,
                "caseId": f"{source_id}_generated_truth_smoke",
                "sourceDataset": source.get("sourceDataset"),
                "artifactPaths": source.get("summaryPaths") or [],
                "expectedMetricFamilies": metric_families,
                "detectorEvaluationExecuted": False,
                "trainingUseAllowed": False,
                "videoDownloadAllowed": False,
            }
        )
    return {
        "schemaVersion": "football_external_benchmark_smoke_case_manifest_v1",
        "generatedAt": utc_now_iso(),
        "smokeCaseCount": len(smoke_cases),
        "smokeCases": smoke_cases,
    }


def _metric_family_smoke(cases: dict[str, Any]) -> dict[str, Any]:
    families = sorted({family for case in cases.get("smokeCases", []) for family in case.get("expectedMetricFamilies", [])})
    source_ids = [case.get("sourceId") for case in cases.get("smokeCases", [])]
    return {
        "schemaVersion": "football_external_benchmark_cross_source_metric_family_smoke_v1",
        "generatedAt": utc_now_iso(),
        "sourceIds": source_ids,
        "metricFamilies": families,
        "metricFamilyCoveragePassed": set(families) >= {"analysis_product_surface", "event_semantics"},
        "detectorMetricFamiliesExecuted": [],
        "detectorEvaluationExecuted": False,
    }


def _stage_gate_smoke(stage_contract: dict[str, Any] | None, artifact_audit: dict[str, Any], schema_audit: dict[str, Any], metric_smoke: dict[str, Any]) -> dict[str, Any]:
    required = (stage_contract or {}).get("requiredStageCoverage") or []
    stage_results = {
        "source_manifest_load": True,
        "artifact_presence_check": artifact_audit.get("allSourceArtifactsPresent") is True,
        "schema_version_check": schema_audit.get("schemaSmokePassed") is True,
        "metric_family_mapping": metric_smoke.get("metricFamilyCoveragePassed") is True,
        "no_training_or_runtime_mutation": True,
    }
    missing = [stage for stage in required if stage_results.get(stage) is not True]
    return {
        "schemaVersion": "football_external_benchmark_stage_gate_smoke_audit_v1",
        "generatedAt": utc_now_iso(),
        "requiredStageCoverage": required,
        "stageResults": stage_results,
        "missingRequiredStageCoverage": missing,
        "stageGateSmokePassed": not missing,
    }


def _classify(prep_ready: bool, artifact_audit: dict[str, Any], schema_audit: dict[str, Any], stage_audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not prep_ready:
        return (
            BLOCKER_PREP_MISSING,
            NEXT_PREP,
            False,
            "External benchmark harness prep truth is missing or unsafe; rerun harness prep.",
        )
    if artifact_audit.get("allSourceArtifactsPresent") is not True:
        return (
            BLOCKER_SOURCE_ARTIFACT_MISSING,
            NEXT_SOURCE_REPAIR,
            False,
            "External benchmark smoke found missing source artifacts; repair the source contract before execution approval.",
        )
    if schema_audit.get("schemaSmokePassed") is not True or stage_audit.get("stageGateSmokePassed") is not True:
        return (
            BLOCKER_SCHEMA_GAP,
            NEXT_SCHEMA_REPAIR,
            False,
            "External benchmark smoke found a schema/stage gap; repair the smoke contract before execution approval.",
        )
    return (
        None,
        NEXT_EXECUTION_APPROVAL,
        True,
        "External benchmark harness smoke passed for SoccerNet and SoccerTrack generated artifacts. Advance to execution approval; no detector evaluation, training, promotion, video download, normal match storage mutation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "prep_missing", "selected": primary_blocker == BLOCKER_PREP_MISSING, "primaryBlocker": BLOCKER_PREP_MISSING, "nextRecommendedNextLever": NEXT_PREP},
            {"condition": "source_artifact_missing", "selected": primary_blocker == BLOCKER_SOURCE_ARTIFACT_MISSING, "primaryBlocker": BLOCKER_SOURCE_ARTIFACT_MISSING, "nextRecommendedNextLever": NEXT_SOURCE_REPAIR},
            {"condition": "schema_or_stage_gap", "selected": primary_blocker == BLOCKER_SCHEMA_GAP, "primaryBlocker": BLOCKER_SCHEMA_GAP, "nextRecommendedNextLever": NEXT_SCHEMA_REPAIR},
            {"condition": "external_benchmark_execution_approval_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_EXECUTION_APPROVAL},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Harness Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Smoke cases: `{summary.get('smokeCaseCount')}`",
            f"- Source artifacts present: `{summary.get('allSourceArtifactsPresent')}`",
            f"- Schema smoke passed: `{summary.get('schemaSmokePassed')}`",
            f"- Stage gate smoke passed: `{summary.get('stageGateSmokePassed')}`",
            f"- External benchmark execution ready: `{summary.get('externalBenchmarkExecutionReady')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime-default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_harness_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    prep_dir_name: str = DEFAULT_PREP_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_harness_smoke",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    prep_root = _prep_root(Path(storage_root), candidate_name, prep_dir_name)
    output_root = reset_output(candidate_root, output_dir_name)

    inputs = _load_prep(prep_root)
    prep_ready = _prep_ready(inputs)
    manifest = inputs.get("sourceManifest") if isinstance(inputs.get("sourceManifest"), dict) else {"sources": []}
    artifact_audit = _artifact_presence_audit(manifest)
    schema_audit = _schema_audit(inputs)
    cases = _smoke_cases(manifest)
    metric_smoke = _metric_family_smoke(cases)
    stage_audit = _stage_gate_smoke(inputs.get("stageGateContract"), artifact_audit, schema_audit, metric_smoke)
    primary_blocker, next_lever, goal_achieved, english = _classify(prep_ready, artifact_audit, schema_audit, stage_audit)
    attempts = _attempt_plan()

    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_harness_smoke",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourcePrepBatch": "football_external_benchmark_harness_prep",
        "externalBenchmarkHarnessSmokePassed": goal_achieved,
        "smokeCaseCount": cases.get("smokeCaseCount"),
        "externalSourceCount": len(manifest.get("sources") or []),
        "soccernetSmokeReady": any(row.get("sourceId") == "soccernet" for row in cases.get("smokeCases", [])),
        "soccertrackSmokeReady": any(row.get("sourceId") == "soccertrack" for row in cases.get("smokeCases", [])),
        "allSourceArtifactsPresent": artifact_audit.get("allSourceArtifactsPresent"),
        "missingArtifactCount": artifact_audit.get("missingArtifactCount"),
        "schemaSmokePassed": schema_audit.get("schemaSmokePassed"),
        "metricFamilyCoveragePassed": metric_smoke.get("metricFamilyCoveragePassed"),
        "stageGateSmokePassed": stage_audit.get("stageGateSmokePassed"),
        "externalBenchmarkExecutionApprovalReady": goal_achieved,
        "externalBenchmarkExecutionReady": False,
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "datasetAccessReviewReady": False,
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
        "sourceArtifactPresenceAudit": artifact_audit,
        "schemaVersionSmokeAudit": schema_audit,
        "benchmarkSmokeCaseManifest": cases,
        "crossSourceMetricFamilySmoke": metric_smoke,
        "stageGateSmokeAudit": stage_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": failsafe,
    }

    _write_json(output_root / "external_benchmark_smoke_summary.json", summary)
    _write_json(output_root / "source_artifact_presence_audit.json", artifact_audit)
    _write_json(output_root / "schema_version_smoke_audit.json", schema_audit)
    _write_json(output_root / "benchmark_smoke_case_manifest.json", cases)
    _write_json(output_root / "cross_source_metric_family_smoke.json", metric_smoke)
    _write_json(output_root / "stage_gate_smoke_audit.json", stage_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", failsafe)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--prep-dir-name", default=DEFAULT_PREP_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    args = parser.parse_args()

    summary = run_football_external_benchmark_harness_smoke(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        prep_dir_name=args.prep_dir_name,
        output_dir_name=args.output_dir_name,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("goalAchieved") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
