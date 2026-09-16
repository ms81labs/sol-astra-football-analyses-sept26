from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_sample_fixture_materialization as materialize


def _write_fetch_outputs(tmp_path: Path, *, ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fetch_root = candidate_root / "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1"
    fixture_root = fetch_root / "sample_fixture_files" / "selected_match_117092"
    fixture_root.mkdir(parents=True, exist_ok=True)
    files = {
        "bas__117092__117092_12_class_events.json": json.dumps(
            {"match_id": "117092", "fps": 25.0, "actions": [{"gameTime": "1 - 0:01", "label": "PASS"}]}
        ),
        "gsr__117092__117092_1st.json": json.dumps({"info": {"frame_rate": 25, "seq_length": 2}, "images": []}),
        "gsr__117092__117092_2nd.json": json.dumps({"info": {"frame_rate": 25, "seq_length": 3}, "images": []}),
        "raw__117092__117092_12_class_events.json": json.dumps(
            {"annotations": [{"gameTime": "1 - 0:01", "label": "PASS"}]}
        ),
        "raw__117092__117092_player_nodes.csv": "id,match_id,x,y\n1,117092,0.5,0.6\n",
        "raw__117092__117092_tracker_box_data.xml": '<data><frame frameNumber="1" matchTime="40" ballStatus="ALIVE"/></data>',
        "raw__117092__117092_tracker_box_metadata.xml": "<metadata><match matchId=\"117092\"/></metadata>",
    }
    downloaded = []
    for name, content in files.items():
        path = fixture_root / name
        path.write_text(content, encoding="utf-8")
        task = "gsr" if name.startswith("gsr") else "bas" if name.startswith("bas") else "mot"
        downloaded.append(
            {
                "taskId": task,
                "sourcePath": name.replace("__", "/"),
                "relativePath": str(path.relative_to(fetch_root)),
                "sizeBytes": path.stat().st_size,
                "sha256": "x",
            }
        )
    (fetch_root / "google_drive_bounded_fixture_fetch_summary.json").write_text(
        json.dumps(
            {
                "batchName": "football_external_soccertrack_google_drive_bounded_fixture_fetch",
                "goalAchieved": ready,
                "primaryBlocker": None if ready else "missing",
                "selectedMatchId": "117092" if ready else None,
                "downloadedFixtureFileCount": len(downloaded) if ready else 0,
                "downloadedTaskIds": ["bas", "gsr", "mot"] if ready else [],
                "sampleDownloadExecuted": ready,
                "datasetDownloadExecuted": False,
                "trainingExecuted": False,
            }
        ),
        encoding="utf-8",
    )
    (fetch_root / "google_drive_bounded_fixture_fetch_manifest.json").write_text(
        json.dumps(
            {
                "selectedMatchId": "117092" if ready else None,
                "downloadedFiles": downloaded if ready else [],
                "datasetDownloadExecuted": False,
                "trainingExecuted": False,
            }
        ),
        encoding="utf-8",
    )
    return candidate_root


def test_soccertrack_sample_fixture_materialization_writes_lightweight_adapter_fixtures(tmp_path: Path) -> None:
    candidate_root = _write_fetch_outputs(tmp_path)

    payload = materialize.run_football_external_soccertrack_sample_fixture_materialization(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_sample_fixture_materialization_v1"
    index = json.loads((output_root / "soccertrack_sample_fixture_index.json").read_text(encoding="utf-8"))
    bas = json.loads((output_root / "soccertrack_bas_event_stream_fixture.json").read_text(encoding="utf-8"))
    gsr = json.loads((output_root / "soccertrack_gsr_frame_state_fixture.json").read_text(encoding="utf-8"))
    mot = json.loads((output_root / "soccertrack_mot_track_frame_fixture.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedMatchId"] == "117092"
    assert payload["materializedTaskIds"] == ["bas", "gsr", "mot"]
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_adapter_smoke_test"
    assert index["fixtureMaterializationMode"] == "lightweight_index_plus_samples"
    assert bas["actionCount"] == 1
    assert gsr["largeFileHeaderOnly"] is True
    assert mot["trackerBoxData"]["sampledFrameCount"] == 1


def test_soccertrack_sample_fixture_materialization_blocks_without_fetch(tmp_path: Path) -> None:
    _write_fetch_outputs(tmp_path, ready=False)

    payload = materialize.run_football_external_soccertrack_sample_fixture_materialization(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_google_drive_bounded_fixture_fetch_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_google_drive_bounded_fixture_fetch"


def test_soccertrack_sample_fixture_materialization_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fetch_outputs(tmp_path)

    payload = materialize.run_football_external_soccertrack_sample_fixture_materialization(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_lightweight_fixture_materialization",
        "soccertrack_fixture_materialization_repair",
        "soccertrack_fixture_materialization_blocker_summary",
    ]
