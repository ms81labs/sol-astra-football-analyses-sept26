from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_CONTRACT_DIR_NAME = "football_external_soccertrack_sample_ingestion_contract_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_sample_fixture_materialization_approval_v1"

BLOCKER_CONTRACT_MISSING = "football_external_soccertrack_sample_ingestion_contract_missing"
BLOCKER_GUARDRAIL_FAILED = "football_external_soccertrack_sample_fixture_approval_guardrail_failed"

NEXT_CONTRACT_PREP = "football_external_soccertrack_sample_ingestion_contract_prep"
NEXT_CONTROLLED_SAMPLE_FETCH = "football_external_soccertrack_controlled_sample_fetch"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_sample_fixture_materialization_approval",
            "successCriteria": [
                "approve only a bounded SoccerTrack fixture/materialization sample scope",
                "explicitly keep full dataset download, training, promotion, and runtime mutation closed",
                "route to controlled sample fetch only",
            ],
            "failureAdaptation": "If contract or guardrails are incomplete, return to contract prep.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_sample_fixture_approval_contract_repair",
            "successCriteria": [
                "repair approval contract fields from generated contract-prep truth",
                "preserve no execution state",
            ],
            "failureAdaptation": "If approval cannot stay bounded, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_sample_fixture_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not download external data, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Stop before controlled sample fetch until approval contract is safe.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    contract_root = candidate_root / DEFAULT_CONTRACT_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "contractRoot": contract_root,
        "contractSummary": _load_json(contract_root / "soccertrack_sample_ingestion_contract_prep_summary.json"),
        "ingestionContract": _load_json(contract_root / "soccertrack_sample_ingestion_contract.json"),
        "fixturePlan": _load_json(contract_root / "soccertrack_sample_fixture_materialization_plan.json"),
        "downloadGuardrail": _load_json(contract_root / "download_scope_guardrail_audit.json"),
    }


def _contract_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None, fixture_plan: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("sampleIngestionContractReady") is True
        and summary.get("sampleDownloadExecuted") is False
        and summary.get("datasetDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(contract, dict)
        and contract.get("selectedSampleResourceId") == "soccertrack_v2"
        and contract.get("schemaToAdapterMappingReady") is True
        and contract.get("sampleDownloadExecuted") is False
        and contract.get("datasetDownloadExecuted") is False
        and contract.get("trainingUseAllowed") is False
        and isinstance(fixture_plan, dict)
        and fixture_plan.get("materializationExecuted") is False
        and fixture_plan.get("approvalRequiredBeforeMaterialization") is True
    )


def _approval_guardrail(summary: dict[str, Any] | None, guardrail: dict[str, Any] | None) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if isinstance(guardrail, dict) and guardrail.get("downloadScopeGuardrailPassed") is not True:
        violations.append({"scope": "contractPrepGuardrail", "field": "downloadScopeGuardrailPassed"})
    for scope, payload in [("contractSummary", summary), ("downloadGuardrail", guardrail)]:
        if not isinstance(payload, dict):
            continue
        for field in ["sampleDownloadExecuted", "datasetDownloadExecuted", "trainingExecuted"]:
            if payload.get(field) is True:
                violations.append({"scope": scope, "field": field})
    return {
        "schemaVersion": "soccertrack_sample_fixture_approval_guardrail_audit_v1",
        "generatedAt": _utc_now_iso(),
        "approvalGuardrailPassed": not violations,
        "violationCount": len(violations),
        "violations": violations,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _approval_contract() -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_sample_fixture_materialization_approval_contract_v1",
        "generatedAt": _utc_now_iso(),
        "selectedSampleResourceId": "soccertrack_v2",
        "approvedUse": "adapter_fixture_materialization_only",
        "sampleFixtureMaterializationApproved": True,
        "sampleDownloadApproved": True,
        "sampleDownloadExecuted": False,
        "datasetDownloadApproved": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadApproved": False,
        "fullDatasetDownloadExecuted": False,
        "trainingUseApproved": False,
        "trainingExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _approved_scope() -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_approved_sample_scope_v1",
        "generatedAt": _utc_now_iso(),
        "selectedSampleResourceId": "soccertrack_v2",
        "maxSampleMatches": 1,
        "requiredTaskFixtures": ["gsr", "bas", "mot"],
        "allowedFilesOrFolders": [
            "one match-level GSR fixture",
            "one match-level BAS fixture",
            "one match-level MOT fixture if available",
            "metadata required to map the selected fixture",
        ],
        "disallowedScopes": [
            "full dataset download",
            "training data generation",
            "runtime candidate evaluation",
            "promotion or runtime-default mutation",
        ],
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _classify(contract_ready: bool, guardrail: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not contract_ready:
        return (
            BLOCKER_CONTRACT_MISSING,
            NEXT_CONTRACT_PREP,
            False,
            "SoccerTrack sample ingestion contract is missing or unsafe; rerun contract prep before approval.",
        )
    if guardrail.get("approvalGuardrailPassed") is not True:
        return (
            BLOCKER_GUARDRAIL_FAILED,
            NEXT_CONTRACT_PREP,
            False,
            "SoccerTrack fixture materialization approval guardrail failed; repair contract prep before controlled fetch.",
        )
    return (
        None,
        NEXT_CONTROLLED_SAMPLE_FETCH,
        True,
        "SoccerTrack fixture materialization approval is ready. Advance to controlled sample fetch; no sample, dataset, training, promotion, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "sample_ingestion_contract_missing", "selected": primary_blocker == BLOCKER_CONTRACT_MISSING, "primaryBlocker": BLOCKER_CONTRACT_MISSING, "nextRecommendedNextLever": NEXT_CONTRACT_PREP},
            {"condition": "approval_guardrail_failed", "selected": primary_blocker == BLOCKER_GUARDRAIL_FAILED, "primaryBlocker": BLOCKER_GUARDRAIL_FAILED, "nextRecommendedNextLever": NEXT_CONTRACT_PREP},
            {"condition": "fixture_materialization_approval_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_CONTROLLED_SAMPLE_FETCH},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Sample Fixture Materialization Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Sample fixture materialization approved: `{summary.get('sampleFixtureMaterializationApproved')}`",
            f"- Sample download approved: `{summary.get('sampleDownloadApproved')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download approved: `{summary.get('datasetDownloadApproved')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_sample_fixture_materialization_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_sample_fixture_materialization_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    contract_ready = _contract_ready(inputs.get("contractSummary"), inputs.get("ingestionContract"), inputs.get("fixturePlan"))
    guardrail = _approval_guardrail(inputs.get("contractSummary"), inputs.get("downloadGuardrail"))
    primary_blocker, next_lever, goal_achieved, english = _classify(contract_ready, guardrail)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    contract = _approval_contract()
    scope = _approved_scope()
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_sample_fixture_materialization_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_sample_ingestion_contract_prep",
        "selectedSampleResourceId": "soccertrack_v2",
        "sampleFixtureMaterializationApproved": goal_achieved,
        "sampleDownloadApproved": goal_achieved,
        "sampleDownloadExecuted": False,
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
        "soccertrackSampleFixtureMaterializationApprovalContract": contract,
        "approvedSampleScope": scope,
        "approvalGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "sample_fixture_materialization_approval_summary.json", summary)
    _write_json(output_root / "soccertrack_sample_fixture_materialization_approval_contract.json", contract)
    _write_json(output_root / "approved_sample_scope.json", scope)
    _write_json(output_root / "approval_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve bounded SoccerTrack sample fixture materialization without executing fetch.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_sample_fixture_materialization_approval")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_sample_fixture_materialization_approval(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
