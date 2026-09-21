from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import struct
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SIZE_PROBE_DIR_NAME = "football_external_soccernet_split_archive_size_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_split_archive_range_index_probe_v1"

BLOCKER_SIZE_PROBE_MISSING = "football_external_soccernet_split_archive_size_probe_missing"
BLOCKER_RANGE_PROBE_FAILED = "football_external_soccernet_split_archive_range_index_probe_failed"
BLOCKER_LABEL_MEMBER_MISSING = "football_external_soccernet_split_archive_label_member_missing"

NEXT_SIZE_PROBE = "football_external_soccernet_split_archive_size_probe"
NEXT_RANGE_CONTRACT_REPAIR = "football_external_soccernet_split_archive_range_index_contract_repair"
NEXT_MANUAL_CONTENT_REVIEW = "football_external_soccernet_split_archive_manual_content_review"
NEXT_LABEL_MEMBER_APPROVAL = "football_external_soccernet_zip_label_member_extract_approval"

HUGGINGFACE_REPO_BY_TASK = {
    "spotting-ball-2025": "SoccerNet/SN-BAS-2025",
}
DEFAULT_TAIL_RANGE_BYTES = 2 * 1024 * 1024
MAX_CENTRAL_DIRECTORY_FETCH_BYTES = 8 * 1024 * 1024
EOCD_SIGNATURE = b"PK\x05\x06"
CENTRAL_DIR_SIGNATURE = b"PK\x01\x02"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_zip_central_directory_range_probe",
            "successCriteria": [
                "use only HTTP range metadata bytes or injected archive bytes",
                "parse ZIP central directory entries",
                "identify label members and video members without downloading full archive contents",
            ],
            "failureAdaptation": "If the ZIP index cannot be parsed, repair the range/index contract before any archive download.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_zip_index_contract_repair",
            "successCriteria": [
                "repair selected archive path or central-directory range size",
                "preserve no full archive/video download guardrails",
            ],
            "failureAdaptation": "If label members cannot be identified, route to manual content review.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_zip_index_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not fetch video members or approve training use",
            ],
            "failureAdaptation": "Stop before label extraction or full archive download.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    size_root = candidate_root / DEFAULT_SIZE_PROBE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "sizeSummary": _load_json(size_root / "split_archive_size_probe_summary.json"),
        "rangeContract": _load_json(size_root / "split_archive_range_index_probe_contract.json"),
    }


def _size_probe_ready(size_summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(size_summary, dict)
        and size_summary.get("goalAchieved") is True
        and size_summary.get("primaryBlocker") is None
        and size_summary.get("selectedArchiveTask") == "spotting-ball-2025"
        and size_summary.get("selectedArchivePath")
        and int(size_summary.get("selectedArchiveSizeBytes") or 0) > 0
        and size_summary.get("archiveDownloadExecuted") is False
        and size_summary.get("trainingExecuted") is False
        and isinstance(contract, dict)
        and contract.get("contractName") == "football_external_soccernet_split_archive_range_index_probe"
        and contract.get("downloadAllowedByThisBatch") is False
        and contract.get("fullArchiveDownloadApproved") is False
        and contract.get("partialRangeMetadataProbeOnly") is True
    )


def _resolve_url(task: str, archive_path: str) -> str | None:
    repo_id = HUGGINGFACE_REPO_BY_TASK.get(task)
    if not repo_id:
        return None
    return f"https://huggingface.co/datasets/{repo_id}/resolve/main/{quote(archive_path)}"


def _head_archive(url: str, timeout_seconds: int) -> dict[str, Any]:
    request = Request(url, method="HEAD", headers={"User-Agent": "fotball-analyst-soccernet-range-index-probe/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return {
            "headExecuted": True,
            "httpStatus": response.status,
            "contentLength": int(response.headers.get("Content-Length") or 0),
            "acceptRanges": response.headers.get("Accept-Ranges"),
            "contentType": response.headers.get("Content-Type"),
            "resolvedHost": response.url.split("/")[2] if "://" in response.url else None,
        }


def _range_fetch(url: str, range_header: str, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "User-Agent": "fotball-analyst-soccernet-range-index-probe/1.0",
            "Range": range_header,
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        data = response.read()
        return data, {
            "rangeHeader": range_header,
            "httpStatus": response.status,
            "contentLength": int(response.headers.get("Content-Length") or len(data)),
            "contentRange": response.headers.get("Content-Range"),
            "bytesFetched": len(data),
            "resolvedHost": response.url.split("/")[2] if "://" in response.url else None,
        }


def _parse_content_range_start(content_range: str | None, archive_size: int, bytes_fetched: int) -> int:
    if content_range and content_range.startswith("bytes "):
        start_text = content_range.split(" ", 1)[1].split("-", 1)[0]
        try:
            return int(start_text)
        except ValueError:
            pass
    return max(0, archive_size - bytes_fetched)


def _fetch_remote_index_bytes(task: str, archive_path: str, expected_size: int, timeout_seconds: int) -> tuple[bytes | None, dict[str, Any]]:
    url = _resolve_url(task, archive_path)
    if not url:
        return None, {"rangeProbeExecuted": False, "rangeProbeError": f"No resolve URL mapping for task {task}"}
    try:
        head = _head_archive(url, timeout_seconds)
        archive_size = int(head.get("contentLength") or expected_size)
        tail_size = min(DEFAULT_TAIL_RANGE_BYTES, archive_size)
        tail, tail_audit = _range_fetch(url, f"bytes=-{tail_size}", timeout_seconds)
        tail_start = _parse_content_range_start(tail_audit.get("contentRange"), archive_size, len(tail))
        audit = {
            "rangeProbeExecuted": True,
            "rangeProbeError": None,
            "resolveUrl": f"https://huggingface.co/datasets/{HUGGINGFACE_REPO_BY_TASK.get(task)}/resolve/main/{archive_path}",
            "head": head,
            "tailRange": tail_audit,
            "tailStartOffset": tail_start,
            "archiveSizeBytes": archive_size,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "partialRangeMetadataProbeOnly": True,
        }
        return tail, audit
    except (HTTPError, URLError, TimeoutError) as exc:
        status = exc.code if isinstance(exc, HTTPError) else None
        return None, {
            "rangeProbeExecuted": True,
            "rangeProbeError": str(exc),
            "httpStatus": status,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "partialRangeMetadataProbeOnly": True,
        }


def _parse_eocd(buffer: bytes, archive_size: int, tail_start_offset: int) -> dict[str, Any]:
    eocd_pos = buffer.rfind(EOCD_SIGNATURE)
    if eocd_pos < 0 or eocd_pos + 22 > len(buffer):
        return {"zipCentralDirectoryParsed": False, "parseError": "EOCD signature not found in range buffer"}
    (
        _signature,
        disk_number,
        central_dir_disk,
        entries_on_disk,
        total_entries,
        central_dir_size,
        central_dir_offset,
        comment_length,
    ) = struct.unpack_from("<4s4H2LH", buffer, eocd_pos)
    central_dir_in_buffer = central_dir_offset >= tail_start_offset and central_dir_offset + central_dir_size <= tail_start_offset + len(buffer)
    return {
        "zipCentralDirectoryParsed": True,
        "eocdOffsetInBuffer": eocd_pos,
        "eocdAbsoluteOffset": tail_start_offset + eocd_pos,
        "diskNumber": disk_number,
        "centralDirectoryDisk": central_dir_disk,
        "entriesOnDisk": entries_on_disk,
        "totalEntries": total_entries,
        "centralDirectorySizeBytes": central_dir_size,
        "centralDirectoryOffset": central_dir_offset,
        "commentLength": comment_length,
        "centralDirectoryInBuffer": central_dir_in_buffer,
        "archiveSizeBytes": archive_size,
    }


def _parse_central_directory(central_dir: bytes) -> tuple[list[dict[str, Any]], str | None]:
    entries: list[dict[str, Any]] = []
    offset = 0
    while offset + 46 <= len(central_dir):
        if central_dir[offset : offset + 4] != CENTRAL_DIR_SIGNATURE:
            break
        fields = struct.unpack_from("<4s6H3L5H2L", central_dir, offset)
        compression_method = fields[4]
        crc32 = fields[7]
        compressed_size = fields[8]
        uncompressed_size = fields[9]
        filename_length = fields[10]
        extra_length = fields[11]
        comment_length = fields[12]
        local_header_offset = fields[16]
        name_start = offset + 46
        name_end = name_start + filename_length
        if name_end > len(central_dir):
            return entries, "Central directory filename extends past buffer"
        path = central_dir[name_start:name_end].decode("utf-8", errors="replace")
        entries.append(
            {
                "path": path,
                "isDirectory": path.endswith("/"),
                "compressionMethod": compression_method,
                "crc32": crc32,
                "compressedSizeBytes": compressed_size,
                "uncompressedSizeBytes": uncompressed_size,
                "localHeaderOffset": local_header_offset,
            }
        )
        offset = name_end + extra_length + comment_length
    if not entries:
        return entries, "No central directory entries parsed"
    return entries, None


def _index_from_bytes(
    *,
    buffer: bytes,
    archive_size: int,
    tail_start_offset: int,
) -> dict[str, Any]:
    eocd = _parse_eocd(buffer, archive_size, tail_start_offset)
    if eocd.get("zipCentralDirectoryParsed") is not True:
        return {**eocd, "zipEntries": []}
    if eocd.get("centralDirectoryInBuffer") is not True:
        return {**eocd, "zipEntries": [], "parseError": "Central directory is not fully available in current range buffer"}
    cd_start = int(eocd["centralDirectoryOffset"]) - tail_start_offset
    cd_size = int(eocd["centralDirectorySizeBytes"])
    entries, parse_error = _parse_central_directory(buffer[cd_start : cd_start + cd_size])
    return {
        **eocd,
        "zipEntries": entries,
        "zipEntryCount": len(entries),
        "parseError": parse_error,
    }


def _entry_extension(path: str) -> str:
    name = Path(path).name.lower()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[1]


def _content_risk_audit(index: dict[str, Any]) -> dict[str, Any]:
    entries = index.get("zipEntries") if isinstance(index, dict) else []
    if not isinstance(entries, list):
        entries = []
    label_extensions = {".json", ".csv", ".txt", ".xml"}
    video_extensions = {".mp4", ".mkv", ".avi", ".mov"}
    label_members = []
    video_members = []
    extension_counts: Counter[str] = Counter()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if entry.get("isDirectory"):
            continue
        ext = _entry_extension(path)
        extension_counts[ext or "<none>"] += 1
        lower = path.lower()
        if ext in label_extensions and "label" in lower:
            label_members.append(entry)
        if ext in video_extensions:
            video_members.append(entry)
    return {
        "zipEntryCount": len(entries),
        "labelMemberCount": len(label_members),
        "labelMemberPaths": [str(row.get("path")) for row in label_members],
        "videoMemberCount": len(video_members),
        "videoMemberPaths": [str(row.get("path")) for row in video_members],
        "containsOriginalVideoFiles": bool(video_members),
        "extensionCounts": dict(sorted(extension_counts.items())),
        "fullArchiveDownloadRecommended": False,
        "labelMemberRangeExtractionFeasible": bool(label_members),
        "trainingUseAllowed": False,
    }


def _label_extract_contract(summary_fields: dict[str, Any], content_risk: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": NEXT_LABEL_MEMBER_APPROVAL,
        "sourceBatch": "football_external_soccernet_split_archive_range_index_probe",
        "selectedArchiveTask": summary_fields.get("selectedArchiveTask"),
        "selectedArchivePath": summary_fields.get("selectedArchivePath"),
        "labelMemberPaths": content_risk.get("labelMemberPaths") or [],
        "videoMemberPaths": content_risk.get("videoMemberPaths") or [],
        "approvalRequiredBeforeLabelMemberExtraction": True,
        "fullArchiveDownloadApproved": False,
        "videoMemberDownloadAllowed": False,
        "labelMemberRangeExtractionOnly": True,
        "trainingUseAllowed": False,
    }


def _classify(
    *,
    size_ready: bool,
    range_audit: dict[str, Any],
    zip_index: dict[str, Any],
    content_risk: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not size_ready:
        return (
            BLOCKER_SIZE_PROBE_MISSING,
            NEXT_SIZE_PROBE,
            False,
            "Split archive size probe truth is missing or unsafe; rerun the size probe before ZIP index probing.",
        )
    if range_audit.get("rangeProbeError") or zip_index.get("zipCentralDirectoryParsed") is not True or zip_index.get("parseError"):
        return (
            BLOCKER_RANGE_PROBE_FAILED,
            NEXT_RANGE_CONTRACT_REPAIR,
            False,
            "ZIP central directory could not be parsed from metadata ranges; repair the range/index contract before any archive download.",
        )
    if int(content_risk.get("labelMemberCount") or 0) <= 0:
        return (
            BLOCKER_LABEL_MEMBER_MISSING,
            NEXT_MANUAL_CONTENT_REVIEW,
            False,
            "ZIP index parsed but no label member was identified; manually review archive contents before extraction.",
        )
    return (
        None,
        NEXT_LABEL_MEMBER_APPROVAL,
        True,
        "ZIP index parsed without full archive download. Label members were identified, and video members remain blocked; advance to label-member range extraction approval.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "split_archive_size_probe_missing",
                "selected": primary_blocker == BLOCKER_SIZE_PROBE_MISSING,
                "primaryBlocker": BLOCKER_SIZE_PROBE_MISSING,
                "nextRecommendedNextLever": NEXT_SIZE_PROBE,
            },
            {
                "condition": "zip_range_index_probe_failed",
                "selected": primary_blocker == BLOCKER_RANGE_PROBE_FAILED,
                "primaryBlocker": BLOCKER_RANGE_PROBE_FAILED,
                "nextRecommendedNextLever": NEXT_RANGE_CONTRACT_REPAIR,
            },
            {
                "condition": "label_member_missing",
                "selected": primary_blocker == BLOCKER_LABEL_MEMBER_MISSING,
                "primaryBlocker": BLOCKER_LABEL_MEMBER_MISSING,
                "nextRecommendedNextLever": NEXT_MANUAL_CONTENT_REVIEW,
            },
            {
                "condition": "label_member_extract_approval_ready",
                "selected": goal_achieved,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_LABEL_MEMBER_APPROVAL,
            },
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Split Archive Range Index Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected archive task: `{summary.get('selectedArchiveTask')}`",
            f"- Selected archive path: `{summary.get('selectedArchivePath')}`",
            f"- ZIP central directory parsed: `{summary.get('zipCentralDirectoryParsed')}`",
            f"- Label members: `{summary.get('labelMemberCount')}`",
            f"- Video members: `{summary.get('videoMemberCount')}`",
            f"- Archive download executed: `{summary.get('archiveDownloadExecuted')}`",
            f"- Video member download executed: `{summary.get('videoMemberDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_split_archive_range_index_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    archive_bytes: bytes | None = None,
    timeout_seconds: int = 60,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_zip_central_directory_range_probe",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    size_ready = _size_probe_ready(inputs["sizeSummary"], inputs["rangeContract"])
    task = str((inputs["rangeContract"] or {}).get("selectedArchiveTask") or "")
    archive_path = str((inputs["rangeContract"] or {}).get("selectedArchivePath") or "")
    expected_size = int((inputs["rangeContract"] or {}).get("selectedArchiveSizeBytes") or 0)

    if archive_bytes is not None:
        range_buffer = archive_bytes
        range_audit = {
            "rangeProbeExecuted": True,
            "rangeProbeError": None,
            "injectedArchiveBytes": True,
            "archiveSizeBytes": len(archive_bytes),
            "tailStartOffset": 0,
            "rangeBytesFetched": len(archive_bytes),
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "partialRangeMetadataProbeOnly": True,
        }
    elif size_ready:
        range_buffer, range_audit = _fetch_remote_index_bytes(task, archive_path, expected_size, timeout_seconds)
    else:
        range_buffer = None
        range_audit = {
            "rangeProbeExecuted": False,
            "rangeProbeError": None,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "partialRangeMetadataProbeOnly": True,
        }

    if range_buffer is not None:
        archive_size = int(range_audit.get("archiveSizeBytes") or len(range_buffer))
        tail_start = int(range_audit.get("tailStartOffset") or 0)
        zip_index = _index_from_bytes(buffer=range_buffer, archive_size=archive_size, tail_start_offset=tail_start)
    else:
        zip_index = {"zipCentralDirectoryParsed": False, "parseError": range_audit.get("rangeProbeError"), "zipEntries": []}

    content_risk = _content_risk_audit(zip_index)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        size_ready=size_ready,
        range_audit=range_audit,
        zip_index=zip_index,
        content_risk=content_risk,
    )
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_split_archive_range_index_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_split_archive_size_probe",
        "selectedArchiveTask": task if size_ready else None,
        "selectedArchivePath": archive_path if size_ready else None,
        "zipCentralDirectoryParsed": zip_index.get("zipCentralDirectoryParsed") is True and not zip_index.get("parseError"),
        "zipEntryCount": zip_index.get("zipEntryCount") or 0,
        "labelMemberCount": content_risk.get("labelMemberCount"),
        "videoMemberCount": content_risk.get("videoMemberCount"),
        "containsOriginalVideoFiles": content_risk.get("containsOriginalVideoFiles"),
        "archiveDownloadApproved": False,
        "archiveDownloadExecuted": False,
        "partialArchiveRangeFetchExecuted": range_audit.get("rangeProbeExecuted") is True,
        "partialArchiveMetadataOnly": True,
        "videoMemberDownloadAllowed": False,
        "videoMemberDownloadExecuted": False,
        "labelMemberExtractionApproved": False,
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
    extract_contract = _label_extract_contract(summary, content_risk)
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "httpRangeProbeAudit": range_audit,
        "zipCentralDirectoryAudit": zip_index,
        "splitArchiveContentRiskAudit": content_risk,
        "zipLabelMemberExtractApprovalContract": extract_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "split_archive_range_index_probe_summary.json", summary)
    _write_json(output_root / "http_range_probe_audit.json", range_audit)
    _write_json(output_root / "zip_central_directory_audit.json", zip_index)
    _write_json(output_root / "split_archive_content_risk_audit.json", content_risk)
    _write_json(output_root / "zip_label_member_extract_approval_contract.json", extract_contract)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_zip_central_directory_range_probe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_split_archive_range_index_probe(
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
