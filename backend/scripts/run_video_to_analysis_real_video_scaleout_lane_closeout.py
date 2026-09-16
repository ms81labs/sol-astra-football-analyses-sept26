from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME, DEFAULT_STORAGE_ROOT, candidate_root, guarded_summary,
    latest_versioned_dir, load_json, reset_output, utc_now_iso, write_outcome,
)

DEFAULT_REPORT_DIR_NAME = "video_to_analysis_real_video_scaleout_report_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_real_video_scaleout_lane_closeout_v1"
BLOCKER_REPORT_MISSING = "video_to_analysis_real_video_scaleout_report_missing"
NEXT_REPORT = "video_to_analysis_real_video_scaleout_report_route_binding"
NEXT_SAMPLE = "video_to_analysis_next_sample_selection_snapshot"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "real_video_scaleout_lane_closeout"},
        {"attemptNumber": 2, "attemptApproachFamily": "scaleout_closeout_evidence_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "scaleout_closeout_blocker_summary"},
    ]}


def run_video_to_analysis_real_video_scaleout_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    report_dir = latest_versioned_dir(root, "video_to_analysis_real_video_scaleout_report_route_binding", DEFAULT_REPORT_DIR_NAME)
    report = load_json(report_dir / "real_video_scaleout_report_route_binding_summary.json")
    ready = bool(isinstance(report, dict) and report.get("goalAchieved") is True and report.get("scaleoutReportRouteReady") is True)
    manifest = {"schemaVersion": "video_to_analysis_real_video_scaleout_lane_closeout_manifest_v1", "generatedAt": utc_now_iso(), "sourceReportDir": report_dir.name, "realVideoScaleoutLaneClosed": ready}
    summary = guarded_summary(
        batch_name="video_to_analysis_real_video_scaleout_lane_closeout",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_REPORT_MISSING,
        next_lever=NEXT_SAMPLE if ready else NEXT_REPORT,
        english="Real-video scaleout lane closed; select next sample." if ready else "Scaleout report missing.",
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={"realVideoScaleoutLaneClosed": ready},
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="real_video_scaleout_lane_closeout_summary.json",
        summary=summary,
        artifacts={
            "real_video_scaleout_lane_closeout_manifest.json": manifest,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Real Video Scaleout Lane Closeout",
    )


def main() -> None:
    main_for("Close real-video scaleout lane.", run_video_to_analysis_real_video_scaleout_lane_closeout)


if __name__ == "__main__":
    main()
