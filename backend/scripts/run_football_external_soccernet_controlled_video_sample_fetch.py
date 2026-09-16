from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_video_sample_download_approval_v1"
DEFAULT_RANGE_INDEX_DIR_NAME = "football_external_soccernet_split_archive_range_index_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_controlled_video_sample_fetch_v1"
DEFAULT_TIMEOUT_SECONDS = 120

BLOCKER_APPROVAL_MISSING = "football_external_soccernet_video_sample_download_approval_missing"
BLOCKER_RANGE_CONTRACT_GAP = "football_external_soccernet_video_sample_range_contract_gap"
BLOCKER_FETCH_FAILED = "football_external_soccernet_controlled_video_sample_fetch_failed"

NEXT_APPROVAL = "football_external_soccernet_video_sample_download_approval"
NEXT_RANGE_REPAIR = "football_external_soccernet_video_sample_range_contract_repair"
NEXT_FETCH_DEBUG = "football_external_soccernet_controlled_video_sample_fetch_debug"
NEXT_SAMPLE_PROBE = "football_external_soccernet_video_sample_probe"

HUGGINGFACE_REPO_BY_TASK = {
    "spotting-ball-2025": "SoccerNet/SN-BAS-2025",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "controlled_video_member_byte_sample_fetch",
            "successCriteria": [
                "fetch only the approved capped byte sample from the selected video member range",
                "do not fetch the full video member or full archive",
                "write byte-count, range, and hash audit artifacts",
            ],
            "failureAdaptation": "If range math is invalid, repair the video sample range contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "video_sample_range_contract_repair",
            "successCriteria": [
                "repair selected member offsets from ZIP central directory metadata",
                "preserve byte cap and full-archive block",
            ],
            "failureAdaptation": "If remote range fetch fails, write fetch blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "controlled_video_sample_fetch_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before training, promotion, runtime mutation, or full download",
            ],
            "failureAdaptation": "Route to approval, range repair, or fetch debug.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    range_root = candidate_root / DEFAULT_RANGE_INDEX_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "approvalSummary": _load_json(approval_root / "video_sample_download_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "video_sample_download_approval_contract.json"),
        "zipAudit": _load_json(range_root / "zip_central_directory_audit.json"),
    }


def _approval_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoSampleDownloadApproved") is True
        and summary.get("fullArchiveDownloadApproved") is False
        and summary.get("videoMemberDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(contract, dict)
        and contract.get("contractName") == "football_external_soccernet_controlled_video_sample_fetch"
        and contract.get("videoSampleDownloadApproved") is True
        and contract.get("fullArchiveDownloadApproved") is False
        and contract.get("videoMemberDownloadExecuted") is False
        and int(contract.get("maxApprovedBytes") or 0) > 0
        and bool(contract.get("selectedVideoMemberPath"))
    )


def _resolve_url(task: str, archive_path: str) -> str | None:
    repo_id = HUGGINGFACE_REPO_BY_TASK.get(task)
    if not repo_id:
        return None
    return f"https://huggingface.co/datasets/{repo_id}/resolve/main/{quote(archive_path)}"


def _range_fetch(url: str, start: int, end: int, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "User-Agent": "fotball-analyst-soccernet-controlled-video-sample-fetch/1.0",
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


def _selected_range(contract: dict[str, Any], zip_audit: dict[str, Any] | None) -> dict[str, Any]:
    selected_path = str(contract.get("selectedVideoMemberPath") or "")
    entries = zip_audit.get("zipEntries") if isinstance(zip_audit, dict) else []
    entries = entries if isinstance(entries, list) else []
    selected = next((row for row in entries if isinstance(row, dict) and row.get("path") == selected_path), None)
    central_offset = int((zip_audit or {}).get("centralDirectoryOffset") or 0)
    if not isinstance(selected, dict):
        return {"valid": False, "reason": "selected_member_missing", "selectedVideoMemberPath": selected_path}
    start = int(selected.get("localHeaderOffset") or contract.get("selectedLocalHeaderOffset") or 0)
    member_end = _member_end_offsets(entries, central_offset).get(selected_path)
    max_bytes = int(contract.get("maxApprovedBytes") or 0)
    if start < 0 or member_end is None or member_end < start or max_bytes <= 0:
        return {"valid": False, "reason": "invalid_range_inputs", "selectedVideoMemberPath": selected_path}
    end = min(member_end, start + max_bytes - 1)
    return {
        "valid": True,
        "selectedVideoMemberPath": selected_path,
        "rangeStart": start,
        "rangeEnd": end,
        "memberEnd": member_end,
        "requestedByteCount": end - start + 1,
        "maxApprovedBytes": max_bytes,
        "selectedCompressedSizeBytes": int(selected.get("compressedSizeBytes") or 0),
        "selectedUncompressedSizeBytes": int(selected.get("uncompressedSizeBytes") or 0),
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _classify(approval_ready: bool, range_contract: dict[str, Any], fetch_error: str | None) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "SoccerNet video sample approval is missing or unsafe; rerun approval before fetch.",
        )
    if range_contract.get("valid") is not True:
        return (
            BLOCKER_RANGE_CONTRACT_GAP,
            NEXT_RANGE_REPAIR,
            False,
            "Controlled video sample range is invalid; repair ZIP member range contract before fetch.",
        )
    if fetch_error:
        return (
            BLOCKER_FETCH_FAILED,
            NEXT_FETCH_DEBUG,
            False,
            "Controlled SoccerNet video sample range fetch failed; debug remote range access without widening scope.",
        )
    return (
        None,
        NEXT_SAMPLE_PROBE,
        True,
        "Controlled SoccerNet video sample bytes were fetched within the approved cap. Advance to sample probing before any broader video download.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "video_sample_download_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "video_sample_range_contract_gap", "selected": primary_blocker == BLOCKER_RANGE_CONTRACT_GAP, "primaryBlocker": BLOCKER_RANGE_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_RANGE_REPAIR},
            {"condition": "controlled_video_sample_fetch_failed", "selected": primary_blocker == BLOCKER_FETCH_FAILED, "primaryBlocker": BLOCKER_FETCH_FAILED, "nextRecommendedNextLever": NEXT_FETCH_DEBUG},
            {"condition": "controlled_video_sample_probe_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SAMPLE_PROBE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Controlled Video Sample Fetch",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected video member: `{summary.get('selectedVideoMemberPath')}`",
            f"- Sample bytes fetched: `{summary.get('sampleBytesFetched')}`",
            f"- Requested byte count: `{summary.get('requestedByteCount')}`",
            f"- Full video member downloaded: `{summary.get('videoMemberFullDownloadExecuted')}`",
            f"- Full archive downloaded: `{summary.get('archiveDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_controlled_video_sample_fetch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    attempt_number: int = 1,
    attempt_approach_family: str = "controlled_video_member_byte_sample_fetch",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _approval_ready(inputs["approvalSummary"], inputs["approvalContract"])
    contract = inputs["approvalContract"] or {}
    range_contract = _selected_range(contract, inputs["zipAudit"])
    url = _resolve_url("spotting-ball-2025", "valid.zip")
    fetch_audit: dict[str, Any] = {}
    sample_bytes = b""
    fetch_error: str | None = None
    if ready and range_contract.get("valid") is True and url:
        try:
            sample_bytes, fetch_audit = _range_fetch(url, int(range_contract["rangeStart"]), int(range_contract["rangeEnd"]), timeout_seconds)
        except Exception as exc:  # pragma: no cover - network failure path
            fetch_error = f"{type(exc).__name__}: {exc}"
    elif ready and range_contract.get("valid") is True:
        fetch_error = "missing_remote_url"

    primary_blocker, next_lever, goal_achieved, english = _classify(ready, range_contract, fetch_error)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    sample_path = output_root / "video_member_sample_bytes.bin"
    if goal_achieved:
        sample_path.write_bytes(sample_bytes)
    sample_sha = _sha256_bytes(sample_bytes) if sample_bytes else None
    sample_audit = {
        "generatedAt": generated_at,
        **range_contract,
        "remoteUrl": url,
        "fetchError": fetch_error,
        "fetchAudit": fetch_audit,
        "samplePath": str(sample_path) if goal_achieved else None,
        "sampleBytesFetched": len(sample_bytes),
        "sampleSha256": sample_sha,
        "archiveDownloadExecuted": False,
        "videoMemberFullDownloadExecuted": False,
        "videoMemberDownloadExecuted": goal_achieved,
    }
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_controlled_video_sample_fetch",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_sample_download_approval",
        "selectedVideoMemberPath": range_contract.get("selectedVideoMemberPath"),
        "requestedByteCount": range_contract.get("requestedByteCount"),
        "sampleBytesFetched": len(sample_bytes),
        "sampleSha256": sample_sha,
        "videoSampleFetchExecuted": goal_achieved,
        "videoMemberDownloadExecuted": goal_achieved,
        "videoMemberFullDownloadExecuted": False,
        "fullArchiveDownloadApproved": False,
        "archiveDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "controlledVideoSampleFetchAudit": sample_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "controlled_video_sample_fetch_summary.json", summary)
    _write_json(output_root / "controlled_video_sample_fetch_audit.json", sample_audit)
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
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="controlled_video_member_byte_sample_fetch")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_controlled_video_sample_fetch(
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
