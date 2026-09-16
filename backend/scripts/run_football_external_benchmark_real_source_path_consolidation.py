from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    load_json,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_DASHBOARD_DIR_NAME = "video_to_analysis_operator_dashboard_polish_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_real_source_path_consolidation_v1"
BLOCKER_DASHBOARD_MISSING = "football_external_real_source_path_operator_dashboard_missing"
NEXT_DASHBOARD = "video_to_analysis_operator_dashboard_polish"
NEXT_SCALEOUT = "video_to_analysis_real_video_scaleout_plan"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "real_source_path_consolidation"},
            {"attemptNumber": 2, "attemptApproachFamily": "source_path_scope_repair"},
            {"attemptNumber": 3, "attemptApproachFamily": "source_path_blocker_summary"},
        ],
    }


def _dashboard_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("operatorDashboardRouteReady") is True
    )


def run_football_external_benchmark_real_source_path_consolidation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    dashboard_summary = load_json(root / DEFAULT_DASHBOARD_DIR_NAME / "operator_dashboard_polish_summary.json")
    ready = _dashboard_ready(dashboard_summary)

    manifest = {
        "schemaVersion": "football_external_real_source_path_consolidation_manifest_v1",
        "generatedAt": utc_now_iso(),
        "sourcePaths": [
            {
                "sourceId": "soccernet",
                "sourceKind": "NDA_API_and_bounded_extracted_video_member",
                "currentArtifactBasis": "generated_truth_and_bounded_224p_member_evidence",
                "boundedStoragePolicy": "no_full_archive_download_without_explicit_approval",
                "nextUse": "bounded_real_video_scaleout_candidate",
            },
            {
                "sourceId": "soccertrack",
                "sourceKind": "Google_Drive_or_materialized_fixture_path",
                "currentArtifactBasis": "generated_truth_sample_fixture_and_product_route_evidence",
                "boundedStoragePolicy": "fixture_or_sample_only_until_approval",
                "nextUse": "structured_event_context_candidate",
            },
        ],
        "fullDatasetDownloadAllowed": False,
        "sourcePathConsolidationReady": ready,
    }
    summary = guarded_summary(
        batch_name="football_external_benchmark_real_source_path_consolidation",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_DASHBOARD_MISSING,
        next_lever=NEXT_SCALEOUT if ready else NEXT_DASHBOARD,
        english=(
            "External real-source paths are consolidated under bounded storage governance."
            if ready
            else "Operator dashboard truth is missing; bind dashboard before source path consolidation."
        ),
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "sourcePathConsolidationReady": ready,
            "sourcePathCount": len(manifest["sourcePaths"]) if ready else 0,
            "fullDatasetDownloadAllowed": False,
        },
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="real_source_path_consolidation_summary.json",
        summary=summary,
        artifacts={
            "real_source_path_consolidation_manifest.json": manifest,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External Benchmark Real Source Path Consolidation",
    )


def main() -> None:
    main_for("Consolidate external benchmark real-source paths.", run_football_external_benchmark_real_source_path_consolidation)


if __name__ == "__main__":
    main()
