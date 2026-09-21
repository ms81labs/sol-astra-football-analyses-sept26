from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from datetime import datetime, timezone
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_nda_api_access_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_api_metadata_probe_v1"

BLOCKER_APPROVAL_MISSING = "football_external_soccernet_api_approval_missing"
BLOCKER_PACKAGE_MISSING = "football_external_soccernet_api_package_missing"
BLOCKER_CREDENTIAL_MISSING = "football_external_soccernet_api_credential_missing"

NEXT_APPROVAL = "football_external_soccernet_nda_api_access_approval"
NEXT_PACKAGE_INSTALL = "football_external_soccernet_api_package_install"
NEXT_SECRET_SETUP = "football_external_soccernet_secret_env_setup"
NEXT_LISTING_PROBE = "football_external_soccernet_api_listing_probe"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_api_package_and_credential_probe",
            "successCriteria": [
                "SoccerNet package imports",
                "SoccerNetDownloader import path is available",
                "SOCCERNET_PASSWORD is present at runtime without persisting it",
                "no API call, video download, label download, training, promotion, or runtime mutation occurs",
            ],
            "failureAdaptation": "If package or secret is missing, route to the exact setup family.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_api_probe_contract_repair",
            "successCriteria": [
                "repair package import path or credential-env contract",
                "keep secrets redacted and out of artifacts",
            ],
            "failureAdaptation": "If probe still cannot run, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_api_probe_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not download SoccerNet data",
            ],
            "failureAdaptation": "Stop until package and credential prerequisites are true.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "approvalSummary": _load_json(approval_root / "soccernet_nda_api_access_approval_summary.json"),
        "accessContract": _load_json(approval_root / "soccernet_api_access_contract.json"),
    }


def _probe_package(python_executable: Path | None = None) -> dict[str, Any]:
    if python_executable is not None:
        probe_code = """
import importlib
import importlib.metadata
import importlib.util
import json

package_ready = importlib.util.find_spec("SoccerNet") is not None
downloader_ready = False
downloader_class = None
if package_ready:
    try:
        downloader_module = importlib.import_module("SoccerNet.Downloader")
        downloader_ready = hasattr(downloader_module, "SoccerNetDownloader")
        downloader_class = "SoccerNetDownloader" if downloader_ready else None
    except Exception:
        downloader_ready = False
version = None
if package_ready:
    try:
        version = importlib.metadata.version("SoccerNet")
    except importlib.metadata.PackageNotFoundError:
        version = None
print(json.dumps({
    "packageName": "SoccerNet",
    "packageImportReady": package_ready,
    "downloaderImportReady": downloader_ready,
    "downloaderClassName": downloader_class,
    "packageVersion": version,
    "pythonExecutable": %r,
}))
""" % str(python_executable)
        completed = subprocess.run(
            [str(python_executable), "-c", probe_code],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return json.loads(completed.stdout)
        return {
            "packageName": "SoccerNet",
            "packageImportReady": False,
            "downloaderImportReady": False,
            "downloaderClassName": None,
            "packageVersion": None,
            "pythonExecutable": str(python_executable),
            "probeReturncode": completed.returncode,
            "probeStderrTail": completed.stderr[-1200:],
        }
    package_ready = importlib.util.find_spec("SoccerNet") is not None
    downloader_ready = False
    downloader_class = None
    if package_ready:
        try:
            downloader_module = importlib.import_module("SoccerNet.Downloader")
            downloader_ready = hasattr(downloader_module, "SoccerNetDownloader")
            downloader_class = "SoccerNetDownloader" if downloader_ready else None
        except Exception:
            downloader_ready = False
    version = None
    if package_ready:
        try:
            version = importlib.metadata.version("SoccerNet")
        except importlib.metadata.PackageNotFoundError:
            version = None
    return {
        "packageName": "SoccerNet",
        "packageImportReady": package_ready,
        "downloaderImportReady": downloader_ready,
        "downloaderClassName": downloader_class,
        "packageVersion": version,
    }


def _install_package(venv_root: Path) -> dict[str, Any]:
    if venv_root.exists():
        shutil.rmtree(venv_root)
    venv_completed = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_root)],
        check=False,
        capture_output=True,
        text=True,
    )
    python_executable = venv_root / "bin" / "python"
    if venv_completed.returncode != 0:
        return {
            "installMode": "artifact_local_venv",
            "venvRoot": str(venv_root),
            "venvReturncode": venv_completed.returncode,
            "installSucceeded": False,
            "stdoutTail": venv_completed.stdout[-1200:],
            "stderrTail": venv_completed.stderr[-1200:],
        }
    command = [str(python_executable), "-m", "pip", "install", "SoccerNet", "--upgrade"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return {
        "installMode": "artifact_local_venv",
        "venvRoot": str(venv_root),
        "pythonExecutable": str(python_executable),
        "command": "venv/bin/python -m pip install SoccerNet --upgrade",
        "venvReturncode": venv_completed.returncode,
        "returncode": completed.returncode,
        "stdoutTail": completed.stdout[-1200:],
        "stderrTail": completed.stderr[-1200:],
        "installSucceeded": completed.returncode == 0,
    }


def _approval_ready(approval_summary: dict[str, Any] | None, access_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(approval_summary, dict)
        and approval_summary.get("goalAchieved") is True
        and approval_summary.get("controlledApiMetadataProbeReady") is True
        and approval_summary.get("credentialPersisted") is False
        and approval_summary.get("passwordRedacted") is True
        and isinstance(access_contract, dict)
        and access_contract.get("credentialEnvVar") == "SOCCERNET_PASSWORD"
        and access_contract.get("credentialPersisted") is False
        and access_contract.get("passwordRedacted") is True
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


def _classify(
    *,
    approval_ready: bool,
    package_audit: dict[str, Any],
    credential_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "SoccerNet NDA/API approval truth is missing or unsafe.",
        )
    if not (package_audit.get("packageImportReady") and package_audit.get("downloaderImportReady")):
        return (
            BLOCKER_PACKAGE_MISSING,
            NEXT_PACKAGE_INSTALL,
            False,
            "SoccerNet Python package or SoccerNetDownloader import path is missing.",
        )
    if not credential_audit["credentialRuntimeAvailable"]:
        return (
            BLOCKER_CREDENTIAL_MISSING,
            NEXT_SECRET_SETUP,
            False,
            "SOCCERNET_PASSWORD is not available in the runtime environment. Set it without persisting it, then rerun.",
        )
    return (
        None,
        NEXT_LISTING_PROBE,
        True,
        "SoccerNet package and runtime credential are ready for an API listing probe. No API call or dataset download was executed in this batch.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet API Metadata Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- API package import ready: `{summary.get('apiPackageImportReady')}`",
            f"- API downloader import ready: `{summary.get('apiDownloaderImportReady')}`",
            f"- Runtime credential available: `{summary.get('credentialRuntimeAvailable')}`",
            f"- Credential persisted: `{summary.get('credentialPersisted')}`",
            f"- API call executed: `{summary.get('apiCallExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_api_metadata_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_api_package_and_credential_probe",
    env: Mapping[str, str] | None = None,
    install_package: bool = False,
    package_probe: Callable[[], dict[str, Any]] = _probe_package,
    installer: Callable[[Path], dict[str, Any]] = _install_package,
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    package_audit = package_probe()
    install_audit: dict[str, Any] = {"installAttempted": False}
    if install_package and not (package_audit.get("packageImportReady") and package_audit.get("downloaderImportReady")):
        install_audit = {"installAttempted": True, **installer(output_root / "soccernet_api_venv")}
        python_path = install_audit.get("pythonExecutable")
        if python_path:
            package_audit = _probe_package(Path(str(python_path)))
        else:
            package_audit = package_probe()
    credential_env_var = str((inputs["accessContract"] or {}).get("credentialEnvVar") or "SOCCERNET_PASSWORD")
    credential_audit = _credential_audit(env or os.environ, credential_env_var)
    approval_ready = _approval_ready(inputs["approvalSummary"], inputs["accessContract"])
    primary_blocker, next_lever, goal_achieved, english = _classify(
        approval_ready=approval_ready,
        package_audit=package_audit,
        credential_audit=credential_audit,
    )
    generated_at = utc_now_iso()
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_api_metadata_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_nda_api_access_approval",
        "apiApprovalReady": approval_ready,
        "apiPackageInstallAttempted": install_audit.get("installAttempted") is True,
        "apiPackageImportReady": package_audit.get("packageImportReady") is True,
        "apiDownloaderImportReady": package_audit.get("downloaderImportReady") is True,
        "apiPackageVersion": package_audit.get("packageVersion"),
        "credentialRuntimeAvailable": credential_audit["credentialRuntimeAvailable"],
        "credentialPersisted": False,
        "passwordRedacted": True,
        "apiMetadataProbeReady": goal_achieved,
        "apiCallExecuted": False,
        "apiListingExecuted": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadExecuted": False,
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
            {"condition": "api_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "api_package_missing", "selected": primary_blocker == BLOCKER_PACKAGE_MISSING, "nextRecommendedNextLever": NEXT_PACKAGE_INSTALL},
            {"condition": "api_credential_missing", "selected": primary_blocker == BLOCKER_CREDENTIAL_MISSING, "nextRecommendedNextLever": NEXT_SECRET_SETUP},
            {"condition": "api_metadata_probe_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_LISTING_PROBE},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "soccernetApiPackageAudit": package_audit,
        "packageInstallAudit": install_audit,
        "credentialRuntimeAudit": credential_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "soccernet_api_metadata_probe_summary.json", summary)
    _write_json(output_root / "soccernet_api_package_audit.json", package_audit)
    _write_json(output_root / "package_install_audit.json", install_audit)
    _write_json(output_root / "credential_runtime_audit.json", credential_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe SoccerNet package and runtime credential readiness without API calls.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_api_package_and_credential_probe")
    parser.add_argument("--install-package", action="store_true", help="Install/upgrade SoccerNet package if import is missing.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccernet_api_metadata_probe(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
        install_package=bool(args.install_package),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
