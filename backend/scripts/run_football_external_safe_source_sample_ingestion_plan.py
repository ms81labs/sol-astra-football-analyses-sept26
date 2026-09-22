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
DEFAULT_FIXTURE_DIR_NAME = "football_external_safe_adapter_fixture_implementation_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_safe_source_sample_ingestion_plan_v1"

BLOCKER_FIXTURE_MISSING = "football_external_sample_ingestion_fixture_missing"
BLOCKER_DOWNLOAD_GUARDRAIL = "football_external_sample_ingestion_download_guardrail_violation"
BLOCKER_NO_SAFE_RESOURCE = "football_external_sample_ingestion_no_safe_resource"

NEXT_FIXTURE_IMPLEMENTATION = "football_external_safe_adapter_fixture_implementation"
NEXT_DATASET_ACCESS_REVIEW = "football_external_dataset_access_review"
NEXT_SAMPLE_DOWNLOAD_APPROVAL = "football_external_safe_source_sample_download_approval"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "safe_source_sample_ingestion_plan",
            "successCriteria": [
                "select first safe source from fixture resources",
                "write manual approval checklist before any external fetch",
                "write controlled ingestion sequence with no downloads executed",
            ],
            "failureAdaptation": "If access or fixture truth is incomplete, move to access-contract repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "sample_ingestion_access_contract_repair",
            "successCriteria": [
                "repair missing resource URLs or approval fields from saved access artifacts",
                "preserve explicit no-download state",
            ],
            "failureAdaptation": "If no safe sample resource can be selected, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "sample_ingestion_blocker_summary",
            "successCriteria": [
                "name exactly one next family",
                "do not download external data, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Stop before sample ingestion until approval is explicit.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fixture_root = candidate_root / DEFAULT_FIXTURE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fixtureRoot": fixture_root,
        "fixtureSummary": _load_json(fixture_root / "safe_adapter_fixture_implementation_summary.json"),
        "fixtureManifest": _load_json(fixture_root / "adapter_fixture_manifest.json"),
        "roundtripAudit": _load_json(fixture_root / "fixture_roundtrip_audit.json"),
        "downloadAudit": _load_json(fixture_root / "dataset_download_guardrail_audit.json"),
    }


def _fixture_resources(fixture_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    resources = (fixture_manifest or {}).get("resources")
    if not isinstance(resources, list):
        return []
    safe: list[dict[str, Any]] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("benchmarkSmokeUseAllowed") is True and resource.get("accessDecision") == "approved_smoke_only":
            safe.append(dict(resource))
    return sorted(safe, key=lambda row: (int(row.get("adapterPriority") or 999), str(row.get("resourceId") or "")))


def _download_guardrail(
    fixture_summary: dict[str, Any] | None,
    fixture_manifest: dict[str, Any] | None,
    download_audit: dict[str, Any] | None,
    resources: list[dict[str, Any]],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if bool((fixture_summary or {}).get("datasetDownloadExecuted")):
        violations.append({"scope": "fixtureSummary", "field": "datasetDownloadExecuted"})
    if bool((fixture_manifest or {}).get("datasetDownloadExecuted")):
        violations.append({"scope": "fixtureManifest", "field": "datasetDownloadExecuted"})
    if (download_audit or {}).get("downloadGuardrailPassed") is False:
        violations.append({"scope": "downloadAudit", "field": "downloadGuardrailPassed"})
    for resource in resources:
        if bool(resource.get("downloadAllowedByThisBatch")):
            violations.append({"scope": "resource", "resourceId": resource.get("resourceId"), "field": "downloadAllowedByThisBatch"})
        if bool(resource.get("datasetDownloadExecuted")):
            violations.append({"scope": "resource", "resourceId": resource.get("resourceId"), "field": "datasetDownloadExecuted"})
    return {
        "sampleIngestionGuardrailPassed": not violations,
        "downloadGuardrailPassed": not violations,
        "violationCount": len(violations),
        "violations": violations,
        "sampleDownloadApprovalRequired": True,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _approval_checklist(resources: list[dict[str, Any]], selected: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "approvalRequiredBeforeDownload": True,
        "selectedFirstSampleResourceId": selected.get("resourceId") if selected else None,
        "requiredApprovals": [
            "confirm current source license and access terms",
            "record exact source URL, commit/version, and license file path before fetch",
            "confirm sample use is adapter smoke only, not model training",
            "confirm attribution/notice obligations are captured in artifact metadata",
            "confirm local storage path is isolated under generated external sample storage",
        ],
        "resources": [
            {
                "resourceId": resource.get("resourceId"),
                "resourceName": resource.get("resourceName"),
                "officialSourceUrls": resource.get("officialSourceUrls") or [],
                "accessRiskClass": resource.get("accessRiskClass"),
                "downloadAllowedByThisBatch": False,
                "trainingUseAllowed": False,
                "approvalStatus": "manual_approval_required",
            }
            for resource in resources
        ],
    }


def _controlled_sequence(selected: dict[str, Any] | None) -> dict[str, Any]:
    selected_id = selected.get("resourceId") if selected else None
    return {
        "selectedFirstSampleResourceId": selected_id,
        "steps": [
            {
                "step": 1,
                "action": "manual_license_confirmation",
                "resourceId": selected_id,
                "requiredBeforeNext": True,
            },
            {
                "step": 2,
                "action": "fetch_smallest_official_sample",
                "resourceId": selected_id,
                "allowedOnlyAfterApproval": True,
                "executedByThisBatch": False,
            },
            {
                "step": 3,
                "action": "run_adapter_fixture_ingestion",
                "resourceId": selected_id,
                "allowedOnlyAfterFetch": True,
                "executedByThisBatch": False,
            },
            {
                "step": 4,
                "action": "compare_ingested_sample_to_canonical_fixtures",
                "resourceId": selected_id,
                "executedByThisBatch": False,
            },
        ],
    }


def _classify(
    *,
    fixture_summary: dict[str, Any] | None,
    roundtrip_audit: dict[str, Any] | None,
    guardrail: dict[str, Any],
    resources: list[dict[str, Any]],
) -> tuple[str | None, str, bool, str]:
    if not (
        isinstance(fixture_summary, dict)
        and fixture_summary.get("goalAchieved") is True
        and fixture_summary.get("adapterFixtureImplementationReady") is True
        and isinstance(roundtrip_audit, dict)
        and roundtrip_audit.get("roundTripPassed") is True
    ):
        return (
            BLOCKER_FIXTURE_MISSING,
            NEXT_FIXTURE_IMPLEMENTATION,
            False,
            "Safe adapter fixture implementation is missing or failed; rerun fixture materialization first.",
        )
    if not guardrail["sampleIngestionGuardrailPassed"]:
        return (
            BLOCKER_DOWNLOAD_GUARDRAIL,
            NEXT_DATASET_ACCESS_REVIEW,
            False,
            "A download guardrail violation was detected; return to dataset access review before sample ingestion planning.",
        )
    if not resources:
        return (
            BLOCKER_NO_SAFE_RESOURCE,
            NEXT_DATASET_ACCESS_REVIEW,
            False,
            "No safe approved source resource is available for controlled sample ingestion.",
        )
    return (
        None,
        NEXT_SAMPLE_DOWNLOAD_APPROVAL,
        True,
        "Safe-source sample ingestion plan is ready. Manual download approval is required before fetching any external sample; do not train, promote, or mutate runtime defaults.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Safe Source Sample Ingestion Plan",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected first sample resource: `{summary.get('selectedFirstSampleResourceId')}`",
            f"- Safe source count: `{summary.get('safeSourceResourceCount')}`",
            f"- Approval required: `{summary.get('sampleDownloadApprovalRequired')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_safe_source_sample_ingestion_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "safe_source_sample_ingestion_plan",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    resources = _fixture_resources(inputs["fixtureManifest"])
    selected = resources[0] if resources else None
    guardrail = _download_guardrail(inputs["fixtureSummary"], inputs["fixtureManifest"], inputs["downloadAudit"], resources)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        fixture_summary=inputs["fixtureSummary"],
        roundtrip_audit=inputs["roundtripAudit"],
        guardrail=guardrail,
        resources=resources,
    )
    generated_at = utc_now_iso()
    attempts = _attempt_plan()
    approval = _approval_checklist(resources, selected)
    sequence = _controlled_sequence(selected)
    summary: dict[str, Any] = {
        "batchName": "football_external_safe_source_sample_ingestion_plan",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_safe_adapter_fixture_implementation",
        "sampleIngestionPlanReady": goal_achieved,
        "safeSourceResourceCount": len(resources),
        "safeSourceResourceIds": [str(row.get("resourceId")) for row in resources],
        "selectedFirstSampleResourceId": selected.get("resourceId") if selected else None,
        "sampleDownloadApprovalRequired": True,
        "sampleDownloadExecuted": False,
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
        "fullExternalBenchmarkExecutionReady": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "fixture_missing", "selected": primary_blocker == BLOCKER_FIXTURE_MISSING, "nextRecommendedNextLever": NEXT_FIXTURE_IMPLEMENTATION},
            {"condition": "download_guardrail_violation", "selected": primary_blocker == BLOCKER_DOWNLOAD_GUARDRAIL, "nextRecommendedNextLever": NEXT_DATASET_ACCESS_REVIEW},
            {"condition": "no_safe_resource", "selected": primary_blocker == BLOCKER_NO_SAFE_RESOURCE, "nextRecommendedNextLever": NEXT_DATASET_ACCESS_REVIEW},
            {"condition": "sample_ingestion_plan_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_SAMPLE_DOWNLOAD_APPROVAL},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "sampleDownloadApprovalChecklist": approval,
        "controlledSampleIngestionSequence": sequence,
        "sampleIngestionGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "safe_source_sample_ingestion_plan_summary.json", summary)
    _write_json(output_root / "sample_download_approval_checklist.json", approval)
    _write_json(output_root / "controlled_sample_ingestion_sequence.json", sequence)
    _write_json(output_root / "sample_ingestion_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan controlled sample ingestion for safe external sources without fetching data.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="safe_source_sample_ingestion_plan")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_safe_source_sample_ingestion_plan(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
