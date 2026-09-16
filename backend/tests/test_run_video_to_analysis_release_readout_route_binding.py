from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_release_readout_route_binding as route_binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_release_readout_pack(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_release_readout_pack_v1"
    _write_json(
        root / "release_readout_pack_summary.json",
        {
            "batchName": "video_to_analysis_release_readout_pack",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "releaseReadoutPackReady": True,
            "growthLaneCloseoutSnapshot": "video_to_analysis_next_sample_selection_snapshot_v38",
            "externalBenchmarkProductBindingReady": True,
            "runtimeOperationallyComplete": True,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_next_strategic_lane_selection",
        },
    )
    _write_json(
        root / "release_readout_manifest.json",
        {
            "schemaVersion": "video_to_analysis_release_readout_manifest_v1",
            "latestSnapshot": "video_to_analysis_next_sample_selection_snapshot_v38",
            "activeQueueCandidateIds": [
                "operator_uploaded_local_video_replenishment_candidate_v23",
                "soccernet_bounded_224p_member_replenishment_candidate_v23",
                "existing_normal_storage_video_replenishment_candidate_v23",
            ],
            "runtimeOperationallyComplete": True,
            "externalBenchmarkProductBindingReady": True,
        },
    )
    _write_json(
        root / "next_strategic_lane_matrix.json",
        {
            "schemaVersion": "video_to_analysis_next_strategic_lane_matrix_v1",
            "recommendedLane": "external_benchmark_expansion_or_release_readout",
            "candidateStrategicLanes": [
                {"id": "external_benchmark_expansion", "label": "External benchmark expansion"},
                {"id": "user_facing_release_readout", "label": "User-facing release/readout"},
            ],
        },
    )
    _write_json(root / "guardrail_audit.json", {"allMutationGuardrailsPreserved": True})
    (root / "operator_release_brief.md").write_text("# Video-to-analysis release readout\n\nv38\n", encoding="utf-8")


def test_release_readout_route_binding_serves_api_and_html(tmp_path: Path) -> None:
    _seed_release_readout_pack(tmp_path)

    payload = route_binding.run_video_to_analysis_release_readout_route_binding(storage_root=tmp_path)

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/release-readout")
            html_response = await client.get("/video-to-analysis/release-readout")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["releaseReadoutRouteReady"] is True
    assert payload["apiRouteStatusCode"] == 200
    assert payload["htmlRouteStatusCode"] == 200
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_next_strategic_lane_selection"
    assert api_payload["schemaVersion"] == "video_to_analysis_release_readout_view_model_v1"
    assert api_payload["latestSnapshot"] == "video_to_analysis_next_sample_selection_snapshot_v38"
    assert api_payload["guardrails"]["trainingExecuted"] is False
    assert "Video-to-analysis release readout" in html
    assert "v38" in html


def test_release_readout_route_binding_blocks_without_pack(tmp_path: Path) -> None:
    payload = route_binding.run_video_to_analysis_release_readout_route_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_release_readout_pack_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_readout_pack"
