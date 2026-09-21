from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import subprocess
import sys
import tempfile
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    extract_zip_members_with_pyzipper,
    load_json as _load_json,
    sha256_file,
    write_json as _write_json,
    utc_now_iso,
)
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_zip_label_member_extract_approval_v1"
DEFAULT_RANGE_INDEX_DIR_NAME = "football_external_soccernet_split_archive_range_index_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_zip_label_member_extract_v1"

BLOCKER_APPROVAL_MISSING = "football_external_soccernet_zip_label_member_extract_approval_missing"
BLOCKER_CREDENTIAL_MISSING = "football_external_soccernet_zip_label_member_credential_missing"
BLOCKER_DEPENDENCY_MISSING = "football_external_soccernet_zip_label_member_extract_dependency_missing"
BLOCKER_EXTRACT_FAILED = "football_external_soccernet_zip_label_member_extract_failed"

NEXT_APPROVAL = "football_external_soccernet_zip_label_member_extract_approval"
NEXT_SECRET_SETUP = "football_external_soccernet_secret_env_setup"
NEXT_DEPENDENCY_SETUP = "football_external_soccernet_zip_label_member_extract_dependency_setup"
NEXT_EXTRACT_DEBUG = "football_external_soccernet_encrypted_label_member_extract_debug"
NEXT_SCHEMA_PROBE = "football_external_soccernet_label_schema_ingestion_probe"

HUGGINGFACE_REPO_BY_TASK = {
    "spotting-ball-2025": "SoccerNet/SN-BAS-2025",
}



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_zip_label_member_range_extract",
            "successCriteria": [
                "fetch only approved label-member ZIP byte ranges and ZIP index bytes",
                "decrypt/extract approved label members with runtime-only credential",
                "do not fetch video members or full archive bytes",
            ],
            "failureAdaptation": "If encrypted extraction fails, repair dependency or extraction contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_encrypted_label_member_extract_repair",
            "successCriteria": [
                "repair pyzipper dependency or sparse ZIP assembly",
                "preserve credential secrecy and video/full-archive blocks",
            ],
            "failureAdaptation": "If extraction still fails, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_label_member_extract_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not proceed to training or video download",
            ],
            "failureAdaptation": "Stop before broader download access.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    range_root = candidate_root / DEFAULT_RANGE_INDEX_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "approvalSummary": _load_json(approval_root / "zip_label_member_extract_approval_summary.json"),
        "extractContract": _load_json(approval_root / "zip_label_member_extract_contract.json"),
        "centralDirectoryAudit": _load_json(range_root / "zip_central_directory_audit.json"),
    }


def _approval_ready(approval_summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(approval_summary, dict)
        and approval_summary.get("goalAchieved") is True
        and approval_summary.get("primaryBlocker") is None
        and approval_summary.get("labelMemberExtractionApproved") is True
        and int(approval_summary.get("approvedLabelMemberCount") or 0) > 0
        and approval_summary.get("fullArchiveDownloadApproved") is False
        and approval_summary.get("archiveDownloadExecuted") is False
        and approval_summary.get("videoMemberDownloadAllowed") is False
        and approval_summary.get("videoMemberDownloadExecuted") is False
        and approval_summary.get("trainingExecuted") is False
        and isinstance(contract, dict)
        and contract.get("contractName") == "football_external_soccernet_zip_label_member_extract"
        and contract.get("labelMemberExtractionApproved") is True
        and contract.get("labelMemberRangeExtractionOnly") is True
        and contract.get("fullArchiveDownloadApproved") is False
        and contract.get("videoMemberDownloadAllowed") is False
        and isinstance(contract.get("labelMembers"), list)
        and len(contract.get("labelMembers") or []) > 0
    )


def _credential_audit(env: Mapping[str, str], contract: dict[str, Any] | None, injected: bool) -> dict[str, Any]:
    required = bool((contract or {}).get("credentialRequired"))
    env_var = str((contract or {}).get("credentialEnvVar") or "SOCCERNET_PASSWORD")
    value = env.get(env_var)
    return {
        "credentialRequired": required,
        "credentialEnvVar": env_var if required else None,
        "credentialRuntimeAvailable": bool(value) or injected,
        "credentialPersisted": False,
        "passwordRedacted": True,
        "artifactContainsSecret": False,
        "credentialLength": len(value) if value else 0,
    }


def _resolve_url(task: str, archive_path: str) -> str | None:
    repo_id = HUGGINGFACE_REPO_BY_TASK.get(task)
    if not repo_id:
        return None
    return f"https://huggingface.co/datasets/{repo_id}/resolve/main/{quote(archive_path)}"


def _range_fetch(url: str, start: int, end: int, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "User-Agent": "fotball-analyst-soccernet-label-member-extract/1.0",
            "Range": f"bytes={start}-{end}",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        data = response.read()
        return data, {
            "rangeStart": start,
            "rangeEnd": end,
            "httpStatus": response.status,
            "contentLength": int(response.headers.get("Content-Length") or len(data)),
            "contentRange": response.headers.get("Content-Range"),
            "bytesFetched": len(data),
            "resolvedHost": response.url.split("/")[2] if "://" in response.url else None,
        }


def _member_end_offsets(entries: list[dict[str, Any]], central_directory_offset: int) -> dict[str, int]:
    offsets = sorted(int(row.get("localHeaderOffset") or 0) for row in entries if isinstance(row, dict))
    result: dict[str, int] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        start = int(row.get("localHeaderOffset") or 0)
        next_offsets = [offset for offset in offsets if offset > start]
        result[str(row.get("path") or "")] = (next_offsets[0] - 1) if next_offsets else (central_directory_offset - 1)
    return result


def _ensure_pyzipper_python(output_root: Path) -> dict[str, Any]:
    try:
        import pyzipper  # noqa: F401

        return {
            "dependencyReady": True,
            "pythonExecutable": sys.executable,
            "venvCreated": False,
            "pipInstallAttempted": False,
            "pipInstallReturnCode": None,
            "stderrTail": "",
        }
    except ModuleNotFoundError:
        pass

    venv_root = output_root / "zip_extract_venv"
    python_path = venv_root / "bin" / "python"
    if not python_path.exists():
        create = subprocess.run([sys.executable, "-m", "venv", str(venv_root)], check=False, capture_output=True, text=True)
        if create.returncode != 0:
            return {
                "dependencyReady": False,
                "pythonExecutable": None,
                "venvCreated": False,
                "pipInstallAttempted": False,
                "pipInstallReturnCode": create.returncode,
                "stderrTail": create.stderr[-1200:],
            }
    install = subprocess.run([str(python_path), "-m", "pip", "install", "-q", "pyzipper"], check=False, capture_output=True, text=True)
    return {
        "dependencyReady": install.returncode == 0,
        "pythonExecutable": str(python_path) if install.returncode == 0 else None,
        "venvCreated": True,
        "pipInstallAttempted": True,
        "pipInstallReturnCode": install.returncode,
        "stderrTail": install.stderr[-1200:],
    }


def _extract_with_pyzipper(
    *,
    python_executable: str,
    sparse_zip_path: Path,
    member_paths: list[str],
    expected_size_bytes_by_member: Mapping[str, int],
    output_dir: Path,
    env: Mapping[str, str],
    credential_env_var: str,
) -> dict[str, Any]:
    return extract_zip_members_with_pyzipper(
        python_executable=python_executable,
        sparse_zip_path=sparse_zip_path,
        member_sizes={member: expected_size_bytes_by_member[member] for member in member_paths},
        output_dir=output_dir,
        env=env,
        credential_env_var=credential_env_var,
    )


def _real_extract(
    *,
    output_root: Path,
    contract: dict[str, Any],
    central_directory_audit: dict[str, Any],
    env: Mapping[str, str],
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    dependency = _ensure_pyzipper_python(output_root)
    if not dependency.get("dependencyReady"):
        return [], dependency, {"extractFailure": "pyzipper dependency unavailable", "rangeFetches": []}

    archive_size = int(central_directory_audit.get("archiveSizeBytes") or 0)
    central_offset = int(central_directory_audit.get("centralDirectoryOffset") or 0)
    task = str(contract.get("selectedArchiveTask") or "")
    archive_path = str(contract.get("selectedArchivePath") or "")
    url = _resolve_url(task, archive_path)
    if not url:
        return [], dependency, {"extractFailure": f"No resolve URL mapping for {task}", "rangeFetches": []}
    label_members = [row for row in contract.get("labelMembers") or [] if isinstance(row, dict)]
    all_entries = [row for row in (central_directory_audit.get("zipEntries") or []) if isinstance(row, dict)]
    end_offsets = _member_end_offsets(all_entries, central_offset)
    central_end = archive_size - 1
    range_fetches: list[dict[str, Any]] = []

    output_dir = output_root / "extracted_labels"
    with tempfile.TemporaryDirectory() as temp_dir:
        sparse_zip = Path(temp_dir) / "valid_sparse.zip"
        with sparse_zip.open("wb") as handle:
            handle.truncate(archive_size)
            for member in label_members:
                start = int(member.get("localHeaderOffset") or 0)
                end = end_offsets.get(str(member.get("path") or ""), central_offset - 1)
                data, audit = _range_fetch(url, start, end, timeout_seconds)
                range_fetches.append({**audit, "memberPath": member.get("path"), "rangeKind": "label_member_local_header_and_payload"})
                handle.seek(start)
                handle.write(data)
            central_data, central_audit = _range_fetch(url, central_offset, central_end, timeout_seconds)
            range_fetches.append({**central_audit, "rangeKind": "central_directory_and_eocd"})
            handle.seek(central_offset)
            handle.write(central_data)
        member_paths = [str(row.get("path")) for row in label_members]
        expected_sizes = {str(row.get("path")): int(row.get("uncompressedSizeBytes") or 0) for row in label_members}
        if any(size <= 0 for size in expected_sizes.values()):
            return [], dependency, {"extractFailure": "approved label member size is missing", "rangeFetches": range_fetches}
        extraction = _extract_with_pyzipper(
            python_executable=str(dependency["pythonExecutable"]),
            sparse_zip_path=sparse_zip,
            member_paths=member_paths,
            expected_size_bytes_by_member=expected_sizes,
            output_dir=output_dir,
            env=env,
            credential_env_var=str(contract.get("credentialEnvVar") or "SOCCERNET_PASSWORD"),
        )
    if extraction.get("returnCode") != 0:
        return [], dependency, {"extractFailure": "pyzipper extraction failed", "rangeFetches": range_fetches, "pyzipperExtraction": extraction}
    parsed = extraction.get("parsedResult") if isinstance(extraction.get("parsedResult"), dict) else {}
    results = parsed.get("results") if isinstance(parsed, dict) else []
    return results if isinstance(results, list) else [], dependency, {"extractFailure": None, "rangeFetches": range_fetches, "pyzipperExtraction": extraction}


def _write_injected_payloads(output_root: Path, payloads: dict[str, bytes]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output_dir = output_root / "extracted_labels"
    results = []
    for member_path, payload in payloads.items():
        out = output_dir / member_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(payload)
        results.append({"memberPath": member_path, "relativePath": str(out.relative_to(output_dir)), "sizeBytes": len(payload)})
    return results, {"extractFailure": None, "rangeFetches": [], "injectedPayloads": True}


def _extracted_inventory(output_root: Path, extraction_results: list[dict[str, Any]]) -> dict[str, Any]:
    output_dir = output_root / "extracted_labels"
    files = []
    for result in extraction_results:
        rel = str(result.get("relativePath") or result.get("memberPath") or "")
        path = output_dir / rel
        if path.exists():
            files.append(
                {
                    "memberPath": result.get("memberPath"),
                    "relativePath": str(path.relative_to(output_root)),
                    "sizeBytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return {
        "extractedLabelFileCount": len(files),
        "extractedLabelFiles": files,
        "archiveDownloadExecuted": False,
        "videoMemberDownloadExecuted": False,
    }


def _schema_preview(output_root: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    files = inventory.get("extractedLabelFiles") if isinstance(inventory, dict) else []
    if not isinstance(files, list) or not files:
        return {"jsonParseSucceeded": False, "annotationCount": 0, "topLevelKeys": []}
    first = files[0]
    path = output_root / str(first.get("relativePath") or "")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"jsonParseSucceeded": False, "parseError": str(exc), "annotationCount": 0, "topLevelKeys": []}
    annotations = payload.get("annotations") if isinstance(payload, dict) else None
    if annotations is None and isinstance(payload, dict):
        annotations = payload.get("Annotations")
    return {
        "jsonParseSucceeded": isinstance(payload, dict),
        "topLevelKeys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "annotationCount": len(annotations) if isinstance(annotations, list) else 0,
        "sampleAnnotationKeys": sorted(annotations[0].keys()) if isinstance(annotations, list) and annotations and isinstance(annotations[0], dict) else [],
    }


def _classify(
    *,
    approval_ready: bool,
    credential_audit: dict[str, Any],
    dependency_audit: dict[str, Any],
    extract_audit: dict[str, Any],
    inventory: dict[str, Any],
    schema_preview: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "Label-member extraction approval truth is missing or unsafe; rerun approval before extraction.",
        )
    if credential_audit.get("credentialRequired") and credential_audit.get("credentialRuntimeAvailable") is not True:
        return (
            BLOCKER_CREDENTIAL_MISSING,
            NEXT_SECRET_SETUP,
            False,
            "Encrypted SoccerNet label member extraction requires a runtime-only credential.",
        )
    if dependency_audit and dependency_audit.get("dependencyReady") is False:
        return (
            BLOCKER_DEPENDENCY_MISSING,
            NEXT_DEPENDENCY_SETUP,
            False,
            "Encrypted ZIP extraction dependency is unavailable.",
        )
    if extract_audit.get("extractFailure") or int(inventory.get("extractedLabelFileCount") or 0) <= 0 or schema_preview.get("jsonParseSucceeded") is not True:
        return (
            BLOCKER_EXTRACT_FAILED,
            NEXT_EXTRACT_DEBUG,
            False,
            "Approved label member extraction did not produce a parseable label JSON file.",
        )
    return (
        None,
        NEXT_SCHEMA_PROBE,
        True,
        "Extracted SoccerNet Labels-ball.json via label-member-only ZIP ranges. Full archive and video members were not downloaded.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "extract_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "runtime_credential_missing", "selected": primary_blocker == BLOCKER_CREDENTIAL_MISSING, "primaryBlocker": BLOCKER_CREDENTIAL_MISSING, "nextRecommendedNextLever": NEXT_SECRET_SETUP},
            {"condition": "encrypted_zip_dependency_missing", "selected": primary_blocker == BLOCKER_DEPENDENCY_MISSING, "primaryBlocker": BLOCKER_DEPENDENCY_MISSING, "nextRecommendedNextLever": NEXT_DEPENDENCY_SETUP},
            {"condition": "label_member_extract_failed", "selected": primary_blocker == BLOCKER_EXTRACT_FAILED, "primaryBlocker": BLOCKER_EXTRACT_FAILED, "nextRecommendedNextLever": NEXT_EXTRACT_DEBUG},
            {"condition": "label_schema_probe_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SCHEMA_PROBE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet ZIP Label Member Extract",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Downloaded label files: `{summary.get('downloadedLabelFileCount')}`",
            f"- Archive download executed: `{summary.get('archiveDownloadExecuted')}`",
            f"- Video member download executed: `{summary.get('videoMemberDownloadExecuted')}`",
            f"- Credential persisted: `{summary.get('credentialPersisted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_zip_label_member_extract(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    label_member_payloads: dict[str, bytes] | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 60,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_zip_label_member_range_extract",
) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    approval_ready = _approval_ready(inputs["approvalSummary"], inputs["extractContract"])
    injected = label_member_payloads is not None
    credential = _credential_audit(env, inputs["extractContract"], injected)
    dependency: dict[str, Any] = {"dependencyReady": True, "injectedPayloads": injected}
    extract_audit: dict[str, Any] = {"extractFailure": None, "rangeFetches": []}
    extraction_results: list[dict[str, Any]] = []

    if approval_ready and (not credential.get("credentialRequired") or credential.get("credentialRuntimeAvailable")):
        if injected:
            extraction_results, extract_audit = _write_injected_payloads(output_root, label_member_payloads or {})
        else:
            extraction_results, dependency, extract_audit = _real_extract(
                output_root=output_root,
                contract=inputs["extractContract"] or {},
                central_directory_audit=inputs["centralDirectoryAudit"] or {},
                env=env,
                timeout_seconds=timeout_seconds,
            )

    inventory = _extracted_inventory(output_root, extraction_results)
    schema = _schema_preview(output_root, inventory)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        approval_ready=approval_ready,
        credential_audit=credential,
        dependency_audit=dependency,
        extract_audit=extract_audit,
        inventory=inventory,
        schema_preview=schema,
    )
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_zip_label_member_extract",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_zip_label_member_extract_approval",
        "downloadedLabelFileCount": inventory.get("extractedLabelFileCount"),
        "labelJsonParseSucceeded": schema.get("jsonParseSucceeded"),
        "annotationCount": schema.get("annotationCount"),
        "credentialRuntimeAvailable": credential.get("credentialRuntimeAvailable"),
        "credentialPersisted": False,
        "archiveDownloadApproved": False,
        "archiveDownloadExecuted": False,
        "partialArchiveRangeFetchExecuted": bool(extract_audit.get("rangeFetches")),
        "partialArchiveMetadataOnly": False,
        "videoMemberDownloadAllowed": False,
        "videoMemberDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "credentialRuntimeAudit": credential,
        "dependencyAudit": dependency,
        "labelMemberRangeFetchAudit": extract_audit,
        "extractedLabelInventory": inventory,
        "labelSchemaPreviewAudit": schema,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "zip_label_member_extract_summary.json", summary)
    _write_json(output_root / "credential_runtime_audit.json", credential)
    _write_json(output_root / "dependency_audit.json", dependency)
    _write_json(output_root / "label_member_range_fetch_audit.json", extract_audit)
    _write_json(output_root / "extracted_label_inventory.json", inventory)
    _write_json(output_root / "label_schema_preview_audit.json", schema)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_zip_label_member_range_extract")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_zip_label_member_extract(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        timeout_seconds=args.timeout_seconds,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
