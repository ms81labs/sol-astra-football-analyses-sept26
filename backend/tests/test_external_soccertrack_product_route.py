from __future__ import annotations

import json
from pathlib import Path

import anyio
import httpx

from backend.app.main import create_app


def _run(coro, *args):
    return anyio.run(coro, *args)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bridge_root(storage_root: Path) -> Path:
    return (
        storage_root
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "football_external_soccertrack_match_bundle_bridge_smoke_v1"
    )


def _write_bridge_bundle(storage_root: Path, *, match_id: str = "117092") -> Path:
    bridge_root = _bridge_root(storage_root)
    _write_json(
        bridge_root / "soccertrack_external_match_bundle.json",
        {
            "schemaVersion": "match_bundle_v1",
            "match": {
                "id": f"soccertrack:{match_id}",
                "name": f"SoccerTrack {match_id}",
                "inputMode": "external_soccertrack_fixture",
            },
            "provenance": {
                "externalDataset": "soccertrack_v2",
                "externalSourceMatchId": match_id,
                "runtimeDefaultMutationAllowed": False,
                "groundTruthReferenceOnly": True,
                "referenceLabelsUsedForInference": False,
            },
            "artifactAvailability": {"frames": True, "events": True, "gsrGroundTruth": True},
            "exports": {"matchJson": f"/api/external/soccertrack/{match_id}/export/match.json"},
            "frames": [
                {
                    "frameId": 1,
                    "timestamp": 0.04,
                    "ball": None,
                    "source": "soccertrack_gsr_ground_truth",
                    "referenceOnly": True,
                    "players": [
                        {
                            "id": 7,
                            "x": 50.0,
                            "y": 50.0,
                            "pitchPositionMeters": {"x": 0.0, "y": 0.0},
                            "sourceTeam": "left",
                        }
                    ],
                }
            ],
            "analytics": {"summary": {"source": "soccertrack_adapter_smoke"}},
            "events": [{"id": "evt-1", "type": "PASS", "timestamp": 1.2}],
        },
    )
    return bridge_root


async def _client(storage_root: Path):
    app = create_app(storage_root=storage_root)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1")


def test_external_soccertrack_match_bundle_route_serves_saved_bridge_bundle(tmp_path: Path) -> None:
    _run(_test_external_soccertrack_match_bundle_route_serves_saved_bridge_bundle, tmp_path)


async def _test_external_soccertrack_match_bundle_route_serves_saved_bridge_bundle(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    _write_bridge_bundle(storage_root)

    async with await _client(storage_root) as client:
        response = await client.get("/api/external/soccertrack/117092/export/match.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == "match_bundle_v1"
    assert payload["match"]["id"] == "soccertrack:117092"
    assert payload["provenance"]["externalDataset"] == "soccertrack_v2"
    assert payload["provenance"]["runtimeDefaultMutationAllowed"] is False
    assert payload["provenance"]["groundTruthReferenceOnly"] is True
    assert payload["provenance"]["referenceLabelsUsedForInference"] is False
    assert payload["artifactAvailability"]["gsrGroundTruth"] is True
    assert payload["frames"][0]["players"][0]["pitchPositionMeters"] == {"x": 0.0, "y": 0.0}
    assert payload["exports"]["matchJson"] == "/api/external/soccertrack/117092/export/match.json"
    assert len(payload["events"]) == 1
    assert len(payload["frames"]) == 1


def test_external_soccertrack_match_bundle_route_fails_closed_without_bridge_bundle(tmp_path: Path) -> None:
    _run(_test_external_soccertrack_match_bundle_route_fails_closed_without_bridge_bundle, tmp_path)


async def _test_external_soccertrack_match_bundle_route_fails_closed_without_bridge_bundle(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"

    async with await _client(storage_root) as client:
        response = await client.get("/api/external/soccertrack/117092/export/match.json")

    assert response.status_code == 404
    assert response.json()["detail"] == "SoccerTrack external match bundle bridge not ready"


def test_external_soccertrack_match_bundle_route_rejects_mismatched_match_id(tmp_path: Path) -> None:
    _run(_test_external_soccertrack_match_bundle_route_rejects_mismatched_match_id, tmp_path)


async def _test_external_soccertrack_match_bundle_route_rejects_mismatched_match_id(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    _write_bridge_bundle(storage_root, match_id="117092")

    async with await _client(storage_root) as client:
        response = await client.get("/api/external/soccertrack/999999/export/match.json")

    assert response.status_code == 404
    assert response.json()["detail"] == "SoccerTrack external match bundle not found"
