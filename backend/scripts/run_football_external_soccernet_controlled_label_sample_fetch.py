from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import hashlib
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
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_controlled_label_sample_fetch_approval_v1"
DEFAULT_METADATA_DIR_NAME = "football_external_soccernet_api_metadata_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_controlled_label_sample_fetch_v1"

BLOCKER_APPROVAL_MISSING = "football_external_soccernet_label_fetch_approval_missing"
BLOCKER_CREDENTIAL_MISSING = "football_external_soccernet_label_fetch_credential_missing"
BLOCKER_FETCH_FAILED = "football_external_soccernet_label_fetch_failed"

NEXT_APPROVAL = "football_external_soccernet_controlled_label_sample_fetch_approval"
NEXT_SECRET_SETUP = "football_external_soccernet_secret_env_setup"
NEXT_CONTRACT_REPAIR = "football_external_soccernet_label_fetch_contract_repair"
NEXT_LABEL_SCHEMA_PROBE = "football_external_soccernet_label_schema_probe"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_single_label_file_fetch",
            "successCriteria": [
                "download exactly one approved Labels.json file",
                "hash and inventory the fetched label file",
                "do not download videos, features, zip archives, bulk datasets, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "If fetch fails, repair the approved label contract or SoccerNet downloader path.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_label_fetch_contract_repair",
            "successCriteria": [
                "repair single label path or package python executable",
                "keep scope limited to one Labels.json file",
            ],
            "failureAdaptation": "If fetch still fails, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_label_fetch_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not broaden SoccerNet access",
            ],
            "failureAdaptation": "Stop before any video or bulk dataset access.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    metadata_root = candidate_root / DEFAULT_METADATA_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "approvalSummary": _load_json(approval_root / "label_sample_fetch_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "label_sample_fetch_approval_contract.json"),
        "packageAudit": _load_json(metadata_root / "soccernet_api_package_audit.json"),
    }


def _approval_ready(approval_summary: dict[str, Any] | None, approval_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(approval_summary, dict)
        and approval_summary.get("goalAchieved") is True
        and approval_summary.get("labelSampleFetchApproved") is True
        and approval_summary.get("labelDownloadExecuted") is False
        and approval_summary.get("fullOriginalVideoDownloadExecuted") is False
        and approval_summary.get("datasetDownloadExecuted") is False
        and isinstance(approval_contract, dict)
        and approval_contract.get("labelSampleFetchApproved") is True
        and approval_contract.get("task") == "spotting-ball"
        and approval_contract.get("files") == ["Labels.json"]
        and int(approval_contract.get("maxGameCount") or 0) == 1
        and isinstance(approval_contract.get("gameRefs"), list)
        and len(approval_contract.get("gameRefs") or []) == 1
        and approval_contract.get("videoDownloadAllowed") is False
        and approval_contract.get("featureDownloadAllowed") is False
        and approval_contract.get("datasetBulkDownloadAllowed") is False
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_fetcher(
    contract: dict[str, Any],
    output_root: Path,
    python_executable: Path | None,
    env: dict[str, str],
) -> dict[str, Any]:
    executable = Path(python_executable) if python_executable else Path(sys.executable)
    sample_root = output_root / "sample_labels"
    sample_root.mkdir(parents=True, exist_ok=True)
    game_ref = str((contract.get("gameRefs") or [""])[0])
    split = str(contract.get("split") or "valid")
    files = [str(row) for row in contract.get("files") or []]
    probe_code = """
import json
import os
from pathlib import Path
from SoccerNet.Downloader import SoccerNetDownloader

local_dir = Path(os.environ["SOCCERNET_LABEL_FETCH_OUTPUT"])
game = os.environ["SOCCERNET_LABEL_FETCH_GAME"]
split = os.environ["SOCCERNET_LABEL_FETCH_SPLIT"]
files = json.loads(os.environ["SOCCERNET_LABEL_FETCH_FILES"])
downloader = SoccerNetDownloader(LocalDirectory=str(local_dir))
downloader.password = os.environ.get("SOCCERNET_PASSWORD")
downloader.downloadGame(game=game, files=files, spl=split, verbose=False)
print(json.dumps({"downloadCallCompleted": True}))
"""
    child_env = dict(env)
    child_env.update(
        {
            "SOCCERNET_LABEL_FETCH_OUTPUT": str(sample_root),
            "SOCCERNET_LABEL_FETCH_GAME": game_ref,
            "SOCCERNET_LABEL_FETCH_SPLIT": split,
            "SOCCERNET_LABEL_FETCH_FILES": json.dumps(files),
        }
    )
    completed = subprocess.run(
        [str(executable), "-c", probe_code],
        check=False,
        capture_output=True,
        text=True,
        env=child_env,
    )
    target = sample_root / game_ref / "Labels.json"
    if completed.returncode != 0 or not target.exists():
        return {
            "fetchExecuted": True,
            "files": [],
            "failures": [
                {
                    "name": "Labels.json",
                    "gameRef": game_ref,
                    "returncode": completed.returncode,
                    "stderrTail": completed.stderr[-1200:],
                    "stdoutTail": completed.stdout[-1200:],
                    "exists": target.exists(),
                }
            ],
        }
    return {
        "fetchExecuted": True,
        "files": [
            {
                "name": "Labels.json",
                "gameRef": game_ref,
                "relativePath": str(target.relative_to(output_root)),
                "sizeBytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        ],
        "failures": [],
    }


def _classify(
    *,
    approval_ready: bool,
    credential_audit: dict[str, Any],
    fetch_audit: dict[str, Any] | None,
) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "SoccerNet label sample fetch approval is missing or unsafe.",
        )
    if not credential_audit["credentialRuntimeAvailable"]:
        return (
            BLOCKER_CREDENTIAL_MISSING,
            NEXT_SECRET_SETUP,
            False,
            "SOCCERNET_PASSWORD is not available at runtime. Refusing label fetch without persisting the credential.",
        )
    if not fetch_audit or fetch_audit.get("failures") or len(fetch_audit.get("files") or []) != 1:
        return (
            BLOCKER_FETCH_FAILED,
            NEXT_CONTRACT_REPAIR,
            False,
            "Controlled SoccerNet label fetch failed or did not produce exactly one label file.",
        )
    return (
        None,
        NEXT_LABEL_SCHEMA_PROBE,
        True,
        "Controlled single-game SoccerNet Labels.json fetch passed. Advance to label schema probe; original videos remain untouched.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Controlled Label Sample Fetch",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Label download executed: `{summary.get('labelDownloadExecuted')}`",
            f"- Downloaded label files: `{summary.get('downloadedLabelFileCount')}`",
            f"- Full original video download executed: `{summary.get('fullOriginalVideoDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_controlled_label_sample_fetch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_single_label_file_fetch",
    env: Mapping[str, str] | None = None,
    fetcher: Callable[[dict[str, Any], Path, Path | None, dict[str, str]], dict[str, Any]] = _default_fetcher,
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    approval_ready = _approval_ready(inputs["approvalSummary"], inputs["approvalContract"])
    credential_env_var = str((inputs["approvalContract"] or {}).get("credentialEnvVar") or "SOCCERNET_PASSWORD")
    runtime_env = dict(os.environ if env is None else env)
    credential_audit = _credential_audit(runtime_env, credential_env_var)
    python_executable_value = (inputs["packageAudit"] or {}).get("pythonExecutable")
    python_executable = Path(str(python_executable_value)) if python_executable_value else None
    fetch_audit: dict[str, Any] | None = None
    if approval_ready and credential_audit["credentialRuntimeAvailable"]:
        fetch_audit = fetcher(inputs["approvalContract"] or {}, output_root, python_executable, runtime_env)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        approval_ready=approval_ready,
        credential_audit=credential_audit,
        fetch_audit=fetch_audit,
    )
    generated_at = utc_now_iso()
    attempts = _attempt_plan()
    fetch_audit = fetch_audit or {"fetchExecuted": False, "files": [], "failures": []}
    files = fetch_audit.get("files") if isinstance(fetch_audit.get("files"), list) else []
    failures = fetch_audit.get("failures") if isinstance(fetch_audit.get("failures"), list) else []
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_controlled_label_sample_fetch",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_controlled_label_sample_fetch_approval",
        "credentialRuntimeAvailable": credential_audit["credentialRuntimeAvailable"],
        "credentialPersisted": False,
        "passwordRedacted": True,
        "labelDownloadExecuted": goal_achieved,
        "downloadedLabelFileCount": len(files),
        "fetchFailureCount": len(failures),
        "sampleDownloadExecuted": goal_achieved,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadApproved": False,
        "fullOriginalVideoDownloadExecuted": False,
        "videoDownloadAllowed": False,
        "featureDownloadAllowed": False,
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
    manifest = {
        "fetchScope": "single_game_label_metadata_only",
        "approvedContract": inputs["approvalContract"] or {},
        "labelDownloadExecuted": goal_achieved,
        "downloadedLabelFileCount": len(files),
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadExecuted": False,
        "trainingExecuted": False,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "label_fetch_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "label_fetch_credential_missing", "selected": primary_blocker == BLOCKER_CREDENTIAL_MISSING, "nextRecommendedNextLever": NEXT_SECRET_SETUP},
            {"condition": "label_fetch_failed", "selected": primary_blocker == BLOCKER_FETCH_FAILED, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "label_schema_probe_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_LABEL_SCHEMA_PROBE},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "credentialRuntimeAudit": credential_audit,
        "controlledLabelFetchManifest": manifest,
        "labelFetchProvenanceAudit": fetch_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "controlled_label_fetch_summary.json", summary)
    _write_json(output_root / "controlled_label_fetch_manifest.json", manifest)
    _write_json(output_root / "credential_runtime_audit.json", credential_audit)
    _write_json(output_root / "label_fetch_provenance_audit.json", fetch_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch one approved SoccerNet Labels.json file without videos.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_single_label_file_fetch")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccernet_controlled_label_sample_fetch(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
