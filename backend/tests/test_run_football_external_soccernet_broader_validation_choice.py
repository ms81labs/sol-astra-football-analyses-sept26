from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_broader_validation_choice as choice


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root / "video_to_analysis_release_acceptance_archive_v1" / "release_acceptance_archive_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "videoToAnalysisReleaseAcceptanceArchived": True,
            "currentReleaseFinished": True,
        },
    )
    _write_json(
        root / "football_external_soccernet_full_analysis_lane_closeout_v1" / "full_analysis_lane_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None},
    )
    _write_json(
        root
        / "football_external_soccernet_bounded_product_validation_report_binding_v1"
        / "soccernet_bounded_product_validation_report_binding_summary.json",
        {"goalAchieved": True, "primaryBlocker": None},
    )


def test_broader_validation_choice_routes_to_upload_walkthrough_when_soccernet_is_bound(tmp_path: Path) -> None:
    _seed_inputs(tmp_path)

    payload = choice.run_football_external_soccernet_broader_validation_choice(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_broader_validation_choice_v1"
    choice_payload = json.loads((output_root / "soccernet_broader_validation_choice.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["broaderValidationRunNow"] is False
    assert payload["broaderValidationHeldAsOptionalFutureGrowth"] is True
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_upload_to_analysis_walkthrough"
    assert choice_payload["soccernetFullAnalysisClosed"] is True


def test_broader_validation_choice_blocks_without_archive(tmp_path: Path) -> None:
    payload = choice.run_football_external_soccernet_broader_validation_choice(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_broader_choice_release_archive_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_acceptance_archive"
