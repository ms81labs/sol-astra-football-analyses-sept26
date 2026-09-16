from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_google_drive_fixture_access_probe as probe


def _row(file_id: str, path: str) -> dict[str, str]:
    return {"id": file_id, "path": path, "localPath": f"/tmp/{path}"}


def _complete_listing() -> list[dict[str, str]]:
    return [
        _row("bas-117092", "bas/117092/117092_12_class_events.json"),
        _row("gsr-117092-1", "gsr/117092/117092_1st.json"),
        _row("gsr-117092-2", "gsr/117092/117092_2nd.json"),
        _row("mot-117092-events", "mot/raw/117092/117092_12_class_events.json"),
        _row("mot-117092-nodes", "mot/raw/117092/117092_player_nodes.csv"),
        _row("mot-117092-box", "mot/raw/117092/117092_tracker_box_data.xml"),
        _row("mot-117092-meta", "mot/raw/117092/117092_tracker_box_metadata.xml"),
        _row("mot-117092-h", "mot/raw/117092/117092_homography.npy"),
        _row("video-117092-1", "videos/117092/117092_panorama_1st_half.mp4"),
        _row("video-117092-2", "videos/117092/117092_panorama_2nd_half.mp4"),
        _row("bas-118575", "bas/118575/118575_12_class_events.json"),
        _row("gsr-118575-1", "gsr/118575/118575_1st.json"),
        _row("gsr-118575-2", "gsr/118575/118575_2nd.json"),
        _row("mot-118575-nodes", "raw/118575/118575_player_nodes.csv"),
        _row("mot-118575-box", "raw/118575/118575_tracker_box_data.xml"),
        _row("mot-118575-meta", "raw/118575/118575_tracker_box_metadata.xml"),
        _row("mot-118575-h", "raw/118575/118575_homography.npy"),
        _row("mot-118575-k", "raw/118575/118575_keypoints.json"),
    ]


def test_google_drive_fixture_access_probe_finds_complete_matches_without_downloading(tmp_path: Path) -> None:
    payload = probe.run_football_external_soccertrack_google_drive_fixture_access_probe(
        storage_root=tmp_path,
        listing_fetcher=lambda *_args, **_kwargs: _complete_listing(),
    )

    output_root = (
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "football_external_soccertrack_google_drive_fixture_access_probe_v1"
    )
    summary = json.loads((output_root / "google_drive_fixture_access_probe_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_root / "drive_fixture_candidate_manifest.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "drive_download_scope_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["driveListingAccessible"] is True
    assert payload["driveListingFileCount"] == len(_complete_listing())
    assert payload["completeFixtureCandidateMatchCount"] == 2
    assert payload["selectedMatchId"] == "117092"
    assert payload["sampleDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["fullDatasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_google_drive_bounded_fixture_fetch_approval"
    assert summary == payload
    assert manifest["selectedMatchId"] == "117092"
    assert set(manifest["selectedMatchTaskCoverage"]["117092"]) == {"bas", "gsr", "mot", "videos"}
    assert guardrail["metadataListingOnly"] is True
    assert guardrail["fileContentDownloadExecuted"] is False


def test_google_drive_fixture_access_probe_blocks_when_listing_fails(tmp_path: Path) -> None:
    def _raise(*_args, **_kwargs):
        raise RuntimeError("drive listing needs cookies")

    payload = probe.run_football_external_soccertrack_google_drive_fixture_access_probe(
        storage_root=tmp_path,
        listing_fetcher=_raise,
    )

    assert payload["goalAchieved"] is False
    assert payload["roadmapAdvanceAllowed"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_google_drive_listing_probe_failed"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_google_drive_access_cookie_setup"
    assert payload["sampleDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False


def test_google_drive_fixture_access_probe_blocks_without_complete_fixture_match(tmp_path: Path) -> None:
    partial_listing = [
        _row("bas-117092", "bas/117092/117092_12_class_events.json"),
        _row("gsr-117092-1", "gsr/117092/117092_1st.json"),
    ]

    payload = probe.run_football_external_soccertrack_google_drive_fixture_access_probe(
        storage_root=tmp_path,
        listing_fetcher=lambda *_args, **_kwargs: partial_listing,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_google_drive_complete_fixture_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_drive_archive_member_probe"
    assert payload["driveListingAccessible"] is True
    assert payload["completeFixtureCandidateMatchCount"] == 0


def test_google_drive_fixture_access_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    payload = probe.run_football_external_soccertrack_google_drive_fixture_access_probe(
        storage_root=tmp_path,
        listing_fetcher=lambda *_args, **_kwargs: _complete_listing(),
    )

    assert payload["attemptPlanFamilies"] == [
        "google_drive_fixture_listing_probe",
        "google_drive_listing_tool_repair",
        "google_drive_access_blocker_summary",
    ]
