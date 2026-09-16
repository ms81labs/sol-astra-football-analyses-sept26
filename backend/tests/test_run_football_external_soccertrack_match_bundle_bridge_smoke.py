from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_match_bundle_bridge_smoke as bridge


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _gsr_frame(half: int, frame_index: int, x: float, y: float) -> dict[str, object]:
    return {
        "half": half,
        "frameIndex": frame_index,
        "sourceImageId": "3000001",
        "timestampSecondsInHalf": frame_index / 25,
        "entities": [
            {
                "trackId": 7,
                "playerId": "11709209",
                "role": "player",
                "jerseyNumber": 9,
                "teamSide": "left",
                "pitchPositionMeters": {"x": x, "y": y},
                "pitchPositionNormalized": {
                    "x": (x + 52.5) / 105 * 100,
                    "y": (34 - y) / 68 * 100,
                },
                "imageBbox": {"x": 100, "y": 200, "w": 20, "h": 40},
            }
        ],
    }


def _write_adapter_outputs(tmp_path: Path, *, ready: bool = True, missing_events: bool = False) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    adapter_root = candidate_root / "football_external_soccertrack_adapter_smoke_test_v1"
    _write_json(
        adapter_root / "soccertrack_adapter_smoke_summary.json",
        {
            "batchName": "football_external_soccertrack_adapter_smoke_test",
            "goalAchieved": ready,
            "primaryBlocker": None if ready else "adapter_failed",
            "canonicalExternalFixtureReady": ready,
            "selectedMatchId": "117092" if ready else None,
            "basEventCount": 2 if ready else 0,
            "gsrHalfCount": 2 if ready else 0,
            "motFrameCount": 20 if ready else 0,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_match_bundle_bridge_smoke",
        },
    )
    _write_json(
        adapter_root / "canonical_external_match_fixture.json",
        {
            "schemaVersion": "canonical_external_match_fixture_v1",
            "sourceDataset": "soccertrack_v2",
            "sourceMatchId": "117092",
            "basEventCount": 0 if missing_events else 2,
            "normalizedEvents": []
            if missing_events
            else [
                {
                    "eventId": "soccertrack-117092-bas-000000",
                    "sourceMatchId": "117092",
                    "period": 1,
                    "positionMs": 1233,
                    "eventType": "PASS",
                    "team": "right",
                    "playerId": "467259",
                },
                {
                    "eventId": "soccertrack-117092-bas-000001",
                    "sourceMatchId": "117092",
                    "period": 1,
                    "positionMs": 3400,
                    "eventType": "DRIVE",
                    "team": "left",
                    "playerId": "467256",
                },
            ],
            "gsrHalfCount": 2,
            "gsrHalfSummaries": [{"seqLength": 10, "frameRate": 25.0}, {"seqLength": 11, "frameRate": 25.0}],
            "gsrFrames": [
                _gsr_frame(1, 0, -52.5, 34.0),
                _gsr_frame(2, 0, 0.0, 0.0),
            ],
            "motFrameCount": 20,
            "motSampledFrameCount": 1,
            "motSampleFrames": [{"frameNumber": "1", "matchTime": "40", "ballStatus": "ALIVE"}],
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        adapter_root / "match_bundle_bridge_plan.json",
        {"bridgeSmokeReady": ready, "targetNextLever": "football_external_soccertrack_match_bundle_bridge_smoke"},
    )
    return candidate_root


def test_soccertrack_match_bundle_bridge_smoke_writes_match_bundle_compatible_external_bundle(tmp_path: Path) -> None:
    candidate_root = _write_adapter_outputs(tmp_path)

    payload = bridge.run_football_external_soccertrack_match_bundle_bridge_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_match_bundle_bridge_smoke_v1"
    bundle = json.loads((output_root / "soccertrack_external_match_bundle.json").read_text(encoding="utf-8"))
    audit = json.loads((output_root / "match_bundle_bridge_contract_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedMatchId"] == "117092"
    assert payload["matchBundleBridgeReady"] is True
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_product_route_smoke"
    assert payload["trainingExecuted"] is False
    assert bundle["schemaVersion"] == "match_bundle_v1"
    assert bundle["match"]["id"] == "soccertrack:117092"
    assert len(bundle["events"]) == 2
    assert len(bundle["frames"]) == 2
    assert bundle["provenance"]["externalDataset"] == "soccertrack_v2"
    assert bundle["provenance"]["groundTruthReferenceOnly"] is True
    assert bundle["provenance"]["referenceLabelsUsedForInference"] is False
    assert bundle["artifactAvailability"]["gsrGroundTruth"] is True
    assert bundle["frames"][0]["source"] == "soccertrack_gsr_ground_truth"
    assert bundle["frames"][0]["referenceOnly"] is True
    assert bundle["frames"][0]["players"][0]["pitchPositionMeters"] == {"x": -52.5, "y": 34.0}
    assert bundle["frames"][0]["players"][0]["x"] == 0.0
    assert bundle["frames"][0]["players"][0]["y"] == 0.0
    assert bundle["frames"][0]["players"][0]["sourceTeam"] == "left"
    assert bundle["frames"][0]["frameId"] != bundle["frames"][1]["frameId"]
    assert audit["bundleContractPassed"] is True


def test_soccertrack_match_bundle_bridge_smoke_blocks_without_adapter_truth(tmp_path: Path) -> None:
    _write_adapter_outputs(tmp_path, ready=False)

    payload = bridge.run_football_external_soccertrack_match_bundle_bridge_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_adapter_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_adapter_smoke_test"


def test_soccertrack_match_bundle_bridge_smoke_blocks_bundle_contract_gap(tmp_path: Path) -> None:
    _write_adapter_outputs(tmp_path, missing_events=True)

    payload = bridge.run_football_external_soccertrack_match_bundle_bridge_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_match_bundle_contract_gap"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_match_bundle_bridge_repair"


def test_soccertrack_match_bundle_bridge_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_adapter_outputs(tmp_path)

    payload = bridge.run_football_external_soccertrack_match_bundle_bridge_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_external_match_bundle_bridge",
        "soccertrack_match_bundle_bridge_contract_repair",
        "soccertrack_match_bundle_bridge_blocker_summary",
    ]
