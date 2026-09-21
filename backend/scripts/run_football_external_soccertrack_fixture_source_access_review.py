from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_FETCH_DIR_NAME = "football_external_soccertrack_controlled_sample_fetch_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_fixture_source_access_review_v1"

BLOCKER_REVIEW_NOT_REQUIRED = "football_external_soccertrack_fixture_source_review_not_required"

NEXT_CONTROLLED_FETCH = "football_external_soccertrack_controlled_sample_fetch"
NEXT_AUTH_APPROVAL = "football_external_soccertrack_authenticated_fixture_access_approval"
NEXT_PUBLIC_HF_TREE = "football_external_soccertrack_huggingface_fixture_tree_probe"

HF_DATASET_API = "https://huggingface.co/api/datasets/atomscott/soccertrack-v2"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_fixture_source_access_review",
            "successCriteria": [
                "review why public GitHub fixture fetch failed",
                "probe Hugging Face access without credentials or download",
                "select the next bounded source-access family",
            ],
            "failureAdaptation": "If source access is unclear, repair source locator evidence.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_fixture_source_locator_repair",
            "successCriteria": [
                "repair public source locator metadata",
                "keep all data downloads blocked",
            ],
            "failureAdaptation": "If no safe source path is identified, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_fixture_access_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not download data, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Stop until authenticated/manual source access is available.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fetch_root = candidate_root / DEFAULT_FETCH_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fetchRoot": fetch_root,
        "fetchSummary": _load_json(fetch_root / "controlled_sample_fetch_summary.json"),
        "sourceTreeAudit": _load_json(fetch_root / "source_tree_fixture_audit.json"),
    }


def _review_required(fetch_summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(fetch_summary, dict)
        and fetch_summary.get("primaryBlocker") == "football_external_soccertrack_public_fixture_files_missing"
        and fetch_summary.get("sourceTreeProbeExecuted") is True
        and fetch_summary.get("controlledSampleFetchExecuted") is False
        and fetch_summary.get("sampleDownloadExecuted") is False
        and fetch_summary.get("datasetDownloadExecuted") is False
        and fetch_summary.get("trainingExecuted") is False
    )


def _default_hf_probe() -> dict[str, Any]:
    request = Request(HF_DATASET_API, headers={"User-Agent": "fotball-analyst-soccertrack-access-review/1.0"})
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - metadata/access probe only.
            payload = json.loads(response.read().decode("utf-8"))
        siblings = payload.get("siblings") if isinstance(payload, dict) else None
        return {
            "statusCode": 200,
            "accessible": True,
            "authRequired": False,
            "siblingCount": len(siblings) if isinstance(siblings, list) else None,
        }
    except HTTPError as exc:
        return {"statusCode": exc.code, "accessible": False, "authRequired": exc.code in {401, 403}}
    except Exception as exc:  # pragma: no cover - network environment path.
        return {"statusCode": None, "accessible": False, "authRequired": None, "error": str(exc)}


def _credential_audit() -> dict[str, Any]:
    env_names = ["HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"]
    available = [name for name in env_names if os.environ.get(name)]
    return {
        "schemaVersion": "soccertrack_fixture_credential_availability_audit_v1",
        "generatedAt": _utc_now_iso(),
        "credentialRuntimeAvailable": bool(available),
        "credentialEnvVarNamesPresent": available,
        "credentialPersisted": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _source_matrix(source_tree_audit: dict[str, Any] | None, hf: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
    hf_auth = hf.get("authRequired") is True
    return {
        "schemaVersion": "soccertrack_fixture_source_access_matrix_v1",
        "generatedAt": _utc_now_iso(),
        "sources": [
            {
                "sourceId": "github_public_tree",
                "url": "https://github.com/AtomScott/SoccerTrack-v2",
                "fixtureAvailable": bool((source_tree_audit or {}).get("completeOneMatchFixtureFound")),
                "accessClass": "public_metadata_and_docs_only",
                "selected": False,
            },
            {
                "sourceId": "huggingface_dataset",
                "url": "https://huggingface.co/datasets/atomscott/soccertrack-v2",
                "accessibleWithoutCredential": hf.get("accessible") is True,
                "authRequired": hf_auth,
                "credentialRuntimeAvailable": credentials.get("credentialRuntimeAvailable") is True,
                "selected": hf.get("accessible") is True or hf_auth,
            },
            {
                "sourceId": "google_drive_dataset_distribution",
                "url": "declared_in_soccertrack_readme",
                "accessibleWithoutCredential": None,
                "authRequired": "manual_review_required",
                "selected": False,
            },
        ],
        "recommendedAccessFamily": "public_huggingface_fixture_tree_probe" if hf.get("accessible") is True else "authenticated_huggingface_or_google_drive_fixture_access",
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _approval_plan(hf: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_authenticated_fixture_access_approval_plan_v1",
        "generatedAt": _utc_now_iso(),
        "approvalRequiredBeforeAuthenticatedAccess": True,
        "credentialRuntimeAvailable": credentials.get("credentialRuntimeAvailable") is True,
        "huggingFaceAuthRequired": hf.get("authRequired") is True,
        "allowedFutureScope": "one_match_gsr_bas_mot_fixture_locator_or_fetch_only",
        "disallowedFutureScope": [
            "full dataset download without separate approval",
            "video/media download unless explicitly bounded",
            "training data generation",
            "runtime mutation",
        ],
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _classify(review_required: bool, hf: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not review_required:
        return (
            BLOCKER_REVIEW_NOT_REQUIRED,
            NEXT_CONTROLLED_FETCH,
            False,
            "Fixture source access review is not required because the prior controlled fetch did not prove the public-fixture blocker.",
        )
    if hf.get("accessible") is True:
        return (
            None,
            NEXT_PUBLIC_HF_TREE,
            True,
            "Public GitHub lacks fixtures, but Hugging Face metadata is accessible. Advance to bounded Hugging Face fixture tree probe; no downloads executed.",
        )
    return (
        None,
        NEXT_AUTH_APPROVAL,
        True,
        "Public GitHub lacks fixtures and Hugging Face requires authentication. Advance to authenticated fixture access approval; no downloads executed.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "review_not_required", "selected": primary_blocker == BLOCKER_REVIEW_NOT_REQUIRED, "primaryBlocker": BLOCKER_REVIEW_NOT_REQUIRED, "nextRecommendedNextLever": NEXT_CONTROLLED_FETCH},
            {"condition": "public_huggingface_accessible", "selected": goal_achieved and next_lever == NEXT_PUBLIC_HF_TREE, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PUBLIC_HF_TREE},
            {"condition": "authenticated_access_required", "selected": goal_achieved and next_lever == NEXT_AUTH_APPROVAL, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_AUTH_APPROVAL},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Fixture Source Access Review",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- GitHub public fixture available: `{summary.get('githubPublicFixtureAvailable')}`",
            f"- Hugging Face auth required: `{summary.get('huggingFaceAuthRequired')}`",
            f"- Credential runtime available: `{summary.get('credentialRuntimeAvailable')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_fixture_source_access_review(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_fixture_source_access_review",
    hf_probe: Callable[[], dict[str, Any]] = _default_hf_probe,
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    review_required = _review_required(inputs.get("fetchSummary"))
    hf = hf_probe() if review_required else {"statusCode": None, "accessible": False, "authRequired": None}
    credentials = _credential_audit()
    source_matrix = _source_matrix(inputs.get("sourceTreeAudit"), hf, credentials)
    approval_plan = _approval_plan(hf, credentials)
    primary_blocker, next_lever, goal_achieved, english = _classify(review_required, hf)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_fixture_source_access_review",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_controlled_sample_fetch",
        "fixtureSourceAccessReviewReady": goal_achieved,
        "githubPublicFixtureAvailable": bool((inputs.get("sourceTreeAudit") or {}).get("completeOneMatchFixtureFound")),
        "huggingFaceStatusCode": hf.get("statusCode"),
        "huggingFaceAccessible": hf.get("accessible") is True,
        "huggingFaceAuthRequired": hf.get("authRequired") is True,
        "credentialRuntimeAvailable": credentials["credentialRuntimeAvailable"],
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "fixtureSourceAccessMatrix": source_matrix,
        "credentialAvailabilityAudit": credentials,
        "authenticatedFixtureAccessApprovalPlan": approval_plan,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "fixture_source_access_review_summary.json", summary)
    _write_json(output_root / "fixture_source_access_matrix.json", source_matrix)
    _write_json(output_root / "credential_availability_audit.json", credentials)
    _write_json(output_root / "authenticated_fixture_access_approval_plan.json", approval_plan)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review SoccerTrack fixture source access after public fixture fetch gap.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_fixture_source_access_review")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_fixture_source_access_review(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
