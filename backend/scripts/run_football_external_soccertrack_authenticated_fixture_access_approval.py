from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
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
DEFAULT_SOURCE_REVIEW_DIR_NAME = "football_external_soccertrack_fixture_source_access_review_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_authenticated_fixture_access_approval_v1"

BLOCKER_SOURCE_REVIEW_MISSING = "football_external_soccertrack_fixture_source_access_review_missing"
BLOCKER_CREDENTIAL_MISSING = "football_external_soccertrack_authenticated_fixture_credential_missing"

NEXT_SOURCE_REVIEW = "football_external_soccertrack_fixture_source_access_review"
NEXT_CREDENTIAL_SETUP = "football_external_soccertrack_authenticated_fixture_credential_setup"
NEXT_AUTH_TREE_PROBE = "football_external_soccertrack_authenticated_fixture_tree_probe"

CREDENTIAL_ENV_NAMES = ["HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_authenticated_fixture_access_approval",
            "successCriteria": [
                "approve authenticated fixture tree probe only when runtime credential exists",
                "do not persist credential values",
                "keep sample download, full dataset download, training, promotion, and runtime mutation closed",
            ],
            "failureAdaptation": "If credential is missing, write setup blocker truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_authenticated_credential_contract_repair",
            "successCriteria": [
                "repair credential environment contract without exposing secrets",
                "preserve no-download state",
            ],
            "failureAdaptation": "If credential remains unavailable, write blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_authenticated_access_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not download data, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Stop until authenticated runtime credential is available.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    review_root = candidate_root / DEFAULT_SOURCE_REVIEW_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "reviewRoot": review_root,
        "reviewSummary": _load_json(review_root / "fixture_source_access_review_summary.json"),
        "approvalPlan": _load_json(review_root / "authenticated_fixture_access_approval_plan.json"),
    }


def _source_review_ready(summary: dict[str, Any] | None, approval_plan: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("fixtureSourceAccessReviewReady") is True
        and summary.get("huggingFaceAuthRequired") is True
        and summary.get("sampleDownloadExecuted") is False
        and summary.get("datasetDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(approval_plan, dict)
        and approval_plan.get("approvalRequiredBeforeAuthenticatedAccess") is True
    )


def _credential_status() -> dict[str, Any]:
    available_names = [name for name in CREDENTIAL_ENV_NAMES if os.environ.get(name)]
    selected = available_names[0] if available_names else None
    return {
        "schemaVersion": "soccertrack_authenticated_fixture_credential_status_v1",
        "generatedAt": _utc_now_iso(),
        "credentialRuntimeAvailable": selected is not None,
        "selectedCredentialEnvVar": selected,
        "credentialEnvVarNamesChecked": CREDENTIAL_ENV_NAMES,
        "credentialPersisted": False,
        "credentialValueCaptured": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _classify(source_ready: bool, credential: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not source_ready:
        return (
            BLOCKER_SOURCE_REVIEW_MISSING,
            NEXT_SOURCE_REVIEW,
            False,
            "Authenticated fixture access approval requires completed source-access review truth first.",
        )
    if credential.get("credentialRuntimeAvailable") is not True:
        return (
            BLOCKER_CREDENTIAL_MISSING,
            NEXT_CREDENTIAL_SETUP,
            False,
            "Authenticated SoccerTrack fixture access needs a runtime Hugging Face credential; no credential is currently available.",
        )
    return (
        None,
        NEXT_AUTH_TREE_PROBE,
        True,
        "Authenticated fixture tree probe is approved using a runtime credential. No sample, dataset, training, promotion, or runtime mutation was executed.",
    )


def _approval_contract(credential: dict[str, Any], approved: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_authenticated_fixture_access_approval_contract_v1",
        "generatedAt": _utc_now_iso(),
        "authenticatedFixtureAccessApproved": approved,
        "approvedCredentialEnvVar": credential.get("selectedCredentialEnvVar") if approved else None,
        "credentialPersisted": False,
        "credentialValueCaptured": False,
        "approvedUse": "one_match_fixture_tree_probe_only" if approved else None,
        "sampleDownloadApproved": approved,
        "sampleDownloadExecuted": False,
        "datasetDownloadApproved": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadApproved": False,
        "fullDatasetDownloadExecuted": False,
        "trainingUseApproved": False,
        "trainingExecuted": False,
    }


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "source_review_missing", "selected": primary_blocker == BLOCKER_SOURCE_REVIEW_MISSING, "primaryBlocker": BLOCKER_SOURCE_REVIEW_MISSING, "nextRecommendedNextLever": NEXT_SOURCE_REVIEW},
            {"condition": "credential_missing", "selected": primary_blocker == BLOCKER_CREDENTIAL_MISSING, "primaryBlocker": BLOCKER_CREDENTIAL_MISSING, "nextRecommendedNextLever": NEXT_CREDENTIAL_SETUP},
            {"condition": "authenticated_access_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_AUTH_TREE_PROBE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Authenticated Fixture Access Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Authenticated fixture access approved: `{summary.get('authenticatedFixtureAccessApproved')}`",
            f"- Credential runtime available: `{summary.get('credentialRuntimeAvailable')}`",
            f"- Credential persisted: `{summary.get('credentialPersisted')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_authenticated_fixture_access_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_authenticated_fixture_access_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    source_ready = _source_review_ready(inputs.get("reviewSummary"), inputs.get("approvalPlan"))
    credential = _credential_status()
    primary_blocker, next_lever, goal_achieved, english = _classify(source_ready, credential)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    contract = _approval_contract(credential, goal_achieved)
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_authenticated_fixture_access_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_fixture_source_access_review",
        "authenticatedFixtureAccessApproved": goal_achieved,
        "credentialRuntimeAvailable": credential["credentialRuntimeAvailable"],
        "credentialPersisted": False,
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
        "authenticatedFixtureAccessApprovalContract": contract,
        "credentialStatusAudit": credential,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "authenticated_fixture_access_approval_summary.json", summary)
    _write_json(output_root / "authenticated_fixture_access_approval_contract.json", contract)
    _write_json(output_root / "credential_status_audit.json", credential)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve authenticated SoccerTrack fixture access when runtime credential exists.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_authenticated_fixture_access_approval")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_authenticated_fixture_access_approval(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
