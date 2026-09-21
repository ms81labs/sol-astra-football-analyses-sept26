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
DEFAULT_PARSE_DIR_NAME = "football_external_soccertrack_schema_doc_parse_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_sample_ingestion_contract_prep_v1"

BLOCKER_PARSE_MISSING = "football_external_soccertrack_schema_doc_parse_missing"
BLOCKER_MAPPING_INCOMPLETE = "football_external_soccertrack_sample_mapping_incomplete"

NEXT_SCHEMA_DOC_PARSE = "football_external_soccertrack_schema_doc_parse"
NEXT_SCHEMA_DOC_PARSE_REPAIR = "football_external_soccertrack_schema_doc_parse_repair"
NEXT_MATERIALIZATION_APPROVAL = "football_external_soccertrack_sample_fixture_materialization_approval"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_sample_ingestion_contract_prep",
            "successCriteria": [
                "build SoccerTrack-specific sample fixture/materialization contract from parsed docs",
                "require explicit approval before sample or dataset download",
                "preserve no training, promotion, candidate evaluation, or runtime mutation",
            ],
            "failureAdaptation": "If mappings are incomplete, return to schema-doc parse repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_sample_ingestion_contract_repair",
            "successCriteria": [
                "repair missing schema-to-adapter mapping rows",
                "keep approval and download scope closed",
            ],
            "failureAdaptation": "If mappings still cannot be prepared, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_sample_ingestion_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not download external data, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Stop before any sample materialization until contract is complete.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    parse_root = candidate_root / DEFAULT_PARSE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "parseRoot": parse_root,
        "parseSummary": _load_json(parse_root / "schema_doc_parse_summary.json"),
        "parsedContract": _load_json(parse_root / "soccertrack_parsed_schema_contract.json"),
        "mappingPlan": _load_json(parse_root / "sample_adapter_mapping_plan.json"),
    }


def _parse_ready(parse_summary: dict[str, Any] | None, parsed_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(parse_summary, dict)
        and parse_summary.get("goalAchieved") is True
        and parse_summary.get("primaryBlocker") is None
        and parse_summary.get("schemaDocParseReady") is True
        and parse_summary.get("datasetDownloadExecuted") is False
        and parse_summary.get("sampleDownloadExecuted") is False
        and parse_summary.get("trainingExecuted") is False
        and isinstance(parsed_contract, dict)
        and parsed_contract.get("contractSource") == "fetched_schema_docs_only"
        and isinstance(parsed_contract.get("taskContracts"), dict)
    )


def _mapping_audit(mapping_plan: dict[str, Any] | None) -> dict[str, Any]:
    rows = (mapping_plan or {}).get("mappingRows")
    rows = rows if isinstance(rows, list) else []
    covered_tasks = sorted({str(row.get("taskId")) for row in rows if isinstance(row, dict) and row.get("taskId")})
    target_fields = sorted({str(row.get("targetField")) for row in rows if isinstance(row, dict) and row.get("targetField")})
    required_targets = {
        "FrameState.frameIndex",
        "TrackedEntity.pitchPositionMeters",
        "BallActionEvent.timestampMs",
        "TrackFrame.entities",
    }
    return {
        "schemaVersion": "soccertrack_schema_to_adapter_mapping_audit_v1",
        "generatedAt": _utc_now_iso(),
        "mappingCompletenessPassed": {"gsr", "bas", "mot"}.issubset(set(covered_tasks)) and required_targets.issubset(set(target_fields)),
        "coveredTaskIds": covered_tasks,
        "targetFields": target_fields,
        "requiredTargetFields": sorted(required_targets),
        "mappingRowCount": len(rows),
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _download_guardrail(parse_summary: dict[str, Any] | None, parsed_contract: dict[str, Any] | None, mapping_plan: dict[str, Any] | None) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for scope, payload in [("parseSummary", parse_summary), ("parsedContract", parsed_contract), ("mappingPlan", mapping_plan)]:
        if not isinstance(payload, dict):
            continue
        for field in ["datasetDownloadExecuted", "sampleDownloadExecuted", "trainingExecuted"]:
            if payload.get(field) is True:
                violations.append({"scope": scope, "field": field})
    return {
        "schemaVersion": "soccertrack_download_scope_guardrail_audit_v1",
        "generatedAt": _utc_now_iso(),
        "downloadScopeGuardrailPassed": not violations,
        "violationCount": len(violations),
        "violations": violations,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadApproved": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadApproved": False,
        "fullDatasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _ingestion_contract(parsed_contract: dict[str, Any], mapping_audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_sample_ingestion_contract_v1",
        "generatedAt": _utc_now_iso(),
        "selectedSampleResourceId": "soccertrack_v2",
        "contractSource": "schema_doc_parse_generated_truth",
        "requiredAdapterSchemaNames": parsed_contract.get("requiredAdapterSchemaNames", []),
        "requiredTaskIds": ["gsr", "bas", "mot"],
        "schemaToAdapterMappingReady": mapping_audit.get("mappingCompletenessPassed") is True,
        "allowedUse": "adapter_fixture_materialization_only_after_approval",
        "trainingUseAllowed": False,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadApproved": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadApproved": False,
        "fullDatasetDownloadExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _sample_selection_plan() -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_sample_selection_plan_v1",
        "generatedAt": _utc_now_iso(),
        "selectedSampleResourceId": "soccertrack_v2",
        "selectionReason": "safe source already metadata-smoked; parsed docs cover gsr, bas, and mot",
        "preferredSampleScope": "smallest_official_fixture_or_single_match_subset_after_approval",
        "sampleDownloadApprovalRequired": True,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _fixture_plan(parsed_contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_sample_fixture_materialization_plan_v1",
        "generatedAt": _utc_now_iso(),
        "materializationApproved": False,
        "materializationExecuted": False,
        "requiredTaskFixtures": ["gsr", "bas", "mot"],
        "fixtureOutputs": [
            "soccertrack_gsr_frame_state_fixture.json",
            "soccertrack_bas_event_stream_fixture.json",
            "soccertrack_mot_track_frame_fixture.json",
            "soccertrack_game_state_fixture.json",
        ],
        "requiredAdapterSchemaNames": parsed_contract.get("requiredAdapterSchemaNames", []),
        "approvalRequiredBeforeMaterialization": True,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _classify(parse_ready: bool, guardrail: dict[str, Any], mapping_audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not parse_ready:
        return (
            BLOCKER_PARSE_MISSING,
            NEXT_SCHEMA_DOC_PARSE,
            False,
            "SoccerTrack schema-doc parse truth is missing or failed; parse docs before preparing sample ingestion.",
        )
    if guardrail.get("downloadScopeGuardrailPassed") is not True:
        return (
            BLOCKER_MAPPING_INCOMPLETE,
            NEXT_SCHEMA_DOC_PARSE_REPAIR,
            False,
            "Prior generated truth shows sample/dataset/training execution; repair the schema-doc lane before sample ingestion.",
        )
    if mapping_audit.get("mappingCompletenessPassed") is not True:
        return (
            BLOCKER_MAPPING_INCOMPLETE,
            NEXT_SCHEMA_DOC_PARSE_REPAIR,
            False,
            "SoccerTrack schema-to-adapter mapping is incomplete; repair parser/mapping before sample fixture materialization.",
        )
    return (
        None,
        NEXT_MATERIALIZATION_APPROVAL,
        True,
        "SoccerTrack sample ingestion contract is ready. Advance to fixture materialization approval; no sample, dataset, training, promotion, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "schema_doc_parse_missing", "selected": primary_blocker == BLOCKER_PARSE_MISSING, "primaryBlocker": BLOCKER_PARSE_MISSING, "nextRecommendedNextLever": NEXT_SCHEMA_DOC_PARSE},
            {"condition": "sample_mapping_incomplete", "selected": primary_blocker == BLOCKER_MAPPING_INCOMPLETE, "primaryBlocker": BLOCKER_MAPPING_INCOMPLETE, "nextRecommendedNextLever": NEXT_SCHEMA_DOC_PARSE_REPAIR},
            {"condition": "sample_ingestion_contract_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_MATERIALIZATION_APPROVAL},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Sample Ingestion Contract Prep",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected sample resource: `{summary.get('selectedSampleResourceId')}`",
            f"- Sample download approval required: `{summary.get('sampleDownloadApprovalRequired')}`",
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


def run_football_external_soccertrack_sample_ingestion_contract_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_sample_ingestion_contract_prep",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    parse_ready = _parse_ready(inputs.get("parseSummary"), inputs.get("parsedContract"))
    parsed_contract = inputs.get("parsedContract") if isinstance(inputs.get("parsedContract"), dict) else {}
    mapping_plan = inputs.get("mappingPlan") if isinstance(inputs.get("mappingPlan"), dict) else {}
    mapping_audit = _mapping_audit(mapping_plan)
    guardrail = _download_guardrail(inputs.get("parseSummary"), parsed_contract, mapping_plan)
    primary_blocker, next_lever, goal_achieved, english = _classify(parse_ready, guardrail, mapping_audit)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    contract = _ingestion_contract(parsed_contract, mapping_audit)
    sample_selection = _sample_selection_plan()
    fixture_plan = _fixture_plan(parsed_contract)
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_sample_ingestion_contract_prep",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_schema_doc_parse",
        "sampleIngestionContractReady": goal_achieved,
        "selectedSampleResourceId": "soccertrack_v2",
        "requiredTaskFixtures": ["gsr", "bas", "mot"],
        "mappingCompletenessPassed": mapping_audit["mappingCompletenessPassed"],
        "sampleDownloadApprovalRequired": True,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadApproved": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadApproved": False,
        "fullDatasetDownloadExecuted": False,
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
    batch_outcome = {
        "summary": summary,
        "soccertrackSampleIngestionContract": contract,
        "soccertrackSampleFixtureMaterializationPlan": fixture_plan,
        "soccertrackSampleSelectionPlan": sample_selection,
        "schemaToAdapterMappingAudit": mapping_audit,
        "downloadScopeGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_sample_ingestion_contract_prep_summary.json", summary)
    _write_json(output_root / "soccertrack_sample_ingestion_contract.json", contract)
    _write_json(output_root / "soccertrack_sample_fixture_materialization_plan.json", fixture_plan)
    _write_json(output_root / "soccertrack_sample_selection_plan.json", sample_selection)
    _write_json(output_root / "schema_to_adapter_mapping_audit.json", mapping_audit)
    _write_json(output_root / "download_scope_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare SoccerTrack sample ingestion/materialization contract without downloads.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_sample_ingestion_contract_prep")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_sample_ingestion_contract_prep(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
