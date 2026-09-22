from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_SELECTION_DIR_NAME = "video_to_analysis_next_strategic_lane_selection_v1"
DEFAULT_RELEASE_ROUTE_DIR_NAME = "video_to_analysis_release_readout_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_user_facing_release_readout_v1"
DEFAULT_OUTPUT_DOC_PATH = Path("docs/video-to-analysis-user-facing-release-readout-2026-05-09.md")

BLOCKER_SELECTION_MISSING = "video_to_analysis_user_readout_strategic_selection_missing"
BLOCKER_RELEASE_ROUTE_MISSING = "video_to_analysis_user_readout_release_route_missing"
NEXT_SELECTION = "video_to_analysis_next_strategic_lane_selection"
NEXT_RELEASE_ROUTE = "video_to_analysis_release_readout_route_binding"
NEXT_STORAGE_CLEANUP = "video_to_analysis_storage_cleanup_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_user_facing_release_readout",
                "successCriteria": [
                    "strategic selector chose user-facing release/readout",
                    "release/readout API and HTML routes are live",
                    "write generated truth plus a shareable markdown readout",
                    "preserve all mutation guardrails",
                ],
                "failureAdaptation": "If selector or route truth is missing, route to the missing prerequisite.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "user_facing_release_readout_reference_repair",
                "successCriteria": ["repair only source references or markdown text"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "user_facing_release_readout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop; do not invent release claims.",
            },
        ],
    }


def _selection_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("selectedStrategicLane") == "user_facing_release_readout"
        and summary.get("nextRecommendedNextLever") == "video_to_analysis_user_facing_release_readout"
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _release_route_ready(summary: dict[str, Any] | None, view_model: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("releaseReadoutRouteReady") is True
        and summary.get("apiRoutePath") == "/api/video-to-analysis/release-readout"
        and summary.get("htmlRoutePath") == "/video-to-analysis/release-readout"
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(view_model, dict)
        and view_model.get("schemaVersion") == "video_to_analysis_release_readout_view_model_v1"
        and view_model.get("latestSnapshot") == "video_to_analysis_next_sample_selection_snapshot_v38"
    )


def _manifest(view_model: dict[str, Any], output_doc_path: Path) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_user_facing_release_manifest_v1",
        "generatedAt": utc_now_iso(),
        "releaseRoute": "/video-to-analysis/release-readout",
        "releaseApiRoute": "/api/video-to-analysis/release-readout",
        "latestSnapshot": view_model.get("latestSnapshot"),
        "runtimeOperationallyComplete": view_model.get("runtimeOperationallyComplete") is True,
        "externalBenchmarkProductBindingReady": view_model.get("externalBenchmarkProductBindingReady") is True,
        "shareableReadoutPath": str(output_doc_path),
    }


def _demo_checklist() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_operator_demo_checklist_v1",
        "generatedAt": utc_now_iso(),
        "demoSteps": [
            {
                "id": "open_release_readout",
                "label": "Open the video-to-analysis release readout",
                "route": "/video-to-analysis/release-readout",
            },
            {
                "id": "confirm_v38_closeout",
                "label": "Confirm v38 closeout and next-lane selection are visible",
                "expected": "latestSnapshot = video_to_analysis_next_sample_selection_snapshot_v38",
            },
            {
                "id": "confirm_guardrails",
                "label": "Confirm no training, promotion, runtime mutation, downloads, or normal storage mutation happened",
                "expected": "all mutation guardrails remain false",
            },
        ],
    }


def _guardrail_audit() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_user_facing_release_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "cleanupMutationExecuted": False,
    }


def _doc(manifest: dict[str, Any], checklist: dict[str, Any]) -> str:
    steps = "\n".join(
        f"{idx}. {row['label']}: `{row.get('route') or row.get('expected')}`"
        for idx, row in enumerate(checklist["demoSteps"], start=1)
    )
    return "\n".join(
        [
            "# Video-To-Analysis User-Facing Release Readout",
            "",
            "Generated: 2026-05-09",
            "",
            "## Status",
            "",
            "The v7.2 video-to-analysis runtime has a release/readout route and a verified v38 growth-lane closeout.",
            "",
            "```text",
            f"latestSnapshot = {manifest['latestSnapshot']}",
            f"releaseRoute = {manifest['releaseRoute']}",
            f"releaseApiRoute = {manifest['releaseApiRoute']}",
            "```",
            "",
            "## Safe Claims",
            "",
            "- Runtime/product lane is operationally complete from generated truth.",
            "- The bounded real-video growth lane was closed and verified at v38.",
            "- External benchmark report/product binding exists as generated truth.",
            "- The release/readout route is live from saved artifacts.",
            "",
            "## Guardrails",
            "",
            "- No new training happened in this release readout.",
            "- No promotion mutation happened in this release readout.",
            "- No runtime-default mutation happened in this release readout.",
            "- No video/data download happened in this release readout.",
            "- No normal match storage mutation happened in this release readout.",
            "",
            "## Demo Checklist",
            "",
            steps,
            "",
            "## Next Recommended Maintenance Lane",
            "",
            "`video_to_analysis_storage_cleanup_approval`",
            "",
            "Reason: the product/readout path is now visible, and storage hygiene is the safest next house-cleaning step before additional growth.",
            "",
        ]
    )


def run_video_to_analysis_user_facing_release_readout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    output_doc_path: Path = DEFAULT_OUTPUT_DOC_PATH,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    selection_summary = load_json(root / DEFAULT_SELECTION_DIR_NAME / "next_strategic_lane_selection_summary.json")
    route_root = root / DEFAULT_RELEASE_ROUTE_DIR_NAME
    route_summary = load_json(route_root / "release_readout_route_binding_summary.json")
    view_model = load_json(route_root / "release_readout_view_model.json")

    selection_ready = _selection_ready(selection_summary)
    route_ready = _release_route_ready(route_summary, view_model)

    if not selection_ready:
        goal = False
        primary_blocker = BLOCKER_SELECTION_MISSING
        next_lever = NEXT_SELECTION
        english = "Strategic lane selection has not selected user-facing release/readout."
    elif not route_ready:
        goal = False
        primary_blocker = BLOCKER_RELEASE_ROUTE_MISSING
        next_lever = NEXT_RELEASE_ROUTE
        english = "Release/readout route is missing or unsafe."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_STORAGE_CLEANUP
        english = "User-facing release readout is ready. Advance to storage cleanup approval before more growth."

    manifest = _manifest(view_model or {}, Path(output_doc_path)) if goal else {
        "schemaVersion": "video_to_analysis_user_facing_release_manifest_v1",
        "generatedAt": utc_now_iso(),
        "releaseRoute": None,
        "latestSnapshot": None,
        "shareableReadoutPath": str(output_doc_path),
    }
    checklist = _demo_checklist()
    guardrails = _guardrail_audit()
    Path(output_doc_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_doc_path).write_text(_doc(manifest, checklist) if goal else "# Video-To-Analysis User-Facing Release Readout\n\nBlocked.\n", encoding="utf-8")

    summary = {
        "batchName": "video_to_analysis_user_facing_release_readout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "userFacingReleaseReadoutReady": goal,
        "shareableReadoutPath": str(output_doc_path),
        **standard_false_flags(),
        "generatedTruthDeleteAllowed": False,
        "cleanupMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_user_facing_release_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "strategic_selection_missing_or_wrong",
                "selected": primary_blocker == BLOCKER_SELECTION_MISSING,
                "primaryBlocker": BLOCKER_SELECTION_MISSING,
                "nextRecommendedNextLever": NEXT_SELECTION,
            },
            {
                "condition": "release_route_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_RELEASE_ROUTE_MISSING,
                "primaryBlocker": BLOCKER_RELEASE_ROUTE_MISSING,
                "nextRecommendedNextLever": NEXT_RELEASE_ROUTE,
            },
            {
                "condition": "user_facing_release_readout_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_STORAGE_CLEANUP,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="user_facing_release_readout_summary.json",
        summary=summary,
        artifacts={
            "user_facing_release_manifest.json": manifest,
            "operator_demo_checklist.json": checklist,
            "guardrail_audit.json": guardrails,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis User Facing Release Readout",
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build user-facing video-to-analysis release readout.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--output-doc-path", type=Path, default=DEFAULT_OUTPUT_DOC_PATH)
    args = parser.parse_args()
    payload = run_video_to_analysis_user_facing_release_readout(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        output_doc_path=args.output_doc_path,
    )
    import json

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
