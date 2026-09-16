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
DEFAULT_ACCESS_REVIEW_DIR_NAME = "football_external_dataset_access_review_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_nda_api_access_approval_v1"

BLOCKER_MANUAL_AUDIT_MISSING = "football_external_soccernet_manual_audit_missing"
BLOCKER_RESOURCE_MISSING = "football_external_soccernet_resource_missing"

NEXT_DATASET_ACCESS_REVIEW = "football_external_dataset_access_review"
NEXT_API_METADATA_PROBE = "football_external_soccernet_api_metadata_probe"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_nda_api_access_approval",
            "successCriteria": [
                "convert manual/gated SoccerNet resource into secretless API access contract",
                "do not persist the NDA password",
                "approve metadata/listing probe only, not full original-video download",
            ],
            "failureAdaptation": "If the manual access audit is missing, return to dataset access review.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_access_contract_repair",
            "successCriteria": [
                "repair missing SoccerNet resource metadata",
                "preserve research-only and no-commercial-use caveats",
                "keep credentials out of artifacts",
            ],
            "failureAdaptation": "If SoccerNet access cannot be represented safely, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_access_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not download videos or labels",
            ],
            "failureAdaptation": "Stop before using the SoccerNet API.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    access_root = candidate_root / DEFAULT_ACCESS_REVIEW_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "manualAudit": _load_json(access_root / "manual_or_gated_access_audit.json"),
    }


def _soccernet_resource(manual_audit: dict[str, Any] | None) -> dict[str, Any] | None:
    resources = (manual_audit or {}).get("manualOrGatedResources")
    if not isinstance(resources, list):
        return None
    for resource in resources:
        if isinstance(resource, dict) and resource.get("resourceId") == "soccernet_broadcast_tasks":
            return dict(resource)
    return None


def _classify(manual_audit: dict[str, Any] | None, resource: dict[str, Any] | None) -> tuple[str | None, str, bool, str]:
    if not isinstance(manual_audit, dict):
        return (
            BLOCKER_MANUAL_AUDIT_MISSING,
            NEXT_DATASET_ACCESS_REVIEW,
            False,
            "SoccerNet manual/gated access audit is missing; rerun dataset access review.",
        )
    if resource is None:
        return (
            BLOCKER_RESOURCE_MISSING,
            NEXT_DATASET_ACCESS_REVIEW,
            False,
            "SoccerNet broadcast task resource is missing from manual/gated access audit.",
        )
    return (
        None,
        NEXT_API_METADATA_PROBE,
        True,
        "SoccerNet NDA/API access is represented as a secretless metadata-probe contract. Use the password only from SOCCERNET_PASSWORD or an interactive prompt; do not persist it.",
    )


def _api_contract(resource: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "resourceId": "soccernet_broadcast_tasks",
        "resourceName": (resource or {}).get("resourceName") or "SoccerNet broadcast tasks",
        "officialSourceUrls": (resource or {}).get("officialSourceUrls") or ["https://www.soccer-net.org/"],
        "pipInstallCommand": "python3 -m pip install SoccerNet --upgrade",
        "pythonPackageName": "SoccerNet",
        "credentialEnvVar": "SOCCERNET_PASSWORD",
        "credentialPromptAllowed": True,
        "credentialPersisted": False,
        "passwordRedacted": True,
        "approvedProbeScope": "api_metadata_or_listing_only",
        "fullOriginalVideoDownloadApproved": False,
        "labelDownloadApproved": False,
        "trainingUseAllowed": False,
        "commercialUseAllowed": False,
        "researchOnly": True,
        "ndaGated": True,
        "coveredStages": (resource or {}).get("coveredStages") or [],
    }


def _credential_audit() -> dict[str, Any]:
    return {
        "credentialReceivedInSession": True,
        "credentialPersisted": False,
        "passwordRedacted": True,
        "credentialStoragePolicy": "Do not write the SoccerNet password to artifacts, git, logs, or command lines. Future commands must read SOCCERNET_PASSWORD from the process environment or prompt interactively.",
        "artifactContainsSecret": False,
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet NDA API Access Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- NDA access available: `{summary.get('soccernetNdaAccessAvailable')}`",
            f"- Credential persisted: `{summary.get('credentialPersisted')}`",
            f"- Password redacted: `{summary.get('passwordRedacted')}`",
            f"- Controlled API metadata probe ready: `{summary.get('controlledApiMetadataProbeReady')}`",
            f"- Full original video download approved: `{summary.get('fullOriginalVideoDownloadApproved')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_nda_api_access_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_nda_api_access_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    resource = _soccernet_resource(inputs["manualAudit"])
    primary_blocker, next_lever, goal_achieved, english = _classify(inputs["manualAudit"], resource)
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    contract = _api_contract(resource)
    credential_audit = _credential_audit()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_nda_api_access_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_dataset_access_review",
        "soccernetNdaAccessAvailable": goal_achieved,
        "credentialPersisted": False,
        "passwordRedacted": True,
        "controlledApiMetadataProbeReady": goal_achieved,
        "fullOriginalVideoDownloadApproved": False,
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
            {"condition": "manual_audit_missing", "selected": primary_blocker == BLOCKER_MANUAL_AUDIT_MISSING, "nextRecommendedNextLever": NEXT_DATASET_ACCESS_REVIEW},
            {"condition": "soccernet_resource_missing", "selected": primary_blocker == BLOCKER_RESOURCE_MISSING, "nextRecommendedNextLever": NEXT_DATASET_ACCESS_REVIEW},
            {"condition": "soccernet_api_metadata_probe_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_API_METADATA_PROBE},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "soccernetApiAccessContract": contract,
        "credentialHandlingAudit": credential_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "soccernet_nda_api_access_approval_summary.json", summary)
    _write_json(output_root / "soccernet_api_access_contract.json", contract)
    _write_json(output_root / "credential_handling_audit.json", credential_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Represent SoccerNet NDA/API access without persisting credentials.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_nda_api_access_approval")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccernet_nda_api_access_approval(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
