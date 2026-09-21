from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_METADATA_DIR_NAME = "football_external_soccernet_api_metadata_probe_v1"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_nda_api_access_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_api_listing_probe_v1"

BLOCKER_METADATA_MISSING = "football_external_soccernet_api_metadata_probe_missing"
BLOCKER_CREDENTIAL_MISSING = "football_external_soccernet_api_listing_credential_missing"
BLOCKER_LISTING_EMPTY = "football_external_soccernet_api_listing_empty"

NEXT_METADATA_PROBE = "football_external_soccernet_api_metadata_probe"
NEXT_SECRET_SETUP = "football_external_soccernet_secret_env_setup"
NEXT_LISTING_REPAIR = "football_external_soccernet_api_listing_contract_repair"
NEXT_LABEL_METADATA_PROBE = "football_external_soccernet_controlled_label_metadata_probe"

LISTING_TASKS = ("spotting", "spotting-ball", "camera-changes", "frames", "caption")
LISTING_SPLITS = ("train", "valid", "test", "challenge")



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_api_local_index_listing_probe",
            "successCriteria": [
                "read SoccerNet package-local game indexes",
                "record task/split counts and sample game refs",
                "require runtime credential presence without persisting it",
                "do not download videos, labels, features, datasets, or train models",
            ],
            "failureAdaptation": "If package-local listing is empty or unavailable, repair the listing contract before any downloads.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_api_listing_contract_repair",
            "successCriteria": [
                "repair package python path or task/split list selection",
                "keep listing-only scope and secret redaction",
            ],
            "failureAdaptation": "If listing still cannot run safely, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_api_listing_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not download SoccerNet data",
            ],
            "failureAdaptation": "Stop before label/video access.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    metadata_root = candidate_root / DEFAULT_METADATA_DIR_NAME
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "metadataSummary": _load_json(metadata_root / "soccernet_api_metadata_probe_summary.json"),
        "packageAudit": _load_json(metadata_root / "soccernet_api_package_audit.json"),
        "accessContract": _load_json(approval_root / "soccernet_api_access_contract.json"),
    }


def _metadata_ready(metadata_summary: dict[str, Any] | None, package_audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(metadata_summary, dict)
        and metadata_summary.get("goalAchieved") is True
        and metadata_summary.get("apiPackageImportReady") is True
        and metadata_summary.get("apiDownloaderImportReady") is True
        and metadata_summary.get("credentialPersisted") is False
        and metadata_summary.get("passwordRedacted") is True
        and isinstance(package_audit, dict)
        and package_audit.get("packageImportReady") is True
    )


def _credential_audit(env: Mapping[str, str], credential_env_var: str) -> dict[str, Any]:
    value = env.get(credential_env_var)
    return {
        "credentialEnvVar": credential_env_var,
        "credentialRuntimeAvailable": bool(value),
        "credentialPersisted": False,
        "passwordRedacted": True,
        "artifactContainsSecret": False,
        "credentialLength": len(value) if value else 0,
    }


def _default_listing_probe(python_executable: Path | None) -> dict[str, Any]:
    executable = Path(python_executable) if python_executable else Path(sys.executable)
    probe_code = f"""
import json
from SoccerNet.utils import getListGames

tasks = {list(LISTING_TASKS)!r}
splits = {list(LISTING_SPLITS)!r}
task_split_counts = {{}}
sample_game_refs = {{}}
errors = []
total = 0
for task in tasks:
    task_split_counts[task] = {{}}
    sample_game_refs[task] = {{}}
    for split in splits:
        try:
            games = getListGames(split, task=task)
            task_split_counts[task][split] = len(games)
            sample_game_refs[task][split] = games[:3]
            total += len(games)
        except Exception as exc:
            task_split_counts[task][split] = 0
            sample_game_refs[task][split] = []
            errors.append({{"task": task, "split": split, "errorType": type(exc).__name__, "message": str(exc)}})
print(json.dumps({{
    "listingSource": "package_local_index",
    "networkApiCallExecuted": False,
    "listedTaskCount": len([task for task, split_counts in task_split_counts.items() if sum(split_counts.values()) > 0]),
    "totalListedGameRefs": total,
    "taskSplitCounts": task_split_counts,
    "sampleGameRefs": sample_game_refs,
    "listingErrors": errors,
}}))
"""
    completed = subprocess.run(
        [str(executable), "-c", probe_code],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {
            "listingSource": "package_local_index",
            "networkApiCallExecuted": False,
            "listedTaskCount": 0,
            "totalListedGameRefs": 0,
            "taskSplitCounts": {},
            "sampleGameRefs": {},
            "listingErrors": [
                {
                    "errorType": "SubprocessFailure",
                    "returncode": completed.returncode,
                    "stderrTail": completed.stderr[-1200:],
                }
            ],
        }
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("SoccerNet listing probe did not return a JSON object")
    return payload


def _classify(
    *,
    metadata_ready: bool,
    credential_audit: dict[str, Any],
    listing_audit: dict[str, Any] | None,
) -> tuple[str | None, str, bool, str]:
    if not metadata_ready:
        return (
            BLOCKER_METADATA_MISSING,
            NEXT_METADATA_PROBE,
            False,
            "SoccerNet metadata/package probe truth is missing or not passed.",
        )
    if not credential_audit["credentialRuntimeAvailable"]:
        return (
            BLOCKER_CREDENTIAL_MISSING,
            NEXT_SECRET_SETUP,
            False,
            "SOCCERNET_PASSWORD is not available at runtime. Refusing listing probe without persisting the credential.",
        )
    if not listing_audit or int(listing_audit.get("totalListedGameRefs") or 0) <= 0:
        return (
            BLOCKER_LISTING_EMPTY,
            NEXT_LISTING_REPAIR,
            False,
            "SoccerNet package-local game listing returned no usable game references.",
        )
    return (
        None,
        NEXT_LABEL_METADATA_PROBE,
        True,
        "SoccerNet package-local listing probe passed. Advance to a controlled label-metadata probe before any original-video download.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet API Listing Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Listing source: `{summary.get('listingSource')}`",
            f"- Listed task count: `{summary.get('listedTaskCount')}`",
            f"- Total listed game refs: `{summary.get('totalListedGameRefs')}`",
            f"- Network API call executed: `{summary.get('networkApiCallExecuted')}`",
            f"- API listing executed: `{summary.get('apiListingExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_api_listing_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_api_local_index_listing_probe",
    env: Mapping[str, str] | None = None,
    listing_probe: Callable[[Path | None], dict[str, Any]] = _default_listing_probe,
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    credential_env_var = str((inputs["accessContract"] or {}).get("credentialEnvVar") or "SOCCERNET_PASSWORD")
    credential_audit = _credential_audit(env or os.environ, credential_env_var)
    metadata_ready = _metadata_ready(inputs["metadataSummary"], inputs["packageAudit"])
    python_executable_value = (inputs["packageAudit"] or {}).get("pythonExecutable")
    python_executable = Path(str(python_executable_value)) if python_executable_value else None

    listing_audit: dict[str, Any] | None = None
    if metadata_ready and credential_audit["credentialRuntimeAvailable"]:
        listing_audit = listing_probe(python_executable)

    primary_blocker, next_lever, goal_achieved, english = _classify(
        metadata_ready=metadata_ready,
        credential_audit=credential_audit,
        listing_audit=listing_audit,
    )
    generated_at = utc_now_iso()
    attempts = _attempt_plan()
    listing_audit = listing_audit or {
        "listingSource": "not_executed",
        "networkApiCallExecuted": False,
        "listedTaskCount": 0,
        "totalListedGameRefs": 0,
        "taskSplitCounts": {},
        "sampleGameRefs": {},
        "listingErrors": [],
    }
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_api_listing_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_api_metadata_probe",
        "apiMetadataProbeReady": metadata_ready,
        "credentialRuntimeAvailable": credential_audit["credentialRuntimeAvailable"],
        "credentialPersisted": False,
        "passwordRedacted": True,
        "apiListingExecuted": goal_achieved,
        "listingSource": listing_audit.get("listingSource"),
        "networkApiCallExecuted": listing_audit.get("networkApiCallExecuted") is True,
        "listedTaskCount": int(listing_audit.get("listedTaskCount") or 0),
        "totalListedGameRefs": int(listing_audit.get("totalListedGameRefs") or 0),
        "listingErrorCount": len(listing_audit.get("listingErrors") or []),
        "apiCallExecuted": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadExecuted": False,
        "labelDownloadExecuted": False,
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
            {"condition": "metadata_probe_missing", "selected": primary_blocker == BLOCKER_METADATA_MISSING, "nextRecommendedNextLever": NEXT_METADATA_PROBE},
            {"condition": "api_listing_credential_missing", "selected": primary_blocker == BLOCKER_CREDENTIAL_MISSING, "nextRecommendedNextLever": NEXT_SECRET_SETUP},
            {"condition": "api_listing_empty", "selected": primary_blocker == BLOCKER_LISTING_EMPTY, "nextRecommendedNextLever": NEXT_LISTING_REPAIR},
            {"condition": "label_metadata_probe_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_LABEL_METADATA_PROBE},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "credentialRuntimeAudit": credential_audit,
        "soccernetApiListingAudit": listing_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "soccernet_api_listing_probe_summary.json", summary)
    _write_json(output_root / "credential_runtime_audit.json", credential_audit)
    _write_json(output_root / "soccernet_api_listing_audit.json", listing_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List SoccerNet package-local game indexes without downloads.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_api_local_index_listing_probe")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccernet_api_listing_probe(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
