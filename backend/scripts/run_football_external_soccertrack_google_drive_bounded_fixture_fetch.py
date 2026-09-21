from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_PROBE_DIR_NAME = "football_external_soccertrack_google_drive_fixture_access_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1"
DEFAULT_TOOL_PYTHON = REPO_ROOT / "backend" / "storage" / "tools" / "gdrive-probe-venv" / "bin" / "python"

BLOCKER_PROBE_UNREADY = "football_external_soccertrack_google_drive_fixture_probe_missing_or_unready"
BLOCKER_FETCH_FAILED = "football_external_soccertrack_google_drive_bounded_fixture_fetch_failed"

NEXT_PROBE = "football_external_soccertrack_google_drive_fixture_access_probe"
NEXT_FETCH_REPAIR = "football_external_soccertrack_google_drive_bounded_fixture_fetch_repair"
NEXT_MATERIALIZATION = "football_external_soccertrack_sample_fixture_materialization"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
MAX_FIXTURE_FILE_BYTES = 6_000_000_000
MAX_TOTAL_FIXTURE_BYTES = 15_000_000_000
OPTIONAL_LARGE_DERIVED_SUFFIXES = ("_mapx.npy", "_mapy.npy")

Downloader = Callable[[str, str, Path, Path], bytes | Path]


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "google_drive_bounded_fixture_fetch",
            "successCriteria": [
                "download only selected BAS/GSR/MOT fixture files from the listed Drive match",
                "skip all video/full-dataset media files",
                "hash every downloaded fixture file and write provenance truth",
            ],
            "failureAdaptation": "If any selected fixture file fails, stop with a repair blocker instead of partial materialization.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "google_drive_bounded_fetch_repair",
            "successCriteria": [
                "repair gdown/local tool path or selected file-id contract",
                "preserve selected-match and non-video-only scope",
            ],
            "failureAdaptation": "If fetch still fails, write blocker summary with exact failing IDs.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "google_drive_bounded_fetch_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not train, promote, mutate runtime defaults, or fetch full videos",
            ],
            "failureAdaptation": "Stop before materialization until bounded fixture files exist locally.",
        },
    ]


def _load_probe_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    probe_root = candidate_root / DEFAULT_PROBE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "probeRoot": probe_root,
        "probeSummary": _load_json(probe_root / "google_drive_fixture_access_probe_summary.json"),
        "candidateManifest": _load_json(probe_root / "drive_fixture_candidate_manifest.json"),
    }


def _probe_ready(summary: dict[str, Any] | None, manifest: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("driveListingAccessible") is True
        and summary.get("metadataListingOnly") is True
        and summary.get("fileContentDownloadExecuted") is False
        and summary.get("datasetDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(manifest, dict)
        and manifest.get("selectedMatchId")
        and int(manifest.get("completeFixtureCandidateMatchCount") or 0) >= 1
    )


def _selected_match(manifest: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(manifest, dict):
        return None
    selected_match_id = manifest.get("selectedMatchId")
    for row in manifest.get("candidateMatches") or []:
        if isinstance(row, dict) and row.get("matchId") == selected_match_id:
            return row
    return None


def _selected_files(match: dict[str, Any] | None) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    if not isinstance(match, dict):
        return [], [], []
    by_task = match.get("selectedFileIdsByTask")
    if not isinstance(by_task, dict):
        return [], []
    fixture_rows: list[dict[str, str]] = []
    skipped_video_rows: list[dict[str, str]] = []
    skipped_optional_rows: list[dict[str, str]] = []
    for task in ["bas", "gsr", "mot", "videos"]:
        rows = by_task.get(task) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            file_id = str(row.get("id") or "")
            path = str(row.get("path") or "")
            if not file_id or not path:
                continue
            record = {"taskId": task, "id": file_id, "path": path}
            if Path(path).suffix.lower() in VIDEO_EXTENSIONS or task == "videos":
                skipped_video_rows.append(record)
            elif path.lower().endswith(OPTIONAL_LARGE_DERIVED_SUFFIXES):
                skipped_optional_rows.append(record)
            else:
                fixture_rows.append(record)
    return fixture_rows, skipped_video_rows, skipped_optional_rows


def _safe_relative(match_id: str, source_path: str) -> str:
    return f"sample_fixture_files/selected_match_{match_id}/" + source_path.replace("/", "__")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gdown_download_file(file_id: str, source_path: str, output_root: Path, tool_python: Path) -> Path:
    if not tool_python.exists():
        raise RuntimeError(f"Google Drive probe tool is missing: {tool_python}")
    temp_dir = output_root / "_gdown_download_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{file_id}_{Path(source_path).name}"
    helper = """
import gdown
import sys

file_id = sys.argv[1]
output = sys.argv[2]
path = gdown.download(id=file_id, output=output, quiet=True, use_cookies=False)
if not path:
    raise SystemExit("gdown returned no output path")
print(path)
"""
    success = False
    try:
        subprocess.run(
            [str(tool_python), "-c", helper, file_id, str(temp_path)],
            check=True,
            text=True,
            capture_output=True,
            timeout=1800,
        )
        success = True
        return temp_path
    finally:
        if not success:
            temp_path.unlink(missing_ok=True)
        for partial_path in temp_dir.glob(f"{file_id}_{Path(source_path).name}*.part"):
            partial_path.unlink(missing_ok=True)


def _download_selected_files(
    *,
    output_root: Path,
    selected_match_id: str,
    selected_rows: list[dict[str, str]],
    tool_python: Path,
    downloader: Downloader,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    total_bytes = 0
    for row in selected_rows:
        file_id = row["id"]
        source_path = row["path"]
        try:
            result = downloader(file_id, source_path, output_root, tool_python)
            if isinstance(result, Path):
                size_bytes = result.stat().st_size
                sha256 = _sha256_file(result)
            else:
                size_bytes = len(result)
                sha256 = hashlib.sha256(result).hexdigest()
            if size_bytes > MAX_FIXTURE_FILE_BYTES:
                failures.append({"id": file_id, "sourcePath": source_path, "error": "downloaded file exceeded max fixture bytes"})
                if isinstance(result, Path):
                    result.unlink(missing_ok=True)
                continue
            if total_bytes + size_bytes > MAX_TOTAL_FIXTURE_BYTES:
                failures.append({"id": file_id, "sourcePath": source_path, "error": "bounded fixture fetch exceeded total byte cap"})
                if isinstance(result, Path):
                    result.unlink(missing_ok=True)
                continue
            relative_path = _safe_relative(selected_match_id, source_path)
            target = output_root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(result, Path):
                shutil.move(str(result), target)
            else:
                target.write_bytes(result)
            total_bytes += size_bytes
            downloaded.append(
                {
                    "taskId": row["taskId"],
                    "id": file_id,
                    "sourcePath": source_path,
                    "relativePath": relative_path,
                    "sizeBytes": size_bytes,
                    "sha256": sha256,
                }
            )
        except Exception as exc:  # pragma: no cover - live Drive failure path.
            temp_dir = output_root / "_gdown_download_tmp"
            for partial_path in temp_dir.glob(f"{file_id}_{Path(source_path).name}*.part"):
                partial_path.unlink(missing_ok=True)
            failures.append({"id": file_id, "sourcePath": source_path, "error": str(exc)})
    return downloaded, failures


def _classify(probe_ready: bool, downloaded_count: int, selected_count: int, failure_count: int) -> tuple[str | None, str, bool, bool, str]:
    if not probe_ready:
        return (
            BLOCKER_PROBE_UNREADY,
            NEXT_PROBE,
            False,
            False,
            "Google Drive bounded fixture fetch requires a successful Drive fixture access probe first.",
        )
    if failure_count or downloaded_count != selected_count:
        return (
            BLOCKER_FETCH_FAILED,
            NEXT_FETCH_REPAIR,
            False,
            True,
            "Bounded Google Drive fixture fetch failed or was incomplete; repair selected IDs/tooling before materialization.",
        )
    return (
        None,
        NEXT_MATERIALIZATION,
        True,
        True,
        "Bounded Google Drive fixture files were downloaded locally for one selected match. Advance to SoccerTrack sample fixture materialization; videos, full dataset, training, promotion, and runtime mutation remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "probe_unready", "selected": primary_blocker == BLOCKER_PROBE_UNREADY, "primaryBlocker": BLOCKER_PROBE_UNREADY, "nextRecommendedNextLever": NEXT_PROBE},
            {"condition": "bounded_fetch_failed", "selected": primary_blocker == BLOCKER_FETCH_FAILED, "primaryBlocker": BLOCKER_FETCH_FAILED, "nextRecommendedNextLever": NEXT_FETCH_REPAIR},
            {"condition": "bounded_fetch_succeeded", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_MATERIALIZATION},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Google Drive Bounded Fixture Fetch",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Downloaded fixture files: `{summary.get('downloadedFixtureFileCount')}`",
            f"- Skipped video files: `{summary.get('skippedVideoFileCount')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_google_drive_bounded_fixture_fetch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    tool_python: Path = DEFAULT_TOOL_PYTHON,
    attempt_number: int = 1,
    attempt_approach_family: str = "google_drive_bounded_fixture_fetch",
    downloader: Downloader = _gdown_download_file,
) -> dict[str, Any]:
    inputs = _load_probe_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _probe_ready(inputs.get("probeSummary"), inputs.get("candidateManifest"))
    selected_match = _selected_match(inputs.get("candidateManifest"))
    selected_match_id = str(selected_match.get("matchId")) if selected_match else None
    selected_rows, skipped_video_rows, skipped_optional_rows = _selected_files(selected_match)
    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if ready and selected_match_id:
        downloaded, failures = _download_selected_files(
            output_root=output_root,
            selected_match_id=selected_match_id,
            selected_rows=selected_rows,
            tool_python=Path(tool_python),
            downloader=downloader,
        )
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(
        ready,
        len(downloaded),
        len(selected_rows),
        len(failures),
    )
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    downloaded_task_ids = sorted({row["taskId"] for row in downloaded})
    manifest = {
        "schemaVersion": "soccertrack_google_drive_bounded_fixture_fetch_manifest_v1",
        "generatedAt": generated_at,
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "fetchScope": "one_match_bas_gsr_mot_fixture_files_only",
        "downloadedFiles": downloaded,
        "skippedVideoFiles": skipped_video_rows,
        "skippedOptionalLargeDerivedFiles": skipped_optional_rows,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingExecuted": False,
    }
    provenance = {
        "schemaVersion": "soccertrack_google_drive_bounded_fixture_fetch_provenance_audit_v1",
        "generatedAt": generated_at,
        "downloadedFiles": downloaded,
        "failures": failures,
        "fetchFailureCount": len(failures),
        "sha256ByPath": {row["sourcePath"]: row["sha256"] for row in downloaded},
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingExecuted": False,
    }
    guardrail = {
        "schemaVersion": "soccertrack_google_drive_bounded_fetch_guardrail_audit_v1",
        "generatedAt": generated_at,
        "maxFixtureFileBytes": MAX_FIXTURE_FILE_BYTES,
        "maxTotalFixtureBytes": MAX_TOTAL_FIXTURE_BYTES,
        "selectedFixtureFileCount": len(selected_rows),
        "downloadedFixtureFileCount": len(downloaded),
        "skippedVideoFileCount": len(skipped_video_rows),
        "skippedOptionalLargeDerivedFileCount": len(skipped_optional_rows),
        "skippedVideoFiles": skipped_video_rows,
        "skippedOptionalLargeDerivedFiles": skipped_optional_rows,
        "videoDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_google_drive_bounded_fixture_fetch",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_google_drive_fixture_access_probe",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "selectedFixtureFileCount": len(selected_rows),
        "downloadedFixtureFileCount": len(downloaded),
        "downloadedTaskIds": downloaded_task_ids,
        "skippedVideoFileCount": len(skipped_video_rows),
        "skippedOptionalLargeDerivedFileCount": len(skipped_optional_rows),
        "sampleDownloadExecuted": goal_achieved,
        "datasetDownloadAllowedByThisBatch": False,
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
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "boundedFixtureFetchManifest": manifest,
        "boundedFixtureFetchProvenanceAudit": provenance,
        "downloadScopeGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "google_drive_bounded_fixture_fetch_summary.json", summary)
    _write_json(output_root / "google_drive_bounded_fixture_fetch_manifest.json", manifest)
    _write_json(output_root / "bounded_fixture_fetch_provenance_audit.json", provenance)
    _write_json(output_root / "download_scope_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded SoccerTrack Google Drive fixture fetch for one selected match.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--tool-python", type=Path, default=DEFAULT_TOOL_PYTHON)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="google_drive_bounded_fixture_fetch")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_google_drive_bounded_fixture_fetch(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        tool_python=Path(args.tool_python),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
