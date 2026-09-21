from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    latest_versioned_dir,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_MANUAL_CLOSEOUT_DIR_NAME = "video_to_analysis_manual_operator_release_decision_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_v7_3_release_packaging_and_worktree_triage_v1"

BLOCKER_MANUAL_CLOSEOUT_MISSING = "video_to_analysis_v7_3_release_packaging_manual_closeout_missing"
NEXT_MANUAL_CLOSEOUT = "video_to_analysis_manual_operator_release_decision"
NEXT_COMMIT_PLAN = "video_to_analysis_v7_3_release_packaging_commit_plan"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "release_packaging_worktree_triage",
                "successCriteria": [
                    "v7.3 manual closeout truth is present",
                    "dirty worktree paths are classified",
                    "large generated/data artifacts are identified",
                    "no-GPU readiness and commit/archive plan are written",
                    "no cleanup, deletion, training, promotion, runtime mutation, downloads, or GPU work",
                ],
                "failureAdaptation": "If closeout truth is missing, route back to manual operator release decision.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "release_packaging_reference_repair",
                "successCriteria": ["repair only triage classification or source references"],
                "failureAdaptation": "Do not delete files or mutate runtime state while repairing triage metadata.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "release_packaging_blocker_summary",
                "successCriteria": ["write one blocker and one next family"],
                "failureAdaptation": "Stop with non-destructive blocker truth.",
            },
        ],
    }


def _manual_closeout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("selectedOperatorDecision") == "declare_current_milestone_done"
        and summary.get("v7_3CurrentMilestoneDeclaredDone") is True
        and summary.get("optionalCoverageLoopDeferred") is True
        and summary.get("releasedRuntimeVersion") == "v7.3"
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _git_status_lines(worktree_root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=worktree_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _status_kind(line: str) -> str:
    code = line[:2]
    if "D" in code:
        return "deleted"
    if code == "??":
        return "untracked"
    if "M" in code:
        return "modified"
    if "A" in code:
        return "added"
    return "other"


def _status_path(line: str) -> str:
    return line[3:].strip()


def _path_bucket(path: str) -> str:
    if path.startswith(("backend/scripts/", "backend/tests/", "backend/app/", "backend/daytona_worker/", "docs/", "memorybank/", "SESSION-HANDOFF.md")):
        return "source_tests_docs"
    if path.startswith("backend/storage/trained_detector_candidates/") or path.startswith("backend/storage/automation/"):
        return "generated_truth"
    if path.startswith("backend/storage/runtime/") or path.startswith("backend/storage/benchmark_suites/"):
        return "runtime_or_benchmark_state"
    if path.startswith(".vscode/") or "__pycache__" in path or ".pytest_cache" in path:
        return "local_junk_or_cache"
    return "needs_manual_classification"


def _classify_worktree(lines: list[str]) -> dict[str, Any]:
    status_counts = {"modified": 0, "untracked": 0, "deleted": 0, "added": 0, "other": 0}
    bucket_counts: dict[str, int] = {}
    rows: list[dict[str, str]] = []
    for line in lines:
        kind = _status_kind(line)
        path = _status_path(line)
        bucket = _path_bucket(path)
        status_counts[kind] = status_counts.get(kind, 0) + 1
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        rows.append({"status": kind, "path": path, "bucket": bucket, "raw": line})
    return {
        "schemaVersion": "video_to_analysis_worktree_classification_v1",
        "generatedAt": utc_now_iso(),
        "totalDirtyPathCount": len(rows),
        "statusCounts": status_counts,
        "bucketCounts": bucket_counts,
        "rows": rows,
    }


def _large_artifact_rows(worktree_root: Path) -> list[dict[str, Any]]:
    storage_root = worktree_root / "backend" / "storage"
    if not storage_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in storage_root.rglob("*"):
        if path.is_file():
            size = path.stat().st_size
            if size >= 50 * 1024 * 1024:
                rows.append({"path": str(path.relative_to(worktree_root)), "sizeBytes": size})
    rows.sort(key=lambda row: int(row["sizeBytes"]), reverse=True)
    return rows[:50]


def _disk_info(worktree_root: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(worktree_root)
    used_percent = round((usage.used / usage.total) * 100, 2) if usage.total else 0
    return {"totalBytes": usage.total, "usedBytes": usage.used, "freeBytes": usage.free, "usedPercent": used_percent}


def _packaging_plan(worktree: dict[str, Any], large_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_release_packaging_plan_v1",
        "generatedAt": utc_now_iso(),
        "recommendedCommitGroups": [
            {
                "id": "source_tests_docs",
                "purpose": "Commit source scripts, tests, docs, and memorybank entries required to reproduce the v7.3 milestone.",
                "candidatePathCount": int(worktree["bucketCounts"].get("source_tests_docs", 0)),
            },
            {
                "id": "essential_generated_truth",
                "purpose": "Commit or archive small generated truth needed for clean-session rehydration.",
                "candidatePathCount": int(worktree["bucketCounts"].get("generated_truth", 0)),
            },
            {
                "id": "runtime_and_benchmark_state",
                "purpose": "Review runtime/benchmark state changes separately because they encode active product behavior.",
                "candidatePathCount": int(worktree["bucketCounts"].get("runtime_or_benchmark_state", 0)),
            },
        ],
        "recommendedArchiveOrIgnoreGroups": [
            {
                "id": "large_external_artifacts",
                "purpose": "Keep large videos/tracker dumps out of source commits; move to artifact storage or document retention.",
                "candidatePathCount": len(large_artifacts),
            },
            {
                "id": "local_junk_or_cache",
                "purpose": "Ignore editor settings and cache directories unless intentionally shared.",
                "candidatePathCount": int(worktree["bucketCounts"].get("local_junk_or_cache", 0)),
            },
        ],
        "destructiveCleanupApproved": False,
        "commitReady": False,
        "commitReadinessReason": "Triage is complete, but commit grouping must be reviewed before staging a large dirty worktree.",
    }


def _no_gpu_audit(disk_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_no_gpu_readiness_audit_v1",
        "generatedAt": utc_now_iso(),
        "noGpuRequiredForPackaging": True,
        "gpuRequired": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "runPodPodsExpected": [],
        "diskInfo": disk_info,
    }


def run_video_to_analysis_v7_3_release_packaging_and_worktree_triage(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    git_status_lines: list[str] | None = None,
    large_artifact_rows: list[dict[str, Any]] | None = None,
    disk_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    worktree_root = Path(__file__).resolve().parents[2]
    candidate = candidate_root(Path(storage_root), candidate_name)
    closeout_dir = latest_versioned_dir(
        candidate,
        "video_to_analysis_manual_operator_release_decision",
        DEFAULT_MANUAL_CLOSEOUT_DIR_NAME,
    )
    output_root = reset_output(candidate, output_dir_name)
    closeout_summary = load_json(closeout_dir / "manual_operator_release_decision_summary.json")
    closeout_ready = _manual_closeout_ready(closeout_summary)

    lines = git_status_lines if git_status_lines is not None else _git_status_lines(worktree_root)
    large_rows = large_artifact_rows if large_artifact_rows is not None else _large_artifact_rows(worktree_root)
    disk = disk_info if disk_info is not None else _disk_info(worktree_root)
    worktree = _classify_worktree(lines)
    packaging = _packaging_plan(worktree, large_rows)
    no_gpu = _no_gpu_audit(disk)

    if closeout_ready:
        goal = True
        primary_blocker = None
        next_lever = NEXT_COMMIT_PLAN
        english = "v7.3 milestone truth is closed; release packaging/worktree triage is ready for commit/archive planning without GPUs."
    else:
        goal = False
        primary_blocker = BLOCKER_MANUAL_CLOSEOUT_MISSING
        next_lever = NEXT_MANUAL_CLOSEOUT
        english = "v7.3 manual closeout truth is missing or unsafe; record the manual release decision before packaging."

    source_or_test_count = int(worktree["bucketCounts"].get("source_tests_docs", 0))
    generated_truth_count = int(worktree["bucketCounts"].get("generated_truth", 0))
    deleted_count = int(worktree["statusCounts"].get("deleted", 0))

    summary = {
        "batchName": "video_to_analysis_v7_3_release_packaging_and_worktree_triage",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "v7_3CurrentMilestoneDeclaredDone": bool((closeout_summary or {}).get("v7_3CurrentMilestoneDeclaredDone")),
        "worktreeTriageReady": goal,
        "totalDirtyPathCount": int(worktree["totalDirtyPathCount"]),
        "sourceOrTestCandidateCount": source_or_test_count,
        "generatedTruthCandidateCount": generated_truth_count,
        "deletedTrackedPathCount": deleted_count,
        "largeArtifactCount": len(large_rows),
        "gpuRequired": False,
        "destructiveCleanupExecuted": False,
        **standard_false_flags(),
        "cleanupDeletionExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_release_packaging_triage_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "manual_closeout_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_MANUAL_CLOSEOUT_MISSING,
                "primaryBlocker": BLOCKER_MANUAL_CLOSEOUT_MISSING,
                "nextRecommendedNextLever": NEXT_MANUAL_CLOSEOUT,
            },
            {
                "condition": "triage_ready_for_commit_plan",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_COMMIT_PLAN,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="release_packaging_worktree_triage_summary.json",
        summary=summary,
        artifacts={
            "worktree_classification.json": worktree,
            "large_artifact_inventory.json": {
                "schemaVersion": "video_to_analysis_large_artifact_inventory_v1",
                "generatedAt": utc_now_iso(),
                "largeArtifactCount": len(large_rows),
                "rows": large_rows,
            },
            "release_packaging_plan.json": packaging,
            "no_gpu_readiness_audit.json": no_gpu,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis V7.3 Release Packaging And Worktree Triage",
    )


def main() -> None:
    main_for(
        "Triage v7.3 release packaging and dirty worktree without GPU work.",
        run_video_to_analysis_v7_3_release_packaging_and_worktree_triage,
    )


if __name__ == "__main__":
    main()
