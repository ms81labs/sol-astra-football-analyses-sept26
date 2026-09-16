from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_google_drive_bounded_fixture_fetch as fetch


def _write_probe_outputs(tmp_path: Path, *, ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    probe_root = candidate_root / "football_external_soccertrack_google_drive_fixture_access_probe_v1"
    probe_root.mkdir(parents=True, exist_ok=True)
    (probe_root / "google_drive_fixture_access_probe_summary.json").write_text(
        json.dumps(
            {
                "batchName": "football_external_soccertrack_google_drive_fixture_access_probe",
                "goalAchieved": ready,
                "primaryBlocker": None if ready else "missing",
                "driveListingAccessible": ready,
                "metadataListingOnly": True,
                "fileContentDownloadExecuted": False,
                "datasetDownloadExecuted": False,
                "trainingExecuted": False,
                "selectedMatchId": "117092" if ready else None,
                "nextRecommendedNextLever": "football_external_soccertrack_google_drive_bounded_fixture_fetch_approval",
            }
        ),
        encoding="utf-8",
    )
    (probe_root / "drive_fixture_candidate_manifest.json").write_text(
        json.dumps(
            {
                "selectedMatchId": "117092" if ready else None,
                "completeFixtureCandidateMatchCount": 1 if ready else 0,
                "candidateMatches": [
                    {
                        "matchId": "117092",
                        "completeFixtureCandidate": ready,
                        "selectedFileIdsByTask": {
                            "bas": [{"id": "bas-id", "path": "bas/117092/117092_12_class_events.json"}],
                            "gsr": [
                                {"id": "gsr-1-id", "path": "gsr/117092/117092_1st.json"},
                                {"id": "gsr-2-id", "path": "gsr/117092/117092_2nd.json"},
                            ],
                            "mot": [
                                {"id": "mot-json-id", "path": "raw/117092/117092_keypoints.json"},
                                {"id": "mot-csv-id", "path": "raw/117092/117092_player_nodes.csv"},
                                {"id": "mot-xml-id", "path": "raw/117092/117092_tracker_box_data.xml"},
                                {"id": "mot-npy-id", "path": "raw/117092/117092_homography.npy"},
                                {"id": "mot-mapx-id", "path": "raw/117092/117092_mapx.npy"},
                            ],
                            "videos": [{"id": "video-id", "path": "videos/117092/117092_panorama_1st_half.mp4"}],
                        },
                    }
                ],
                "fileContentDownloadExecuted": False,
                "datasetDownloadExecuted": False,
                "trainingExecuted": False,
            }
        ),
        encoding="utf-8",
    )
    return candidate_root


def test_google_drive_bounded_fixture_fetch_downloads_selected_non_video_fixture_files(tmp_path: Path) -> None:
    candidate_root = _write_probe_outputs(tmp_path)

    payload = fetch.run_football_external_soccertrack_google_drive_bounded_fixture_fetch(
        storage_root=tmp_path,
        downloader=lambda file_id, _path, _output_root, _tool_python: f"{file_id}\n".encode("utf-8"),
    )

    output_root = candidate_root / "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1"
    manifest = json.loads((output_root / "google_drive_bounded_fixture_fetch_manifest.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "download_scope_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedMatchId"] == "117092"
    assert payload["downloadedFixtureFileCount"] == 7
    assert payload["skippedVideoFileCount"] == 1
    assert payload["skippedOptionalLargeDerivedFileCount"] == 1
    assert payload["datasetDownloadExecuted"] is False
    assert payload["fullDatasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_fixture_materialization"
    assert all((output_root / row["relativePath"]).exists() for row in manifest["downloadedFiles"])
    assert guardrail["skippedVideoFileCount"] == 1
    assert guardrail["skippedOptionalLargeDerivedFileCount"] == 1
    assert guardrail["videoDownloadExecuted"] is False


def test_google_drive_bounded_fixture_fetch_blocks_without_ready_probe(tmp_path: Path) -> None:
    _write_probe_outputs(tmp_path, ready=False)

    payload = fetch.run_football_external_soccertrack_google_drive_bounded_fixture_fetch(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_google_drive_fixture_probe_missing_or_unready"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_google_drive_fixture_access_probe"
    assert payload["sampleDownloadExecuted"] is False


def test_google_drive_bounded_fixture_fetch_fails_closed_on_download_error(tmp_path: Path) -> None:
    _write_probe_outputs(tmp_path)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("download failed")

    payload = fetch.run_football_external_soccertrack_google_drive_bounded_fixture_fetch(
        storage_root=tmp_path,
        downloader=_raise,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_google_drive_bounded_fixture_fetch_failed"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_google_drive_bounded_fixture_fetch_repair"


def test_google_drive_bounded_fixture_fetch_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_probe_outputs(tmp_path)

    payload = fetch.run_football_external_soccertrack_google_drive_bounded_fixture_fetch(
        storage_root=tmp_path,
        downloader=lambda file_id, _path, _output_root, _tool_python: file_id.encode("utf-8"),
    )

    assert payload["attemptPlanFamilies"] == [
        "google_drive_bounded_fixture_fetch",
        "google_drive_bounded_fetch_repair",
        "google_drive_bounded_fetch_blocker_summary",
    ]


def test_google_drive_bounded_fixture_fetch_cleans_partial_temp_files_on_download_error(tmp_path: Path) -> None:
    _write_probe_outputs(tmp_path)

    def _write_partial_then_raise(file_id: str, source_path: str, output_root: Path, _tool_python: Path) -> bytes:
        temp_dir = output_root / "_gdown_download_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / f"{file_id}_{Path(source_path).name}.part").write_bytes(b"partial")
        raise RuntimeError("download failed")

    payload = fetch.run_football_external_soccertrack_google_drive_bounded_fixture_fetch(
        storage_root=tmp_path,
        downloader=_write_partial_then_raise,
    )

    output_root = (
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1"
    )
    assert payload["primaryBlocker"] == "football_external_soccertrack_google_drive_bounded_fixture_fetch_failed"
    assert list((output_root / "_gdown_download_tmp").glob("*.part")) == []


def test_google_drive_bounded_fixture_fetch_accepts_path_returning_downloader(tmp_path: Path) -> None:
    _write_probe_outputs(tmp_path)

    def _path_downloader(file_id: str, source_path: str, output_root: Path, _tool_python: Path) -> Path:
        temp_dir = output_root / "_gdown_download_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        path = temp_dir / f"{file_id}_{Path(source_path).name}"
        path.write_bytes(f"{file_id}:{source_path}".encode("utf-8"))
        return path

    payload = fetch.run_football_external_soccertrack_google_drive_bounded_fixture_fetch(
        storage_root=tmp_path,
        downloader=_path_downloader,
    )

    output_root = (
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1"
    )
    manifest = json.loads((output_root / "google_drive_bounded_fixture_fetch_manifest.json").read_text(encoding="utf-8"))
    assert payload["goalAchieved"] is True
    assert all((output_root / row["relativePath"]).exists() for row in manifest["downloadedFiles"])
    assert [row.name for row in (output_root / "_gdown_download_tmp").glob("*") if row.is_file()] == []
