from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import json
from pathlib import Path
import shutil
import struct
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_FETCH_DIR_NAME = "football_external_soccernet_controlled_video_sample_fetch_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_sample_probe_v1"

BLOCKER_FETCH_MISSING = "football_external_soccernet_controlled_video_sample_fetch_missing"
BLOCKER_SAMPLE_MISSING = "football_external_soccernet_video_sample_bytes_missing"
BLOCKER_PROBE_GAP = "football_external_soccernet_video_sample_probe_gap"

NEXT_FETCH = "football_external_soccernet_controlled_video_sample_fetch"
NEXT_PROBE_REPAIR = "football_external_soccernet_video_sample_probe_contract_repair"
NEXT_MEMBER_EXTRACT_APPROVAL = "football_external_soccernet_video_member_extract_approval"
NEXT_FRAME_PROBE = "football_external_soccernet_video_frame_probe"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "controlled_video_sample_signature_probe",
            "successCriteria": [
                "classify the controlled sample bytes as playable video or encrypted ZIP member bytes",
                "do not widen download scope",
                "route to member extraction approval if the sample is encrypted ZIP data",
            ],
            "failureAdaptation": "If sample metadata is incomplete, repair probe contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "video_sample_probe_contract_repair",
            "successCriteria": [
                "repair sample path/hash/signature audit from saved fetch artifacts",
                "preserve full-download and training blocks",
            ],
            "failureAdaptation": "If sample bytes are missing, route back to controlled sample fetch.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "video_sample_probe_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before training, promotion, runtime mutation, or wider download",
            ],
            "failureAdaptation": "Route to fetch, probe repair, or member extraction approval.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fetch_root = candidate_root / DEFAULT_FETCH_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fetchSummary": _load_json(fetch_root / "controlled_video_sample_fetch_summary.json"),
        "fetchAudit": _load_json(fetch_root / "controlled_video_sample_fetch_audit.json"),
    }


def _fetch_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoSampleFetchExecuted") is True
        and summary.get("videoMemberFullDownloadExecuted") is False
        and summary.get("archiveDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and bool(audit.get("samplePath"))
    )


def _signature_class(prefix: bytes) -> str:
    if prefix.startswith(b"\x00\x00\x00") and b"ftyp" in prefix[:16]:
        return "mp4_ftyp"
    if prefix.startswith(b"PK\x03\x04"):
        return "zip_local_file_header"
    return "unknown"


def _zip_local_header(prefix: bytes) -> dict[str, Any]:
    if not prefix.startswith(b"PK\x03\x04") or len(prefix) < 30:
        return {"zipLocalHeaderParsed": False}
    (
        _sig,
        version_needed,
        general_purpose_flag,
        compression_method,
        _mtime,
        _mdate,
        crc32,
        compressed_size,
        uncompressed_size,
        file_name_length,
        extra_length,
    ) = struct.unpack("<IHHHHHIIIHH", prefix[:30])
    name_start = 30
    name_end = min(len(prefix), name_start + file_name_length)
    try:
        file_name = prefix[name_start:name_end].decode("utf-8", errors="replace")
    except Exception:
        file_name = ""
    return {
        "zipLocalHeaderParsed": True,
        "versionNeeded": version_needed,
        "generalPurposeFlag": general_purpose_flag,
        "compressionMethod": compression_method,
        "aesEncrypted": compression_method == 99,
        "crc32": crc32,
        "compressedSizeFromHeader": compressed_size,
        "uncompressedSizeFromHeader": uncompressed_size,
        "fileNameLength": file_name_length,
        "extraFieldLength": extra_length,
        "fileNamePreview": file_name,
    }


def _probe_sample(sample_path: Path) -> dict[str, Any]:
    size = sample_path.stat().st_size if sample_path.exists() else 0
    prefix = sample_path.read_bytes()[:512] if sample_path.exists() else b""
    signature = _signature_class(prefix)
    zip_header = _zip_local_header(prefix)
    return {
        "samplePath": str(sample_path),
        "sampleExists": sample_path.exists(),
        "sampleSizeBytes": size,
        "firstBytesHex": prefix[:32].hex(),
        "fileSignatureClass": signature,
        "sampleIsPlayableVideo": signature == "mp4_ftyp",
        "sampleIsEncryptedZipMember": signature == "zip_local_file_header" and zip_header.get("aesEncrypted") is True,
        "zipLocalHeader": zip_header,
        "ffprobeAvailable": shutil.which("ffprobe") is not None,
        "archiveDownloadExecuted": False,
        "videoMemberFullDownloadExecuted": False,
    }


def _classify(fetch_ready: bool, sample_probe: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not fetch_ready:
        return (
            BLOCKER_FETCH_MISSING,
            NEXT_FETCH,
            False,
            "Controlled SoccerNet video sample fetch truth is missing or unsafe; rerun fetch first.",
        )
    if sample_probe.get("sampleExists") is not True or int(sample_probe.get("sampleSizeBytes") or 0) <= 0:
        return (
            BLOCKER_SAMPLE_MISSING,
            NEXT_FETCH,
            False,
            "Controlled SoccerNet sample bytes are missing; rerun controlled sample fetch.",
        )
    if sample_probe.get("sampleIsPlayableVideo") is True:
        return (
            None,
            NEXT_FRAME_PROBE,
            True,
            "Controlled SoccerNet sample appears directly playable; advance to a bounded frame probe.",
        )
    if sample_probe.get("sampleIsEncryptedZipMember") is True:
        return (
            None,
            NEXT_MEMBER_EXTRACT_APPROVAL,
            True,
            "Controlled SoccerNet sample is encrypted ZIP member bytes, not playable MP4. Approve a scoped member extraction before frame probing.",
        )
    return (
        BLOCKER_PROBE_GAP,
        NEXT_PROBE_REPAIR,
        False,
        "Controlled SoccerNet sample signature is unknown; repair probe contract before widening scope.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool, sample_probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "controlled_video_sample_fetch_missing", "selected": primary_blocker == BLOCKER_FETCH_MISSING, "primaryBlocker": BLOCKER_FETCH_MISSING, "nextRecommendedNextLever": NEXT_FETCH},
            {"condition": "video_sample_bytes_missing", "selected": primary_blocker == BLOCKER_SAMPLE_MISSING, "primaryBlocker": BLOCKER_SAMPLE_MISSING, "nextRecommendedNextLever": NEXT_FETCH},
            {"condition": "sample_is_encrypted_zip_member", "selected": sample_probe.get("sampleIsEncryptedZipMember") is True and goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_MEMBER_EXTRACT_APPROVAL},
            {"condition": "sample_is_playable_video", "selected": sample_probe.get("sampleIsPlayableVideo") is True and goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_FRAME_PROBE},
            {"condition": "video_sample_probe_gap", "selected": primary_blocker == BLOCKER_PROBE_GAP, "primaryBlocker": BLOCKER_PROBE_GAP, "nextRecommendedNextLever": NEXT_PROBE_REPAIR},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Sample Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Sample probe completed: `{summary.get('sampleProbeCompleted')}`",
            f"- Playable video: `{summary.get('sampleIsPlayableVideo')}`",
            f"- Encrypted ZIP member: `{summary.get('sampleIsEncryptedZipMember')}`",
            f"- Sample bytes: `{summary.get('sampleSizeBytes')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_sample_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "controlled_video_sample_signature_probe",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _fetch_ready(inputs["fetchSummary"], inputs["fetchAudit"])
    sample_path = Path(str((inputs["fetchAudit"] or {}).get("samplePath") or ""))
    sample_probe = _probe_sample(sample_path) if sample_path else {"sampleExists": False, "sampleSizeBytes": 0}
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, sample_probe)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_sample_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_controlled_video_sample_fetch",
        "sampleProbeCompleted": goal_achieved,
        "sampleSizeBytes": sample_probe.get("sampleSizeBytes"),
        "sampleIsPlayableVideo": sample_probe.get("sampleIsPlayableVideo") is True,
        "sampleIsEncryptedZipMember": sample_probe.get("sampleIsEncryptedZipMember") is True,
        "fileSignatureClass": sample_probe.get("fileSignatureClass"),
        "archiveDownloadExecuted": False,
        "videoMemberFullDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved, sample_probe)
    batch_outcome = {
        "summary": summary,
        "videoSampleProbeAudit": sample_probe,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_sample_probe_summary.json", summary)
    _write_json(output_root / "video_sample_probe_audit.json", sample_probe)
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
    parser.add_argument("--attempt-approach-family", default="controlled_video_sample_signature_probe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_sample_probe(
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
