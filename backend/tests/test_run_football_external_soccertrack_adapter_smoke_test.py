from __future__ import annotations

import io
import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_adapter_smoke_test as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _gsr_payload() -> dict[str, object]:
    def annotation(image_id: str, annotation_id: str, x: float, y: float) -> dict[str, object]:
        return {
            "id": annotation_id,
            "image_id": image_id,
            "track_id": 7,
            "supercategory": "object",
            "category_id": 1,
            "attributes": {
                "role": "player",
                "jersey": "9",
                "team": "left",
                "player_id": 11709209,
            },
            "bbox_image": {
                "x": 100,
                "y": 200,
                "x_center": 110.0,
                "y_center": 220.0,
                "w": 20,
                "h": 40,
            },
            "bbox_pitch": {
                "x_bottom_left": x,
                "y_bottom_left": y,
                "x_bottom_middle": x,
                "y_bottom_middle": y,
                "x_bottom_right": x,
                "y_bottom_right": y,
            },
            "bbox_pitch_raw": {},
        }

    return {
        "info": {"frame_rate": 25, "seq_length": 3},
        "images": [{"image_id": "3000001"}, {"image_id": "3000002"}],
        "annotations": [
            annotation("3000001", "300000001", -52.5, 34.0),
            annotation("3000002", "300000101", 0.0, 0.0),
        ],
        "categories": [],
    }


def _write_fixture_inputs(tmp_path: Path, *, fixture_goal: bool = True, bad_gsr: bool = False) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fixture_root = candidate_root / "football_external_soccertrack_sample_fixture_materialization_v1"
    source_root = tmp_path / "soccertrack_source"
    source_root.mkdir(parents=True, exist_ok=True)
    bas_source = source_root / "bas.json"
    bas_source.write_text(
        json.dumps(
            {
                "match_id": "117092",
                "fps": 25.0,
                "actions": [
                    {"gameTime": "1 - 0:01", "label": "PASS", "position": "1233", "team": "right", "player_id": "467259"},
                    {"gameTime": "1 - 0:03", "label": "DRIVE", "position": "3400", "team": "left", "player_id": "467256"},
                    {"gameTime": "90:01", "label": "SHOT", "position": "5401560", "team": "left", "player_id": "467257"},
                ],
            }
        ),
        encoding="utf-8",
    )
    gsr_sources = [source_root / "117092_1st.json", source_root / "117092_2nd.json"]
    for source in gsr_sources:
        _write_json(source, _gsr_payload())
    _write_json(
        fixture_root / "soccertrack_sample_fixture_materialization_summary.json",
        {
            "batchName": "football_external_soccertrack_sample_fixture_materialization",
            "goalAchieved": fixture_goal,
            "primaryBlocker": None if fixture_goal else "fixture_missing",
            "selectedMatchId": "117092" if fixture_goal else None,
            "materializedTaskIds": ["bas", "gsr", "mot"] if fixture_goal else [],
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        fixture_root / "soccertrack_sample_fixture_index.json",
        {
            "selectedMatchId": "117092" if fixture_goal else None,
            "fixtureMaterializationMode": "lightweight_index_plus_samples",
            "materializedTaskIds": ["bas", "gsr", "mot"] if fixture_goal else [],
            "trainingExecuted": False,
        },
    )
    _write_json(
        fixture_root / "soccertrack_bas_event_stream_fixture.json",
        {
            "schemaVersion": "soccertrack_bas_event_stream_fixture_v1",
            "sourcePath": str(bas_source),
            "matchId": "117092",
            "fps": 25.0,
            "actionCount": 3,
            "sampleActions": [
                {"gameTime": "1 - 0:01", "label": "PASS", "position": "1233", "team": "right", "player_id": "467259"}
            ],
        },
    )
    _write_json(
        fixture_root / "soccertrack_gsr_frame_state_fixture.json",
        {
            "schemaVersion": "soccertrack_gsr_frame_state_fixture_v1",
            "largeFileHeaderOnly": True,
            "halfFiles": []
            if bad_gsr
            else [
                {
                    "sourcePath": str(gsr_sources[0]),
                    "info": {"frame_rate": 25, "seq_length": 3, "game_time_start": "1 - 00:00"},
                    "sizeBytes": gsr_sources[0].stat().st_size,
                    "sampleImageIds": ["3000001"],
                },
                {
                    "sourcePath": str(gsr_sources[1]),
                    "info": {"frame_rate": 25, "seq_length": 3, "game_time_start": "2 - 00:00"},
                    "sizeBytes": gsr_sources[1].stat().st_size,
                    "sampleImageIds": ["3000001"],
                },
            ],
        },
    )
    _write_json(
        fixture_root / "soccertrack_mot_track_frame_fixture.json",
        {
            "schemaVersion": "soccertrack_mot_track_frame_fixture_v1",
            "trackerBoxData": {
                "frameCount": 20,
                "sampledFrameCount": 1,
                "sampleFrames": [{"frameNumber": "1", "matchTime": "40", "ballStatus": "ALIVE"}],
            },
            "playerNodes": {
                "fieldNames": ["match_id", "event_time", "x", "y"],
                "sampleRows": [{"match_id": "117092", "event_time": "1233", "x": "0.5", "y": "0.6"}],
            },
        },
    )
    _write_json(
        fixture_root / "soccertrack_game_state_fixture.json",
        {
            "schemaVersion": "soccertrack_game_state_fixture_v1",
            "selectedMatchId": "117092",
            "taskFixtures": ["bas", "gsr", "mot"],
        },
    )
    return candidate_root


def test_soccertrack_adapter_smoke_passes_and_writes_canonical_external_match_fixture(tmp_path: Path) -> None:
    candidate_root = _write_fixture_inputs(tmp_path)

    payload = smoke.run_football_external_soccertrack_adapter_smoke_test(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_adapter_smoke_test_v1"
    canonical = json.loads((output_root / "canonical_external_match_fixture.json").read_text(encoding="utf-8"))
    bas_audit = json.loads((output_root / "soccertrack_bas_adapter_audit.json").read_text(encoding="utf-8"))
    gsr_audit = json.loads((output_root / "soccertrack_gsr_adapter_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedMatchId"] == "117092"
    assert payload["canonicalExternalFixtureReady"] is True
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_match_bundle_bridge_smoke"
    assert payload["trainingExecuted"] is False
    assert canonical["sourceDataset"] == "soccertrack_v2"
    assert canonical["basEventCount"] == 3
    assert canonical["gsrHalfCount"] == 2
    assert len(canonical["gsrFrames"]) == 4
    assert canonical["gsrFrames"][0]["half"] == 1
    assert canonical["gsrFrames"][0]["sourceImageId"] == "3000001"
    assert canonical["gsrFrames"][0]["timestampSecondsInHalf"] == 0.0
    first_entity = canonical["gsrFrames"][0]["entities"][0]
    assert first_entity["trackId"] == 7
    assert first_entity["playerId"] == "11709209"
    assert first_entity["role"] == "player"
    assert first_entity["jerseyNumber"] == 9
    assert first_entity["teamSide"] == "left"
    assert first_entity["pitchPositionMeters"] == {"x": -52.5, "y": 34.0}
    assert first_entity["pitchPositionNormalized"] == {"x": 0.0, "y": 0.0}
    assert canonical["gsrFrames"][1]["entities"][0]["pitchPositionNormalized"] == {"x": 50.0, "y": 50.0}
    assert canonical["gsrFrames"][2]["half"] == 2
    assert gsr_audit["gsrFrameCount"] == 4
    assert gsr_audit["gsrEntityCount"] == 4
    assert gsr_audit["omittedPositionCount"] == 0
    assert gsr_audit["fullGsrJsonLoaded"] is False
    assert canonical["motSampledFrameCount"] == 1
    assert canonical["normalizedEvents"][0]["eventId"] == "soccertrack-117092-bas-000000"
    assert canonical["normalizedEvents"][0]["positionMs"] == 1233
    assert canonical["normalizedEvents"][-1]["period"] == 3
    assert bas_audit["basAdapterPassed"] is True


def test_soccertrack_gsr_iterator_decodes_across_chunks_and_can_stop_before_malformed_tail() -> None:
    stream = io.StringIO(
        '{"images":[],"annotations":['
        '{"image_id":"3000001"},'
        '{"image_id":"3000002"},'
        '{"image_id":"3000003"},BROKEN'
    )

    records = smoke._iter_json_array(stream, "annotations", chunk_size=7)
    assert [next(records)["image_id"] for _ in range(3)] == ["3000001", "3000002", "3000003"]
    records.close()


def test_bas_period_follows_the_global_match_clock() -> None:
    assert smoke._period_from_game_time("1 - 44:59") == 1
    assert smoke._period_from_game_time("2 - 45:00") == 2
    assert smoke._period_from_game_time("90:01") == 3


def test_soccertrack_adapter_smoke_blocks_without_materialized_fixture(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path, fixture_goal=False)

    payload = smoke.run_football_external_soccertrack_adapter_smoke_test(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_sample_fixture_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_fixture_materialization"


def test_soccertrack_adapter_smoke_routes_gsr_gap_to_streaming_adapter(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path, bad_gsr=True)

    payload = smoke.run_football_external_soccertrack_adapter_smoke_test(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_gsr_adapter_contract_gap"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_streaming_gsr_adapter"


def test_soccertrack_adapter_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path)

    payload = smoke.run_football_external_soccertrack_adapter_smoke_test(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_lightweight_adapter_smoke",
        "soccertrack_adapter_contract_repair",
        "soccertrack_adapter_blocker_summary",
    ]
