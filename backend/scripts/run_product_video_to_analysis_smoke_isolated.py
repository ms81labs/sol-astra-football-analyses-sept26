from __future__ import annotations

from pathlib import Path
import shutil
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchConfig, MatchSummary  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    candidate_root,
    guardrails_false,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)
from backend.scripts.run_product_video_to_analysis_smoke import run_product_video_to_analysis_smoke  # noqa: E402

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_finish_line_execution_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "product_video_to_analysis_smoke_isolated_v1"

BLOCKER_APPROVAL_MISSING = "product_video_to_analysis_smoke_finish_line_approval_missing"
BLOCKER_SMOKE_FAILED = "product_video_to_analysis_smoke_isolated_failure"
NEXT_APPROVAL = "video_to_analysis_finish_line_execution_approval"
NEXT_REPAIR = "product_video_to_analysis_smoke_isolated_repair"
NEXT_CLOSEOUT = "video_to_analysis_finish_line_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "isolated_product_video_to_analysis_smoke",
                "successCriteria": [
                    "seed a ready video bundle in isolated benchmark storage",
                    "run the existing product video-to-analysis smoke against that isolated root",
                    "keep normal match storage untouched",
                ],
                "failureAdaptation": "If approval is missing, route back to finish-line execution approval.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "isolated_product_video_to_analysis_storage_repair",
                "successCriteria": [
                    "repair isolated storage setup only",
                    "do not run against normal storage",
                ],
                "failureAdaptation": "If smoke still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "isolated_product_video_to_analysis_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to approval, isolated smoke repair, or finish-line closeout.",
            },
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineExecutionApproved") is True
        and summary.get("approvedExecutionMode") == "isolated_product_video_to_analysis_smoke"
        and summary.get("normalMatchStorageMutationApproved") is False
        and summary.get("isolatedBenchmarkStorageMutationApproved") is True
        and guardrails_false(summary)
        and isinstance(scope, dict)
        and scope.get("isolatedBenchmarkStorageMutationAllowed") is True
        and scope.get("normalMatchStorageMutationAllowed") is False
        and scope.get("allowedRunner") == "backend/scripts/run_product_video_to_analysis_smoke.py"
    )


def _seed_ready_video_bundle(storage_root: Path) -> str:
    storage = Storage(storage_root)
    upload_path = storage.save_upload("finish-line-smoke.mp4", b"isolated video fixture")
    match = storage.create_match(
        name="Finish Line Isolated Video Fixture",
        input_mode="video",
        original_filename="finish-line-smoke.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.update_match_status(match.id, status="ready")
    storage.save_frames(match.id, [FrameData(frameId=0, timestamp=0.0, ball={"x": 52.0, "y": 50.0, "confidence": 0.95})])
    storage.save_analytics(
        match.id,
        MatchSummary(
            possession=55,
            myTeamDistance=100,
            enemyDistance=90,
            myTeamAvgPos={"x": 50.0, "y": 50.0},
            enemyAvgPos={"x": 55.0, "y": 50.0},
            myTeamTopSpeed=30.0,
            enemyTopSpeed=28.0,
            myTeamSprints=2,
            enemySprints=1,
            formation="4-3-3",
        ),
        [BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0)],
        [],
        [],
    )
    storage.save_events(match.id, [DetectedEvent(type="recovery", frameId=0, timestamp=0.0, description="isolated recovery")])
    storage.save_analysis_artifact(
        match.id,
        "ball_pipeline_trace",
        {
            "traceVersion": 1,
            "source": "isolated_product_video_to_analysis_smoke",
            "runtimeDefaultMutationExecuted": False,
        },
    )
    return match.id


def run_product_video_to_analysis_smoke_isolated(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    approval_root = root / DEFAULT_APPROVAL_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    approval_summary = load_json(approval_root / "finish_line_execution_approval_summary.json")
    approval_scope = load_json(approval_root / "approved_finish_line_execution_scope.json")
    approval_ready = _approval_ready(approval_summary, approval_scope)

    isolated_root = output_root / "isolated_storage_root"
    seeded_match_id: str | None = None
    smoke_payload: dict[str, Any] | None = None
    if approval_ready:
        if isolated_root.exists():
            shutil.rmtree(isolated_root)
        isolated_root.mkdir(parents=True, exist_ok=True)
        seeded_match_id = _seed_ready_video_bundle(isolated_root)
        smoke_payload = run_product_video_to_analysis_smoke(storage_root=isolated_root)

    smoke_passed = bool(
        isinstance(smoke_payload, dict)
        and smoke_payload.get("goalAchieved") is True
        and smoke_payload.get("apiUploadJobSmokePassed") is True
        and smoke_payload.get("existingVideoBundleSmokePassed") is True
    )
    if not approval_ready:
        primary_blocker = BLOCKER_APPROVAL_MISSING
        next_lever = NEXT_APPROVAL
        goal = False
        english = "Finish-line execution approval is missing or unsafe; rerun approval before product smoke."
    elif not smoke_passed:
        primary_blocker = BLOCKER_SMOKE_FAILED
        next_lever = NEXT_REPAIR
        goal = False
        english = "Isolated product video-to-analysis smoke failed; repair isolated storage or product smoke plumbing."
    else:
        primary_blocker = None
        next_lever = NEXT_CLOSEOUT
        goal = True
        english = "Isolated product video-to-analysis smoke passed. Close out the finish-line path next."

    nested_summary_path = (
        isolated_root
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "product_video_to_analysis_smoke_v1"
        / "product_video_to_analysis_smoke_summary.json"
    )
    isolated_storage_audit = {
        "schemaVersion": "product_video_to_analysis_isolated_storage_audit_v1",
        "generatedAt": utc_now_iso(),
        "approvalReady": approval_ready,
        "isolatedStorageRoot": str(isolated_root),
        "seededReadyVideoMatchId": seeded_match_id,
        "normalStorageRootUsedForSmoke": False,
        "isolatedBenchmarkStorageMutationExecuted": bool(approval_ready),
        "nestedSmokeSummaryPath": str(nested_summary_path),
        "nestedSmokeSummaryExists": nested_summary_path.exists(),
    }
    smoke_result = smoke_payload if isinstance(smoke_payload, dict) else {}
    summary = {
        "batchName": "product_video_to_analysis_smoke",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "productVideoToAnalysisSmokePassed": smoke_passed,
        "apiUploadJobSmokePassed": bool(smoke_result.get("apiUploadJobSmokePassed")),
        "existingVideoBundleSmokePassed": bool(smoke_result.get("existingVideoBundleSmokePassed")),
        "seededReadyVideoMatchId": seeded_match_id,
        "isolatedSmokeSummaryPath": str(nested_summary_path),
        "normalMatchStorageMutationApproved": False,
        "normalMatchStorageMutationExecuted": False,
        "isolatedBenchmarkStorageMutationApproved": approval_ready,
        "isolatedBenchmarkStorageMutationExecuted": bool(approval_ready),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "finish_line_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "isolated_product_smoke_failed", "selected": primary_blocker == BLOCKER_SMOKE_FAILED, "primaryBlocker": BLOCKER_SMOKE_FAILED, "nextRecommendedNextLever": NEXT_REPAIR},
            {"condition": "isolated_product_smoke_passed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_CLOSEOUT},
        ],
    }
    artifacts = {
        "isolated_storage_audit.json": isolated_storage_audit,
        "nested_product_smoke_summary.json": smoke_result,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="product_video_to_analysis_smoke_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Product Video To Analysis Smoke Isolated",
    )


def main() -> None:
    main_for("Run product video-to-analysis smoke through isolated benchmark storage.", run_product_video_to_analysis_smoke_isolated)


if __name__ == "__main__":
    main()
