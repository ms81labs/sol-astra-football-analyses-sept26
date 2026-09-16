from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_upload_to_analysis_walkthrough as walkthrough


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_broader_choice(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
        / "football_external_soccernet_broader_validation_choice_v1"
        / "soccernet_broader_validation_choice_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "broaderValidationHeldAsOptionalFutureGrowth": True,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )


def test_upload_to_analysis_walkthrough_routes_to_v7_4_training_decision(tmp_path: Path) -> None:
    _seed_broader_choice(tmp_path)

    payload = walkthrough.run_video_to_analysis_upload_to_analysis_walkthrough(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_upload_to_analysis_walkthrough_v1"
    walkthrough_payload = json.loads((output_root / "upload_to_analysis_walkthrough.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["uploadToAnalysisWalkthroughReady"] is True
    assert payload["nextRecommendedNextLever"] == "v7_4_training_decision_from_real_misses"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert (output_root / "upload_to_analysis_walkthrough.md").exists()
    assert walkthrough_payload["guardrails"] == {
        "downloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }


def test_upload_to_analysis_walkthrough_blocks_without_broader_choice(tmp_path: Path) -> None:
    payload = walkthrough.run_video_to_analysis_upload_to_analysis_walkthrough(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_upload_walkthrough_broader_choice_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_broader_validation_choice"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
