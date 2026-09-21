from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccertrack_sample_fixture_materialization_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_controlled_sample_fetch_v1"

BLOCKER_APPROVAL_MISSING = "football_external_soccertrack_controlled_sample_fetch_approval_missing"
BLOCKER_PUBLIC_FIXTURE_MISSING = "football_external_soccertrack_public_fixture_files_missing"
BLOCKER_FETCH_FAILED = "football_external_soccertrack_controlled_sample_fetch_failed"

NEXT_APPROVAL = "football_external_soccertrack_sample_fixture_materialization_approval"
NEXT_SOURCE_ACCESS_REVIEW = "football_external_soccertrack_fixture_source_access_review"
NEXT_MATERIALIZATION = "football_external_soccertrack_sample_fixture_materialization"

REPO_RAW_BASE = "https://raw.githubusercontent.com/AtomScott/SoccerTrack-v2/main"
REPO_TREE_API = "https://api.github.com/repos/AtomScott/SoccerTrack-v2/git/trees/main?recursive=1"
MAX_FIXTURE_FILE_BYTES = 5_000_000
MEDIA_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".jpg", ".jpeg", ".png", ".webp"}


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _http_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "fotball-analyst-soccertrack-sample-fetch/1.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - controlled official GitHub API URL.
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


def _http_fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "fotball-analyst-soccertrack-sample-fetch/1.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - controlled raw URLs from filtered official tree.
        return response.read()


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_controlled_fixture_source_tree_fetch",
            "successCriteria": [
                "probe official SoccerTrack tree for one-match GSR/BAS/MOT fixture files",
                "fetch only bounded non-media fixture files if a complete match exists",
                "skip large media and full dataset scopes",
            ],
            "failureAdaptation": "If public fixtures are absent, write source-access locator truth instead of fabricating a sample.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_controlled_fixture_source_locator_repair",
            "successCriteria": [
                "repair fixture path detection from official repo metadata",
                "preserve max one-match scope and media skip guardrail",
            ],
            "failureAdaptation": "If fixture files remain unavailable, route to source access review.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_controlled_sample_fetch_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not download full datasets, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Stop before fixture materialization until actual fixture files are available.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "approvalRoot": approval_root,
        "approvalSummary": _load_json(approval_root / "sample_fixture_materialization_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "soccertrack_sample_fixture_materialization_approval_contract.json"),
        "approvedScope": _load_json(approval_root / "approved_sample_scope.json"),
    }


def _approval_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("sampleFixtureMaterializationApproved") is True
        and summary.get("sampleDownloadApproved") is True
        and summary.get("sampleDownloadExecuted") is False
        and summary.get("datasetDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(contract, dict)
        and contract.get("approvedUse") == "adapter_fixture_materialization_only"
        and contract.get("sampleDownloadApproved") is True
        and contract.get("datasetDownloadApproved") is False
        and contract.get("fullDatasetDownloadApproved") is False
        and contract.get("trainingUseApproved") is False
        and isinstance(scope, dict)
        and scope.get("selectedSampleResourceId") == "soccertrack_v2"
        and int(scope.get("maxSampleMatches") or 0) == 1
    )


def _tree_rows(tree_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = tree_payload.get("tree")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _path_task(path: str) -> str | None:
    lowered = path.lower()
    if re.match(r"^gsr/\d+/.+\.json$", lowered):
        return "gsr"
    if re.match(r"^bas/\d+/.+\.json$", lowered):
        return "bas"
    if re.match(r"^mot/\d+/.+/gt\.txt$", lowered) or re.match(r"^mot/\d+/gt\.txt$", lowered):
        return "mot"
    return None


def _path_match_id(path: str) -> str | None:
    match = re.match(r"^(?:gsr|bas|mot)/(\d+)/", path.lower())
    return match.group(1) if match else None


def _is_media_or_large(row: dict[str, Any]) -> bool:
    path = str(row.get("path") or "")
    size = int(row.get("size") or 0)
    return Path(path).suffix.lower() in MEDIA_EXTENSIONS or size > MAX_FIXTURE_FILE_BYTES


def _discover_fixture_candidates(rows: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    skipped_media = [row for row in rows if row.get("type") == "blob" and _is_media_or_large(row)]
    by_match: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    fixture_like_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.get("type") != "blob":
            continue
        path = str(row.get("path") or "")
        task = _path_task(path)
        match_id = _path_match_id(path)
        if not task or not match_id or _is_media_or_large(row):
            continue
        by_match[match_id][task].append(row)
        fixture_like_rows.append(row)
    for match_id in sorted(by_match):
        task_map = by_match[match_id]
        if {"gsr", "bas", "mot"}.issubset(task_map):
            return {task: sorted(task_map[task], key=lambda row: str(row.get("path")))[:1] for task in ["gsr", "bas", "mot"]}, fixture_like_rows, skipped_media
    return None, fixture_like_rows, skipped_media


def _safe_relative(path: str) -> str:
    return "sample_fixture_files/" + path.replace("/", "__")


def _fetch_selected_files(
    output_root: Path,
    selected: dict[str, list[dict[str, Any]]] | None,
    fetcher: Callable[[str], bytes],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not selected:
        return [], []
    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for task in ["gsr", "bas", "mot"]:
        for row in selected.get(task, []):
            source_path = str(row.get("path") or "")
            url = f"{REPO_RAW_BASE}/{source_path}"
            try:
                content = fetcher(url)
                if len(content) > MAX_FIXTURE_FILE_BYTES:
                    failures.append({"sourcePath": source_path, "url": url, "error": "file exceeded max fixture bytes after fetch"})
                    continue
                relative_path = _safe_relative(source_path)
                (output_root / relative_path).parent.mkdir(parents=True, exist_ok=True)
                (output_root / relative_path).write_bytes(content)
                downloaded.append(
                    {
                        "taskId": task,
                        "sourcePath": source_path,
                        "url": url,
                        "relativePath": relative_path,
                        "sizeBytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
            except Exception as exc:  # pragma: no cover - live network failure path.
                failures.append({"sourcePath": source_path, "url": url, "error": str(exc)})
    return downloaded, failures


def _classify(approval_ready: bool, selected: dict[str, list[dict[str, Any]]] | None, downloaded: list[dict[str, Any]], failures: list[dict[str, Any]]) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "SoccerTrack controlled sample fetch approval is missing or unsafe; rerun fixture materialization approval.",
        )
    if selected is None:
        return (
            BLOCKER_PUBLIC_FIXTURE_MISSING,
            NEXT_SOURCE_ACCESS_REVIEW,
            False,
            "Official SoccerTrack repo tree does not expose a complete one-match GSR/BAS/MOT fixture set; route to fixture source access review.",
        )
    if failures or len(downloaded) < 3:
        return (
            BLOCKER_FETCH_FAILED,
            NEXT_APPROVAL,
            False,
            "Controlled SoccerTrack fixture fetch failed; repair source locator or approval before materialization.",
        )
    return (
        None,
        NEXT_MATERIALIZATION,
        True,
        "Controlled SoccerTrack sample fixture files fetched. Advance to fixture materialization; full dataset download, training, promotion, and runtime mutation remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "public_fixture_files_missing", "selected": primary_blocker == BLOCKER_PUBLIC_FIXTURE_MISSING, "primaryBlocker": BLOCKER_PUBLIC_FIXTURE_MISSING, "nextRecommendedNextLever": NEXT_SOURCE_ACCESS_REVIEW},
            {"condition": "fixture_fetch_failed", "selected": primary_blocker == BLOCKER_FETCH_FAILED, "primaryBlocker": BLOCKER_FETCH_FAILED, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "controlled_fixture_fetch_succeeded", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_MATERIALIZATION},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Controlled Sample Fetch",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Downloaded fixture files: `{summary.get('downloadedFixtureFileCount')}`",
            f"- Downloaded task IDs: `{summary.get('downloadedTaskIds')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Full dataset download executed: `{summary.get('fullDatasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_controlled_sample_fetch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_controlled_fixture_source_tree_fetch",
    tree_fetcher: Callable[[], dict[str, Any]] = lambda: _http_json(REPO_TREE_API),
    fetcher: Callable[[str], bytes] = _http_fetch,
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    approval_ready = _approval_ready(inputs.get("approvalSummary"), inputs.get("approvalContract"), inputs.get("approvedScope"))
    tree_payload: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    selected: dict[str, list[dict[str, Any]]] | None = None
    fixture_like_rows: list[dict[str, Any]] = []
    skipped_media: list[dict[str, Any]] = []
    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if approval_ready:
        try:
            tree_payload = tree_fetcher()
            rows = _tree_rows(tree_payload)
            selected, fixture_like_rows, skipped_media = _discover_fixture_candidates(rows)
            downloaded, failures = _fetch_selected_files(output_root, selected, fetcher)
        except Exception as exc:  # pragma: no cover - live API/network failure.
            failures = [{"sourcePath": REPO_TREE_API, "url": REPO_TREE_API, "error": str(exc)}]
    primary_blocker, next_lever, goal_achieved, english = _classify(approval_ready, selected, downloaded, failures)
    selected_match_id = _path_match_id(downloaded[0]["sourcePath"]) if downloaded else None
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    downloaded_task_ids = sorted({row["taskId"] for row in downloaded})
    source_tree_audit = {
        "schemaVersion": "soccertrack_source_tree_fixture_audit_v1",
        "generatedAt": generated_at,
        "sourceRepositoryUrl": "https://github.com/AtomScott/SoccerTrack-v2",
        "treeApiUrl": REPO_TREE_API,
        "treeRowCount": len(rows),
        "fixtureLikeRowCount": len(fixture_like_rows),
        "completeOneMatchFixtureFound": selected is not None,
        "selectedMatchId": selected_match_id,
        "fixtureLikeRows": [{"path": row.get("path"), "size": row.get("size")} for row in fixture_like_rows[:200]],
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }
    guardrail = {
        "schemaVersion": "soccertrack_sample_fetch_guardrail_audit_v1",
        "generatedAt": generated_at,
        "maxFixtureFileBytes": MAX_FIXTURE_FILE_BYTES,
        "largeMediaFileSkippedCount": len(skipped_media),
        "largeMediaFilesSkipped": [{"path": row.get("path"), "size": row.get("size")} for row in skipped_media[:50]],
        "sampleDownloadExecuted": goal_achieved,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }
    manifest = {
        "schemaVersion": "soccertrack_controlled_sample_fetch_manifest_v1",
        "generatedAt": generated_at,
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "fetchScope": "one_match_gsr_bas_mot_fixture_files_only",
        "downloadedFiles": downloaded,
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingExecuted": False,
    }
    provenance = {
        "schemaVersion": "soccertrack_sample_fetch_provenance_audit_v1",
        "generatedAt": generated_at,
        "downloadedFiles": downloaded,
        "failures": failures,
        "fetchFailureCount": len(failures),
        "sha256ByPath": {row["sourcePath"]: row["sha256"] for row in downloaded},
        "datasetDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingExecuted": False,
    }
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_controlled_sample_fetch",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_sample_fixture_materialization_approval",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "controlledSampleFetchExecuted": goal_achieved,
        "sourceTreeProbeExecuted": approval_ready and not failures,
        "completeOneMatchFixtureFound": selected is not None,
        "downloadedFixtureFileCount": len(downloaded),
        "downloadedTaskIds": downloaded_task_ids,
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
        "controlledSampleFetchManifest": manifest,
        "sampleFetchProvenanceAudit": provenance,
        "sourceTreeFixtureAudit": source_tree_audit,
        "sampleFetchGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "controlled_sample_fetch_summary.json", summary)
    _write_json(output_root / "controlled_sample_fetch_manifest.json", manifest)
    _write_json(output_root / "sample_fetch_provenance_audit.json", provenance)
    _write_json(output_root / "source_tree_fixture_audit.json", source_tree_audit)
    _write_json(output_root / "sample_fetch_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled SoccerTrack one-match fixture fetch from official source.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_controlled_fixture_source_tree_fetch")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_controlled_sample_fetch(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
