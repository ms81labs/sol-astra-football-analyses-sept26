from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_ACCESS_REVIEW_DIR_NAME = "football_external_soccernet_split_archive_access_review_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_split_archive_size_probe_v1"

BLOCKER_ACCESS_REVIEW_MISSING = "football_external_soccernet_split_archive_access_review_missing"
BLOCKER_METADATA_MISSING = "football_external_soccernet_selected_archive_metadata_missing"
BLOCKER_METADATA_UNAVAILABLE = "football_external_soccernet_split_archive_metadata_unavailable"

NEXT_ACCESS_REVIEW = "football_external_soccernet_split_archive_access_review"
NEXT_METADATA_REPAIR = "football_external_soccernet_split_archive_metadata_contract_repair"
NEXT_METADATA_ACCESS_REPAIR = "football_external_soccernet_huggingface_metadata_access_repair"
NEXT_RANGE_INDEX_PROBE = "football_external_soccernet_split_archive_range_index_probe"
NEXT_DOWNLOAD_APPROVAL = "football_external_soccernet_split_archive_download_approval"

HUGGINGFACE_REPO_BY_TASK = {
    "spotting-ball-2025": "SoccerNet/SN-BAS-2025",
}
SMALL_ARCHIVE_MAX_BYTES = 512 * 1024 * 1024
LARGE_ARCHIVE_MAX_BYTES = 3 * 1024 * 1024 * 1024


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_huggingface_split_archive_metadata_probe",
            "successCriteria": [
                "query remote repository file metadata only",
                "identify selected split archive path and size",
                "do not download archive bytes or partial archive contents",
            ],
            "failureAdaptation": "If metadata access fails, route to HuggingFace metadata access repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_split_archive_metadata_contract_repair",
            "successCriteria": [
                "repair archive pattern/path matching without broadening download approval",
                "preserve metadata-only guardrails",
            ],
            "failureAdaptation": "If selected archive metadata is still missing, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_split_archive_size_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "avoid any full split archive fetch until size and contents are understood",
            ],
            "failureAdaptation": "Stop before archive download approval.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    access_root = candidate_root / DEFAULT_ACCESS_REVIEW_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "accessSummary": _load_json(access_root / "split_archive_access_review_summary.json"),
        "sizeProbeContract": _load_json(access_root / "split_archive_size_probe_contract.json"),
    }


def _access_review_ready(access_summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(access_summary, dict)
        and access_summary.get("goalAchieved") is True
        and access_summary.get("primaryBlocker") is None
        and access_summary.get("selectedArchiveTask") == "spotting-ball-2025"
        and access_summary.get("selectedAccessMode") == "huggingface_snapshot_allow_pattern"
        and access_summary.get("splitArchiveDownloadApproved") is False
        and access_summary.get("datasetDownloadExecuted") is False
        and access_summary.get("fullOriginalVideoDownloadExecuted") is False
        and access_summary.get("trainingExecuted") is False
        and isinstance(contract, dict)
        and contract.get("contractName") == "football_external_soccernet_split_archive_size_probe"
        and contract.get("downloadAllowedByThisBatch") is False
        and contract.get("metadataOnly") is True
        and contract.get("approvalRequiredBeforeArchiveDownload") is True
    )


def _fetch_huggingface_tree(task: str, timeout_seconds: int = 30) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repo_id = HUGGINGFACE_REPO_BY_TASK.get(task)
    if not repo_id:
        return [], {"metadataFetchExecuted": False, "metadataFetchError": f"No HuggingFace repo mapping for {task}"}
    url = f"https://huggingface.co/api/datasets/{repo_id}/tree/main?recursive=true"
    request = Request(url, headers={"User-Agent": "fotball-analyst-soccernet-metadata-probe/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        status = exc.code if isinstance(exc, HTTPError) else None
        return [], {
            "metadataFetchExecuted": True,
            "metadataFetchError": str(exc),
            "httpStatus": status,
            "repoId": repo_id,
            "url": url,
        }
    if not isinstance(payload, list):
        return [], {"metadataFetchExecuted": True, "metadataFetchError": "Unexpected HuggingFace tree payload shape", "repoId": repo_id, "url": url}
    rows = [row for row in payload if isinstance(row, dict)]
    return rows, {"metadataFetchExecuted": True, "metadataFetchError": None, "httpStatus": 200, "repoId": repo_id, "url": url}


def _file_inventory(remote_tree_rows: list[dict[str, Any]], metadata_fetch: dict[str, Any]) -> dict[str, Any]:
    files = [
        {
            "path": str(row.get("path") or ""),
            "sizeBytes": int(row.get("size") or 0),
            "type": row.get("type"),
            "lfsSizeBytes": int((row.get("lfs") or {}).get("size") or 0) if isinstance(row.get("lfs"), dict) else None,
        }
        for row in remote_tree_rows
        if row.get("type") == "file" and row.get("path")
    ]
    zip_files = [row for row in files if str(row["path"]).endswith(".zip")]
    return {
        "metadataFetch": metadata_fetch,
        "remoteFileCount": len(files),
        "remoteZipFileCount": len(zip_files),
        "zipFiles": sorted(zip_files, key=lambda row: str(row["path"])),
        "archiveDownloadExecuted": False,
        "partialArchiveContentDownloadExecuted": False,
    }


def _match_selected_archive(inventory: dict[str, Any], contract: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(contract, dict):
        return None
    pattern = str(contract.get("selectedArchiveFileOrPattern") or "")
    split = str(contract.get("selectedSplit") or "")
    zip_files = inventory.get("zipFiles") if isinstance(inventory, dict) else []
    if not isinstance(zip_files, list):
        return None
    exact_path = f"{split}.zip"
    for row in zip_files:
        if isinstance(row, dict) and row.get("path") == exact_path:
            return row
    for row in zip_files:
        path = str(row.get("path") or "") if isinstance(row, dict) else ""
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern):
            return row
    return None


def _size_class(size_bytes: int) -> str:
    if size_bytes <= SMALL_ARCHIVE_MAX_BYTES:
        return "small_archive"
    if size_bytes <= LARGE_ARCHIVE_MAX_BYTES:
        return "large_archive"
    return "very_large_archive"


def _labels_only_archive_audit(inventory: dict[str, Any]) -> dict[str, Any]:
    zip_files = inventory.get("zipFiles") if isinstance(inventory, dict) else []
    candidates = []
    if isinstance(zip_files, list):
        for row in zip_files:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            if path.endswith(".zip") and "label" in path.lower():
                candidates.append(row)
    return {
        "labelsOnlyArchiveCandidateCount": len(candidates),
        "labelsOnlyArchiveCandidates": candidates,
        "labelsOnlyArchiveUseApproved": False,
        "labelsOnlyArchiveNeedsSemanticReview": bool(candidates),
    }


def _selected_archive_audit(selected: dict[str, Any] | None) -> dict[str, Any]:
    if not selected:
        return {
            "selectedArchiveMetadataFound": False,
            "selectedArchivePath": None,
            "selectedArchiveSizeBytes": None,
            "selectedArchiveSizeClass": None,
            "fullArchiveDownloadRecommended": False,
        }
    size_bytes = int(selected.get("sizeBytes") or 0)
    size_class = _size_class(size_bytes)
    return {
        "selectedArchiveMetadataFound": True,
        "selectedArchivePath": selected.get("path"),
        "selectedArchiveSizeBytes": size_bytes,
        "selectedArchiveSizeClass": size_class,
        "selectedArchiveSizeMiB": round(size_bytes / (1024 * 1024), 3),
        "fullArchiveDownloadRecommended": size_class == "small_archive",
        "rangeIndexProbeRecommended": size_class != "small_archive",
        "archiveContentsUnknown": True,
    }


def _range_index_contract(summary_fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": NEXT_RANGE_INDEX_PROBE,
        "sourceBatch": "football_external_soccernet_split_archive_size_probe",
        "selectedArchiveTask": summary_fields.get("selectedArchiveTask"),
        "selectedArchivePath": summary_fields.get("selectedArchivePath"),
        "selectedArchiveSizeBytes": summary_fields.get("selectedArchiveSizeBytes"),
        "downloadAllowedByThisBatch": False,
        "fullArchiveDownloadApproved": False,
        "partialRangeMetadataProbeOnly": True,
        "expectedProbe": "Use remote ZIP central-directory/range metadata where available to inspect archive contents before any full archive download.",
    }


def _classify(
    *,
    access_ready: bool,
    metadata_fetch: dict[str, Any],
    selected_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not access_ready:
        return (
            BLOCKER_ACCESS_REVIEW_MISSING,
            NEXT_ACCESS_REVIEW,
            False,
            "Split archive access review truth is missing or unsafe; rerun access review before metadata probing.",
        )
    if metadata_fetch.get("metadataFetchError"):
        return (
            BLOCKER_METADATA_UNAVAILABLE,
            NEXT_METADATA_ACCESS_REPAIR,
            False,
            "Remote split archive metadata could not be read; repair HuggingFace metadata access before download approval.",
        )
    if selected_audit.get("selectedArchiveMetadataFound") is not True:
        return (
            BLOCKER_METADATA_MISSING,
            NEXT_METADATA_REPAIR,
            False,
            "Remote metadata did not contain the selected split archive path; repair the archive metadata contract.",
        )
    if selected_audit.get("fullArchiveDownloadRecommended") is True:
        return (
            None,
            NEXT_DOWNLOAD_APPROVAL,
            True,
            "Selected split archive is small enough for a separate controlled download approval; no archive bytes were downloaded in this probe.",
        )
    return (
        None,
        NEXT_RANGE_INDEX_PROBE,
        True,
        "Selected split archive metadata was found, but the archive is large and contents remain unknown. Advance to a range/index metadata probe before any full download.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {
                "condition": "split_archive_access_review_missing",
                "selected": primary_blocker == BLOCKER_ACCESS_REVIEW_MISSING,
                "primaryBlocker": BLOCKER_ACCESS_REVIEW_MISSING,
                "nextRecommendedNextLever": NEXT_ACCESS_REVIEW,
            },
            {
                "condition": "split_archive_metadata_unavailable",
                "selected": primary_blocker == BLOCKER_METADATA_UNAVAILABLE,
                "primaryBlocker": BLOCKER_METADATA_UNAVAILABLE,
                "nextRecommendedNextLever": NEXT_METADATA_ACCESS_REPAIR,
            },
            {
                "condition": "selected_archive_metadata_missing",
                "selected": primary_blocker == BLOCKER_METADATA_MISSING,
                "primaryBlocker": BLOCKER_METADATA_MISSING,
                "nextRecommendedNextLever": NEXT_METADATA_REPAIR,
            },
            {
                "condition": "split_archive_range_index_probe_ready",
                "selected": goal_achieved and next_lever == NEXT_RANGE_INDEX_PROBE,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_RANGE_INDEX_PROBE,
            },
            {
                "condition": "split_archive_download_approval_ready",
                "selected": goal_achieved and next_lever == NEXT_DOWNLOAD_APPROVAL,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_DOWNLOAD_APPROVAL,
            },
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Split Archive Size Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected archive task: `{summary.get('selectedArchiveTask')}`",
            f"- Selected archive path: `{summary.get('selectedArchivePath')}`",
            f"- Selected archive size bytes: `{summary.get('selectedArchiveSizeBytes')}`",
            f"- Selected archive size class: `{summary.get('selectedArchiveSizeClass')}`",
            f"- Labels-only archive candidates: `{summary.get('labelsOnlyArchiveCandidateCount')}`",
            f"- Archive download executed: `{summary.get('archiveDownloadExecuted')}`",
            f"- Partial archive content download executed: `{summary.get('partialArchiveContentDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_split_archive_size_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    remote_tree_rows: list[dict[str, Any]] | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_huggingface_split_archive_metadata_probe",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    access_ready = _access_review_ready(inputs["accessSummary"], inputs["sizeProbeContract"])
    if remote_tree_rows is None and access_ready:
        remote_tree_rows, metadata_fetch = _fetch_huggingface_tree(str(inputs["sizeProbeContract"].get("selectedArchiveTask")))
    elif remote_tree_rows is None:
        remote_tree_rows, metadata_fetch = [], {"metadataFetchExecuted": False, "metadataFetchError": None}
    else:
        metadata_fetch = {"metadataFetchExecuted": True, "metadataFetchError": None, "httpStatus": None, "repoId": "injected_test_repo", "url": None}

    inventory = _file_inventory(remote_tree_rows, metadata_fetch)
    selected = _match_selected_archive(inventory, inputs["sizeProbeContract"])
    selected_audit = _selected_archive_audit(selected)
    labels_audit = _labels_only_archive_audit(inventory)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        access_ready=access_ready,
        metadata_fetch=metadata_fetch,
        selected_audit=selected_audit,
    )
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()

    selected_task = (inputs["sizeProbeContract"] or {}).get("selectedArchiveTask")
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_split_archive_size_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_split_archive_access_review",
        "selectedArchiveTask": selected_task if access_ready else None,
        "selectedArchivePath": selected_audit.get("selectedArchivePath") if goal_achieved else None,
        "selectedArchiveSizeBytes": selected_audit.get("selectedArchiveSizeBytes") if goal_achieved else None,
        "selectedArchiveSizeClass": selected_audit.get("selectedArchiveSizeClass") if goal_achieved else None,
        "labelsOnlyArchiveCandidateCount": labels_audit.get("labelsOnlyArchiveCandidateCount"),
        "metadataFetchExecuted": metadata_fetch.get("metadataFetchExecuted"),
        "archiveDownloadApproved": False,
        "archiveDownloadExecuted": False,
        "partialArchiveContentDownloadExecuted": False,
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
    range_contract = _range_index_contract(summary)
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "remoteArchiveFileInventory": inventory,
        "selectedArchiveSizeAudit": selected_audit,
        "labelsOnlyArchiveCandidateAudit": labels_audit,
        "splitArchiveRangeIndexProbeContract": range_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "split_archive_size_probe_summary.json", summary)
    _write_json(output_root / "remote_archive_file_inventory.json", inventory)
    _write_json(output_root / "selected_archive_size_audit.json", selected_audit)
    _write_json(output_root / "labels_only_archive_candidate_audit.json", labels_audit)
    _write_json(output_root / "split_archive_range_index_probe_contract.json", range_contract)
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
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_huggingface_split_archive_metadata_probe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_split_archive_size_probe(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
