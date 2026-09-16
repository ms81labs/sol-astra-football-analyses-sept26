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

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_real_video_scaleout_lane_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_next_sample_selection_snapshot_v1"
BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_next_sample_scaleout_closeout_missing"
NEXT_CLOSEOUT = "video_to_analysis_real_video_scaleout_lane_closeout"
NEXT_APPROVAL = "video_to_analysis_bounded_next_sample_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "next_sample_selection_snapshot"},
        {"attemptNumber": 2, "attemptApproachFamily": "next_sample_selection_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "next_sample_blocker_summary"},
    ]}


def _candidate_samples_from_scaleout_results(root: Path, closeout: dict[str, Any]) -> list[dict[str, str]]:
    report_dir_name = closeout.get("sourceReportDir")
    if not report_dir_name:
        return []
    view_model = load_json(root / str(report_dir_name) / "real_video_scaleout_report_view_model.json")
    results = view_model.get("scaleoutResults", []) if isinstance(view_model, dict) else []
    passed_ids = [
        str(row.get("caseId"))
        for row in results
        if isinstance(row, dict) and row.get("status") == "passed" and row.get("caseId")
    ]
    passed_id_set = set(passed_ids)
    if "operator_selected_canary_video" in passed_id_set:
        return [
            {"id": "operator_selected_canary_video", "reason": "operator followup from initial scaleout"},
            {"id": "soccernet_second_bounded_member", "reason": "external broadcast diversity from initial scaleout queue"},
            {"id": "normal_storage_recent_upload", "reason": "fresh product-path followup from initial scaleout"},
        ]
    if {
        "operator_canary_followup_clip",
        "soccernet_third_bounded_member",
        "normal_storage_followup_upload",
    }.issubset(passed_id_set):
        return [
            {"id": "operator_canary_followup_clip", "reason": "operator followup from latest scaleout"},
            {"id": "soccernet_third_bounded_member", "reason": "external broadcast diversity from latest scaleout"},
            {"id": "normal_storage_followup_upload", "reason": "fresh product-path followup from latest scaleout"},
        ]
    preferred: list[dict[str, str]] = []
    for family, reason in [
        ("operator", "operator followup from latest scaleout"),
        ("soccernet", "external broadcast diversity from latest scaleout"),
        ("normal_storage", "fresh product-path followup from latest scaleout"),
    ]:
        match = next((case_id for case_id in passed_ids if case_id.startswith(family)), None)
        if match:
            preferred.append({"id": match, "reason": reason})
    if len(preferred) >= 3:
        return preferred[:3]
    seen = {row["id"] for row in preferred}
    for case_id in passed_ids:
        if case_id not in seen:
            preferred.append({"id": case_id, "reason": "scaleout followup from latest passed case"})
        if len(preferred) == 3:
            break
    return preferred


def run_video_to_analysis_next_sample_selection_snapshot(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    closeout_dir = latest_versioned_dir(root, "video_to_analysis_real_video_scaleout_lane_closeout", DEFAULT_CLOSEOUT_DIR_NAME)
    closeout = load_json(closeout_dir / "real_video_scaleout_lane_closeout_summary.json")
    closeout_manifest = load_json(closeout_dir / "real_video_scaleout_lane_closeout_manifest.json")
    ready = bool(isinstance(closeout, dict) and closeout.get("goalAchieved") is True and closeout.get("realVideoScaleoutLaneClosed") is True)
    candidates = _candidate_samples_from_scaleout_results(root, closeout_manifest) if isinstance(closeout_manifest, dict) else []
    snapshot = {
        "schemaVersion": "video_to_analysis_next_sample_selection_snapshot_v1",
        "generatedAt": utc_now_iso(),
        "sourceCloseoutDir": closeout_dir.name,
        "nextSampleSelectionSnapshotReady": ready,
        "selectedNextLever": NEXT_APPROVAL if ready else None,
        "candidateSamples": candidates,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_next_sample_selection_snapshot",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_CLOSEOUT_MISSING,
        next_lever=NEXT_APPROVAL if ready else NEXT_CLOSEOUT,
        english="Next sample selection snapshot is ready for bounded execution approval." if ready else "Scaleout closeout missing.",
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "nextSampleSelectionSnapshotReady": ready,
            "sourceCloseoutDir": closeout_dir.name,
            "selectedNextLever": NEXT_APPROVAL if ready else None,
            "candidateSampleCount": len(candidates) if ready else 0,
            "candidateSampleIds": [row["id"] for row in candidates] if ready else [],
        },
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="next_sample_selection_snapshot_summary.json",
        summary=summary,
        artifacts={
            "next_sample_selection_snapshot.json": snapshot,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Next Sample Selection Snapshot",
    )


def main() -> None:
    main_for("Write next sample selection snapshot.", run_video_to_analysis_next_sample_selection_snapshot)


if __name__ == "__main__":
    main()
