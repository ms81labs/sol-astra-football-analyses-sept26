from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_product_route_smoke as route_smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_bridge_outputs(tmp_path: Path, *, ready: bool = True, malformed_bundle: bool = False) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    bridge_root = candidate_root / "football_external_soccertrack_match_bundle_bridge_smoke_v1"
    _write_json(
        bridge_root / "soccertrack_match_bundle_bridge_summary.json",
        {
            "batchName": "football_external_soccertrack_match_bundle_bridge_smoke",
            "goalAchieved": ready,
            "primaryBlocker": None if ready else "bridge_failed",
            "selectedMatchId": "117092" if ready else None,
            "matchBundleBridgeReady": ready,
            "externalBundleEventCount": 1 if ready else 0,
            "externalBundleFrameCount": 1 if ready else 0,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_product_route_smoke",
        },
    )
    _write_json(
        bridge_root / "soccertrack_external_match_bundle.json",
        {
            "schemaVersion": "not_match_bundle_v1" if malformed_bundle else "match_bundle_v1",
            "match": {
                "id": "soccertrack:117092",
                "name": "SoccerTrack 117092",
                "inputMode": "external_soccertrack_fixture",
            },
            "provenance": {
                "externalDataset": "soccertrack_v2",
                "externalSourceMatchId": "117092",
                "runtimeDefaultMutationAllowed": False,
            },
            "artifactAvailability": {"frames": True, "events": True},
            "exports": {"matchJson": "/api/external/soccertrack/117092/export/match.json"},
            "frames": [{"frameId": 1, "timestamp": 0.04}],
            "analytics": {"summary": {"source": "soccertrack_adapter_smoke"}},
            "events": [{"id": "evt-1", "type": "PASS", "timestamp": 1.2}],
        },
    )
    return candidate_root


def test_soccertrack_product_route_smoke_writes_route_contract_artifacts(tmp_path: Path) -> None:
    candidate_root = _write_bridge_outputs(tmp_path)

    payload = route_smoke.run_football_external_soccertrack_product_route_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_product_route_smoke_v1"
    route_audit = json.loads((output_root / "product_route_response_audit.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "external_route_contract_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedMatchId"] == "117092"
    assert payload["routePath"] == "/api/external/soccertrack/117092/export/match.json"
    assert payload["productRouteSmokePassed"] is True
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_analysis_report_smoke"
    assert route_audit["routeStatusCode"] == 200
    assert contract["externalRouteContractPassed"] is True


def test_soccertrack_product_route_smoke_blocks_without_bridge_truth(tmp_path: Path) -> None:
    _write_bridge_outputs(tmp_path, ready=False)

    payload = route_smoke.run_football_external_soccertrack_product_route_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_match_bundle_bridge_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_match_bundle_bridge_smoke"


def test_soccertrack_product_route_smoke_blocks_route_contract_gap(tmp_path: Path) -> None:
    _write_bridge_outputs(tmp_path, malformed_bundle=True)

    payload = route_smoke.run_football_external_soccertrack_product_route_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_match_bundle_bridge_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_match_bundle_bridge_smoke"


def test_soccertrack_product_route_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_bridge_outputs(tmp_path)

    payload = route_smoke.run_football_external_soccertrack_product_route_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_external_product_route_smoke",
        "soccertrack_product_route_contract_repair",
        "soccertrack_product_route_blocker_summary",
    ]
