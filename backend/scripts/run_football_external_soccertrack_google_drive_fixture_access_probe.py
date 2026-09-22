from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_google_drive_fixture_access_probe_v1"
DEFAULT_DRIVE_FOLDER_ID = "1N2Qx2qkFgRtpbHitl2Vh6sLVYGgqkWwn"
DEFAULT_DRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{DEFAULT_DRIVE_FOLDER_ID}"
DEFAULT_TOOL_PYTHON = REPO_ROOT / "backend" / "storage" / "tools" / "gdrive-probe-venv" / "bin" / "python"

BLOCKER_LISTING_FAILED = "football_external_soccertrack_google_drive_listing_probe_failed"
BLOCKER_COMPLETE_FIXTURE_MISSING = "football_external_soccertrack_google_drive_complete_fixture_missing"

NEXT_COOKIE_SETUP = "football_external_soccertrack_google_drive_access_cookie_setup"
NEXT_ARCHIVE_PROBE = "football_external_soccertrack_drive_archive_member_probe"
NEXT_BOUNDED_FETCH_APPROVAL = "football_external_soccertrack_google_drive_bounded_fixture_fetch_approval"

MEDIA_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}

ListingFetcher = Callable[[str, Path, Path], list[dict[str, Any]]]


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "google_drive_fixture_listing_probe",
            "successCriteria": [
                "install or use local Drive folder listing helper",
                "list Google Drive folder metadata only",
                "identify one-match GSR/BAS/MOT fixture candidates without file-content download",
            ],
            "failureAdaptation": "If listing is blocked, try listing-tool repair or cookie-backed access setup.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "google_drive_listing_tool_repair",
            "successCriteria": [
                "repair local listing helper path or Drive folder parsing",
                "preserve metadata-only scope",
                "write candidate manifest if complete fixtures are visible",
            ],
            "failureAdaptation": "If listing works but no complete fixture exists, route to archive/member probe.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "google_drive_access_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not download full dataset, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Stop before bounded fixture fetch until Drive listing or source structure is clear.",
        },
    ]


def _tool_install_audit(tool_python: Path) -> dict[str, Any]:
    audit: dict[str, Any] = {
        "schemaVersion": "soccertrack_google_drive_tool_install_audit_v1",
        "generatedAt": _utc_now_iso(),
        "toolPythonPath": str(tool_python),
        "toolPythonExists": tool_python.exists(),
        "gdownImportAvailable": False,
        "gdownVersion": None,
        "systemPipInstallAttempted": False,
        "localToolVenvExpected": True,
    }
    if not tool_python.exists():
        return audit
    code = "import gdown, json; print(json.dumps({'version': getattr(gdown, '__version__', 'unknown')}))"
    try:
        completed = subprocess.run(
            [str(tool_python), "-c", code],
            check=True,
            text=True,
            capture_output=True,
            timeout=20,
        )
        payload = json.loads(completed.stdout.strip() or "{}")
        audit["gdownImportAvailable"] = True
        audit["gdownVersion"] = payload.get("version")
    except Exception as exc:  # pragma: no cover - live environment failure path.
        audit["toolImportError"] = str(exc)
    return audit


def _gdown_skip_download_listing(drive_url: str, output_root: Path, tool_python: Path) -> list[dict[str, Any]]:
    if not tool_python.exists():
        raise RuntimeError(f"Google Drive probe tool is missing: {tool_python}")
    helper = """
import json
import sys
import gdown

url = sys.argv[1]
output = sys.argv[2]
files = gdown.download_folder(
    url=url,
    output=output,
    quiet=True,
    use_cookies=False,
    skip_download=True,
)
print(json.dumps([
    {
        "id": getattr(row, "id", None),
        "path": getattr(row, "path", None),
        "localPath": getattr(row, "local_path", None),
    }
    for row in files
]))
"""
    completed = subprocess.run(
        [str(tool_python), "-c", helper, drive_url, str(output_root / "_metadata_only_listing_paths")],
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )
    rows = json.loads(completed.stdout.strip() or "[]")
    if not isinstance(rows, list):
        raise ValueError("Expected Google Drive listing helper to return a JSON array")
    return [dict(row) for row in rows if isinstance(row, dict)]


def _normalize_listing_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        path = str(row.get("path") or "")
        file_id = str(row.get("id") or "")
        if not path or not file_id:
            continue
        normalized.append(
            {
                "id": file_id,
                "path": path,
                "localPath": str(row.get("localPath") or row.get("local_path") or ""),
                "extension": Path(path).suffix.lower(),
                "isMedia": Path(path).suffix.lower() in MEDIA_EXTENSIONS,
            }
        )
    return sorted(normalized, key=lambda item: item["path"])


def _match_id(path: str) -> str | None:
    match = re.match(r"^(?:bas|gsr)/(\d+)/", path.lower())
    if match:
        return match.group(1)
    match = re.match(r"^(?:mot/)?raw/(\d+)/", path.lower())
    if match:
        return match.group(1)
    match = re.match(r"^videos/(\d+)/", path.lower())
    return match.group(1) if match else None


def _row_task(path: str) -> str | None:
    lowered = path.lower()
    if re.match(r"^bas/\d+/.+_12_class_events\.json$", lowered):
        return "bas"
    if re.match(r"^gsr/\d+/.+_(?:1st|2nd)\.json$", lowered):
        return "gsr"
    if re.match(r"^(?:mot/)?raw/\d+/.+\.(?:csv|json|xml|npy|npz)$", lowered):
        return "mot"
    if re.match(r"^videos/\d+/.+\.mp4$", lowered):
        return "videos"
    return None


def _coverage_by_match(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    coverage: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        path = str(row.get("path") or "")
        match_id = _match_id(path)
        task = _row_task(path)
        if match_id and task:
            coverage[match_id][task].append(row)
    return {match_id: dict(task_map) for match_id, task_map in coverage.items()}


def _is_complete_fixture(task_map: dict[str, list[dict[str, Any]]]) -> bool:
    gsr_paths = {Path(row["path"]).name.lower() for row in task_map.get("gsr", [])}
    return bool(
        task_map.get("bas")
        and any(name.endswith("_1st.json") for name in gsr_paths)
        and any(name.endswith("_2nd.json") for name in gsr_paths)
        and len(task_map.get("mot", [])) >= 4
    )


def _candidate_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = _coverage_by_match(rows)
    candidate_matches: list[dict[str, Any]] = []
    for match_id in sorted(coverage):
        task_map = coverage[match_id]
        complete = _is_complete_fixture(task_map)
        candidate_matches.append(
            {
                "matchId": match_id,
                "completeFixtureCandidate": complete,
                "taskCoverage": sorted(task_map),
                "basFileCount": len(task_map.get("bas", [])),
                "gsrFileCount": len(task_map.get("gsr", [])),
                "motFileCount": len(task_map.get("mot", [])),
                "videoFileCount": len(task_map.get("videos", [])),
                "selectedFileIdsByTask": {
                    task: [{"id": row["id"], "path": row["path"]} for row in task_map.get(task, [])]
                    for task in ["bas", "gsr", "mot", "videos"]
                    if task_map.get(task)
                },
            }
        )
    complete_ids = [row["matchId"] for row in candidate_matches if row["completeFixtureCandidate"]]
    selected_match_id = complete_ids[0] if complete_ids else None
    return {
        "schemaVersion": "soccertrack_google_drive_fixture_candidate_manifest_v1",
        "generatedAt": _utc_now_iso(),
        "selectedSampleResourceId": "soccertrack_v2",
        "candidateMatches": candidate_matches,
        "completeFixtureCandidateMatchIds": complete_ids,
        "completeFixtureCandidateMatchCount": len(complete_ids),
        "selectedMatchId": selected_match_id,
        "selectedMatchTaskCoverage": {match_id: sorted(coverage[match_id]) for match_id in coverage},
        "fileContentDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _classify(
    listing_accessible: bool,
    complete_fixture_count: int,
    listing_error: str | None,
) -> tuple[str | None, str, bool, bool, str]:
    if not listing_accessible:
        return (
            BLOCKER_LISTING_FAILED,
            NEXT_COOKIE_SETUP,
            False,
            False,
            f"Google Drive folder listing failed without downloading data: {listing_error or 'unknown error'}",
        )
    if complete_fixture_count < 1:
        return (
            BLOCKER_COMPLETE_FIXTURE_MISSING,
            NEXT_ARCHIVE_PROBE,
            False,
            True,
            "Google Drive listing is accessible, but no complete BAS/GSR/MOT one-match fixture candidate was found.",
        )
    return (
        None,
        NEXT_BOUNDED_FETCH_APPROVAL,
        True,
        True,
        "Google Drive folder listing is accessible and exposes complete one-match BAS/GSR/MOT fixture candidates. Advance to bounded fixture fetch approval; no file contents were downloaded.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "drive_listing_failed", "selected": primary_blocker == BLOCKER_LISTING_FAILED, "primaryBlocker": BLOCKER_LISTING_FAILED, "nextRecommendedNextLever": NEXT_COOKIE_SETUP},
            {"condition": "complete_fixture_missing", "selected": primary_blocker == BLOCKER_COMPLETE_FIXTURE_MISSING, "primaryBlocker": BLOCKER_COMPLETE_FIXTURE_MISSING, "nextRecommendedNextLever": NEXT_ARCHIVE_PROBE},
            {"condition": "complete_fixture_visible", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BOUNDED_FETCH_APPROVAL},
        ],
    }


def _download_guardrail(rows: list[dict[str, Any]]) -> dict[str, Any]:
    media_rows = [row for row in rows if row.get("isMedia")]
    return {
        "schemaVersion": "soccertrack_google_drive_download_scope_guardrail_audit_v1",
        "generatedAt": _utc_now_iso(),
        "metadataListingOnly": True,
        "fileContentDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "largeMediaCandidateCount": len(media_rows),
        "largeMediaCandidates": [{"id": row["id"], "path": row["path"]} for row in media_rows[:50]],
        "trainingExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _folder_listing_audit(rows: list[dict[str, Any]], drive_url: str, drive_folder_id: str, listing_error: str | None) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_google_drive_folder_listing_audit_v1",
        "generatedAt": _utc_now_iso(),
        "driveFolderUrl": drive_url,
        "driveFolderId": drive_folder_id,
        "driveListingAccessible": listing_error is None,
        "driveListingError": listing_error,
        "driveListingFileCount": len(rows),
        "pathPrefixCounts": {
            prefix: sum(1 for row in rows if row["path"].split("/", 1)[0] == prefix)
            for prefix in sorted({row["path"].split("/", 1)[0] for row in rows})
        },
        "rows": [{"id": row["id"], "path": row["path"], "isMedia": row["isMedia"]} for row in rows],
        "fileContentDownloadExecuted": False,
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Google Drive Fixture Access Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Drive listing accessible: `{summary.get('driveListingAccessible')}`",
            f"- Listed file count: `{summary.get('driveListingFileCount')}`",
            f"- Complete fixture candidates: `{summary.get('completeFixtureCandidateMatchCount')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_google_drive_fixture_access_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    drive_folder_url: str = DEFAULT_DRIVE_FOLDER_URL,
    drive_folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
    tool_python: Path = DEFAULT_TOOL_PYTHON,
    attempt_number: int = 1,
    attempt_approach_family: str = "google_drive_fixture_listing_probe",
    listing_fetcher: ListingFetcher | None = None,
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(candidate_root, output_dir_name)

    fetcher = listing_fetcher or _gdown_skip_download_listing
    listing_error: str | None = None
    raw_rows: list[dict[str, Any]] = []
    try:
        raw_rows = fetcher(drive_folder_url, output_root, Path(tool_python))
    except Exception as exc:  # pragma: no cover - live access failure path.
        listing_error = str(exc)
    rows = _normalize_listing_rows(raw_rows)
    manifest = _candidate_manifest(rows)
    complete_fixture_count = int(manifest["completeFixtureCandidateMatchCount"])
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(
        listing_error is None,
        complete_fixture_count,
        listing_error,
    )
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    tool_audit = _tool_install_audit(Path(tool_python))
    folder_audit = _folder_listing_audit(rows, drive_folder_url, drive_folder_id, listing_error)
    guardrail = _download_guardrail(rows)
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_google_drive_fixture_access_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "selectedSampleResourceId": "soccertrack_v2",
        "driveFolderUrl": drive_folder_url,
        "driveFolderId": drive_folder_id,
        "driveListingProbeExecuted": True,
        "driveListingAccessible": listing_error is None,
        "driveListingFileCount": len(rows),
        "completeFixtureCandidateMatchCount": complete_fixture_count,
        "fixtureCandidateCount": len(manifest["candidateMatches"]),
        "selectedMatchId": manifest["selectedMatchId"],
        "largeMediaCandidateCount": guardrail["largeMediaCandidateCount"],
        "metadataListingOnly": True,
        "fileContentDownloadExecuted": False,
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
    batch_outcome = {
        "summary": summary,
        "driveToolInstallAudit": tool_audit,
        "driveFolderListingAudit": folder_audit,
        "driveFixtureCandidateManifest": manifest,
        "driveDownloadScopeGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "google_drive_fixture_access_probe_summary.json", summary)
    _write_json(output_root / "drive_tool_install_audit.json", tool_audit)
    _write_json(output_root / "drive_folder_listing_audit.json", folder_audit)
    _write_json(output_root / "drive_fixture_candidate_manifest.json", manifest)
    _write_json(output_root / "drive_download_scope_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Metadata-only SoccerTrack Google Drive fixture access probe.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--drive-folder-url", default=DEFAULT_DRIVE_FOLDER_URL)
    parser.add_argument("--drive-folder-id", default=DEFAULT_DRIVE_FOLDER_ID)
    parser.add_argument("--tool-python", type=Path, default=DEFAULT_TOOL_PYTHON)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="google_drive_fixture_listing_probe")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_google_drive_fixture_access_probe(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        drive_folder_url=str(args.drive_folder_url),
        drive_folder_id=str(args.drive_folder_id),
        tool_python=Path(args.tool_python),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
